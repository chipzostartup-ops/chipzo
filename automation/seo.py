#!/usr/bin/env python3
"""
FREE KEYWORD RESEARCH — no API key, no Ahrefs, no limits.

Uses Google's public autocomplete endpoint (what people actually type) plus
optional-seed expansion, and clusters results into content ideas.

    python automation/seo.py --seed "vlsi"
    python automation/seo.py --seed "verilog" --seed "static timing analysis"
    python automation/seo.py --from-drafts          # expand from your own titles
    python automation/seo.py --seed "dft" --alphabet

Output: content/keywords.csv  (sorted by estimated opportunity)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import CONTENT, DRAFTS, OUT, slugify  # noqa: E402

ENDPOINT = "http://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=in&q="

# Cheap intent signal — these modifiers mean someone is close to a decision.
INTENT_HIGH = ("salary", "interview", "job", "jobs", "course", "fees", "vs", "how to", "which", "best")
INTENT_LOW = ("what is", "definition", "meaning", "full form", "pdf", "notes")

MODIFIERS = (
    "interview questions",
    "for freshers",
    "salary",
    "vs",
    "tutorial",
    "pdf",
    "notes",
    "roadmap",
    "course",
    "projects",
    "jobs",
    "questions",
)


def fetch(query: str, retries: int = 2) -> list[str]:
    url = ENDPOINT + urllib.parse.quote(query)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", "replace")
            data = json.loads(raw)
            return [s for s in data[1] if isinstance(s, str)]
        except Exception:
            if attempt == retries:
                return []
            time.sleep(1.5)
    return []


def score(keyword: str) -> int:
    k = keyword.lower()
    s = 50
    s += 20 if any(w in k for w in INTENT_HIGH) else 0
    s -= 10 if any(w in k for w in INTENT_LOW) else 0
    s += 10 if len(k.split()) >= 4 else 0  # long tail = easier to rank
    return max(1, min(100, s))


def exists_in_drafts(keyword: str) -> bool:
    target = slugify(keyword)
    for p in list(DRAFTS.glob("*.md")) + list(OUT.glob("*/manifest.json")):
        if target[:28] in p.name.lower().replace("_", "-"):
            return True
    return False


def mine(seeds: list[str], alphabet: bool) -> list[dict]:
    queries: list[str] = []
    for seed in seeds:
        queries.append(seed)
        for mod in MODIFIERS:
            queries.append(f"{seed} {mod}")
    if alphabet:
        for seed in seeds:
            for ch in "abcdefghijklmnopqrstuvwxyz":
                queries.append(f"{seed} {ch}")

    seen: dict[str, dict] = {}
    for q in queries:
        for suggestion in fetch(q):
            key = suggestion.lower().strip()
            if key in seen:
                continue
            seen[key] = {
                "keyword": suggestion.strip(),
                "seed": q.split()[0] if q.split() else q,
                "score": score(suggestion),
                "words": len(suggestion.split()),
                "have_draft": "yes" if exists_in_drafts(suggestion) else "",
            }
        time.sleep(0.12)  # be polite, avoid rate limiting

    return sorted(seen.values(), key=lambda r: (-r["score"], -r["words"]))


def from_drafts() -> list[str]:
    seeds = []
    for p in sorted(DRAFTS.glob("*.md")):
        stem = re.sub(r"^\d{4}-\d{2}-\d{2}[-_]", "", p.stem).replace("-", " ")
        seeds.append(stem)
    for p in OUT.glob("*/manifest.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
            if m.get("keyword"):
                seeds.append(m["keyword"])
        except Exception:
            pass
    return seeds


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["keyword", "seed", "score", "words", "have_draft"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Free keyword miner (Google Suggest)")
    ap.add_argument("--seed", action="append", default=[])
    ap.add_argument("--from-drafts", action="store_true")
    ap.add_argument("--alphabet", action="store_true", help="a-z expansion (slow, thorough)")
    ap.add_argument("--out", default=str(CONTENT / "keywords.csv"))
    args = ap.parse_args()

    seeds = list(args.seed)
    if args.from_drafts:
        seeds += from_drafts()
    if not seeds:
        seeds = ["vlsi", "verilog", "static timing analysis", "physical design", "dft", "uvm"]

    seeds = list(dict.fromkeys(s.strip() for s in seeds if s.strip()))
    print(f"Mining {len(seeds)} seed(s) x {len(MODIFIERS) + 1} modifiers...")

    rows = mine(seeds, args.alphabet)
    if not rows:
        print("No suggestions returned (network blocked?). Try again or use a VPN-free connection.")
        return 1

    out = Path(args.out) if Path(args.out).is_absolute() else Path(args.out)
    write_csv(rows, out)

    fresh = [r for r in rows if not r["have_draft"]]
    print(f"\n{len(rows)} keywords, {len(fresh)} not yet covered.")
    print(f"Saved -> {out}\n")
    print(f"{'SCORE':<7}{'KW'}")
    print("-" * 78)
    for r in rows[:25]:
        print(f"{r['score']:<7}{r['keyword'][:68]}")
    print("\nNext: pick 3 with score >= 70, write them as drafts, run repurpose.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
