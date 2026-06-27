"""DistilBERT-based theme + tone tagger for Indian news articles.

Produces the synthetic fields that score_articles() needs:
  V2Themes  — semicolon-separated GDELT-style theme codes (TIER1/2/3)
  tone_neg  — negative tone on GKG scale (0–30; >5 required to contribute)
  tone_overall — signed overall tone
  tone_polarity — polarity (0–1)

Theme assignment:
  Uses sentence-transformers/distiluse-base-multilingual-cased-v2 to embed
  (title × 2 + body) and compare against prototype embeddings for each
  TIER1/2/3 code. Codes whose cosine similarity exceeds SIMILARITY_THRESHOLD
  are emitted. Model loaded once at import time (lazy on first call).

Tone assignment:
  Uses distilbert-base-uncased-finetuned-sst-2-english (binary sentiment).
  negative_prob × TONE_SCALE → tone_neg.
  TONE_SCALE calibrated so mean tone_neg ≈ 3–5 on neutral days.

Usage as module:
  from scripts.theme_tagger import tag_article
  result = tag_article(title="...", body="...")
  # result.v2themes  -> "ARMEDCONFLICT;BORDER_DISPUTE"
  # result.tone_neg  -> 7.3

Usage as CLI (calibration / batch):
  python -m scripts.theme_tagger --calibrate   (run on 500 sample articles)
  python -m scripts.theme_tagger --batch input.jsonl.gz output.jsonl.gz
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TIER taxonomy (must mirror gkg_gpr_pipeline.py exactly)
# ---------------------------------------------------------------------------

TIER1_CODES: list[str] = [
    "ARMEDCONFLICT", "TERROR_ATTACK", "INVASION", "COUP",
    "ETHNIC_VIOLENCE", "GENOCIDE", "NUCLEAR_WEAPONS",
    "CHEMICAL_WEAPONS", "BIOLOGICAL_WEAPONS",
]
TIER2_CODES: list[str] = [
    "TERROR", "TAX_FNCACT_MILITARY", "TAX_FNCACT_SOLDIER", "TAX_FNCACT_REBEL",
    "TAX_FNCACT_TERRORIST", "SANCTION", "NUCLEAR", "DIPLOMATIC_CRISIS",
    "BLOCKADE", "BORDER_DISPUTE", "MARITIME_DISPUTE", "PROXY_WAR",
    "BALLISTIC_MISSILES",
]
TIER3_CODES: list[str] = [
    "ESPIONAGE", "CYBERATTACK", "WAR_CRIME",
]

ALL_CODES: list[str] = TIER1_CODES + TIER2_CODES + TIER3_CODES

# Prototype phrases describing each theme code (used to build embedding prototypes)
CODE_DESCRIPTIONS: dict[str, str] = {
    "ARMEDCONFLICT":      "armed conflict military war battle fighting troops killed airstrike",
    "TERROR_ATTACK":      "terror attack bombing explosion blast suicide attack killed civilians",
    "INVASION":           "invasion troops cross border military forces enter territory occupation",
    "COUP":               "military coup overthrow government takeover power seized junta",
    "ETHNIC_VIOLENCE":    "ethnic violence communal riots religious conflict massacre sectarian",
    "GENOCIDE":           "genocide ethnic cleansing mass killing systematic murder atrocities",
    "NUCLEAR_WEAPONS":    "nuclear weapon warhead atomic bomb detonation nuclear strike",
    "CHEMICAL_WEAPONS":   "chemical weapon sarin chlorine gas attack nerve agent toxic",
    "BIOLOGICAL_WEAPONS": "biological weapon anthrax bioterrorism pandemic weaponized pathogen",
    "TERROR":             "terrorism terrorist threat threat plot radicalization extremism",
    "TAX_FNCACT_MILITARY":"military forces army navy airforce defence personnel soldiers",
    "TAX_FNCACT_SOLDIER": "soldier troops military personnel armed forces combat veteran",
    "TAX_FNCACT_REBEL":   "rebel insurgent militant armed group guerrilla uprising resistance",
    "TAX_FNCACT_TERRORIST":"terrorist jihadist extremist bomber attacker radicalized",
    "SANCTION":           "sanctions economic penalties trade restrictions embargo asset freeze",
    "NUCLEAR":            "nuclear program enrichment reactor uranium plutonium proliferation",
    "DIPLOMATIC_CRISIS":  "diplomatic crisis relations severed ambassador expelled tensions",
    "BLOCKADE":           "blockade siege naval blockade supply cut access denied embargo",
    "BORDER_DISPUTE":     "border dispute territorial claim Line of Control LAC skirmish",
    "MARITIME_DISPUTE":   "maritime dispute South China Sea territorial waters island claim",
    "PROXY_WAR":          "proxy war foreign-backed militia arms supply proxy conflict",
    "BALLISTIC_MISSILES": "ballistic missile launch ICBM test fire range nuclear capable",
    "ESPIONAGE":          "espionage spy intelligence leak classified surveillance covert",
    "CYBERATTACK":        "cyberattack hacking ransomware data breach infrastructure attack",
    "WAR_CRIME":          "war crime civilian target atrocity human rights violation torture",
}

# Similarity threshold: cosine similarity above which a code is assigned
SIMILARITY_THRESHOLD = 0.42

# Tone scale: negative_prob × TONE_SCALE = tone_neg
# Calibrated so mean tone_neg ≈ 4.0 on neutral articles.
# This constant is adjusted by --calibrate.
TONE_SCALE = 16.0

# Max tokens for embedding (truncate long bodies)
MAX_CHARS = 4000


# ---------------------------------------------------------------------------
# Lazy model loading
# ---------------------------------------------------------------------------

_embed_model = None
_tone_pipeline = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        logger.info("[tagger] Loading sentence-transformers model …")
        _embed_model = SentenceTransformer(
            "sentence-transformers/distiluse-base-multilingual-cased-v2"
        )
    return _embed_model


def _get_tone_pipeline():
    global _tone_pipeline
    if _tone_pipeline is None:
        from transformers import pipeline  # noqa: PLC0415
        logger.info("[tagger] Loading DistilBERT sentiment model …")
        _tone_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            truncation=True,
            max_length=512,
        )
    return _tone_pipeline


# ---------------------------------------------------------------------------
# Prototype embeddings (built once per process)
# ---------------------------------------------------------------------------

_prototype_embeddings: Optional[np.ndarray] = None


def _get_prototypes() -> np.ndarray:
    """Return (N_codes, embed_dim) prototype matrix."""
    global _prototype_embeddings
    if _prototype_embeddings is None:
        model = _get_embed_model()
        phrases = [CODE_DESCRIPTIONS[c] for c in ALL_CODES]
        _prototype_embeddings = model.encode(phrases, convert_to_numpy=True, normalize_embeddings=True)
    return _prototype_embeddings


# ---------------------------------------------------------------------------
# Core tagging
# ---------------------------------------------------------------------------

@dataclass
class TagResult:
    v2themes: str = ""
    tone_neg: float = 0.0
    tone_overall: float = 0.0
    tone_polarity: float = 0.0
    matched_codes: list[str] = field(default_factory=list)
    similarities: dict[str, float] = field(default_factory=dict)


def tag_article(
    title: str,
    body: str,
    tone_scale: float = TONE_SCALE,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> TagResult:
    """Tag a single article with themes and tone. Models loaded on first call."""
    # Build text for embedding: title twice (2× weight) + body (truncated)
    text_for_embed = f"{title} {title} {body}"[:MAX_CHARS]
    # Shorter text for tone (transformer limited to ~512 tokens)
    text_for_tone = f"{title}. {body}"[:1024]

    model = _get_embed_model()
    art_embedding = model.encode([text_for_embed], convert_to_numpy=True, normalize_embeddings=True)[0]

    prototypes = _get_prototypes()
    sims = (prototypes @ art_embedding).tolist()  # cosine sims for all codes

    matched: list[str] = []
    sim_map: dict[str, float] = {}
    for code, sim in zip(ALL_CODES, sims):
        sim_map[code] = round(sim, 3)
        if sim >= similarity_threshold:
            matched.append(code)

    # Tone via DistilBERT sentiment
    tone_pipe = _get_tone_pipeline()
    result = tone_pipe(text_for_tone[:512])[0]
    label = result["label"]     # "POSITIVE" or "NEGATIVE"
    score = result["score"]     # confidence 0-1

    # negative_prob: if label is NEGATIVE, score; else 1-score
    negative_prob = score if label == "NEGATIVE" else (1.0 - score)
    raw_tone_neg = float(negative_prob * tone_scale)

    # tone_overall: positive = positive, negative = negative (matching GKG sign)
    positive_prob = 1.0 - negative_prob
    tone_overall  = float((positive_prob - negative_prob) * 10.0)
    tone_polarity = float(abs(positive_prob - negative_prob))

    return TagResult(
        v2themes=";".join(matched),
        tone_neg=round(raw_tone_neg, 3),
        tone_overall=round(tone_overall, 3),
        tone_polarity=round(tone_polarity, 3),
        matched_codes=matched,
        similarities=sim_map,
    )


def _run_distilbert(articles: list[dict], tone_scale: float) -> list[TagResult]:
    """Run DistilBERT on articles (no cache). Internal helper."""
    texts_embed = [
        f"{a.get('title', '')} {a.get('title', '')} {a.get('content', '')}"[:MAX_CHARS]
        for a in articles
    ]
    texts_tone = [
        f"{a.get('title', '')}. {a.get('content', '')}"[:1024]
        for a in articles
    ]

    model      = _get_embed_model()
    embeddings = model.encode(texts_embed, convert_to_numpy=True, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
    prototypes = _get_prototypes()
    sims_matrix = embeddings @ prototypes.T

    tone_pipe    = _get_tone_pipeline()
    tone_results = tone_pipe(texts_tone, batch_size=32, truncation=True, max_length=512)

    results: list[TagResult] = []
    for art, sims_row, t_res in zip(articles, sims_matrix, tone_results):
        matched  = [c for c, s in zip(ALL_CODES, sims_row.tolist()) if s >= SIMILARITY_THRESHOLD]
        neg_prob = t_res["score"] if t_res["label"] == "NEGATIVE" else (1.0 - t_res["score"])
        pos_prob = 1.0 - neg_prob
        results.append(TagResult(
            v2themes=";".join(matched),
            tone_neg=round(float(neg_prob * tone_scale), 3),
            tone_overall=round(float((pos_prob - neg_prob) * 10.0), 3),
            tone_polarity=round(float(abs(pos_prob - neg_prob)), 3),
            matched_codes=matched,
        ))
    return results


def tag_batch(
    articles: list[dict],
    tone_scale: float = TONE_SCALE,
    use_cache: bool = True,
) -> list[TagResult]:
    """Tag a batch of article dicts, consulting the persistent tag cache first.

    Only cache-miss articles are sent through DistilBERT, making re-runs of the
    full Jan-Jun backfill ~10 min instead of ~10h after the first pass.

    Set use_cache=False to bypass (e.g. during calibration).
    """
    if not articles:
        return []

    if not use_cache:
        return _run_distilbert(articles, tone_scale)

    from scripts.tag_cache import TagCache  # noqa: PLC0415
    cache = TagCache()

    cached_tags, miss_indices = cache.lookup(articles)

    # Run model only on cache misses
    miss_articles = [articles[i] for i in miss_indices]
    miss_results: list[TagResult] = []
    if miss_articles:
        logger.info(f"[tag_batch] {len(miss_articles)} cache misses — running DistilBERT …")
        miss_results = _run_distilbert(miss_articles, tone_scale)
        cache.store(miss_articles, miss_results)

    # Merge: fill in miss results at their original positions
    miss_iter = iter(miss_results)
    final: list[TagResult] = []
    for i, cached in enumerate(cached_tags):
        if cached is not None:
            final.append(TagResult(
                v2themes=cached.v2themes,
                tone_neg=cached.tone_neg,
                tone_overall=cached.tone_overall,
                tone_polarity=cached.tone_polarity,
            ))
        else:
            final.append(next(miss_iter))
    return final


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def calibrate(sample_jsonl_gz: Path, n: int = 500) -> float:
    """Compute mean tone_neg on n neutral (non-GPR-positive) articles.

    A good calibration produces mean ≈ 3–5 which is the GKG baseline.
    Returns the recommended TONE_SCALE adjustment factor.
    """
    articles: list[dict] = []
    with gzip.open(sample_jsonl_gz, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                articles.append(json.loads(line))
            except json.JSONDecodeError:
                pass
            if len(articles) >= n:
                break

    if not articles:
        print("[calibrate] No articles found in sample file")
        return TONE_SCALE

    results = tag_batch(articles, use_cache=False)
    tone_negs = [r.tone_neg for r in results]
    mean_neg = sum(tone_negs) / len(tone_negs)
    target = 4.0  # midpoint of 3-5 target range

    new_scale = TONE_SCALE * (target / mean_neg) if mean_neg > 0 else TONE_SCALE

    print(f"\n[calibrate] n={len(articles)}")
    print(f"  TONE_SCALE current : {TONE_SCALE}")
    print(f"  Mean tone_neg (raw): {mean_neg:.3f}")
    print(f"  Target mean        : {target}")
    print(f"  Recommended scale  : {new_scale:.2f}")
    print(f"\n  Positive theme hit rate: {sum(1 for r in results if r.matched_codes) / len(results) * 100:.1f}%")
    print(f"  Top matched codes: {_top_codes(results)}")

    return new_scale


def _top_codes(results: list[TagResult], top_n: int = 10) -> list[tuple[str, int]]:
    from collections import Counter  # noqa: PLC0415
    c: Counter = Counter()
    for r in results:
        for code in r.matched_codes:
            c[code] += 1
    return c.most_common(top_n)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DistilBERT theme+tone tagger")
    sub = p.add_subparsers(dest="cmd")

    cal = sub.add_parser("calibrate", help="Calibrate tone scale on sample JSONL")
    cal.add_argument("sample", help="Path to india_raw/YYYY-MM-DD.jsonl.gz")
    cal.add_argument("--n", type=int, default=500, help="Number of articles to sample")

    bat = sub.add_parser("batch", help="Tag articles in a JSONL file")
    bat.add_argument("input",  help="Input .jsonl.gz")
    bat.add_argument("output", help="Output .jsonl.gz with v2themes/tone_neg added")

    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    args = parse_args()

    if args.cmd == "calibrate":
        calibrate(Path(args.sample), n=args.n)

    elif args.cmd == "batch":
        inp = Path(args.input)
        out = Path(args.output)
        articles: list[dict] = []
        with gzip.open(inp, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        articles.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        print(f"[batch] Tagging {len(articles)} articles …")
        results = tag_batch(articles)
        with gzip.open(out, "wt", encoding="utf-8") as f:
            for art, res in zip(articles, results):
                art["v2themes_tagged"]   = res.v2themes
                art["tone_neg_tagged"]   = res.tone_neg
                art["tone_overall_tag"]  = res.tone_overall
                art["tone_polarity_tag"] = res.tone_polarity
                f.write(json.dumps(art, ensure_ascii=False) + "\n")
        print(f"[batch] Done → {out}")
    else:
        print("Use: python -m scripts.theme_tagger calibrate <file.jsonl.gz>")
        print("     python -m scripts.theme_tagger batch <in.jsonl.gz> <out.jsonl.gz>")


if __name__ == "__main__":
    main()
