# Forsyt — Capstone Pitch Speaker Script

**Use this document as your spoken script for the mid-semester evaluation.**

| | |
|---|---|
| **Project** | Forsyt — Live Geopolitical Risk Intelligence Platform for Indian Financial Markets |
| **Team** | Aadi Jain · Aaditi Verma · Arianna Vohra · Devasya Kanwar · Vansh Gupta |
| **Mentors** | Dr. Kapil Tomar · Dr. Jasmeet Singh |
| **Institution** | Thapar Institute of Engineering & Technology · CPG No. 300 · BE CSE, Fourth Year |
| **Deck reference** | `CAPSTONE EVAL 2.pdf` |
| **Total time** | ~7 minutes presentation + ~2 minutes live demo + Q&A |

---

## Before You Start

- Confirm the API is running (`python -m news_dataset.api.server`) and the frontend is up (`npm run dev` in `frontend/`).
- Open the dashboard at **http://127.0.0.1:5173** in a browser tab before you enter the room.
- Keep **Slide 8 screenshots** ready as backup if Wi‑Fi or the demo fails.
- Speak slowly on numbers — evaluators need time to absorb validation results.

**Suggested speaker split (adjust as your team prefers):**

| Slides | Suggested speaker | Why |
|---|---|---|
| 1–2 | Arianna (PM) | Sets context and scope |
| 3 | Aaditi (Domain) | Literature and research gap |
| 4–7 | Aadi (Backend) | Architecture, stack, data design |
| 8 | Vansh (Frontend) | Live UI demo |
| 9 | Arianna | Cost |
| 10 | Devasya (AI/ML) | News pipeline + NLP |
| 11 | Aaditi + Devasya | GPR validation |
| 12 | Aaditi | Corridor risk |
| 13 | Devasya | NIFTY + Joint Stress |
| 14–15 | Arianna + any teammate | Progress, future work, close |

---

## Slide 1 — Title · ~15 seconds

> Good morning / good afternoon. We are **Team Forsyt**, CPG number 300, from the Computer Science and Engineering department at Thapar Institute.
>
> We have built **Forsyt** — a live geopolitical risk intelligence platform for Indian financial markets.
>
> Our pipeline runs in one line: **News → GPR → Corridors → NIFTY 50 → Joint Stress**.
>
> Everything we will show you today is **implemented and working** — not a mockup or a concept slide.

**[Advance to Slide 2]**

---

## Slide 2 — Problem, Scope & Objectives · ~45 seconds

> Let me start with the problem.
>
> Geopolitical information today is **fragmented** across many news sources. At the same time, the risk indices that analysts commonly reference are **global**, **lagged**, and often **not India-specific**.
>
> Forsyt addresses this by structuring Indian news into **India-centric risk intelligence**, and presenting it alongside **market signals** and **trade-corridor exposure**.
>
> Our current scope covers six things:
>
> First, **automated ingestion** from nine Indian news sources, refreshed every twenty-five minutes.
>
> Second, **NLP tagging** — we extract geopolitical themes, tone, and locations from every retained article.
>
> Third, an **India AI-GPR Index**, validated against the Caldara–Iacoviello academic benchmark.
>
> Fourth, **Trade and Corridor Risk** across twelve strategic routes that matter to India.
>
> Fifth, a **NIFTY 50 volatility study** and a transparent **Joint Stress** composite.
>
> And sixth, a **live REST API** and **React dashboard** that deliver all of this to the user.
>
> One thing we want to be clear about upfront: Forsyt is a **decision-support tool**. It supports human judgement. It does **not** execute trades, and it does **not** present its outputs as guaranteed financial forecasts.

**[Advance to Slide 3]**

---

## Slide 3 — Literature Survey · ~30 seconds

