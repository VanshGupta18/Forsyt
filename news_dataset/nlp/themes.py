"""Semantic theme extraction using GPR taxonomy prototypes."""

from __future__ import annotations

from typing import Any

from gpr_index.scripts.taxonomy import TIER1_CODES, TIER2_CODES, TIER3_CODES

MODEL_ID = "sentence-transformers/distiluse-base-multilingual-cased-v2"
# Coverage-aware calibration on 234 canonical articles: 58 positive, score-shape PASS.
SIMILARITY_THRESHOLD = 0.34
MAX_CHARS = 4_000

ALL_CODES = [*TIER1_CODES, *TIER2_CODES, *TIER3_CODES]

CODE_DESCRIPTIONS = {
    "ARMEDCONFLICT": "armed conflict military war battle fighting troops killed airstrike",
    "TERROR_ATTACK": "terror attack bombing explosion blast suicide attack killed civilians",
    "INVASION": "invasion troops cross border military forces enter territory occupation",
    "COUP": "military coup overthrow government takeover power seized junta",
    "ETHNIC_VIOLENCE": "ethnic violence communal riots religious conflict massacre sectarian",
    "GENOCIDE": "genocide ethnic cleansing mass killing systematic murder atrocities",
    "NUCLEAR_WEAPONS": "nuclear weapon warhead atomic bomb detonation nuclear strike",
    "CHEMICAL_WEAPONS": "chemical weapon sarin chlorine gas attack nerve agent toxic",
    "BIOLOGICAL_WEAPONS": "biological weapon anthrax bioterrorism weaponized pathogen",
    "TERROR": "terrorism terrorist threat plot radicalization extremism",
    "TAX_FNCACT_MILITARY": "military forces army navy air force defence personnel",
    "TAX_FNCACT_SOLDIER": "soldier troops military personnel armed forces combat veteran",
    "TAX_FNCACT_REBEL": "rebel insurgent militant armed group guerrilla uprising resistance",
    "TAX_FNCACT_TERRORIST": "terrorist jihadist extremist bomber attacker radicalized",
    "SANCTION": "sanctions economic penalties trade restrictions embargo asset freeze",
    "NUCLEAR": "nuclear program enrichment reactor uranium plutonium proliferation",
    "DIPLOMATIC_CRISIS": "diplomatic crisis relations severed ambassador expelled tensions",
    "BLOCKADE": "blockade siege naval blockade supply cut access denied embargo",
    "BORDER_DISPUTE": "border dispute territorial claim Line of Control LAC skirmish",
    "MARITIME_DISPUTE": "maritime dispute territorial waters island claim naval standoff",
    "PROXY_WAR": "proxy war foreign-backed militia arms supply proxy conflict",
    "BALLISTIC_MISSILES": "ballistic missile launch ICBM test fire nuclear capable",
    "ESPIONAGE": "espionage spy intelligence leak classified surveillance covert",
    "CYBERATTACK": "cyberattack hacking ransomware data breach infrastructure attack",
    "WAR_CRIME": "war crime civilian target atrocity human rights violation torture",
}

_model: Any = None
_prototypes: Any = None


def _get_model() -> Any:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_ID)
    return _model


def _get_prototypes() -> Any:
    global _prototypes
    if _prototypes is None:
        _prototypes = _get_model().encode(
            [CODE_DESCRIPTIONS[code] for code in ALL_CODES],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
    return _prototypes


def theme_similarities(title: str, body: str) -> dict[str, float]:
    """Return one cosine similarity per GPR theme code."""
    text = f"{title or ''} {title or ''} {body or ''}"[:MAX_CHARS]
    if not text.strip():
        return {code: 0.0 for code in ALL_CODES}
    embedding = _get_model().encode(
        [text],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0]
    similarities = _get_prototypes() @ embedding
    return {
        code: float(similarity)
        for code, similarity in zip(ALL_CODES, similarities)
    }


def themes_at_threshold(
    similarities: dict[str, float],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[str]:
    """Return theme codes meeting a threshold from cached similarities."""
    return [
        code
        for code in ALL_CODES
        if similarities.get(code, 0.0) >= threshold
    ]


def extract_themes(
    title: str,
    body: str,
    *,
    similarities: dict[str, float] | None = None,
) -> list[str]:
    """Return every GPR theme whose prototype clears the production threshold."""
    return themes_at_threshold(
        similarities if similarities is not None else theme_similarities(title, body)
    )
