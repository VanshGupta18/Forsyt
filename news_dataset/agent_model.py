"""One model provider for every LLM feature in Forsyt.

Beginner note — why this module exists at all:
    Forsyt has two features that call a language model: the daily corridor
    explanations (pipeline/explain_corridors.py) and the portfolio summary
    (api/ai_summary.py). They used to be written completely differently —
    one built a Strands agent against a local Ollama model, the other hand-
    rolled an HTTP POST to Google's Gemini REST API. Two code paths, two
    sets of environment variables, and two places to edit whenever the model
    changes.

    Both now build their agent here instead. Switching model provider is one
    environment variable, not a rewrite of two modules — which is the point:
    if this is ever hosted on something like SageMaker, `strands` already
    ships a `sagemaker` provider and only FORSYT_MODEL_PROVIDER changes.

Choosing a provider:
    FORSYT_MODEL_PROVIDER — "ollama" or "gemini". If unset, we pick Gemini
    when GEMINI_API_KEY is present and Ollama otherwise, because that's the
    right default in both places this runs: the GitHub Actions runner
    installs Ollama locally (no API key, no account), while a hosted API
    process has no Ollama server to talk to but can have a key.

    ollama: OLLAMA_HOST (default http://localhost:11434)
            OLLAMA_MODEL_ID (default qwen2.5:7b-instruct)
    gemini: GEMINI_API_KEY (required), GEMINI_MODEL (default below)

Nothing here is a hard dependency. `strands` lives in requirements-ai.txt and
is NOT installed in the API container, so every import is done lazily inside
the functions: callers that can't build an agent are expected to degrade to
their own deterministic fallback rather than fail. Use is_configured() to
check before calling build_agent().
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"


def provider_name() -> str:
    """Which provider we'd use right now — also the `source` value the API reports."""
    explicit = os.environ.get("FORSYT_MODEL_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    return "gemini" if os.environ.get("GEMINI_API_KEY") else "ollama"


def is_configured() -> bool:
    """True if the selected provider has what it needs and strands is importable.

    Deliberately cheap and side-effect free: it does not reach out to Ollama or
    Gemini. A provider that's configured but unreachable surfaces as an
    exception from build_agent()/the agent call, which callers already catch.
    """
    try:
        import strands  # noqa: F401
    except ImportError:
        return False

    provider = provider_name()
    if provider == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY"))
    if provider == "ollama":
        return True  # no credential to check; reachability is caught at call time
    return False


def _build_model(temperature: float) -> Any:
    provider = provider_name()

    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        return OllamaModel(
            host=os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
            model_id=os.environ.get("OLLAMA_MODEL_ID", DEFAULT_OLLAMA_MODEL),
            temperature=temperature,
        )

    if provider == "gemini":
        from strands.models.gemini import GeminiModel

        return GeminiModel(
            client_args={"api_key": os.environ["GEMINI_API_KEY"]},
            model_id=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            params={
                "temperature": temperature,
                "max_output_tokens": 800,
                # Gemini 3.x flash are thinking models: without a zero thinking
                # budget the reasoning tokens eat max_output_tokens and the answer
                # truncates (finishReason MAX_TOKENS -> empty/garbled text).
                # Neither of our two prompts needs reasoning. Do not drop this.
                "thinking_config": {"thinking_budget": 0},
            },
        )

    raise ValueError(
        f"unknown FORSYT_MODEL_PROVIDER {provider!r} (expected 'ollama' or 'gemini')"
    )


def build_agent(system_prompt: str, temperature: float = 0.2) -> Any:
    """A Strands Agent on the configured provider.

    Raises if strands isn't installed or the provider is misconfigured — call
    is_configured() first if you have a fallback to fall back to.
    """
    from strands import Agent

    return Agent(model=_build_model(temperature), system_prompt=system_prompt)
