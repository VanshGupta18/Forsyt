"""Forsyt — Caldara GPR replication via GDELT GKG (2025).

Pipeline:
  download    → data/gkg_raw/          (GDELT 15-min GKG zips)
  preprocess  → data/gkg_processed/    (daily Parquet)
  gpr         → outputs/               (daily/monthly/event/country indices)
  fill-gaps   → outputs/               (Caldara imputation for missing days)
  validate    → outputs/validation/    (10-check validation vs Caldara)
  diagnose    → sample scoring stats
  plot        → outputs/plots/
  reprocess   → rebuild index from existing parquets

Quickstart (2025):
  cd gpr_index
  python main.py download   --start-date 2025-01-01 --end-date 2025-12-31
  python main.py preprocess --start-date 2025-01-01 --end-date 2025-12-31
  python main.py gpr        --start-date 2025-01-01 --end-date 2025-12-31
  python main.py fill-gaps  --start-date 2025-01-01 --end-date 2025-12-31
  python main.py validate   --start-date 2025-01-01 --end-date 2025-12-31

Or from repo root:  python gpr_index/main.py gpr ...
"""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

COMMANDS: dict[str, str] = {
    "download":    "scripts.download_gkg",
    "preprocess":  "scripts.preprocess_gkg",
    "gpr":         "scripts.gkg_gpr_pipeline",
    "fill-gaps":   "scripts.fill_gpr_gaps",
    "validate":    "scripts.validate_gpr",
    "diagnose":    "scripts.diagnose_gpr_scoring",
    "plot":        "scripts.plot_gpr",
    "reprocess":   "scripts.reprocess_gpr_index",
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        if len(sys.argv) >= 2:
            print(f"Unknown command: {sys.argv[1]!r}")
            print(f"Available: {', '.join(sorted(COMMANDS))}")
        sys.exit(0 if len(sys.argv) < 2 else 1)

    import importlib
    mod = importlib.import_module(COMMANDS[sys.argv[1]])
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    mod.main()


if __name__ == "__main__":
    main()
