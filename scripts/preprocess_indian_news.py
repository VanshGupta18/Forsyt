"""Preprocess daily India JSONL files into GKG-compatible Parquet.

Reads:  data/india_raw/YYYY-MM-DD.jsonl.gz   (from live scraper or backfill)
Writes: data/india_processed/india_processed_YYYYMMDD.parquet

Output schema matches what gkg_gpr_pipeline.score_articles() expects:
  SQLDATE          — pd.Timestamp (IST noon for the day)
  SourceCommonName — outlet display name (e.g. "The Hindu")
  DocumentIdentifier — canonical URL (dedup key)
  V2Themes         — synthetic; semicolon-separated TIER codes from theme_tagger
  V2Locations      — synthetic; country mentions extracted by location_tagger.py
                     (populates gpr_country_level.csv from the news path)
  GCAM             — empty string (no GKG GCAM; gcam_score will be 0)
  tone_overall     — signed tone from DistilBERT
  tone_neg         — absolute negative tone (calibrated to GKG scale 0–30)
  tone_polarity    — polarity 0–1

The scraper-based parquets feed the same gkg_gpr_pipeline.py as GDELT GKG data,
producing the full GPR suite (daily, monthly, event-type, country-level) from
Indian newspaper coverage of global geopolitical events.

Usage:
  python -m scripts.preprocess_indian_news \\
      --start-date 2026-01-01 \\
      --end-date   2026-06-26 \\
      [--raw-dir   data/india_raw] \\
      [--out-dir   data/india_processed] \\
      [--batch-size 256]
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

import pandas as pd

logger = logging.getLogger(__name__)


def _extract_locations(title: str, content: str) -> str:
    """Extract country mentions from text → synthetic V2Locations string."""
    from scripts.location_tagger import tag_locations  # noqa: PLC0415
    return tag_locations(title, content)

REPO_ROOT  = Path(__file__).parent.parent
RAW_DIR    = REPO_ROOT / "data" / "india_raw"
OUT_DIR    = REPO_ROOT / "data" / "india_processed"

SOURCE_NAMES: dict[str, str] = {
    # English
    "TH":   "The Hindu",
    "TOI":  "Times of India",
    "TIE":  "Indian Express",
    "IT":   "India Today",
    "NDTV": "NDTV",
    # Hindi
    "AU":   "Amar Ujala",
    "BBC":  "BBC Hindi",
    "OI":   "OneIndia Hindi",
    "LH":   "Live Hindustan",
    "N18":  "News18 Hindi",
}


def _date_range(start: date, end: date) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _tag_batch(articles: list[dict]) -> list[dict]:
    """Call theme_tagger.tag_batch and merge results back into article dicts."""
    from scripts.theme_tagger import tag_batch  # noqa: PLC0415
    results = tag_batch(articles)
    for art, res in zip(articles, results):
        art["_v2themes"]        = res.v2themes
        art["_tone_neg"]        = res.tone_neg
        art["_tone_overall"]    = res.tone_overall
        art["_tone_polarity"]   = res.tone_polarity
    return articles


def process_day(
    day: date,
    raw_dir: Path = RAW_DIR,
    out_dir: Path = OUT_DIR,
    batch_size: int = 256,
    force: bool = False,
) -> int:
    """Process one day's JSONL → parquet. Returns article count written."""
    jsonl_path = raw_dir / f"{day.isoformat()}.jsonl.gz"
    out_path   = out_dir / f"india_processed_{day.strftime('%Y%m%d')}.parquet"

    if not jsonl_path.exists():
        logger.debug(f"[preprocess] {day}: no JSONL file — skip")
        return 0

    if out_path.exists() and not force:
        logger.info(f"[preprocess] {day}: parquet already exists — skip (use --force to reprocess)")
        return 0

    rows = _load_jsonl(jsonl_path)
    if not rows:
        logger.warning(f"[preprocess] {day}: JSONL empty — skip")
        return 0

    logger.info(f"[preprocess] {day}: {len(rows)} articles loaded → tagging …")

    # Tag in batches
    tagged: list[dict] = []
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        tagged.extend(_tag_batch(chunk))

    # Build DataFrame
    records = []
    sqldate = pd.Timestamp(day.isoformat() + " 12:00:00")  # noon for the day
    seen_links: set[str] = set()

    for art in tagged:
        link = art.get("link", "").strip()
        if not link or link in seen_links:
            continue
        seen_links.add(link)

        source_code = art.get("source", "")
        title   = art.get("title", "")
        content = art.get("content", "")
        records.append({
            "SQLDATE":             sqldate,
            "SourceCommonName":    SOURCE_NAMES.get(source_code.upper(), source_code),
            "DocumentIdentifier":  link,
            "V2Themes":            art.get("_v2themes", ""),
            "V2Locations":         _extract_locations(title, content),
            "GCAM":                "",  # no GCAM for scraped articles (gcam_score = 0)
            "tone_overall":        float(art.get("_tone_overall",  0.0)),
            "tone_neg":            float(art.get("_tone_neg",      0.0)),
            "tone_polarity":       float(art.get("_tone_polarity", 0.0)),
            "language":            art.get("language", "en"),
        })

    if not records:
        logger.warning(f"[preprocess] {day}: 0 usable records after dedup")
        return 0

    df = pd.DataFrame(records)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False, compression="snappy")

    n_gpr_candidates = (df["V2Themes"].str.len() > 0).sum()
    logger.info(
        f"[preprocess] {day}: {len(df)} rows → {out_path.name}"
        f"  (GPR candidate themes: {n_gpr_candidates}/{len(df)})"
    )
    return len(df)


def run(
    start_date: str,
    end_date: str,
    raw_dir: Path = RAW_DIR,
    out_dir: Path = OUT_DIR,
    batch_size: int = 256,
    force: bool = False,
) -> None:
    start = date.fromisoformat(start_date)
    end   = date.fromisoformat(end_date)
    total = 0
    skipped = 0
    for day in _date_range(start, end):
        count = process_day(day, raw_dir=raw_dir, out_dir=out_dir, batch_size=batch_size, force=force)
        if count > 0:
            total += count
        else:
            skipped += 1
    print(f"\n[preprocess-india] Done: {total} articles across {(end-start).days+1-skipped} days "
          f"({skipped} days skipped/empty)")
    print(f"  Output dir: {out_dir}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Preprocess Indian news JSONL → GKG-compatible parquet")
    p.add_argument("--start-date",  default="2026-01-01")
    p.add_argument("--end-date",    default="2026-06-26")
    p.add_argument("--raw-dir",     default=str(RAW_DIR),  help="Directory with YYYY-MM-DD.jsonl.gz files")
    p.add_argument("--out-dir",     default=str(OUT_DIR),  help="Output directory for parquet files")
    p.add_argument("--batch-size",  type=int, default=256, help="Articles per DistilBERT batch")
    p.add_argument("--force",       action="store_true",   help="Reprocess even if parquet already exists")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    run(
        start_date=args.start_date,
        end_date=args.end_date,
        raw_dir=Path(args.raw_dir),
        out_dir=Path(args.out_dir),
        batch_size=args.batch_size,
        force=args.force,
    )


if __name__ == "__main__":
    main()
