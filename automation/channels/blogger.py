#!/usr/bin/env python3
"""Blogger publisher via the built-in "post by email" feature (zero API keys).

Setup (2 minutes, see SETUP-FREE-STACK.md):
  Blogger -> Settings -> Email -> "Post using email" -> Save
  Choose "Publish immediately", copy the secret address it shows you.

Then put that address + any free SMTP account in config.json.
"""

from __future__ import annotations

import mimetypes
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import load_config  # noqa: E402


def extract_fragment(full_html: str) -> str:
    """Blogger wraps posts in its own template, so send the article body only.

    Keeps the <style> block so the CTA box still looks right, drops the
    <html>/<head>/<title> envelope that would nest badly inside a post.
    """
    style = ""
    m = re.search(r"<style>(.*?)</style>", full_html, re.S)
    if m:
        style = f"<style>{m.group(1)}</style>"

    m = re.search(r"<article>(.*?)</article>", full_html, re.S)
    body = m.group(1) if m else full_html
    return style + "\n" + body.strip()


def send(subject: str, html_body: str, cfg: dict | None = None, images: list[str] | None = None) -> None:
    cfg = cfg or load_config()
    conf = cfg.get("blogger", {})

    required = {
        "email_address": "blogger.email_address (the secret @blogger.com address)",
        "smtp_host": "blogger.smtp_host",
        "smtp_user": "blogger.smtp_user",
        "smtp_password": "blogger.smtp_password",
    }
    missing = [label for key, label in required.items() if not conf.get(key)]
    if missing:
        raise RuntimeError("missing config: " + ", ".join(missing))

    sender = conf.get("from_address") or conf["smtp_user"]
    port = int(conf.get("smtp_port", 587))

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = conf["email_address"]
    msg["Subject"] = subject
    msg.set_content("This post is HTML. View it in an HTML-capable client.")
    msg.add_alternative(html_body, subtype="html")

    for image_path in images or []:
        p = Path(image_path)
        if not p.exists():
            continue
        ctype, _ = mimetypes.guess_type(p.name)
        maintype, subtype = (ctype or "image/png").split("/", 1)
        msg.add_attachment(p.read_bytes(), maintype=maintype, subtype=subtype, filename=p.name)

    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(conf["smtp_host"], port, context=context, timeout=45) as smtp:
                smtp.login(conf["smtp_user"], conf["smtp_password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(conf["smtp_host"], port, timeout=45) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(conf["smtp_user"], conf["smtp_password"])
                smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            "SMTP login failed. For Gmail use a 16-character App Password "
            "(2-Step Verification required), not your normal password. "
            f"Server said: {exc.smtp_code}"
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise RuntimeError(f"SMTP send failed: {exc}") from exc


def send_post(html_file: str | Path, cfg: dict | None = None, full_page: bool = False) -> None:
    """Publish a generated blog.html. The <title> tag becomes the post title."""
    cfg = cfg or load_config()
    path = Path(html_file)
    raw = path.read_text(encoding="utf-8")

    title = path.stem
    marker = "<title>"
    if marker in raw:
        start = raw.index(marker) + len(marker)
        end = raw.index("</title>", start)
        title = raw[start:end].split("|")[0].strip()

    html_body = raw if full_page else extract_fragment(raw)
    send(title, html_body, cfg)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Publish a generated blog.html to Blogger via email")
    ap.add_argument("file")
    args = ap.parse_args()
    try:
        send_post(args.file)
        print(f"OK: submitted {args.file} to Blogger")
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        raise SystemExit(1)
