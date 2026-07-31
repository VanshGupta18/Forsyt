"""Calibrate scraped-news NLP fields against GDELT GPR score distributions."""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from news_dataset.nlp.themes import (
    SIMILARITY_THRESHOLD,
    TIER1_CODES,
    TIER2_CODES,
    TIER3_CODES,
    extract_themes,
    theme_similarities,
    themes_at_threshold,
)
from news_dataset.nlp.tone import extract_gcam, extract_tone

TARGETS = {
    "theme_score median": (0.30, 0.40, 0.3333),
    "theme_score mean": (0.35, 0.45, 0.4048),
    "tone_score mean": (0.03, 0.08, 0.0517),
    "gcam_score mean": (0.14, 0.20, 0.18),
    "score share in (0, 0.20]": (0.0, 0.02, 0.0),
}
TIERS = {
    "tier1": frozenset(TIER1_CODES),
    "tier2": frozenset(TIER2_CODES),
    "tier3": frozenset(TIER3_CODES),
}


def _score_articles() -> Callable[[pd.DataFrame], pd.DataFrame]:
    """Import the validated scorer with its expected top-level scripts package."""
    gpr_root = Path(__file__).resolve().parents[2] / "gpr_index"
    root = str(gpr_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    from scripts.gkg_gpr_pipeline import score_articles

    return score_articles


def _load_articles(limit: int) -> list[dict[str, Any]]:
    from news_dataset.db import get_gpr_articles

    articles = get_gpr_articles(datetime.min, datetime.max)
    return articles[-limit:]


def _extract(
    articles: list[dict[str, Any]],
    keep_similarities: bool,
) -> tuple[pd.DataFrame, list[dict[str, float]]]:
    rows: list[dict[str, Any]] = []
    all_similarities: list[dict[str, float]] = []
    for article in articles:
        title = str(article.get("title") or "")
        body = str(article.get("content") or "")
        text = f"{title}\n{body}".strip()
        similarities = theme_similarities(title, body) if keep_similarities else None
        themes = extract_themes(title, body, similarities=similarities)
        tone_neg, tone_polarity = extract_tone(text)
        rows.append({
            "V2Themes": ";".join(themes),
            "tone_neg": tone_neg,
            "tone_polarity": tone_polarity,
            "GCAM": extract_gcam(text),
        })
        if similarities is not None:
            all_similarities.append(similarities)
    return pd.DataFrame(rows), all_similarities


def _actual_metrics(scored: pd.DataFrame) -> dict[str, float]:
    positive = scored[scored["gpr_score"] > 0]
    return {
        "theme_score median": float(positive["theme_score"].median()),
        "theme_score mean": float(positive["theme_score"].mean()),
        "tone_score mean": float(positive["tone_score"].mean()),
        "gcam_score mean": float(positive["gcam_score"].mean()),
        "score share in (0, 0.20]": float(
            ((scored["gpr_score"] > 0) & (scored["gpr_score"] <= 0.20)).mean()
        ),
    }


def _in_range(value: float, low: float, high: float) -> bool:
    return math.isfinite(value) and low <= value <= high


def _print_metrics(scored: pd.DataFrame) -> None:
    actual = _actual_metrics(scored)
    print("\n--- Calibration metrics (component metrics use gpr_score > 0) ---")
    print(f"{'metric':34} {'actual':>9} {'GDELT':>9} {'pass range':>13}  result")
    for name, value in actual.items():
        low, high, reference = TARGETS[name]
        is_share = name.startswith("score share")
        target = f"{low:.2f}-{high:.2f}" if not is_share else f"< {high:.2%}"
        shown = f"{value:.2%}" if is_share else f"{value:.4f}"
        gdelt = f"{reference:.2%}" if is_share else f"{reference:.4f}"
        passed = math.isfinite(value) and (
            value < high if is_share else low <= value <= high
        )
        print(
            f"{name:34} {shown:>9} {gdelt:>9} {target:>13}  "
            f"{'PASS' if passed else 'FAIL'}"
        )


def _theme_tokens(raw: str) -> set[str]:
    return {token.strip().upper() for token in raw.split(";") if token.strip()}


def _theme_article_counts(themes: pd.Series) -> tuple[int, Counter[str]]:
    tier_articles: Counter[str] = Counter()
    any_articles = 0
    for raw in themes.fillna("").astype(str):
        tokens = _theme_tokens(raw)
        matched_any = False
        for tier, codes in TIERS.items():
            if tokens & codes:
                tier_articles[tier] += 1
                matched_any = True
        any_articles += matched_any
    return any_articles, tier_articles


def _warn_if_low_theme_coverage(count: int, total: int) -> None:
    share = count / total if total else 0.0
    if count < 30 or share < 0.10:
        print(
            "WARNING: fewer than 30 theme-positive articles survive or "
            "theme-positive share is below 10%; this sample cannot justify "
            "a production threshold change."
        )


def _print_theme_hits(themes: pd.Series) -> None:
    total = len(themes)
    counts: Counter[tuple[str, str]] = Counter()
    any_articles, tier_articles = _theme_article_counts(themes)
    for raw in themes.fillna("").astype(str):
        tokens = _theme_tokens(raw)
        for tier, codes in TIERS.items():
            hits = tokens & codes
            counts.update((tier, code) for code in hits)

    print("\n--- Theme hit rates (all sampled articles) ---")
    for tier in TIERS:
        print(f"{tier:6} {tier_articles[tier]:5}/{total:<5} {tier_articles[tier] / total:7.2%}")
    print(f"{'any':6} {any_articles:5}/{total:<5} {any_articles / total:7.2%}")
    _warn_if_low_theme_coverage(any_articles, total)
    print("\n--- Top matched theme codes ---")
    if not counts:
        print("none")
    for (tier, code), count in counts.most_common(15):
        print(f"{tier:6} {code:30} {count:5}  {count / total:7.2%}")


def _thresholds(start: float, stop: float, step: float) -> list[float]:
    count = int(math.floor((stop - start) / step + 1e-9))
    return [round(start + index * step, 6) for index in range(count + 1)]


def _sweep(
    frame: pd.DataFrame,
    similarities: list[dict[str, float]],
    score_articles: Callable[[pd.DataFrame], pd.DataFrame],
    start: float,
    stop: float,
    step: float,
) -> None:
    candidates = []
    total = len(frame)
    for threshold in _thresholds(start, stop, step):
        candidate = frame.copy()
        candidate["V2Themes"] = [
            ";".join(themes_at_threshold(values, threshold))
            for values in similarities
        ]
        metrics = _actual_metrics(score_articles(candidate))
        median = metrics["theme_score median"]
        mean = metrics["theme_score mean"]
        positive_count, tier_counts = _theme_article_counts(candidate["V2Themes"])
        passed = (
            _in_range(median, *TARGETS["theme_score median"][:2])
            and _in_range(mean, *TARGETS["theme_score mean"][:2])
        )
        candidates.append(
            (threshold, median, mean, positive_count, tier_counts, passed)
        )

    print("\n--- Theme threshold sweep (embeddings reused) ---")
    print(
        f"{'threshold':>9} {'median':>9} {'mean':>9} "
        f"{'positive':>10} {'share':>8} "
        f"{'tier1':>8} {'tier2':>8} {'tier3':>8}  shape"
    )
    for threshold, median, mean, positive_count, tier_counts, passed in candidates:
        print(
            f"{threshold:9.3f} {median:9.4f} {mean:9.4f} "
            f"{positive_count:10d} {positive_count / total:8.2%} "
            f"{tier_counts['tier1'] / total:8.2%} "
            f"{tier_counts['tier2'] / total:8.2%} "
            f"{tier_counts['tier3'] / total:8.2%}  "
            f"{'PASS' if passed else 'FAIL'}"
        )

    low_coverage = [
        f"{threshold:.3f}"
        for threshold, _, _, positive_count, _, _ in candidates
        if positive_count < 30 or positive_count / total < 0.10
    ]
    if low_coverage:
        print(
            "WARNING: thresholds "
            + ", ".join(low_coverage)
            + " leave fewer than 30 theme-positive articles or below 10% "
            "theme-positive share; those samples cannot justify a production "
            "threshold change."
        )

    print(
        "\nCoverage-aware rule: among thresholds passing both conditional "
        "theme-score shape ranges, choose the highest theme-positive article "
        "coverage; ties choose the lower threshold."
    )
    passing = [candidate for candidate in candidates if candidate[5]]
    if passing:
        best = max(passing, key=lambda candidate: (candidate[3], -candidate[0]))
        print(
            f"coverage-aware candidate: {best[0]:.3f} "
            f"(theme-positive={best[3]}/{total}, {best[3] / total:.2%}; "
            f"theme median={best[1]:.4f}, mean={best[2]:.4f})"
        )
        _warn_if_low_theme_coverage(best[3], total)
    else:
        print("No coverage-aware candidate: no threshold passed both shape ranges.")
    print(f"Production threshold remains unchanged at {SIMILARITY_THRESHOLD:.3f}.")
    if len(frame) < 100:
        print("WARNING: sample is too small to support a production threshold change.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=500, help="GPR articles (default: 500)")
    parser.add_argument("--sweep", action="store_true", help="sweep theme similarity thresholds")
    parser.add_argument("--sweep-min", type=float, default=0.34)
    parser.add_argument("--sweep-max", type=float, default=0.50)
    parser.add_argument("--sweep-step", type=float, default=0.02)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")
    if not 0 <= args.sweep_min <= args.sweep_max <= 1:
        parser.error("sweep bounds must satisfy 0 <= min <= max <= 1")
    if args.sweep_step <= 0:
        parser.error("--sweep-step must be positive")

    articles = _load_articles(args.limit)
    if not articles:
        parser.error("no NLP-complete GPR articles found")
    print(f"Loaded {len(articles):,} GPR articles (limit {args.limit:,}).")

    frame, similarities = _extract(articles, keep_similarities=args.sweep)
    score_articles = _score_articles()
    scored = score_articles(frame)
    _print_metrics(scored)
    _print_theme_hits(frame["V2Themes"])
    if args.sweep:
        _sweep(
            frame,
            similarities,
            score_articles,
            args.sweep_min,
            args.sweep_max,
            args.sweep_step,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
