#!/usr/bin/env python3
"""Brevo email delivery (free tier: 300 emails/day).

Two different Brevo APIs, and they are not interchangeable:

  transactional   POST /v3/smtp/email            needs explicit "to" addresses
  campaign        POST /v3/emailCampaigns        accepts "listIds", then sendNow

The old code sent "listIds" to the transactional endpoint, which Brevo rejects,
so a newsletter could never have gone out. This module picks the right one:

    python automation/channels/email_brevo.py content/out/<slug>/email.html
    python automation/channels/email_brevo.py --test me@example.com

An API key (xkeysib-...) is not IP-restricted. An SMTP key (xsmtpsib-...) is,
which is why SMTP was abandoned.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import load_config, strip_md  # noqa: E402

BASE = "https://api.brevo.com/v3"
TX_ENDPOINT = f"{BASE}/smtp/email"
CAMPAIGN_ENDPOINT = f"{BASE}/emailCampaigns"


def _call(url: str, api_key: str, payload: dict | None = None, method: str = "POST") -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
            "Accept": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Brevo {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Brevo network error: {exc.reason}") from exc


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


def _sender(cfg: dict) -> dict:
    conf = cfg.get("email", {})
    email = (
        conf.get("from_address")
        or cfg.get("brand", {}).get("from_address")
        or conf.get("smtp_user")  # leftover from the old SMTP config
        or ""
    )
    if not email:
        raise RuntimeError("email.from_address missing (must be a sender verified in Brevo)")
    return {"name": cfg["brand"]["name"], "email": email}


def send_transactional(html: str, subject: str, to: list[str], cfg: dict) -> dict:
    conf = cfg.get("email", {})
    payload = {
        "sender": _sender(cfg),
        "to": [{"email": addr} for addr in to],
        "subject": subject,
        "htmlContent": html,
    }
    return _call(TX_ENDPOINT, conf["api_key"], payload)


def send_campaign(html: str, subject: str, list_id: int, cfg: dict) -> dict:
    conf = cfg.get("email", {})
    campaign = {
        "name": f"{cfg['brand']['name']} - {subject[:60]}",
        "subject": subject,
        "sender": _sender(cfg),
        "type": "classic",
        "htmlContent": html,
        "recipients": {"listIds": [int(list_id)]},
    }
    created = _call(CAMPAIGN_ENDPOINT, conf["api_key"], campaign)
    campaign_id = created.get("id")
    if not campaign_id:
        raise RuntimeError(f"campaign not created: {created}")
    _call(f"{CAMPAIGN_ENDPOINT}/{campaign_id}/sendNow", conf["api_key"], {}, method="POST")
    return {"campaignId": campaign_id}


def contacts_in_list(list_id: int, cfg: dict) -> int:
    """How many people would actually receive this."""
    conf = cfg.get("email", {})
    res = _call(f"{BASE}/contacts/lists/{int(list_id)}", conf["api_key"], method="GET")
    return int(res.get("totalSubscribers", 0))


def send(email_file: str | Path, cfg: dict | None = None, to: list[str] | None = None) -> dict:
    cfg = cfg or load_config()
    conf = cfg.get("email", {})
    if not conf.get("api_key"):
        raise RuntimeError("email.api_key missing (Brevo API key, starts with xkeysib-)")
    if not conf["api_key"].startswith("xkeysib-"):
        raise RuntimeError(
            "that looks like an SMTP key (xsmtpsib-...). SMTP keys are IP-restricted; "
            "use an API key from Brevo -> SMTP & API -> API Keys"
        )

    text = Path(email_file).read_text(encoding="utf-8")
    subject, _preview, body = _split_subject(text)
    html = md_to_simple_html(body)

    if to:
        return send_transactional(html, subject, to, cfg)

    list_id = conf.get("list_id")
    if not list_id:
        raise RuntimeError("no recipients: pass --to or set email.list_id")

    count = contacts_in_list(list_id, cfg)
    if count == 0:
        raise RuntimeError(
            f"list {list_id} has 0 subscribers - nothing to send. "
            "Add the signup form to the blog first (see email-form.html)."
        )
    return send_campaign(html, subject, list_id, cfg)


def smoke_test(to: str, cfg: dict | None = None) -> dict:
    """Prove the key works without touching a subscriber list."""
    cfg = cfg or load_config()
    conf = cfg.get("email", {})
    if not conf.get("api_key"):
        raise RuntimeError("email.api_key missing")
    html = (
        '<div style="font-family:Inter,Arial,sans-serif">'
        "<h2>Chipzo email is connected</h2>"
        "<p>This was sent by the automation to prove the Brevo API key works "
        "from any IP address.</p></div>"
    )
    return send_transactional(html, "Chipzo email test", [to], cfg)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Send a generated email via Brevo")
    ap.add_argument("file", nargs="?", help="generated email.html")
    ap.add_argument("--to", nargs="*", help="send transactionally to these addresses")
    ap.add_argument("--test", metavar="EMAIL", help="send a test message to prove the key works")
    ap.add_argument("--list-count", type=int, metavar="LIST_ID", help="how many subscribers a list has")
    args = ap.parse_args()

    try:
        if args.list_count:
            print(f"list {args.list_count}: {contacts_in_list(args.list_count, load_config())} subscriber(s)")
        elif args.test:
            res = smoke_test(args.test)
            print(f"OK: test sent, messageId {res.get('messageId')}")
        elif args.file:
            res = send(args.file, to=args.to)
            print(f"OK: {res}")
        else:
            ap.print_help()
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        raise SystemExit(1)
