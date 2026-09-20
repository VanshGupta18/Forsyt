"""k-NN vector search over article embeddings, backed by OpenSearch.

What this adds that Postgres doesn't have:
    "Find coverage that means the same thing" — articles whose embedding sits
    near another article's, even with no shared words and no shared place tag.
    The keyword path in db.get_recent_news() (pg_trgm + delimited tag matching)
    stays exactly as it is; this is a second, different capability alongside
    it, not a replacement.

Why it's cheap:
    The vectors are already paid for. nlp/themes.py encodes every article once
    to score it against the theme prototypes; nlp/run_extraction.py now keeps
    that same vector (articles.nlp_embedding) instead of discarding it, and
    this module just ships it to an index. No second encode anywhere.

Optional by construction:
    Every function here is a no-op when OPENSEARCH_URL is unset — returns []
    or 0 rather than raising. That's the normal state for the GitHub Actions
    runners, a plain .venv and the API container, none of which have an
    OpenSearch to talk to. Only the Finch/Docker compose stack sets it.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

INDEX = os.environ.get("OPENSEARCH_INDEX", "forsyt-articles")
# distiluse-base-multilingual-cased-v2, the model nlp/themes.py loads. Changing
# MODEL_ID there changes this, and the index has to be recreated — a k-NN field's
# dimension is fixed at mapping time.
EMBEDDING_DIM = 512

_client: Any = None


def is_enabled() -> bool:
    return bool(os.environ.get("OPENSEARCH_URL", "").strip())


def _get_client() -> Any:
    """Lazily build the client. Import is inside the function because
    opensearch-py lives in requirements-ai.txt and isn't installed everywhere.
    """
    global _client
    if _client is None:
        from opensearchpy import OpenSearch

        _client = OpenSearch(
            hosts=[os.environ["OPENSEARCH_URL"]],
            http_compress=True,
            # Local single-node dev cluster in compose — no auth, no TLS.
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
        )
    return _client


def ensure_index() -> bool:
    """Create the k-NN index if missing. False if OpenSearch isn't configured."""
    if not is_enabled():
        return False
    client = _get_client()
    if client.indices.exists(index=INDEX):
        return True
    client.indices.create(
        index=INDEX,
        body={
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "article_id": {"type": "integer"},
                    "title": {"type": "text"},
                    "link": {"type": "keyword"},
                    "published": {"type": "date"},
                    "themes": {"type": "keyword"},
                    "locations": {"type": "keyword"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": EMBEDDING_DIM,
                        # Embeddings are L2-normalised (themes.py passes
                        # normalize_embeddings=True), so cosine and inner
                        # product rank identically; cosine keeps the score
                        # readable as a similarity.
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                        },
                    },
                }
            },
        },
    )
    logger.info("created OpenSearch index %s", INDEX)
    return True


def _to_vector(raw: Any) -> list[float] | None:
    """articles.nlp_embedding is REAL[], which psycopg2 hands back as a list of
    floats. A JSON string is tolerated too so rows written by any other path
    still index. Anything that isn't exactly EMBEDDING_DIM values is dropped
    rather than indexed at the wrong dimension, which OpenSearch would reject
    per-document mid-bulk.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    if not isinstance(raw, list) or len(raw) != EMBEDDING_DIM:
        return None
    return [float(x) for x in raw]


def index_articles(rows: list[dict]) -> int:
    """Bulk-index rows from db.get_articles_for_search_sync(). Returns the
    number indexed (0 when OpenSearch isn't configured).
    """
    if not is_enabled() or not rows:
        return 0
    from opensearchpy.helpers import bulk

    ensure_index()
    actions = []
    for row in rows:
        vector = _to_vector(row.get("nlp_embedding"))
        if vector is None:
            continue
        published = row.get("published_at") or row.get("scraped_at")
        actions.append(
            {
                "_index": INDEX,
                # Article id as the doc id makes the sync idempotent: re-running
                # a day overwrites rather than duplicating.
                "_id": str(row["id"]),
                "_source": {
                    "article_id": row["id"],
                    "title": row.get("title"),
                    "link": row.get("link"),
                    "published": published.isoformat() if hasattr(published, "isoformat") else published,
                    "themes": [t for t in (row.get("nlp_themes") or "").split(";") if t],
                    "locations": [p for p in (row.get("nlp_locations") or "").split(";") if p],
                    "embedding": vector,
                },
            }
        )
    if not actions:
        return 0
    indexed, _ = bulk(_get_client(), actions, refresh=True)
    return indexed


def _knn(vector: list[float], k: int, exclude_id: int | None) -> list[dict]:
    query: dict[str, Any] = {
        "size": k,
        "_source": ["article_id", "title", "link", "published", "themes"],
        "query": {"knn": {"embedding": {"vector": vector, "k": k + (1 if exclude_id else 0)}}},
    }
    hits = _get_client().search(index=INDEX, body=query)["hits"]["hits"]
    return [
        {
            "article_id": h["_source"]["article_id"],
            "title": h["_source"].get("title"),
            "link": h["_source"].get("link"),
            "published": h["_source"].get("published"),
            "themes": h["_source"].get("themes") or [],
            "score": h["_score"],
        }
        for h in hits
        if exclude_id is None or h["_source"]["article_id"] != exclude_id
    ][:k]


def related_articles(article_id: int, k: int = 5) -> list[dict]:
    """Nearest neighbours of an already-indexed article, excluding itself.

    Reads the stored vector straight out of the index rather than re-encoding
    the article — the whole point of persisting it. [] if OpenSearch isn't
    configured or the article was never indexed.
    """
    if not is_enabled():
        return []
    client = _get_client()
    try:
        doc = client.get(index=INDEX, id=str(article_id), _source=["embedding"])
    except Exception:
        return []
    vector = doc.get("_source", {}).get("embedding")
    if not vector:
        return []
    return _knn(vector, k, exclude_id=article_id)


def semantic_search(query_text: str, k: int = 5) -> list[dict]:
    """Nearest neighbours of ad-hoc text, embedded with the same model.

    For retrieval with no source article to compare against — see
    pipeline/explain_corridors.py, which uses a corridor's description to pull
    in coverage that never names the corridor's places.
    """
    if not is_enabled():
        return []
    from news_dataset.nlp.themes import embed_text

    vector = embed_text(query_text)
    if vector is None:
        return []
    return _knn([float(x) for x in vector], k, exclude_id=None)
