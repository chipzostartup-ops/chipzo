#!/usr/bin/env python3
"""Copy a generated file to the clipboard — for the platforms with no free API.

    python automation/channels/clipboard.py content/out/<slug>/linkedin.txt
    python automation/channels/clipboard.py --from content/pages/interview-bank.html

Every copy is read back and compared. tkinter is NOT used first: a Tk window
that is destroyed immediately leaves Windows holding a clipboard reference the
process no longer services, so the copy silently evaporates and the paste comes
out empty. SetClipboardData reaches the real clipboard and survives exit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _win_write(text: str) -> bool:
    """Win32 SetClipboardData(CF_UNICODETEXT). Owns the data, so it survives exit."""
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.restype = wintypes.BOOL

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    payload = text.encode("utf-16-le") + b"\x00\x00"

    if not user32.OpenClipboard(None):
        return False
    ok = False
    handle = None
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return False
        ctypes.memmove(ptr, payload, len(payload))
        kernel32.GlobalUnlock(handle)
        # On success the clipboard owns the handle; do not free it.
        ok = bool(user32.SetClipboardData(CF_UNICODETEXT, handle))
        return ok
    finally:
        user32.CloseClipboard()


def _win_read() -> str:
    """Read CF_UNICODETEXT back, so a successful copy can be proven."""
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT = 13

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _tk_write(text: str) -> None:
    """Fallback, kept only for platforms without Win32."""
    import tkinter

    root = tkinter.Tk()
    root.withdraw()
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()
    root.destroy()


def copy(text: str) -> None:
    if sys.platform == "win32":
        if _win_write(text):
            return
        import subprocess

        subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd())"],
                       input=text.encode("utf-8"), check=True)
        return
    _tk_write(text)


def read_back() -> str:
    if sys.platform == "win32":
        return _win_read()
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        value = root.clipboard_get()
        root.destroy()
        return value
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Copy generated content to clipboard")
    ap.add_argument("file", help="file to copy")
    ap.add_argument("--strip-front", action="store_true", help="drop lines above the first blank line")
    ap.add_argument("--from", dest="noop", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--no-verify", action="store_true", help="skip the read-back check")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"FAILED: no such file: {path}")
        return 1

    text = path.read_text(encoding="utf-8")
    if args.strip_front and "\n\n" in text:
        text = text.split("\n\n", 1)[1]

    copy(text)

    if args.no_verify:
        print(f"OK: {len(text)} chars copied (unverified).")
        return 0

    back = read_back()
    if back.strip() != text.strip():
        print(f"FAILED: clipboard holds {len(back)} chars, expected {len(text)}.")
        print("Another app may be holding the clipboard. Close it and retry.")
        return 1

    print(f"OK: {len(text)} chars copied and verified. Paste now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
