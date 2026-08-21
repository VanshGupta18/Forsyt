# Glossary — Plain-English Terms

This page exists for one reason: nobody should have to already know the tech stack or the geopolitical-risk theory to read this codebase. If you hit a term anywhere in the code, comments, or other docs and don't recognize it, check here first.

Terms are grouped by category. Within each category they're roughly in the order you'd meet them reading through the project.

---

## The tech stack

**Repository / repo** — the whole folder of code and history tracked by git (i.e. everything under `/Volumes/My Passport/Forsyt`).

**Git / commit / branch** — git is the version-control tool that records every change to the code as a "commit" (a snapshot with a message). `git log` shows the history. A "branch" is a named line of commits (this repo's main branch is `main`).

**Python** — the programming language used for `gpr_index/`, `news_dataset/`, and `nifty-50/`. Runs top-to-bottom, uses indentation instead of `{}` to mark blocks.

**TypeScript / `.ts` / `.tsx`** — a version of JavaScript with type annotations (e.g. `count: number`), used for the `frontend/`. `.tsx` files also contain HTML-like markup (JSX) for UI; `.ts` files are plain logic.

**React** — a JavaScript/TypeScript library for building web pages out of reusable "components" (functions that return markup). Forsyt's frontend is a React app: every file in `frontend/src/components/` and `frontend/src/pages/` is a component.

**Component / hook** — a "component" is one UI building block (e.g. `<Footer />`). A "hook" is a reusable piece of stateful logic a component can call (e.g. `useHomeLiveData()` in `frontend/src/hooks/`); by convention hook names start with `use`.

**JSX** — the HTML-like syntax you write inside `.tsx` files, e.g. `<div className="card">{title}</div>`. It compiles down to regular JavaScript function calls.

**SPA (Single-Page Application)** — a web app where the browser loads one HTML page once, and JavaScript (React, here) swaps content in and out as you navigate, instead of requesting a whole new page from the server each time. Forsyt's frontend is an SPA.

**Router / route** — the part of a SPA that decides which page-component to show based on the URL (e.g. `/news` shows `NewsDashboard.tsx`). Forsyt uses the `react-router-dom` library; all routes are listed in `frontend/src/App.tsx`.

**Vite** — the build tool that turns the frontend's TypeScript/React source code into the JavaScript bundle a browser can actually run, and that runs a local dev server (`npm run dev`) with instant reload while you edit.

**npm / `package.json` / `node_modules`** — npm is JavaScript's package manager. `package.json` lists which external libraries a project depends on; `npm install` downloads them into `node_modules/` (never committed to git, hence not counted as "real" source files in this project).

**Tailwind CSS** — a CSS framework where you style elements by combining small utility class names (e.g. `class="text-sm font-bold"`) directly in markup, instead of writing separate `.css` rule files.

**react-query (`@tanstack/react-query`)** — a library that manages fetching data from the API and caching it, so components don't have to hand-roll loading states and refetch timers.

**D3.js (`d3-geo`, `d3-zoom`, `d3-selection`)** — a JavaScript library for turning raw data into custom visuals (here: hand-drawn maps and a rotating globe), by computing pixel coordinates from geographic/data coordinates. Contrast with a typical "chart library" (like Recharts) that gives you ready-made chart types — Forsyt draws its own charts on an HTML `<canvas>` instead (see `frontend/src/lib/chartCanvas.ts`).

**topojson / world-atlas** — a compact file format (and a pre-packaged dataset of it) describing country/coastline shapes, used to draw the world map and globe.

**Flask** — a lightweight Python web framework used to build Forsyt's backend API (`news_dataset/api/server.py`). It listens for HTTP requests (like `GET /api/pages/home`) and returns JSON.

**REST API / endpoint / JSON** — a "REST API" is a server that responds to URLs ("endpoints") over HTTP. `GET /api/pages/home` is one endpoint. Responses are in JSON, a text format for structured data (`{"key": "value"}`) that both Python and JavaScript can read natively.

**CORS** — a browser security rule that blocks a web page from calling an API on a different origin (domain/port) unless the API explicitly allows it. Flask's CORS setting in `server.py` is what lets the frontend (port 5173 in dev) call the API (port 5001).

**Gunicorn** — a production-grade server that runs the Flask app with multiple worker processes/threads (Flask's own built-in server is dev-only). Configured in `news_dataset/gunicorn.conf.py`.

**PostgreSQL / Postgres** — the relational (table-based) database Forsyt stores all its data in (articles, daily GPR scores, corridor scores). Accessed via a hosted Supabase instance, not a local install.

**Connection pool** — instead of opening a brand-new database connection for every single query (slow), the app keeps a small pool of already-open connections and reuses them. See `ThreadedConnectionPool` in `news_dataset/db.py`.

**Environment variable / `.env` file** — a way to configure an app (URLs, secrets, dates) outside the code, so the same code can run differently in different places without editing it. `.env` files hold these locally and are never committed to git; `.env.example` files show what variables are expected without real secrets.

**GitHub Actions / CI (Continuous Integration) / workflow** — GitHub's built-in system for running scripts automatically on a schedule or on events (a push, a manual click). Each `.yml` file in `.github/workflows/` is one such automated job — this is what actually keeps Forsyt's data fresh (scraping every 25 minutes, etc.) without anyone's laptop needing to be on.

**Parquet** — a compact, column-oriented file format for tabular data (like CSV, but smaller and faster to read/write for large datasets). Used to hand data between `news_dataset` and `gpr_index`.

**pandas / DataFrame** — pandas is Python's standard library for working with tables of data; a "DataFrame" is its table object (rows + named columns), roughly like a spreadsheet you can manipulate in code.

**RSS feed** — a standardized XML file a news website publishes listing its latest articles (title, link, summary, publish time), meant to be machine-read rather than viewed as a web page. Forsyt's `news_dataset/ingestion/` reads RSS feeds, not full web pages.

**Regex (regular expression)** — a mini pattern-matching language for text, e.g. matching any of a list of keywords in an article. Used in `news_dataset/nlp/locations.py` and `tone.py`.

**Sentence-transformer / embedding** — a pretrained machine-learning model that converts a sentence into a list of numbers ("embedding") capturing its meaning, such that similar-meaning sentences produce similar number-lists. Forsyt uses one to check whether an article's text is semantically close to a hand-written description of a risk theme (see Glossary entry "theme classifier" below) — no separate training is done in this project, the model is used as-is.

**XGBoost** — a popular, fast machine-learning algorithm for tabular prediction problems (here: forecasting NIFTY volatility from recent market/GPR data). Used only in `nifty-50/forsyt_gpr/vol_model.py`.

---

## The domain: geopolitical risk & finance

**GPR (Geopolitical Risk) index** — a number meant to measure how much of today's news is about wars, sanctions, terrorism, border conflicts, etc. — not how much economic damage happened, just how much adverse-event news there is. Originated in an academic paper by Caldara & Iacoviello (2022); this project builds an India-specific daily version of it. See `gpr_index/docs/gpr-theory.md` for the full math.

**GDELT / GKG (Global Knowledge Graph)** — GDELT is a huge, free, continuously-updated public database that scans news worldwide and auto-tags each article with themes, tone, and locations; GKG is its specific tagging format. Forsyt uses GDELT only as a one-time historical reference dataset to calibrate its scoring — live news comes from Indian RSS feeds instead, tagged by Forsyt's own NLP code in a GDELT-compatible format.

**Theme / theme classifier / theme code** — GDELT groups articles into ~hundreds of standard "theme" categories like `ARMEDCONFLICT` or `SANCTION`. Forsyt's own NLP replicates a subset of this taxonomy (`gpr_index/scripts/taxonomy.py`) using a sentence-transformer to compare an article against a hand-written description of each theme code, rather than a full classifier trained from scratch.

**Tone (in the GDELT/GPR sense)** — a percentage-based measure of how negative and/or emotionally polarized an article's language is (not the same as full "sentiment analysis" — it's a word-list-density calculation, not a trained model, in Forsyt's implementation).

**GCAM (Global Content Analysis Measures)** — GDELT's system of scoring text against dozens of psychology/emotion word-lists, several of which specifically capture conflict-related emotional language. Forsyt emulates 4 of these dimensions with its own lexicon.

**Tier 1 / Tier 2 sources** — Forsyt's own tiering of its 9 Indian RSS feeds: Tier 1 is 4 dedicated defence/strategic-affairs sites, trusted enough to ingest every article unfiltered; Tier 2 is 5 mainstream outlets, filtered down to only World/International-section articles that also match a geopolitics keyword list.

**Corridor (trade corridor)** — a specific shipping/border route that matters to Indian trade (e.g. the Strait of Hormuz, the India-China LAC border). Forsyt tracks 12 of these and scores each one's risk separately from the overall national GPR score, weighted by how much India-relevant trade/energy flows through it.

**Split-era normalization** — because the volume of articles scored per day is wildly different between the historical GDELT-warmup period (tens of thousands/day, globally) and the live India-news period (a few hundred/day), the scoring pipeline keeps two separate baselines instead of one shared one — otherwise the India-era numbers would be squashed down near zero. See `gpr_index/docs/gpr-theory.md` §9.

**Normalization / baseline / z-score** — "normalizing" a raw number means rescaling it against some reference point (a "baseline," e.g. an average) so it's comparable across time. A "z-score" specifically expresses how many standard deviations a value is from the mean.

**Realized volatility** — a standard finance measure of how much a stock/index's price has actually fluctuated over a recent window, calculated from historical returns (as opposed to *implied* volatility, which is inferred from options prices). NIFTY 50's realized volatility is what `nifty-50/forsyt_gpr` tries to forecast.

**Dual-signal / joint stress** — Forsyt's design choice to show the geopolitical-risk reading and the market-volatility reading *side by side* as two independent signals, plus one blended "joint stress" number (60% weight on the geo signal's percentile, 40% on the volatility signal's percentile) — rather than claiming one predicts the other.

**Walk-forward validation / purging** — a way to test a forecasting model on historical data without "cheating": instead of training once on all data and testing on the same data, you repeatedly train only on data up to a point in time and test only on data after it, moving that point forward through history. "Purging" means leaving a gap around the train/test boundary so a target that spans multiple days (e.g. "5-day-ahead volatility") can't leak future information into training.

**ROC-AUC** — a single number (0.5 = no better than random guessing, 1.0 = perfect) summarizing how well a model separates two outcomes (here: "will volatility be unusually high or not") across all possible decision thresholds at once. Used in `nifty-50/` to compare whether adding GPR data actually improves volatility forecasts.

**NIFTY 50** — the benchmark stock market index tracking the 50 largest companies listed on India's National Stock Exchange (NSE) — the market Forsyt's dual-signal panel contextualizes geopolitical risk against.

**Historical analog** — looking up past dates when the GPR score was at a similar level, and reporting what actually happened to NIFTY's volatility/returns on/after those dates, as an intuitive (not causal) point of reference.

---

Still stuck on a term? Search for it directly in the code — most files that use domain-specific jargon now have a comment explaining it near the first use (added as part of this documentation pass — see `docs/DISCREPANCIES.md` if something here looks out of date).
