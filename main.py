"""Forsyt — India GPR Research Pipeline.

Commands:
  download          Download raw GKG 15-min slot files from GDELT
  fill-bq           Fill missing days from Google BigQuery (when zip server has gaps)
  preprocess        Merge raw slots into 365 daily Parquet files
  gpr               Score articles and build GPR index
  fill-gaps         Fill calendar gaps in existing GPR output (forward-fill or linear)
  validate          Validate outputs against paper benchmarks
  diagnose          Diagnose article scoring on a sample of processed days
  plot              Plot daily and monthly GPR charts

India newspaper path (Newsemble scraper integration):
  export-news       Export today's SQLite articles → data/india_raw/YYYY-MM-DD.jsonl.gz
  backfill-india    Backfill Jan-Jun 2026 via Wayback/Common Crawl CDX (no SQLite)
  preprocess-india  Tag + convert india_raw JSONL → GKG-compatible parquet

Examples (GKG path):
  python main.py download   --start-date 2025-01-01 --end-date 2025-12-31
  python main.py fill-bq    --start-date 2025-06-15 --end-date 2025-07-01
  python main.py preprocess --start-date 2025-01-01 --end-date 2025-12-31
  python main.py gpr        --start-date 2025-01-01 --end-date 2025-12-31
  python main.py gpr        --start-date 2025-01-01 --end-date 2025-12-31 --resume
  python main.py fill-gaps  --start-date 2025-01-01 --end-date 2025-12-31
  python main.py validate   --start-date 2025-01-01 --end-date 2025-12-31
  python main.py plot       --start-date 2025-01-01 --end-date 2025-12-31

Examples (India newspaper path — same output dir as GKG, full GPR suite):
  python main.py export-news
  python main.py backfill-india    --start-date 2026-01-01 --end-date 2026-06-20
  python main.py preprocess-india  --start-date 2026-01-01 --end-date 2026-06-26
  python main.py gpr               --processed-dir data/india_processed --output-dir outputs \\
                                   --start-date 2026-01-01 --end-date 2026-06-26
  python main.py validate          --output-dir outputs --benchmark all \\
                                   --start-date 2026-01-01 --end-date 2026-06-26
  python main.py incremental-update   # hourly: re-scores today, updates outputs/
"""

from __future__ import annotations

import sys

COMMANDS = {
    "download":          "scripts.download_gkg",
    "fill-bq":           "scripts.fill_gkg_bigquery",
    "preprocess":        "scripts.preprocess_gkg",
    "gpr":               "scripts.gkg_gpr_pipeline",
    "fill-gaps":         "scripts.fill_gpr_gaps",
    "validate":          "scripts.validate_gpr",
    "diagnose":          "scripts.diagnose_gpr_scoring",
    "reprocess":         "scripts.reprocess_gpr_index",
    "plot":              "scripts.plot_gpr",
    # India newspaper path
    "export-news":        "scripts.export_news_db",
    "backfill-india":     "scripts.backfill_cdx",
    "preprocess-india":   "scripts.preprocess_indian_news",
    "incremental-update": "scripts.incremental_update",
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        if len(sys.argv) >= 2:
            print(f"Unknown command: {sys.argv[1]!r}")
        sys.exit(0 if len(sys.argv) < 2 else 1)

    cmd = sys.argv[1]
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    import importlib
    mod = importlib.import_module(COMMANDS[cmd])
    mod.main()


if __name__ == "__main__":
    main()
