#!/usr/bin/env python3
"""
CHIPZO REPURPOSING ENGINE
=========================
One markdown source file  ->  every platform's native format.

Usage
-----
    python automation/repurpose.py content/drafts/my-post.md
    python automation/repurpose.py --all
    python automation/repurpose.py --all --force

Source file format (front matter is optional but recommended):

    ---
    title: Setup Time vs Hold Time
    slug: setup-time-vs-hold-time
    keyword: setup time and hold time
    hook: 90% of VLSI interviews start with this question.
    cta: Save this for your next interview.
    tags: sta, timing, interview
    ---

    ## What setup time actually means

    Setup time is ...
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DRAFTS,
    OUT,
    first_sentence,
    load_config,
    now_utc,
    read_json,
    slugify,
    strip_md,
    write_json,
    write_text,
)

PLATFORM_FILES = [
    "blog.html",
    "linkedin.txt",
    "instagram_carousel.txt",
    "instagram_reel.txt",
    "telegram.md",
    "whatsapp.txt",
    "facebook.txt",
    "x_thread.txt",
    "email.md",
    "manifest.json",
]

# ---------------------------------------------------------------- parsing ----


def parse_front_matter(text: str) -> tuple[dict, str]:
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm, body = parts[1], parts[2]
    meta: dict = {}
    for line in fm.splitlines():
        line = line.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            meta[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
        else:
            meta[key] = val.strip("\"'")
    return meta, body.lstrip("\n")


KEY_SECTION_WORDS = ("takeaway", "key point", "summary", "in short", "tl;dr", "tldr", "bottom line")


def analyze(md: str) -> dict:
    """Pull the pieces every platform template needs."""
    lines = md.splitlines()
    headings, bullets, paras, code_blocks = [], [], [], []
    sections: dict[str, list[str]] = {}
    current = ""
    buf: list[str] = []
    in_code = False
    code_buf: list[str] = []

    def flush_para():
        nonlocal buf
        if buf:
            paras.append(" ".join(buf).strip())
            buf = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("```"):
            flush_para()
            if in_code:
                code_blocks.append("\n".join(code_buf))
                code_buf = []
            in_code = not in_code
            continue
        if in_code:
            code_buf.append(raw)
            continue
        if not line:
            flush_para()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            current = m.group(2).strip()
            headings.append(current)
            continue
        if re.match(r"^[-*+]\s+", line):
            flush_para()
            b = strip_md(re.sub(r"^[-*+]\s+", "", line))
            bullets.append(b)
            sections.setdefault(current, []).append(b)
            continue
        if re.match(r"^\d+\.\s+", line):
            flush_para()
            b = strip_md(re.sub(r"^\d+\.\s+", "", line))
            bullets.append(b)
            sections.setdefault(current, []).append(b)
            continue
        buf.append(line)
    flush_para()

    return {
        "headings": headings,
        "bullets": [b for b in bullets if b],
        "sections": sections,
        "paras": [p for p in paras if p],
        "code_blocks": code_blocks,
        "first_para": paras[0] if paras else "",
    }


def meta_for(md_path: Path, md: str) -> dict:
    meta, body = parse_front_matter(md)
    meta["_body"] = body

    stem = md_path.stem
    date_part = ""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[-_](.+)$", stem)
    if m:
        date_part, stem = m.group(1), m.group(2)

    title = meta.get("title") or stem.replace("-", " ").replace("_", " ").title()
    meta.setdefault("title", title)
    meta.setdefault("slug", slugify(meta.get("title", stem)))
    meta.setdefault("keyword", meta["slug"].replace("-", " "))
    meta.setdefault("date", date_part or now_utc().strftime("%Y-%m-%d"))
    meta.setdefault("tags", [])
    if isinstance(meta["tags"], str):
        meta["tags"] = [t.strip() for t in meta["tags"].split(",") if t.strip()]
    return meta


# ------------------------------------------------------------ md -> html ----


def _inline(t: str) -> str:
    t = htmllib.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue

        if s.startswith("```"):
            lang = s[3:].strip()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            body = htmllib.escape("\n".join(buf))
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{body}</code></pre>")
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lvl, txt = len(m.group(1)), m.group(2)
            out.append(f'<h{lvl} id="{slugify(txt)}">{_inline(txt)}</h{lvl}>')
            i += 1
            continue

        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote><p>" + _inline(" ".join(buf)) + "</p></blockquote>")
            continue

        if re.match(r"^[-*+]\s+", s):
            buf = []
            while i < len(lines) and re.match(r"^[-*+]\s+", lines[i].strip()):
                buf.append(re.sub(r"^[-*+]\s+", "", lines[i].strip()))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(b)}</li>" for b in buf) + "</ul>")
            continue

        if re.match(r"^\d+\.\s+", s):
            buf = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                buf.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            out.append("<ol>" + "".join(f"<li>{_inline(b)}</li>" for b in buf) + "</ol>")
            continue

        buf = []
        while (
            i < len(lines)
            and lines[i].strip()
            and not re.match(r"^(#{1,6}\s|[-*+]\s|\d+\.\s|>|```)", lines[i].strip())
        ):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + _inline(" ".join(buf)) + "</p>")

    return "\n".join(out)


# -------------------------------------------------------------- builders ----


def default_hook(meta: dict, sec: dict) -> str:
    if meta.get("hook"):
        return str(meta["hook"])
    title = meta["title"]
    return f"{title} — explained properly, in under 2 minutes."


def pick(seq: list[str], n: int) -> list[str]:
    """First n items, de-duplicated."""
    out, seen = [], set()
    for item in seq:
        key = re.sub(r"[^a-z0-9]", "", item.lower())[:60]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) == n:
            break
    return out


def spread(seq: list[str], n: int) -> list[str]:
    """n items sampled evenly across the list, de-duplicated."""
    clean, seen = [], set()
    for item in seq:
        key = re.sub(r"[^a-z0-9]", "", item.lower())[:60]
        if not key or key in seen:
            continue
        seen.add(key)
        clean.append(item)
    if len(clean) <= n:
        return clean
    step = len(clean) / n
    return [clean[min(len(clean) - 1, int(i * step))] for i in range(n)]


def key_points(sec: dict, n: int = 6) -> list[str]:
    """Prefer an explicit 'key takeaways / summary' section, else sample the doc."""
    for heading, items in sec.get("sections", {}).items():
        if any(w in heading.lower() for w in KEY_SECTION_WORDS) and len(items) >= 3:
            got = pick(items, n)
            if len(got) >= 3:
                return got
    if sec["bullets"]:
        return spread(sec["bullets"], n)
    if sec["headings"]:
        return pick(sec["headings"], n)
    return [first_sentence(p, 120) for p in sec["paras"][:n]]


def build_blog(meta: dict, sec: dict, cfg: dict) -> str:
    brand = cfg["brand"]
    body_html = md_to_html(meta["_body"])
    desc = first_sentence(
        strip_md(meta.get("description") or sec["first_para"] or meta["title"]), 155
    )
    canonical = f"{brand['site'].rstrip('/')}/{meta['slug']}.html"
    cta = meta.get("cta") or "Save this for your next interview."

    # jump break after the first paragraph for Blogger
    body_html = body_html.replace("</p>", "</p>\n<!-- more -->", 1)

    toc_items = "".join(
        f'<li><a href="#{slugify(h)}">{htmllib.escape(h)}</a></li>' for h in sec["headings"][:12]
    )
    toc = f'<div class="toc"><strong>In this post</strong><ul>{toc_items}</ul></div>' if toc_items else ""

    product = brand.get("product_url") or brand.get("lead_magnet_url") or ""

    schema = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": meta["title"],
        "description": desc,
        "datePublished": meta["date"],
        "author": {"@type": "Organization", "name": brand["name"]},
        "publisher": {"@type": "Organization", "name": brand["name"]},
        "mainEntityOfPage": canonical,
        "keywords": ", ".join(meta["tags"]) if meta["tags"] else meta["keyword"],
    }

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{htmllib.escape(meta['title'])} | {brand['name']}</title>
<meta name="description" content="{htmllib.escape(desc)}">
<meta name="keywords" content="{htmllib.escape(meta['keyword'])}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{htmllib.escape(meta['title'])}">
<meta property="og:description" content="{htmllib.escape(desc)}">
<meta property="og:site_name" content="{brand['name']}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
<style>
:root{{--bg:#0B1020;--fg:#F5F7FA;--accent:#00E5A0;--muted:#9AA4B2}}
body{{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,system-ui,sans-serif;
line-height:1.75;font-size:18px}}
main{{max-width:720px;margin:0 auto;padding:48px 20px 96px}}
h1{{font-size:2rem;line-height:1.25;margin:0 0 .5rem}}
h2{{font-size:1.35rem;margin:2.2rem 0 .6rem;color:var(--accent)}}
h3{{font-size:1.1rem;margin:1.6rem 0 .4rem}}
p,li{{color:#DCE3EC}}
a{{color:var(--accent)}}
code{{background:#151C2E;padding:.15em .4em;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:.9em}}
pre{{background:#151C2E;padding:16px;border-radius:8px;overflow:auto}}
blockquote{{border-left:3px solid var(--accent);margin:1.4rem 0;padding:.2rem 1rem;color:var(--muted)}}
.toc{{background:#121A2A;border:1px solid #1E2A40;border-radius:10px;padding:14px 18px;margin:28px 0}}
.toc ul{{margin:.4rem 0 0;padding-left:1.2rem}}
.toc a{{color:#DCE3EC;text-decoration:none;font-size:.95rem}}
.cta{{background:linear-gradient(135deg,#0E2A24,#121A2A);border:1px solid #1E5C4A;
border-radius:12px;padding:22px;margin:36px 0}}
.cta a{{display:inline-block;background:var(--accent);color:#062018;font-weight:700;
padding:10px 18px;border-radius:8px;text-decoration:none;margin-top:10px}}
.meta{{color:var(--muted);font-size:.85rem;margin-bottom:24px}}
</style>
</head>
<body>
<main>
<article>
<p class="meta">{brand['name']} · {meta['date']} · {htmllib.escape(meta['keyword'])}</p>
<h1>{htmllib.escape(meta['title'])}</h1>
{toc}
{body_html}
<div class="cta">
<strong>{htmllib.escape(cta)}</strong>
<p>Grab the free {brand['name']} VLSI Interview Bank — 120 questions with answers.</p>
{f'<a href="{htmllib.escape(product)}">Get it free →</a>' if product else ''}
</div>
<p><em>{brand['tagline']}</em></p>
</article>
</main>
</body>
</html>
"""


