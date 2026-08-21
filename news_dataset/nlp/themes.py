"""Semantic theme extraction using GPR taxonomy prototypes.

Beginner note — what is a "sentence-transformer embedding"?
    A neural network model (MODEL_ID below) reads a piece of text and turns
    it into a list of a few hundred numbers (a "vector" or "embedding").
    Texts with similar MEANING end up with similar vectors, even if they
    don't share any exact words — e.g. "troops crossed the border" and
    "soldiers entered enemy territory" would land close together, because
    the model was trained on huge amounts of text to learn meaning, not just
    spelling. This is different from the keyword matching used elsewhere in
    this codebase (see ingestion/geo_pipeline.py's KEYWORDS) — no exact word
    has to match.

    How we use that here ("prototype" comparison):
    For every GPR theme code (ARMEDCONFLICT, TERROR_ATTACK, etc.) we wrote a
    short hand-picked description of what that theme looks like
    (CODE_DESCRIPTIONS below) and turned each description into its own
    embedding — its "prototype" vector. Then, for a real article, we embed
    its title+body text the same way and measure how close (cosine
    similarity, a number from -1 to 1) that article's vector is to each
    theme's prototype vector. If the similarity clears SIMILARITY_THRESHOLD
    (0.34), we say the article has that theme. An article can match zero,
    one, or several themes.
"""

from __future__ import annotations

from typing import Any

from gpr_index.scripts.taxonomy import TIER1_CODES, TIER2_CODES, TIER3_CODES

MODEL_ID = "sentence-transformers/distiluse-base-multilingual-cased-v2"
# Coverage-aware calibration on 234 canonical articles: 58 positive, score-shape PASS.
SIMILARITY_THRESHOLD = 0.34  # cosine-similarity cutoff (see module docstring) — tuned by nlp/calibrate.py, not something to hand-edit casually
MAX_CHARS = 4_000  # truncate very long articles before embedding — the model has a fixed input-size limit and longer text doesn't reliably improve results here

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
    """Return one cosine similarity per GPR theme code.

    Beginner note: the title is repeated twice in the text below (title +
    title + body) so the headline counts for a bit more than the body text
    when the model builds the embedding — a cheap way to weight the part of
    the article that's usually most on-topic. `_get_prototypes() @ embedding`
    is a matrix multiplication that computes the similarity between this
    one article's vector and every theme prototype's vector all in one
    step (much faster than comparing one at a time in a loop).
    """
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
    """Return theme codes meeting a threshold from cached similarities.

    Split out from extract_themes() so nlp/calibrate.py can re-use the same
    (expensive-to-compute) similarity scores while testing many different
    threshold values, instead of re-running the neural network every time.
    """
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
    """Return every GPR theme whose prototype clears the production threshold.

    This is the function the rest of the pipeline calls (see
    nlp/run_extraction.py): give it an article's title/body, get back a list
    of matched theme codes like ["ARMEDCONFLICT", "BORDER_DISPUTE"].
    """
    return themes_at_threshold(
        similarities if similarities is not None else theme_similarities(title, body)
    )
