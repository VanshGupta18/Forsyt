# Forsyt — 3-Minute Submission Video

Covers the four required points: **About the project · Tech stack & architecture · How you used AWS · Learning and growth.**

Target runtime **2:50** (hard ceiling 3:00). Word budget ≈ 430 words at a calm 150 wpm. Every second below is accounted for — if you overrun, cut from §1, never from §3 (AWS) .

---

## Pre-record checklist

- [ ] Backend up: `python -m news_dataset.api.server` (port 5001) — or `finch compose up`
- [ ] Frontend up: `npm run dev` in `frontend/` → http://127.0.0.1:5173
- [ ] Browser at **1920×1080**, zoom 100%, bookmarks bar hidden, one clean window
- [ ] Pre-open tabs in this order so you never fumble: **Home → News → Trade Corridor → Macro → Quality**
- [ ] Editor pre-opened at `template.yaml` and `news_dataset/api/cache.py` (for the AWS beat)
- [ ] A terminal with `sam validate --lint` typed but **not run** (run it on camera — it's one clean line of proof)
- [ ] Architecture diagram exported as a PNG (render the Mermaid block in `README.md`) — you need it as a still, not a code block
- [ ] Record at 1080p/30fps, mic test first — audio quality matters more than video quality
- [ ] Upload as **Unlisted** (or Public) on YouTube, **not Private** — verify by opening the link in an incognito window before submitting

---

## Full video architecture (shot list)

| # | Time | Duration | On screen | Audio |
|---|------|----------|-----------|-------|
| 1 | 0:00–0:08 | 8s | Title card: *Forsyt — Geopolitical Risk Intelligence for Indian Markets*, name, team, CPG 300 | Hook line |
| 2 | 0:08–0:35 | 27s | **Live dashboard Home page**, scrolling slowly: GPR gauge, regime badge, threat panels | §1 About the project |
| 3 | 0:35–0:55 | 20s | **Demo A** — News page: theme filter click, tagged article feed | §1 continued |
| 4 | 0:55–1:15 | 20s | **Demo B** — Trade Corridor page: map, click a corridor, AI explanation panel opens | §1 continued |
| 5 | 1:15–1:50 | 35s | **Architecture diagram PNG**, animate/highlight left→right as you narrate each hop | §2 Tech stack & architecture |
| 6 | 1:50–2:30 | 40s | **Split**: `template.yaml` on screen → `cache.py` backend switch → terminal running `sam validate --lint` → `docker-compose.yml` localstack/opensearch services | §3 How I used AWS |
| 7 | 2:30–2:48 | 18s | Back to dashboard, slow zoom-out on Home; or Quality page showing validation numbers | §4 Learning and growth |
| 8 | 2:48–2:55 | 7s | End card: repo URL + live URL + thanks | Close |

**Editing notes**
- No transitions longer than 0.3s. Hard cuts only.
- Burn in small lower-third captions for each section title ("Architecture", "AWS Usage") so a reviewer skimming still hits all four points.
- Keep your webcam either off, or a small circle in the bottom-right for §1 and §4 only. Screen must dominate during §2 and §3.
- Record narration and screen separately if you can — it is far easier to hit 3:00 when the voice track is cut first and the screen is matched to it.

---

## The script

### §0 — Hook · 0:00–0:08

> Hi, I'm Devasya. This is **Forsyt** — a platform that turns Indian news into a daily, measurable geopolitical risk score for Indian financial markets.

### §1 — About the project · 0:08–1:15 *(over live demo)*

> India's markets react to border tensions, sanctions and shipping-lane disruptions, but the risk indices analysts use are Western-sourced, global, and published monthly with a lag.
>
> Forsyt closes that gap. It polls **nine Indian news sources** on a schedule, tags every article with a geopolitical theme, a tone score and location tags, and aggregates them into a **daily India GPR Index** — calibrated so an average day reads 100, and validated against the Caldara–Iacoviello academic benchmark.
>
> *(cut to News page)* Here's the tagged event feed, filterable by theme.
>
> *(cut to Corridor page)* And here's what makes it India-specific — **twelve trade corridors**, from the Strait of Hormuz to the India–China border, each scored independently. Click one, and an AI-generated explanation tells you *which headlines* moved that score. It's a decision-support tool, not a trading system.

### §2 — Tech stack & architecture · 1:15–1:50 *(over diagram)*

> The architecture is a one-way pipeline.
>
> RSS feeds land in **PostgreSQL**. An NLP layer — sentence-transformer embeddings for theme classification, lexicon scoring for tone, regex extraction for locations — tags each article. Those tags export as Parquet into the **GPR scoring engine**, which writes the daily index and corridor scores back to Postgres.
>
> A **Flask API** served by Gunicorn exposes it, and a **React 19 + TypeScript + Vite** dashboard consumes it across six pages. A separate NIFTY volatility model plugs in as a second signal, shown side-by-side rather than blended — because our own validation showed GPR features did *not* improve out-of-sample volatility forecasts, and we report that honestly.
>
> Scheduled **GitHub Actions** keep every stage fresh with no machine of mine running.

### §3 — How I used AWS · 1:50–2:30 *(over code + terminal)*

> AWS shows up at the infrastructure seam.
>
> The API's hot-read cache was an in-process dictionary — which pinned us to a single Gunicorn worker, because two workers each hold their own copy and clients see inconsistent state. I defined a **DynamoDB** table in **AWS SAM** — `template.yaml` — as a shared, out-of-process cache backend: on-demand billing, a constant partition key so prefix invalidation is a `begins_with` query instead of a table scan, and native **TTL** for garbage collection.
>
> *(run `sam validate --lint`)* It validates as real infrastructure-as-code.
>
> The backend is swappable by one environment variable, and fails open — a DynamoDB error is logged as a cache miss, never raised.
>
> For development I run it against **LocalStack**, so the whole AWS path is testable locally. **OpenSearch** provides k-NN vector search over the article embeddings we already compute, and **Finch**, AWS's open-source container CLI, builds the local stack. The frontend is served through **AWS Amplify and CloudFront**.

### §4 — Learning and growth · 2:30–2:48

> The biggest lesson was that infrastructure choices are trade-offs, not defaults. I kept the heavy NLP on GitHub Actions instead of Lambda, because `torch` and sentence-transformers don't fit a fifteen-minute ceiling — and moved only the piece that genuinely pays for itself onto AWS. I also learned to report negative results: when GPR features failed to beat a market-only baseline, we published that instead of hiding it.
>
> Thank you for watching.

---

## Timing safety valves

If you run long, cut in this order:

1. The News-page sentence in §1 (−6s)
2. The NIFTY/validation sentence in §2 (−10s)
3. The "fails open" sentence in §3 (−5s)

Never cut the SAM/DynamoDB sentences or the `sam validate` shot — that is the load-bearing AWS evidence.

## One thing to verify before recording

The stack doc (`docs/STACK_GAP_AND_IMPLEMENTATION_PLAN.md`) records the frontend on **Amplify + CloudFront** and notes Elastic Beanstalk was decommissioned, leaving the backend without a live host. Confirm the Amplify deployment is still live before you claim it on camera — if it isn't, change that line to "the frontend is built for Amplify and CloudFront hosting" and show the dashboard locally.
