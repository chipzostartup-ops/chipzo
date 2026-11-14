#!/usr/bin/env python3
"""Brevo transactional email (free tier: 300 emails/day, unlimited contacts)."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import load_config, strip_md  # noqa: E402

API = "https://api.brevo.com/v3/smtp/email"


def _split_subject(text: str) -> tuple[str, str, str]:
    """email.md starts with 'Subject:' and 'Preview:' lines. Split them off."""
    subject = "Chipzo update"
    preview = ""
    lines = text.splitlines()
    idx = 0
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            idx = i + 1
        elif line.lower().startswith("preview:"):
            preview = line.split(":", 1)[1].strip()
            idx = i + 1
    body = "\n".join(lines[idx:]).strip()
    return subject, preview, body


def md_to_simple_html(text: str) -> str:
    out = []
    for block in re.split(r"\n\s*\n", strip_md(text)):
        b = block.strip()
        if not b:
            continue
        if b.startswith("- "):
            items = "".join(f"<li>{line[2:].strip()}</li>" for line in b.splitlines() if line.startswith("- "))
            out.append(f"<ul>{items}</ul>")
        else:
            out.append(f"<p>{b.replace(chr(10), ' ')}</p>")
    return (
        '<div style="font-family:Inter,Arial,sans-serif;line-height:1.7;color:#111;max-width:600px">'
        + "".join(out)
        + "</div>"
    )


def send(email_file: str | Path, cfg: dict | None = None, to: list[str] | None = None) -> dict:
    cfg = cfg or load_config()
    conf = cfg.get("email", {})
    if not conf.get("api_key"):
        raise RuntimeError("email.api_key missing (Brevo SMTP/API key)")

    text = Path(email_file).read_text(encoding="utf-8")
    subject, _preview, body = _split_subject(text)
    sender = conf.get("from_address") or cfg["brand"].get("from_address") or ""

    payload = {
        "sender": {"name": cfg["brand"]["name"], "email": sender},
        "subject": subject,
        "htmlContent": md_to_simple_html(body),
        "textContent": body,
    }
    if to:
        payload["to"] = [{"email": addr} for addr in to]
    elif conf.get("list_id"):
        payload["to"] = [{"email": sender}]  # placeholder; use listIds below
        payload.pop("to")
        payload["listIds"] = [int(conf["list_id"])]
    else:
        raise RuntimeError("no recipients: pass --to or set email.list_id")

    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "api-key": conf["api_key"],
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Brevo {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Send a generated email via Brevo")
    ap.add_argument("file")
    ap.add_argument("--to", nargs="*", help="override recipients")
    args = ap.parse_args()
    try:
        res = send(args.file, to=args.to)
        print(f"OK: messageId {res.get('messageId')}")
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        raise SystemExit(1)
