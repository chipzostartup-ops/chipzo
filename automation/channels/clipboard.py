#!/usr/bin/env python3
"""Copy a generated file to the clipboard — for the platforms with no free API.

    python automation/channels/clipboard.py content/out/<slug>/linkedin.txt
    python automation/channels/clipboard.py content/pages/interview-bank.html

Windows gets two formats at once:

  CF_HTML          formatted HTML, so a rich-text editor (Blogger's Compose
                   view, Gmail, Word) inserts real headings/links/buttons
  CF_UNICODETEXT   the raw source, so an HTML-view box still pastes correctly

Every copy is read back and compared before success is reported. tkinter is
avoided on Windows: a Tk window that is destroyed immediately leaves the
clipboard pointing at data the dead process no longer serves, so the copy
silently evaporates and the paste comes out empty.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

_HTML_OPEN = "<html><body>\r\n<!--StartFragment-->"
_HTML_CLOSE = "<!--EndFragment-->\r\n</body></html>"


def _libs():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    return ctypes, user32, kernel32


def cf_html(fragment: str) -> bytes:
    """Wrap a fragment in the Microsoft 'HTML Format' envelope.

    The offsets in the header are byte offsets into the finished payload, and
    the header length depends on the offsets themselves, so it is rendered
    twice: once with zeros to measure, once for real.
    """
    def render(start_html: int, end_html: int, start_frag: int, end_frag: int) -> str:
        return (
            "Version:0.9\r\n"
            f"StartHTML:{start_html:010d}\r\n"
            f"EndHTML:{end_html:010d}\r\n"
            f"StartFragment:{start_frag:010d}\r\n"
            f"EndFragment:{end_frag:010d}\r\n"
        )

    header = render(0, 0, 0, 0)
    body = _HTML_OPEN + fragment + _HTML_CLOSE

    start_html = len(header.encode("utf-8"))
    start_frag = start_html + len(_HTML_OPEN.encode("utf-8"))
    end_frag = start_frag + len(fragment.encode("utf-8"))
    end_html = start_html + len(body.encode("utf-8"))

    header = render(start_html, end_html, start_frag, end_frag)
    return (header + body).encode("utf-8")


def _win_set(formats: dict[int, bytes]) -> bool:
    ctypes, user32, kernel32 = _libs()

    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        for fmt, payload in formats.items():
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, max(1, len(payload)))
            if not handle:
                return False
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return False
            try:
                ctypes.memmove(ptr, payload, len(payload))
            finally:
                kernel32.GlobalUnlock(handle)
            # On success the clipboard owns the handle; never free it.
            if not user32.SetClipboardData(fmt, handle):
                return False
        return True
    finally:
        user32.CloseClipboard()


def _win_read() -> str:
    ctypes, user32, kernel32 = _libs()
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
    import tkinter

    root = tkinter.Tk()
    root.withdraw()
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()
    root.destroy()


def looks_like_html(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("<") and ">" in stripped


def copy(text: str, as_html: bool | None = None) -> None:
    rich = looks_like_html(text) if as_html is None else as_html

    if sys.platform == "win32":
        _, user32, _ = _libs()
        formats = {CF_UNICODETEXT: text.encode("utf-16-le") + b"\x00\x00"}
        if rich:
            html_fmt = user32.RegisterClipboardFormatW("HTML Format")
            if html_fmt:
                formats[html_fmt] = cf_html(text)
        if _win_set(formats):
            return
        import subprocess

        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd())"],
            input=text.encode("utf-8"),
            check=True,
        )
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
    ap.add_argument("--plain", action="store_true", help="force plain text even if the file is HTML")
    ap.add_argument("--no-verify", action="store_true", help="skip the read-back check")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"FAILED: no such file: {path}")
        return 1

    text = path.read_text(encoding="utf-8")
    if args.strip_front and "\n\n" in text:
        text = text.split("\n\n", 1)[1]

    as_html = False if args.plain else None
    rich = looks_like_html(text) if as_html is None else as_html
    copy(text, as_html=rich)

    if args.no_verify:
        print(f"OK: {len(text)} chars copied (unverified).")
        return 0

    back = read_back()
    if back.strip() != text.strip():
        print(f"FAILED: clipboard holds {len(back)} chars, expected {len(text)}.")
        print("Another app may be holding the clipboard. Close it and retry.")
        return 1

    kind = "formatted HTML" if rich else "plain text"
    print(f"OK: {len(text)} chars copied and verified as {kind}.")
    if rich:
        print("Paste directly into Compose view - no HTML toggle needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
