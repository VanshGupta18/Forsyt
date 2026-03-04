"""
Stage 1 LLM filter: FinBERT sentiment classifier.
Rejects positive/neutral articles before the expensive GPT-4o-mini call.

Model: ProsusAI/finbert (HuggingFace)
Input: first 512 tokens of article text
Output: positive | negative | neutral
"""

import logging
from typing import Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# Lazy-loaded model (loaded once on first call, not at import)
_pipeline = None


def _get_pipeline():
    """Load FinBERT model lazily. Baked into Docker image at build time."""
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline
        logger.info("Loading ProsusAI/finbert model (first run only)...")
        _pipeline = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            device=-1,           # CPU inference
            top_k=None,          # Return all 3 label scores
        )
        logger.info("FinBERT loaded")
    return _pipeline


def classify_sentiment(text: str) -> Tuple[str, float]:
    """
    Classify article sentiment with FinBERT.

    Args:
        text: Article text (truncated to 512 tokens internally)

    Returns:
        (label, confidence) where label is 'positive', 'negative', or 'neutral'
    """
    pipe = _get_pipeline()

    # FinBERT handles 512-token limit internally; truncation is automatic
    try:
        results = pipe(text[:2048], truncation=True, max_length=512)[0]
        # results is a list of {'label': ..., 'score': ...}
        best = max(results, key=lambda x: x["score"])
        return best["label"].lower(), round(best["score"], 4)
    except Exception as e:
        logger.warning(f"FinBERT classification failed: {e}")
        # On failure, pass through to GPT (conservative default)
        return "negative", 0.5


def should_extract(text: str) -> Tuple[bool, str, float]:
    """
    Decide whether to route article to GPT-4o-mini extraction.

    Routing rules:
    - 'negative' → proceed to Stage 2 (regardless of confidence)
    - 'positive' or 'neutral' with confidence > 0.70 → discard
    - 'positive' or 'neutral' with low confidence (< 0.70) → proceed
      (borderline cases pass through to avoid false negatives on risk events)

    Returns:
        (should_extract: bool, label: str, confidence: float)
    """
    label, confidence = classify_sentiment(text)

    if label == "negative":
        return True, label, confidence

    if confidence >= 0.70:
        # High-confidence non-negative → safe to discard
        return False, label, confidence

    # Low-confidence → pass through (risk of false negative too high)
    logger.debug(f"Low-confidence {label} ({confidence:.2f}) — passing to GPT as precaution")
    return True, label, confidence
