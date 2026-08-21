"""Module-root paths for gpr_index (stable regardless of cwd).

Beginner note: every other script imports its folder locations from here
instead of hardcoding them, so if you ever move the gpr_index/ folder or
rename data/outputs subfolders, this is the one file to update.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

# parents[1] = go up two levels from this file (scripts/paths.py -> scripts/ -> gpr_index/).
# That makes MODULE_ROOT the gpr_index/ folder itself, regardless of which
# directory you were in when you ran a script.
MODULE_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = MODULE_ROOT / "data"       # raw + processed GDELT/India article files
OUTPUT_DIR = MODULE_ROOT / "outputs"  # everything the pipeline produces (CSVs, charts, reports)

GKG_RAW_DIR = DATA_DIR / "gkg_raw"                # untouched GDELT slot files, straight off the download
GKG_PROCESSED_DIR = DATA_DIR / "gkg_processed"     # one cleaned Parquet file per day, global GDELT news
INDIA_PROCESSED_DIR = DATA_DIR / "india_processed" # one cleaned Parquet file per day, India-only news
INDEX_PROCESSED_DIR = DATA_DIR / "index_processed" # local-only: symlinks that stitch GDELT + India together
VALIDATION_DIR = OUTPUT_DIR / "validation"         # benchmark/quality-check reports
PLOTS_DIR = OUTPUT_DIR / "plots"                   # PNG charts

# --- The two "eras" of this index, and the env vars that move their boundary ---
# Early on there wasn't enough India news to compute a stable index, so the
# pipeline was "warmed up" on global GDELT data first, then switched over to
# India-only news once that source had enough volume. See split_era.py for
# why these two periods must be scored with separate baselines.

# GDELT warmup window for index normalization (local only; not synced to Postgres).
# Override with the GPR_WARMUP_START env var if you need to shift the warmup start.
GPR_WARMUP_START = date.fromisoformat(
    os.environ.get("GPR_WARMUP_START", "2026-01-01")
)

# First UTC day included in the India news GPR index (parquets may exist earlier).
# This is the "product" cutover date: everything on/after this day is the real,
# user-facing India index; everything before it is warmup/calibration only.
# Override with the INDIA_GPR_INDEX_START env var.
INDIA_GPR_INDEX_START = date.fromisoformat(
    os.environ.get("INDIA_GPR_INDEX_START", "2026-08-09")
)


def gpr_index_processed_dir() -> Path:
    """Directory of daily parquets for GPR scoring (override for warmup merge).

    By default this is INDIA_PROCESSED_DIR (what cloud/CI jobs use every day).
    Set the GPR_INDEX_PROCESSED_DIR env var to INDEX_PROCESSED_DIR when you
    want to run a local warmup batch that also includes the older GDELT days.
    """
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

# Caldara benchmark spreadsheets (the "answer key" this index is checked against).
# These are downloaded by hand from https://www.matteoiacoviello.com/gpr.htm and
# get saved under slightly different names depending on how they were exported,
# so each CANDIDATES list tries a few known filenames in order and uses the
# first one that actually exists on disk.
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
