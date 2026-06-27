# Phase 1: GKG-Based GPR Pipeline — Complete Methodology

---

## Overview

```
INPUT:  35000+ Raw GKG Files (2025)
OUTPUT: Validated GPR Index + All Decompositions

Steps:
1. Data Ingestion & Storage Strategy
2. Schema Understanding & Field Selection
3. Preprocessing Pipeline
4. Geopolitical Candidate Filtering
5. Article-Level GPR Scoring
6. Daily Index Construction
7. Feature Decompositions
8. Validation Framework
9. Decision Gate
```

---

## 1. Data Ingestion & Storage Strategy

### 1.1 File Structure Understanding

Your 35000+ files are GKG 2.0 format:
- Each file covers a 15-minute window
- Named as: `YYYYMMDDHHMMSS.gkg.csv`
- Tab-separated, no header row
- 27 columns per record
- Approximate size: 5–20 MB per file uncompressed

```
35000 files × 15 min = ~364 days = full year 2025 ✓
Expected total records: 50–150 million rows
Expected uncompressed size: 200–500 GB
```

### 1.2 Storage Strategy

Do not load all files into memory at once. Use a batched processing approach:

```
Raw GKG Files (.csv)
        ↓
    Batch Processing
    (500 files per batch)
        ↓
    Filtered Parquet Files
    (only necessary columns)
        ↓
    Single Merged Parquet
    (cleaned, deduplicated)
        ↓
    Scored Parquet
    (with GPR scores)
        ↓
    Aggregated CSV Outputs
    (daily index, decompositions)
```

**Why Parquet:**
- Columnar storage — reading one column does not load others
- Compression built-in — typically 5–10x smaller than CSV
- Pandas/Polars read it significantly faster than CSV
- Preserves data types correctly

### 1.3 Processing Framework Choice

For 35000+ files you have two options:

**Option A: Pandas (simpler)**
- Sufficient if you process in batches
- Familiar API
- Slower on large datasets

**Option B: Polars (recommended)**
- 5–10x faster than Pandas on large files
- Lazy evaluation — builds query plan before executing
- Much lower memory usage
- Same conceptual operations, different syntax

Recommendation: Use Polars for file parsing and aggregation, Pandas for analysis and visualization since most validation libraries expect Pandas DataFrames.

---

## 2. Schema Understanding & Field Selection

### 2.1 Full GKG 2.0 Schema

```
Col 1:  GKGRECORDID          → Unique record identifier
Col 2:  DATE                 → YYYYMMDDHHMMSS format
Col 3:  SourceCollectionIdentifier → 1=web, 2=citation, 3=core
Col 4:  SourceCommonName     → Publication name
Col 5:  DocumentIdentifier   → Article URL
Col 6:  Counts               → V1 event counts (deprecated)
Col 7:  V2Counts             → V2 event counts
Col 8:  Themes               → V1 themes (deprecated)
Col 9:  V2Themes             → Primary theme codes ← USE THIS
Col 10: Locations            → V1 locations (deprecated)
Col 11: V2Locations          → Structured location data ← USE THIS
Col 12: Persons              → V1 persons
Col 13: V2Persons            → Named persons mentioned
Col 14: Organizations        → V1 organizations
Col 15: V2Organizations      → Named organizations mentioned
Col 16: V2Tone               → Sentiment scores ← USE THIS
Col 17: Dates                → Dates mentioned in text
Col 18: GCAM                 → Content analysis measures ← USE THIS
Col 19: SharingImage         → Primary image URL
Col 20: RelatedImages        → Related image URLs
Col 21: SocialImageEmbeds    → Social media images
Col 22: SocialVideoEmbeds    → Social media videos
Col 23: Quotations           → Direct quotes extracted
Col 24: AllNames             → All named entities
Col 25: Amounts              → Numerical amounts mentioned
Col 26: TranslationInfo      → Translation metadata
Col 27: Extras               → Additional metadata
```

### 2.2 Fields You Will Use

```
DATE            → Time series construction
SourceCommonName → Source tracking and normalization
DocumentIdentifier → Deduplication key
V2Themes        → Primary geopolitical signal (most important)
V2Tone          → Sentiment intensity signal
V2Locations     → Country-level decomposition
GCAM            → Fine-grained conflict dimensions
```

**Fields you do NOT need:**
Everything else. Load only the 7 fields above to save memory and processing time.

