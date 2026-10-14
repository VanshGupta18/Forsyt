# Execution Plan — Country Cards (15) + Ask Forsyt Agent

**Status:** proposed · **Owner:** @19aadijain · **Created:** 2026-09-21

Two features, one plan, because the agent's best tool is the country-card data:

1. **Country cards** — click a country on the map → an **India-relative** risk brief
   (bilateral GPR toward India, trend, event mix, corridors, market, AI summary) for
   **15 high-relevance countries**.
2. **Ask Forsyt** — a chatbot backed by an **AI agent** (Strands + Gemini) whose tools
   wrap Forsyt's existing endpoints *plus* the new country-card data.

The guiding constraint: **keep Forsyt India-native.** These are not generic global
"instability indices" (that's World Monitor's game, and it needs data we don't have for
the long tail). Every country score answers *"how much geopolitical risk does this
country carry toward India, and through which channel."*

---

## 0. Principles (do not violate)

- **Reuse over build.** The AI brief reuses `news_dataset/api/ai_summary.py` verbatim
  (Gemini + deterministic fallback + cache). The map reuses the existing d3-geo setup.
- **No new infra.** Stays on Flask + gunicorn on Elastic Beanstalk, Postgres/parquet,
  GitHub Actions cron. No Kubernetes, no serverless migration, no AgentCore (yet).
- **No auth, no Pro gating, no new map layers, no real-time.** Explicitly out of scope
  (§8). World Monitor's Mongolia panel ("CII unavailable", "6 sections unavailable",
  "Sign in to unlock") shows these are cost/coverage sinks — we skip them on purpose.
- **One new dependency:** `strands-agents` (+ `strands-agents-tools`). Nothing else.
- **Ship India + neighbors well, not 200 countries poorly.**

---

## 1. The 15 countries

Selected by relevance to India GPR: land/maritime borders, energy corridors, top trade
partners. **Codes are FIPS 10-4** — that is what the GKG pipeline and
`gpr_country_level.csv` already use (note the traps: `CH`=China, `RS`=Russia, `IN`=India).

| # | Country | FIPS | Why relevant to India | Primary corridor link |
|---|---------|------|-----------------------|-----------------------|
| 1 | China | CH | LAC border, trade deficit | LAC |
| 2 | Pakistan | PK | Border, active conflict | LoC / land |
| 3 | United States | US | Strategic partner, tech/defense | — |
| 4 | Russia | RS | Oil, defense imports | — |
| 5 | Iran | IR | Chabahar, oil, Hormuz-adjacent | Hormuz |
| 6 | Saudi Arabia | SA | Crude supplier | Hormuz |
| 7 | UAE | AE | Crude, trade, diaspora | Hormuz |
| 8 | Bangladesh | BD | Neighbor, trade, migration | Bay of Bengal |
| 9 | Sri Lanka | CE | IOR neighbor, ports | Indian Ocean |
| 10 | Nepal | NP | Open border | land |
| 11 | Myanmar | BM | Neighbor, insurgency, energy | Malacca-adjacent |
| 12 | Afghanistan | AF | Regional stability, trade route | land |
| 13 | Israel | IS | Defense tech | Red Sea |
| 14 | Qatar | QA | LNG supplier | Hormuz |
| 15 | Singapore | SN | Trade hub, Malacca | Malacca |

> Keep this list in one config constant (backend + frontend read the same source of
> truth). Add a `COUNTRIES` dict: `{fips: {name, iso2, corridors:[...]}}`. `iso2` is only
> for flag emojis on the frontend (FIPS≠ISO, e.g. CH→CN, RS→RU, CE→LK, BM→MM, SN→SG).

---

## 2. Architecture (fits the current stack)

```
GKG / India news  →  nlp/locations (co-mention)  →  bilateral_gpr (NEW)  →  Postgres/parquet
                                                                                │
frontend map click ── GET /api/pages/country/<fips> ──── country bundle ◄───────┤
                                                          (score+trend+mix+       │
                                                           corridors+market+AI)   │
                                                                                  │
chat box ── POST /api/ask ── Strands agent (Gemini) ── tools wrap endpoints ◄─────┘
```

Nothing here is a new service. `bilateral_gpr` is a scoring pass in the existing
pipeline; the two routes register on the existing Flask app like `register_ai_summary`.

---

## 3. Workstream A — Bilateral country GPR (data/backend)

**Goal:** a daily per-country score = geopolitical risk *between India and country X*.

**Method (MVP = undirected co-mention; directed is a later upgrade):**
- For each scored article, we already have GPR score + tagged locations
  (`news_dataset/nlp/locations.py`, GKG `V2Locations`).
