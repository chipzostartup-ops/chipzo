#!/usr/bin/env python3
"""Telegram channel publisher (Bot API, free, stdlib only).

    python automation/channels/telegram.py --test
    python automation/channels/telegram.py --send "hello"
    python automation/channels/telegram.py --file content/out/<slug>/telegram.md
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import load_config  # noqa: E402

API = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 3900


def _call(token: str, method: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API.format(token=token, method=method),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Telegram HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Telegram network error: {exc.reason}") from exc

    if not body.get("ok"):
        raise RuntimeError(f"Telegram error: {body.get('description')}")
    return body


def to_html(text: str) -> str:
    """Convert the tiny markdown we emit into Telegram-safe HTML."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    import re

    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def split_message(text: str, limit: int = MAX_LEN) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    return chunks


def send(text: str, cfg: dict | None = None, chat_id: str | None = None) -> list[dict]:
    cfg = cfg or load_config()
    conf = cfg.get("telegram", {})
    token = conf.get("bot_token", "")
    target = chat_id or conf.get("chat_id", "")
    if not token:
        raise RuntimeError("telegram.bot_token missing (config.json or TELEGRAM_BOT_TOKEN)")
    if not target:
        raise RuntimeError("telegram.chat_id missing (config.json or TELEGRAM_CHAT_ID)")

    results = []
    for chunk in split_message(text):
        results.append(
            _call(
                token,
                "sendMessage",
                {
                    "chat_id": target,
                    "text": to_html(chunk),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
            )
        )
    return results


def send_photo(image_url: str, caption: str, cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    conf = cfg.get("telegram", {})
    return _call(
        conf["bot_token"],
        "sendPhoto",
        {
            "chat_id": conf["chat_id"],
            "photo": image_url,
            "caption": to_html(caption)[:1000],
            "parse_mode": "HTML",
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish to a Telegram channel")
    ap.add_argument("--test", action="store_true", help="send a test message")
    ap.add_argument("--send", help="send this text")
    ap.add_argument("--file", help="send the contents of this file")
    args = ap.parse_args()

    cfg = load_config()
    try:
        if args.test:
            send(
                "<b>Chipzo is connected.</b>\n\n"
                "This channel is now publishing automatically.\n"
                "Next: run run_daily.py on a schedule.",
                cfg,
            )
            print("OK: test message sent. Check your channel.")
        elif args.send:
            send(args.send, cfg)
            print("OK: message sent.")
        elif args.file:
            text = Path(args.file).read_text(encoding="utf-8")
            send(text, cfg)
            print(f"OK: sent {args.file}")
        else:
            ap.print_help()
            return 1
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
