"""Daily job: a short natural-language explanation of each corridor's risk
score, generated once per day by a local LLM (via the Strands Agents SDK +
Ollama) and stored in Postgres — not served live.

Beginner note — why this is a batch job, not a live API endpoint:
    Running LLM inference needs either a paid always-on server, or, here, a
    fresh Ollama pull on the GitHub Actions runner for the few minutes this
    takes once a day (see .github/workflows/daily_index.yml). The Flask API
    only ever reads what this script already wrote (see api/server.py's
    GET /api/corridor/<id>/explanation) — no inference happens at request
    time, so there is nothing here that needs an always-on server.

Run standalone: python -m news_dataset.pipeline.explain_corridors
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strands import Agent  # noqa: E402
from strands.models.ollama import OllamaModel  # noqa: E402

from gpr_index.scripts.corridors import CORRIDOR_PLACES  # noqa: E402
from news_dataset import db  # noqa: E402

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL_ID = os.environ.get("OLLAMA_MODEL_ID", "qwen2.5:7b-instruct")
ARTICLES_PER_CORRIDOR = 5

SYSTEM_PROMPT = (
    "You are a geopolitical risk analyst. Given a trade corridor's risk "
    "score and a handful of related recent headlines, write a 2-4 sentence "
    "explanation of why the risk score is where it is today. Reference the "
    "actual headlines given, not generic geopolitics commentary. Do not "
    "invent facts that are not present in the input. If no headlines are "
    "given, say the score reflects the absence of recent corridor-specific "
    "news rather than guessing at a cause."
)


def _places_for_corridor(corridor_id: str) -> list[str]:
    """Place names (from gpr_index's corridor definitions) belonging to a corridor,
    e.g. "taiwan_south_china_sea" -> ["Taiwan Strait", "South China Sea"]. These are
    the same place names embedded in articles' nlp_locations by nlp/locations.py,
    so they're what db.get_recent_news(corridor=...) actually matches against —
    the corridor *slug* itself (e.g. "taiwan_south_china_sea") never appears in
    article text and would match nothing.
    """
    return [
        name
        for name, spec in CORRIDOR_PLACES.items()
        if corridor_id in spec.get("corridors", ())
    ]


def _cited_articles(corridor_id: str, limit: int = ARTICLES_PER_CORRIDOR) -> list[dict]:
    seen: dict[int, dict] = {}
    for place in _places_for_corridor(corridor_id):
        for row in db.get_recent_news(corridor=place, limit=limit, tagged_only=True):
            seen.setdefault(row["id"], row)
    articles = sorted(
        seen.values(),
        key=lambda r: r.get("published_at") or r.get("scraped_at") or "",
        reverse=True,
    )
    return articles[:limit]


def _build_agent() -> Agent:
    model = OllamaModel(
        host=OLLAMA_HOST,
        model_id=OLLAMA_MODEL_ID,
        temperature=0.2,
    )
    return Agent(model=model, system_prompt=SYSTEM_PROMPT)


def explain_corridor(agent: Agent, corridor_row: dict, articles: list[dict]) -> str:
    headlines = (
        "\n".join(f"- {a['title']} ({a['source']})" for a in articles)
        if articles
        else "(no recent tagged articles for this corridor)"
    )
    prompt = (
        f"Corridor: {corridor_row['corridor_name']}\n"
        f"Today's risk score: {corridor_row['corridor_risk']:.1f} "
        f"(7-day avg: {corridor_row.get('corridor_risk_7ma')}, "
        f"30-day avg: {corridor_row.get('corridor_risk_30ma')})\n"
        f"Recent related headlines:\n{headlines}\n\n"
        "Explain why this corridor's risk score is at this level today."
    )
    result = agent(prompt)
    return str(result).strip()


def run() -> dict:
    latest, rows = db.get_corridors_latest()
    if not rows:
        db.log_pipeline_run("explain_corridors", "skipped", {"reason": "no corridor data"})
        return {"day": None, "explained": 0}

    agent = _build_agent()
    explained = 0
    errors: list[str] = []
    for row in rows:
        corridor_id = row["corridor"]
        try:
            articles = _cited_articles(corridor_id)
            text = explain_corridor(agent, row, articles)
            db.upsert_corridor_explanation(
                date=latest,
                corridor=corridor_id,
                explanation_text=text,
                cited_article_ids=[a["id"] for a in articles],
            )
            explained += 1
        except Exception as exc:  # noqa: BLE001 - one bad corridor shouldn't stop the rest
            errors.append(f"{corridor_id}: {exc}")

    status = "ok" if not errors else ("partial" if explained else "error")
    details = {"day": str(latest), "explained": explained, "corridors": len(rows), "errors": errors}
    db.log_pipeline_run("explain_corridors", status, details)
    return details


def main() -> int:
    result = run()
    print(f"[explain_corridors] {result}")
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
