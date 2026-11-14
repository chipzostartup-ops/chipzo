#!/usr/bin/env python3
"""Copy a generated file to the clipboard — for the platforms with no free API.

    python automation/channels/clipboard.py content/out/<slug>/linkedin.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def copy(text: str) -> None:
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return
    except Exception:
        pass

    if sys.platform == "win32":
        import subprocess

        subprocess.run(["clip"], input=text.encode("utf-16le"), check=True)
        return

    raise RuntimeError("clipboard unavailable: install tkinter or xclip")


def main() -> int:
    ap = argparse.ArgumentParser(description="Copy generated content to clipboard")
    ap.add_argument("file")
    ap.add_argument("--strip-front", action="store_true", help="drop lines above the first blank line")
    args = ap.parse_args()

    text = Path(args.file).read_text(encoding="utf-8")
    if args.strip_front and "\n\n" in text:
        text = text.split("\n\n", 1)[1]
    copy(text)
    print(f"OK: {len(text)} chars copied. Paste it into the app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
