"""Persistent SQLite cache for DistilBERT theme+tone tagging results.

Key = sha256(MODEL_EMBED_ID + MODEL_TONE_ID + title[:200] + content[:4000])
Swapping either model automatically invalidates old entries.

Usage (called from theme_tagger.tag_batch — not directly):
  from scripts.tag_cache import TagCache
  cache = TagCache()
  hits, misses, miss_idxs = cache.lookup(articles)
  # run DistilBERT on misses only
  cache.store(miss_articles, miss_results)
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_REPO_ROOT  = Path(__file__).parent.parent
CACHE_PATH  = _REPO_ROOT / "data" / "india_archive" / "tag_cache.sqlite"

MODEL_EMBED_ID = "distiluse-base-multilingual-cased-v2"
MODEL_TONE_ID  = "distilbert-base-uncased-finetuned-sst-2-english"
_CACHE_KEY_PREFIX = f"{MODEL_EMBED_ID}||{MODEL_TONE_ID}||"


@dataclass
class CachedTag:
    v2themes:      str
    tone_neg:      float
    tone_overall:  float
    tone_polarity: float


class TagCache:
    def __init__(self, db_path: Path = CACHE_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db_path)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tag_cache (
                hash          TEXT PRIMARY KEY,
                model_id      TEXT NOT NULL,
                v2themes      TEXT NOT NULL DEFAULT '',
                tone_neg      REAL NOT NULL DEFAULT 0,
                tone_overall  REAL NOT NULL DEFAULT 0,
                tone_polarity REAL NOT NULL DEFAULT 0,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_model ON tag_cache(model_id)")
        conn.commit()
        conn.close()

    @staticmethod
    def _article_hash(art: dict) -> str:
        raw = _CACHE_KEY_PREFIX + art.get("title", "")[:200] + art.get("content", "")[:4000]
        return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()

    def lookup(
        self, articles: list[dict]
    ) -> tuple[list[Optional[CachedTag]], list[int]]:
        """Look up all articles. Returns (results_list, miss_indices).

        results_list[i] = CachedTag if hit, None if miss.
        miss_indices = [i for i where results_list[i] is None]
        """
        hashes = [self._article_hash(a) for a in articles]
        conn   = self._connect()

        # Batch select
        placeholders = ",".join("?" * len(hashes))
        rows = conn.execute(
            f"SELECT hash, v2themes, tone_neg, tone_overall, tone_polarity "
            f"FROM tag_cache WHERE hash IN ({placeholders})",
            hashes,
        ).fetchall()
        conn.close()

        row_map = {r["hash"]: r for r in rows}

        results: list[Optional[CachedTag]] = []
        miss_indices: list[int] = []
        for i, h in enumerate(hashes):
            if h in row_map:
                r = row_map[h]
                results.append(CachedTag(
                    v2themes=r["v2themes"],
                    tone_neg=r["tone_neg"],
                    tone_overall=r["tone_overall"],
                    tone_polarity=r["tone_polarity"],
                ))
            else:
                results.append(None)
                miss_indices.append(i)

        hit_count = len(articles) - len(miss_indices)
        if articles:
            logger.debug(f"[tag_cache] {hit_count}/{len(articles)} hits ({hit_count/len(articles)*100:.0f}%)")
        return results, miss_indices

    def store(self, articles: list[dict], tags: list) -> None:
        """Store tagging results for the given articles."""
        if not articles:
            return
        conn = self._connect()
        model_id = _CACHE_KEY_PREFIX
        for art, tag in zip(articles, tags):
            h = self._article_hash(art)
            conn.execute(
                "INSERT OR REPLACE INTO tag_cache "
                "(hash, model_id, v2themes, tone_neg, tone_overall, tone_polarity) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (h, model_id, tag.v2themes, tag.tone_neg, tag.tone_overall, tag.tone_polarity),
            )
        conn.commit()
        conn.close()

    def stats(self) -> dict:
        conn = self._connect()
        total = conn.execute("SELECT COUNT(*) FROM tag_cache").fetchone()[0]
        conn.close()
        return {"total_cached": total, "db_path": self._db_path}
