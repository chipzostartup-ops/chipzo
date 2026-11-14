# Platform Playbooks — what actually works in VLSI

Niche-specific tactics. Generic advice removed.

---

## 1. LinkedIn — your #1 growth engine

**Why:** VLSI hiring managers, recruiters, and edtech founders all live here.
One good post reaches 5k–50k people for free. No other platform gives a nobody
that reach.

**Setup**
- Use your **personal profile** as the main account. A company page gets ~5%
  of the reach. Create the Chipzo page anyway (for credibility) and repost there.
- Headline: `Chipzo · VLSI content for freshers | RTL · DV · STA` — keyword-loaded.
- Banner: the lead-magnet offer, not a logo.
- Featured section: lead magnet link + best post + product page.

**Post formats ranked by reach**
1. **Text + one image** — "5 interview questions on CDC that stumped me"
2. **PDF carousel (document post)** — highest dwell time, best for saves
3. **Poll** — cheap engagement, use max 1/week ("Which is harder to learn?")
4. **Story/lesson** — "I failed 3 VLSI interviews before I understood this"
5. Link posts — **worst reach. Put the link in the first comment instead.**

**Post structure that converts**
```
Line 1:  hook, <10 words, no hashtags, no emoji spam
Line 2:  one-line stakes ("This question eliminated 80% of candidates.")
(blank)
Body:    5–7 short lines, one idea per line, max 2 lines per paragraph
(blank)
CTA:     "Save this. Repost if a friend is interviewing."
(blank)
3 hashtags max: #VLSI #Semiconductor #VLSIFreshers
```

**Growth hack that works here:** 30 min/day commenting *substantively* on posts
by VLSI recruiters, hiring managers, and edtech accounts. A 3-line technical
comment gets you profile views from exactly the right people. This is worth more
than 5 extra posts.

**Timing (IST):** Tue–Thu 8–10am and 8–10pm. Test, then lock.

---

## 2. Telegram — your owned asset

**Why:** no algorithm, 100% delivery, instant, free bot API, and this audience
already uses it for placement groups and study material. Highest trust per follower.

**Setup**
- Channel (not group) for broadcasts; a group later for discussion.
- Bot via @BotFather → token → drop in `config.json`.
- Pinned message: lead magnet + "start here" index.
- Set a channel description with keywords ("VLSI jobs, interview questions, RTL, DV, STA").

**What to post (daily, 2 min via automation)**
- 1 concept/fact with a diagram
- 1 interview question (answer in a "spoiler" or next post)
- 1 job/hiring signal
- Weekly: the blog post of the week

**Growth (all free)**
- Cross-link from blog + every other bio.
- Answer questions in public VLSI Telegram groups, then link your channel.
- Cross-promo swaps with channels of similar size (DM 5/week — 1 in 5 says yes).
- **Never** buy subscribers. Dead subs destroy your post-reach ratio and sponsors check.

**Premium tier later:** ₹99/mo for placement alerts + resume templates. Telegram
has native paid-subscription support in some regions; otherwise just use a private
channel + manual/PayU link.

---

## 3. WhatsApp Channel — highest open rate on earth (~90%)

**Setup**
- WhatsApp **Channel** (broadcast, one-way, free, no API needed for posting).
- Name `Chipzo · VLSI`, description with keywords, same avatar.
- Link it in bio: `https://whatsapp.com/channel/<id>`

**Reality check:** Channels have **no public posting API**. You post from your
phone (30 seconds) or use the Meta Cloud API for a *Business* number to a
subscriber list (different product, needs opt-in + template approval).

**Practical system (₹0):**
1. `repurpose.py` writes `whatsapp.txt` (short, 3–4 lines, one link, no markdown).
2. `channels/whatsapp.py` generates `wa.me` share links and a clipboard-ready file.
3. You paste into the Channel. 20 seconds.

**Why it's worth it:** WhatsApp forwards are how content travels in Indian
engineering colleges. One forward to a class group = 60 warm eyeballs.