def build_linkedin(meta: dict, sec: dict, cfg: dict) -> str:
    brand = cfg["brand"]
    hook = default_hook(meta, sec)
    points = key_points(sec, 6)
    if not points:
        points = [first_sentence(p, 120) for p in sec["paras"][1:5]]
    bullets = "\n".join(f"→ {p}" for p in points)
    cta = meta.get("cta") or "Save this. Repost if someone you know is interviewing."
    link = f"{brand['site'].rstrip('/')}/{meta['slug']}.html"

    return f"""{hook}

{bullets}

{cta}

Full breakdown (with diagrams): {link}

{brand['hashtags_linkedin']}
"""


def build_instagram_carousel(meta: dict, sec: dict, cfg: dict) -> str:
    brand = cfg["brand"]
    hook = default_hook(meta, sec)
    points = key_points(sec, 6)

    slides = [f"SLIDE 1 (cover)\nHeadline: {hook}\nSub: {meta['keyword']}"]
    for idx, p in enumerate(points, start=2):
        slides.append(f"SLIDE {idx}\nTitle: {first_sentence(p, 46)}\nBody: {p}")
    last = len(slides) + 1
    slides.append(
        f"SLIDE {last} (CTA)\nHeadline: Save this.\nBody: Free VLSI Interview Bank — link in bio.\n"
        f"Footer: {brand['handle']}"
    )

    return (
        f"=== {meta['title']} — CAROUSEL (1080x1350) ===\n\n"
        + "\n\n".join(slides)
        + f"""

=== CAPTION ===
{hook}

{key_points(sec, 1)[0] if key_points(sec, 1) else first_sentence(sec['first_para'], 120)}
Save this before your next interview 📌
Free Interview Bank → link in bio.

{brand['hashtags_instagram']}
"""
    )


