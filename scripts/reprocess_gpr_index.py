"""Re-normalize GPR index and gap-fill without re-scoring articles.

Usage:
  python -m scripts.reprocess_gpr_index \\
    --output-dir outputs \\
    --start-date 2025-01-01 --end-date 2025-12-31
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.gkg_gpr_pipeline import reprocess_index


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Re-normalize GPR index from saved daily CSV")
    p.add_argument("--output-dir",     default="outputs")
    p.add_argument("--start-date",     default="2025-01-01")
    p.add_argument("--end-date",       default="2025-12-31")
    p.add_argument("--baseline-start", default=None)
    p.add_argument("--baseline-end",   default=None)
    p.add_argument("--fill-method",    default="caldara", choices=["forward", "linear", "caldara"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    reprocess_index(
        output_dir=Path(args.output_dir),
        start_date=args.start_date,
        end_date=args.end_date,
        baseline_start=args.baseline_start or args.start_date,
        baseline_end=args.baseline_end or args.end_date,
        fill_method=args.fill_method,
    )


if __name__ == "__main__":
    main()
