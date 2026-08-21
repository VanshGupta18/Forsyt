"""Forsyt — Caldara GPR replication via GDELT GKG.

Beginner note: "GPR" = Geopolitical Risk index (see docs/README.md for a
plain-language intro, or docs/gpr-theory.md for the full methodology).
This module has been run over more than one calendar year of data (a full
2025 GDELT batch, then a 2026 India-news product run — see
docs/gpr-theory.md section 9 on "split-era normalization"), so the example
dates below are illustrative, not a hardcoded requirement: substitute
whatever start/end dates match the data you actually want to score.

Pipeline:
  download    → data/gkg_raw/          (GDELT 15-min GKG zips)
  preprocess  → data/gkg_processed/    (daily Parquet)
  gpr         → outputs/               (daily/monthly/event/country indices)
  fill-gaps   → outputs/               (Caldara imputation for missing days)
  validate    → outputs/validation/    (10-check validation vs Caldara)
  diagnose    → sample scoring stats
  corridor    → daily corridor threat/exposure indices
  validate-corridors → corridor specificity, coverage, parity, and summary
  plot        → outputs/plots/
  reprocess   → rebuild index from existing daily CSV
  merge-processed → symlink gkg + india parquets into index_processed/

Quickstart (example: one full calendar year):
  cd gpr_index
  python main.py download   --start-date YYYY-01-01 --end-date YYYY-12-31
  python main.py preprocess --start-date YYYY-01-01 --end-date YYYY-12-31
  python main.py gpr        --start-date YYYY-01-01 --end-date YYYY-12-31
  python main.py fill-gaps  --start-date YYYY-01-01 --end-date YYYY-12-31
  python main.py validate   --start-date YYYY-01-01 --end-date YYYY-12-31

(See README.md for a copy-pasteable command list with concrete dates for the
current run.)

Or from repo root:  python gpr_index/main.py gpr ...
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

COMMANDS: dict[str, str] = {
    "download":    "scripts.download_gkg",       # fetch raw GDELT GKG slot files from the internet into data/gkg_raw/
    "preprocess":  "scripts.preprocess_gkg",      # merge+clean each day's raw slots into one Parquet file in data/gkg_processed/
    "gpr":         "scripts.gkg_gpr_pipeline",    # score every article and build the daily/monthly GPR index CSVs in outputs/
    "fill-gaps":   "scripts.fill_gpr_gaps",       # fill in any missing calendar days so the series has no holes
    "validate":    "scripts.validate_gpr",        # compare our index against the published Caldara benchmark
    "diagnose":    "scripts.diagnose_gpr_scoring",# print scoring statistics on a small sample, for debugging the scorer itself
    "corridor":    "scripts.corridor_index",      # build the India trade-corridor threat/risk indices
    "validate-corridors": "scripts.validate_corridors",  # sanity-check the corridor indices (coverage, parity, event response)
    "plot":        "scripts.plot_gpr",            # draw the daily/monthly GPR charts as PNG files
    "reprocess":   "scripts.gkg_gpr_pipeline",    # re-normalize an existing gpr_daily_index.csv without re-scoring articles
    "merge-processed": "scripts.merge_processed_dirs",  # symlink GDELT-warmup + India parquets together for a local warmup run
}

COMMAND_ENTRYPOINTS = {
    "reprocess": "reprocess_main",
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        if len(sys.argv) >= 2:
            print(f"Unknown command: {sys.argv[1]!r}")
            print(f"Available: {', '.join(sorted(COMMANDS))}")
        sys.exit(0 if len(sys.argv) < 2 else 1)

    command = sys.argv[1]
    mod = importlib.import_module(COMMANDS[command])
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    getattr(mod, COMMAND_ENTRYPOINTS.get(command, "main"))()


if __name__ == "__main__":
    main()