def build_instagram_reel(meta: dict, sec: dict, cfg: dict) -> str:
    brand = cfg["brand"]
    hook = default_hook(meta, sec)
    beats = key_points(sec, 3)
    while len(beats) < 3:
        beats.append("Show the diagram / waveform for this point.")

    return f"""=== {meta['title']} — REEL (1080x1920, 30-45s) ===

0-3s   HOOK (say it while showing the diagram)
       "{hook}"

3-10s  BEAT 1
       Say: {beats[0]}
       On screen: {first_sentence(beats[0], 40)}

10-22s BEAT 2
       Say: {beats[1]}
       On screen: {first_sentence(beats[1], 40)}

22-32s BEAT 3
       Say: {beats[2]}
       On screen: {first_sentence(beats[2], 40)}

32-40s CTA
       Say: "Full explanation on the blog. Follow {brand['handle']} for VLSI."

=== ON-SCREEN TEXT (burn these in) ===
1. {hook}
2. {first_sentence(beats[0], 55)}
3. {first_sentence(beats[1], 55)}
4. {first_sentence(beats[2], 55)}
5. Save this · {brand['handle']}

=== CAPTION ===
{hook}

{key_points(sec, 1)[0] if key_points(sec, 1) else first_sentence(sec['first_para'], 120)}
Follow {brand['handle']} for daily VLSI.

{brand['hashtags_instagram']}
"""