### 2.3 Field Format Details

**V2Themes format:**
```
THEME1;THEME2;THEME3;...
Example:
ARMEDCONFLICT;TAX_WORLDMAG_WAR_CONFLICT;MILITARY;WB_CONFLICT_AND_VIOLENCE
```
Each theme is separated by semicolon. Some themes include character offsets after a comma — strip these.

**V2Tone format:**
```
overall,positive,negative,polarity,actrefdensity,selfrefdensity
Example:
-3.45,2.11,5.56,7.67,12.3,1.2
```
Six comma-separated float values. Negative overall tone = more negative sentiment.

**V2Locations format:**
```
type#fullname#countrycode#adm1code#adm2code#lat#lon#featureid;...
Example:
1#Ukraine#UP#UP00#UP00#48.3794#31.1656#UP;3#Kyiv#UP#UP12#UP12#50.45#30.52#UP12
```
Multiple locations separated by semicolon. Country code is position 3 (index 2) after splitting by #.

**GCAM format:**
```
dimension:value,dimension:value,...
Example:
c18.1:0.45,c18.2:0.23,c18.3:0.67,c9.1:0.34,wc:245
```
Key:value pairs separated by comma. wc = word count, useful for normalization.

---

## 3. Preprocessing Pipeline

### 3.1 Step-by-Step Process

**Step 1: Batch File Parsing**

```
For each batch of 500 files:
  → Read tab-separated file with no header
  → Assign column names from schema
  → Load only 7 required columns
  → Skip malformed rows (on_bad_lines='skip')
  → Save batch as compressed Parquet
```

Handle these common issues:
- Some files may be empty or corrupted → catch exceptions per file
- Encoding issues → force UTF-8, replace errors
- Files may have variable number of columns → use error handling
- Compressed files (.csv.gz) → handle automatically

**Step 2: Date Parsing**

```
DATE field: 20250115143000
Extract:    20250115
Parse as:   2025-01-15

Drop records where date parsing fails
Drop records outside 2025 range (data quality check)
```

**Step 3: V2Tone Parsing**

```
Input:  "-3.45,2.11,5.56,7.67,12.3,1.2"
Output:
  tone_overall   = -3.45
  tone_positive  =  2.11
  tone_negative  =  5.56  (take absolute value)
  tone_polarity  =  7.67
  tone_actref    = 12.30
  tone_selfref   =  1.20

Handle: missing values, non-numeric values → set to 0.0
Handle: fewer than 6 comma-separated values → fill missing with 0.0
```

**Step 4: GCAM Dimension Extraction**

Target dimensions for GPR:
```
c18.1 = Security threat intensity
c18.2 = Military force intensity  
c18.3 = Conflict intensity
c9.1  = Conflict affect (emotional tone)
c9.2  = Hostility intensity
wc    = Word count (for normalization)
```

Extraction logic:
```
Input:  "c18.1:0.45,c18.2:0.23,c18.3:0.67,c9.1:0.34,wc:245"
For dimension c18.3:
  → Check if "c18.3" exists in string
  → Split on "c18.3:" → take second part
  → Split on "," → take first part
  → Convert to float
  → If any step fails → return 0.0
```

**Step 5: V2Themes Cleaning**

```
Input:  "ARMEDCONFLICT,45;TAX_WORLDMAG_WAR_CONFLICT,120;MILITARY,89"
Note:   Some GDELT versions append character offset after comma

Clean:  Split on ";" → for each theme → split on "," → take first part
Output: ["ARMEDCONFLICT", "TAX_WORLDMAG_WAR_CONFLICT", "MILITARY"]
Store:  As cleaned semicolon-separated string or list
```

**Step 6: V2Locations Parsing**

```
Input:  "1#Ukraine#UP#UP00#UP00#48.37#31.16#UP;3#Kyiv#UP#UP12#UP12#50.45#30.52#UP12"
For each location (split by ";"):
  → Split by "#"
  → Extract index 2 = country code (ISO2 or GDELT country code)
  → Keep unique country codes per article
Output: ["UP", "UP"] → deduplicate → ["UP"]  (UP = Ukraine in GDELT)
```

Note: GDELT uses its own 2-letter country codes that mostly match ISO 3166-1 alpha-2 but with some differences. Maintain a mapping table for important countries.

**Step 7: Deduplication**