> We reviewed existing work to find where Forsyt fits.
>
> **Caldara and Iacoviello's GPR index** is the established benchmark — but it is global in scope and published at monthly cadence.
>
> **Iacoviello and Tong's AI-GPR** brings AI into news analysis — but any such index needs explicit validation before it can be used downstream.
>
> **Commercial geopolitical monitors** offer broad coverage — but they are proprietary and less reproducible for academic work.
>
> **AI financial prediction systems** are strong on market modelling — but the value of geopolitical signals must be tested, not assumed.
>
> The **research gap** we identified is this: there is no India-centric system that combines **news intelligence**, a **validated GPR index**, **corridor-level risk**, **market analysis**, and an **explicit accuracy and transparency layer** — all in one deployed platform.
>
> That is what Forsyt is.

**[Advance to Slide 4]**

---

## Slide 4 — Use Case & Sequence Diagrams · ~30 seconds

> From a design perspective, the end user interacts with six main views:
>
> **Home** for a live snapshot, **News Intelligence** for the tagged event feed, **India AI-GPR** for the index, **Macro** for joint stress, **Trade and Corridor Risk** for route-level exposure, and **Platform Quality** for validation and feed health.
>
> Behind the scenes, a scheduled pipeline runs continuously: scrape, NLP batch, benchmark validation, and feed-health checks.
>
> When the dashboard loads, the React frontend calls our Flask API, which reads from PostgreSQL and returns structured JSON — one bundle per screen. The user never talks to the database directly.

**[Advance to Slide 5]**

---

## Slide 5 — System Architecture · ~45 seconds

> Our architecture is a **layered pipeline** from raw news to user-facing intelligence.
>
> At the top, **data sources**: nine Indian RSS feeds, market data from yfinance, and GDELT GKG used **only for benchmark validation and historical calibration** — not for live ingestion.
>
> Next, **ingestion and preprocessing**: tiered polling, keyword filtering, deduplication, and cleaning.
>
> Then **NLP**: theme classification using sentence-transformers, plus tone and location extraction.
>
> That feeds the **India AI-GPR layer**: article scoring, daily aggregation, and split-era normalization.
>
> **Analytics** adds corridor risk, NIFTY volatility, and Joint Stress.
>
> **Quality and explainability** covers validation metrics, feed health, and SHAP attribution at the research level.
>
> Finally, **delivery**: PostgreSQL, a Flask REST API with twelve JSON endpoints, and a React dashboard.
>
> Three principles we stand by:
>
> **Modular** — four packages: `news_dataset`, `gpr_index`, `nifty-50`, and `frontend`.
>
> **Honest outputs** — market volatility uses market data only; GPR stays a separate geopolitical signal until Joint Stress combines them transparently.
>
> **Reusable scoring** — our NLP layer produces a GDELT-compatible data contract that the GPR engine consumes.

**[Advance to Slide 6]**

---

## Slide 6 — Tools & Platforms · ~20 seconds

> On the technology side, everything is open source.
>
> **Data acquisition** uses feedparser for RSS, yfinance for market data, and GDELT for benchmark validation.
>
> The **backend** is Python 3.10 and above, Flask, and PostgreSQL hosted on Supabase.
>
> **NLP** uses sentence-transformers for zero-shot theme classification, plus hand-built tone and location lexicons.
>
> The **frontend** is React 19, TypeScript, Vite, and Tailwind CSS v4, with custom canvas charts — no off-the-shelf chart library.
>
> **Automation** runs through GitHub Actions on a schedule, with Playwright smoke tests and unit tests for corridor tagging.
>
> SHAP is implemented at the research level; exposing it interactively in the dashboard is planned future work.

**[Advance to Slide 7]**

---

## Slide 7 — Data Design · ~15 seconds

> All live product data lives in PostgreSQL.
>
> Core tables store articles with NLP tags, daily GPR scores, daily corridor scores, dual-signal cache, and pipeline run logs.
>
> The Flask API is the single read layer for the dashboard. This keeps the frontend simple and the data contract stable.

**[Advance to Slide 8 — LIVE DEMO]**

---

## Slide 8 — Live UI Demo · ~2 minutes

> Let me show you the working prototype.