def build_telegram(meta: dict, sec: dict, cfg: dict) -> str:
    brand = cfg["brand"]
    points = key_points(sec, 4)
    body = "\n".join(f"• {p}" for p in points)
    link = f"{brand['site'].rstrip('/')}/{meta['slug']}.html"

    return f"""**{meta['title']}**

{first_sentence(sec['first_para'] or meta['title'], 180)}

{body}

Read the full post → {link}

{brand['tagline']}
"""


def build_whatsapp(meta: dict, sec: dict, cfg: dict) -> str:
    brand = cfg["brand"]
    lead = first_sentence(sec["first_para"] or meta["title"], 130)
    point = key_points(sec, 1)
    point = point[0] if point else ""
    link = f"{brand['site'].rstrip('/')}/{meta['slug']}.html"

    lines = [f"*{meta['title']}*", "", lead]
    if point:
        lines += ["", f"Key point: {point}"]
    lines += ["", f"Full post → {link}"]
    return "\n".join(lines) + "\n"


def build_facebook(meta: dict, sec: dict, cfg: dict) -> str:
    brand = cfg["brand"]
    hook = default_hook(meta, sec)
    points = key_points(sec, 5)
    bullets = "\n".join(f"• {p}" for p in points)
    link = f"{brand['site'].rstrip('/')}/{meta['slug']}.html"

    return f"""{hook}

{bullets}

Which of these have you been asked in an interview? Tell us below 👇

Full explanation: {link}
"""


