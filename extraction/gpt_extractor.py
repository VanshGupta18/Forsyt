"""
Stage 2 LLM extractor: GPT-4o-mini structured event extraction.
Extracts: event_type, severity, india_exposure, confidence, actors, locations, summary
"""

import os
import json
import time
import logging
from typing import Optional

from openai import OpenAI
from pydantic import ValidationError

from extraction.schema import EventSchema

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1.3"
GPT_MODEL      = "gpt-4o-mini"
MAX_RETRIES    = 3
BASE_BACKOFF   = 2.0    # seconds (exponential: 2, 4, 8)

SYSTEM_PROMPT = """You are a geopolitical risk analyst specializing in South Asia.
Extract structured information from news articles about events that may affect India's security or economy.

You MUST respond with valid JSON only. No explanation, no markdown, just the JSON object.

Scoring guidance:
- severity: 0.0-0.3 = minor tensions/rhetoric, 0.3-0.6 = significant incident, 0.6-0.8 = major crisis, 0.8-1.0 = catastrophic event
- india_exposure: 0.0-0.2 = global event with minimal India impact, 0.3-0.6 = regional event with indirect India impact, 0.7-1.0 = directly involves India as primary actor or victim
- confidence: your confidence that this extraction accurately captures the article's content (0.0-1.0)
"""

USER_PROMPT_TEMPLATE = """Analyze this news article and extract the geopolitical risk event:

{article_text}

Respond with this exact JSON format:
{{
  "event_type": "one of: military_conflict, diplomatic_incident, sanctions, terrorism, border_dispute, civil_unrest, cyber_attack, economic_coercion, nuclear_threat, other",
  "severity": 0.0,
  "india_exposure": 0.0,
  "confidence": 0.0,
  "actors": ["country or org 1", "country or org 2"],
  "locations": ["location 1", "location 2"],
  "summary": "One sentence summary of the event."
}}"""


def extract_event(article_text: str,
                  article_id: Optional[int] = None) -> Optional[EventSchema]:
    """
    Extract a structured geopolitical event from article text using GPT-4o-mini.

    Retries up to MAX_RETRIES times with exponential backoff on API errors.
    Returns None if all retries fail (article routed to dead_letter_queue by caller).

    Args:
        article_text: Cleaned article text (pre-truncated to ~1500 tokens)
        article_id: PostgreSQL article ID for logging

    Returns:
        EventSchema Pydantic model, or None on failure
    """
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = USER_PROMPT_TEMPLATE.format(article_text=article_text)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=GPT_MODEL,
                temperature=0.0,      # Deterministic — same article always gives same extraction
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=300,
            )

            raw_json  = response.choices[0].message.content
            parsed    = json.loads(raw_json)
            event     = EventSchema(**parsed)

            logger.debug(
                f"Extracted event for article {article_id}: "
                f"{event.event_type} sev={event.severity:.2f} "
                f"india={event.india_exposure:.2f} conf={event.confidence:.2f}"
            )
            return event

        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"GPT parse/validation error (attempt {attempt}/{MAX_RETRIES}): {e}")
            # Don't backoff on parse errors — retry immediately
            if attempt == MAX_RETRIES:
                return None

        except Exception as e:
            logger.warning(f"GPT API error (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                backoff = BASE_BACKOFF ** attempt
                logger.info(f"Backing off {backoff:.0f}s before retry...")
                time.sleep(backoff)
            else:
                return None

    return None
