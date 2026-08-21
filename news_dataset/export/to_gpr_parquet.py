"""Export daily news populations to GPR-compatible Parquet files.

Beginner note — what is Parquet, and why "filler rows"?
    Parquet is just a file format for storing tables of data efficiently
    (like a compressed CSV, but faster to read for the pandas/analysis code
    downstream). Each day gets one Parquet file with one row per article.

    The "filler rows" trick (see FILLER_SOURCE below) exists because of how
    the GPR risk score is calculated elsewhere (gpr_index/): the score for a
    day is roughly "how many articles about conflict, out of everyone we
    looked at that day". Tier 2 articles that get rejected by the keyword
    filter (see ingestion/geo_pipeline.py's match_keywords()) were still
    "looked at" — they just didn't make it into the dataset as full articles.
    If we only counted the KEPT articles, the day's "everyone we looked at"
    denominator would be wrong (too small), making the risk score
    artificially high. So process_day() below adds one blank/empty filler
    row per rejected article, just to keep that denominator honest, without
    those filler rows contributing any theme/tone/location content.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from gpr_index.scripts.paths import INDIA_PROCESSED_DIR


COLUMNS = [
    "SQLDATE",
    "SourceCommonName",
    "DocumentIdentifier",
    "V2Themes",
    "V2Locations",
    "GCAM",
    "tone_overall",
    "tone_neg",
    "tone_polarity",
]
FILLER_SOURCE = "__KEYWORD_REJECTED__"


class ExportIntegrityError(RuntimeError):
    """Raised when a daily population cannot be exported safely."""


def _day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def _days(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=COLUMNS)
    frame["SQLDATE"] = pd.to_datetime(frame["SQLDATE"], utc=True)
    for column in ("SourceCommonName", "DocumentIdentifier", "V2Themes", "V2Locations", "GCAM"):
        frame[column] = frame[column].fillna("").astype(str)
    for column in ("tone_overall", "tone_neg", "tone_polarity"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0).astype(float)
    return frame


def process_day(
    day: date,
    out_dir: Path,
    force: bool = False,
    allow_incomplete_denominator: bool = False,
    *,
    count_seen: Callable | None = None,
    count_ingested: Callable | None = None,
    get_articles: Callable | None = None,
) -> Path | None:
    """Validate and export one UTC calendar day."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ymd = day.strftime("%Y%m%d")
    output_path = out_dir / f"india_processed_{ymd}.parquet"
    if output_path.exists() and not force:
        print(f"[{ymd}] SKIP (already exists): {output_path}")
        return None

    if count_seen is None or count_ingested is None or get_articles is None:
        from news_dataset import db

        count_seen = count_seen or db.count_geo_seen_articles
        count_ingested = count_ingested or db.count_geo_ingested_articles
        get_articles = get_articles or db.get_gpr_articles

    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    seen_count = int(count_seen(start, end))
    ingested_count = int(count_ingested(start, end))
    if seen_count == 0 and ingested_count == 0:
        print(f"[{ymd}] SKIP (no observed articles)")
        return None

    articles = list(get_articles(start, end))
    nlp_complete_count = len(articles)

    if ingested_count != nlp_complete_count:
        raise ExportIntegrityError(
            f"{ymd}: {ingested_count:,} ingested articles but only "
            f"{nlp_complete_count:,} are NLP-complete. Run "
            "`python -m news_dataset.nlp.run_extraction` for this date first."
        )

    by_link = {}
    for article in articles:
        link = article.get("link")
        if not link:
            raise ExportIntegrityError(f"{ymd}: an NLP-complete article has no link.")
        by_link.setdefault(link, article)
    if len(by_link) != ingested_count:
        raise ExportIntegrityError(
            f"{ymd}: defensive link deduplication produced {len(by_link):,} rows, "
            f"but the ingested count is {ingested_count:,}; refusing to export."
        )

    denominator_incomplete = seen_count < ingested_count
    if denominator_incomplete and not allow_incomplete_denominator:
        raise ExportIntegrityError(
            f"{ymd}: seen count ({seen_count:,}) is below ingested count "
            f"({ingested_count:,}); denominator history is incomplete. "
            "Restore geo_seen_links history or rerun only for a historical "
            "experiment with --allow-incomplete-denominator."
        )
    if denominator_incomplete:
        print(
            f"[{ymd}] WARNING: INCOMPLETE DENOMINATOR OVERRIDE — "
            f"seen={seen_count:,}, ingested={ingested_count:,}; "
            "the output denominator is not historically complete."
        )

    rows = [
        {
            "SQLDATE": article.get("published_at") or article.get("scraped_at"),
            "SourceCommonName": article.get("source") or "",
            "DocumentIdentifier": link,
            "V2Themes": article.get("nlp_themes") or "",
            "V2Locations": article.get("nlp_locations") or "",
            "GCAM": article.get("nlp_gcam") or "",
            "tone_overall": 0.0,
            "tone_neg": article.get("nlp_tone_neg") or 0.0,
            "tone_polarity": article.get("nlp_tone_polarity") or 0.0,
        }
        for link, article in by_link.items()
    ]
    # These "filler" rows represent Tier-2 articles that were fetched but
    # rejected by the geopolitics keyword filter (see module docstring above
    # for why we need them at all). They carry no theme/tone/location content
    # — their only job is to make the row count for this day match how many
    # articles were actually observed, so scoring's "share of the day's news
    # that was about conflict" denominator is accurate.
    filler_count = max(0, seen_count - ingested_count)
    rows.extend(
        {
            "SQLDATE": start,
            "SourceCommonName": FILLER_SOURCE,
            "DocumentIdentifier": f"forsyt://keyword-rejected/{ymd}/{index:08d}",
            "V2Themes": "",
            "V2Locations": "",
            "GCAM": "",
            "tone_overall": 0.0,
            "tone_neg": 0.0,
            "tone_polarity": 0.0,
        }
        for index in range(filler_count)
    )
    frame = _frame(rows)
    if not denominator_incomplete and len(frame) != seen_count:
        raise ExportIntegrityError(
            f"{ymd}: output has {len(frame):,} rows, expected seen count "
            f"{seen_count:,}; refusing to write."
        )

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=out_dir
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    try:
        frame.to_parquet(temporary_path, index=False, compression="snappy")
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    print(
        f"[{ymd}] seen={seen_count:,} ingested={ingested_count:,} "
        f"NLP complete={nlp_complete_count:,} filler={filler_count:,} "
        f"output rows={len(frame):,} path={output_path}"
    )
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=_day, help="one UTC day (YYYY-MM-DD)")
    parser.add_argument("--start", type=_day, help="first UTC day")
    parser.add_argument("--end", type=_day, help="last UTC day, inclusive")
    parser.add_argument("--out-dir", type=Path, default=INDIA_PROCESSED_DIR)
    parser.add_argument("--force", action="store_true", help="replace existing daily files")
    parser.add_argument(
        "--allow-incomplete-denominator",
        action="store_true",
        help="allow seen counts below ingested counts for historical experiments",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.date and (args.start or args.end):
        parser.error("--date cannot be combined with --start or --end")
    if args.date:
        start_day = end_day = args.date
    elif args.start and args.end:
        start_day, end_day = args.start, args.end
    else:
        parser.error("use --date, or provide both --start and --end")
    if start_day > end_day:
        parser.error("--start cannot be after --end")

    failed = False
    for day in _days(start_day, end_day):
        try:
            process_day(
                day,
                args.out_dir,
                force=args.force,
                allow_incomplete_denominator=args.allow_incomplete_denominator,
            )
        except Exception as exc:
            failed = True
            print(f"[{day:%Y%m%d}] FAIL: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
