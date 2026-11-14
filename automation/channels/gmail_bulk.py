#!/usr/bin/env python3
"""Send the daily article to the subscriber list over Gmail SMTP.

No new credentials: this reuses the same SMTP host, user and app password that
already publish to Blogger, so GitHub already holds them as secrets.

Gmail limits that shape this code:
  500 recipients per day on a free account
  ~100 addresses per message before it refuses
so the list is sent in BCC batches, with a pause between them. BCC keeps every
address invisible to the other subscribers.

    python automation/channels/gmail_bulk.py content/out/<slug>/email.md
    python automation/channels/gmail_bulk.py --test you@example.com
    python automation/channels/gmail_bulk.py content/out/<slug>/email.md --dry-run
"""

from __future__ import annotations

import smtplib
import ssl
import sys
import time
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import subscribers  # noqa: E402
from channels.email_brevo import _split_subject, md_to_simple_html  # noqa: E402
from common import load_config  # noqa: E402

BATCH_SIZE = 90
PAUSE_SECONDS = 8


def _smtp(cfg: dict) -> dict:
    """Gmail details, falling back to the Blogger SMTP block that already works."""
    email_conf = cfg.get("email", {})
    blog = cfg.get("blogger", {})
    conf = {
        "host": email_conf.get("smtp_host") or blog.get("smtp_host") or "smtp.gmail.com",
        "port": int(email_conf.get("smtp_port") or blog.get("smtp_port") or 587),
        "user": email_conf.get("smtp_user") or blog.get("smtp_user") or "",
        "password": email_conf.get("smtp_password") or blog.get("smtp_password") or "",
        "from_address": email_conf.get("from_address") or email_conf.get("smtp_user") or blog.get("from_address") or "",
    }
    missing = [k for k in ("user", "password", "from_address") if not conf[k]]
    if missing:
        raise RuntimeError("missing Gmail settings: " + ", ".join(missing))
    return conf


def _footer(cfg: dict, conf: dict) -> str:
    brand = cfg["brand"]
    site = brand["site"].rstrip("/")
    return (
        '<hr style="border:none;border-top:1px solid #e4e7ec;margin:28px 0 14px">'
        '<p style="font-size:12px;line-height:1.6;color:#8a8f98;font-family:Inter,Arial,sans-serif">'
        f'{brand["name"]} &middot; {brand["tagline"]}<br>'
        f'<a href="{site}" style="color:#0a8f6b">{site.replace("https://", "")}</a> &middot; '
        f'<a href="{brand.get("telegram_url") or "https://t.me/chipzostartup"}" style="color:#0a8f6b">Telegram</a><br>'
        f'You get this because you signed up on the blog. '
        f'<a href="mailto:{conf["from_address"]}?subject=unsubscribe" style="color:#8a8f98">Unsubscribe</a>'
        "</p>"
    )


def _batches(items: list[str], size: int) -> list[list[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)] or []


def _deliver(conf: dict, subject: str, html: str, recipients: list[str]) -> int:
    context = ssl.create_default_context()
    sent = 0
    for n, batch in enumerate(_batches(recipients, BATCH_SIZE), start=1):
        msg = EmailMessage()
        msg["From"] = f"Chipzo <{conf['from_address']}>"
        msg["To"] = conf["from_address"]
        msg["Bcc"] = ", ".join(batch)
        msg["Subject"] = subject
        msg["List-Unsubscribe"] = f"<mailto:{conf['from_address']}?subject=unsubscribe>"
        msg.set_content("This email is HTML. View it in an HTML-capable client.")
        msg.add_alternative(html, subtype="html")

        with smtplib.SMTP(conf["host"], conf["port"], timeout=60) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(conf["user"], conf["password"])
            smtp.send_message(msg)

        sent += len(batch)
        print(f"  batch {n}: {len(batch)} recipient(s) -> {sent} total")
        if n < len(_batches(recipients, BATCH_SIZE)):
            time.sleep(PAUSE_SECONDS)
    return sent


def send(email_file: str | Path, cfg: dict | None = None, dry_run: bool = False) -> dict:
    cfg = cfg or load_config()
    conf = _smtp(cfg)

    recipients = subscribers.load()
    if not recipients:
        raise RuntimeError(
            "subscriber list is empty - nothing to send. "
            "Add addresses with: py -3 automation/subscribers.py import <sheet.csv>"
        )

    text = Path(email_file).read_text(encoding="utf-8")
    subject, _preview, body = _split_subject(text)
    html = md_to_simple_html(body) + _footer(cfg, conf)

    if dry_run:
        print(f"DRY RUN: would send to {len(recipients)} subscriber(s) in {len(_batches(recipients, BATCH_SIZE))} batch(es)")
        print(f"Subject: {subject}")
        return {"dry_run": True, "recipients": len(recipients)}

    sent = _deliver(conf, subject, html, recipients)
    return {"sent": sent, "subject": subject}


def smoke_test(to: str, cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    conf = _smtp(cfg)
    html = (
        '<div style="font-family:Inter,Arial,sans-serif;line-height:1.7;color:#111">'
        "<h2>Chipzo email is connected</h2>"
        "<p>Sent over Gmail SMTP with the same app password that publishes to Blogger. "
        "If this arrived, the daily article can be mailed to the whole list.</p>"
        "</div>"
    ) + _footer(cfg, conf)
    _deliver(conf, "Chipzo email test", html, [to])
    return {"tested": to}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Mail the daily article to subscribers over Gmail SMTP")
    ap.add_argument("file", nargs="?", help="generated email.md")
    ap.add_argument("--test", metavar="EMAIL", help="send one test message to this address")
    ap.add_argument("--dry-run", action="store_true", help="show what would be sent")
    args = ap.parse_args()

    try:
        if args.test:
            smoke_test(args.test)
            print(f"OK: test sent to {args.test}")
        elif args.file:
            print(f"OK: {send(args.file, dry_run=args.dry_run)}")
        else:
            ap.print_help()
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        raise SystemExit(1)
