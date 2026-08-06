"""NLP extractor version string stored on each article row."""

from .themes import MODEL_ID, SIMILARITY_THRESHOLD

EXTRACTOR_VERSION = (
    f"{MODEL_ID}@{SIMILARITY_THRESHOLD}"
    "|lexicon-tone-gcam-v2|fips-locations-v2-corridor-places"
)
