# GPR Validation — Status & Next Steps

Last updated: after Phase 4 enhanced validation (2025 pipeline).

---

## Completed phases

| Phase | Status | Outcome |
|-------|--------|---------|
| **1 — Diagnose** | ✅ | positive_share 12.2% (target 10–25%) |
| **2 — GPR re-run** | ✅ | 348 days scored, 12.5% positive share |
| **3 — Validate** | ✅ | 6/10 statistical checks pass |
| **4 — Enhanced validation** | ✅ | MA30 Caldara r=0.589; gap analysis documented |

---

## Current scorecard (round 2 GPR outputs)

### Passing

| Check | Result |
|-------|--------|
| positive_share | **12.5%** ✅ |
| skewness | 0.71 ✅ |
| Caldara monthly (global GPR) | r=**0.599** ✅ |
| Caldara monthly (GPRC_IND India) | r=**0.653** ✅ |
| Caldara daily **MA30** | r=**0.589** ✅ |
| Caldara daily **MA7** | r=**0.579** ✅ |

### Failing (with explanation)

| Check | Result | Why |
|-------|--------|-----|
| std (daily) | 15.6 vs 35–70 | 2025-only baseline + sparse signal compresses variance |
| p99 / p75 | 144 / 108 | No extreme crisis days in our data (June gap) |
| autocorr lag-90 | 0.003 | Low daily variance; use MA series for persistence checks |
| Raw daily Caldara r | -0.058 | Misleading — Caldara raw is very noisy; **use MA30 instead** |
| Event spikes (hardcoded) | 0/3 | Events not producing z>1 vs 30-day pre-window |
| Component check | skipped | No article scores parquet (OOM on full year) |

### Key Phase 4 finding — June 2025 GKG gap

Caldara's top 10 spike days in 2025: **7 of 10 fall in our missing GKG window** (Jun 15–Jul 1).

| Metric | Caldara | Ours (forward-filled) |
|--------|---------|----------------------|
| Mean GPRD during gap | **245.5** | **128.7** (flat) |
| Peak day (Jun 23) | **540.2** | 128.7 (imputed) |

This gap is the primary reason raw daily correlation and p99 fail. **Not fixable without GKG data** (GDELT never published those days).

See: `outputs/validation/gap_caldara_comparison.csv`, `caldara_spike_crosscheck.csv`

---

## Phase 4b — In progress: positive-only aggregation

**Change:** `gpr_sum` / `raw_ratio` now sum only articles above `GPR_POSITIVE_THRESHOLD` (paper Eq. 1 alignment).

**Requires:** Full GPR re-run (~2 hrs).

```bash
python -u main.py gpr \
  --start-date 2025-01-01 --end-date 2025-12-31 \
  --output-dir outputs --no-article-scores
python main.py validate --start-date 2025-01-01 --end-date 2025-12-31
```

---

## Phase 5 — Out of scope

- Full-year `gpr_article_scores.parquet` (OOM; use `diagnose` with sampling)
- BigQuery re-fetch for Jun 15–Jul 1 (0 rows confirmed)
- Country-level re-scoring
- Dashboard (`plan/dashboard.md`, `plan/application.md`)

---

## Recommended validation interpretation

For **India GPR research**, prioritize:

1. **Monthly Caldara GPRC_IND** r > 0.50 — **passing at 0.653**
2. **Daily MA30 vs Caldara GPRD_MA30** r > 0.50 — **passing at 0.589**
3. **positive_share** 10–25% — **passing at 12.5%**

Deprioritize raw daily r and p99 until GKG gap is resolved or accepted as documented limitation.

---

## Validation reports

All in `outputs/validation/`:

| File | Purpose |
|------|---------|
| `statistical_properties.csv` | Paper Table 1 checks (daily index) |
| `statistical_properties_ma30.csv` | Same checks on 30-day MA |
| `caldara_correlation.csv` | Monthly global + India |
| `caldara_daily_correlation.csv` | Raw, MA7, MA30 daily |
| `caldara_spike_crosscheck.csv` | Top Caldara days vs our response |
| `gap_caldara_comparison.csv` | June gap: Caldara vs imputed |
| `coverage_report.csv` | Autocorr, article counts, missing days |
| `scoring_diagnosis.csv` | Article-level scoring diagnostics |
