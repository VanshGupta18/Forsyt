"""Persistent model/version-aware cache for NLP extraction results."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .themes import MODEL_ID, SIMILARITY_THRESHOLD

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "tag_cache.sqlite"
EXTRACTOR_VERSION = (
    f"{MODEL_ID}@{SIMILARITY_THRESHOLD}"
    "|lexicon-tone-gcam-v1|fips-locations-v1"
)


@dataclass(frozen=True)
class CachedTag:
    v2themes: str
    tone_neg: float
    tone_polarity: float
    gcam: str = ""
    locations: str = ""
    tone_overall: float = 0.0


class TagCache:
    """SQLite cache keyed by extractor versions and bounded article text."""

    def __init__(self, db_path: Path = CACHE_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db_path)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tag_cache (
                    hash TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    v2themes TEXT NOT NULL DEFAULT '',
                    tone_neg REAL NOT NULL DEFAULT 0,
                    tone_polarity REAL NOT NULL DEFAULT 0,
                    gcam TEXT NOT NULL DEFAULT '',
                    locations TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tag_cache_model "
                "ON tag_cache(model_id)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _article_hash(article: dict[str, Any]) -> str:
        title = str(article.get("title") or "")[:200]
        body = str(article.get("body") or article.get("content") or "")[:4_000]
        raw = f"{EXTRACTOR_VERSION}|{title}|{body}"
        return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()

    def lookup(
        self,
        articles: list[dict[str, Any]],
    ) -> tuple[list[CachedTag | None], list[int]]:
        """Return result slots and indices requiring extraction."""
        if not articles:
            return [], []
        hashes = [self._article_hash(article) for article in articles]
        placeholders = ",".join("?" for _ in hashes)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT hash, v2themes, tone_neg, tone_polarity, gcam, locations "
                f"FROM tag_cache WHERE hash IN ({placeholders})",
                hashes,
            ).fetchall()
        by_hash = {row["hash"]: row for row in rows}
        results: list[CachedTag | None] = []
        misses: list[int] = []
        for index, article_hash in enumerate(hashes):
            row = by_hash.get(article_hash)
            if row is None:
                results.append(None)
                misses.append(index)
            else:
                results.append(CachedTag(
                    v2themes=row["v2themes"],
                    tone_neg=row["tone_neg"],
                    tone_polarity=row["tone_polarity"],
                    gcam=row["gcam"],
                    locations=row["locations"],
                ))
        return results, misses

    def store(
        self,
        articles: list[dict[str, Any]],
        tags: list[CachedTag],
    ) -> None:
        """Store extraction results corresponding to articles."""
        rows = [
            (
                self._article_hash(article),
                EXTRACTOR_VERSION,
                tag.v2themes,
                tag.tone_neg,
                tag.tone_polarity,
                tag.gcam,
                tag.locations,
            )
            for article, tag in zip(articles, tags)
        ]
        if not rows:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO tag_cache
                (hash, model_id, v2themes, tone_neg, tone_polarity, gcam, locations)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def stats(self) -> dict[str, Any]:
        with self._connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM tag_cache"
            ).fetchone()[0]
        return {"total_cached": total, "db_path": self._db_path}
