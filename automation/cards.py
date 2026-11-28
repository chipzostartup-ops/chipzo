#!/usr/bin/env python3
"""Render the Instagram carousel script into 1080x1350 slides.

Instagram cannot be posted to as text, and Buffer has no upload endpoint - it
only accepts a public image URL. So the carousel copy has to become real PNGs
before any of it can go out. This does that with Pillow and no AI: same input,
same pixels, every time, which matters when a pipeline republishes a post.

    python automation/cards.py --slug latch-vs-flip-flop
    python automation/cards.py --all

Output: content/cards/<slug>/slide-1.png ... (committed, so the raw GitHub URL
is a stable public address Buffer can fetch at publish time).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import OUT, ROOT  # noqa: E402

W, H = 1080, 1350
BG = (11, 18, 32)
PANEL = (17, 26, 43)
ACCENT = (56, 189, 248)
TEXT = (248, 250, 252)
MUTED = (148, 163, 184)

CARDS_DIR = ROOT / "content" / "cards"

FONT_CANDIDATES = {
    "bold": [
        r"C:\Windows\Fonts\seguisb.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "regular": [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=f) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def parse_script(text: str) -> list[dict]:
    slides: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        head = re.match(r"^\s*SLIDE\s+(\d+)\s*(?:\((cover|cta)\))?", line, re.I)
        if head:
            current = {"n": int(head.group(1)), "kind": (head.group(2) or "body").lower(), "fields": {}}
            slides.append(current)
            continue
        if current is None:
            continue
        m = re.match(r"^\s*(Headline|Sub|Title|Body|Footer)\s*:\s*(.+)$", line, re.I)
        if m:
            current["fields"][m.group(1).lower()] = m.group(2).strip()
    return slides


def chrome(draw: ImageDraw.ImageDraw, n: int, total: int) -> None:
    """Shared furniture: wordmark, slide counter, hairline."""
    draw.text((64, 60), "CHIPZO", font=font("bold", 30), fill=ACCENT)
    counter = f"{n:02d} / {total:02d}"
    f = font("regular", 28)
    draw.text((W - 64 - draw.textlength(counter, font=f), 62), counter, font=f, fill=MUTED)
    draw.line([(64, H - 96), (W - 64, H - 96)], fill=PANEL, width=2)


def layout(
    draw: ImageDraw.ImageDraw,
    blocks: list[dict],
    width: int,
    top: int = 200,
    bottom: int = H - 150,
) -> list[tuple[str, ImageFont.FreeTypeFont, tuple, int]]:
    """Turn paragraphs into positioned lines, vertically centred in the frame."""
    lines: list[tuple[str, ImageFont.FreeTypeFont, tuple, int]] = []
    for block in blocks:
        f = font(block.get("kind", "regular"), block["size"])
        if block.get("gap") and lines:
            lines.append(("", f, TEXT, block["gap"]))
        for line in wrap(draw, block["text"], f, width):
            lines.append((line, f, block.get("fill", TEXT), block.get("line_height", block["size"] + 18)))
    total = sum(h for *_, h in lines)
    y = top + max(0, (bottom - top - total) // 2)
    positioned = []
    for line, f, fill, h in lines:
        positioned.append((line, f, fill, y))
        y += h
    return positioned


def paint(draw: ImageDraw.ImageDraw, positioned) -> None:
    for line, f, fill, y in positioned:
        if line:
            draw.text((64 if f.size < 60 else 64, y), line, font=f, fill=fill)


def render_cover(slide: dict, total: int) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    chrome(d, slide["n"], total)
    f = slide["fields"]

    blocks = [{"text": f.get("headline", ""), "kind": "bold", "size": 64, "line_height": 80, "fill": TEXT}]
    if f.get("sub"):
        blocks.append({"text": f["sub"], "kind": "regular", "size": 34, "line_height": 48, "fill": ACCENT, "gap": 28})
    lines = layout(d, blocks, W - 128, top=260)
    paint(d, lines)
    # accent rule above the headline
    first_y = lines[0][3] if lines else 360
    d.rectangle([(64, first_y - 56), (128, first_y - 48)], fill=ACCENT)
    return img


def render_body(slide: dict, total: int) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    chrome(d, slide["n"], total)
    f = slide["fields"]

    blocks = []
    if f.get("title"):
        blocks.append({"text": f["title"], "kind": "bold", "size": 52, "line_height": 66, "fill": TEXT})
    if f.get("body"):
        blocks.append({"text": f["body"], "kind": "regular", "size": 40, "line_height": 58, "fill": MUTED, "gap": 44})
    lines = layout(d, blocks, W - 220, top=240)
    paint_offset(d, lines, x=112)
    if lines:
        top = lines[0][3] - 18
        bottom = lines[-1][3] + 62
        d.rectangle([(64, top), (72, bottom)], fill=ACCENT)
    return img


def paint_offset(draw: ImageDraw.ImageDraw, positioned, x: int) -> None:
    for line, f, fill, y in positioned:
        if line:
            draw.text((x, y), line, font=f, fill=fill)


def render_cta(slide: dict, total: int) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    chrome(d, slide["n"], total)
    f = slide["fields"]

    blocks = [{"text": f.get("headline", ""), "kind": "bold", "size": 76, "line_height": 92, "fill": TEXT}]
    if f.get("body"):
        blocks.append({"text": f["body"], "kind": "regular", "size": 40, "line_height": 56, "fill": ACCENT, "gap": 34})
    paint(d, layout(d, blocks, W - 128))
    if f.get("footer"):
        footer = f["footer"]
        ff = font("bold", 34)
        d.text(((W - d.textlength(footer, font=ff)) / 2, H - 190), footer, font=ff, fill=MUTED)
    return img


RENDERERS = {"cover": render_cover, "cta": render_cta, "body": render_body}


def build(slug: str) -> list[Path]:
    source = OUT / slug / "instagram_carousel.txt"
    if not source.exists():
        raise RuntimeError(f"no carousel script: {source}")
    slides = parse_script(source.read_text(encoding="utf-8"))
    if not slides:
        raise RuntimeError(f"could not parse any SLIDE blocks in {source}")

    dest = CARDS_DIR / slug
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for slide in slides:
        img = RENDERERS.get(slide["kind"], render_body)(slide, len(slides))
        path = dest / f"slide-{slide['n']}.png"
        img.save(path, optimize=True)
        written.append(path)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Render Instagram carousel slides")
    ap.add_argument("--slug", help="content slug")
    ap.add_argument("--all", action="store_true", help="every slug that has a carousel script")
    args = ap.parse_args()

    slugs = [p.parent.name for p in OUT.glob("*/instagram_carousel.txt")] if args.all else [args.slug]
    if not any(slugs):
        ap.print_help()
        return 1

    for slug in slugs:
        try:
            paths = build(slug)
        except RuntimeError as exc:
            print(f"FAILED {slug}: {exc}")
            return 1
        print(f"{slug}: {len(paths)} slide(s) -> {paths[0].parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
