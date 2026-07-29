# Geopolitical News Dataset: Codebase Documentation

This document explains the technical architecture, line-of-code (LOC) flow, and function-level responsibilities of the `news_dataset` generation pipeline.

## 1. `ingestion/feed_utils.py`
This module acts as the low-level network and parsing layer.
- **`safe_get(url, timeout)`**: Wraps `requests.get()` in a `try-except` block. Uses a spoofed browser `User-Agent` (defined in `HEADERS`) to prevent HTTP 403 blocks from news sites. Returns the response or `None` on failure.
- **`parse_feed(url, retries, backoff)`**: Uses `feedparser` to read RSS/Atom feeds. Includes an exponential backoff retry loop. This is critical because shared CI/CD IPs (like GitHub Actions) often experience transient rate limits.
- **`parse_rss_time(entry)`**: A normalizer function. Different news agencies use different time formats (e.g., `published_parsed` vs `updated_parsed`). This function standardizes the feed entry into a clean string.

## 2. `ingestion/geo_pipeline.py`
This is the core business logic layer for data extraction and heuristic filtering.
- **Data Dictionaries (`TIER1_FEEDS`, `TIER2_FEEDS`)**: Configures the target URLs, source codes (e.g., `TOI`, `TH`), and maps them to their respective frequency tiers.
- **`matches_geopolitics(text)`**: The heuristic engine. Takes article text and checks it against arrays of keywords (`KEYWORDS_MILITARY`, `KEYWORDS_DIPLOMACY`, etc.). Calculates a `confidence` score (e.g., "HIGH", "MEDIUM") based on term frequency and returns the matched keywords.
- **`find_duplicate(title, published_at, recent_articles)`**: The fuzzy dedup engine. Uses `difflib.SequenceMatcher` to compare a new title against articles stored in the last 24 hours. Returns the database `id` of the canonical article if a match > 65% is found.
- **`fetch_tier(tier)`**: Iterates over all feeds in a given tier. For each feed:
  1. Calls `parse_feed`
  2. Extracts title, link, and description.
  3. Passes the text through `matches_geopolitics`.
  4. Returns a dictionary of valid candidates to the scheduler.

## 3. `ingestion/geo_scheduler.py`
This is the execution driver. It manages state and triggers `geo_pipeline.py`.
- **`tier_due(tier, health, now)`**: Checks the database `geo_feed_health` table. Determines if a tier's required interval (e.g., 7 mins) has elapsed since `last_attempt`.
- **`run_cycle()`**: 
  1. Determines which tiers are due.
  2. Calls `fetch_tier()` for due tiers.
  3. Sorts all fetched candidates chronologically (oldest first) so the *earliest* reporting outlet gets the canonical database entry.
  4. Calls `find_duplicate()` for each candidate.
  5. Pushes the article to the database via `insert_geo_article`.
  6. Logs cycle statistics (`log_geo_cycle_stats`) and health metadata.
- **`run_continuous()`**: A while-loop wrapper for running locally. Sleeps for `POLL_TICK` (60s) between checking if a tier is due.

## 4. `db.py`
The storage abstraction layer. Automatically toggles between PostgreSQL (production) and SQLite (local dev) based on the `DATABASE_URL` environment variable.
- **`init_db()`**: Bootstraps the `articles`, `geo_feed_health`, and `geo_cycle_stats` tables. Includes necessary indexes on `tier`, `scraped_at`, and `duplicate_of` to keep queries fast.
- **`insert_geo_article(article)`**: Writes the structured dictionary into the SQL table. Uses `ON CONFLICT DO NOTHING` (or `INSERT OR IGNORE`) on the `link` column to ensure strict URL uniqueness.
- **`get_geo_articles(...)`**: Retrieves the dataset. By default, it uses `duplicate_of IS NULL` to filter out fuzzy duplicates, serving only canonical unique events to the API.
- **Health & Stats Loggers**: `upsert_geo_feed_health` and `log_geo_cycle_stats` maintain the telemetry needed by the scheduler to know when to fetch next.

## 5. `api/server.py` & `api/utils.py`
The data exposure layer.
- **`api/server.py`**: A Flask app with `flask_restful`. Defines three endpoints:
  - `/news/<tier>`: Serves the dataset as JSON.
  - `/health`: Exposes total article counts and DB status.
  - `/stats`: Exposes the telemetry data (recent cycle yields, feed failure rates).
- **`api/utils.py`**: Acts as a bridge, cleanly importing `get_geo_articles` from `db.py` to decouple the Flask routing from the raw SQL queries.

## 6. `.github/workflows/scrape.yml`
The automation engine.
- Runs on a cron schedule (`*/25 * * * *`). 
- Changes the working directory to `./news_dataset`.
- Installs `requirements.txt` with pip caching.
- Executes `python -m ingestion.geo_scheduler --once`, which lets GitHub Actions trigger the script statelessly while the database maintains the `last_attempt` timing logic.
