# Forsyt Frontend — Architecture

React + Vite + Tailwind dashboard consuming the unified Forsyt API.

**Product overview:** [`docs/PRODUCT.md`](../../docs/PRODUCT.md)  
**API reference:** [`news_dataset/docs/codebase.md`](../../news_dataset/docs/codebase.md)  
**Term definitions:** [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md)

---

## New to this project? Start here

If you're new to React/TypeScript/this stack, here's the short version of
what each piece does and how a page actually loads. See
[`docs/GLOSSARY.md`](../../docs/GLOSSARY.md) for deeper definitions of any
term below.

- **React** — a JavaScript library for building UIs out of reusable
  "components" (functions that return HTML-like markup called JSX). Forsyt
  is a "single-page app": the browser loads one HTML file, and React swaps
  content in and out of it as you navigate, instead of requesting a whole
  new page from the server each time.
- **TypeScript** — JavaScript with an added type system. It lets you say
  "this function takes a string and returns a number" and catches mistakes
  (typos, wrong argument types) while you're writing code, before it ever
  runs in a browser.
- **Vite** — the build tool / dev server. `npm run dev` starts Vite, which
  serves the app instantly in development and rebuilds only what changed
  when you edit a file; `npm run build` bundles everything into optimized
  static files for production.
- **Tailwind CSS** — a utility-first CSS framework: instead of writing
  custom `.css` classes, you compose small pre-made classes directly in your
  markup (e.g. `className="flex gap-2 text-sm"`). This project also defines
  a handful of its own semantic classes on top (`corridor-panel`,
  `corridor-kicker`, etc.) — see `src/index.css`.
- **TanStack Query ("react-query")** — the library that fetches data from
  the backend API and caches it, so pages don't have to hand-roll their own
  loading/error/refetch state machines. See `lib/queryClient.ts`.

**How a page load actually flows:**

```text
Browser requests "/"
  → index.html loads, which loads src/main.tsx
  → React starts, App.tsx picks the right page component for the URL
  → that page calls useQuery(...), which calls a fetch...() function in lib/api.ts
  → in dev, Vite's proxy forwards that request to the Flask API at 127.0.0.1:5001
    (see vite.config.ts) — in production, VITE_API_BASE points straight at the
    deployed API
  → the Flask API (in the separate news_dataset/ Python module) reads from
    Postgres (or a CSV fallback) and returns JSON
  → react-query caches that JSON and hands it to the page component, which renders it
```

---

## Stack

| Layer | Technology |
|-------|------------|
| Framework | React 19 + TypeScript |
| Build | Vite |
| Routing | React Router |
| Data fetching | TanStack Query (`queryClient.ts`) |
| Styling | Tailwind CSS + custom tokens in `index.css` |
| Charts | Canvas helpers (`lib/chartCanvas.ts`), sparklines |
| Maps / globe | `d3-geo`, `d3-selection`, `d3-zoom`, `topojson-client`, `world-atlas` (`HeroGlobe.tsx`, `CorridorRiskMap.tsx`) |

Dev server proxies `/api` → `http://127.0.0.1:5001` (see `vite.config.ts`).

---

## Routes → API bundles

| Route | Page | Primary API |
|-------|------|-------------|
| `/` | `Home.tsx` | `GET /api/pages/home` |
| `/news` | `NewsDashboard.tsx` | `GET /api/pages/news` |
| `/macroeconomics` | `MacroDashboard.tsx` | `GET /api/pages/macro` |
| `/trade-corridor` | `CorridorRiskDashboard.tsx` | `GET /api/pages/corridor` |
| `/portfolio-exposure` | `PortfolioDashboard.tsx` | `GET /api/pages/portfolio` |
| `/quality` | `AccuracyDashboard.tsx` | `GET /api/pages/quality` |
| `/about` | redirect → `/quality` | — |

Navigation modules defined in `lib/modules.ts`. Shell chrome: `AppChrome.tsx`, `Layout.tsx`, `Footer.tsx`.

