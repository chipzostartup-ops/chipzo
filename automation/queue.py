#!/usr/bin/env python3
"""
Build / refresh the publishing queue from generated content.

    python automation/queue.py build                  # 3 topics per week, starting today
    python automation/queue.py build --start 2026-12-01 --per-week 3
    python automation/queue.py build --reset          # wipe all statuses
    python automation/queue.py list                   # show what is coming up
    python automation/queue.py done <item-id>         # mark a manual task as done

The queue is a plain JSON file at automation/state/queue.json so you can edit it
by hand, in git, or from anything else.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    OUT,
    PY,
    STATE,
    load_config,
    now_utc,
    parse_dt,
    read_json,
    write_json,
)
from digest import write as write_digest  # noqa: E402

QUEUE_PATH = STATE / "queue.json"
IST = timezone(timedelta(hours=5, minutes=30))

# key, output file, local time (HH:MM), manual?
PLATFORMS = [
    ("linkedin",          "linkedin.txt",            "08:30", True),
    ("blog",              "blog.html",               "09:00", False),
    ("facebook",          "facebook.txt",            "12:30", False),
    ("telegram",          "telegram.md",             "18:30", False),
    ("whatsapp",          "whatsapp.txt",            "19:00", True),
    ("instagram_carousel","instagram_carousel.txt",  "20:00", True),
    ("instagram_reel",    "instagram_reel.txt",      "21:00", True),
    ("x_thread",          "x_thread.txt",            "21:30", True),
]

EMAIL_DAY = 0  # Monday (Monday=0) — one weekly digest, every Monday 10:00 IST

# Platforms Buffer publishes on our behalf. With a Buffer key configured these
# stop being "copy the file and paste it" chores and become scheduled sends.
BUFFER_PLATFORMS = {"linkedin", "facebook", "x_thread"}


def load_manifests() -> list[dict]:
    items = []
    for path in sorted(OUT.glob("*/manifest.json")):
        m = read_json(path, {})
        if isinstance(m, dict) and m.get("slug"):
            m["_dir"] = str(path.parent)
            items.append(m)
    items.sort(key=lambda m: (m.get("date", ""), m.get("slug", "")))
    return items


def build(start: date, per_week: int, reset: bool) -> None:
    cfg = load_config()
    buffer_on = bool(cfg.get("buffer", {}).get("enabled"))
    queue = {"updated_at": "", "items": []} if reset else (read_json(QUEUE_PATH, {}) or {"items": []})
    old = {i["id"]: i for i in queue.get("items", [])}

    manifests = load_manifests()
    if not manifests:
        print("No generated content found. Run: python automation/repurpose.py --all")
        return

    per_week = max(1, min(7, per_week))
    step_days = 7 / per_week

    # Slugs already in the queue keep their existing schedule. New slugs are
    # appended AFTER the last scheduled item so a rebuild never dumps a pile of
    # posts onto today.
    known = {i.get("slug") for i in old.values()}
    new_slugs = [m["slug"] for m in manifests if m["slug"] not in known]

    if old and not reset:
        anchor = max(parse_dt(i["scheduled_at"]).date() for i in old.values()) + timedelta(days=1)
        anchor = max(anchor, start)
    else:
        anchor = start

    new_index = {slug: n for n, slug in enumerate(new_slugs)}
    existing_base: dict[str, date] = {}
    for i in old.values():
        slug = i.get("slug")
        if slug and slug not in existing_base:
            existing_base[slug] = parse_dt(i["scheduled_at"]).date()

    items: list[dict] = []
    slug_day: dict[str, date] = {}
    for idx, m in enumerate(manifests):
        if m["slug"] in existing_base:
            base_day = existing_base[m["slug"]]
        else:
            offset = round(new_index.get(m["slug"], 0) * step_days)
            base_day = anchor + timedelta(days=offset)
        slug_day[m["slug"]] = base_day

        base = datetime.combine(base_day, datetime.min.time(), tzinfo=IST)
        for key, filename, hhmm, manual in PLATFORMS:
            h, mi = (int(x) for x in hhmm.split(":"))
            when = base.replace(hour=h, minute=mi)

            # priority platforms are every topic; secondary ones on alternating topics
            if key in {"instagram_carousel", "instagram_reel", "x_thread"} and idx % 3 != 0:
                continue

            item_id = f"{m['slug']}:{key}"
            prev = old.get(item_id, {})
            # keep existing schedule if already dispatched
            scheduled = prev.get("scheduled_at") or when.isoformat()
            items.append(
                {
                    "id": item_id,
                    "slug": m["slug"],
                    "title": m.get("title", m["slug"]),
                    "platform": key,
                    "file": f"content/out/{m['slug']}/{filename}",
                    "scheduled_at": scheduled,
                    "status": prev.get("status", "pending"),
                    "manual": bool(manual and not (buffer_on and key in BUFFER_PLATFORMS)),
                    "attempts": prev.get("attempts", 0),
                    "last_error": prev.get("last_error", ""),
                    "sent_at": prev.get("sent_at", ""),
                }
            )

        # The weekly digest is built once per week below, not per post, so it
        # still goes out on a Monday when no article happens to be scheduled.

    # --- weekly digest: one email every Monday, whatever the posting schedule
    if slug_day:
        by_slug = {m["slug"]: m for m in manifests}
        first_day, last_day = min(slug_day.values()), max(slug_day.values())
        monday = first_day + timedelta(days=(EMAIL_DAY - first_day.weekday()) % 7)

        while monday <= last_day:
            # A Monday that has already gone by is dead weight: the dispatcher
            # will never send it, and it sits in the queue as permanently
            # overdue. Only schedule digests that can still go out.
            if monday < date.today():
                monday += timedelta(days=7)
                continue

            week = [
                by_slug[slug]
                for slug, day in slug_day.items()
                if monday - timedelta(days=6) <= day <= monday
            ]
            week.sort(key=lambda m: m.get("date", ""))

            digest_file = write_digest(monday, week, cfg)
            if digest_file:
                item_id = f"digest:{monday.isoformat()}"
                prev = old.get(item_id, {})
                when = datetime.combine(monday, datetime.min.time(), tzinfo=IST).replace(hour=10, minute=0)
                items.append(
                    {
                        "id": item_id,
                        "slug": "_digest",
                        "title": f"Weekly digest - {len(week)} article(s)",
                        "platform": "email",
                        "file": digest_file,
                        "scheduled_at": prev.get("scheduled_at") or when.isoformat(),
                        "status": prev.get("status", "pending"),
                        "manual": False,
                        "attempts": prev.get("attempts", 0),
                        "last_error": prev.get("last_error", ""),
                        "sent_at": prev.get("sent_at", ""),
                    }
                )
            monday += timedelta(days=7)

    items.sort(key=lambda i: (i["scheduled_at"], i["slug"], i["platform"]))
    queue = {"updated_at": now_utc().isoformat(timespec="seconds"), "items": items}
    write_json(QUEUE_PATH, queue)

    pending = sum(1 for i in items if i["status"] == "pending")
    print(f"Queue built: {len(items)} items, {pending} pending")
    print(f"  {QUEUE_PATH}")
    first = items[0]["scheduled_at"][:16] if items else "-"
    last = items[-1]["scheduled_at"][:16] if items else "-"
    print(f"  window: {first} -> {last}")
    print(f"  {PY} automation/dashboard.py   (visual)  /  {PY} automation/run_daily.py --dry-run")


def reschedule(start: date, per_week: int) -> None:
    """Move every unsent post to a future slot, keeping sent history intact.

    `build()` deliberately never moves a slug it has seen before, which is right
    day to day but leaves the schedule stranded after an outage: every slot is
    in the past, the dispatcher's tolerance excludes them, and nothing ever
    publishes again. This shifts the backlog forward instead.
    """
    queue = read_json(QUEUE_PATH, {}) or {}
    items = queue.get("items", [])
    if not items:
        print("Queue is empty. Run: python automation/queue.py build")
        return

    per_week = max(1, min(7, per_week))
    step_days = 7 / per_week

    # first scheduled day per slug, ignoring the digest pseudo-slug
    base_day: dict[str, date] = {}
    for i in items:
        slug = i.get("slug")
        if slug and slug != "_digest" and slug not in base_day:
            base_day[slug] = parse_dt(i["scheduled_at"]).date()

    # `failed` means it never went out, so it belongs in the backlog too.
    retryable = {"pending", "failed"}
    pending_slugs = {
        i["slug"] for i in items if i["status"] in retryable and i.get("slug") not in (None, "_digest")
    }
    todo = sorted((s for s in base_day if s in pending_slugs), key=lambda s: base_day[s])
    if not todo:
        print("Nothing to reschedule: every post has already been sent.")
        return

    moved = 0
    for idx, slug in enumerate(todo):
        new_day = start + timedelta(days=round(idx * step_days))
        delta = new_day - base_day[slug]
        for i in items:
            if i.get("slug") != slug:
                continue
            if i["status"] not in retryable:
                continue  # never rewrite history
            i["scheduled_at"] = (parse_dt(i["scheduled_at"]) + delta).isoformat()
            i["status"] = "pending"  # a failed item gets a fresh attempt
            i["last_error"] = ""
            moved += 1

    # Stale digests carry their date in the id; `build` regenerates them.
    dropped = [i["id"] for i in items if i.get("slug") == "_digest" and i["status"] == "pending"]
    items = [i for i in items if i["id"] not in dropped]

    items.sort(key=lambda i: (i["scheduled_at"], i["slug"], i["platform"]))
    queue["items"] = items
    queue["updated_at"] = now_utc().isoformat(timespec="seconds")
    write_json(QUEUE_PATH, queue)

    print(f"Rescheduled {moved} item(s) across {len(todo)} post(s) from {start.isoformat()}")
    print(f"  dropped {len(dropped)} stale digest item(s); run `build` to regenerate")
    for slug in todo:
        days = [i["scheduled_at"][:10] for i in items if i.get("slug") == slug]
        print(f"  {slug:<34}{min(days) if days else '-'}")


def show_list(limit: int = 25) -> None:
    queue = read_json(QUEUE_PATH, {}) or {}
    items = queue.get("items", [])
    if not items:
        print("Queue is empty. Run: python automation/queue.py build")
        return
    upcoming = [i for i in items if i["status"] == "pending"][:limit]
    print(f"{'SCHEDULED':<17}{'PLATFORM':<20}{'STATUS':<9}TITLE")
    print("-" * 100)
    for i in upcoming:
        mark = "manual" if i["manual"] else ""
        print(f"{i['scheduled_at'][:16]:<17}{i['platform']:<20}{i['status']:<9}{i['title'][:44]:<45}{mark}")


def mark_done(item_id: str) -> None:
    queue = read_json(QUEUE_PATH, {}) or {}
    found = False
    for i in queue.get("items", []):
        if i["id"] == item_id:
            i["status"] = "sent"
            i["sent_at"] = now_utc().isoformat(timespec="seconds")
            found = True
    if found:
        write_json(QUEUE_PATH, queue)
        print(f"marked done: {item_id}")
    else:
        print(f"not found: {item_id}")
        print("tip: python automation/queue.py list")


def main() -> int:
    ap = argparse.ArgumentParser(description="Chipzo publishing queue")
    sub = ap.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="(re)build the schedule")
    b.add_argument("--start", default=date.today().isoformat())
    b.add_argument("--per-week", type=int, default=3)
    b.add_argument("--reset", action="store_true", help="reset all statuses")

    lst = sub.add_parser("list", help="show upcoming items")
    lst.add_argument("--limit", type=int, default=25)

    d = sub.add_parser("done", help="mark a manual item as published")
    d.add_argument("item_id")

    rs = sub.add_parser("reschedule", help="move every unsent post to future slots")
    rs.add_argument("--start", default=(date.today() + timedelta(days=1)).isoformat())
    rs.add_argument("--per-week", type=int, default=3)

    args = ap.parse_args()
    if args.cmd == "build":
        build(date.fromisoformat(args.start), args.per_week, args.reset)
    elif args.cmd == "list":
        show_list(args.limit)
    elif args.cmd == "done":
        mark_done(args.item_id)
    elif args.cmd == "reschedule":
        reschedule(date.fromisoformat(args.start), args.per_week)
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
