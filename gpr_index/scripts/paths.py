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
VALIDATION_DIR = OUTPUT_DIR / "validation"
PLOTS_DIR = OUTPUT_DIR / "plots"

# First UTC day included in the India news GPR index (parquets may exist earlier).
INDIA_GPR_INDEX_START = date.fromisoformat(
    os.environ.get("INDIA_GPR_INDEX_START", "2026-08-09")
)

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
