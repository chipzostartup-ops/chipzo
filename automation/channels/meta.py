#!/usr/bin/env python3
"""Facebook Page + Instagram publishing via Meta Graph API (free).

Requires a Meta app with the right permissions. See SETUP-FREE-STACK.md.
Rate limit: 25 IG posts / 24h. Page feed: generous.

    python automation/channels/meta.py --fb "hello world"
    python automation/channels/meta.py --ig https://example.com/img.jpg "caption"
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import load_config  # noqa: E402

GRAPH = "https://graph.facebook.com/v21.0"


def _post(path: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Graph API {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Graph API network error: {exc.reason}") from exc


def _get(path: str, params: dict) -> dict:
    url = f"{GRAPH}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Graph API {exc.code}: {detail}") from exc


def fb_post(message: str, link: str | None = None, cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    conf = cfg.get("facebook", {})
    if not conf.get("page_id") or not conf.get("page_token"):
        raise RuntimeError("facebook.page_id / page_token missing")
    params = {"message": message, "access_token": conf["page_token"]}
    if link:
        params["link"] = link
    return _post(f"{conf['page_id']}/feed", params)


def ig_publish(image_url: str, caption: str, cfg: dict | None = None) -> dict:
    """Single-image publish. image_url MUST be a public HTTPS URL."""
    cfg = cfg or load_config()
    conf = cfg.get("instagram", {})
    if not conf.get("ig_user_id") or not conf.get("page_token"):
        raise RuntimeError("instagram.ig_user_id / page_token missing")

    container = _post(
        f"{conf['ig_user_id']}/media",
        {
            "image_url": image_url,
            "caption": caption[:2200],
            "access_token": conf["page_token"],
        },
    )
    creation_id = container["id"]

    # Meta needs a moment to ingest the media
    for _ in range(10):
        time.sleep(3)
        status = _get(creation_id, {"fields": "status_code", "access_token": conf["page_token"]})
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") == "ERROR":
            raise RuntimeError(f"IG container failed: {status}")

    return _post(
        f"{conf['ig_user_id']}/media_publish",
        {"creation_id": creation_id, "access_token": conf["page_token"]},
    )


def ig_carousel(image_urls: list[str], caption: str, cfg: dict | None = None) -> dict:
    """2-10 public image URLs."""
    cfg = cfg or load_config()
    conf = cfg.get("instagram", {})
    if not 2 <= len(image_urls) <= 10:
        raise RuntimeError("carousel needs 2-10 images")

    children = []
    for url in image_urls:
        child = _post(
            f"{conf['ig_user_id']}/media",
            {
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": conf["page_token"],
            },
        )
        children.append(child["id"])

    container = _post(
        f"{conf['ig_user_id']}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption[:2200],
            "access_token": conf["page_token"],
        },
    )
    time.sleep(10)
    return _post(
        f"{conf['ig_user_id']}/media_publish",
        {"creation_id": container["id"], "access_token": conf["page_token"]},
    )


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Facebook / Instagram publisher")
    ap.add_argument("--fb", metavar="MESSAGE")
    ap.add_argument("--link")
    ap.add_argument("--ig", nargs=2, metavar=("IMAGE_URL", "CAPTION"))
    args = ap.parse_args()

    try:
        if args.fb:
            res = fb_post(args.fb, args.link)
            print(f"OK: Facebook post id {res.get('id')}")
        elif args.ig:
            res = ig_publish(args.ig[0], args.ig[1])
            print(f"OK: Instagram media id {res.get('id')}")
        else:
            ap.print_help()
            return 1
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