```
Same article appears in multiple 15-minute GKG files
Deduplication key: DocumentIdentifier + date
Keep first occurrence
Expected reduction: 10–20% of records are duplicates
```

**Step 8: Source Classification**

Classify sources into tiers for optional filtering:
```
Tier A: Major international outlets
        (reuters, apnews, bbc, nytimes, washingtonpost, theguardian, ft, bloomberg)
Tier B: Regional major outlets
        (aljazeera, scmp, thehindu, dawn, dawnews)
Tier C: All other sources

Track source count per day per tier
This enables sensitivity analysis by source tier
```

---

## 4. Geopolitical Candidate Filtering

### 4.1 Purpose

This is the first-stage filter that replicates the keyword pre-filter in Iacoviello & Tong (2026). It reduces the full corpus to articles plausibly discussing geopolitical events before applying the more expensive scoring step.

Expected outcome:
```
All articles:       100%  (50–150M records)
After pre-filter:    20–30%  (candidate articles)
After scoring (>0): 10–15%  (GPR-positive articles)
```

### 4.2 Three-Tier Theme Taxonomy

Build based on GDELT's actual theme codes. This is the most critical design decision in Phase 1.

**Tier 1 — Geopolitical Acts (Direct Conflict Realization)**
These themes indicate an adverse geopolitical event is actually happening. Correspond to Caldara's GPA index categories.

```
TAX_WORLDMAG_WAR_CONFLICT
ARMEDCONFLICT
WB_CONFLICT_AND_VIOLENCE
TERROR_ATTACK
INVASION
COUP
ETHNIC_VIOLENCE
GENOCIDE
CRISISLEX_C07_SAFETY
NUCLEAR_WEAPONS
CHEMICAL_WEAPONS
BIOLOGICAL_WEAPONS
BALLISTIC_MISSILES
WEAPONS_TRADE
```

Weight: 1.0

**Tier 2 — Geopolitical Threats (Buildup and Risk Signals)**
These themes indicate geopolitical risk is building or being discussed. Correspond to Caldara's GPT index categories.

```
CONFLICT
TERROR
MILITARY
TAX_FNCACT_MILITARY
TAX_FNCACT_SOLDIER
TAX_FNCACT_REBEL
TAX_FNCACT_TERRORIST
SANCTION
NUCLEAR
REFUGEE
WB_POLITICAL_STABILITY
DIPLOMATIC_CRISIS
BLOCKADE
BORDER_DISPUTE
MARITIME_DISPUTE
PROXY_WAR
POLITICAL_UNREST
CRISISLEX_CRISISLEXREC
```

Weight: 0.6

**Tier 3 — Geopolitical Context (Background Signals)**
These themes provide geopolitical context without direct risk. Lower weight, help capture articles missed by Tier 1/2.

```
SOVEREIGNTY
SELF_DETERMINATION
ARMS_TRADE
MILITARY_ALLIANCE
ESPIONAGE
CYBERATTACK
WAR_CRIME
CEASEFIRE
PEACE_AGREEMENT
POLITICAL_PRISONER
TAX_FNCACT_SPY
SECESSION
```

Weight: 0.3

### 4.3 Pre-Filter Logic

```
Article passes pre-filter IF:
  V2Themes contains at least ONE theme from any tier

Articles that fail pre-filter:
  → gpr_score = 0.0
  → Still counted in total daily article count (A_t denominator)
  → Not processed further

Articles that pass pre-filter:
  → Proceed to full GPR scoring
```

### 4.4 Validating the Pre-Filter

After applying pre-filter, check:
```
1. Candidate rate: expect 20–30% of all articles
   If < 10%: theme taxonomy too restrictive, add more themes
   If > 50%: theme taxonomy too broad, tighten to Tier 1/2 only

2. False negative estimate:
   Sample 200 non-candidate articles
   Manually check: how many actually discuss geopolitical risk?
   Target: < 5% false negative rate
   Paper benchmark: 0.9%
```

---

## 5. Article-Level GPR Scoring

### 5.1 Scoring Architecture

Each candidate article receives a score in [0, 1] from three independent components:

```
gpr_score = theme_score + tone_score + gcam_score

Constraints:
  - If theme_score = 0 → gpr_score = 0 (theme is necessary condition)
  - gpr_score = min(1.0, sum of components)
  - Each component is bounded above (prevents any single component dominating)
```

### 5.2 Component 1: Theme Score

