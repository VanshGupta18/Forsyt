"""Lexicon-density tone and GCAM extraction."""

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
    """Return (negative density, tonal density), each as a 0-100 percentage."""
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
    """Return four conflict dimensions in GDELT's GCAM key:value format."""
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
