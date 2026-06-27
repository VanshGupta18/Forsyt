"""Forsyt — India GPR Research Pipeline.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GKG PATH (GDELT) — historical, writes to outputs/gkg/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  download      Download raw GKG 15-min slot files from GDELT
  fill-bq       Fill missing days from Google BigQuery
  preprocess    Merge raw slots into daily Parquet files (gkg_processed/)
  gpr-gkg       Score GKG parquets → full GPR suite in outputs/gkg/
  validate-gkg  Validate outputs/gkg/ vs Caldara benchmarks
  fill-gaps     Fill calendar gaps in outputs/gkg/ (Caldara imputation)

NEWS PATH (10 Indian outlets) — forward from anchor day, writes to outputs/news/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  export-news       Export today's SQLite articles → data/india_raw/YYYY-MM-DD.jsonl.gz
  preprocess-india  Tag + convert india_raw JSONL → india_processed/ parquet
  gpr-news          Score india_processed/ → full GPR suite in outputs/news/
  validate-news     Validate outputs/news/ vs Caldara benchmarks (GPRC_IND)
  incremental-update Hourly: export → preprocess → gpr-news (today only)

COMPARISON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  compare-gpr   Compare news vs GKG on overlapping dates → outputs/compare/

SHARED UTILITIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  gpr           Generic GPR scorer (pass --processed-dir and --output-dir)
  validate      Generic validator (pass --output-dir)
  diagnose      Diagnose article scoring on a sample of processed days
  plot          Plot daily and monthly GPR charts
  reprocess     Reprocess / recalculate existing GPR index

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUICKSTART — GKG path (2025 historical)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  python main.py download   --start-date 2025-01-01 --end-date 2025-12-31
  python main.py preprocess --start-date 2025-01-01 --end-date 2025-12-31
  python main.py gpr-gkg    --start-date 2025-01-01 --end-date 2025-12-31
  python main.py fill-gaps  --output-dir outputs/gkg --start-date 2025-01-01 --end-date 2025-12-31
  python main.py validate-gkg --start-date 2025-01-01 --end-date 2025-12-31

QUICKSTART — News path (forward from today)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Day 1 (run once):
  python -m scraper once
  python main.py export-news
  python main.py preprocess-india --start-date 2026-06-27 --end-date 2026-06-27 --force
  python main.py gpr-news         --start-date 2026-06-27 --end-date 2026-06-27

  # Ongoing (via cron):
  python -m scraper schedule          # every 5 min
  python main.py incremental-update   # every hour

COMPARISON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  python main.py compare-gpr --news-dir outputs/news --gkg-dir outputs/gkg
"""

from __future__ import annotations

import sys


# ---------------------------------------------------------------------------
# Command registry
# ---------------------------------------------------------------------------

COMMANDS: dict[str, str] = {
    # GKG path
    "download":       "scripts.download_gkg",
    "fill-bq":        "scripts.fill_gkg_bigquery",
    "preprocess":     "scripts.preprocess_gkg",
    "gpr-gkg":        "scripts.gkg_gpr_pipeline",       # default --output-dir outputs/gkg
    "validate-gkg":   "scripts.validate_gpr",            # default --output-dir outputs/gkg
    "fill-gaps":      "scripts.fill_gpr_gaps",

    # News path
    "export-news":        "scripts.export_news_db",
    "preprocess-india":   "scripts.preprocess_indian_news",
    "gpr-news":           "scripts.gkg_gpr_pipeline",   # default --output-dir outputs/news
    "validate-news":      "scripts.validate_gpr",        # default --output-dir outputs/news
    "incremental-update": "scripts.incremental_update",

    # Comparison
    "compare-gpr":    "scripts.compare_gpr_sources",

    # Shared / generic
    "gpr":            "scripts.gkg_gpr_pipeline",
    "validate":       "scripts.validate_gpr",
    "diagnose":       "scripts.diagnose_gpr_scoring",
    "reprocess":      "scripts.reprocess_gpr_index",
    "plot":           "scripts.plot_gpr",
}

# Path-specific default injection: when these commands are invoked without an
# explicit --output-dir (or --processed-dir), inject a sensible default so the
# user doesn't have to type the full flag each time.
_CMD_DEFAULTS: dict[str, list[str]] = {
    "gpr-gkg":      ["--output-dir", "outputs/gkg",
                     "--processed-dir", "data/gkg_processed"],
    "validate-gkg": ["--output-dir", "outputs/gkg"],
    "gpr-news":     ["--output-dir", "outputs/news",
                     "--processed-dir", "data/india_processed"],
    "validate-news":["--output-dir", "outputs/news",
                     "--benchmark", "gprc_ind"],
}


def _inject_defaults(cmd: str, argv: list[str]) -> list[str]:
    """Inject default flags for path-specific commands unless already provided."""
    defaults = _CMD_DEFAULTS.get(cmd, [])
    if not defaults:
        return argv
    result = list(argv)
    it = iter(range(0, len(defaults), 2))
    for i in it:
        flag, value = defaults[i], defaults[i + 1]
        if flag not in result:
            result = [flag, value] + result
    return result


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        if len(sys.argv) >= 2:
            print(f"Unknown command: {sys.argv[1]!r}")
            print(f"Available: {', '.join(sorted(COMMANDS))}")
        sys.exit(0 if len(sys.argv) < 2 else 1)

    cmd = sys.argv[1]
    remaining = sys.argv[2:]
    remaining = _inject_defaults(cmd, remaining)
    sys.argv = [sys.argv[0]] + remaining

    import importlib
    mod = importlib.import_module(COMMANDS[cmd])
    mod.main()


if __name__ == "__main__":
    main()
