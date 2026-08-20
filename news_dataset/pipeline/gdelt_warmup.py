"""Local GDELT warmup: download GKG, merge with India parquets, recompute GPR/corridors."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gpr_index.scripts.merge_processed_dirs import merge_processed_dirs  # noqa: E402
from gpr_index.scripts.paths import (  # noqa: E402
    GPR_WARMUP_START,
    GKG_PROCESSED_DIR,
    GKG_RAW_DIR,
    INDEX_PROCESSED_DIR,
    INDIA_GPR_INDEX_START,
    OUTPUT_DIR,
)
from news_dataset.export.to_db import sync_all  # noqa: E402
from news_dataset.pipeline.daily_index import (  # noqa: E402
    _run_cmd,
    refresh_dual_signal,
    run_gpr_range,
)

STAGE = "gdelt_warmup"


def _warmup_end() -> date:
    return INDIA_GPR_INDEX_START - timedelta(days=1)


def run_gdelt_warmup(
    *,
    warmup_start: date | None = None,
    warmup_end: date | None = None,
    score_end: date | None = None,
    slot_step: int = 4,
    slot_offset: int = 0,
    delay_seconds: float = 0.3,
    skip_download: bool = False,
    skip_preprocess: bool = False,
    skip_merge: bool = False,
    skip_gpr: bool = False,
    skip_sync: bool = False,
    skip_dual_signal: bool = False,
) -> dict:
    w_start = warmup_start or GPR_WARMUP_START
    w_end = warmup_end or _warmup_end()
    end_day = score_end or date.today()
    details: dict = {
        "warmup_start": w_start.isoformat(),
        "warmup_end": w_end.isoformat(),
        "score_end": end_day.isoformat(),
        "slot_step": slot_step,
    }

    if w_end < w_start:
        raise ValueError(f"warmup_end {w_end} is before warmup_start {w_start}")

    if not skip_download:
        _run_cmd(
            [
                sys.executable,
                "gpr_index/main.py",
                "download",
                "--start-date",
                w_start.isoformat(),
                "--end-date",
                w_end.isoformat(),
                "--raw-dir",
                str(GKG_RAW_DIR),
                "--slot-step",
                str(slot_step),
                "--slot-offset",
                str(slot_offset),
                "--delay-seconds",
                str(delay_seconds),
            ]
        )
        details["download"] = "ok"

    if not skip_preprocess:
        _run_cmd(
            [
                sys.executable,
                "gpr_index/main.py",
                "preprocess",
                "--start-date",
                w_start.isoformat(),
                "--end-date",
                w_end.isoformat(),
                "--raw-dir",
                str(GKG_RAW_DIR),
                "--processed-dir",
                str(GKG_PROCESSED_DIR),
                "--slot-step",
                str(slot_step),
                "--slot-offset",
                str(slot_offset),
            ]
        )
        details["preprocess"] = "ok"

    if not skip_merge:
        merge_summary = merge_processed_dirs(
            output_dir=INDEX_PROCESSED_DIR,
            warmup_start=w_start,
            india_start=INDIA_GPR_INDEX_START,
            india_end=end_day,
        )
        details["merge"] = merge_summary
        if merge_summary["linked_gkg"] == 0:
            raise RuntimeError(
                "No GDELT warmup parquets linked — run download + preprocess first "
                f"for {w_start.isoformat()}..{w_end.isoformat()}"
            )

    os.environ["GPR_INDEX_PROCESSED_DIR"] = str(INDEX_PROCESSED_DIR.resolve())

    if not skip_gpr:
        run_gpr_range(w_start, end_day)
        details["gpr_corridor"] = "ok"

    if not skip_dual_signal:
        details["dual_signal_as_of"] = refresh_dual_signal()

    if not skip_sync:
        details["sync"] = sync_all()

    return details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warmup-start", type=date.fromisoformat, default=GPR_WARMUP_START)
    parser.add_argument(
        "--warmup-end",
        type=date.fromisoformat,
        default=None,
        help="last GDELT day (default: day before INDIA_GPR_INDEX_START)",
    )
    parser.add_argument(
        "--score-end",
        type=date.fromisoformat,
        default=date.today(),
        help="last day to score after merge (default: today UTC)",
    )
    parser.add_argument("--slot-step", type=int, default=4)
    parser.add_argument("--slot-offset", type=int, default=0)
    parser.add_argument("--delay-seconds", type=float, default=0.3)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-preprocess", action="store_true")
    parser.add_argument("--skip-merge", action="store_true")
    parser.add_argument("--skip-gpr", action="store_true")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--skip-dual-signal", action="store_true")
    args = parser.parse_args()

    try:
        summary = run_gdelt_warmup(
            warmup_start=args.warmup_start,
            warmup_end=args.warmup_end,
            score_end=args.score_end,
            slot_step=args.slot_step,
            slot_offset=args.slot_offset,
            delay_seconds=args.delay_seconds,
            skip_download=args.skip_download,
            skip_preprocess=args.skip_preprocess,
            skip_merge=args.skip_merge,
            skip_gpr=args.skip_gpr,
            skip_sync=args.skip_sync,
            skip_dual_signal=args.skip_dual_signal,
        )
        print(f"[{STAGE}] ok: {summary}")
        return 0
    except Exception as exc:
        print(f"[{STAGE}] FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
