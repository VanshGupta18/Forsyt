# Corridor Risk Index

The corridor index reuses the existing article score and changes only the
geographic aggregation. It covers 12 India-relevant maritime, land-border,
and strategic corridors.

**Primary source code:** `scripts/corridor_index.py`, `scripts/corridors.py`, `scripts/split_era.py`

## Threat × exposure

For corridor \(c\) on day \(t\):

```text
raw_ratio(c,t) = sum(positive article scores tagged to c) / total_articles(t)
Threat(c,t) = per-corridor GPR index transform (mean 100 on that corridor's baseline)
EnergyRisk(c,t) = clamp(Threat × energy_exposure, 0, 100)
GoodsRisk(c,t) = clamp(Threat × goods_exposure, 0, 100)
CorridorRisk(c,t) = max(EnergyRisk, GoodsRisk)
CorridorRisk_7MA(c,t) = 7-day rolling mean of CorridorRisk (product era only when split-era active)
```

The output retains `raw_ratio` and `threat_index`; exposure never changes the
news-derived threat signal. Energy and goods are separate because their
published denominators differ (for example, crude-import share versus
merchandise-trade share). Taking the larger channel produces one bounded
operational score without adding incompatible percentages.

**Operational score:** UI and API sort corridors by `corridor_risk_7ma` (smoothed), not raw daily `corridor_risk`.

The denominator is all articles on that day, exactly as in the parent GPR
index. A single article may tag multiple corridors, but it contributes at most
once to each corridor.

### Normalization (softer than parent GPR)

Corridor threat uses a **softer** tail than global GPR:

| Parameter | Global GPR | Corridor |
|-----------|------------|----------|
| Tail exponent | 2.45 | **1.5** (`CORRIDOR_TAIL_EXPONENT`) |
| Upper-half stretch | 1.08 | **1.05** |

Each corridor needs at least **2 baseline hit-days** (`MIN_BASELINE_HIT_DAYS`) or it gets `score_status=insufficient_history` and `threat_index=0`.

### Split-era (2026)

When a batch spans GKG warmup and India product eras, corridor normalization mirrors GPR:

- Separate warmup vs product baselines **per corridor**
- `corridor_risk_7ma` / `_30ma` computed on product-era rows only
- `hit_days` for baseline eligibility still use full merged history when hits are merged

