# Geopolitical News Dataset: Theoretical Foundation & Logic

This document explains the sourcing logic, filtering heuristics, and how ingested articles feed the India GPR product pipeline.

**Code map:** [codebase.md](./codebase.md)

---

## 1. The Two-Tier Sourcing Logic

Rather than scraping every possible news outlet constantly, we separate sources into two tiers. This prevents IP bans, keeps the database focused, and improves relevance.

### Tier 1: Dedicated Geopolitics (4 sources)

**Sources:** *StratNews Global (SNG), Bharat Shakti (BS), Gateway House (GH), ThePrint Defence (TPD)*

**Cadence:** Every ~7 minutes.

**Logic:** These four sources are dedicated to Indian defence, strategic affairs, and foreign policy. Because their baseline relevance is high, **every article from these feeds is ingested unfiltered** (bypassing keyword checks). They form the high-confidence core of the dataset.

### Tier 2: Mainstream World News (5 sources)

**Sources:** *India Today, The Hindu, Times of India, NDTV, Hindustan Times* (world RSS)

**Cadence:** Every ~12 minutes.

**Logic:** These are India's largest mainstream outlets. To avoid Bollywood, cricket, and local politics:

1. We target **World/International RSS feeds** only (e.g. The Hindu international feeder).
2. Tier 2 articles pass through a **strict keyword filter** — only geopolitical keyword matches are ingested.

> **Note (Aug 2026):** Indian Express was removed from Tier 2 — its feed returns well-formed XML but blocks shared CI IPs. Hindustan Times world RSS replaced it.

In live testing, this approach yields ~29% geopolitically relevant articles from Tier 2 feeds while filtering the rest.

---

## 2. Heuristic Filtering (Keyword Matrix)

For Tier 2 sources, an article must match at least one term from the curated geopolitics keyword matrix (40+ high-signal terms):

- **Borders & Neighbors:** `LAC`, `LoC`, `China`, `Pakistan`, `cross-border`
- **Military & Defence:** `defence ministry`, `army`, `navy`, `missile`, `S-400`, `BrahMos`
- **Diplomacy & Treaties:** `foreign policy`, `diplomatic`, `embassy`, `sanctions`, `Quad`, `SCO`, `UNSC`, `G20`
- **Security & Conflict:** `terrorism`, `ceasefire`, `intelligence agency`, `RAW`, `ISI`

This ensures generic international stories are ignored unless they touch strategic, military, or diplomatic affairs relevant to Indian interests.

---

## 3. Fuzzy Deduplication Logic

A single geopolitical event is reported by multiple outlets (and sometimes updated multiple times by one outlet). Unchecked duplicates create artificial spikes in ML and index construction.

**The solution:**

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `DEDUP_WINDOW` | 2 hours | Compare only against recent canonical articles |
| `DEDUP_THRESHOLD` | **0.85** | `SequenceMatcher` title similarity ratio |
| Storage | `duplicate_of` column | Duplicate rows kept; API serves canonical only |

When similarity ≥ 0.85, the new row is saved with `duplicate_of` set to the **earliest** matching article ID. This preserves auditability and supports "event prominence" (how many outlets covered the same story).

---

## 4. From articles to GPR (downstream)

Ingestion is only step 1. The product pipeline:

```
articles (Postgres)
    → NLP tagging (themes, tone, V2Locations, GCAM)
    → india_processed_YYYYMMDD.parquet
    → gkg_gpr_pipeline (same scoring as GDELT GKG method)
    → split-era normalization (India baseline from 2026-08-09)
    → gpr_daily + corridor_daily → Postgres → API page bundles
```

**Score semantics (product era):** GPR **100** = average India-news stress day; corridors sorted by **7-day moving average** risk.

**GDELT warmup (local only):** Jan–Aug 2026 global GKG builds baselines for 7MA; those rows are **not** synced to Postgres. See [`docs/GDELT_WARMUP.md`](../../docs/GDELT_WARMUP.md).

**Theory for scoring math:** [`gpr_index/docs/gpr-theory.md`](../../gpr_index/docs/gpr-theory.md)
