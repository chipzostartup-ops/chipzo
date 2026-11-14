#!/usr/bin/env python3
"""
CONNECT — guided, verified platform setup.

    py -3 automation/connect.py              # interactive menu
    py -3 automation/connect.py telegram     # one platform
    py -3 automation/connect.py --check      # test what is already saved
    py -3 automation/connect.py blogger --test-send

This does not just save keys. It calls the real API / logs into SMTP first, and
only writes config.json if the credential actually works. No silent failures.
"""

from __future__ import annotations

import argparse
import getpass
import json
import smtplib
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import AUTOMATION, load_config, write_json  # noqa: E402

CONFIG_PATH = AUTOMATION / "config.json"
EXAMPLE_PATH = AUTOMATION / "config.example.json"

GREEN, RED, DIM, YELLOW, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[93m", "\033[0m"
if not sys.stdout.isatty():  # logs, CI, redirected output
    GREEN = RED = DIM = YELLOW = RESET = ""

# set by --test-send
FORCE_TEST_SEND = False


def ok(msg: str) -> None:
    print(f"  {GREEN}OK{RESET}  {msg}")


def bad(msg: str) -> None:
    print(f"  {RED}FAIL{RESET} {msg}")


def hint(msg: str) -> None:
    print(f"  {DIM}{msg}{RESET}")


def ask(prompt: str, secret: bool = False, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        # getpass needs a real terminal; fall back to input() when piped (CI, tests)
        if secret and sys.stdin.isatty():
            val = getpass.getpass(f"  {prompt}{suffix}: ")
        else:
            val = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0)
    val = val.strip()
    return val or default


def http_json(url: str, headers: dict | None = None, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network: {exc.reason}") from exc


# ---------------------------------------------------------------- validators


def check_telegram(cfg: dict, chat_override: str = "") -> tuple[bool, str]:
    conf = cfg.get("telegram", {})
    token = conf.get("bot_token", "")
    chat = chat_override or conf.get("chat_id", "")
    if not token:
        return False, "bot_token not set"
    try:
        me = http_json(f"https://api.telegram.org/bot{token}/getMe")
    except RuntimeError as exc:
        return False, str(exc)
    if not me.get("ok"):
        return False, "token rejected by Telegram"
    bot = me["result"].get("username", "?")

    if not chat:
        return True, f"token valid (@{bot}); chat_id not set yet (step 3)"
    try:
        info = http_json(
            f"https://api.telegram.org/bot{token}/getChat?chat_id={urllib.parse.quote(chat)}"
        )
    except RuntimeError as exc:
        return False, f"token valid (@{bot}) but cannot see chat '{chat}': {exc}"
    if not info.get("ok"):
        return False, f"bot @{bot} is not in chat '{chat}' - add it as an admin first"
    title = info["result"].get("title") or info["result"].get("username") or chat
    return True, f"@{bot} can post to '{title}'"


def check_blogger(cfg: dict, test_send: bool = False) -> tuple[bool, str]:
    conf = cfg.get("blogger", {})
    need = ("email_address", "smtp_host", "smtp_user", "smtp_password")
    missing = [k for k in need if not conf.get(k)]
    if missing:
        return False, "missing: " + ", ".join(missing)

    port = int(conf.get("smtp_port", 587))
    context = ssl.create_default_context()
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(conf["smtp_host"], port, context=context, timeout=30)
        else:
            server = smtplib.SMTP(conf["smtp_host"], port, timeout=30)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        with server:
            server.login(conf["smtp_user"], conf["smtp_password"])
    except smtplib.SMTPAuthenticationError as exc:
        return False, (
            f"login rejected ({exc.smtp_code}). For Gmail use a 16-char App Password, "
            "not your normal password"
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"

    target = conf["email_address"]
    if test_send:
        from channels import blogger as blogger_channel

        try:
            blogger_channel.send(
                "Chipzo connection test",
                "<p>If you can read this, publishing works.</p>",
                cfg,
            )
        except Exception as exc:  # noqa: BLE001
            return False, f"login ok but send failed: {exc}"
        return True, f"logged in and sent a test post to {target}"
    return True, f"SMTP login ok -> posts will go to {target}"


def check_facebook(cfg: dict) -> tuple[bool, str]:
    conf = cfg.get("facebook", {})
    if not conf.get("page_id") or not conf.get("page_token"):
        return False, "page_id / page_token not set"
    try:
        data = http_json(
            f"https://graph.facebook.com/v21.0/{conf['page_id']}"
            f"?fields=name,id&access_token={conf['page_token']}"
        )
    except RuntimeError as exc:
        return False, str(exc)
    return True, f"page '{data.get('name', '?')}' reachable"


def check_instagram(cfg: dict) -> tuple[bool, str]:
    conf = cfg.get("instagram", {})
    token = conf.get("page_token")
    if not conf.get("ig_user_id") or not token:
        return False, "ig_user_id / page_token not set"
    try:
        data = http_json(
            f"https://graph.facebook.com/v21.0/{conf['ig_user_id']}"
            f"?fields=username&access_token={token}"
        )
    except RuntimeError as exc:
        return False, str(exc)
    return True, f"IG account @{data.get('username', '?')} reachable"


def check_whatsapp(cfg: dict) -> tuple[bool, str]:
    conf = cfg.get("whatsapp", {})
    if not conf.get("phone_number_id") or not conf.get("token"):
        return False, "phone_number_id / token not set"
    try:
        data = http_json(
            f"https://graph.facebook.com/v21.0/{conf['phone_number_id']}"
            "?fields=display_phone_number,verified_name",
            headers={"Authorization": f"Bearer {conf['token']}"},
        )
    except RuntimeError as exc:
        return False, str(exc)
    return True, f"number {data.get('display_phone_number', '?')} reachable"


def check_email(cfg: dict) -> tuple[bool, str]:
    conf = cfg.get("email", {})
    if not conf.get("api_key"):
        return False, "api_key not set"
    try:
        data = http_json(
            "https://api.brevo.com/v3/account", headers={"api-key": conf["api_key"]}
        )
    except RuntimeError as exc:
        return False, str(exc)
    return True, f"Brevo account {data.get('email', '?')}"


CHECKS = {
    "telegram": ("Telegram bot + channel", check_telegram),
    "blogger": ("Blogger via SMTP", check_blogger),
    "facebook": ("Facebook Page", check_facebook),
    "instagram": ("Instagram Business", check_instagram),
    "whatsapp": ("WhatsApp Cloud API", check_whatsapp),
    "email": ("Brevo email list", check_email),
}


# ------------------------------------------------------------------ writers


def load_or_create_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    with open(EXAMPLE_PATH, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    write_json(CONFIG_PATH, cfg)
    print(f"{DIM}created {CONFIG_PATH}{RESET}\n")
    return cfg


def save(cfg: dict) -> None:
    write_json(CONFIG_PATH, cfg)
    print(f"{DIM}saved -> {CONFIG_PATH}{RESET}")


# ------------------------------------------------------------------- flows


def flow_telegram(cfg: dict) -> None:
    print("\nTELEGRAM  (5 minutes, fully automatic publishing)")
    hint("1. Telegram -> @BotFather -> /newbot -> copy the token")
    hint("2. Create a public channel, e.g. @chipzo")
    hint("3. Channel -> Administrators -> Add -> your bot -> enable Post Messages")
    token = ask("Bot token", secret=True, default=cfg["telegram"].get("bot_token", ""))
    chat = ask("Channel username or -100 id", default=cfg["telegram"].get("chat_id", ""))
    if not token:
        bad("no token entered")
        return

    cfg.setdefault("telegram", {})
    cfg["telegram"]["bot_token"] = token
    if chat:
        cfg["telegram"]["chat_id"] = chat

    passed, detail = check_telegram(cfg)
    if not passed:
        bad(detail)
        hint("nothing saved - fix the above and run again")
        return
    ok(detail)

    if ask("send a test message to the channel now? (y/n)", default="y").lower().startswith("y"):
        from channels import telegram as tg

        try:
            tg.send("<b>Chipzo connected.</b>\nThis channel now publishes automatically.", cfg)
            ok("test message delivered - check your phone")
        except Exception as exc:  # noqa: BLE001
            bad(str(exc))
            return

    cfg["telegram"]["enabled"] = True
    save(cfg)


def flow_blogger(cfg: dict) -> None:
    print("\nBLOGGER  (free blog + auto-publishing via email)")
    hint("1. blogger.com -> create your blog")
    hint("2. Settings -> Email -> 'Post using email' -> Save")
    hint("3. Copy the secret address, set 'Publish immediately'")
    hint("4. SMTP: use Brevo (smtp-relay.brevo.com:587) or Gmail App Password")
    email = ask("Blogger secret address", default=cfg["blogger"].get("email_address", ""))
    host = ask("SMTP host", default=cfg["blogger"].get("smtp_host", "smtp-relay.brevo.com"))
    port = ask("SMTP port", default=str(cfg["blogger"].get("smtp_port", 587)))
    user = ask("SMTP username (your email)", default=cfg["blogger"].get("smtp_user", ""))
    pwd = ask("SMTP password / app key", secret=True)
    sender = ask("From address", default=cfg["blogger"].get("from_address", "") or user)

    if not (email and user and pwd):
        bad("email, username and password are all required")
        return

    cfg["blogger"].update(
        {
            "email_address": email,
            "smtp_host": host,
            "smtp_port": int(port or 587),
            "smtp_user": user,
            "smtp_password": pwd or cfg["blogger"].get("smtp_password", ""),
            "from_address": sender,
        }
    )

    passed, detail = check_blogger(cfg)
    if not passed:
        bad(detail)
        hint("nothing saved - fix the above and run again")
        return
    ok(detail)

    if FORCE_TEST_SEND or ask(
        "publish a real test post to the blog? (y/n)", default="n"
    ).lower().startswith("y"):
        passed, detail = check_blogger(cfg, test_send=True)
        (ok if passed else bad)(detail)
        if not passed:
            return

    cfg["blogger"]["enabled"] = True
    save(cfg)


def flow_facebook(cfg: dict) -> None:
    print("\nFACEBOOK PAGE")
    hint("developers.facebook.com -> create app (Business) -> Graph API Explorer")
    hint("permissions: pages_show_list, pages_manage_posts")
    page_id = ask("Page ID", default=cfg["facebook"].get("page_id", ""))
    token = ask("Page access token", secret=True)
    if not (page_id and token):
        bad("both values are required")
        return
    cfg["facebook"].update({"page_id": page_id, "page_token": token})
    passed, detail = check_facebook(cfg)
    if not passed:
        bad(detail)
        return
    ok(detail)
    ok("NOTE: refresh this token every ~50 days or it expires silently")
    cfg["facebook"]["enabled"] = True
    save(cfg)


def flow_instagram(cfg: dict) -> None:
    print("\nINSTAGRAM BUSINESS")
    hint("IG must be Business/Creator and linked to your Facebook Page")
    hint("permissions: instagram_basic, instagram_content_publish, pages_show_list")
    ig_id = ask("IG user id", default=cfg["instagram"].get("ig_user_id", ""))
    token = ask("Page access token", secret=True)
    if not (ig_id and token):
        bad("both values are required")
        return
    cfg["instagram"].update({"ig_user_id": ig_id, "page_token": token})
    passed, detail = check_instagram(cfg)
    if not passed:
        bad(detail)
        return
    ok(detail)
    cfg["instagram"]["enabled"] = True
    save(cfg)


def flow_whatsapp(cfg: dict) -> None:
    print("\nWHATSAPP CLOUD API  (optional - the channel works manually for free)")
    phone_id = ask("Phone number id", default=cfg["whatsapp"].get("phone_number_id", ""))
    token = ask("Permanent access token", secret=True)
    if not (phone_id and token):
        bad("both values are required")
        return
    cfg["whatsapp"].update({"phone_number_id": phone_id, "token": token})
    passed, detail = check_whatsapp(cfg)
    if not passed:
        bad(detail)
        return
    ok(detail)
    cfg["whatsapp"]["enabled"] = True
    save(cfg)


def flow_email(cfg: dict) -> None:
    print("\nBREVO EMAIL LIST  (300 emails/day free)")
    hint("brevo.com -> SMTP & API -> API keys -> create")
    key = ask("API key", secret=True)
    if not key:
        bad("no key entered")
        return
    cfg["email"]["api_key"] = key
    passed, detail = check_email(cfg)
    if not passed:
        bad(detail)
        return
    ok(detail)
    cfg["email"]["enabled"] = True
    save(cfg)


FLOWS = {
    "telegram": flow_telegram,
    "blogger": flow_blogger,
    "facebook": flow_facebook,
    "instagram": flow_instagram,
    "whatsapp": flow_whatsapp,
    "email": flow_email,
}


# -------------------------------------------------------------------- main


def status_board(cfg: dict) -> int:
    print("=" * 66)
    print(" CONNECTION STATUS")
    print("=" * 66)
    ready = 0
    for key, (label, fn) in CHECKS.items():
        passed, detail = fn(cfg)
        print(f"{GREEN if passed else RED}{'LIVE' if passed else '----'}{RESET}  {label:<24}{detail}")
        ready += passed
    print("=" * 66)
    if ready == 0:
        print("Nothing connected. Start here:  py -3 automation/connect.py telegram")
    else:
        print(f"{ready} of {len(CHECKS)} connected.")
        if ready < 2:
            print("Next best: blogger  ->  py -3 automation/connect.py blogger")
    return ready


def menu(cfg: dict) -> None:
    while True:
        print("\nWhat do you want to connect?")
        print("  1  Telegram        (start here, 5 min, fully automatic)")
        print("  2  Blogger         (free blog, auto-post by email)")
        print("  3  Brevo email     (build the list)")
        print("  4  Facebook page   (auto-post)")
        print("  5  Instagram       (images only)")
        print("  6  WhatsApp API    (optional)")
        print("  s  show status")
        print("  q  quit")
        choice = ask("choose").lower()
        mapping = {
            "1": "telegram", "2": "blogger", "3": "email",
            "4": "facebook", "5": "instagram", "6": "whatsapp",
        }
        if choice == "q":
            return
        if choice == "s":
            status_board(cfg)
        elif choice in mapping:
            FLOWS[mapping[choice]](cfg)
            cfg = load_or_create_config()


def main() -> int:
    ap = argparse.ArgumentParser(description="Connect and verify Chipzo platform access")
    ap.add_argument("platform", nargs="?", choices=sorted(FLOWS) + [""], default="")
    ap.add_argument("--check", action="store_true", help="test everything already saved")
    ap.add_argument("--test-send", action="store_true", help="send a real test post (blogger)")
    args = ap.parse_args()

    cfg = load_or_create_config()

    if args.check:
        status_board(cfg)
        return 0

    if args.platform:
        if args.platform == "blogger" and args.test_send:
            global FORCE_TEST_SEND
            FORCE_TEST_SEND = True
        FLOWS[args.platform](cfg)
        print()
        status_board(load_or_create_config())
        return 0

    status_board(cfg)
    menu(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