- **Bilateral hit** = article mentions **India AND country X**. Country-X bilateral GPR
  for a day = sum/mean of GPR scores over India∩X co-mention articles, normalized to the
  same India baseline the product already uses (100 = avg India-news stress day).
- Emit: `date, country_fips, bilateral_gpr, article_count, band, trend_7d` and the
  **event-category mix** (reuse the existing 8 sub-indices, restricted to the co-mention
  set) → gives the Unrest/Conflict/Mil.Activity-style bars.
- **Directed (Phase 2, optional):** split India→X vs X→India using article
  actor/tone ordering. Skip for MVP; undirected co-mention is enough to ship.

**Tasks:**
- [ ] `COUNTRIES` config constant (§1) — single source of truth.
- [ ] `gpr_index/scripts/bilateral_index.py` — co-mention scan over the same processed
      GKG/India rows `gkg_gpr_pipeline.py` reads; writes `outputs/gpr_bilateral_daily.csv`.
- [ ] Reuse split-era normalization + 7MA logic already in the pipeline (do not
      reinvent — call the same helpers).
- [ ] Wire into an existing GitHub Actions job (the nlp/daily_index step) so it refreshes
      with everything else and commits the CSV back (repo already does this).
- [ ] **Runnable check:** `bilateral_index.py --self-check` asserts (a) India∩India is
      excluded, (b) a known co-mention day (e.g. a PK border event) scores > that day's
      baseline, (c) every one of the 15 FIPS codes produces a row or an explicit
      "insufficient data" flag.

**Constraint to surface in output:** thin-coverage countries (Nepal, Bhutan-tier) will
have low `article_count` days. Emit a `low_confidence` flag when `article_count < N`
(reuse the existing <60-day / low-volume flag convention). The card must show it.

---

## 4. Workstream B — Country-card API bundle

One page-bundle endpoint, same shape as the existing `/api/pages/*` handlers.

- [ ] `news_dataset/api/country.py` → `register_country(app)` (mirror
      `register_ai_summary`), route **`GET /api/pages/country/<fips>`** returning:
  ```json
  {
    "country": {"fips":"CH","name":"China","iso2":"CN"},
    "score": {"value": 57, "band": "Elevated", "trend": "rising", "low_confidence": false},
    "channels": {"unrest": 0, "conflict": 12, "military": 65},   // from event-category mix
    "history": [{"date":"...","value":...}, ...],                 // 30d for the sparkline
    "corridors": [{"name":"LAC","risk_7ma":...}],                 // filter existing corridor data
    "market": {"index":"^SSEC","last":3911.87,"chg_week_pct":0.61}, // yfinance, may be null
    "top_events": [ ... ],                                        // from /api/events/feed, filtered
    "summary": "…"                                                // AI brief, §5
  }
  ```
- [ ] Read bilateral CSV, corridor CSV, event feed via the **functions the existing
      handlers already call** — don't duplicate query logic; refactor shared readers if
      needed.
- [ ] Per-country market index: extend the yfinance layer with a `fips→ticker` map
      (`^SSEC`, `^NSEI`, etc.). `null` when unmapped — card degrades gracefully.
- [ ] Cache the whole bundle with `cache_get/cache_set` (per fips + data date).
- [ ] **Runnable check:** `test_country.py` — every one of the 15 fips returns 200 with a
      valid band; an unknown fips returns 404; a low-coverage country returns
      `low_confidence: true` not a crash.

---

## 5. Workstream C — AI brief per country (reuses ai_summary.py)

- [ ] Add `_country_prompt(bundle)` + `_country_deterministic(bundle)` to
      `ai_summary.py` (same file, same pattern) — framed **India-relative**: *"Explain
      this country's geopolitical risk toward India, the dominant channel (border / oil /
      trade / news), the 30-day trend, and the corridors implicated. NOT investment
      advice."*
- [ ] Reuse `_gemini_summary`, the `thinkingBudget:0` config, the cache, and the
      deterministic fallback **unchanged**. (World Monitor uses the exact same
      key-or-fallback design — "Configure GROQ_API_KEY" — we already have ours.)
- [ ] Brief is generated lazily on first card open and cached (cost control).

---

## 6. Workstream D — Frontend country cards

Reuse the existing map (d3-geo, world-atlas, react-query).

- [ ] Make the 15 countries clickable on the existing map; others inert (or greyed).
- [ ] `CountryCard` side panel: header (flag via `iso2`, name), big score + band + trend
      arrow, channel bars, 30-day sparkline, corridor chips, market line, AI brief,
      top-events list. Low-confidence badge when flagged.
- [ ] react-query hook on `/api/pages/country/<fips>`; loading + error + `null market`
      states handled.
- [ ] Colour the 15 countries on the map by score band (you already do d3 choropleth for
      corridors — reuse the scale).