**[Switch to browser: http://127.0.0.1:5173]**

### Home (`/`)

> This is the **Home screen**. At the top you see today's **GPR regime** — whether geopolitical risk is Low, Moderate, Elevated, or High — and the **Joint Stress** reading.
>
> The globe highlights **top corridors** under stress. This is live data from our API, not static screenshots.

### News Intelligence (`/news`)

> On **News Intelligence**, every retained article appears with its **theme tags**, **tone score**, and **location matches**.
>
> I can filter by theme — for example, armed conflict — or by corridor. This is the explainability layer: users can see *which headlines* are driving the index.

### Macro (`/macroeconomics`)

> The **Macro** page shows our **dual-signal design**. On one side: the geopolitical GPR signal. On the other: a **market-only** NIFTY volatility estimate.
>
> Below that, **Joint Stress** combines them with a transparent formula — sixty percent GPR percentile, forty percent volatility percentile.
>
> When these two signals diverge — geo hot but markets calm, or the reverse — that gap itself is useful intelligence.

### Trade & Corridor Risk (`/trade-corridor`)

> **Trade and Corridor Risk** maps all **twelve tracked corridors** — Hormuz, Malacca, the India-China LAC border, Red Sea, and others.
>
> Each corridor shows **risk, threat, energy exposure, and goods exposure** — weighted by how much India-relevant trade flows through that route.

### Platform Quality (`/quality`)

> Finally, **Platform Quality** is where we show our validation numbers, per-feed health, and methodology — including results that did not go our way. Transparency is part of the product.

**[Return to slides — Slide 9]**

---

## Slide 9 — Cost Analysis · ~15 seconds

> Project cost is minimal because the entire stack is open source.
>
> **Software cost: zero rupees.** Python, React, PostgreSQL, PyTorch, scikit-learn, sentence-transformers, Git and GitHub Actions — all free for educational use.
>
> **External storage and accessories: two thousand five hundred rupees.**
>
> **Optional future cloud deployment: one thousand rupees** — an estimate; current development uses existing laptop and internet resources.
>
> **Total estimated project cost: three thousand five hundred rupees.**
>
> No direct labour cost is incurred — development is within the B.E. capstone curriculum.

**[Advance to Slide 10]**

---

## Slide 10 — News Intelligence Outcomes · ~45 seconds

> Let me walk through what happens to news before it becomes an index.
>
> We ingest from **nine configured sources** in two tiers.
>
> **Tier 1** — four dedicated geopolitics and defence feeds: StratNews Global, Bharat Shakti, Gateway House, and ThePrint Defence. These are ingested **without** a keyword gate.
>
> **Tier 2** — five mainstream outlets: India Today, The Hindu, Times of India, NDTV, and Hindustan Times. These pass through a **geopolitics keyword filter** before insertion.
>
> All sources are **deduplicated** using title similarity within a two-hour window.
>
> The pipeline runs **every twenty-five minutes** via GitHub Actions.
>
> Typical hit rate: about **twelve percent** of articles are GPR-positive — right inside our target band of ten to twenty-five percent.
>
> Each retained article is stored with structured output: themes, tone, locations, confidence, and model metadata. That becomes the input for both GPR and corridor scoring.

**[Advance to Slide 11]**

---

## Slide 11 — India AI-GPR · ~60 seconds

> The India AI-GPR Index is our core analytical output, and we validated it against the academic benchmark.
>
> **Distribution targets — all met:**
>
> - Mean GPR index: **one hundred** — target one hundred. ✓
> - Standard deviation: **sixty-four point one five** — target thirty-five to seventy. ✓
> - Median: **ninety-two point three** — target ninety to one fifteen. ✓
> - Ninety-ninth percentile: **two thirty-nine point four** — target two hundred to four hundred. ✓
> - GPR-positive share: **eleven point nine zero percent** — target ten to twenty-five percent. ✓
>
> **Benchmark correlation — all passed:**
>
> - Monthly global GPR: Pearson **r equals zero point five seven one** — target greater than zero point five zero. ✓
> - Monthly India GPRC_IND: **r equals zero point six six** — target greater than zero point four five. ✓
> - Daily moving average thirty versus Caldara GPRD: **r equals zero point five six eight**. ✓
> - Daily moving average seven versus Caldara GPRD: **r equals zero point five five six**. ✓
>
> We use **split-era normalization** because historical GDELT volume — tens of thousands of articles per day — is incomparable to live India news — a few hundred per day. One shared baseline would squash India-era scores near zero.
>
> **Regime bands:** Low below zero sigma, Moderate from zero to one, Elevated from one to two, High at two sigma and above.

**[Advance to Slide 12]**

---

## Slide 12 — Trade & Corridor Risk · ~45 seconds

> Global GPR tells you *that* risk is elevated. Corridor risk tells you *where*.
>
> The pipeline has four steps:
>
> **One** — location extraction from NLP output in GDELT format.
>
> **Two** — corridor matching using aliases, country and ADM1 codes, and geographic bounds.
>
> **Three** — exposure weighting for energy and goods trade relevant to India.
>
> **Four** — daily output: corridor risk, threat, energy score, and goods score.
>
> We track **twelve strategic corridors**. Each has metadata for India's energy and goods exposure. Articles are matched by named aliases, country codes, or geographic bounds.
>
> Validation includes **hand-labelled corridor fixtures** — we did not ship this without testing the matching logic.

**[Advance to Slide 13]**

---

## Slide 13 — NIFTY 50 + Joint Stress · ~45 seconds

> We studied whether GPR improves NIFTY fifty volatility forecasts. We kept the market model honest.
>
> **Two independent signals:**
>
> The **GPR signal** comes from our India AI-GPR index, expressed as a geopolitical percentile.
>
> The **NIFTY signal** comes from a market-only volatility model — XGBoost with purged walk-forward validation — expressed as a volatility percentile.
>
> **Joint Stress** combines them transparently:
>
> > Joint Stress equals **zero point six** times GPR percentile **plus zero point four** times volatility percentile.
>
> Regimes: **Calm** below fifty, **Watch** from fifty to seventy-four, **High Stress** at seventy-five and above.
>
> Here is our honest finding: GPR does **not** beat market-only volatility forecasts out of sample. Market-only ROC-AUC is approximately **zero point eight three one**; adding GPR drops it to approximately **zero point eight one five**.
>
> Rather than hide that, we show both signals **side by side**. When geo risk is elevated but markets are calm — or the opposite — that divergence is itself decision-relevant intelligence.

**[Advance to Slide 14]**

---

## Slide 14 — Team & Progress · ~30 seconds

> Quick note on team contributions and where we stand at mid-semester.
>
> **Aaditi Verma** — Domain Analyst — geopolitical modelling and domain validation.
>
> **Devasya Kanwar** — AI/ML Engineer — NLP pipelines and predictive algorithms.
>
> **Aadi Jain** — Backend Developer — infrastructure and data pipeline management.
>
> **Vansh Gupta** — Frontend Engineer — UI/UX design and data visualization.
>
> **Arianna Vohra** — Project Manager — planning, scheduling, and risk analysis.
>
> **Current progress — all core modules complete:**
>
> - Automated news pipeline, nine sources — **one hundred percent**
> - India AI-GPR, validated versus benchmark — **one hundred percent**
> - NIFTY volatility study, out-of-sample result — **one hundred percent**
> - Trade and Corridor Risk, twelve corridors — **one hundred percent**
>
> **Current work focus:** Joint Stress integration and validation, explainable AI, and Portfolio Exposure in the dashboard.

**[Advance to Slide 15]**

---

## Slide 15 — Future Work & Closing · ~45 seconds

> Five items on our roadmap for the remainder of the capstone:
>
> **One** — Native GPR wiring at full historical scale, so we can substitute our own India-native series for the public benchmark dependency.
>
> **Two** — Full-article extraction, moving beyond the roughly forty-word RSS summaries we store today, to reduce tone-scoring noise.
>
> **Three** — Automated test coverage extended across ingestion, NLP, and NIFTY models.
>
> **Four** — Containerized deployment with Docker Compose for the API, database, and frontend.
>
> **Five** — SHAP exposed in the dashboard UI, so users can see feature attribution alongside Platform Quality.
>
> **Six** — Portfolio Integration, bringing portfolio-level risk context into the dashboard.
>
> **Closing:**
>
> India has over **one hundred seventy million** active demat accounts. Markets here react to border conflicts, sanctions, commodity shocks, and diplomatic crises — often before global indices catch up.
>
> Forsyt is not trying to predict the market. It is trying to give analysts, investors, and supply-chain teams something they have not had before: a **daily, validated, India-specific geopolitical risk picture** — mapped to the trade routes that matter, shown **honestly** alongside market volatility, in a **live dashboard that runs itself**.
>
> Thank you. We are happy to take your questions or run the demo again.

---

## Q&A — Prepared Answers

Use these if an evaluator asks follow-up questions. Answer in your own words; do not read verbatim.

### "Why not just use GDELT for live news?"

> GDELT relies heavily on Western media and misses India-specific regional events. We use GDELT only as a one-time historical dataset to calibrate normalization baselines. Live news comes from nine curated Indian RSS sources, tagged by our own NLP pipeline in a GDELT-compatible format.

### "Is this investment advice?"

> No. Forsyt is a research and intelligence tool for informational purposes only. It supports human judgement. It is not a SEBI-registered investment advisor and should not be used as the sole basis for financial decisions.

### "Does GPR predict NIFTY?"

> We tested this rigorously with purged walk-forward validation. GPR does not improve out-of-sample volatility forecasts. Market-only performs better. That is why we show both signals separately instead of claiming GPR predicts the market.

### "How do you know the index is credible?"

> Monthly correlation with Caldara-Iacoviello is zero point five seven one — above our zero point five zero target. Distribution statistics match our design targets. Known crisis events like Galwan and Pulwama show GPR spikes within three days in manual checks.

### "What happens when an RSS feed breaks?"

> We track per-feed health in the database. The Platform Quality page shows feed status. There is no automated email alert today — that is future work.

### "What is split-era normalization?"

> Historical GDELT-era article volume is roughly fifteen thousand to thirty thousand articles per day globally. Live India news is roughly two hundred to four hundred per day. If we used one shared baseline, India-era scores would be compressed near zero. Split-era normalization keeps two separate baselines so the index remains meaningful in the live product era.

### "What is not built yet?"

> Full article text extraction, SHAP in the dashboard UI, a real portfolio allocation engine, and containerized deployment. The Portfolio page today is informational, not an allocation tool. We state this explicitly in our documentation.

### "What does it cost to run?"

> Zero rupees for software. GitHub Actions and Supabase free tier cover current automation and storage. Optional cloud deployment is estimated at one thousand rupees.

---

## Emergency Backup Plan

If the live demo fails:

1. Say: *"We have screenshots from the working prototype in our report — let me walk you through those while the API reconnects."*
2. Use Slide 8 captures from `CAPSTONE EVAL 2.pdf`.
3. Offer to show `/quality` validation numbers from the slide deck (Slide 11) — those do not require live data.

---

## Timing Cheat Sheet

| Section | Target time | Cumulative |
|---|---|---|
| Slides 1–2 (intro + problem) | 1:00 | 1:00 |
| Slides 3–7 (design + architecture) | 2:20 | 3:20 |
| Slide 8 (live demo) | 2:00 | 5:20 |
| Slides 9–13 (outcomes) | 3:30 | 8:50 |
| Slides 14–15 (team + close) | 1:15 | ~10:00 |

**If you are capped at 7 minutes:** shorten the demo to Home + Macro only (~1 min) and compress Slides 4–7 into one minute.

---

## Key Numbers to Memorize

| What | Number |
|---|---|
| News sources | 9 |
| Scrape interval | Every 25 minutes |
| GPR-positive hit rate | ~12% (target 10–25%) |
| Corridors tracked | 12 |
| Caldara monthly r | 0.571 (target > 0.50) |
| India GPRC_IND r | 0.66 (target > 0.45) |
| Joint Stress formula | 0.6 × GPR + 0.4 × vol |
| Market-only ROC-AUC | ~0.831 |
| Market + GPR ROC-AUC | ~0.815 |
| Total project cost | ₹3,500 |
| Software cost | ₹0 |

---

*Last updated: August 2026 · aligned with `CAPSTONE EVAL 2.pdf` and current codebase documentation.*
