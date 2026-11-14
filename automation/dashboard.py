#!/usr/bin/env python3
"""
Builds dashboard/index.html — a single self-contained file you can open
directly (no server, no dependencies, works offline).

    python automation/dashboard.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DASHBOARD,
    OUT,
    ROOT,
    STATE,
    load_config,
    now_utc,
    parse_dt,
    read_json,
    write_text,
)

QUEUE_PATH = STATE / "queue.json"


def collect() -> dict:
    cfg = load_config()
    queue = read_json(QUEUE_PATH, {}) or {"items": []}
    items = queue.get("items", [])
    manifests = [read_json(p, {}) for p in sorted(OUT.glob("*/manifest.json"))]
    manifests = [m for m in manifests if isinstance(m, dict) and m.get("slug")]

    status_counts = Counter(i.get("status", "pending") for i in items)
    platform_counts = Counter(i.get("platform") for i in items)
    by_day: dict[str, int] = defaultdict(int)
    for i in items:
        try:
            by_day[parse_dt(i["scheduled_at"]).strftime("%Y-%m-%d")] += 1
        except Exception:
            pass

    now = now_utc()
    upcoming = sorted(
        (i for i in items if i.get("status") == "pending"),
        key=lambda i: i.get("scheduled_at", ""),
    )
    next7 = [i for i in upcoming if parse_dt(i["scheduled_at"]) <= now + timedelta(days=7)]

    return {
        "brand": cfg.get("brand", {}),
        "dry_run": cfg.get("publish", {}).get("dry_run", True),
        "generated": now.isoformat(timespec="seconds"),
        "totals": {
            "items": len(items),
            "topics": len(manifests),
            "pending": status_counts.get("pending", 0),
            "sent": status_counts.get("sent", 0),
            "failed": status_counts.get("failed", 0),
            "manual": sum(1 for i in items if i.get("manual")),
            "next7": len(next7),
        },
        "platforms": platform_counts.most_common(),
        "upcoming": [
            {
                "when": i["scheduled_at"][:16].replace("T", " "),
                "platform": i["platform"],
                "title": i.get("title", ""),
                "manual": bool(i.get("manual")),
                "status": i.get("status", ""),
                "error": (i.get("last_error") or "")[:120],
            }
            for i in upcoming[:40]
        ],
        "timeline": sorted(by_day.items())[:60],
        "topics": [
            {"title": m.get("title"), "slug": m.get("slug"), "date": m.get("date")}
            for m in manifests
        ][-20:],
    }


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chipzo Control Room</title>
<style>
:root{--bg:#0B1020;--card:#121A2A;--line:#1E2A40;--fg:#F5F7FA;--muted:#8B97A8;--accent:#00E5A0;--warn:#FFB020;--bad:#FF5C5C}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,system-ui,-apple-system,sans-serif}
header{padding:28px 32px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px}
h1{margin:0;font-size:22px;letter-spacing:-.3px}
h1 span{color:var(--accent)}
.sub{color:var(--muted);font-size:13px;margin-top:4px}
main{padding:24px 32px 64px;max-width:1200px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:26px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.card .n{font-size:30px;font-weight:700;letter-spacing:-1px}
.card .l{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em;margin-top:2px}
.card.good .n{color:var(--accent)} .card.warn .n{color:var(--warn)} .card.bad .n{color:var(--bad)}
section{margin-bottom:30px}
section h2{font-size:13px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:0 0 12px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;color:var(--muted);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.06em;padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:10px;border-bottom:1px solid #16203400}
tr:hover td{background:#0F1626}
.pill{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;border:1px solid var(--line);color:var(--muted)}
.pill.auto{color:var(--accent);border-color:#0F5B46}
.pill.manual{color:var(--warn);border-color:#5B440F}
.pill.sent{color:var(--accent);border-color:#0F5B46}
.pill.failed{color:var(--bad);border-color:#5B1414}
.bars{display:flex;align-items:flex-end;gap:3px;height:90px;margin-top:8px}
.bars div{flex:1;background:var(--accent);border-radius:2px 2px 0 0;opacity:.75;min-height:3px}
.barwrap{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.barwrap .lbl{display:flex;justify-content:space-between;font-size:12px;color:var(--muted)}
code{background:#0A101C;padding:1px 5px;border-radius:4px;font-size:12px;color:var(--accent)}
.empty{color:var(--muted);font-size:14px;padding:18px 0}
.err{color:var(--bad);font-size:12px}
footer{color:var(--muted);font-size:12px;padding:0 32px 40px}
</style>
</head>
<body>
<header>
  <div>
    <h1>__BRAND__ <span>control room</span></h1>
    <div class="sub">__TAGLINE__</div>
  </div>
  <div class="sub">Built __GENERATED__ &middot; dry run: <code>__DRY__</code></div>
</header>
<main>
  <div class="grid" id="cards"></div>

  <section>
    <h2>Upcoming queue</h2>
    <table id="queue"></table>
  </section>

  <section>
    <h2>Volume by platform</h2>
    <div class="grid" id="platforms"></div>
  </section>

  <section>
    <h2>Publishing timeline</h2>
    <div class="barwrap">
      <div class="lbl"><span id="tl-start"></span><span id="tl-end"></span></div>
      <div class="bars" id="timeline"></div>
    </div>
  </section>

  <section>
    <h2>Topics generated</h2>
    <table id="topics"></table>
  </section>
</main>
<footer>
  Regenerate with <code>python automation/dashboard.py</code> &middot;
  publish due items with <code>python automation/run_daily.py</code>
</footer>
<script>
const DATA = __DATA__;

const card = (n, l, cls='') =>
  `<div class="card ${cls}"><div class="n">${n}</div><div class="l">${l}</div></div>`;

document.getElementById('cards').innerHTML = [
  card(DATA.totals.pending, 'pending'),
  card(DATA.totals.next7, 'due in 7 days'),
  card(DATA.totals.sent, 'published', 'good'),
  card(DATA.totals.failed, 'failed', DATA.totals.failed ? 'bad' : ''),
  card(DATA.totals.manual, 'manual tasks'),
  card(DATA.totals.topics, 'topics'),
].join('');

const q = document.getElementById('queue');
q.innerHTML = `<tr><th>When</th><th>Platform</th><th>Title</th><th>Mode</th><th>Error</th></tr>` +
  (DATA.upcoming.length ? DATA.upcoming.map(i => `<tr>
    <td>${i.when}</td>
    <td><span class="pill">${i.platform}</span></td>
    <td>${i.title}</td>
    <td>${i.manual ? '<span class="pill manual">manual</span>' : '<span class="pill auto">auto</span>'}</td>
    <td class="err">${i.error || ''}</td></tr>`).join('')
  : `<tr><td colspan="5" class="empty">Nothing scheduled. Run <code>python automation/queue.py build</code></td></tr>`);

document.getElementById('platforms').innerHTML = DATA.platforms.length
  ? DATA.platforms.map(([p, n]) => card(n, p)).join('')
  : `<div class="empty">No items yet.</div>`;

const tl = DATA.timeline;
const max = Math.max(1, ...tl.map(t => t[1]));
document.getElementById('timeline').innerHTML =
  tl.map(([d, n]) => `<div style="height:${Math.round(n / max * 100)}%" title="${d}: ${n}"></div>`).join('');
if (tl.length) {
  document.getElementById('tl-start').textContent = tl[0][0];
  document.getElementById('tl-end').textContent = tl[tl.length - 1][0];
}

const t = document.getElementById('topics');
t.innerHTML = `<tr><th>Date</th><th>Title</th><th>Slug</th></tr>` +
  (DATA.topics.length ? DATA.topics.slice().reverse().map(x => `<tr>
    <td>${x.date || ''}</td><td>${x.title || ''}</td>
    <td><code>${x.slug || ''}</code></td></tr>`).join('')
  : `<tr><td colspan="3" class="empty">No content generated yet.</td></tr>`);
</script>
</body>
</html>
"""


def main() -> int:
    data = collect()
    brand = data["brand"]
    html = (
        HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
        .replace("__BRAND__", brand.get("name", "Chipzo"))
        .replace("__TAGLINE__", brand.get("tagline", ""))
        .replace("__GENERATED__", data["generated"][:16].replace("T", " "))
        .replace("__DRY__", "true" if data["dry_run"] else "false")
    )
    out = DASHBOARD / "index.html"
    write_text(out, html)
    print(f"Dashboard written -> {out}")
    print(f"  pending={data['totals']['pending']} sent={data['totals']['sent']} "
          f"failed={data['totals']['failed']} topics={data['totals']['topics']}")
    print("  open it: start dashboard/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
