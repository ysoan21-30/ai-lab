# Validation Plan — First 10 Users → First 3 Paying Users → First ₹1,000

Do not scale before proving people will pay. This plan defines how to get
there with the MVP as built.

## First 10 target users

Data scientists, ML engineers, and students on communities you already have
some presence in are the fastest path — they immediately understand "ML
readiness score" without explanation:

1. Kaggle forums / Kaggle Discord (post the tool against a public dataset).
2. r/datascience, r/MachineLearning ("I built a tool that...", Sunday
   Showerthoughts-style low-key posts, not hard sales).
3. LinkedIn — data science + analytics hashtags, short demo video/GIF.
4. Local/online data science meetup or Slack/Discord communities.
5. Direct outreach to 10 people you know personally who work with messy
   CSVs regularly (colleagues, ex-classmates, bootcamp alumni).

## How to acquire them

- A single before/after screenshot (messy CSV → clean report with issues
  found) performs better than a feature list. Lead with that.
- Offer to run their dataset for them personally in a DM/call — high-touch,
  doesn't scale, but for the first 10 users it builds trust and generates
  qualitative feedback fast.
- No ads spend until you have evidence people convert from free → paid.

## What free functionality to provide

The Free plan as built: 3 analyses/month, basic profiling + data quality
report, web report viewer, CSV export. This is enough to prove the core
value prop ("upload → understand your data") without giving away the two
things worth paying for.

## What users should pay for

- **AI-generated insights** (plain-language executive summary + cleaning
  steps) — Pro+.
- **PDF export** — for sharing with a boss/team/stakeholder who won't open a
  web dashboard — Pro+.
- **Higher monthly analysis limits and larger file sizes** — for anyone
  doing this as part of their actual job, not a one-off.
- **Team plan**: shared reports + multiple seats — for the first team that
  wants to standardize a "profile every dataset before modeling" habit.

## What metrics define product-market fit

- **Activation**: % of signups who complete at least 1 analysis within 24
  hours. Target: >50%.
- **Repeat usage**: % of activated users who run a 2nd analysis within 7
  days without being prompted. Target: >25% — this is the strongest signal
  that the report is actually useful, not just a novelty.
- **Free → paid conversion**: % of users who hit the free monthly limit and
  upgrade within 7 days. Even 1-2 out of the first 10 converting is a strong
  early signal given the tiny sample.
- **Qualitative**: at least 3 unprompted "this caught something I didn't
  know about my data" comments.

## What feedback to collect

After each user's first analysis, ask directly (DM or a 1-question popup):
"Did this report tell you something about your dataset you didn't already
know?" and "What would make you use this again next week?" Prioritize
feedback about the *report content* (is the ML readiness score trustworthy?
are the cleaning steps actually correct/useful?) over UI polish requests at
this stage.

## What features to prioritize next (only after PMF signal)

In order, contingent on user feedback actually asking for them:

1. Background job processing for larger files (if users hit the current
   size/row caps).
2. Saved report comparison (re-run after cleaning, see score improve).
3. Team/shared-workspace features (only after a Team-tier lead exists).
4. Razorpay billing (only if a meaningful share of interested users are
   India-based and Stripe is a real checkout blocker — validate this by
   asking, not by assuming).
5. Email delivery of reports / scheduled re-analysis.

Do **not** build: multi-user role permissions beyond basic Team access,
custom branding/white-labeling, or an API before at least one Team-tier
customer explicitly asks for API access (it's already scaffolded in the
Team plan feature list but not implemented — validate demand first).

## Expected infrastructure + LLM cost per user

See the main response for the full breakdown; in short: a single analysis
costs roughly $0.001–0.01 in LLM spend (gpt-4o-mini on a small aggregated
summary, or $0 on the deterministic fallback) plus negligible compute for
the pandas pipeline itself (sub-second to a few seconds for typical MVP-size
files). Infrastructure (DB + backend + frontend hosting) on a low-cost
platform runs roughly $10-25/month total at this stage, independent of user
count until you have real concurrent load.

## Break-even point

At ₹499/month for Pro, roughly 2-5 paying Pro users cover total monthly
infrastructure cost at this stage (hosting + LLM spend for a modest analysis
volume). The real target isn't break-even on hosting cost — it's proving
someone will pay ₹499 for this at all. **First ₹1,000 in revenue (2 Pro
subscribers) is the actual milestone to hit before spending more engineering
time on anything beyond what's already built.**
