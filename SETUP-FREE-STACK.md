# Free Stack Setup — every account, every key, step by step

Work through this once. ~2 hours total. Everything below is genuinely free.

Legend: 🔑 = you copy a key into `automation/config.json`

---

## 0. Accounts to create (all free)

| Purpose | Service | Free limit | Notes |
|---|---|---|---|
| Blog | Blogger.com | Unlimited posts | Google account |
| Email list | Brevo | 300 emails/day, unlimited contacts | Best free tier |
| Scheduling | GitHub Actions | 2,000 min/mo private, unlimited public | Public repo = free |
| Images | Canva free | Unlimited basic designs | Batch carousels |
| Booking | Cal.com | Unlimited 1:1 | For services |
| Selling | Gumroad | 10% per sale | No monthly fee |
| Payments | Razorpay | ~2% + GST | UPI for India |
| Analytics | Google Search Console | Free | The only SEO tool you need |
| Keywords | Google Suggest (our script) | Free | `automation/seo.py` |
| SEO audit | Google PageSpeed / Rich Results | Free | |
| Link shortener | Bitly free / `wa.me` direct | — | Or just use full links |

---

## 1. Blogger 🔑 (blog automation)

### Create the blog
1. blogger.com → Create blog → name `Chipzo` → address `chipzo.blogspot.com`
2. Settings → Meta tags → enable search description → paste your description.
3. Add pages: About, Contact, Privacy, Work with me.

### Enable post-by-email (this is your free publishing API)
1. Settings → **Email**
2. *Post using email* → **Save** (reveals the secret address, e.g.
   `chipzo.a1b2c3d4e5@blogger.com`)
3. *Email posts to* → choose **Publish immediately**
4. *Comment notification* → off

🔑 In `config.json`:
```json
"blogger": {
  "email_address": "chipzo.SECRET@blogger.com",
  "smtp_host": "smtp-relay.brevo.com",
  "smtp_port": 587,
  "smtp_user": "you@email.com",
  "smtp_password": "YOUR_SMTP_KEY",
  "from_address": "you@email.com"
}
```

> **Why this instead of the Blogger API?** The API needs an OAuth consent screen,
> a client secret, and a refresh token that expires when you change your password.
> Email posting needs one secret address and any SMTP account. Fewer moving parts
> = fewer 3am failures. (An API backend is included anyway if you prefer it.)

**Gmail SMTP alternative:** Google Account → Security → 2-Step Verification →
App passwords → create → use `smtp.gmail.com:587`, user = your Gmail,
password = the 16-char app password. Free but capped ~500 recipients/day.

---

## 2. Telegram 🔑 (the easiest win)

1. Open Telegram → search `@BotFather` → `/newbot` → name it `ChipzoBot` →
   username `chipzo_publisher_bot`.
2. 🔑 Copy the token into `config.json → telegram.bot_token`.
3. Create your channel `@chipzo` (public).
4. Channel → Administrators → Add Admin → search your bot → give it **Post Messages**.
5. 🔑 `config.json → telegram.chat_id` = `@chipzo` (the @username works if public;
   otherwise use the numeric `-100...` id).

**Test immediately:**
```powershell
python automation\channels\telegram.py --test
```

Optional: `/setcommands` in BotFather, `/setdescription` with keywords.

---

## 3. WhatsApp — two paths

### Path A (₹0, recommended now): WhatsApp Channel
1. WhatsApp → Updates → **+** → New channel → name `Chipzo · VLSI`.
2. Copy the channel link into every bio.
3. Post manually from `content/out/*/whatsapp.txt` (20 seconds, 3x/week).

No key needed. The script generates the text + a shareable `wa.me` link.

### Path B (later, real automation): WhatsApp Cloud API
1. developers.facebook.com → Create App → **Business** type → add **WhatsApp** product.
2. Get a free test number + temporary token (24h) to experiment.
3. For production: add a phone number, verify business, generate a **System User**
   permanent token.
4. 🔑 `config.json → whatsapp`: `phone_number_id`, `token`, and a template name.
   Messages to users require an **approved template** and opt-in — this is why
   Path A is better until you have a real list.

---

## 4. Facebook Page 🔑 (Graph API)