**Logic:** Count how many and which tier of geopolitical themes are present.

```
For each article:
  high_score  = count of Tier 1 themes present × 1.0
  med_score   = count of Tier 2 themes present × 0.6
  low_score   = count of Tier 3 themes present × 0.3
  raw_total   = high_score + med_score + low_score
  theme_score = min(0.50, raw_total / 3.0)
```

**Why divide by 3.0:**
Normalization factor so that a single high-weight theme match gives ~0.33, which after adding tone and GCAM components produces a score around 0.4–0.5 — reflecting moderate geopolitical risk as intended.

**Why cap at 0.50:**
Leaves room for tone and GCAM to contribute. An article with many themes but neutral tone is less credibly a crisis article than one with matching themes AND strong negative sentiment.

**Examples:**
```
Article with ARMEDCONFLICT + INVASION:
  raw = 1.0 + 1.0 = 2.0
  theme_score = min(0.50, 2.0/3.0) = 0.50

Article with MILITARY + SANCTION:
  raw = 0.6 + 0.6 = 1.2
  theme_score = min(0.50, 1.2/3.0) = 0.40

Article with SOVEREIGNTY only:
  raw = 0.3
  theme_score = min(0.50, 0.3/3.0) = 0.10
```

### 5.3 Component 2: Tone Score

**Logic:** More negative tone AND higher polarity indicates more intense geopolitical coverage.

```
neg_component = min(0.20, |tone_negative| / 30.0 × 0.20)
pol_component = min(0.10, |tone_polarity| / 20.0 × 0.10)
tone_score    = neg_component + pol_component
```

**Why these bounds:**
- GDELT negative tone typically ranges 0–30 in practice
- Polarity (difference between positive and negative) typically ranges 0–20
- Normalizing by these ranges puts both on a 0–1 scale before weighting

**Why polarity matters:**
A balanced article discussing both risks and peace efforts has low polarity. An article focused exclusively on conflict has high polarity. The latter is a stronger GPR signal.

**Examples:**
```
Highly negative conflict article (tone_neg=18, polarity=15):
  neg = min(0.20, 18/30 × 0.20) = 0.12
  pol = min(0.10, 15/20 × 0.10) = 0.075
  tone_score = 0.195

Moderately negative article (tone_neg=8, polarity=6):
  neg = min(0.20, 8/30 × 0.20) = 0.053
  pol = min(0.10, 6/20 × 0.10) = 0.030
  tone_score = 0.083
```

### 5.4 Component 3: GCAM Score

**Logic:** Use GDELT's pre-computed conflict semantic dimensions as independent validation of the theme signal.

```
gcam_score = min(0.20,
               c18_3 × 0.40 +    (conflict - highest weight)
               c18_2 × 0.30 +    (military force)
               c18_1 × 0.20 +    (security threat)
               c9_1  × 0.10      (conflict affect)
             )
```

**Why these weights:**
- c18.3 (conflict) is the most direct measure → highest weight
- c18.2 (military force) is specific to geopolitical context → second highest
- c18.1 (security threat) is broader → moderate weight
- c9.1 (conflict affect) captures emotional language → lowest weight as supplementary

**GCAM value ranges:**
GCAM dimensions are normalized by word count in GDELT, typically ranging 0.0 to 1.0. Very high values (> 0.5) indicate the article is dominated by conflict-related language.

### 5.5 Final Score Interpretation

```
0.0       → Not geopolitical (failed pre-filter or all components zero)
0.0–0.20  → Minimal geopolitical content (background context only)
0.20–0.40 → Minor tensions, diplomatic context, indirect references
0.40–0.60 → Significant tensions, ongoing conflicts, moderate risk
0.60–0.80 → Major conflict coverage, active war/terrorism discussion
0.80–1.00 → Extreme crisis coverage, imminent war, major attack

GPR-positive threshold: score > 0.20
(matches paper's effective classification threshold)
```

### 5.6 Acts vs Threats Decomposition at Article Level

Tag each scored article with its primary GPR type:

```
IF article contains any Tier 1 theme → tag as 'act'
ELIF article contains any Tier 2 theme → tag as 'threat'
ELSE → tag as 'context'

This enables:
  GPR_acts_index    = daily index using only 'act' articles
  GPR_threats_index = daily index using only 'threat' articles
  (mirrors Caldara Figure 4 exactly)
```

---

## 6. Daily Index Construction

