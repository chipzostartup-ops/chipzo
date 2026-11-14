# Free-AI prompts (Gemini / ChatGPT free tier / Claude free)

The Python engine produces solid deterministic output. These prompts produce
*sharper* output. Use whichever fits your time.

**Workflow that beats both:** write the source `.md` yourself (that's the part
that needs your expertise), then use `repurpose.py`. Only reach for AI when a
specific platform post needs more punch.

---

## 1. Master repurposing prompt

Paste your blog post and this:

```
You are the content lead for Chipzo, a VLSI education brand for Indian
students and 0-3 year engineers (RTL, DV, STA, PD, DFT).

Voice: a senior engineer who remembers being confused. Direct, specific, no
hype, no "delve", no "game-changer", no emoji spam.

From the article below, produce:

1. LINKEDIN POST — hook line under 10 words (no hashtags/emoji), 6-8 short
   lines, one idea per line, ends with "Save this." + 3 hashtags max.
   Must contain at least one number or named concept.

2. INSTAGRAM CAROUSEL — 7 slides. Slide 1 = hook. Slides 2-6 = one idea each,
   title under 6 words + one line of body. Slide 7 = CTA. Also write a caption.

3. INSTAGRAM REEL — 40 second script with timestamps, spoken words, and
   on-screen text for each beat.

4. TELEGRAM — under 120 words, 4 bullets, ends with a link placeholder [LINK].

5. WHATSAPP — under 60 words, must survive being forwarded to a college group.

6. X THREAD — 6 tweets, each under 270 characters, numbered.

Rules: never invent statistics. If the article does not state a number, do not
add one. Keep every technical claim exactly as written.

ARTICLE:
<paste>
```

---

## 2. Hook generator

```
Give me 15 LinkedIn hook lines for a VLSI audience on this topic: <topic>.

Mix: interview-pain, myth-breaking, number/list, contrarian, curiosity gap.
Rules: under 12 words each. No emoji. No "In today's world". No question that
can be answered with yes/no. Every hook must be literally true for a post that
delivers on it.
```

---

## 3. Blog SEO brief (before you write)

```
Act as an SEO editor. Target query: "<keyword>".
Audience: VLSI students and 0-3 yr engineers in India.

Give me:
- the search intent in one sentence (what the searcher actually wants)
- 8 H2/H3 headings that fully answer the query
- 5 follow-up questions people will ask next (for FAQ + internal links)
- 3 things most existing articles get wrong or skip
- the 40-word answer to put in the first paragraph for featured snippets

Do not write the article.
```

---

## 4. Turn a post into a project/example

```
Take this VLSI concept and give me one small, runnable example a student can
build in a free simulator (EDA Playground / Icarus Verilog). Include the exact
file name, the code with comments, and what output proves it works. Keep the
code under 40 lines.

Concept: <concept>
```

---

## 5. Weekly content batch

```
Here are my top 5 performing posts from last week: <list>.

Identify the common structural pattern (format, hook type, topic depth).
Then propose 10 new topics that follow the SAME pattern but cover different
VLSI concepts. For each: title, hook line, and the one specific fact that makes
it worth reading. Prioritise topics that a fresher would search before an
interview.
```

---

## 6. Sales page copy (for a ₹149 product)

```
Write a short product page for "VLSI Interview Bank PRO" (300 questions with
answers, ₹149, instant PDF download).

Audience: Indian engineering students in their final year, applying to VLSI
roles, afraid of technical interviews.

Structure: headline (outcome, not feature) -> 3 lines of pain -> what's inside
(bulleted, with counts) -> who it is for / not for -> price justification
(compare to course fees) -> FAQ (5) -> CTA.

No fake urgency. No fake testimonials. Under 400 words.
```

---

## 7. Comment generator (for LinkedIn growth)

```
Write 5 genuinely useful LinkedIn comments I could leave on a recruiter's post
about VLSI hiring in India.

Each comment: 2-3 sentences, adds a specific technical or market insight, no
self-promotion, no "great post", no emoji. Should make the reader want to check
my profile.
```

---

## Rules for using AI here

1. **Never let AI invent an interview question "asked at Qualcomm".** That is
   how small brands die.
2. Verify every number and formula before publishing.
3. Rewrite at least the first line yourself — it's the only part that carries
   your voice.
4. If the output sounds like a LinkedIn influencer, delete half the sentences.
