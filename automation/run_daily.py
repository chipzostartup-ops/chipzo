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
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from channels import blogger, email_brevo, meta, telegram  # noqa: E402
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

# platform -> config section whose "enabled" flag decides if we can send
SECTION = {
    "telegram": "telegram",
    "blog": "blogger",
    "facebook": "facebook",
    "email": "email",
    "instagram_carousel": "instagram",
    "instagram_reel": "instagram",
    "whatsapp": "whatsapp",
}


def can_send(item: dict, cfg: dict) -> bool:
    """A platform with no connected account must be handled by hand, not retried."""
    section = SECTION.get(item["platform"])
    if not section:
        return False
    return bool(cfg.get(section, {}).get("enabled"))


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

    if item["platform"] == "telegram":
        telegram.send(text, cfg)
    elif item["platform"] == "blog":
        blogger.send_post(path, cfg)
    elif item["platform"] == "facebook":
        meta.fb_post(text, cfg=cfg)
    elif item["platform"] == "email":
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
        due = [i for i in pending if parse_dt(i["scheduled_at"]) <= cutoff][: args.limit]

    manual_due = [i for i in due if i["manual"] and i["platform"] != "instagram_carousel"]

    if args.manual_report:
        write_text(REPORT_PATH, manual_report(manual_due))
        print(f"wrote {REPORT_PATH} ({len(manual_due)} manual tasks)")
        return 0

    print(f"Now: {now.isoformat(timespec='seconds')}")
    print(f"Dry run: {dry}")
    print(f"Due: {len(due)} item(s)\n")

    sent = skipped = failed = 0
    for item in due:
        label = f"{item['platform']:<20}{item['title'][:46]}"

        if item["manual"] or not can_send(item, cfg):
            reason = "" if item["manual"] else "  (not connected)"
            print(f"  MANUAL  {label}{reason}")
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

    print(f"\nSummary: {sent} {'would send' if dry else 'sent'}, {skipped} manual, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
