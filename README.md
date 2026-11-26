# CHIPZO — Zero-Investment Growth System

VLSI / semiconductor brand. Blog + services + digital products.
Everything here runs on **free tiers and free APIs**. No paid tools. No ads spend.

---

## The core idea

> **Write once. Publish everywhere. Automate the boring 80%.**

You create **one source file per topic**. The engine turns it into a blog post,
LinkedIn post, Instagram carousel, Instagram reel script, Telegram message,
WhatsApp broadcast, Facebook post and an X thread — then a scheduler pushes
whatever the free APIs allow, and gives you copy-paste blocks for the rest.

```
content/drafts/2026-11-14-setup-time-vs-hold-time.md
                 │
                 ▼  python automation/repurpose.py
content/out/setup-time-vs-hold-time/
     ├── blog.html              ← Blogger (auto-post via SMTP)
     ├── linkedin.txt           ← copy-paste (LinkedIn API is locked)
     ├── instagram_carousel.txt ← copy-paste / Meta Graph API
     ├── instagram_reel.txt     ← film from this script
     ├── telegram.md            ← auto via Bot API
     ├── whatsapp.txt           ← auto via Cloud API or wa.me links
     ├── facebook.txt           ← auto via Graph API
     ├── x_thread.txt           ← copy-paste
     └── email.md               ← auto via Brevo free tier
```

---

## What is actually automated (be honest with yourself)

| Platform | Automation level | How | Cost |
|---|---|---|---|
| **Blogger** | ✅ Full auto | HTML email → Blogger "post by email" (or API v3) | ₹0 |
| **Telegram** | ✅ Full auto | Bot API `sendMessage` / `sendPhoto` | ₹0 |
| **WhatsApp Channel** | 🟡 Semi | Generated copy + `wa.me` links; Cloud API for real automation | ₹0 / free tier |
| **Facebook Page** | ✅ Auto (after app setup) | Graph API `/{page-id}/feed` | ₹0 |
| **Instagram** | 🟡 Auto images only | Graph API `media` + `media_publish` (needs public image URL) | ₹0 |
| **LinkedIn** | 🔴 Copy-paste | API is partner-only. Use the generated block + free Buffer plan | ₹0 |
| **X / Twitter** | 🔴 Copy-paste | Free API tier is read-mostly now | ₹0 |
| **Email list** | ✅ Auto | Brevo free 300 emails/day | ₹0 |
| **Scheduling** | ✅ | GitHub Actions cron (free minutes on public repos) | ₹0 |
| **Analytics** | ✅ | Blogger + Telegram stats pulled into one HTML dashboard | ₹0 |

**Rule:** if a platform blocks free automation, you do 30 seconds of copy-paste.
Do not pay for a scheduler in month 1.

---

## Quick start — connect FIRST, content second

> **Note on this machine:** the bare `python` command is the Microsoft Store
> stub and fails. Use `py -3` (verified working, Python 3.14).
> In the GitHub Action, `python` is correct.

**Nothing can publish until you connect an account.** The content files are just
text on disk until a platform has access to them.

### The easy way — no typing at all

Open the folder `D:\ai\chipzo` in File Explorer (press `Win+E`, paste
`D:\ai\chipzo` into the address bar, Enter). Then **double-click**:

| File | What it does |
|---|---|
| `1-CONNECT.bat` | Guided setup. Tests each credential before saving. |
| `2-CHECK.bat` | Shows what is connected |
| `3-PUBLISH.bat` | Publishes everything that is due |

The window stays open after each run so you can read the result.

### Step 1 — connect Telegram (5 minutes, fully automatic)

```powershell
cd D:\ai\chipzo
py -3 automation\connect.py
```

Pick `1` and follow the prompts. It **verifies the token against Telegram's
servers before saving it**, and offers to send a real test message to your
channel. If you see `OK @yourbot can post to 'Chipzo · VLSI'` — you are connected.

### Step 2 — check what is live

```powershell
py -3 automation\connect.py --check
```

