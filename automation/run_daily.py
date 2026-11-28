#!/usr/bin/env python3
"""
DAILY DISPATCHER — the cron entry point.

    python automation/run_daily.py --dry-run        # preview, sends nothing
    python automation/run_daily.py                  # publish everything due now
    python automation/run_daily.py --platform telegram
    python automation/run_daily.py --catchup 3      # ignore schedule, oldest 3
    python automation/run_daily.py --manual-report  # list what needs copy-paste

Exit code is 1 if any item failed, so GitHub Actions shows red.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from channels import blogger, buffer, email_brevo, gmail_bulk, meta, telegram  # noqa: E402
import links  # noqa: E402
from common import (  # noqa: E402
    DRAFTS,
    ROOT,
    STATE,
    load_config,
    now_utc,
    parse_dt,
    read_json,
    write_json,
    write_text,
)

QUEUE_PATH = STATE / "queue.json"
REPORT_PATH = STATE / "manual_tasks.md"

AUTOMATED = {"blog", "telegram", "facebook", "instagram", "email"}

# Channels the whole pipeline is built around. If one of these is switched off
# while items are due, the run must go red — otherwise it "succeeds" for days
# while nothing is actually published.
CORE_CHANNELS = {"blog", "telegram"}

# platform -> config section whose "enabled" flag decides if we can send
SECTION = {
    "telegram": "telegram",
    "blog": "blogger",
    "facebook": "buffer",
    "linkedin": "buffer",
    "x_thread": "buffer",
    "email": "email",
    "instagram_carousel": "instagram",
    "instagram_reel": "instagram",
    "whatsapp": "whatsapp",
}


def can_send(item: dict, cfg: dict) -> bool:
    """A platform with no connected account must be handled by hand, not retried."""
    platform = item["platform"]
    buffer_on = bool(cfg.get("buffer", {}).get("enabled"))

    # Buffer covers LinkedIn, X and Facebook. Without it, LinkedIn and X have
    # no free API at all, and Facebook falls back to Meta's own token.
    if platform in buffer.PLATFORMS:
        if not buffer_on:
            if platform == "facebook":
                return bool(cfg.get("facebook", {}).get("enabled"))
            return False
        ready = cfg.get("_buffer_ready")
        # A Buffer key does not guarantee every network is connected; an
        # unconnected one is a chore for a human, not a failed send.
        return platform in ready if ready is not None else True

    section = SECTION.get(platform)
    if not section:
        return False
    return bool(cfg.get(section, {}).get("enabled"))


# No free API exists for these, so a human has to paste them. Everything else
# that is switched off is a fault worth reporting, not a chore worth listing.
HUMAN_ONLY = {"whatsapp", "instagram_reel"}


def is_manual(item: dict, cfg: dict) -> bool:
    """Decide from *current* config, never from the flag stored in the queue.

    The stored flag goes stale the moment a channel is connected or switched
    off, and a stale flag silently skips a channel that could be publishing.
    """
    platform = item["platform"]
    if platform in HUMAN_ONLY:
        return True
    if platform in buffer.PLATFORMS and cfg.get("buffer", {}).get("enabled"):
        ready = cfg.get("_buffer_ready")
        return ready is not None and platform not in ready
    return not can_send(item, cfg)


def read_queue() -> dict:
    q = read_json(QUEUE_PATH, {})
    if not q or "items" not in q:
        raise SystemExit("No queue found. Run: python automation/queue.py build")
    return q


def manual_report(items: list[dict]) -> str:
    lines = ["# Manual publishing tasks\n", "Platforms with no free API. Copy, paste, done.\n"]
    for i in items:
        lines.append(f"## {i['title']}")
        lines.append(f"- Platform: **{i['platform']}**")
        lines.append(f"- Scheduled: {i['scheduled_at'][:16]}")
        lines.append(f"- File: `{i['file']}`")
        lines.append(f"- Mark done: `python automation/queue.py done {i['id']}`\n")
    lines.append("\nTip: `python automation/channels/clipboard.py <file>` copies it for you.")
    return "\n".join(lines)


def dispatch(item: dict, cfg: dict) -> None:
    path = ROOT / item["file"]
    if not path.exists():
        raise RuntimeError(f"missing file: {item['file']}")
    text = path.read_text(encoding="utf-8")

    if item["platform"] in buffer.PLATFORMS and cfg.get("buffer", {}).get("enabled"):
        # Queued with its planned time so LinkedIn/X/Facebook land on the same
        # schedule the rest of the pipeline uses. Instagram needs its slides.
        if item["platform"] == "instagram_carousel":
            buffer.send_carousel(item["slug"], cfg=cfg, due_at=item["scheduled_at"])
        else:
            buffer.send_file(item["platform"], path, cfg=cfg, due_at=item["scheduled_at"])
    elif item["platform"] == "telegram":
        telegram.send(text, cfg)
    elif item["platform"] == "blog":
        blogger.send_post(path, cfg)
    elif item["platform"] == "facebook":
        meta.fb_post(text, cfg=cfg)
    elif item["platform"] == "email":
        if item.get("slug") == "_digest":
            # Links to posts that went live minutes ago are only known now.
            from digest import refresh as refresh_digest

            day = date.fromisoformat(item["id"].split(":", 1)[1])
            rebuilt = refresh_digest(day, cfg)
            if rebuilt:
                path = ROOT / rebuilt
        provider = (cfg.get("email", {}).get("provider") or "brevo").lower()
        if provider == "gmail":
            gmail_bulk.send(path, cfg)
        else:
            email_brevo.send(path, cfg)
    elif item["platform"].startswith("instagram"):
        raise RuntimeError(
            "Instagram needs a public image URL. Publish manually from instagram_carousel.txt "
            "or extend channels/meta.py:ig_publish with your own image host."
        )
    else:
        raise RuntimeError(f"no automated sender for {item['platform']}")


def refresh_after_publish(slug: str, cfg: dict) -> None:
    """Blogger just created a post. Learn its real URL and regenerate the rest."""
    try:
        links.invalidate()
        links.sync(verbose=False)
    except Exception as exc:  # noqa: BLE001
        print(f"          (link sync skipped: {exc})")
        return

    manifest = read_json(ROOT / "content" / "out" / slug / "manifest.json", {}) or {}
    source = manifest.get("source")
    if not source:
        return
    try:
        import repurpose

        links.invalidate()
        repurpose.process(DRAFTS / source, cfg, force=True)
        print("          (platform files regenerated with the real URL)")
    except Exception as exc:  # noqa: BLE001
        print(f"          (regenerate skipped: {exc})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish everything that is due")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--platform", action="append", help="only this platform (repeatable)")
    ap.add_argument("--catchup", type=int, default=0, help="publish the N oldest pending items now")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--tolerance-min", type=int, default=0, help="publish items due within N minutes")
    ap.add_argument("--manual-report", action="store_true", help="only write the manual task list")
    ap.add_argument("--reset-failed", action="store_true", help="retry previously failed items")
    args = ap.parse_args()

    cfg = load_config()
    dry = args.dry_run or cfg.get("publish", {}).get("dry_run", True)

    # One channel lookup per run, not one per item. A Buffer platform with no
    # channel is a chore for a human; a bad key is a configuration fault.
    config_error = ""
    if cfg.get("buffer", {}).get("enabled"):
        try:
            cfg["_buffer_ready"] = buffer.ready_platforms(cfg)
        except RuntimeError as exc:
            config_error = f"buffer: {exc}"
            cfg["_buffer_ready"] = set()
        missing = [p for p in buffer.PLATFORMS if p not in cfg["_buffer_ready"]]
        if missing and not config_error:
            print(f"Buffer: no channel for {', '.join(missing)} yet - those stay manual")

    queue = read_queue()
    items = queue["items"]
    now = now_utc()
    cutoff = now + timedelta(minutes=args.tolerance_min)

    if args.reset_failed:
        for i in items:
            if i["status"] == "failed":
                i["status"] = "pending"

    pending = [i for i in items if i["status"] == "pending"]
    if args.platform:
        pending = [i for i in pending if i["platform"] in args.platform]

    if args.catchup:
        due = pending[: args.catchup]
    else:
        within = [i for i in pending if parse_dt(i["scheduled_at"]) <= cutoff]
        # Manual platforms are reported, never sent, so they must not eat the
        # send budget. With a flat slice, six skipped LinkedIn/WhatsApp rows
        # could crowd the one blog post out of the run entirely.
        auto = [i for i in within if not is_manual(i, cfg)]
        manual_slice = [i for i in within if is_manual(i, cfg)]
        due = auto[: args.limit] + manual_slice

    manual_due = [i for i in due if is_manual(i, cfg) and i["platform"] != "instagram_carousel"]

    if args.manual_report:
        write_text(REPORT_PATH, manual_report(manual_due))
        print(f"wrote {REPORT_PATH} ({len(manual_due)} manual tasks)")
        return 0

    print(f"Now: {now.isoformat(timespec='seconds')}")
    print(f"Dry run: {dry}")
    print(f"Due: {len(due)} item(s)\n")
    sent = skipped = failed = 0
    blocked: dict[str, int] = {}
    for item in due:
        label = f"{item['platform']:<20}{item['title'][:46]}"

        if is_manual(item, cfg):
            human = item["platform"] in HUMAN_ONLY
            if not human:
                # Automated platform with no working account. Silence here is
                # what let the blog go unpublished for days while every run
                # still reported success.
                blocked[item["platform"]] = blocked.get(item["platform"], 0) + 1
            print(f"  MANUAL  {label}{'' if human else '  (not connected)'}")
            skipped += 1
            continue

        if dry:
            print(f"  WOULD   {label}")
            sent += 1
            continue

        try:
            dispatch(item, cfg)
            item["status"] = "sent"
            item["sent_at"] = now.isoformat(timespec="seconds")
            item["attempts"] = item.get("attempts", 0) + 1
            item["last_error"] = ""
            print(f"  OK      {label}")
            sent += 1
            if item["platform"] == "blog":
                refresh_after_publish(item["slug"], cfg)
        except Exception as exc:  # noqa: BLE001 - keep the run alive
            item["status"] = "failed"
            item["attempts"] = item.get("attempts", 0) + 1
            item["last_error"] = str(exc)[:400]
            print(f"  FAILED  {label}")
            print(f"          -> {exc}")
            failed += 1

    if not dry:
        queue["items"] = items
        queue["updated_at"] = now.isoformat(timespec="seconds")
        write_json(QUEUE_PATH, queue)

    if manual_due:
        write_text(REPORT_PATH, manual_report(manual_due))
        print(f"\n{len(manual_due)} manual task(s) written to {REPORT_PATH}")

    # A core channel that is switched off is a configuration bug, not a
    # scheduling detail: those items can never publish on their own.
    deaf = {p: n for p, n in blocked.items() if p in CORE_CHANNELS}
    for platform, count in sorted(blocked.items()):
        if platform in deaf:
            print(f"::error::{platform}: {count} item(s) due but the channel is not connected")
        else:
            print(f"::warning::{platform}: {count} item(s) due but not connected - skipped")
    if deaf:
        print("   fix the missing secret, then: python automation/queue.py reschedule")

    if config_error:
        print(f"::error::{config_error}")
        print("   fix the credential, then: python automation/queue.py reschedule")

    print(f"\nSummary: {sent} {'would send' if dry else 'sent'}, {skipped} manual, {failed} failed")
    return 1 if failed or deaf or config_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
