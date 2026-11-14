#!/usr/bin/env python3
"""Shows exactly what is wired up, what is missing, and what still works.

    python automation/check_env.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import AUTOMATION, OUT, PY, load_config  # noqa: E402

OK = "[ok]  "
NO = "[--]  "
WARN = "[!!]  "


def mask(value: str) -> str:
    if not value:
        return ""
    value = str(value)
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def main() -> int:
    cfg = load_config()
    brand = cfg.get("brand", {})

    print("=" * 72)
    print(f" CHIPZO ENV CHECK  -  {brand.get('name', '?')}")
    print("=" * 72)
    print(f"config file : {AUTOMATION / 'config.json'}"
          f"{'' if (AUTOMATION / 'config.json').exists() else '  (missing -> using example)'}")
    print()

    rows: list[tuple[str, bool, str]] = []

    # Telegram
    tg = cfg.get("telegram", {})
    tg_ok = bool(tg.get("bot_token") and tg.get("chat_id"))
    rows.append(("Telegram  (full auto)", tg_ok,
                 f"chat={tg.get('chat_id') or '-'} token={mask(tg.get('bot_token', '')) or '-'}"))

    # Blogger
    bl = cfg.get("blogger", {})
    bl_ok = all(bl.get(k) for k in ("email_address", "smtp_host", "smtp_user", "smtp_password"))
    rows.append(("Blogger   (full auto)", bl_ok,
                 f"post-email={mask(bl.get('email_address', '')) or '-'} smtp={bl.get('smtp_host') or '-'}"))

    # Facebook
    fb = cfg.get("facebook", {})
    fb_ok = bool(fb.get("page_id") and fb.get("page_token"))
    rows.append(("Facebook  (auto page)", fb_ok,
                 f"page={mask(fb.get('page_id', '')) or '-'} token={mask(fb.get('page_token', '')) or '-'}"))

    # Instagram
    ig = cfg.get("instagram", {})
    ig_ok = bool(ig.get("ig_user_id") and ig.get("page_token"))
    rows.append(("Instagram (image only)", ig_ok,
                 f"ig_user={mask(ig.get('ig_user_id', '')) or '-'}"))

    # WhatsApp
    wa = cfg.get("whatsapp", {})
    wa_ok = bool(wa.get("phone_number_id") and wa.get("token"))
    rows.append(("WhatsApp  (Cloud API)", wa_ok,
                 "fallback: manual channel post + wa.me link" if not wa_ok else "cloud api ready"))

    # Email
    em = cfg.get("email", {})
    em_ok = bool(em.get("api_key"))
    rows.append(("Email     (Brevo)", em_ok,
                 f"list={em.get('list_id', '-')} key={mask(em.get('api_key', '')) or '-'}"))

    for label, ok, detail in rows:
        print(f"{OK if ok else NO}{label:<26}{detail}")

    print()
    print("Always free, always available (no keys needed):")
    for line in (
        "     LinkedIn, X, Instagram reels, WhatsApp channel  -> copy-paste files",
        "     Keyword research                                -> automation/seo.py",
        "     Dashboard                                       -> automation/dashboard.py",
    ):
        print(line)

    # content state
    drafts = list((AUTOMATION.parent / "content" / "drafts").glob("*.md"))
    generated = list(OUT.glob("*/manifest.json"))
    queue_exists = (AUTOMATION / "state" / "queue.json").exists()
    print()
    print(f"drafts      : {len(drafts)}")
    print(f"generated   : {len(generated)} topic(s)")
    print(f"queue       : {'present' if queue_exists else 'not built yet'}")

    ready = tg_ok or bl_ok or fb_ok or em_ok
    print()
    if ready:
        print("READY. Next:")
        print(f"  {PY} automation/repurpose.py --all")
        print(f"  {PY} automation/queue.py build")
        print(f"  {PY} automation/run_daily.py --catchup 1")
    else:
        print("NOT CONNECTED. Nothing can publish yet.")
        print(f"Connect first: {PY} automation/connect.py")
        print("Read: CONNECT-FIRST.md")
        print(f"(Content generation still works: {PY} automation/repurpose.py --all)")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