See [GPR split-era](./gpr-theory.md#9-split-era-normalization-2026-product).

### Incremental merge (hourly / dirty-day rescans)

Product-only rescans must not drop warmup hit history:

- `_merge_prior_corridor_hits()` — keeps prior warmup rows in `corridor_article_hits.parquet` when rescoring `>= INDIA_GPR_INDEX_START`
- `_merge_corridor_totals()` — reuses denominator metadata from saved `gpr_corridor_daily.csv` for days not rescanned

CLI: `corridor --dates YYYY-MM-DD,...` for specific days; `corridor --from-hits` to rebuild from saved hits without rescanning source parquets.

## Matching rules

`scripts/corridors.py` is the single registry used by both GDELT and the news
NLP path. A V2Locations block matches a corridor when any of these rules holds:

1. A place fullname matches a registered alias.
2. Its GDELT FIPS country code belongs to the corridor.
3. Its latitude/longitude falls in a maritime bounding box.

Land-border corridors additionally require a registered ADM1 code. This stops
an India-wide mention from matching Ladakh, Attari, Petrapole, or Raxaul.
Codes are GDELT FIPS 10-4 (`CH` is China), not ISO.

`news_dataset/nlp/locations.py` imports `CORRIDOR_PLACES` and emits canonical
type-4 blocks when an alias appears. Both sources therefore run through the
same `tag_corridors()` function.

## Exposure registry and sources

Zero means that no current comparable throughput percentage is encoded; it
does not mean zero strategic importance.

- Strait of Hormuz — energy 33.6%, goods 0%.
  [H1 2025 crude share](https://www.businessupturn.com/nation/india-cut-its-hormuz-dependence-from-61-to-33-before-the-war-began-this-chart-shows-how-foresighted-that-decision-was/)
- Red Sea / Bab el-Mandeb / Suez — energy 27.1%, goods 35%.
  [H1 2025 crude share](https://www.businessupturn.com/nation/india-cut-its-hormuz-dependence-from-61-to-33-before-the-war-began-this-chart-shows-how-foresighted-that-decision-was/);
  [ICRA trade exposure](https://www.icra.in/Rating/DownloadResearchSummaryReport?id=5494)
- Strait of Malacca — energy 0%, goods 55%.
  [Ministry of External Affairs, Indian trade through the South China Sea](https://www.mea.gov.in/lok-sabha.htm?dtl%2F35118%2Fquestion+no+4832+indian+trade+through+south+china+sea=)
- Cape of Good Hope — energy 13.6%, goods 0%.
  [H1 2025 crude share](https://www.businessupturn.com/nation/india-cut-its-hormuz-dependence-from-61-to-33-before-the-war-began-this-chart-shows-how-foresighted-that-decision-was/)
- Danish Straits / Baltic — energy 17.6%, goods 0%.
  [H1 2025 crude share](https://www.businessupturn.com/nation/india-cut-its-hormuz-dependence-from-61-to-33-before-the-war-began-this-chart-shows-how-foresighted-that-decision-was/)
- Taiwan Strait / South China Sea — energy 0%, goods 55%.
  [Ministry of External Affairs, Indian trade through the South China Sea](https://www.mea.gov.in/lok-sabha.htm?dtl%2F35118%2Fquestion+no+4832+indian+trade+through+south+china+sea=)
- India-China LAC — energy 0%, goods 0%.
  [Ministry of External Affairs](https://www.mea.gov.in/press-releases.htm?dtl/37455/)
- India-Pakistan / Attari-Wagah — energy 0%, goods 0%.
  [Department of Commerce](https://www.commerce.gov.in/international-trade/trade-agreements/india-pakistan-trade-relations/)
- India-Bangladesh / Petrapole — energy 0%, goods 0%.
  [Land Ports Authority of India](https://www.lpai.gov.in/en/icp-petrapole)
- India-Nepal / Raxaul-Birgunj — energy 0%, goods 0%.
  [Ministry of External Affairs bilateral brief](https://www.mea.gov.in/Portal/ForeignRelation/India-Nepal_2024.pdf)
- IMEC — energy 0%, goods 0%.
  [Press Information Bureau](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2122269)
- INSTC / Chabahar — energy 0%, goods 0%.
  [Ministry of External Affairs](https://www.mea.gov.in/press-releases.htm?dtl/37867/)

## Outputs and validation

- `gpr_corridor_daily.csv`: raw threat, normalized threat, both exposure
  channels, and bounded CorridorRisk.
- `corridor_article_hits.parquet`: slim positive-article hits used for fast
  re-aggregation after registry changes.
- `validation/corridor_*.csv`: event response, cross-corridor discrimination,
  parent-index leakage, match coverage, optional slot-sampling comparison, and
  optional GDELT/news-path parity.

The validation flags parent correlation above 0.95. Coverage is the share of
GPR-positive articles matching at least one corridor. Slot sampling compares
daily `raw_ratio` from fully downloaded days with a fixed every-Nth-slot
sample. News parity runs the identical tagger over both sources and flags a
corridor when GDELT matches it but the news path produces no matches.

Use `corridor --from-hits` to rebuild normalization and exposure columns from
the saved hits and denominator metadata without reading source Parquets.

## 2026 data decision

**Decision:** use fixed every-4th-slot sampling (`--slot-step 4 --slot-offset 0`)
for the Hormuz-closure validation window (2026-01-01 to 2026-04-30).

Rationale: the corridor index is a ratio with `A_t` in the denominator, so a
fixed systematic sample of the 96 daily slots leaves the ratio unbiased while
cutting storage roughly 4× (~45 GB instead of ~200 GB for four months). Full
2026 download is deferred unless the sampling bias check fails.

Verification procedure before trusting 2026 sampled data:

1. Rebuild a few fully downloaded 2025 days at `--slot-step 4`.
2. Build corridor indices for both the full and sampled versions.
3. Run `validate-corridors --sample-full-path ... --sample-subset-path ...`.
4. Accept the sample only if relative bias stays within ~10%.

## Sampling and parity CLI support

`download --slot-step 4 --slot-offset 0` downloads 24 fixed slots per day.
`preprocess` accepts the same flags, allowing a few fully downloaded 2025 days
to be rebuilt at quarter density without downloading them again. Build
separate full and sampled corridor output directories, then pass their daily
CSVs to:

```text
validate-corridors --sample-full-path FULL/gpr_corridor_daily.csv \
  --sample-subset-path SAMPLED/gpr_corridor_daily.csv
```

After the fixed-slot comparison is accepted, use the same `--slot-step` and
`--slot-offset` for both the 2026 download and preprocessing commands.

For source parity, point validation at a GDELT processed file/directory and a
news-export processed file/directory:

```text
validate-corridors --gdelt-locations GDELT_PATH \
  --news-locations NEWS_PATH --parity-sample-size 100000
```

Omit `--parity-sample-size` for a full comparison.
