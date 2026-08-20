"""Build index_processed/ from GDELT warmup parquets + India news parquets."""

from __future__ import annotations

import argparse
import re
from datetime import date, timedelta
from pathlib import Path

from .paths import (
    GKG_PROCESSED_DIR,
    GPR_WARMUP_START,
    INDEX_PROCESSED_DIR,
    INDIA_GPR_INDEX_START,
    INDIA_PROCESSED_DIR,
)

GKG_PATTERN = re.compile(r"^gkg_processed_(\d{8})\.parquet$")
INDIA_PATTERN = re.compile(r"^india_processed_(\d{8})\.parquet$")


def _parse_ymd(name: str, pattern: re.Pattern[str]) -> date | None:
    match = pattern.match(name)
    if not match:
        return None
    return date.fromisoformat(
        f"{match.group(1)[:4]}-{match.group(1)[4:6]}-{match.group(1)[6:8]}"
    )


def merge_processed_dirs(
    *,
    output_dir: Path | None = None,
    gkg_dir: Path | None = None,
    india_dir: Path | None = None,
    warmup_start: date | None = None,
    india_start: date | None = None,
    india_end: date | None = None,
    clean: bool = True,
) -> dict:
    """Symlink GKG warmup days and India news days into one scoring directory."""
    out = Path(output_dir or INDEX_PROCESSED_DIR)
    gkg = Path(gkg_dir or GKG_PROCESSED_DIR)
    india = Path(india_dir or INDIA_PROCESSED_DIR)
    w_start = warmup_start or GPR_WARMUP_START
    i_start = india_start or INDIA_GPR_INDEX_START
    gkg_end = i_start - timedelta(days=1)

    out.mkdir(parents=True, exist_ok=True)
    if clean:
        for existing in out.iterdir():
            if existing.is_symlink() or existing.is_file():
                existing.unlink()

    linked_gkg = 0
    linked_india = 0
    skipped: list[str] = []

    for path in sorted(gkg.glob("gkg_processed_*.parquet")):
        day = _parse_ymd(path.name, GKG_PATTERN)
        if day is None or day < w_start or day > gkg_end:
            continue
        target = out / path.name
        target.symlink_to(path.resolve())
        linked_gkg += 1

    for path in sorted(india.glob("india_processed_*.parquet")):
        day = _parse_ymd(path.name, INDIA_PATTERN)
        if day is None or day < i_start:
            continue
        if india_end and day > india_end:
            continue
        target = out / path.name
        target.symlink_to(path.resolve())
        linked_india += 1

    if linked_gkg == 0:
        skipped.append(
            f"no GKG parquets in {gkg} for {w_start.isoformat()}..{gkg_end.isoformat()}"
        )

    summary = {
        "output_dir": str(out),
        "warmup_range": f"{w_start.isoformat()}..{gkg_end.isoformat()}",
        "india_from": i_start.isoformat(),
        "linked_gkg": linked_gkg,
        "linked_india": linked_india,
        "skipped": skipped,
    }
    print(f"[merge-processed] {summary}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(INDEX_PROCESSED_DIR))
    parser.add_argument("--gkg-dir", default=str(GKG_PROCESSED_DIR))
    parser.add_argument("--india-dir", default=str(INDIA_PROCESSED_DIR))
    parser.add_argument("--warmup-start", type=date.fromisoformat, default=GPR_WARMUP_START)
    parser.add_argument("--india-start", type=date.fromisoformat, default=INDIA_GPR_INDEX_START)
    parser.add_argument("--india-end", type=date.fromisoformat, default=None)
    parser.add_argument("--no-clean", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    merge_processed_dirs(
        output_dir=Path(args.output_dir),
        gkg_dir=Path(args.gkg_dir),
        india_dir=Path(args.india_dir),
        warmup_start=args.warmup_start,
        india_start=args.india_start,
        india_end=args.india_end,
        clean=not args.no_clean,
    )


if __name__ == "__main__":
    main()