**Rules**
- Max 3–4 messages/week. More = mute.
- No attachments over 5MB.
- Every message ends with one CTA, never two.

---

## 4. Instagram — reach, not conversion

**What works in this niche**
- **Reels:** "Draw setup/hold in 20 seconds", "This Verilog line is a race condition".
  Screen recordings of a simulator or a timing waveform outperform talking heads.
- **Carousels:** 6–8 slides, slide 1 = question, last slide = CTA + save prompt.
  Carousels get saved, and saves are the metric IG rewards.
- **Text-on-dark-background** quote cards: "Setup time is not a delay." Cheap to make.

**What does NOT work:** generic motivational content, stock photos of chips,
long talking-head videos, posting 3x/day.

**Cadence:** 3/week is enough. 1 reel + 2 carousels.

**Bio:**
```
VLSI, explained without the gatekeeping
RTL · DV · STA · PD
Free Interview Bank ↓
```

**Automation:** Graph API can publish images/carousels if you have an IG Business
account linked to a FB Page and a public image URL. Reels need a video URL — do
those manually. Honestly: IG is the least automatable platform. Budget 30 min/week
in Canva free and batch-produce 3 carousels at once.

---

## 5. Facebook — the underestimated one

**Why:** Indian engineering college groups on Facebook are enormous and active.
A good answer in a 200k-member VLSI group gets more reach than your page will in a year.

**Play**
- Create the Page (credibility, Graph API auto-posting).
- Join 15–25 groups: "VLSI Jobs", "VLSI/Digital Design", "ECE Jobs India",
  college-specific placement groups, "Semiconductor India".
- **Post in groups 3–5x/week** — but as a *person helping*, not a brand posting links.
  Answer the question fully in the post, then one soft line: "I put the full list in Chipzo."
- Page = auto-published archive + ad-free credibility. Groups = growth.

**Group post format that doesn't get removed**
```
[Full useful answer — 8–15 lines, self-contained]
No link in the post body.
If someone asks for more: comment with the link.
```
Admins delete link-drops. They keep helpful answers.

---

## 6. Blogger (blog) — the compounding asset

**Why Blogger over WordPress:** free forever, no hosting, no plugin maintenance,
Google-owned (fast indexing in Search Console), and supports post-by-email which
gives you free automation.

**SEO setup checklist**
- Settings → Meta tags → enable search description.
- Custom robots.txt: allow everything, submit sitemap to Search Console.
- Enable "Post via email" with a secret address (this is your automation hook).
- Add a mobile-friendly theme (default Contempo/Notable is fine).
- Add: About page, Contact page, Privacy page, "Work with me" page. Needed for
  affiliate disclosure and AdSense later.

**Content = search intent, not essays**
Every post targets one long-tail query and answers it in the first 100 words,
then expands. VLSI long-tails are low competition — you can rank page 1 with a
600-word post that's actually correct.

**Money-on-blog**
- AdSense (needs ~3 months of content + traffic; apply at 5k pageviews).
- Affiliate links in "best course/book" posts.
- Product CTA box at the end of every post (the engine inserts it).
- Email capture box mid-post.

**Internal linking:** every new post links to 3 older posts + the product page.
This is free ranking juice and it's the #1 thing beginners skip.

---

## 7. X / Twitter — optional, low priority for VLSI

Indian VLSI is thin on X. Use it only to repost threads if you already have an
account. Don't spend growth time here. The engine still generates `x_thread.txt`
in case you want to post.

---

## Cross-platform rules

1. **Never post identical text on two platforms.** The engine rewrites; trust it.
2. **One CTA per piece of content.**
3. **Every platform bio links to the same lead magnet.**
4. **Reply to every comment for the first 90 days.** It's the cheapest growth lever.
5. **Post the same idea at most twice** (once as carousel, once as reel) — never
   three times in a week, or you look like a spam bot.
