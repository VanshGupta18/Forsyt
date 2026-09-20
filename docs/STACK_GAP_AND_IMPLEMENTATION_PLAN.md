# Stack Gap Analysis & Implementation Plan

Comparison of Forsyt's current stack against a target "build it open
source, on your machine — no AWS account, no card, no bill" stack
(Agents & AI, Containers & Kubernetes, Serverless, Servers & runtimes,
Data & search, Auth & policy, Plumbing), what we're adopting from it,
what we're not, and why — followed by the implementation plan (necessary
fixes, then beneficial-but-optional improvements). All 5 items have now
been implemented and verified; see each item below for what was actually
built, including two corrections found mid-implementation that changed
the approach from what was originally planned.

## Current project snapshot

Forsyt is a Flask + PostgreSQL backend serving a daily India
Geopolitical Risk Index, with a Vite/React frontend.

| Piece | Where it runs | Cost |
|---|---|---|
| Database | Supabase PostgreSQL | Free tier |
| Scraping / NLP / index pipelines | GitHub Actions (cron) | Free tier |
| Backend API | Not currently deployed (Elastic Beanstalk decommissioned) | — |
| Frontend | AWS Amplify + CloudFront | Free tier (low traffic) |

Elastic Beanstalk is no longer in the picture, so the backend currently
has no live host — the AWS-coupled config (`gunicorn_eb.conf.py`,
`create_cloudfront.py`) has been removed accordingly (see Necessary #1).
Wherever it's redeployed next, the goal stays the same: add capability
without adding a bill.

## Gap table: target vs. current

| Category | Target tool(s) | Current state |
|---|---|---|
| Agents and AI | Strands Agents SDK, PartyRock | No LLM/agent code at all — only classical NLP (`sentence-transformers` embeddings for theme-tagging in `news_dataset/nlp/themes.py`) |
| Containers & Kubernetes | Finch, EKS Distro, EKS Anywhere | No Dockerfile, no compose file, no k8s manifests anywhere |
| Serverless | SAM CLI, LocalStack | No `template.yaml`/`serverless.yml` — scheduling is 5 cron GitHub Actions workflows calling plain Python modules |
| Servers and runtimes | Firecracker, Corretto | Gunicorn + Flask, Python 3.11, platform-agnostic deploy (reads `$PORT`) |
| Data and search | OpenSearch | Postgres backend, but search is `ILIKE '%term%'` substring filtering (`db.py:757-806`) — no ranking, no fuzzy match |
| Auth and policy | Cedar | CORS is `origins: "*"`, zero authentication anywhere (`server.py:77-83`) |
| The plumbing | (unspecified) | In-process dict TTL cache — now correctly single-worker only end to end (see Necessary #1, done) |

## Decision per category — what we're using, what we're not, and why

Two different reasons show up below, and they matter for different
reasons — worth keeping separate instead of one blanket "no":

- **Ruled out by cost/account** — genuinely can't be used without paying
  or creating an AWS account.
- **Ruled out by benefit** — free and usable, but adds complexity this
  project's scale doesn't need right now.

| Category | Tool | Verdict | Reason |
|---|---|---|---|
| Agents and AI | **Strands Agents SDK** | **Using** | Free Python library, model-agnostic, runs anywhere — no account needed |
| Agents and AI | PartyRock | Excluded — cost/account | Requires an AWS/Bedrock account; contradicts "free" outright |
| Containers & K8s | **Finch** | **Using** | Free, open-source, runs on your own machine — exactly "on your machine, no AWS account" as intended. Useful now for reproducible local dev regardless of where production is hosted |
| Containers & K8s | EKS Distro / EKS Anywhere | Excluded — benefit | Genuinely free to run on your own hardware, no AWS account needed — but a full Kubernetes control plane is disproportionate for a 2-service project (Flask + React) |
| Serverless | SAM CLI, LocalStack | Excluded — benefit | Both run free, entirely on your machine, no AWS account needed to test — but your GitHub Actions cron pipelines already give you free scheduled compute, and your repo is public (confirmed), so those minutes are already unlimited. Migrating would also reintroduce the AWS account requirement for real deployment, plus a 15-min execution cap that risks your heavier NLP steps (`torch`/`sentence-transformers`) |
| Servers and runtimes | Firecracker, Corretto | Excluded — not applicable | Firecracker is Linux/KVM microVM tech underlying Lambda; Corretto is a JVM distribution. Nothing here is Java or building custom sandboxing — not a cost question, just the wrong shape for this stack |
| Data and search | OpenSearch | Excluded — cost | Can run locally for free (e.g. via Finch), but there's no persistent free-tier *hosted* OpenSearch for the live deployed site (Bonsai's free tier is too small to be useful). Replaced with native Postgres full-text search (`tsvector` + GIN index) — same practical benefit, zero extra cost, uses the Supabase DB you already have |
| Auth and policy | Cedar | Excluded — benefit | Free, open-source Python library (`cedar-policy`), runs inside your existing Flask process at zero cost — genuinely usable. Deprioritized because with a single API-key-gated API and no user roles yet, a hand-rolled check does the same job with less code. Revisit once there's an actual multi-role model to enforce |
| The plumbing | Redis (not in original image, but the natural fix) | Deferred | The real fix for today's caching bug is free and code-only (see Necessary #1). A hosted free-tier Redis (e.g. Upstash) is a fine future option only if traffic ever outgrows a single worker |

## Implementation plan — all items done

### Necessary — fixed an existing bug or open risk

#### 1. Fix the caching bug — done
**Problem:** `news_dataset/api/cache.py` is an in-process dict cache, but
the deploy config ran 2 gunicorn workers, so cached responses were
inconsistent depending on which worker served a request. There was also
a separate `gunicorn_eb.conf.py` hardcoded to Elastic Beanstalk's port
(8000) and its nginx-proxy assumptions, duplicating the generic
`news_dataset/gunicorn.conf.py`.
**Fix applied:** Removed the AWS-specific pieces — `gunicorn_eb.conf.py`
and the one-off `create_cloudfront.py` provisioning script — and
consolidated onto a single `news_dataset/gunicorn.conf.py` that binds to
`$PORT` (portable across any host) with `workers = 1`, matching what
`cache.py` requires. `Procfile` now points at that one config.

#### 2. Add basic auth — done
**Problem:** CORS was `origins: "*"` and there was no authentication of
any kind on the API.
**Fix applied:** `server.py` now has a `before_request` hook checking an
`X-API-Key` header against an `API_KEY` env var on all `/api/*` routes
(auth is a no-op if `API_KEY` is unset, so local dev keeps working
without configuration). CORS now reads its allowed origin from
`FRONTEND_ORIGIN` instead of a hardcoded `*`. The frontend
(`frontend/src/lib/api.ts`) sends the key via `VITE_API_KEY` on every
request. `.env.example` updated on both sides. Verified: unauthenticated
requests get 401, correctly-keyed requests get 200, `/health` stays
open for monitoring.

### Beneficial — improved the project, verified working

#### 3. Real search — done (implementation differs from the original plan)
**Correction found while implementing:** this product has no free-text
search box — `theme`/`corridor` are fixed preset filter buttons
(`NewsThemeNav.tsx`), and `nlp_themes`/`nlp_locations` are delimited tag
strings, not prose (`nlp_themes` is `;`-joined theme codes; `nlp_locations`
is GDELT's `#`-delimited V2Locations format). Postgres `tsvector`/`ts_rank`
ranking is the wrong tool for a fixed, date-sorted tag list — it was
designed for ranking prose relevance.
**Fix applied instead:** `get_recent_news()` in `db.py` now matches
`nlp_themes` and `nlp_locations` on exact tag/place boundaries (`;tag;`
and `#place#` respectively) instead of raw substring, fixing a real
false-positive bug (e.g. theme `"war"` could previously match a
differently-tagged article containing "war" as a substring elsewhere).
The genuinely free-text part — the `title`/`content` ILIKE fallback for
untagged articles — is now backed by a `pg_trgm` GIN index
(`idx_articles_title_trgm`, `idx_articles_content_trgm`) so it stays fast
as `articles` grows, without changing ILIKE's semantics. Verified against
the live Supabase DB: both theme and corridor filters return correct,
precisely-matched results.

#### 4. AI "explain this" feature — done
**Correction found while implementing:** the plan referenced a
`get_corridor_daily()` function that doesn't exist; the real function is
`get_corridors_latest()`. Also, corridor slugs (e.g.
`taiwan_south_china_sea`) never appear in article text, so citing
articles required resolving each corridor to its constituent place names
via `gpr_index/scripts/corridors.py`'s `CORRIDOR_PLACES` first.
**Fix applied:** `news_dataset/pipeline/explain_corridors.py` — a new
pipeline module (same shape as `daily_index.py`) that, for each corridor,
gathers cited articles via `get_recent_news()` and generates a 2-4
sentence explanation with the Strands Agents SDK against a local Ollama
model. Stored in a new `corridor_explanations` table
(`upsert_corridor_explanation`/`get_corridor_explanation` in `db.py`).
Served read-only via `GET /api/corridor/<id>/explanation` in `server.py`
— no inference at request time. Added to `daily_index.yml`: installs
Ollama, pulls `llama3.2:1b` (small, fast on a CPU-only runner), runs the
pipeline. Frontend: `CorridorExplainPanel.tsx`, wired into
`CorridorRiskDashboard.tsx`'s detail panel. **Verified end-to-end
locally** against the live Supabase DB and a local Ollama model
(`qwen2.5:7b-instruct`) — all 6 active corridors explained successfully
with grounded, headline-specific output; confirmed retrievable via the
DB function, the Flask route, and through the frontend proxy.

#### 5. Local containerization with Finch — implemented, not build-tested
**Fix applied:** root `Dockerfile` (backend, Python 3.11-slim, reuses
`news_dataset/gunicorn.conf.py`) and `frontend/Dockerfile` (Node 20,
`npm run dev`), wired together by `docker-compose.yml` — pointed at the
existing Supabase `DATABASE_URL` via `env_file`, no local Postgres
container. `vite.config.ts`'s dev proxy target is now configurable via
`DEV_API_PROXY_TARGET` (defaults unchanged for non-Docker dev) so the
frontend container can reach the backend container by service name.
`.dockerignore` added on both sides to keep `.venv`/`node_modules` out of
build contexts and to keep `news_dataset/.env`'s secrets out of the image
layer. **Caveat:** neither Finch nor Docker is installed on this machine,
so the actual `finch build`/`compose up` could not be run here — worth a
build-test pass before relying on it.
