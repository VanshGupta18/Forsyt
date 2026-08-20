"""Module-root paths for gpr_index (stable regardless of cwd)."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = MODULE_ROOT / "data"
OUTPUT_DIR = MODULE_ROOT / "outputs"

GKG_RAW_DIR = DATA_DIR / "gkg_raw"
GKG_PROCESSED_DIR = DATA_DIR / "gkg_processed"
INDIA_PROCESSED_DIR = DATA_DIR / "india_processed"
INDEX_PROCESSED_DIR = DATA_DIR / "index_processed"
VALIDATION_DIR = OUTPUT_DIR / "validation"
PLOTS_DIR = OUTPUT_DIR / "plots"

# GDELT warmup window for index normalization (local only; not synced to Postgres).
GPR_WARMUP_START = date.fromisoformat(
    os.environ.get("GPR_WARMUP_START", "2026-01-01")
)

# First UTC day included in the India news GPR index (parquets may exist earlier).
INDIA_GPR_INDEX_START = date.fromisoformat(
    os.environ.get("INDIA_GPR_INDEX_START", "2026-08-09")
)


def gpr_index_processed_dir() -> Path:
    """Directory of daily parquets for GPR scoring (override for warmup merge)."""
    raw = os.environ.get("GPR_INDEX_PROCESSED_DIR", "").strip()
    if raw:
        return Path(raw)
    return INDIA_PROCESSED_DIR


def gpr_baseline_start() -> date:
    """Normalization baseline start: warmup start when using merged index dir."""
    if gpr_index_processed_dir().resolve() == INDEX_PROCESSED_DIR.resolve():
        return GPR_WARMUP_START
    return INDIA_GPR_INDEX_START


def gpr_score_start(requested: date) -> date:
    """Earliest calendar day included in a GPR scoring batch."""
    if requested < INDIA_GPR_INDEX_START:
        return max(requested, GPR_WARMUP_START)
    return max(requested, INDIA_GPR_INDEX_START)

CALDARA_MONTHLY = DATA_DIR / "caldara_gpr_monthly.xls"
CALDARA_DAILY = DATA_DIR / "caldara_gpr_daily.xls"
CALDARA_MONTHLY_CANDIDATES = [
    CALDARA_MONTHLY,
    DATA_DIR / "data_gpr_export (1).xls",
    DATA_DIR / "benchmarks" / "caldara_gpr_monthly.xls",
]
CALDARA_DAILY_CANDIDATES = [
    CALDARA_DAILY,
    DATA_DIR / "data_gpr_daily_recent.xls",
    DATA_DIR / "benchmarks" / "caldara_gpr_daily.xls",
]
