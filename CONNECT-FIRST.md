# CONNECT FIRST — read this before anything else

Right now **nothing is connected**. The content files exist, but no platform has
access to them. That is the one thing blocking you.

Run this:

```powershell
cd D:\ai\chipzo
py -3 automation\connect.py
```

It will show a status board, then walk you through each platform. It **tests the
credential against the real API before saving it**, so you never end up with a
config that looks fine and fails at 3am.

---

## Order of operations (do not skip ahead)

| # | Connect | Time | What it unlocks |
|---|---|---|---|
| 1 | Telegram | 5 min | Daily auto-publishing, no API review, no cost |
| 2 | Blogger | 10 min | Free blog that auto-posts from email |
| 3 | Brevo | 5 min | Email list (300 free/day) |
| 4 | Facebook | 10 min | Auto-post to page |
| 5 | Instagram | 20 min | Image posts only |
| 6 | WhatsApp API | optional | Skip it — use the channel manually |

You do **not** need all six. Telegram alone already gives you a working
auto-published channel.

---

## 1. Telegram — the exact taps

**On your phone, in Telegram:**

1. Menu → **New Channel** → name `Chipzo · VLSI` → make it **Public** →
   username `chipzo` → Create
2. Search **@BotFather** → open it → send `/newbot`
3. Name: `Chipzo Publisher` → username: `chipzo_publisher_bot`
4. BotFather replies with a token like `7912345678:AAH...` — copy the whole line
5. Open your channel → tap the channel name → **Administrators** → **Add
   Administrator** → search `chipzo_publisher_bot` → turn on **Post Messages** →
   Save

**On your computer:**

```powershell
py -3 automation\connect.py telegram
```

Paste the token, press Enter for the channel (`@chipzo` is filled in). It will:

- call `getMe` to confirm the token
- call `getChat` to confirm the bot is actually in your channel
- offer to send a test message

**Read the result:**

| What you see | What it means | Fix |
|---|---|---|
| `OK @bot can post to 'Chipzo · VLSI'` | Connected | Nothing — done |
| `token rejected` | Wrong/copied-part token | Copy again from BotFather |
| `bot is not in chat` | Step 5 was skipped | Add the bot as channel admin |
| `nothing saved` | Validation failed | Nothing was written — safe to retry |

---

## 2. Blogger — the exact steps

1. blogger.com → **Create blog** → title `Chipzo` → address `chipzo.blogspot.com`
2. **Settings** → **Email** → next to *Post using email* → **Save**
3. Copy the secret address it reveals (looks like `chipzo.a1b2c3@blogger.com`)
4. Set *Email posts to* → **Publish immediately**

**SMTP** (the account that sends the post): easiest is Brevo.
- brevo.com → free account → **SMTP & API** → **SMTP** tab → generate key
- Host `smtp-relay.brevo.com`, port `587`, username = your Brevo login

```powershell
py -3 automation\connect.py blogger
```

It logs into SMTP for real before saving. If you choose to send a test post, a
real post appears on your blog — that is the proof.

> Gmail alternative: 2-Step Verification must be ON, then Security →
> App passwords → create one. Use that 16-character value, never your normal
> password.

---

## 3. After connecting — the first real publish

```powershell
py -3 automation\connect.py --check          # confirm LIVE lines
py -3 automation\repurpose.py --all          # regenerate outputs
py -3 automation\queue.py build              # schedule
py -3 automation\run_daily.py --catchup 1    # publish ONE item right now
```

Then go look at your Telegram channel. If the post is there, the whole system
works and you are unblocked.

---

## Why some platforms stay manual

LinkedIn's publishing API is partner-only. Instagram needs a public image URL.
WhatsApp Channels have no posting API at all. That is a platform restriction,
not a budget one — no amount of free tooling fixes it.

So `run_daily.py` writes those to `automation/state/manual_tasks.md`:

```powershell
py -3 automation\channels\clipboard.py content\out\<slug>\linkedin.txt
# then Ctrl+V in LinkedIn. ~15 seconds.
```

---

## Common failures and what they actually mean

**`bot is not in chat`** — the bot token is fine; the bot was never added as a
channel administrator. Step 5 above.

**`login rejected (535)`** — Gmail refused a normal password. Needs an App
Password.

**`HTTP 190`** on Facebook — the page token expired. Refresh it; they last about
50 days.

**`HTTP 401`** anywhere — the token itself is wrong or revoked. Re-copy it.

**Nothing publishes but no error** — check `"dry_run": true` in
`automation/config.json`. Dry run is ON by default so nothing posts by accident.