---

## 7. Workstream E — Ask Forsyt agent (the AI agent)

**The chatbot is an agent** (multi-step, tool-using), because a user question ("compare
India's risk with China vs Pakistan and what's driving it") doesn't have a known
fetch-path — the model decides which tools to call. Framework: **Strands Agents SDK**
on **Gemini** (model-agnostic; keeps our existing `GEMINI_API_KEY`, no Bedrock).

- [ ] `pip install strands-agents strands-agents-tools` → add to `requirements.txt`.
- [ ] `news_dataset/api/agent.py`:
  - `@tool` wrappers over data we already serve — thin functions, docstring = schema:
    - `country_brief(fips)` → the §4 bundle
    - `analyze_portfolio(holdings)` → existing `/api/portfolio/analyze` logic
    - `recent_news(theme, location)` → existing events feed
    - `gpr_index_history(days)` → existing GPR series
    - `corridor_risk()` → existing corridor data
    - `list_countries()` → the 15 (so the agent knows its universe)
  - `Agent(model=GeminiModel("gemini-3.8-flash"), tools=[...], system_prompt=SYSTEM)`
  - `SYSTEM` = reuse `ai_summary.py` guardrails: ground every claim in tool output,
    never invent figures/tickers, **NOT investment advice**, plain text.
- [ ] Route **`POST /api/ask`** → `{"answer": str(agent(question))}`; register like the
      others. Cache identical questions per data-date.
- [ ] **Guardrails:** tool functions are read-only; wrap the loop in try/except →
      deterministic "couldn't answer from current data" on failure (never 500 to the UI).
- [ ] Frontend: a chat panel hitting `/api/ask` (react-query mutation). Plain text out.
- [ ] **Runnable check:** `test_agent.py` — with `GEMINI_API_KEY` unset, `/api/ask`
      returns the graceful fallback, not an exception; a canned question triggers at least
      one tool call (mock the model) and never fabricates a ticker.

> Deferred: Strands MCP tools, multi-agent, Bedrock AgentCore deployment. Only if a
> hand-rolled single agent measurably falls short.

---

## 8. Explicitly OUT of scope (do not build)

- Global 200-country coverage — India + 15 only.
- Extra map layers (nuclear sites, military bases, undersea cables, spaceports). Each is
  a separate licensed dataset + ongoing data-ops. High cost, low fit.
- ACLED / conflict-event ingestion for a "true" instability index — **revisit only if**
  the news-only bilateral score proves too thin (it's the #1 future upgrade, not MVP).
- Auth, accounts, Pro/premium gating, billing, export/decision-brief PDFs.
- Real-time / streaming ("LIVE", DEFCON, 1h windows). Daily batch stays.
- Directed (initiator→target) bilateral split — Phase 2 nicety.

---

## 9. Phasing

| Phase | Deliverable | Gate to next |
|-------|-------------|--------------|
| **P0 — spike** | `bilateral_index.py` on existing data; eyeball that PK/CH days score sensibly | Scores pass sanity (Galwan-type spike visible) |
| **P1 — data** | Bilateral CSV wired into cron + `low_confidence` flags | 15/15 countries produce rows or explicit flag |
| **P2 — API** | `/api/pages/country/<fips>` bundle + AI brief | All 15 return 200, cached |
| **P3 — UI** | Country cards on the map | Clickable, degrades on null market / low-conf |
| **P4 — agent** | Strands `/api/ask` + chat panel | Fallback works keyless; no fabricated figures |

Each phase is independently shippable. P0–P2 are the real value; P4 rides on them.

---

## 10. Risks / constraints (carry-forward)

- **Coverage (top risk).** India-only news is thin on distant countries. Mitigate:
  restrict to the 15, show `low_confidence` honestly, consider the GKG global era as a
  secondary lane for far countries (already ingested).
- **Score credibility.** News-GPR ≠ multi-dimensional instability. We frame it correctly
  ("news attention to India-related tension"), not as a sovereign risk score.
- **FIPS/ISO mismatch.** Single mapping table; unit-test the 15.
- **LLM cost.** Lazy generation + caching per country and per question.
- **Market data gaps.** yfinance coverage varies; `null` is a first-class state.

---

## 11. Definition of done

- 15 country cards render from live data with score, trend, channel bars, corridors,
  market (or graceful null), and an India-relative AI brief.
- Low-coverage countries show a confidence badge, never a crash or a fake number.
- Ask Forsyt answers multi-country questions by calling tools, grounded, no-advice, and
  degrades gracefully with no API key.
- Bilateral pipeline runs in the existing cron and commits its CSV like the others.
- Each non-trivial module leaves one runnable self-check (§3, §4, §7).