### 6.1 Core Formula

Following Iacoviello & Tong (2026) Equation 1:

```
GPR_t = (1 / S̄) × (1 / A_t) × Σᵢ Sᵢₜ

Where:
  Sᵢₜ = gpr_score of article i on day t
  A_t  = total articles on day t (ALL articles, not just candidates)
  S̄   = normalization constant
         = mean of (Σ Sᵢₜ / A_t) over baseline period
         chosen so that mean(GPR_t) = 100 over baseline period
```

### 6.2 Why Each Element Matters

**Why sum scores rather than count positive articles:**
Summing continuous scores captures intensity. A day with 10 articles each scoring 0.8 should register higher than a day with 10 articles each scoring 0.3, even though both have 10 positive articles.

**Why divide by A_t (total articles, not candidate articles):**
If total news volume doubles but geopolitical news stays constant, the index should stay constant. Dividing by total articles controls for variation in overall news production.

**Why normalize to mean = 100:**
Allows comparison across time periods and with the published Caldara index. The absolute value of raw ratios is not interpretable; the normalized index tells you whether today is above or below average geopolitical risk.

### 6.3 Baseline Period Choice

For 2025-only data:
```
Option A: Use full 2025 mean as baseline
  → Simple, but baseline includes high-risk periods
  → Index will have mean = 100 but interpretation is circular

Option B: Use a specific low-risk reference period
  → Choose a few months in 2025 with known low geopolitical activity
  → More interpretable but subjective

Option C: Use published 2015-2019 GDELT data as baseline (if available)
  → Most comparable to Caldara's normalization
  → Requires additional historical data
```

Recommendation: For Phase 1, use Option A (full 2025 mean). The validation purpose is to check that the index moves correctly with events, not to produce a precisely calibrated level.

### 6.4 Daily Computed Metrics

For each day compute:

```
total_articles      → A_t denominator
candidate_count     → articles passing pre-filter
gpr_positive_count  → articles with score > 0.20
gpr_sum             → Σ Sᵢₜ numerator
raw_ratio           → gpr_sum / total_articles
gpr_index           → normalized raw_ratio × 100 / S̄
positive_share      → gpr_positive_count / total_articles
mean_score          → gpr_sum / gpr_positive_count (intensity measure)

gpr_acts_sum        → Σ Sᵢₜ for act-tagged articles only
gpr_threats_sum     → Σ Sᵢₜ for threat-tagged articles only
gpr_acts_index      → normalized acts index
gpr_threats_index   → normalized threats index

gpr_7ma             → 7-day moving average of gpr_index
gpr_30ma            → 30-day moving average (main plotting series)
gpr_monthly         → monthly mean of gpr_index
```

---

## 7. Feature Decompositions

### 7.1 Event Type Sub-Indices

Replicate Caldara (2022) and Iacoviello & Tong (2026) Figure 7:

```
Eight categories:
1. military_conflict  → Tier 1 war/invasion themes
2. terrorism          → TERROR, TERROR_ATTACK themes
3. diplomatic_tension → DIPLOMATIC_CRISIS, BORDER_DISPUTE themes
4. nuclear_threat     → NUCLEAR, BALLISTIC_MISSILES, NUCLEAR_WEAPONS themes
5. sanctions          → SANCTION, BLOCKADE, ARMS_TRADE themes
6. coup_regime        → COUP themes
7. civil_war          → PROXY_WAR, TAX_FNCACT_REBEL themes
8. other              → GPR-positive but no category match
```

Classification logic:
```
Assign article to FIRST matching category in order above
(higher categories take precedence)
Build separate daily index for each category
using same formula as main index
```

### 7.2 Country-Level Sub-Indices

Replicate Caldara (2022) Figure 6 and Iacoviello & Tong Figure 8:

**Parsing V2Locations:**
```
Input:  "1#Ukraine#UP#...;3#Kyiv#UP#...;1#Russia#RS#..."
Step 1: Split by ";"
Step 2: For each location: split by "#", extract index 2
Step 3: Deduplicate country codes per article
Output: ["UP", "RS"]
```

**Building country index:**
```
For each GPR-positive article (score > 0.20):
  → Extract all countries mentioned
  → Attribute full gpr_score to each country

Country_GPR_t(C) = Σ Sᵢₜ for articles mentioning country C on day t
                  / A_t (same denominator as main index)

Normalize each country index to mean = 100 over baseline
```

