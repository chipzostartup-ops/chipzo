#!/usr/bin/env python3
"""WhatsApp helpers.

WhatsApp Channels have NO public posting API. So this module does two things:

1. `share_links()` - builds ready-to-send wa.me links from a text file, so you
   can forward a formatted message to your channel / contacts in 2 taps.
2. `send_cloud()` - real automation via the Meta WhatsApp Cloud API for an
   opted-in recipient list. Needs an approved template for cold sends.

Both are free. Start with path 1.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import load_config  # noqa: E402

GRAPH = "https://graph.facebook.com/v21.0"


def share_links(text: str, numbers: list[str] | None = None) -> list[str]:
    """One link per number with the text pre-filled; plus a generic link."""
    encoded = urllib.parse.quote(text)
    links = [f"https://wa.me/?text={encoded}"]
    for num in numbers or []:
        digits = "".join(ch for ch in num if ch.isdigit())
        if digits:
            links.append(f"https://wa.me/{digits}?text={encoded}")
    return links


def send_cloud(to: str, body: str, cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    conf = cfg.get("whatsapp", {})
    if not conf.get("phone_number_id") or not conf.get("token"):
        raise RuntimeError("whatsapp.phone_number_id / token missing")

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "".join(ch for ch in to if ch.isdigit()),
        "type": "text",
        "text": {"preview_url": True, "body": body[:4096]},
    }
    req = urllib.request.Request(
        f"{GRAPH}/{conf['phone_number_id']}/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {conf['token']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"WhatsApp API {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc


def write_share_pack(text_file: str | Path, out_dir: str | Path | None = None) -> Path:
    "Write a .txt of share links plus a plain copy for pasting into the app."
    path = Path(text_file)
    text = path.read_text(encoding="utf-8")
    cfg = load_config()
    nums = []
    csv = Path("automation/state/whatsapp_contacts.csv")
    if csv.exists():
        for line in csv.read_text(encoding="utf-8").splitlines()[1:]:
            if line.strip():
                nums.append(line.split(",")[0].strip())

    links = share_links(text, nums)
    target = Path(out_dir) if out_dir else path.parent
    out = target / "whatsapp_sharepack.txt"
    body = (
        "=== MESSAGE (paste into your WhatsApp Channel) ===\n\n"
        + text
        + "\n\n=== SHARE LINKS ===\n"
        + "\n".join(links)
        + f"\n\nChannel: {cfg['brand'].get('site', '')}\n"
    )
    out.write_text(body, encoding="utf-8")
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="WhatsApp share pack builder")
    ap.add_argument("file", help="whatsapp.txt from content/out/<slug>/")
    args = ap.parse_args()
    p = write_share_pack(args.file)
    print(f"OK: wrote {p}")
    print("Open it, copy the message, paste in your WhatsApp Channel.")
