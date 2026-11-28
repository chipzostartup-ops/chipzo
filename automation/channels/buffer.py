#!/usr/bin/env python3
"""Buffer publisher (GraphQL API, free plan, stdlib only).

Why this exists: LinkedIn, X and Facebook have no free API a cron job can use
without a registered app and a review process, so those three were "copy the
file and paste it" tasks. They were never done — 16 of them piled up in
manual_tasks.md while the blog published itself. Buffer's free plan (3 channels,
10 scheduled posts per channel, 1 API key) removes the human step entirely.

    python automation/channels/buffer.py --check
    python automation/channels/buffer.py --test linkedin
    python automation/channels/buffer.py --platform x_thread --file content/out/<slug>/x_thread.txt --dry-run

Auth: a personal API key from https://publish.buffer.com/settings/api
Read from BUFFER_API_KEY, then config.json's buffer.api_key, then a
`.buffer-key` file in the repo root (gitignored) so the key never has to be
typed into a config file by hand.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT, load_config, parse_dt  # noqa: E402

API = "https://api.buffer.com"
KEY_FILE = ROOT / ".buffer-key"

# platform (as used in the queue) -> Buffer's service name
SERVICE = {
    "linkedin": "linkedin",
    "facebook": "facebook",
    "x_thread": "twitter",
    "threads": "threads",
    "instagram_carousel": "instagram",
}

PLATFORMS = tuple(SERVICE)

# Buffer validates against the network's own limit, counted in UTF-16 units.
LIMITS = {"linkedin": 3000, "facebook": 5000, "twitter": 280, "threads": 500, "instagram": 2200}

# Where the rendered Instagram slides live once committed. Buffer accepts no
# uploads, so every asset has to be a public URL.
ASSETS_BASE = "https://raw.githubusercontent.com/chipzostartup-ops/chipzo/main/content/cards"

# Free-plan friendly: how much of a tweet we will keep when trimming.
ELLIPSIS = "…"


def api_key(cfg: dict | None = None) -> str:
    key = (cfg or {}).get("buffer", {}).get("api_key") or ""
    if not key:
        import os

        key = os.environ.get("BUFFER_API_KEY", "")
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError(
            "buffer.api_key missing — put your Buffer API key in BUFFER_API_KEY, "
            "config.json's buffer.api_key, or .buffer-key "
            "(create one at https://publish.buffer.com/settings/api)"
        )
    return key


def gql(query: str, variables: dict | None = None, cfg: dict | None = None) -> dict:
    payload = json.dumps({"query": query, **({"variables": variables} if variables else {})}).encode("utf-8")
    req = urllib.request.Request(
        API,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key(cfg)}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code in (401, 403):
            raise RuntimeError(f"Buffer rejected the API key ({exc.code}). Create a fresh one at publish.buffer.com/settings/api") from exc
        raise RuntimeError(f"Buffer HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Buffer network error: {exc.reason}") from exc

    if body.get("errors"):
        msg = "; ".join(e.get("message", "?") for e in body["errors"])
        raise RuntimeError(f"Buffer API error: {msg}")
    return body.get("data") or {}


def organizations(cfg: dict | None = None) -> list[dict]:
    data = gql("query { account { organizations { id name } } }", cfg=cfg)
    return data.get("account", {}).get("organizations", []) or []


def channels(cfg: dict | None = None) -> list[dict]:
    """Every channel on the account, flattened across organizations."""
    out: list[dict] = []
    for org in organizations(cfg):
        data = gql(
            "query($id: OrganizationId!) { channels(input: { organizationId: $id }) { id name service } }",
            {"id": org["id"]},
            cfg=cfg,
        )
        for ch in data.get("channels", []) or []:
            out.append({**ch, "organization_id": org["id"], "organization": org.get("name", "")})
    return out


def channel_map(cfg: dict | None = None) -> dict[str, dict]:
    """platform -> channel, honouring an explicit override in config."""
    found = channels(cfg)
    by_service: dict[str, dict] = {}
    for ch in found:
        by_service.setdefault((ch.get("service") or "").lower(), ch)

    override = ((cfg or load_config()).get("buffer", {}) or {}).get("channels", {}) or {}
    resolved: dict[str, dict] = {}
    for platform, service in SERVICE.items():
        if override.get(platform):
            match = next((c for c in found if c["id"] == override[platform]), None)
            if not match:
                raise RuntimeError(
                    f"buffer.channels.{platform} points at {override[platform]}, "
                    "which is not a channel on this Buffer account"
                )
            resolved[platform] = match
        elif service in by_service:
            resolved[platform] = by_service[service]
    return resolved


def utf16_len(text: str) -> int:
    """What Buffer counts: emoji and fancy unicode cost two units, not one."""
    return len(text.encode("utf-16-le")) // 2


def trim(text: str, limit: int) -> str:
    if utf16_len(text) <= limit:
        return text
    kept = text
    while kept and utf16_len(kept) + utf16_len(ELLIPSIS) > limit:
        kept = kept[:-1]
    return kept.rstrip() + ELLIPSIS


def split_thread(text: str) -> list[str]:
    """x_thread.txt is numbered tweets separated by ---. Buffer wants the bare text."""
    blocks = [b.strip() for b in text.split("\n---\n")]
    tweets: list[str] = []
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        # drop the "1/7" counter line, Buffer numbers nothing
        if lines and len(lines[0].strip()) <= 6 and "/" in lines[0] and lines[0].strip().replace("/", "").isdigit():
            lines = lines[1:]
        body = "\n".join(lines).strip()
        if body:
            tweets.append(trim(body, LIMITS["twitter"]))
    return tweets


def _due_at(value: datetime | str | None) -> str | None:
    if not value:
        return None
    when = parse_dt(value) if isinstance(value, str) else value
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id text dueAt status } }
    ... on MutationError { message }
  }
}
"""