def build_x_thread(meta: dict, sec: dict, cfg: dict) -> str:
    hook = default_hook(meta, sec)
    points = key_points(sec, 5)
    link = f"{cfg['brand']['site'].rstrip('/')}/{meta['slug']}.html"

    tweets = [f"{hook}\n\nA thread 🧵"]
    for p in points[:5]:
        t = f"{p}"
        if len(t) > 270:
            t = t[:267].rsplit(" ", 1)[0] + "…"
        tweets.append(t)
    tweets.append(f"That's it. Full version with diagrams: {link}")

    return "\n\n---\n\n".join(f"{i}/{len(tweets)}\n{t}" for i, t in enumerate(tweets, 1)) + "\n"


def build_email(meta: dict, sec: dict, cfg: dict) -> str:
    brand = cfg["brand"]
    points = key_points(sec, 3)
    bullets = "\n".join(f"- {p}" for p in points)
    link = f"{brand['site'].rstrip('/')}/{meta['slug']}.html"

    return f"""Subject: {meta['title']}
Preview: {first_sentence(sec['first_para'] or meta['title'], 90)}

Hi,

{first_sentence(sec['first_para'] or meta['title'], 300)}

In this post:

{bullets}

Read it here: {link}

— {brand['name']}
{brand['tagline']}

---
Reply STOP to unsubscribe.
"""


BUILDERS = {
    "blog.html": build_blog,
    "linkedin.txt": build_linkedin,
    "instagram_carousel.txt": build_instagram_carousel,
    "instagram_reel.txt": build_instagram_reel,
    "telegram.md": build_telegram,
    "whatsapp.txt": build_whatsapp,
    "facebook.txt": build_facebook,
    "x_thread.txt": build_x_thread,
    "email.md": build_email,
}


# ------------------------------------------------------------------ main ----


def process(md_path: Path, cfg: dict, force: bool = False) -> Path:
    raw = md_path.read_text(encoding="utf-8")
    meta = meta_for(md_path, raw)
    sec = analyze(meta["_body"])

    out_dir = OUT / meta["slug"]
    manifest_path = out_dir / "manifest.json"

    if not force and manifest_path.exists():
        existing = read_json(manifest_path, {}) or {}
        if existing.get("generated_at") and existing.get("source_mtime") == md_path.stat().st_mtime:
            print(f"  = {meta['slug']} (unchanged)")
            return out_dir

    if not sec["paras"] and not sec["bullets"]:
        print(f"  ! {md_path.name}: no body content, skipping")
        return out_dir

    for filename, builder in BUILDERS.items():
        write_text(out_dir / filename, builder(meta, sec, cfg))

    manifest = {
        "slug": meta["slug"],
        "title": meta["title"],
        "date": meta["date"],
        "keyword": meta["keyword"],
        "tags": meta["tags"],
        "hook": default_hook(meta, sec),
        "source": md_path.name,
        "source_mtime": md_path.stat().st_mtime,
        "generated_at": now_utc().isoformat(timespec="seconds"),
        "files": PLATFORM_FILES,
    }
    write_json(manifest_path, manifest)
    print(f"  + {meta['slug']}  ->  {len(BUILDERS)} platform files")
    return out_dir


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn one markdown post into every platform format.")
    ap.add_argument("paths", nargs="*", help="draft markdown file(s)")
    ap.add_argument("--all", action="store_true", help="process every file in content/drafts")
    ap.add_argument("--force", action="store_true", help="regenerate even if unchanged")
    args = ap.parse_args()

    cfg = load_config()

    if args.all:
        files = sorted(p for p in DRAFTS.glob("*.md"))
    elif args.paths:
        files = [Path(p) if Path(p).is_absolute() else (DRAFTS.parent.parent / p) for p in args.paths]
        files = [f if f.exists() else DRAFTS / f.name for f in files]
    else:
        files = []

    if not files:
        ap.print_help()
        print("\nNo input files found. Add a .md file to content/drafts/ and run with --all.")
        return 1

    print(f"Repurposing {len(files)} file(s)...")
    for f in files:
        if not f.exists():
            print(f"  ! not found: {f}")
            continue
        process(f, cfg, force=args.force)

    print(f"\nDone. Output: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
