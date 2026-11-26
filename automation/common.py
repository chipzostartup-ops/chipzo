"""Shared helpers for the Chipzo automation toolkit (stdlib only)."""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Windows consoles default to cp1252 and mangle em-dashes/arrows in output.
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent
AUTOMATION = ROOT / "automation"
CONTENT = ROOT / "content"
DRAFTS = CONTENT / "drafts"
OUT = CONTENT / "out"
STATE = AUTOMATION / "state"
DASHBOARD = ROOT / "dashboard"

# How the user should invoke scripts on this machine (bare `python` is a
# Microsoft Store stub on many Windows installs).
PY = "py -3" if sys.platform == "win32" else "python"

# env var -> (section, key)
ENV_MAP = {
    "TELEGRAM_BOT_TOKEN": ("telegram", "bot_token"),
    "TELEGRAM_CHAT_ID": ("telegram", "chat_id"),
    "BLOGGER_EMAIL": ("blogger", "email_address"),
    "SMTP_HOST": ("blogger", "smtp_host"),
    "SMTP_PORT": ("blogger", "smtp_port"),
    "SMTP_USER": ("blogger", "smtp_user"),
    "SMTP_PASSWORD": ("blogger", "smtp_password"),
    "SMTP_FROM": ("blogger", "from_address"),
    "FB_PAGE_ID": ("facebook", "page_id"),
    "FB_PAGE_TOKEN": ("facebook", "page_token"),
    "IG_USER_ID": ("instagram", "ig_user_id"),
    "BREVO_API_KEY": ("email", "api_key"),
    "WHATSAPP_TOKEN": ("whatsapp", "token"),
    "WHATSAPP_PHONE_ID": ("whatsapp", "phone_number_id"),
}


def load_config() -> dict:
    # CHIPZO_CONFIG lets a test point at a different file without touching the
    # real one. Handy for reproducing a CI failure locally.
    override = os.environ.get("CHIPZO_CONFIG")
    if override:
        path = Path(override)
    else:
        path = AUTOMATION / "config.json"
        if not path.exists():
            path = AUTOMATION / "config.example.json"
    with open(path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    for env_key, (section, key) in ENV_MAP.items():
        val = os.environ.get(env_key)
        if val:
            cfg.setdefault(section, {})[key] = val

    # env overrides for flags
    if os.environ.get("CHIPZO_DRY_RUN", "").lower() in {"0", "false", "no"}:
        cfg.setdefault("publish", {})["dry_run"] = False

    # The email channel only becomes live when there is a list to send to.
    if os.environ.get("SUBSCRIBERS_CSV", "").strip():
        cfg.setdefault("email", {})["enabled"] = True
        cfg["email"].setdefault("provider", "gmail")

    return cfg


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", text) or "untitled"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: str) -> datetime:
    """Parse an ISO8601 string into an aware datetime (naive => UTC)."""
    value = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def tz_offset(hours: float) -> timezone:
    return timezone(timedelta(hours=hours))


def read_json(path: Path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def first_sentence(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "? ", "! "):
        idx = cut.rfind(sep)
        if idx > 40:
            return cut[: idx + 1].strip()
    return cut.rsplit(" ", 1)[0].strip() + "…"


def strip_md(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    return text.strip()