---

## Key components

### Home & hero

| Component | Role |
|-----------|------|
| `Hero.tsx`, `HeroGlobe.tsx` | Visual hero + corridor globe thresholds |
| `HeroVerdictBlock.tsx` | Today's regime verdict copy |
| `TodayVerdict.tsx` | GPR regime badge |
| `MacroPulseStrip.tsx`, `PulseCard.tsx` | Live market + GPR strip |
| `useHomeLiveData.ts` | Home bundle hook with polling |

### Macro / dual-signal

| Component | Role |
|-----------|------|
| `DualSignalChart.tsx` | Geo + vol side-by-side dials |
| `GprHistoryChart.tsx` | GPR history with event markers; baseline line gated before index start |
| `MarketSparkline.tsx`, `MicroSparkline.tsx` | Quote sparklines |

### Corridors & news

| Component | Role |
|-----------|------|
| `CorridorRiskMap.tsx` | Map visualization |
| `CorridorNewsTicker.tsx` | Corridor-linked headlines |
| `NewsHero.tsx`, `NewsArticleCard.tsx` | Event feed cards |
| `NewsRiskPanel.tsx` | Risk context panel |

### Quality / accuracy (`components/quality/`)

| Component | Role |
|-----------|------|
| `HeadlineTrustCards.tsx` | Trust metrics summary |
| `MethodologyPipeline.tsx` | Pipeline diagram |
| `DataArchitectureDiagram.tsx` | System architecture viz |
| `QualityCheckTable.tsx`, `QualityMetricTile.tsx` | Validation checks |
| `ValidationSummaryBar.tsx`, `ValidationVizPanel.tsx` | Report visuals |
| `LiveStatusStrip.tsx`, `StaleDataBanner.tsx` | Freshness UX |
| `QualityPassBadge.tsx` | Pass/fail badges |

Copy and plain-language strings: `lib/qualityCopy.ts`, `qualityPlain.ts`, `qualityVisuals.ts`.

---

## Client data layer

**`lib/api.ts`** — TypeScript types + fetch helpers for all page bundles, events feed, dual-signal, health/status.

**`lib/queryClient.ts`** — Shared QueryClient; default `staleTime` is 5 minutes (`5 * 60_000`ms), with per-page `refetchInterval`s on top (5–15 min depending on page).

**`lib/storage.ts`** — Local preferences (watchlist, news filters).

### Domain copy & config

| Module | Purpose |
|--------|---------|
| `homeCopy.ts`, `macroCopy.ts`, `corridorCopy.ts` | User-facing strings, regime labels |
| `corridorGeo.ts`, `corridorWatchlist.ts` | Map coords + default watchlist |
| `modules.ts` | Nav module definitions |

---

## Score semantics in UI

- **GPR 100** = average India-news stress day (product era from **2026-08-09**)
- **Calibrating badges** when index history &lt; 60 days or low confidence
- **Corridor board** sorted by `corridor_risk_7ma`, not raw daily spike
- **Chart baseline line** hidden until enough product-era history exists

---

## Local development

```bash
# Terminal 1 — API (required)
python -m news_dataset.api.server

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
```

Open **http://127.0.0.1:5173**. Do **not** set `ALLOW_CSV_FALLBACK=1` unless offline — stale CSVs mask live Postgres data.

**Smoke test:** `node smoke.mjs` (checks key routes against running API).

**Production build:** set `VITE_API_BASE` in `frontend/.env`, then `npm run build`.

---

## Known unused / dead files

A few files in this module appear to be leftover cruft with no code
references anywhere: `frontend/undefined/bg-mouse-tight.png`, all five files
in `src/assets/`, `public/icons.svg`, and `src/lib/macroNews.ts`. None have
been deleted — see [`docs/DISCREPANCIES.md`](../../docs/DISCREPANCIES.md)
for the full list and reasoning.
