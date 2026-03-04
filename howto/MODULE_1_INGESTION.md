# Module 1 — Ingestion, Cleaning & LLM Extraction
## Step-by-Step Build Guide

---

## What This Module Does
Pulls India-relevant geopolitical news from GDELT every 15 minutes, cleans it, deduplicates it, and uses a 2-stage LLM pipeline (FinBERT → GPT-4o-mini) to extract structured event records stored in PostgreSQL.

---

## Prerequisites
Before starting this module, you need:
- Python 3.10+
- PostgreSQL 15+ running locally or via Docker
- Redis 7+ running locally or via Docker
- An OpenAI API key (for GPT-4o-mini)
- The following Python packages installed (see Step 1)

---

## Step 1 — Set Up Your Python Environment

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install all required packages
pip install \
  requests \
  beautifulsoup4 \
  lxml \
  psycopg2-binary \
  redis \
  openai \
  transformers \
  torch \
  datasketch \
  apscheduler \
  pydantic \
  python-dotenv \
  prometheus-client
```

Create a `.env` file in your project root:
```
OPENAI_API_KEY=sk-...
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=india_gpr
POSTGRES_USER=gpr_user
POSTGRES_PASSWORD=yourpassword
REDIS_HOST=localhost
REDIS_PORT=6379
```

---

## Step 2 — Set Up PostgreSQL Tables

Connect to your PostgreSQL instance and run the following SQL. This creates everything Module 1 needs.

```sql
-- Connect as superuser first, create database and user
CREATE DATABASE india_gpr;
CREATE USER gpr_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE india_gpr TO gpr_user;

