# Geopolitical News Dataset: Theoretical Foundation & Logic

This document explains the specific, hard-coded logic driving our dataset generation, why we selected our sources, and how we filter out noise to create a highly accurate, India-centric geopolitical intelligence feed.

## 1. The Two-Tier Sourcing Logic
Rather than scraping every possible news outlet constantly, we carefully curate and separate our sources into two distinct tiers. This prevents server IP bans, optimizes database size, and dramatically improves dataset relevance.

### Tier 1: Dedicated Geopolitics (4 Sources)
**Sources:** *StratNews Global (SNG), Bharat Shakti (BS), Gateway House (GH), ThePrint Defence (TPD)*
**Cadence:** Every 7 minutes.
**Logic:** These four sources are 100% dedicated to Indian defence, strategic affairs, and foreign policy. Because their baseline relevance is so high, **every article from these feeds is ingested unfiltered** (bypassing keyword checks). They represent the "high confidence" core of our dataset and are polled aggressively to capture breaking defense news.

### Tier 2: Mainstream World News (5 Sources)
**Sources:** *India Today, The Hindu, Times of India, NDTV, Indian Express*
**Cadence:** Every 12 minutes.
**Logic:** These are India's largest mainstream outlets. If we scraped their homepages, our dataset would be overwhelmed by Bollywood, cricket, and local politics. To solve this:
1. We strictly target their **World/International RSS feeders** (e.g., `/news/international/feeder/default.rss` for The Hindu).
2. Even in the World sections, there is noise (e.g., celebrity gossip abroad). Therefore, Tier 2 articles are passed through a **Strict Keyword Filter**. Only articles containing specific geopolitical keywords in their title or description are ingested.
*Note: In live testing, this pre-narrowed approach combined with keyword filtering yields ~29% geopolitically relevant articles from these feeds, successfully ignoring the remaining 71% of noise.*

## 2. Heuristic Filtering (Keyword Matrix)
For Tier 2 sources, an article must match at least one term from our curated geopolitics keyword matrix. The matrix contains 40+ high-signal terms categorized into:
- **Borders & Neighbors:** `LAC`, `LoC`, `China`, `Pakistan`, `cross-border`
- **Military & Defence:** `defence ministry`, `army`, `navy`, `missile`, `S-400`, `BrahMos`
- **Diplomacy & Treaties:** `foreign policy`, `diplomatic`, `embassy`, `sanctions`, `Quad`, `SCO`, `UNSC`, `G20`
- **Security & Conflict:** `terrorism`, `ceasefire`, `intelligence agency`, `RAW`, `ISI`

This ensures that a mainstream article about a generic international event is ignored unless it touches on strategic, military, or diplomatic affairs relevant to Indian interests.

## 3. Fuzzy Deduplication Logic
In the 24-hour news cycle, a single geopolitical event (e.g., a border skirmish) will be reported by all 9 of our sources. Furthermore, a single outlet might push 3 updated versions of the same story. If left unchecked, this creates artificial data spikes that ruin ML-based event extraction.

**The Solution:**
- **Rolling Window:** We establish a strict **2-hour deduplication window** (`DEDUP_WINDOW`). 
- **Similarity Scoring:** When a new article is fetched, its title is compared against all canonical (unique) articles ingested in the last 2 hours using Python's `SequenceMatcher`.
- **Threshold:** If the similarity ratio is **>= 85%** (`DEDUP_THRESHOLD = 0.85`), the new article is flagged as a duplicate.
- **Auditability:** We do not delete duplicates. Instead, the new row is saved but its `duplicate_of` column is set to the ID of the *earliest* (canonical) article. This allows our REST API to serve only canonical events (filtering out duplicates), while preserving the duplicate rows in the database for auditing and calculating "event prominence" (how many outlets covered the same story).
