# Forsyt — Project Guide (Plain English)

**What this project does, how it works, and how every file fits in.**

Thapar Institute · Capstone CPG #300 · 2025–2026

---

## Table of Contents

1. [The Simple Idea](#1-the-simple-idea)
2. [Why This Project Exists](#2-why-this-project-exists)
3. [What's Done vs What's Coming](#3-whats-done-vs-whats-coming)
4. [How the Whole System Works (Step by Step)](#4-how-the-whole-system-works-step-by-step)
5. [What Is Geopolitical Risk (GPR)?](#5-what-is-geopolitical-risk-gpr)
6. [How We Score a Single News Article](#6-how-we-score-a-single-news-article)
7. [How We Build the Daily Risk Number](#7-how-we-build-the-daily-risk-number)
8. [Trade Corridors — Risk on Specific Routes](#8-trade-corridors--risk-on-specific-routes)
9. [Where the News Comes From](#9-where-the-news-comes-from)
10. [Every File Explained](#10-every-file-explained)
11. [Tools We Use (And Why)](#11-tools-we-use-and-why)
12. [Important Choices We Made](#12-important-choices-we-made)
13. [How We Check If It's Working](#13-how-we-check-if-its-working)
14. [How to Run It](#14-how-to-run-it)
15. [Interview Questions (Simple Answers)](#15-interview-questions-simple-answers)
16. [Team and Papers We Follow](#16-team-and-papers-we-follow)

---

## 1. The Simple Idea

Imagine you open the news every morning and ask:

> **"How much of today's news is about wars, border fights, sanctions, or terrorism?"**

Forsyt answers that question with a **number**.

- On a normal day, the number might be around **100** (that's our baseline).
- On a bad day — say, after a major border clash or a Gulf oil crisis — it might jump to **150 or 200**.

We build this number from **Indian news websites**, not just Western papers. That matters because Indian markets react to things like Galwan, Pulwama, or Red Sea shipping problems — events that global indices often miss.

### A concrete example

**Day 1 — quiet day**

- 400 articles collected from Indian news feeds
- 40 of them mention wars, sanctions, border issues, etc.
- Each risky article gets a score (explained in Section 6)
- We add up those scores, divide by 400, and scale to get something like **GPR = 95**

**Day 2 — crisis day**

- 450 articles collected
- 80 are about a military conflict somewhere
- Same math, but more risky articles with higher scores
- Result might be **GPR = 160**

That's the whole project in one sentence: **read news → find risky articles → turn that into a daily number**.

---

## 2. Why This Project Exists

### The problem

If you're an investor or analyst in India, you need to know when geopolitical trouble is building. Existing options have gaps:

| What's wrong today | Example | What Forsyt does instead |
|---|---|---|
| Western news focus | A tool tracking NYT might miss a Ladakh border report in The Hindu | We read The Hindu, TOI, StratNews, etc. |
| Old data | Caldara's famous GPR index comes out monthly, with delay | We update daily |
| No India-specific routes | Global risk doesn't tell you if Hormuz or Malacca is the problem | We track 12 routes India actually uses (oil lanes, land borders) |

### Who cares?

India had **170 million+ stock trading accounts** by 2024. More people than ever are exposed to market moves caused by wars, oil shocks, and border news. A India-focused daily risk number fills a real gap.

---

## 3. What's Done vs What's Coming

The big README describes the full dream (dashboard, stock prediction, portfolio tool). Here's what's **actually in the code today**:

| Part | Status | What it does |
|---|---|---|
| News scraping from 9 Indian sites | ✅ Done | Tier 1 (4 defence feeds) + Tier 2 (5 world RSS), dedup @ 85% |
| Database storage | ✅ Done | Supabase PostgreSQL |
| NLP tagging (themes, tone, places) | ✅ Done | GDELT-compatible fields for GPR scoring |
| GPR index (India news + GDELT validation) | ✅ Done | Split-era normalization from Aug 9, 2026 |
| Corridor risk (12 routes) | ✅ Done | Threat × exposure; sorted by 7MA |
| Automated cloud pipeline | ✅ Done | scrape → NLP → hourly refresh → daily close |
| Unified REST API + page bundles | ✅ Done | `/api/pages/*`, dual-signal, quality report |
| React dashboard (6 screens) | ✅ Done | Home, macro, corridors, news, portfolio, quality |
| Dual-signal (geo + market vol) | ✅ Done | Side-by-side; market-only vol model |
| GDELT warmup (local) | ✅ Done | Jan–Aug 2026 GKG baselines; not in Postgres |
| Portfolio optimizer / SHAP advisor | 🔜 Planned | Exposure view exists; no allocation engine |

**For interviews:** The shipped product is news → NLP → daily GPR + corridors → dual-signal dashboard. ML vol backtests live in `nifty-50/` as honest QA (GPR does not beat market-only OOS).

---

## 4. How the Whole System Works (Step by Step)

Think of it like a factory assembly line:

```
Step 1: COLLECT NEWS
   ↓
   Read RSS feeds from 9 Indian news sites
   Save to PostgreSQL database

Step 2: TAG EACH ARTICLE
   ↓
   For each article, figure out:
   - What kind of event? (war, sanction, terrorism...)
   - How negative is the language?
   - Which countries/places are mentioned?

Step 3: SCORE AND SUM
   ↓
   Give each article a risk score (0 to 1)
   Add up risky articles for the day
   Divide by total articles → daily GPR number

Step 4: SYNC TO API
   ↓
   Postgres gpr_daily + corridor_daily (from Aug 9, 2026)
   Page bundles serve React dashboard

Step 5: CHECK OUR WORK
   ↓
   Compare our numbers to the famous Caldara index
   Quality dashboard at /quality
```

### Real walkthrough with a fake article

**Input article (from RSS):**

```
Title: "India, China hold talks amid LAC tensions"
Body:  "Officials met after reports of troop movement near Ladakh.
        Both sides discussed border protocols..."
Source: The Hindu (Tier 2)
```

**Step 1 — Saved to database** with title, body, source, link, timestamp.

**Step 2 — NLP tagging produces:**

| Field | Value | Meaning |
|---|---|---|
| `nlp_themes` | `BORDER_DISPUTE;DIPLOMATIC_CRISIS` | Article is about border + diplomacy |
| `nlp_tone_neg` | 8.5 | 8.5% of words are negative (conflict, tension, etc.) |
| `nlp_tone_polarity` | 12.0 | 12% of words are emotional (positive or negative) |
| `nlp_locations` | `1#India#IN#...;1#China#CH#...;4#Ladakh#IN#...` | Mentions India, China, and Ladakh |
| `nlp_gcam` | `c18.1:0.15,c18.2:0.20,...` | Conflict-related word counts |

**Step 3 — Scoring function reads those fields:**

```
theme_score = 0.40  (two TIER2 themes matched)
tone_score  = 0.06  (negative words present)
gcam_score  = 0.00  (no TIER1 "act" theme, so GCAM doesn't apply)
─────────────────────
gpr_score   = 0.46  → counts toward today's index (above 0.20 cutoff)
```

**Step 4 — This article also tags the "India-China LAC" corridor** because "Ladakh" was mentioned.

---

## 5. What Is Geopolitical Risk (GPR)?

### It's about news, not the economy directly

GPR does **not** measure how much money was lost or how much the stock market fell.

It measures: **"How much of today's news is talking about bad geopolitical stuff?"**

Bad stuff includes: wars, invasions, terrorism, sanctions, coups, nuclear threats, border fights, diplomatic breakdowns.

### Where the method comes from

Two economics papers define the approach we follow:

1. **Caldara & Iacoviello (2022)** — Originally counted keyword matches in 10 big newspapers. Created the GPR index that economists cite in research.

2. **Iacoviello & Tong (2026)** — Updated the method to use GDELT (a huge global news database with pre-tagged articles). Same idea, but scores each article individually instead of just counting keyword hits.

We follow the 2026 method. Our twist: instead of GDELT's global news, we use **Indian news** — but we format our data the same way GDELT does, so the same scoring code works.

### The daily formula (in plain English)

```
Daily GPR = (sum of risky article scores) ÷ (total articles that day) × scaling factor
```

Only articles scoring above **0.20** count as "risky."

The scaling factor adjusts things so a normal year averages around **100**.

**Why divide by total articles?**

Suppose two days both have 50 risky articles:

- Day A: 500 total articles → risky articles are 10% of news
- Day B: 5,000 total articles → risky articles are only 1% of news

Day A is genuinely riskier in terms of news attention, even though both had 50 risky articles. Dividing by total articles captures that.

---

## 6. How We Score a Single News Article

Every article gets three ingredients. Add them up (with caps) to get the final score.

```
Article score = theme part + tone part + conflict-emotion part
                (max 0.50)   (max 0.30)  (max 0.20)
                ─────────────────────────────────────
                Total capped at 1.0
```

If the theme part is zero, the whole article scores zero — no geopolitical topic detected means it doesn't count.

### Ingredient 1: Theme part (max 0.50)

We check if the article matches any of 24 geopolitical topic codes, grouped in three levels:

| Level | What it means | Weight | Example codes |
|---|---|---|---|
| **Level 1 — Acts** | Something is actually happening | 1.0 | ARMEDCONFLICT, INVASION, TERROR_ATTACK, COUP |
| **Level 2 — Threats** | Tension building, not yet an act | 0.6 | SANCTION, TERROR, BORDER_DISPUTE, DIPLOMATIC_CRISIS |
| **Level 3 — Context** | Related background | 0.3 | ESPIONAGE, CYBERATTACK, WAR_CRIME |

**How we detect themes:** We compare the article text against 24 short description phrases using a language model. If the article is similar enough to "sanctions economic penalties trade restrictions embargo," we tag it as SANCTION.

**Example — article about sanctions on Russia:**

```
Matched themes: SANCTION (Level 2), TAX_FNCACT_MILITARY (Level 2)

Calculation:
  raw = 0.6 + 0.6 = 1.2
  theme_score = min(0.50, 1.2 / 3.0) = 0.40
```

**Example — article about an actual airstrike:**

```
Matched themes: ARMEDCONFLICT (Level 1)

Calculation:
  raw = 1.0
  theme_score = min(0.50, 1.0 / 3.0) = 0.33
```

### Ingredient 2: Tone part (max 0.30)

We count how many **negative words** appear in the article (words like "attack," "kill," "crisis," "war," "sanction") and express it as a **percentage of total words**.

```
Example article (20 words):
"Army troops clash near border after missile strike kills three civilians"

Negative words: clash, border, missile, strike, kills = 5 out of 20
tone_neg = 5/20 × 100 = 25%

Calculation:
  neg part = min(0.20, (25 - 5) / 25 × 0.20) = 0.16
  pol part = min(0.10, 25 / 20 × 0.10) = 0.10  (same % for polarity)
  tone_score = 0.16 + 0.10 = 0.26
```

**Why percentages, not a 0-to-1 sentiment score?**

The scoring code was built for GDELT data, where tone is already a percentage (usually 2–10% negative words). If we fed it a 0.0–1.0 sentiment score, a "very negative" article scoring 0.9 would become 0.9% — below the 5% floor — and contribute **nothing**. That was a real bug we fixed.

### Ingredient 3: Conflict-emotion part (max 0.20)

This only applies if the article has a **Level 1 (Act)** theme — an actual conflict event.

We count words from four conflict word lists (things like "bomb," "massacre," "escalation," "outrage") and combine them with weights:

```
gcam_score = 0.40×(violent words) + 0.30×(threat words) + 0.20×(military words) + 0.10×(anger words)
             capped at 0.20
```

**Example — airstrike article with Level 1 theme:**

```
Violent words: airstrike, kill = 2 hits
Threat words: missile = 1 hit
Total words: 20

gcam_score ≈ 0.15 (contributes to final score)
```

An article about sanctions (Level 2 only) gets **gcam_score = 0** even if the language is harsh.

### Putting it together — three examples

**Example A: Bollywood gossip (filtered out before scoring)**

Never enters the pipeline — Tier 2 keyword filter rejects it.

**Example B: "India signs trade deal with Japan"**

```
Themes: none matched
theme_score = 0 → entire article score = 0 → excluded
```

**Example C: "Sanctions imposed after border clash kills soldiers"**

```
Themes: SANCTION + BORDER_DISPUTE (both Level 2)
theme_score = min(0.50, (0.6+0.6)/3) = 0.40

Negative words: 6 out of 30 → tone_neg = 20%
tone_score ≈ 0.10

No Level 1 theme → gcam_score = 0

Final: 0.40 + 0.10 + 0 = 0.50 → COUNTS (above 0.20 cutoff)
```

**Example D: "Airstrike on military base, 20 killed"**

```
Themes: ARMEDCONFLICT (Level 1) + TERROR_ATTACK (Level 1)
theme_score = min(0.50, (1.0+1.0)/3) = 0.50

Negative words: high → tone_score ≈ 0.08

Level 1 present → gcam_score ≈ 0.18

Final: 0.50 + 0.08 + 0.18 = 0.76 → STRONG positive
```

### The 0.20 cutoff

Articles below 0.20 are ignored in the daily sum. This cleanly separates:

| Article type | Typical score | Counts? |
|---|---|---|
| Level 1 (actual conflict) | 0.33 + tone + gcam ≈ 0.55+ | Yes |
| Level 2 (sanctions, threats) | 0.20 + tone ≈ 0.24+ | Usually yes |
| Level 3 (espionage, cyber) | 0.10 + tone ≈ 0.14 | No |
| No theme match | 0 | No |

---

## 7. How We Build the Daily Risk Number

### Step 1: Add up risky articles

For one day, say we have 400 articles and 48 score above 0.20:

```
Article 1: score 0.55
Article 2: score 0.46
Article 3: score 0.72
... (45 more)
─────────────────────
gpr_sum = 28.4
```

### Step 2: Divide by total articles

```
raw_ratio = 28.4 / 400 = 0.071
```

Meaning: on average, each article contributes 0.071 "risk units."

### Step 3: Scale to make normal days ≈ 100

We compare today's ratio to the average ratio across the whole year, then apply a curve that makes big spikes stand out more:

```
Normal day  → GPR ≈ 95–105
Bad day     → GPR ≈ 130–160
Crisis day  → GPR ≈ 180–250
```

We also compute 7-day and 30-day moving averages to smooth out daily noise.

### What the output files look like

| File | What it contains |
|---|---|
| `gpr_daily_index.csv` | One row per day: article counts, sum, GPR number, 7-day avg, 30-day avg |
| `gpr_monthly_index.csv` | Average GPR per month |
| `gpr_country_level.csv` | GPR broken down by country (India, China, Pakistan, etc.) |
| `gpr_corridor_daily.csv` | GPR broken down by trade route |
| `gpr_event_type.csv` | Split by event type (terrorism, sanctions, military, etc.) |

---

## 8. Trade Corridors — Risk on Specific Routes

Global GPR tells you "the world looks risky today." Corridors tell you **which route** is the problem.

### Why this matters for India

India imports most of its oil through a few narrow passages. If news reports trouble at one of them, Indian energy prices and shipping costs can move — even if the overall global GPR looks fine.

### The 12 corridors we track

| Corridor | Why India cares |
|---|---|
| **Strait of Hormuz** | ~34% of India's crude oil imports pass through here |
| **Red Sea / Suez** | Major shipping lane to Europe; Houthi attacks disrupted it in 2024 |
| **Strait of Malacca** | ~55% of India's goods trade with East Asia |
| **Taiwan Strait / South China Sea** | Same trade route concern |
| **India-China LAC (Ladakh)** | Direct border; Galwan clash was here |
| **Attari-Wagah (Pakistan)** | Main land border crossing |
| **Petrapole (Bangladesh)** | Busiest land port with Bangladesh |
| **Raxaul (Nepal)** | Main trade crossing with Nepal |
| **Cape of Good Hope** | Alternative route when Suez is blocked |
| **Danish Straits** | Baltic oil/gas route |
| **IMEC** | India-Middle East-Europe trade corridor (announced 2023) |
| **Chabahar / INSTC** | India's port access to Central Asia, bypassing Pakistan |

### How corridor scoring works

Same article scores as before. The difference is **which corridor the article is linked to**.

**Example:**

```
Article: "Houthi attack on ship in Red Sea disrupts Indian crude imports"
Score: 0.62
Locations tagged: Red Sea, Bab el-Mandeb

→ Adds 0.62 to the Red Sea corridor's daily sum
→ Red Sea corridor has energy_exposure = 27.1%, goods_exposure = 35%
→ If Red Sea threat index = 120 today:
     EnergyRisk = 120 × 0.271 = 32.5
     GoodsRisk  = 120 × 0.35  = 42.0
     CorridorRisk = max(32.5, 42.0) = 42.0
```

### How we know which corridor an article belongs to

We look at the places mentioned in the article:

1. **Country name** — "Iran" mentioned → might match Hormuz corridor (Iran is in its country list)
2. **Specific place name** — "Ladakh" mentioned → matches India-China LAC corridor
3. **Map coordinates** — if a location's lat/lon falls inside a maritime box (e.g., the Strait of Malacca area)

For land borders, we require a specific place (like "Ladakh"), not just "India" — otherwise every article mentioning India would count toward the LAC corridor.

---

## 9. Where the News Comes From

### Two groups of sources

**Group 1 — Defence/geopolitics-only sites (4 sources)**

These sites only publish military, defence, and foreign policy news. We take **everything** they publish — no filtering needed.

| Site | Code |
|---|---|
| StratNews Global | SNG |
| Bharat Shakti | BS |
| Gateway House | GH |
| ThePrint Defence | TPD |

Checked every **~7 minutes**.

**Group 2 — Mainstream news, world section only (5 sources)**

These are big general news sites. We only read their **World/International** RSS feeds, and even then we require at least one keyword match.

| Site | Code | Feed used |
|---|---|---|
| India Today | IT | International section |
| The Hindu | TH | International section |
| Times of India | TOI | Top stories (keyword filter does the work) |
| NDTV | NDTV | World news |
| Indian Express | TIE | World section |

Checked every **~12 minutes**.

### Keyword filter (Group 2 only)

An article must contain at least one of ~40 terms like:

```
border, LAC, LoC, China, Pakistan, missile, sanctions, terrorism,
defence ministry, navy, Quad, nuclear, BrahMos, diplomatic, ...
```

**Example — kept:**

> "India and Pakistan exchange fire along LoC, army on alert"
> → matches "LoC", "Pakistan", "army" ✓

**Example — rejected:**

> "Bollywood star announces new film release date"
> → no keyword match ✗

In testing, about **29%** of Group 2 articles pass the filter. The rest (sports, entertainment, local politics) are skipped.

### Duplicate handling

The same story often appears on 5+ sites within an hour. Example:

```
10:00 AM — The Hindu:  "Army reports exchange of fire along LoC"
10:15 AM — NDTV:        "Exchange of fire reported along Line of Control"
10:30 AM — TOI:         "LoC firing: Army on high alert"
```

We compare titles using text similarity. If two titles are **≥ 85% similar** within a **2-hour window**, the later ones are marked as duplicates of the first.

- The **first one** is the "canonical" article (used in the index)
- The **later ones** are kept in the database with `duplicate_of = <first article's id>`
- This lets us later count "how many outlets covered this story" without double-counting in the index

---

## 10. Every File Explained

### Folder: `news_dataset/` — collecting and tagging news

#### `ingestion/feed_utils.py`
Basic web tools. Fetches RSS feeds from URLs. Retries if a site is slow. Parses dates that come in different formats from different news sites.

#### `ingestion/geo_pipeline.py`
The main logic for collecting news.

- Lists all 9 RSS feed URLs
- For Group 2: checks if title/description contains a geopolitics keyword
- Removes HTML tags from descriptions
- Finds duplicate titles using text similarity

#### `ingestion/geo_scheduler.py`
The timer that decides when to fetch.

- Checks: "Has it been 7 minutes since we last checked Group 1?"
- If yes → fetch Group 1 feeds
- Same for Group 2 at 12 minutes
- GitHub Actions calls this with `--once` every 25 minutes

#### `db.py`
All database operations.

- Creates the `articles` table (and related tables)
- Saves new articles
- Finds articles that still need NLP tagging
- Writes NLP results back to the article row
- Tracks which RSS links were seen (even rejected ones) for accurate daily article counts

#### `nlp/themes.py`
Figures out **what kind of geopolitical event** an article is about.

Uses a pre-trained language model (`distiluse-base-multilingual-cased-v2`) to compare the article against 24 topic descriptions. Returns matching codes like `SANCTION`, `ARMEDCONFLICT`, `BORDER_DISPUTE`.

```python
# Simplified logic:
article_text = title + title + body  # title counted twice (more important)
similarity = compare(article_text, "sanctions economic penalties trade restrictions")
if similarity >= 0.34:
    tag as SANCTION
```

#### `nlp/tone.py`
Measures **how negative** the language is.

Counts negative words (war, kill, crisis, attack...) and positive words (peace, agreement, cooperation...) as a percentage of total words.

Also builds the GCAM conflict-emotion string by counting words from four conflict word lists.

#### `nlp/locations.py`
Finds **which countries and places** are mentioned.

Two types of output:

```
Country:  1#India#IN#IN#20.0#77.0#0
Place:    4#Ladakh#IN#IN30#34.15#77.58#0
```

Uses a dictionary of ~100 country names/demonyms. For corridor places (Hormuz, Ladakh, Suez...), imports a shared list from `gpr_index/scripts/corridors.py`.

#### `nlp/run_extraction.py`
Runs tagging on a batch of articles.

```bash
python -m news_dataset.nlp.run_extraction --limit 100
python -m news_dataset.nlp.run_extraction --date 2026-03-24
```

Reads untagged articles from the database, runs all four taggers, saves results back. Skips articles already tagged with the current model version.

#### `nlp/calibrate.py`
Quality check. Runs the taggers on 500 sample articles, feeds the output to the scoring function, and prints whether the score distributions match what GDELT produces.

```bash
python -m news_dataset.nlp.calibrate --limit 500
```

If theme scores are too high or too low, we know our tagging thresholds need adjustment.

#### `export/to_gpr_parquet.py`
Converts database rows into a file format the GPR scoring code can read (Parquet — a column-based file format, like a very fast CSV).

Also adds "filler" rows for articles that were seen but rejected by the keyword filter. This is important: the daily GPR formula divides by **all articles seen that day**, not just the ones we kept.

#### `api/server.py`
A simple web server (Flask) with four endpoints:

| URL | Returns |
|---|---|
| `GET /news` | All unique articles as JSON |
| `GET /news/1` | Only Group 1 articles |
| `GET /health` | "Is the database working? How many articles?" |
| `GET /stats` | Recent scraping stats (how many fetched, how many kept) |

---

### Folder: `gpr_index/` — building the risk index

#### `main.py`
Command-line entry point. You run steps like:

```bash
python main.py download    # get GDELT data files
python main.py preprocess  # clean and organize them
python main.py gpr         # score articles and build index
python main.py validate    # compare to Caldara benchmark
python main.py corridor    # build corridor indices
```

#### `scripts/gkg_gpr_pipeline.py`
The core scoring engine. Contains `score_articles()` — the function that takes a table of articles with their tagged fields and returns scores.

**This function is tested and validated. We do not change it.** Our NLP layer must produce inputs in the format this function expects.

#### `scripts/taxonomy.py`
The list of 24 theme codes in three levels. Shared between the scorer and the NLP tagger so they always agree on what codes exist.

#### `scripts/preprocess_gkg.py`
Downloads and cleans GDELT data. GDELT publishes news in 96 small files per day (one every 15 minutes). This script merges them into one file per day.

#### `scripts/corridors.py`
The master list of 12 corridors: which countries/places belong to each, what India's trade exposure is, and the function that matches an article's locations to corridors.

Also exports `CORRIDOR_PLACES` — the list of specific place names (Hormuz, Ladakh, Suez...) used by the NLP location tagger.

#### `scripts/corridor_index.py`
Builds daily corridor risk numbers from scored articles.

#### `scripts/validate_gpr.py`
Runs 10 statistical checks comparing our index to the published Caldara GPR data. Checks things like: Does our average equal 100? Is the distribution shape similar? Does it correlate with Caldara month-by-month?

#### `scripts/fill_gpr_gaps.py`
GDELT sometimes has missing days (no data uploaded). This fills those gaps using Caldara's published daily numbers so we have a complete calendar.

#### `scripts/diagnose_gpr_scoring.py`
Prints detailed stats about how articles are being scored — useful for debugging if scores look wrong.

---

### Other files

| File | Purpose |
|---|---|
| `.github/workflows/scrape.yml` | GitHub Actions config: run the scraper every 25 minutes |
| `gpr_index/docs/gpr-theory.md` | Full math writeup for the GPR index |
| `gpr_index/docs/corridor-theory.md` | Full math writeup for corridors |
| `news_dataset/docs/theory.md` | Why we chose these news sources |
| `news_dataset/docs/codebase.md` | Short function-level docs for news_dataset |

---

## 11. Tools We Use (And Why)

| Tool | What it is | Why we use it |
|---|---|---|
| **Python 3.10+** | Programming language | Good libraries for data, ML, and web scraping |
| **PostgreSQL** | Database | Stores articles reliably; handles concurrent writes from the scraper |
| **feedparser** | Python library | Reads RSS/Atom news feeds |
| **sentence-transformers** | Pre-trained language model | Compares article text to topic descriptions for theme tagging |
| **pandas + numpy** | Data processing libraries | Score and aggregate thousands of articles quickly |
| **Parquet (pyarrow)** | File format | Fast column-based storage; same format GDELT uses |
| **Flask** | Small web framework | Serves our news API |
| **GitHub Actions** | Cloud automation | Runs the scraper on a schedule without needing our own server |
| **uv** | Package installer | Faster alternative to pip for installing Python packages |
| **GDELT GKG** | External news database | Global news with pre-tagged fields; used to validate our method |
| **Caldara GPR data** | Published academic index | Benchmark to check our numbers against |

**Two separate requirements files:**

- `news_dataset/requirements.txt` — lightweight (installed every 25 min by GitHub Actions)
- `news_dataset/requirements-nlp.txt` — heavy (includes PyTorch ~2 GB; installed only when running NLP)

We keep them separate so the scraper doesn't download 2 GB of ML libraries every 25 minutes.

---

## 12. Important Choices We Made

### "Don't change the scoring function"

We spent significant effort validating `score_articles()` against the Caldara benchmark (10 statistical checks). Instead of rewriting it for Indian news, we made our NLP tagging produce the **same type of input** that GDELT provides. Change the data source, keep the scoring engine.

### "Use word percentages, not sentiment scores"

The scoring code expects tone as "8% of words are negative." A sentiment model that returns 0.85 (very negative) would be read as 0.85% — below the 5% floor — and contribute zero. We count negative words directly.

### "Use FIPS country codes, not ISO"

GDELT uses FIPS codes where `CH` = China (not Switzerland), `BG` = Bangladesh. Our location tagger outputs the same codes so the scorer and corridor matcher work without conversion.

### "Track rejected articles too"

When a TOI sports article is rejected by the keyword filter, we still record that we saw it (`geo_seen_links` table). The GPR formula divides by **all articles seen that day**, not just geopolitical ones. Without this, our index would look artificially high.

### "Keep duplicates, don't delete them"

Duplicate articles stay in the database with a pointer to the original. This lets us answer "how many news outlets covered this story?" later, while the index only counts each story once.

### "RSS descriptions are short (~40 words)"

We currently store only the RSS summary, not the full article text. This makes word-count-based tone scoring noisier. Full article extraction is planned but not yet implemented.

---

## 13. How We Check If It's Working

### Check 1: Compare to the famous Caldara index

Caldara & Iacoviello published a GPR index used in economics research. We compare our monthly numbers to theirs.

- Target: correlation ≥ 0.60
- If our index moves up when theirs moves up (over months), our method is sound

### Check 2: Are our article scores the right shape?

When we run our NLP tagging on 500 articles and score them, the results should look like GDELT's:

| What we measure | GDELT typical value | Our acceptable range |
|---|---|---|
| Median theme score | 0.33 | 0.30 – 0.40 |
| Average theme score | 0.40 | 0.35 – 0.45 |
| Average tone score | 0.05 | 0.03 – 0.08 |
| Average conflict-emotion score | 0.18 | 0.14 – 0.20 |
| Articles scoring between 0 and 0.20 | 0% | less than 2% |

That last row is the sharpest test. In GDELT, articles either score zero (no theme) or above 0.20 (has a theme). Nothing lands in between. If our scores cluster in the 0.10–0.19 range, our tagging thresholds are miscalibrated.

### Check 3: Do corridors get tagged?

Run corridor matching on 500 articles. Every corridor should match at least some articles (except remote ones like Danish Straits that rarely appear in Indian news). A corridor with **zero matches** means our location tagging is broken for that route — and the corridor would silently show "all clear" when it's actually untagged.

### Check 4: Historical events (planned)

Pick 17 major Indian events (Galwan clash, Pulwama, 26/11, Farmers' Protest...) and verify our index spiked on those dates. Target: detect at least 14 out of 17.

---

## 14. How to Run It

### Setup (one time)

```bash
# Activate Python environment
source "$HOME/.venv/forsyt/bin/activate"

# Install packages
uv pip install -r news_dataset/requirements.txt
uv pip install -r news_dataset/requirements-nlp.txt
uv pip install -r gpr_index/requirements.txt

# Set database connection (Supabase — copy from Project Settings → Database)
export DATABASE_URL="postgresql://postgres.xxxx:password@....pooler.supabase.com:6543/postgres"
```

### Collect news

```bash
cd news_dataset
python -m ingestion.geo_scheduler --once
```

This checks which feed groups are due, fetches new articles, removes duplicates, and saves to the database.

### Tag articles with NLP

```bash
python -m news_dataset.nlp.run_extraction --limit 100
```

Processes up to 100 untagged articles. Add `--date 2026-03-24` for a specific day.

### Check tagging quality

```bash
python -m news_dataset.nlp.calibrate --limit 500
```

Prints a report comparing our score distributions to GDELT's.

### Build the GPR index (using GDELT data)

```bash
cd gpr_index
python main.py gpr --start-date 2025-01-01 --end-date 2025-12-31
python main.py validate --start-date 2025-01-01 --end-date 2025-12-31
```

### Start the API

```bash
cd news_dataset
python api/server.py
# Visit http://localhost:5000/news
```

---

## 15. Interview Questions (Simple Answers)

**Q: What does Forsyt do?**

> It reads Indian news every day, finds articles about wars, sanctions, border conflicts, and terrorism, and turns that into a daily risk number. Normal days ≈ 100. Crisis days go higher. We also break it down by trade routes India depends on (Hormuz, Malacca, Ladakh, etc.).

**Q: Why not just use the existing Caldara GPR index?**

> Caldara's index uses Western newspapers and comes out monthly with a delay. Indian markets react to regional events that Western papers underreport. We build a daily index from Indian sources, using the same scoring method, and validate it against Caldara to prove it's reliable.

**Q: Why not just use GDELT directly?**

> GDELT covers global news but underrepresents Indian regional events — state politics, local defence reporting, Hindi-language sources. Our Indian feed catches things GDELT misses. We still use GDELT to validate our scoring method works correctly.

**Q: How do you detect if an article is about geopolitical risk?**

> Three checks: (1) Does it match a topic like "sanction" or "armed conflict"? We compare the text against 24 topic descriptions using a language model. (2) How negative is the language? We count negative words as a percentage. (3) Where does it happen? We look for country and place names. Combine those three into a score from 0 to 1.

**Q: What was the hardest part?**

> Getting the numbers to match. The scoring function was tuned on GDELT's data over years. Our NLP tagging must produce the same kind of numbers — same average theme score, same tone range — or articles end up on the wrong side of the 0.20 cutoff and the index breaks silently. We built a calibration tool to catch this.

**Q: How do you handle the same story appearing on 5 websites?**

> We compare titles using text similarity. If two titles are 85%+ similar within 2 hours, we keep the first and mark the rest as duplicates. The index counts the story once. The duplicates stay in the database so we can see how many outlets covered it.

**Q: What is a corridor risk index?**

> Instead of one global number, we compute a separate risk score for each trade route India uses — like the Strait of Hormuz (where a third of our oil passes) or the Ladakh border. Same article scoring, but grouped by location. Then we multiply by India's trade exposure through that route.

**Q: What's the project status?**

> The core pipeline works: scraping, tagging, scoring, index building, corridor tracking, and validation against Caldara. Next steps are a web dashboard, stock market prediction model, and portfolio risk tool.

**Q: What would you improve next?**

> Fetch full article text instead of short RSS summaries (currently ~40 words, which makes tone scoring noisy). Add Hindi news sources. Build the dashboard so analysts can see the index and corridor map in a browser.

---

## 16. Team and Papers We Follow

### Team

| Name | Role |
|---|---|
| Devasya Kanwar | AI/ML — NLP tagging and models |
| Aaditi Verma | Domain expert — geopolitical analysis |
| Aadi Jain | Backend — scraping pipeline and API |
| Vansh Gupta | Frontend — dashboard and visualization |
| Arianna Vohra | Project management and finance analysis |

Mentors: Dr. Jasmeet Singh, Dr. Kapil Tomar (Thapar Institute)

### Papers

1. **Caldara & Iacoviello (2022)** — "Measuring Geopolitical Risk." The original GPR index. *American Economic Review.*
2. **Iacoviello & Tong (2026)** — Updated method using GDELT data and per-article scoring. *Federal Reserve Working Paper.*
3. **Lundberg & Lee (2017)** — SHAP explainability (planned for ML module). *NeurIPS.*

### External data

- **GDELT:** https://www.gdeltproject.org/ — global news database we validate against
- **Caldara GPR data:** https://www.matteoiacoviello.com/gpr.htm — benchmark numbers

---

## Quick Reference: Project Structure

```
Forsyt/
├── docs/
│   └── PROJECT_GUIDE.md          ← you are here
│
├── news_dataset/                  ← collect and tag Indian news
│   ├── ingestion/                 ← RSS fetching, keyword filter, dedup
│   ├── nlp/                       ← theme, tone, location tagging
│   ├── export/                    ← convert to Parquet for scoring
│   ├── api/                       ← simple REST API
│   └── db.py                      ← database schema and queries
│
├── gpr_index/                     ← build and validate the risk index
│   ├── main.py                    ← run pipeline steps from command line
│   ├── scripts/
│   │   ├── gkg_gpr_pipeline.py    ← score_articles() — the core scorer
│   │   ├── corridors.py           ← 12 trade routes + place names
│   │   ├── validate_gpr.py        ← compare to Caldara benchmark
│   │   └── ...                    ← download, preprocess, plot, etc.
│   ├── docs/                      ← detailed math writeups
│   └── outputs/                   ← generated CSV files and plots
│
└── .github/workflows/scrape.yml   ← automated scraping every 25 min
```

---

*Forsyt — Thapar Institute of Engineering & Technology, Patiala · CPG #300 · 2025–2026*
