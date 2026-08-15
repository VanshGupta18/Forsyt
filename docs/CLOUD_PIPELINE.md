# Cloud pipeline — keep Postgres fresh without local runs

Production data flows through GitHub Actions into Supabase. Your laptop only reads `DATABASE_URL` via the API.

## Prerequisites

1. **`DATABASE_URL`** — set in `news_dataset/.env` locally and as a GitHub Actions secret (same Supabase project).
2. **Workflows on `main`** — merge and push:
   - `.github/workflows/scrape.yml`
   - `.github/workflows/nlp.yml`
   - `.github/workflows/platform_refresh.yml`
   - `.github/workflows/daily_index.yml`
   - `.github/workflows/catch_up_index.yml`

## One-time backfill (after merge)

Use when corridor/GPR dates lag behind news (e.g. stuck at 12 Aug while headlines are current).

**GitHub UI:** Actions → **Catch up index** → Run workflow

| Input | Value |
|-------|--------|
| `from_date` | `2026-08-13` (or first missing day) |
| `to_date` | leave blank for today UTC |

**CLI (requires `gh` auth):**

```bash
cd "/Volumes/My Passport/Forsyt"
gh workflow run catch_up_index.yml \
  -f from_date=2026-08-13
```

Watch the run:

```bash
gh run list --workflow=catch_up_index.yml --limit 3
gh run watch
```

## Ongoing automation

| Workflow | Schedule | Updates |
|----------|----------|---------|
| `scrape.yml` | every 25 min | `geo_articles` (news feed) |
| `nlp.yml` | hourly `:10` | NLP tags on new articles |
| `platform_refresh.yml` | hourly `:20` | parquets → GPR + corridors → Postgres + dual-signal |
| `daily_index.yml` | daily ~midnight IST | authoritative end-of-day close |

Manual trigger for platform refresh:

```bash
gh workflow run platform_refresh.yml
```

## Verify (no local pipeline)

```bash
curl -s http://127.0.0.1:5001/api/status | python3 -m json.tool
```

Expect:

- `latest_dates.corridor` and `latest_dates.gpr` within 1–2 days of today
- `last_pipeline_runs.platform_refresh` populated after first hourly run
- `stale_warning` null when index is current

## Push checklist

```bash
git add .github/workflows/ news_dataset/pipeline/ news_dataset/api/ frontend/src/ docs/CLOUD_PIPELINE.md README.md
git commit -m "Align score UX with hourly cloud refresh model."
git push origin HEAD
```

Then run **Catch up index** once in GitHub Actions.