You should see at least one `LIVE` line. Anything showing `----` is not connected
and will not publish.

### Step 3 — connect Blogger (10 minutes)

```powershell
py -3 automation\connect.py blogger
```

### Step 4 — publish something for real

```powershell
py -3 automation\repurpose.py --all
py -3 automation\queue.py build
py -3 automation\run_daily.py --catchup 1     # sends the oldest item NOW
```

### Step 5 — schedule the rest

```powershell
py -3 automation\run_daily.py                  # publishes whatever is due
py -3 automation\dashboard.py
start dashboard\index.html
```

If the schedule ever falls behind — a failed cron, a week away — every slot ends
up in the past and nothing can publish again, because `build` never moves a post
it has already seen. Shift the backlog forward instead:

```powershell
py -3 automation\queue.py reschedule --start 2026-11-27
py -3 automation\queue.py build                # regenerates the digests
```

Already-sent items keep their dates, so history stays honest.

### Step 6 — hand LinkedIn, X and Facebook to Buffer (free plan)

Buffer's free plan covers 3 channels with an API key, which turns the three
biggest copy-paste chores into scheduled sends:

1. On [buffer.com](https://buffer.com) connect **LinkedIn**, **X** and your
   **Facebook page** — exactly three channels, the free limit.
2. Create a key at **publish.buffer.com/settings/api**.
3. Save it and verify:

```powershell
py -3 automation\connect.py buffer      # asks for the key, checks the channels, enables it
```

Add the same key to GitHub as the `BUFFER_API_KEY` secret, or CI cannot post.
Locally the key may also live in `.buffer-key` (gitignored); CI only reads the
secret.

Once it is on, `run_daily.py` queues LinkedIn, X threads and Facebook posts
through Buffer with the same schedule the blog uses, and `manual_tasks.md` keeps
only WhatsApp and the Instagram scripts. Buffer uses its own posting slots, so
an item scheduled for 08:30 may leave slightly later — that is Buffer picking a
better time, not a missed run.

Platforms with no free API (WhatsApp, IG reels) stay manual on purpose —
`run_daily.py` writes them to `automation/state/manual_tasks.md` with a one-line
copy command for each.

---

## Folder map

```
chipzo/
├── README.md                  ← you are here
├── PLAN-90-DAYS.md            ← the actual growth plan + numbers
├── MONETIZATION.md            ← how Chipzo makes money (offer ladder, prices)
├── PLATFORM-PLAYBOOKS.md      ← per-platform tactics that actually work in VLSI
├── SETUP-FREE-STACK.md        ← step-by-step setup of every free account + key
├── automation/
│   ├── repurpose.py           ← THE core engine
│   ├── queue.py               ← schedule builder
│   ├── run_daily.py           ← dispatcher / cron entry point
│   ├── seo.py                 ← free keyword mining (Google Suggest)
│   ├── dashboard.py           ← static HTML dashboard generator
│   ├── check_env.py           ← validates your keys
│   ├── channels/              ← telegram, blogger, meta, whatsapp senders
│   └── prompts/               ← free-AI prompts (Gemini/ChatGPT) for each platform
├── content/
│   ├── ideas.csv              ← 60 VLSI content ideas, funnel-tagged
│   ├── drafts/                ← your source files (write here)
│   └── out/                   ← generated, never edit by hand
├── brand/
│   ├── brand-kit.md           ← positioning, voice, colors, bio text
│   └── hooks.md               ← 80 hook templates for VLSI content
├── .github/workflows/daily.yml ← free cron automation
└── dashboard/                 ← generated
```

---

## The only three things that matter

1. **Volume of useful specifics.** VLSI people share things that make them
   look smart or pass an interview. Every post should contain a fact a fresher
   can quote in an interview.
2. **Distribution loops.** Blog SEO (slow, compounding) + LinkedIn/FB groups
   (fast, free) + Telegram/WhatsApp (owned, no algorithm).
3. **An owned list.** Followers are rented. Telegram + email are yours.
   Everything funnels to those two.

Start with `PLAN-90-DAYS.md`.