def create_post(
    platform: str,
    text: str,
    cfg: dict | None = None,
    due_at: datetime | str | None = None,
    dry_run: bool = False,
    draft: bool = False,
    assets: list[str] | None = None,
    share_now: bool = False,
) -> dict:
    """Schedule one post on the Buffer channel that matches `platform`."""
    cfg = cfg or load_config()
    if platform not in SERVICE:
        raise RuntimeError(f"buffer has no mapping for {platform}")

    resolved = channel_map(cfg)
    channel = resolved.get(platform)
    if not channel:
        have = ", ".join(sorted({(c.get("service") or "?") for c in channels(cfg)})) or "none"
        raise RuntimeError(
            f"no Buffer channel for {platform} (service '{SERVICE[platform]}'). "
            f"Connected services: {have}. Connect it in Buffer, or set buffer.channels.{platform}."
        )

    service = (channel.get("service") or "").lower()
    limit = LIMITS.get(service, 3000)
    scheduled = _due_at(due_at)

    payload: dict = {
        "text": trim(text, limit),
        "channelId": channel["id"],
        "schedulingType": "automatic",
    }

    if assets:
        payload["assets"] = [{"image": {"url": url}} for url in assets]

    if platform == "x_thread":
        tweets = split_thread(text)
        if not tweets:
            raise RuntimeError("x_thread file produced no tweets")
        # Buffer treats the thread array as the source of truth; the top-level
        # text must repeat the first entry.
        payload["text"] = tweets[0]
        payload["metadata"] = {"twitter": {"thread": [{"text": t} for t in tweets]}}

    if platform == "instagram_carousel":
        # Two fields Buffer's docs omit: without a type it rejects the post, and
        # without shouldShareToFeed it rejects the metadata object.
        if not assets:
            raise RuntimeError("Instagram needs at least one public image URL")
        payload["metadata"] = {"instagram": {"type": "post", "shouldShareToFeed": True}}

    if share_now:
        payload["mode"] = "shareNow"
        payload.pop("dueAt", None)
    # A time in the past is rejected; let Buffer slot it instead of firing blind.
    elif scheduled and parse_dt(scheduled) > datetime.now(timezone.utc) + timedelta(minutes=5):
        payload["mode"] = "customScheduled"
        payload["dueAt"] = scheduled
    else:
        payload["mode"] = "addToQueue"

    if draft:
        # Leaves it in Buffer as a draft: proves the connection works without
        # publishing anything to the user's network.
        payload["mode"] = "addToQueue"
        payload.pop("dueAt", None)
        payload["saveToDraft"] = True

    if dry_run:
        return {"dry_run": True, "channel": channel.get("name"), "service": service, "input": payload}

    data = gql(POST_MUTATION, {"input": payload}, cfg=cfg)
    result = data.get("createPost") or {}
    if "message" in result:
        raise RuntimeError(f"Buffer refused the {platform} post: {result['message']}")
    post = result.get("post") or {}
    if not post.get("id"):
        raise RuntimeError(f"Buffer returned no post id: {json.dumps(result)[:200]}")
    return post


def send(platform: str, text: str, cfg: dict | None = None, due_at=None, dry_run: bool = False) -> dict:
    return create_post(platform, text, cfg=cfg, due_at=due_at, dry_run=dry_run)


