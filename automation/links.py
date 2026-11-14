#!/usr/bin/env python3
"""
Resolve the real published URL of each post.

Blogger does not use the file name. It builds
    /<year>/<month>/<slug-from-title>.html
so the URL cannot be predicted before publishing. This module asks Blogger's
public feed what the URL actually is, and caches the answer.

    python automation/links.py sync      # refresh the cache
    python automation/links.py show      # what is known
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import OUT, STATE, load_config, read_json, slugify, write_json  # noqa: E402

LINKS_PATH = STATE / "links.json"


def _normalise(text: str) -> str:
    text = re.sub(r"&[a-z]+;|&#\d+;", " ", text or "")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def fetch_feed(site: str) -> list[dict]:
    base = site.rstrip("/")
    url = f"{base}/feeds/posts/default?alt=json&max-results=150"
    req = urllib.request.Request(url, headers={"User-Agent": "chipzo-links/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"feed HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"feed network error: {exc.reason}") from exc

    entries = []
    for e in data.get("feed", {}).get("entry", []):
        link = next((l["href"] for l in e.get("link", []) if l.get("rel") == "alternate"), "")
        if not link:
            continue
        entries.append(
            {"title": e.get("title", {}).get("$t", ""), "url": link, "id": e.get("id", {}).get("$t", "")}
        )
    return entries


def sync(verbose: bool = True) -> dict:
    cfg = load_config()
    site = cfg["brand"]["site"]
    entries = fetch_feed(site)

    by_title = {_normalise(e["title"]): e["url"] for e in entries}
    mapping = read_json(LINKS_PATH, {}) or {}
    resolved = 0

    for path in OUT.glob("*/manifest.json"):
        manifest = read_json(path, {})
        if not isinstance(manifest, dict):
            continue
        slug = manifest.get("slug")
        title = manifest.get("title", "")
        if not slug:
            continue
        if mapping.get(slug):
            continue

        url = by_title.get(_normalise(title))
        if not url:
            # tolerate small title edits: match on the first 40 normalised chars
            key = _normalise(title)[:40]
            for norm, candidate in by_title.items():
                if norm.startswith(key):
                    url = candidate
                    break
        if url:
            mapping[slug] = url
            resolved += 1

    write_json(LINKS_PATH, mapping)
    if verbose:
        print(f"feed: {len(entries)} post(s) | resolved: {resolved} new | known: {len(mapping)}")
    return mapping


def resolve(slug: str) -> str | None:
    mapping = read_json(LINKS_PATH, {}) or {}
    return mapping.get(slug)


_CACHE: dict | None = None


def invalidate() -> None:
    global _CACHE
    _CACHE = None


def cached(slug: str) -> str | None:
    global _CACHE
    if _CACHE is None:
        _CACHE = read_json(LINKS_PATH, {}) or {}
    return _CACHE.get(slug)


def show() -> None:
    mapping = read_json(LINKS_PATH, {}) or {}
    if not mapping:
        print("nothing resolved yet - run: python automation/links.py sync")
        return
    for slug, url in mapping.items():
        print(f"{slug:<40} {url}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    try:
        if cmd == "sync":
            sync()
        elif cmd == "show":
            show()
        else:
            print(__doc__)
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        raise SystemExit(1)
