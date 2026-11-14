#!/usr/bin/env python3
"""The Monday weekly digest.

Why this is its own module: a digest that is written once at queue-build time
carries guessed URLs for anything not yet published. Blogger only reveals a
post's real address after it goes live, so the digest must be rebuilt moments
before it is sent. Both the builder and the dispatcher need that logic, and
`queue` would shadow the stdlib module of the same name if run_daily imported
it directly.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import OUT, load_config, parse_dt, read_json, write_text  # noqa: E402

QUEUE_PATH = Path(__file__).resolve().parent / "state" / "queue.json"


def article_url(slug: str, cfg: dict) -> str:
    """The real Blogger URL once links.py has learned it, otherwise a best guess."""
    try:
        from links import cached

        url = cached(slug)
    except Exception:  # noqa: BLE001 - never block a send on link lookup
        url = None
    return url or f"{cfg['brand']['site'].rstrip('/')}/{slug}.html"


def render(day: date, week: list[dict], cfg: dict) -> str:
    brand = cfg["brand"]
    count = len(week)
    plural = "" if count == 1 else "s"

    bullets = "\n".join(
        f"- **[{m['title']}]({article_url(m['slug'], cfg)})** — {m.get('hook', '').strip()}"
        for m in week
    )
    first = week[0]
    site = brand["site"].rstrip("/")

    return f"""Subject: This week on Chipzo: {count} VLSI idea{plural} worth five minutes
Preview: {first.get('hook', '').strip()[:120]}

Hi,

{count} new article{plural} on the blog this week:

{bullets}

Start here: [{first['title']}]({article_url(first['slug'], cfg)})

Everything ever published: [{site}]({site})

— {brand['name']}
{brand['tagline']}

---

Reply STOP to unsubscribe."""


def write(day: date, week: list[dict], cfg: dict) -> str | None:
    """Write content/out/_digest/<date>.md. Returns a ROOT-relative path."""
    if not week:
        return None
    week = sorted(week, key=lambda m: m.get("date", ""))
    path = OUT / "_digest" / f"{day.isoformat()}.md"
    write_text(path, render(day, week, cfg))
    return path.relative_to(OUT.parent.parent).as_posix()


def refresh(day: date, cfg: dict | None = None) -> str | None:
    """Rebuild one digest from the live queue, so links point at real URLs."""
    cfg = cfg or load_config()
    queue = read_json(QUEUE_PATH, {}) or {}

    post_day: dict[str, date] = {}
    for item in queue.get("items", []):
        if item.get("platform") == "blog":
            post_day[item["slug"]] = parse_dt(item["scheduled_at"]).date()

    manifests: dict[str, dict] = {}
    for path in OUT.glob("*/manifest.json"):
        m = read_json(path, {})
        if isinstance(m, dict) and m.get("slug"):
            manifests[m["slug"]] = m

    week = [
        manifests[slug]
        for slug, when in post_day.items()
        if slug in manifests and day - timedelta(days=6) <= when <= day
    ]
    return write(day, week, cfg)