**Expected top countries in 2025 data:**
US, Russia, Ukraine, China, Israel, Iran, UK, Germany, France, India

### 7.3 Bilateral GPR

Simplified version without subject-verb-object parsing:

```
For each GPR-positive article:
  Extract country list [C1, C2, C3, ...]
  Generate all unique pairs: (C1,C2), (C1,C3), (C2,C3)...
  Attribute gpr_score to each pair

Bilateral_GPR_t(A,B) = Σ Sᵢₜ for articles mentioning both A and B
                       / A_t

Note: This is undirected (A,B) = (B,A)
      True directed bilateral requires NLP subject-verb-object
      extraction which is Phase 2 territory
```

Build for top 100 country pairs by total bilateral GPR.

---

## 8. Validation Framework

### 8.1 Statistical Properties Check

Compare against paper's Table 1 benchmarks:

```
Metric                  AI-GPR(paper)  Target range for yours
─────────────────────────────────────────────────────────────
Mean (normalized)            100          100 (by construction)
Standard deviation           48.5         35–70
Skewness                     1.64         > 0.5 (right-skewed)
1st percentile               41.97        > 0
25th percentile              79.61        50–90
Median                      105.46        90–115
75th percentile             138.33        120–160
99th percentile             266.95        200–400
90-day autocorrelation        0.73         > 0.50
Positive article share        15%          10–25%
```

Interpretation:
```
Right-skewed: ✓ Most days are calm, few days are extreme spikes
Autocorrelation > 0.5: ✓ Geopolitical risk is persistent, not random
Positive share 10-25%: ✓ Reasonable fraction of news is geopolitical
```

### 8.2 Event Spike Validation

**Method:**
For each known high-GPR event in 2025:
1. Compute mean GPR in 7-day window around event
2. Compute mean GPR in 30-day pre-event baseline
3. Compute z-score: (window_mean - baseline_mean) / baseline_std
4. Expect z > 1.0 for moderate events, z > 2.0 for major events

**Expected high-GPR events in 2025 to test against:**
```
Q1 2025: Trump inauguration policy shifts, Gaza developments
Q2 2025: US-China trade war escalation, tariff announcements  
Q3 2025: Various regional tensions (verify from news)
Q4 2025: (depends on what occurred)
```

Use your own knowledge of 2025 events to build this list. The more specific the event date, the sharper the validation.

### 8.3 False Positive Rate Audit

**Procedure:**
```
Step 1: Sample 500 articles with gpr_score > 0.20 randomly
Step 2: For each article, visit the URL and read it
Step 3: Label each as:
          1 = genuinely discusses current geopolitical risk
          0 = false positive (war movie, historical anniversary,
              sports metaphor, domestic politics, natural disaster)
Step 4: Compute FP rate = count(label=0) / 500
```

**Decision thresholds:**
```
FP rate < 20%  → Pipeline acceptable, proceed to Phase 2
FP rate 20-30% → Examine which themes cause most FPs
                  Tighten weights or remove problematic themes
                  Re-run audit on fresh 200-article sample
FP rate > 30%  → Add DistilBERT refinement (Phase 1 extension)
```

**Paper benchmarks:**
```
Caldara & Iacoviello (2022): FP rate = 21%
Iacoviello & Tong (2026):    FP rate = 13.3%
```

### 8.4 False Negative Rate Audit

**Procedure:**
```
Step 1: Sample 200 articles with gpr_score = 0.0
        (articles that failed pre-filter)
Step 2: Read each article
Step 3: Label as:
          1 = actually discusses geopolitical risk (false negative)
          0 = correctly excluded
Step 4: Compute FN rate = count(label=1) / 200
```

**Decision thresholds:**
```
FN rate < 5%   → Pre-filter is working well
FN rate 5-15%  → Add more themes to Tier 2 or Tier 3
FN rate > 15%  → Pre-filter too restrictive, expand significantly
```

**Paper benchmark:** 0.9% FN rate (very low because GDELT theme extraction is comprehensive)

### 8.5 Component Contribution Analysis

Verify all three scoring components are contributing:

```
Compute for all GPR-positive articles:
  - Mean theme_score
  - Mean tone_score  
  - Mean gcam_score
  - Correlation between pairs of components

Healthy decomposition:
  Theme:  50–60% of total score variance
  Tone:   20–30% of total score variance
  GCAM:   10–20% of total score variance

Correlations between components:
  Should be positive (0.2–0.5) but not too high
  High correlation (>0.8) means components are redundant
  Near-zero correlation means components are independent signals
```