def send_file(platform: str, path: Path, cfg: dict | None = None, due_at=None, dry_run: bool = False) -> dict:
    return create_post(platform, path.read_text(encoding="utf-8"), cfg=cfg, due_at=due_at, dry_run=dry_run)


def carousel_caption(path: Path) -> str:
    """The carousel file is a slide script plus a CAPTION block; Instagram wants only the caption."""
    text = path.read_text(encoding="utf-8")
    marker = "=== CAPTION ==="
    return text.split(marker, 1)[1].strip() if marker in text else text.strip()


def card_urls(slug: str, cfg: dict | None = None) -> list[str]:
    """Public URLs of the rendered slides, in order. Instagram has no upload API."""
    cfg = cfg or load_config()
    base = ((cfg.get("buffer", {}) or {}).get("assets_base") or ASSETS_BASE).rstrip("/")
    folder = ROOT / "content" / "cards" / slug
    slides = sorted(folder.glob("slide-*.png"), key=lambda p: int(p.stem.split("-")[1]))
    if not slides:
        raise RuntimeError(
            f"no rendered slides in {folder} - run: python automation/cards.py --slug {slug}"
        )
    return [f"{base}/{slug}/{p.name}" for p in slides]


def send_carousel(
    slug: str,
    cfg: dict | None = None,
    due_at=None,
    share_now: bool = False,
    dry_run: bool = False,
) -> dict:
    """Post a rendered carousel to Instagram through Buffer."""
    cfg = cfg or load_config()
    script = ROOT / "content" / "out" / slug / "instagram_carousel.txt"
    if not script.exists():
        raise RuntimeError(f"missing carousel script: {script}")
    return create_post(
        "instagram_carousel",
        carousel_caption(script),
        cfg=cfg,
        due_at=due_at,
        dry_run=dry_run,
        assets=card_urls(slug, cfg),
        share_now=share_now,
    )


def ready_platforms(cfg: dict | None = None) -> set[str]:
    """Which queue platforms actually have a Buffer channel right now."""
    return set(channel_map(cfg))


def describe(cfg: dict | None = None) -> str:
    """Read-only report used by --check and by connect.py."""
    cfg = cfg or load_config()
    found = channels(cfg)
    resolved = channel_map(cfg)

    lines = [f"{len(found)} channel(s) on this Buffer account:"]
    for ch in found:
        lines.append(f"  - {ch.get('name')} [{ch.get('service')}] on {ch.get('organization')}")
    lines.append("queue platform -> Buffer channel:")
    for platform, service in SERVICE.items():
        ch = resolved.get(platform)
        if ch:
            lines.append(f"  {platform:<10} -> {ch.get('name')} ({service})")
        else:
            lines.append(f"  {platform:<10} -> NOT CONNECTED (needs a '{service}' channel)")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish to Buffer-connected networks")
    ap.add_argument("--check", action="store_true", help="show connected channels and the platform mapping (read-only)")
    ap.add_argument("--platform", choices=sorted(SERVICE), help="which queue platform to publish")
    ap.add_argument("--file", help="file to publish")
    ap.add_argument("--text", help="text to publish")
    ap.add_argument("--due", help="ISO timestamp; omit to let Buffer pick the next slot")
    ap.add_argument("--test", choices=sorted(SERVICE), help="save a test post as a Buffer draft (publishes nothing)")
    ap.add_argument("--draft", action="store_true", help="save as a draft instead of scheduling")
    ap.add_argument("--dry-run", action="store_true", help="print the request instead of sending")
    args = ap.parse_args()

    cfg = load_config()
    try:
        if args.check:
            try:
                print(describe(cfg))
                return 0
            except RuntimeError as exc:
                print(f"FAILED: {exc}")
                return 1

        if args.test:
            platform = args.test
            result = create_post(
                platform,
                "Chipzo test post — saved as a draft, so nothing is published. "
                "If you can see this in Buffer, the pipeline can publish here on its own.",
                cfg=cfg,
                dry_run=args.dry_run,
                draft=True,
            )
            print(json.dumps(result, indent=2)[:600])
            return 0

        if not args.platform or not (args.file or args.text):
            ap.print_help()
            return 1

        if args.file:
            result = send_file(args.platform, Path(args.file), cfg=cfg, due_at=args.due, dry_run=args.dry_run)
        else:
            result = send(args.platform, args.text, cfg=cfg, due_at=args.due, dry_run=args.dry_run)
        print(json.dumps(result, indent=2)[:600])
        return 0
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
