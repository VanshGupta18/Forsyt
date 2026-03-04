"""
Pydantic schemas for LLM-extracted geopolitical event validation.
Used by gpt_extractor.py before database insert.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class EventSchema(BaseModel):
    """
    Structured output schema for GPT-4o-mini event extraction.
    All fields are validated before the row is inserted to structured_events.
    """

    event_type: str = Field(
        description=(
            "One of: military_conflict, diplomatic_incident, sanctions, "
            "terrorism, border_dispute, civil_unrest, cyber_attack, "
            "economic_coercion, nuclear_threat, other"
        )
    )

    severity: float = Field(
        ge=0.0, le=1.0,
        description="Event severity (0 = trivial, 1 = catastrophic)"
    )

    india_exposure: float = Field(
        ge=0.0, le=1.0,
        description=(
            "How directly India is affected "
            "(0 = pure global, 1 = exclusively India)"
        )
    )

    confidence: float = Field(
        ge=0.0, le=1.0,
        description="LLM confidence in the extraction accuracy"
    )

    actors: List[str] = Field(
        default_factory=list,
        description="Countries / organizations involved, e.g. ['India', 'Pakistan']"
    )

    locations: List[str] = Field(
        default_factory=list,
        description="Geographic locations mentioned, e.g. ['Kashmir', 'Line of Control']"
    )

    summary: str = Field(
        max_length=500,
        description="One-sentence summary of the event"
    )

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        valid = {
            "military_conflict", "diplomatic_incident", "sanctions",
            "terrorism", "border_dispute", "civil_unrest", "cyber_attack",
            "economic_coercion", "nuclear_threat", "other"
        }
        v_lower = v.lower().strip()
        if v_lower not in valid:
            # Map unknown types to "other" rather than rejecting the article
            return "other"
        return v_lower

    @field_validator("actors", "locations", mode="before")
    @classmethod
    def coerce_list(cls, v) -> List[str]:
        if isinstance(v, str):
            return [v] if v else []
        return v or []