-- Connect to india_gpr database, then run:
CREATE TABLE raw_articles (
    id              BIGSERIAL PRIMARY KEY,
    url_hash        CHAR(64) UNIQUE NOT NULL,
    url             TEXT NOT NULL,
    headline        TEXT,
    body_text       TEXT,
    source_domain   VARCHAR(255),
    publish_ts      TIMESTAMPTZ,
    gdelt_event_id  VARCHAR(64),
    ingested_at     TIMESTAMPTZ DEFAULT now(),
    is_deduplicated BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_raw_articles_publish_ts ON raw_articles (publish_ts);
CREATE INDEX idx_raw_articles_url_hash   ON raw_articles (url_hash);

CREATE TABLE structured_events (
    id              BIGSERIAL PRIMARY KEY,
    raw_article_id  BIGINT REFERENCES raw_articles(id),
    event_type      VARCHAR(50) NOT NULL,
    severity        NUMERIC(4,3) NOT NULL,
    india_exposure  NUMERIC(4,3) NOT NULL,
    confidence      NUMERIC(4,3) NOT NULL,
    actors          JSONB,
    locations       JSONB,
    event_date      DATE NOT NULL,
    extracted_at    TIMESTAMPTZ DEFAULT now(),
    prompt_version  VARCHAR(20) NOT NULL,
    finbert_label   VARCHAR(20),
    llm_raw_output  TEXT
);

CREATE INDEX idx_events_event_date ON structured_events (event_date);
CREATE INDEX idx_events_event_type ON structured_events (event_type);

CREATE TABLE dead_letter_queue (
    id              BIGSERIAL PRIMARY KEY,
    raw_article_id  BIGINT REFERENCES raw_articles(id),
    failure_reason  TEXT,
    retry_count     SMALLINT DEFAULT 0,
    failed_at       TIMESTAMPTZ DEFAULT now()
);
```

**Verify:** Run `\dt` in psql — you should see `raw_articles`, `structured_events`, `dead_letter_queue`.

---

## Step 3 — Write the GDELT Puller (`ingestion/gdelt_puller.py`)

This file is responsible for querying GDELT and returning a list of article URLs with metadata.

```python
# ingestion/gdelt_puller.py

import requests
import csv
import io
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict

logger = logging.getLogger(__name__)

# GDELT GKG v2 API — returns CSV of articles
GDELT_GKG_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

def fetch_gdelt_articles(minutes_back: int = 20) -> List[Dict]:
    """
    Pull India-relevant articles from GDELT published in the last `minutes_back` minutes.
    Uses the GDELT DOC API (v2) filtered by India + negative tone + conflict events.
    
    Returns a list of dicts: {url, title, source_domain, publish_ts, gdelt_event_id}
    """
    params = {
        "query": (
            'India '
            'sourcelang:english '
            'tone<-3 '
            '(conflict OR military OR attack OR tension OR sanctions '
            'OR terrorism OR border OR nuclear OR diplomatic)'
        ),
        "mode": "ArtList",
        "maxrecords": 250,
        "timespan": f"{minutes_back}min",
        "format": "json"
    }

    try:
        response = requests.get(GDELT_DOC_API, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"GDELT API request failed: {e}")
        return []
    except ValueError:
        logger.error("Failed to parse GDELT response as JSON")
        return []

    articles = []
    for item in data.get("articles", []):
        articles.append({
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "source_domain": item.get("domain", ""),
            # GDELT returns seendate in format YYYYMMDDTHHMMSSZ
            "publish_ts": parse_gdelt_date(item.get("seendate", "")),
            "gdelt_event_id": item.get("url", "")[:64],   # use URL as proxy ID
        })

    logger.info(f"GDELT returned {len(articles)} articles")
    return articles


def parse_gdelt_date(date_str: str) -> datetime:
    """Parse GDELT date format: 20260304T142500Z"""
    try:
        return datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def fetch_article_text(url: str) -> str:
    """
    Download and return raw HTML for a given article URL.
    Returns empty string on failure.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; IndiaGPR-Research-Bot/1.0; "
            "+https://github.com/yourorg/india-ai-gpr)"
        )
    }
    try:
        # Respect robots.txt implicitly by using a descriptive User-Agent
        time.sleep(1)   # 1-second rate limit between fetches
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return ""
```

**Test this step:**
```python
from ingestion.gdelt_puller import fetch_gdelt_articles
articles = fetch_gdelt_articles(minutes_back=60)
print(f"Found {len(articles)} articles")
print(articles[0])   # inspect first result
```

---

## Step 4 — Write the Cleaner (`ingestion/cleaner.py`)

```python
# ingestion/cleaner.py

import re
import unicodedata
from bs4 import BeautifulSoup
from typing import Optional

# Boilerplate patterns to strip
BOILERPLATE_PATTERNS = [
    r'subscribe (now|today)',
    r'sign up for (our )?newsletter',
    r'cookies? (policy|settings?)',
    r'javascript (is )?required',
    r'advertisement',
    r'share (this )?article',
    r'follow us on',
    r'read (more|also):',
]

def clean_article(html: str) -> Optional[str]:
    """
    Extract and clean main article text from raw HTML.
    Returns None if article is too short (likely paywalled/stub).
    """
    if not html:
        return None

    soup = BeautifulSoup(html, 'lxml')

    # Remove script, style, nav, header, footer elements
    for tag in soup(['script', 'style', 'nav', 'header', 'footer',
                     'aside', 'form', 'iframe', 'noscript']):
        tag.decompose()

    # Try to find main article content
    main_content = (
        soup.find('article') or
        soup.find('main') or
        soup.find(class_=re.compile(r'article[-_]?(body|content|text)', re.I)) or
        soup.find(id=re.compile(r'article[-_]?(body|content|text)', re.I)) or
        soup.find('div', class_=re.compile(r'story[-_]?(body|content)', re.I))
    )

    if main_content:
        text = main_content.get_text(separator=' ')
    else:
        # Fallback: extract all paragraph text
        paragraphs = soup.find_all('p')
        text = ' '.join(p.get_text() for p in paragraphs)

    # Unicode normalization — handles Hindi/mixed encoding
    text = unicodedata.normalize('NFKC', text)

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Remove boilerplate sentences
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Remove URLs embedded in text
    text = re.sub(r'https?://\S+', '', text)

    # Length check (< 100 words = likely stub/paywall)
    word_count = len(text.split())
    if word_count < 100:
        return None

    # Token budget: truncate to first ~1,500 tokens (approx 6,000 chars)
    # This keeps the lede (most info-dense part) within GPT context budget
    if len(text) > 6000:
        text = text[:6000]

    return text.strip()


def extract_headline(html: str) -> str:
    """Extract article headline from HTML."""
    soup = BeautifulSoup(html, 'lxml')
    
    # Try meta tags first (most reliable)
    og_title = soup.find('meta', property='og:title')
    if og_title:
        return og_title.get('content', '')
    
    # Try h1
    h1 = soup.find('h1')
    if h1:
        return h1.get_text().strip()
    
    # Try title tag
    title = soup.find('title')
    if title:
        return title.get_text().strip().split('|')[0].strip()
    
    return ""
```

**Test this step:**
```python
import requests
from ingestion.cleaner import clean_article, extract_headline

html = requests.get("https://www.ndtv.com/india-news/some-article", timeout=10).text
text = clean_article(html)
if text:
    print(f"Clean text ({len(text.split())} words):")
    print(text[:500])
else:
    print("Article too short / paywalled")
```

---

## Step 5 — Write the Deduplicator (`ingestion/deduplicator.py`)

```python
# ingestion/deduplicator.py

import hashlib
import re
import logging
import redis as redis_lib
from datasketch import MinHash, MinHashLSH
from typing import Optional

logger = logging.getLogger(__name__)

# Initialize Redis connection
r = redis_lib.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Initialize MinHash LSH index (threshold = 0.80 Jaccard similarity)
# Note: In production, persist this to Redis. For simplicity we use in-memory here.
lsh = MinHashLSH(threshold=0.80, num_perm=128)

def normalize_url(url: str) -> str:
    """Remove tracking params and normalize URL for hashing."""
    # Remove common tracking params
    url = re.sub(r'[?&](utm_[^&]*|ref=[^&]*|source=[^&]*)', '', url)
    url = url.rstrip('/')
    return url.lower().strip()


def is_duplicate_url(url: str) -> bool:
    """
    Layer 1: Check if exact URL (after normalization) has been seen before.
    Returns True if duplicate.
    """
    url_hash = hashlib.sha256(normalize_url(url).encode()).hexdigest()
    
    # SETNX: set only if not exists. Returns 1 (new) or 0 (duplicate)
    is_new = r.setnx(f"dedup:url:{url_hash}", "1")
    if is_new:
        r.expire(f"dedup:url:{url_hash}", 7 * 86400)   # 7-day TTL
        return False    # Not a duplicate — this is new
    return True         # Duplicate — already seen


def get_minhash(text: str) -> MinHash:
    """
    Compute MinHash signature for article text using 5-word shingles.
    128 permutations balances accuracy vs speed.
    """
    m = MinHash(num_perm=128)
    words = text.lower().split()
    
    # Generate 5-word shingles (consecutive 5-word sequences)
    for i in range(len(words) - 4):
        shingle = ' '.join(words[i:i+5])
        m.update(shingle.encode('utf8'))
    
    return m


def is_near_duplicate(url_hash: str, text: str) -> bool:
    """
    Layer 2: Check if article is a near-duplicate using MinHash LSH.
    Returns True if a similar article (Jaccard ≥ 0.80) was seen within 48h.
    """
    m = get_minhash(text)
    
    try:
        results = lsh.query(m)
        if results:
            logger.debug(f"Near-duplicate found for {url_hash}: matches {results}")
            return True
        
        # Not a duplicate — add to LSH index
        lsh.insert(url_hash, m)
        return False
    except Exception as e:
        # If LSH check fails, err on the side of inclusion (don't drop)
        logger.warning(f"LSH check failed for {url_hash}: {e}")
        return False


def should_process(url: str, article_text: str) -> bool:
    """
    Main entry point. Returns True if article should be processed (not a duplicate).
    Run Layer 1 first (O(1) Redis lookup), then Layer 2 (MinHash) only if Layer 1 passes.
    """
    url_hash = hashlib.sha256(normalize_url(url).encode()).hexdigest()
    
    # Layer 1: Exact URL check
    if is_duplicate_url(url):
        logger.debug(f"URL duplicate: {url[:60]}")
        return False
    
    # Layer 2: Near-duplicate check (only for non-exact-URL duplicates)
    if article_text and is_near_duplicate(url_hash, article_text):
        logger.debug(f"Near-duplicate detected: {url[:60]}")
        return False
    
    return True
```

**Test this step:**
```python
from ingestion.deduplicator import should_process

# First time — should return True
print(should_process("https://ndtv.com/article-1", "India Pakistan conflict text " * 50))

# Exact same URL — should return False
print(should_process("https://ndtv.com/article-1", "India Pakistan conflict text " * 50))

# Different URL, same content — should return False (MinHash)
print(should_process("https://hindustantimes.com/same-story", "India Pakistan conflict text " * 50))
```

---

## Step 6 — Write FinBERT Classifier (`extraction/finbert_classifier.py`)

```python
# extraction/finbert_classifier.py

import logging
import torch
from transformers import pipeline
from typing import Literal

logger = logging.getLogger(__name__)

# Load FinBERT model ONCE at module import time (not per call — expensive)
# Downloads ~440MB on first run, cached after that
_finbert = None

def get_finbert():
    """Lazy-load FinBERT to avoid loading it if module is imported but not used."""
    global _finbert
    if _finbert is None:
        logger.info("Loading FinBERT model (first load may take 30-60 seconds)...")
        _finbert = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            truncation=True,
            max_length=512,
            device=0 if torch.cuda.is_available() else -1
        )
        logger.info("FinBERT loaded successfully")
    return _finbert


SentimentLabel = Literal["positive", "negative", "neutral"]

def classify_sentiment(text: str) -> tuple[SentimentLabel, float]:
    """
    Classify article sentiment using FinBERT.
    
    Returns:
        (label, score) where label is 'positive'/'negative'/'neutral'
        and score is the confidence (0.0-1.0)
    
    Routing logic:
        negative → send to GPT-4o-mini for full extraction
        positive/neutral → discard (not a geopolitical risk event)
        low confidence (< 0.60) → send to GPT anyway (err on side of inclusion)
    """
    finbert = get_finbert()
    
    # FinBERT max 512 tokens — use first 512 tokens of article
    truncated = ' '.join(text.split()[:400])   # ~400 words ≈ 512 tokens
    
    result = finbert(truncated)[0]
    label = result['label'].lower()  # 'positive', 'negative', or 'neutral'
    score = result['score']
    
    return label, score


def should_extract(text: str) -> bool:
    """
    Returns True if the article should be sent to GPT-4o-mini for extraction.
    
    Decision logic:
    - Negative → Yes (core risk signal)
    - Neutral/Positive with confidence < 0.60 → Yes (uncertain, don't miss)
    - Neutral/Positive with confidence ≥ 0.60 → No (skip, save API cost)
    """
    label, score = classify_sentiment(text)
    
    if label == "negative":
        return True
    
    # Low-confidence non-negative: still pass through to avoid missing events
    if score < 0.60:
        logger.debug(f"Low-confidence {label} ({score:.2f}) — passing to GPT anyway")
        return True
    
    return False
```

**Test this step:**
```python
from extraction.finbert_classifier import classify_sentiment, should_extract

conflict_text = """
India and China troops clashed along the Line of Actual Control in Ladakh,
resulting in injuries on both sides. The Indian Army confirmed the altercation
near Depsang Plains. Diplomatic tensions are escalating rapidly.
"""

benign_text = """
India's GDP grew at 7.2% in the third quarter, exceeding analyst expectations.
The finance minister credited robust manufacturing and services sector growth.
"""

print(classify_sentiment(conflict_text))   # Should be ('negative', ~0.9+)
print(classify_sentiment(benign_text))     # Should be ('positive', ~0.8+)
print(should_extract(conflict_text))       # True
print(should_extract(benign_text))         # False
```

---

## Step 7 — Write GPT Extractor (`extraction/gpt_extractor.py`)

```python
# extraction/gpt_extractor.py

import os
import json
import time
import logging
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

PROMPT_VERSION = "v1.3"

SYSTEM_PROMPT = """You are a geopolitical risk analyst specializing in India.
You extract structured risk event information from news articles.
Always respond with valid JSON matching the schema exactly.
Do not add commentary outside the JSON."""

USER_PROMPT_TEMPLATE = """Analyze the following news article and extract a structured geopolitical risk event.

Article:
---
{article_text}
---

Output the following JSON and nothing else:
{{
  "event_type": "<one of: military_conflict | sanctions | terrorism | diplomatic_tension | cyber_attack | economic_shock | political_instability | other>",
  "severity": <float 0.0-1.0: how serious is this event globally>,
  "india_exposure": <float 0.0-1.0: how directly does this affect India>,
  "confidence": <float 0.0-1.0: your confidence in this classification>,
  "actors": [<list of country/entity names>],
  "locations": [<list of geographic locations>],
  "summary": "<one sentence summary>"
}}

Severity guide:
- 0.9-1.0: Active war, major terrorist attack (50+ casualties), nuclear threat
- 0.6-0.8: Armed skirmish, major sanctions, significant diplomatic rupture
- 0.3-0.5: Diplomatic protest, minor military posturing, economic warning
- 0.0-0.2: Routine political disagreement, verbal rhetoric

India exposure guide:
- 0.9-1.0: Attack on Indian territory, Indian nationals killed/captured
- 0.6-0.8: Direct bilateral issue (India-Pakistan, India-China)
- 0.3-0.5: Regional event affecting India's neighborhood or trade
- 0.0-0.2: Global event with indirect India implications"""


# Pydantic schema for response validation
class EventSchema(BaseModel):
    event_type: str
    severity: float = Field(ge=0.0, le=1.0)
    india_exposure: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    actors: List[str]
    locations: List[str]
    summary: str

    @field_validator('event_type')
    @classmethod
    def valid_event_type(cls, v):
        allowed = {
            'military_conflict', 'sanctions', 'terrorism',
            'diplomatic_tension', 'cyber_attack',
            'economic_shock', 'political_instability', 'other'
        }
        if v.lower() not in allowed:
            return 'other'   # Normalize unknown types to 'other'
        return v.lower()


def extract_event(article_text: str) -> Optional[EventSchema]:
    """
    Extract structured event from article text using GPT-4o-mini.
    
    Retries up to 3 times with exponential backoff.
    Returns None if all retries fail (caller should route to dead_letter_queue).
    """
    user_message = USER_PROMPT_TEMPLATE.format(article_text=article_text)
    
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,    # CRITICAL: deterministic output
                max_tokens=400
            )
            
            raw_json = response.choices[0].message.content
            parsed = json.loads(raw_json)
            event = EventSchema(**parsed)
            return event
            
        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt+1}: JSON parse failed — {e}")
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}: Validation failed — {e}")
            
            # Rate limit: wait longer
            if "rate_limit" in str(e).lower():
                wait = 60
            else:
                wait = 2 ** attempt   # 1s, 2s, 4s
            
            if attempt < 2:
                time.sleep(wait)
    
    logger.error(f"All 3 attempts failed for article extraction")
    return None
```

**Test this step:**
```python
from extraction.gpt_extractor import extract_event

text = """
Indian and Pakistani forces exchanged fire across the Line of Control in Kashmir
on Wednesday, with the Indian Army reporting 3 soldiers injured. Pakistan's ISPR
confirmed the engagement but blamed Indian provocation. External Affairs Ministry
summoned the Pakistani ambassador to lodge a formal protest.
"""

event = extract_event(text)
if event:
    print(f"Event type: {event.event_type}")
    print(f"Severity: {event.severity}")
    print(f"India exposure: {event.india_exposure}")
    print(f"Confidence: {event.confidence}")
    print(f"Actors: {event.actors}")
    print(f"Summary: {event.summary}")
```

---

## Step 8 — Write the Pipeline Orchestrator (`ingestion/pipeline.py`)

This is the main script that ties everything together and runs every 15 minutes.

```python
# ingestion/pipeline.py

import os
import hashlib
import logging
import psycopg2
import redis
from datetime import datetime, timezone
from apscheduler.schedulers.blocking import BlockingScheduler

from ingestion.gdelt_puller import fetch_gdelt_articles, fetch_article_text
from ingestion.cleaner import clean_article, extract_headline
from ingestion.deduplicator import should_process
from extraction.finbert_classifier import should_extract
from extraction.gpt_extractor import extract_event, PROMPT_VERSION

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
def get_db():
    return psycopg2.connect(
        host=os.environ['POSTGRES_HOST'],
        port=os.environ['POSTGRES_PORT'],
        dbname=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD']
    )

def run_ingestion_cycle():
    """
    Full ingestion cycle — runs every 15 minutes.
    Pulls GDELT → cleans → deduplicates → FinBERT → GPT → stores.
    """
    logger.info("=== Ingestion cycle started ===")
    
    conn = get_db()
    cur = conn.cursor()
    
    # Pull articles from GDELT (last 20 minutes with 5-min overlap)
    raw_articles = fetch_gdelt_articles(minutes_back=20)
    logger.info(f"GDELT returned {len(raw_articles)} articles")
    
    stats = {"total": len(raw_articles), "cleaned": 0, "deduped_out": 0,
             "finbert_out": 0, "extracted": 0, "failed": 0}
    
    for article_meta in raw_articles:
        url = article_meta['url']
        if not url:
            continue
        
        # Step 1: Fetch HTML
        html = fetch_article_text(url)
        if not html:
            continue
        
        # Step 2: Clean
        text = clean_article(html)
        if not text:
            continue
        stats["cleaned"] += 1
        
        # Step 3: Deduplication check
        if not should_process(url, text):
            stats["deduped_out"] += 1
            continue
        
        headline = extract_headline(html)
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        
        # Insert into raw_articles
        cur.execute("""
            INSERT INTO raw_articles 
                (url_hash, url, headline, body_text, source_domain, publish_ts, gdelt_event_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url_hash) DO NOTHING
            RETURNING id
        """, (
            url_hash, url, headline, text,
            article_meta['source_domain'],
            article_meta['publish_ts'],
            article_meta['gdelt_event_id']
        ))
        
        result = cur.fetchone()
        if not result:
            continue    # Already existed
        raw_article_id = result[0]
        
        # Step 4: FinBERT filter
        if not should_extract(text):
            stats["finbert_out"] += 1
            conn.commit()
            continue
        
        # Step 5: GPT-4o-mini extraction
        event = extract_event(text)
        
        if event is None:
            # Route to dead letter queue
            cur.execute("""
                INSERT INTO dead_letter_queue (raw_article_id, failure_reason)
                VALUES (%s, %s)
            """, (raw_article_id, "GPT extraction failed after 3 retries"))
            stats["failed"] += 1
        else:
            # Store structured event
            cur.execute("""
                INSERT INTO structured_events
                    (raw_article_id, event_type, severity, india_exposure, confidence,
                     actors, locations, event_date, prompt_version, finbert_label, llm_raw_output)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s)
            """, (
                raw_article_id,
                event.event_type,
                event.severity,
                event.india_exposure,
                event.confidence,
                str(event.actors),   # Will store as JSONB
                str(event.locations),
                article_meta['publish_ts'].date(),
                PROMPT_VERSION,
                "negative",   # Only negatives reach here
                None          # llm_raw_output optional
            ))
            stats["extracted"] += 1
        
        conn.commit()
    
    cur.close()
    conn.close()
    
    logger.info(f"=== Cycle complete: {stats} ===")


if __name__ == "__main__":
    # Run once immediately, then schedule every 15 minutes
    run_ingestion_cycle()
    
    scheduler = BlockingScheduler()
    scheduler.add_job(run_ingestion_cycle, 'interval', minutes=15)
    
    logger.info("Scheduler started — running every 15 minutes")
    scheduler.start()
```

---

## Step 9 — Test the Full Pipeline End-to-End

Run a single ingestion cycle and verify data appears in PostgreSQL:

```bash
# From project root
python -m ingestion.pipeline

# Then check PostgreSQL
psql -U gpr_user -d india_gpr -c "SELECT COUNT(*) FROM raw_articles;"
psql -U gpr_user -d india_gpr -c "SELECT COUNT(*) FROM structured_events;"
psql -U gpr_user -d india_gpr -c "
  SELECT event_type, severity, india_exposure, confidence
  FROM structured_events 
  ORDER BY extracted_at DESC 
  LIMIT 5;
"
```

**Expected output after first run:**
- `raw_articles`: 50–200 rows
- `structured_events`: 10–50 rows (after FinBERT + GPT filtering)
- Severity scores should range 0.1 – 0.9
- India exposure should range 0.4 – 1.0 (since we pre-filter for India)

---

## Step 10 — Run in Docker

Create `ingestion/Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for lxml
RUN apt-get update && apt-get install -y \
    libxml2-dev libxslt-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download FinBERT model during build (bakes it into image)
RUN python -c "from transformers import pipeline; pipeline('text-classification', model='ProsusAI/finbert')"

COPY . .

CMD ["python", "-m", "ingestion.pipeline"]
```

```bash
# Build and test locally
docker build -t india-gpr-ingestion -f ingestion/Dockerfile .
docker run --env-file .env india-gpr-ingestion
```

---

## Verification Checklist

Before moving to Module 2, confirm all of the following:

- [ ] PostgreSQL has `raw_articles` rows being populated every 15 minutes
- [ ] `structured_events` has rows with severity, india_exposure, confidence all in [0, 1]
- [ ] `dead_letter_queue` has < 5% of raw articles (low failure rate)
- [ ] FinBERT is rejecting 50–70% of articles (check logs: "finbert_out" stat)
- [ ] GPT extraction is succeeding > 90% of the time
- [ ] No articles from the same URL appearing twice (dedup working)
- [ ] `prompt_version` column in structured_events is consistently "v1.3"
- [ ] `event_date` column matches the article's actual publication date (not ingestion date)

---

## Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `GDELT API returned 0 articles` | No India events in last 20 min | Normal during quiet periods; increase `minutes_back` to 60 for testing |
| `JSONDecodeError in GPT response` | GPT returned malformed JSON | Usually resolves with retry; if persistent, check prompt formatting |
| `FinBERT CUDA out of memory` | GPU too small for batch | Set `device=-1` to force CPU |
| `psycopg2.UniqueViolation` | Duplicate URL hash | Expected — handled by `ON CONFLICT DO NOTHING` |
| `requests.Timeout` | Article behind paywall/slow CDN | Handled — article skipped silently |
| `datasketch error: key already exists in LSH` | LSH not persisted between restarts | Normal on restart — LSH rebuilds from scratch each run |
