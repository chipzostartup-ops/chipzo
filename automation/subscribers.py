#!/usr/bin/env python3
"""Subscriber list for the email channel.

The list lives in automation/state/subscribers.csv, which is gitignored — email
addresses must never land in a public repo. Google Forms writes to a Sheet, so
the workflow is:

    Google Form -> Sheet -> File > Download > CSV
    python automation/subscribers.py import Downloads/subscribers.csv

    python automation/subscribers.py add someone@example.com
    python automation/subscribers.py list
    python automation/subscribers.py count
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import STATE  # noqa: E402

CSV_PATH = STATE / "subscribers.csv"
FIELDS = ["email", "added_at", "source"]

# Deliberately loose: reject obvious junk, let the mail server reject the rest.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")


def normalise(email: str) -> str:
    return (email or "").strip().lower().strip("<>").strip()


def valid(email: str) -> bool:
    return bool(EMAIL_RE.match(email)) and len(email) <= 254


def load(path: Path | None = None) -> list[str]:
    """Unique, validated addresses in the order they were added."""
    path = path or CSV_PATH
    if not path.exists():
        return []
    seen: set[str] = set()
    out: list[str] = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            email = normalise(next((v for k, v in row.items() if k and k.lower() == "email"), ""))
            if email and valid(email) and email not in seen:
                seen.add(email)
                out.append(email)
    return out


def _write(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDS})


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def add(email: str, source: str = "manual", path: Path | None = None) -> bool:
    path = path or CSV_PATH
    email = normalise(email)
    if not valid(email):
        raise RuntimeError(f"not a valid email: {email!r}")
    if email in load(path):
        return False
    rows = _rows(path)
    rows.append({"email": email, "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": source})
    _write(rows, path)
    return True


def remove(email: str, path: Path | None = None) -> bool:
    path = path or CSV_PATH
    email = normalise(email)
    rows = _rows(path)
    kept = [r for r in rows if normalise(r.get("email", "")) != email]
    if len(kept) == len(rows):
        return False
    _write(kept, path)
    return True


def import_csv(src: Path, source: str = "google-form", path: Path | None = None) -> dict:
    """Import a Google Sheets / Forms CSV export.

    Handles the common shapes: a column called Email / E-mail / Email Address,
    or a single-column file. Adds only addresses that are valid and new.
    """
    path = path or CSV_PATH
    if not src.exists():
        raise RuntimeError(f"no such file: {src}")

    existing = set(load(path))
    added = skipped = invalid = 0
    rows = _rows(path)

    with open(src, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise RuntimeError("empty CSV")
        email_col = next(
            (f for f in reader.fieldnames if f and re.search(r"e-?mail", f, re.I)),
            reader.fieldnames[0],
        )
        for row in reader:
            email = normalise(row.get(email_col, ""))
            if not email:
                continue
            if not valid(email):
                invalid += 1
                continue
            if email in existing:
                skipped += 1
                continue
            existing.add(email)
            rows.append({"email": email, "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": source})
            added += 1

    _write(rows, path)
    return {"added": added, "already_there": skipped, "invalid": invalid, "total": len(existing)}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Manage the Chipzo subscriber list")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="add one address")
    p_add.add_argument("email")

    p_rm = sub.add_parser("remove", help="remove one address")
    p_rm.add_argument("email")

    p_imp = sub.add_parser("import", help="import a Google Sheets CSV export")
    p_imp.add_argument("file")

    sub.add_parser("list", help="list addresses")
    sub.add_parser("count", help="how many are subscribed")

    args = ap.parse_args()

    try:
        if args.cmd == "add":
            print("added" if add(args.email) else "already subscribed")
        elif args.cmd == "remove":
            print("removed" if remove(args.email) else "not in the list")
        elif args.cmd == "import":
            print(import_csv(Path(args.file)))
        elif args.cmd == "list":
            emails = load()
            for e in emails:
                print(e)
            print(f"-- {len(emails)} subscriber(s)")
        elif args.cmd == "count":
            print(f"{len(load())} subscriber(s)")
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
