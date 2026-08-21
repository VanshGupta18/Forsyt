"""Lexicon-density tone and GCAM extraction.

Beginner note — this is NOT a trained sentiment-analysis model.
    There's no neural network here, unlike nlp/themes.py. Instead, this
    module has two hand-written word lists (NEGATIVE_WORDS, POSITIVE_WORDS)
    and simply counts: "out of all the words in this article, what fraction
    are in the negative list? What fraction are in the positive list?" That
    fraction (times 100) is the "tone" score. It's simple, fast, has no
    external dependencies, and is easy for a human to audit (you can read
    every word in the list yourself) — the tradeoff is it can't understand
    context, sarcasm, or negation the way a trained model might.

    What is "GCAM emulation"?
    GDELT (the academic geopolitical-risk dataset this project is modeled
    on) publishes a "Global Content Analysis Measures" (GCAM) score per
    article, built from dozens of proprietary emotion/topic dictionaries.
    We don't have access to GDELT's exact dictionaries, so extract_gcam()
    below builds a similar-shaped output (four conflict-related dimensions,
    each a 0-1 density score) using our own small hand-picked word lists —
    "emulating" GCAM's output format and rough scale, not reproducing its
    exact lexicons.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

NEGATIVE_WORDS = frozenset({
    "abuse", "aggression", "angry", "attack", "atrocity", "bad", "ban",
    "battle", "betrayal", "blast", "blockade", "bomb", "casualty", "chaos",
    "clash", "conflict", "corrupt", "crisis", "damage", "danger", "dead",
    "death", "defeat", "destroy", "disaster", "dispute", "embargo", "enemy",
    "escalation", "expel", "explosion", "extremist", "fail", "fear", "fight",
    "fraud", "genocide", "grief", "hate", "hostile", "illegal", "injure",
    "invasion", "kill", "massacre", "militant", "missile", "murder", "nuclear",
    "outrage", "rebel", "riot", "risk", "sanction", "siege", "strike",
    "suffer", "terror", "terrorist", "threat", "torture", "toxic", "tragic",
    "unrest", "violence", "violent", "war", "weapon", "wound",
})

POSITIVE_WORDS = frozenset({
    "accord", "agreement", "ally", "approve", "ceasefire", "cooperate",
    "cooperation", "diplomacy", "friend", "gain", "good", "hope", "improve",
    "peace", "peaceful", "progress", "protect", "reconcile", "recover",
    "relief", "resolve", "safe", "secure", "stability", "success", "support",
    "truce", "victory", "welcome",
})

_GCAM_LEXICONS = {
    "c18.1": frozenset({
        "battle", "blockade", "clash", "conflict", "coup", "dispute",
        "invasion", "military", "rebel", "sanction", "siege", "soldier",
        "troop", "war",
    }),
    "c18.2": frozenset({
        "alarm", "danger", "escalation", "fear", "hostage", "missile",
        "nuclear", "risk", "terror", "terrorist", "threat", "weapon",
    }),
    "c18.3": frozenset({
        "airstrike", "attack", "blast", "bomb", "destroy", "explosion",
        "fight", "genocide", "kill", "massacre", "murder", "strike",
        "torture", "violence", "violent",
    }),
    "c9.1": frozenset({
        "aggression", "angry", "condemn", "enemy", "fury", "hate",
        "hostile", "outrage", "rage", "retaliation", "revenge",
    }),
}

# Short RSS summaries need a slightly lower reference density to reach GDELT GCAM levels.
_GCAM_REFERENCE_DENSITY = 0.04


def _words(text: str) -> list[str]:
    return [word.lower() for word in _WORD_RE.findall(text or "")]


def extract_tone(text: str) -> tuple[float, float]:
    """Return (negative density, tonal density), each as a 0-100 percentage.

    "negative density" = what % of all words are in NEGATIVE_WORDS.
    "tonal density" = what % of all words are in EITHER word list (negative
    or positive) — i.e. how emotionally/conflict-charged the text is overall,
    regardless of which direction. Both are plain word counts, no weighting.
    """
    words = _words(text)
    if not words:
        return 0.0, 0.0
    negative = sum(word in NEGATIVE_WORDS for word in words)
    positive = sum(word in POSITIVE_WORDS for word in words)
    denominator = len(words)
    return (
        round(100.0 * negative / denominator, 3),
        round(100.0 * (negative + positive) / denominator, 3),
    )


def extract_gcam(text: str) -> str:
    """Return four conflict dimensions in GDELT's GCAM key:value format.

    Each of the four dimensions (c18.1 = "conflict/military", c18.2 =
    "danger/threat", c18.3 = "violence/attack", c9.1 = "hostility/anger" —
    see _GCAM_LEXICONS above for the exact word lists) is scored as: how many
    words from that dimension's list appear, divided by a reference density
    (_GCAM_REFERENCE_DENSITY) meant to land typical GDELT-scale articles
    around a comparable 0-1 range, capped at 1.0. The result is serialized as
    a comma-separated "key:value" string because that's the plain-text format
    GDELT itself uses for GCAM columns, which keeps this dataset compatible
    with the same downstream GPR-scoring code GDELT data uses.
    """
    words = _words(text)
    if not words:
        values = {dimension: 0.0 for dimension in _GCAM_LEXICONS}
    else:
        denominator = len(words) * _GCAM_REFERENCE_DENSITY
        values = {
            dimension: min(1.0, sum(word in lexicon for word in words) / denominator)
            for dimension, lexicon in _GCAM_LEXICONS.items()
        }
    return ",".join(
        f"{dimension}:{values[dimension]:.3f}"
        for dimension in ("c18.1", "c18.2", "c18.3", "c9.1")
    )