1. Create the Page: facebook.com/pages/create → `Chipzo` → category
   *Education / Science & Technology*.
2. developers.facebook.com → **Create App** → use case *Other* → type **Business**.
3. Add product **Facebook Login for Business** (not needed for page feed, but helps
   get tokens) and note your **App ID / App Secret**.
4. Graph API Explorer (developers.facebook.com/tools/explorer):
   - Permissions: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
   - Generate token → select your Page → copy the **Page access token**
5. 🔑 `config.json → facebook`: `page_id`, `page_token`.

**Make the token long-lived (60 days)**, or it dies silently:
```
GET https://graph.facebook.com/v21.0/oauth/access_token
    ?grant_type=fb_exchange_token
    &client_id=APP_ID
    &client_secret=APP_SECRET
    &fb_exchange_token=SHORT_TOKEN
```
Then exchange the *user* token for the *page* token again. Refresh every 50 days
(put a reminder in your calendar, or the GitHub Action will start failing).

---

## 5. Instagram 🔑 (optional, hardest)

1. Convert to **Instagram Business** or Creator account.
2. Link it to your Facebook Page (IG app → Settings → Account type → linked page).
3. Same Meta app → permissions `instagram_basic`, `instagram_content_publish`,
   `pages_show_list`.
4. Get your **IG User ID**: `GET /me/accounts` → page id →
   `GET /{page-id}?fields=instagram_business_account`
5. 🔑 `config.json → instagram`: `ig_user_id`, `page_token`.
6. Images must be **publicly reachable HTTPS URLs** — post an image to your blog
   and use that URL, or host in a public GitHub repo via raw.githubusercontent.com.

> Reality: IG publishing is fragile and rate-limited (25 posts/24h).
> Carousels + reels are faster to do by hand in the app. Use the API only if you
> truly want hands-off image posts.

---

## 6. LinkedIn (no API) 🔑

LinkedIn's publishing API is partner-only. Do not chase it.

Free workflow:
1. `repurpose.py` writes `linkedin.txt`.
2. Open the file, `Ctrl+A`, `Ctrl+C`, paste. 15 seconds.
3. Or use **Buffer free** (3 channels, 10 queued posts) to schedule it.

If you want a one-click copy helper:
```powershell
python automation\channels\clipboard.py content\out\<slug>\linkedin.txt
```

---

## 7. Email list — Brevo 🔑

1. brevo.com → free account (300 emails/day, unlimited contacts).
2. Senders & IPs → add your domain or verify your email address.
3. SMTP & API → **SMTP** tab → generate an SMTP key.
4. 🔑 Use the same SMTP values as Blogger. One key drives both.

**Lead magnet delivery, zero code:**
- Create a Brevo *Automation*: "When contact added → send email with PDF link".
- Or use a free Form (Brevo Forms) embedded on a Blogger page.
- Or simplest: Gumroad "free product" listing at ₹0 — it captures email and
  delivers the file automatically. Start here; it's 5 minutes.

---

## 8. GitHub Actions cron 🔑

1. Create a **public** repo (unlimited Actions minutes) or private (2,000 min/mo — plenty).
2. Push this `chipzo` folder.
3. Repo → Settings → Secrets and variables → **Actions** → New repository secret
   for each: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `BLOGGER_EMAIL`,
   `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FB_PAGE_ID`,
   `FB_PAGE_TOKEN`, `IG_USER_ID`, `BREVO_API_KEY`.
4. The workflow at `.github/workflows/daily.yml` runs `run_daily.py` on a cron.
   **Note:** GitHub cron is UTC and can be delayed 5–20 min. Fine for content.

---

## 9. Config file

```powershell
copy automation\config.example.json automation\config.json
python automation\check_env.py
```

`check_env.py` tells you exactly which keys are missing and what still works.
You do **not** need all of them. Telegram alone already gives you a daily
auto-published channel.

---

## 10. The 30-minute "minimum viable automation"

If you only do one thing today:

1. Blogger blog live
2. Telegram bot + channel + admin rights
3. `config.json` with those two blocks
4. `python automation\repurpose.py <post>` → `python automation\run_daily.py`

That publishes to a blog and a Telegram channel automatically, forever, for ₹0.
Everything else is a bonus.