### 8.6 Correlation with Published Caldara Index

Download monthly GPR data from matteoiacoviello.com/gpr.htm.

For 2025 months:
```
1. Compute your monthly GPR index
2. Get Caldara monthly values for same months
3. Compute Pearson correlation
4. Compute rank correlation (Spearman)
5. Plot both series on same chart
```

**Interpretation:**
```
Correlation > 0.65: Strong alignment, your index is valid
Correlation 0.40-0.65: Moderate alignment, acceptable given different sources
Correlation < 0.40: Investigate — likely a systematic bias in theme weights
```

Note: Do not expect perfect correlation. GDELT covers global news from thousands of sources; Caldara uses 10 curated newspapers. The index levels will differ but the direction of movements should align.

---

## 9. Decision Gate

```
After completing all validation steps:

┌──────────────────────────────────────────────────────────────────┐
│                     VALIDATION SCORECARD                         │
├─────────────────────────────┬────────────────────────────────────┤
│ CHECK                       │ RESULT → ACTION                    │
├─────────────────────────────┼────────────────────────────────────┤
│ Statistical properties      │ Pass → continue                    │
│ (skewness, autocorr, etc.)  │ Fail → check normalization logic   │
├─────────────────────────────┼────────────────────────────────────┤
│ Event spike alignment       │ Pass → continue                    │
│ (z > 1.0 for known events)  │ Fail → check theme taxonomy        │
├─────────────────────────────┼────────────────────────────────────┤
│ False positive rate         │ < 20% → proceed to Phase 2         │
│                             │ 20-30% → tune weights, re-audit    │
│                             │ > 30% → add DistilBERT             │
├─────────────────────────────┼────────────────────────────────────┤
│ False negative rate         │ < 5% → proceed                     │
│                             │ > 5% → expand theme taxonomy       │
├─────────────────────────────┼────────────────────────────────────┤
│ Caldara correlation         │ > 0.50 → methodology confirmed     │
│                             │ < 0.50 → investigate systematically│
└─────────────────────────────┴────────────────────────────────────┘

ALL PASS → Phase 1 complete, proceed to Phase 2 (Indian news dashboard)
ANY FAIL → Fix identified issue, re-run relevant validation steps
```

---

## Phase 1 Output Files

```
/outputs/
├── gpr_daily_index.csv
│     date, total_articles, gpr_index, gpr_acts_index,
│     gpr_threats_index, gpr_7ma, gpr_30ma, positive_share
│
├── gpr_monthly_index.csv
│     year_month, gpr_index, gpr_acts_index, gpr_threats_index
│
├── gpr_event_type.csv
│     date, military_conflict, terrorism, diplomatic_tension,
│     nuclear_threat, sanctions, coup_regime, civil_war, other
│
├── gpr_country_level.csv
│     date, country_code, country_gpr_index
│
├── gpr_bilateral.csv
│     date, country_a, country_b, bilateral_gpr
│
├── gpr_article_scores.parquet
│     date, source, url, gpr_score, theme_score,
│     tone_score, gcam_score, gpr_type, countries
│
└── validation_report/
      statistical_properties.csv
      event_spike_analysis.csv
      fp_audit_sample.csv
      component_contributions.csv
      caldara_correlation.png
      gpr_index_plot.png
```

---

## Summary of Key Methodological Decisions

| Decision | Choice | Justification |
|---|---|---|
| Theme as necessary condition | If no theme match → score = 0 | Prevents tone/GCAM noise generating false positives |
| Three-tier weighting | 1.0 / 0.6 / 0.3 | Maps to Caldara's Acts/Threats/Context distinction |
| Score components bounded separately | Theme ≤ 0.50, Tone ≤ 0.30, GCAM ≤ 0.20 | No single component dominates |
| Denominator = total articles | A_t includes non-candidates | Controls for daily news volume variation |
| Pre-filter before scoring | Theme filter first | Reduces compute, mirrors paper's two-stage design |
| 0.20 as positive threshold | Score > 0.20 = GPR-positive | Aligns with paper's effective classification boundary |
| Normalize to 100 | Divide by baseline mean | Enables cross-period comparison and Caldara benchmarking |