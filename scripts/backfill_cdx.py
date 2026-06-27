"""Async backfill of Jan-Jun 2026 Indian news via Wayback Machine CDX.

BACKFILL PATH ONLY — never touches SQLite.

Performance improvements over v1:
  - httpx.AsyncClient replaces blocking requests
  - Day-level asyncio.Semaphore(4): 4 days processed in parallel
  - Monthly CDX batching: 1 Wayback query per outlet per month (~30 queries
    total for Jan-Jun) instead of 1 per outlet per day (~850)
  - CDX response cache in data/india_archive/_cdx_cache/<outlet>_YYYY-MM.json.gz
    — re-runs hit cache, no network needed
  - CC fallback policy: Wayback-only for TH and NDTV (high Wayback coverage);
    Wayback + CC for TOI, TIE, IT (lower coverage, needs both)

Usage:
  python -m scripts.backfill_cdx \\
      --start-date 2026-01-01 \\
      --end-date   2026-06-20 \\
      [--outlets TH,TOI,TIE,IT,NDTV] \\
      [--day-workers 4] \\
      [--fetch-workers 16]
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import logging
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

REPO_ROOT   = Path(__file__).parent.parent
ARCHIVE_DIR = REPO_ROOT / "data" / "india_archive"
RAW_DIR     = REPO_ROOT / "data" / "india_raw"
CDX_CACHE   = ARCHIVE_DIR / "_cdx_cache"

BROWSER_UA = (
    "ForsytGPRResearch/2.0 (+https://github.com/vanshgupta; "
    "academic research bot; backfill only; rate-limited)"
)

# Wayback-only outlets (high coverage); others also query CC
WAYBACK_ONLY = frozenset({"TH", "NDTV"})

# URL prefixes per outlet
OUTLET_PREFIXES: dict[str, list[str]] = {
    "TH":   ["thehindu.com/news/national/", "thehindu.com/news/international/"],
    "TOI":  ["timesofindia.indiatimes.com/india/", "timesofindia.indiatimes.com/world/"],
    "TIE":  ["indianexpress.com/article/india/", "indianexpress.com/article/"],
    "IT":   ["indiatoday.in/india/", "indiatoday.in/"],
    "NDTV": ["ndtv.com/india-news/", "ndtv.com/world-news/"],
}

WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
CC_INDEX    = "https://index.commoncrawl.org/{index}-index"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_range(start: date, end: date) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def _months_in_range(start: date, end: date) -> list[str]:
    seen: set[str] = set()
    result = []
    for d in _date_range(start, end):
        mk = _month_key(d)
        if mk not in seen:
            seen.add(mk)
            result.append(mk)
    return result


def _cdx_cache_path(outlet: str, month: str) -> Path:
    return CDX_CACHE / f"{outlet}_{month}.json.gz"


def _cache_html_path(outlet: str, url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()
    return ARCHIVE_DIR / outlet / f"{h}.html.gz"


def _count_existing(jsonl_path: Path) -> int:
    if not jsonl_path.exists():
        return 0
    try:
        with gzip.open(jsonl_path, "rt", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# CDX discovery — monthly batch queries
# ---------------------------------------------------------------------------

async def _query_wayback_month(
    client,
    outlet: str,
    month: str,
) -> list[dict]:
    """Query Wayback CDX for one outlet for an entire month. Returns list of records."""
    year, mo = month.split("-")
    from_ts = f"{year}{mo}01000000"
    # Last day: use next month minus 1 second
    from datetime import datetime  # noqa: PLC0415
    next_month = date(int(year), int(mo), 1) + timedelta(days=32)
    to_ts = (date(next_month.year, next_month.month, 1) - timedelta(days=1)).strftime("%Y%m%d") + "235959"

    records: list[dict] = []
    for prefix in OUTLET_PREFIXES.get(outlet, []):
        params = {
            "url":       f"{prefix}*",
            "output":    "json",
            "fl":        "url,timestamp,statuscode,length",
            "from":      from_ts,
            "to":        to_ts,
            "filter":    "statuscode:200",
            "collapse":  "urlkey",
            "limit":     "10000",
            "matchType": "prefix",
        }
        try:
            resp = await client.get(WAYBACK_CDX, params=params, timeout=60)
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                continue
            headers = rows[0]
            for row in rows[1:]:
                r = dict(zip(headers, row))
                r["_source"] = "wayback"
                r["_outlet"] = outlet
                records.append(r)
        except Exception as exc:
            logger.debug(f"Wayback CDX {outlet}/{prefix}/{month}: {exc}")
    return records


async def _query_cc_month(
    client,
    outlet: str,
    month: str,
) -> list[dict]:
    """Query Common Crawl index for one outlet for an entire month."""
    year, mo = month.split("-")
    from_ts = f"{year}{mo}01000000"
    next_month = date(int(year), int(mo), 1) + timedelta(days=32)
    to_ts = (date(next_month.year, next_month.month, 1) - timedelta(days=1)).strftime("%Y%m%d") + "235959"

    cc_indices = [f"CC-MAIN-{year}-04", f"CC-MAIN-{year}-10", f"CC-MAIN-{year}-17",
                  f"CC-MAIN-{year}-22", f"CC-MAIN-{year}-26"]

    records: list[dict] = []
    for idx_name in cc_indices:
        url = CC_INDEX.format(index=idx_name)
        for prefix in OUTLET_PREFIXES.get(outlet, []):
            params = {"url": f"{prefix}*", "output": "json",
                      "from": from_ts, "to": to_ts, "matchType": "prefix", "limit": "5000"}
            try:
                resp = await client.get(url, params=params, timeout=30)
                if resp.status_code == 404:
                    break   # index doesn't exist — skip remaining prefixes for this index
                for line in resp.text.strip().splitlines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        obj["_source"] = "cc"
                        obj["_outlet"] = outlet
                        records.append(obj)
                    except json.JSONDecodeError:
                        pass
            except Exception as exc:
                logger.debug(f"CC {idx_name}/{outlet}/{prefix}: {exc}")
    return records


async def fetch_cdx_month(client, outlet: str, month: str) -> list[dict]:
    """Fetch CDX records for outlet+month, using cache."""
    cache_path = _cdx_cache_path(outlet, month)
    CDX_CACHE.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        logger.debug(f"[cdx_cache] hit {outlet}/{month}")
        with gzip.open(cache_path, "rt", encoding="utf-8") as f:
            return json.loads(f.read())

    logger.info(f"[CDX] querying {outlet}/{month} …")
    records = await _query_wayback_month(client, outlet, month)

    if outlet not in WAYBACK_ONLY:
        cc_records = await _query_cc_month(client, outlet, month)
        records.extend(cc_records)

    # Dedup by URL
    seen: set[str] = set()
    unique = []
    for r in records:
        u = r.get("url", "")
        if u and u not in seen:
            seen.add(u)
            unique.append(r)

    with gzip.open(cache_path, "wt", encoding="utf-8") as f:
        f.write(json.dumps(unique, ensure_ascii=False))

    logger.info(f"[CDX] {outlet}/{month}: {len(unique)} unique URLs")
    return unique


# ---------------------------------------------------------------------------
# HTML fetch + cache
# ---------------------------------------------------------------------------

async def fetch_html(client, url: str, outlet: str, timestamp: str = "") -> Optional[str]:
    """Fetch and cache article HTML from Wayback. Returns cached or fetched text."""
    cache = _cache_html_path(outlet, url)
    if cache.exists():
        with gzip.open(cache, "rt", encoding="utf-8") as f:
            return f.read()

    cache.parent.mkdir(parents=True, exist_ok=True)
    fetch_url = f"https://web.archive.org/web/{timestamp}/{url}" if timestamp else \
                f"https://web.archive.org/web/*/{url}"
    try:
        resp = await client.get(fetch_url, timeout=20, follow_redirects=True)
        if resp.status_code != 200:
            return None
        html = resp.text
        with gzip.open(cache, "wt", encoding="utf-8") as f:
            f.write(html)
        return html
    except Exception as exc:
        logger.debug(f"Fetch failed {fetch_url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Day-level orchestration
# ---------------------------------------------------------------------------

async def _process_day(
    day: date,
    records_by_outlet: dict[str, list[dict]],
    fetch_sem: asyncio.Semaphore,
    min_rows_skip: int = 200,
) -> int:
    """Parse records for one day, write atomic JSONL. Returns article count."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = RAW_DIR / f"{day.isoformat()}.jsonl.gz"

    if _count_existing(jsonl_path) >= min_rows_skip:
        logger.info(f"[backfill] {day}: already has ≥{min_rows_skip} rows — skipping")
        return 0

    day_str = day.isoformat()

    # Gather all records for this day
    from scraper.outlets import get_parser  # noqa: PLC0415

    import httpx  # noqa: PLC0415

    articles: list[dict] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": BROWSER_UA},
        follow_redirects=True,
        timeout=25,
    ) as client:
        fetch_tasks = []
        for outlet, records in records_by_outlet.items():
            parser_cls = get_parser(outlet)
            if parser_cls is None:
                continue
            parser = parser_cls()

            # Filter records whose CDX timestamp is on this day
            day_records = [
                r for r in records
                if r.get("timestamp", "")[:8] == day.strftime("%Y%m%d")
                or r.get("timestamp", "") == ""  # CC records may lack timestamp
            ]
            for rec in day_records:
                fetch_tasks.append((outlet, rec, parser))

        # Fetch HTML with semaphore
        async def fetch_and_parse(outlet, rec, parser):
            url = rec.get("url", "")
            if not url:
                return None
            async with fetch_sem:
                html = await fetch_html(client, url, outlet, rec.get("timestamp", ""))
            if not html:
                return None
            try:
                art = await parser.parse(url=url, html=html)
                return art
            except Exception as exc:
                logger.debug(f"Parse error {url}: {exc}")
                return None

        parsed = await asyncio.gather(
            *[fetch_and_parse(o, r, p) for o, r, p in fetch_tasks],
            return_exceptions=True,
        )

    # Dedup by link, collect articles assigned to this day
    seen_links: set[str] = set()
    bucket: list[dict] = []
    for result in parsed:
        if isinstance(result, Exception) or result is None:
            continue
        if not result.get("title") or not result.get("content"):
            continue
        link = result.get("link", "")
        if link and link not in seen_links:
            seen_links.add(link)
            bucket.append(result)

    if not bucket:
        logger.warning(f"[backfill] {day}: 0 usable articles from {sum(len(v) for v in records_by_outlet.values())} records")
        return 0

    # Atomic write
    tmp_path = jsonl_path.with_suffix(".gz.tmp")
    with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
        for art in bucket:
            f.write(json.dumps(art, ensure_ascii=False) + "\n")
    tmp_path.rename(jsonl_path)

    logger.info(f"[backfill] {day}: wrote {len(bucket)} articles → {jsonl_path.name}")
    return len(bucket)


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

async def _run_async(
    start_date: str,
    end_date: str,
    outlets: list[str],
    day_workers: int = 4,
    fetch_workers: int = 16,
) -> None:
    start = date.fromisoformat(start_date)
    end   = date.fromisoformat(end_date)
    months = _months_in_range(start, end)

    logger.info(f"[backfill] {start} → {end} | {len(months)} months | outlets={outlets}")

    # Phase 1: batch CDX queries (one per outlet per month)
    import httpx  # noqa: PLC0415

    cdx_records: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    # cdx_records[outlet][month] = list of CDX records

    async with httpx.AsyncClient(
        headers={"User-Agent": BROWSER_UA},
        follow_redirects=True,
        timeout=60,
    ) as client:
        cdx_tasks = []
        for outlet in outlets:
            for month in months:
                cdx_tasks.append((outlet, month, fetch_cdx_month(client, outlet, month)))

        for outlet, month, coro in cdx_tasks:
            try:
                records = await coro
                cdx_records[outlet][month] = records
            except Exception as exc:
                logger.warning(f"CDX fetch failed {outlet}/{month}: {exc}")

    # Phase 2: group CDX records by day, then process days in parallel
    day_sem  = asyncio.Semaphore(day_workers)
    fetch_sem = asyncio.Semaphore(fetch_workers)

    all_days = list(_date_range(start, end))
    total = 0

    async def process_one_day(day: date) -> int:
        async with day_sem:
            records_by_outlet: dict[str, list[dict]] = {}
            for outlet in outlets:
                month = _month_key(day)
                records_by_outlet[outlet] = cdx_records[outlet].get(month, [])
            return await _process_day(day, records_by_outlet, fetch_sem)

    results = await asyncio.gather(
        *[process_one_day(d) for d in all_days],
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, int):
            total += r

    # Coverage report
    _write_coverage_report(start, end)
    logger.info(f"\n[backfill] Complete. Total articles written: {total}")


def _write_coverage_report(start: date, end: date) -> None:
    rows = []
    for day in _date_range(start, end):
        jsonl_path = RAW_DIR / f"{day.isoformat()}.jsonl.gz"
        rows.append({"date": day.isoformat(), "articles": _count_existing(jsonl_path)})
    try:
        import pandas as pd  # noqa: PLC0415
        df = pd.DataFrame(rows)
        report = ARCHIVE_DIR / "backfill_coverage.csv"
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(report, index=False)
        print(f"\n[coverage] {report}")
        print(f"  Days ≥200 articles : {(df['articles'] >= 200).sum()}")
        print(f"  Days 0 articles    : {(df['articles'] == 0).sum()}")
        print(f"  Mean articles/day  : {df['articles'].mean():.0f}")
    except ImportError:
        pass


def run(
    start_date: str,
    end_date: str,
    outlets: list[str],
    day_workers: int = 4,
    fetch_workers: int = 16,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(_run_async(start_date, end_date, outlets, day_workers, fetch_workers))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Async backfill Indian news from Wayback + CC")
    p.add_argument("--start-date",    default="2026-01-01")
    p.add_argument("--end-date",      default="2026-06-20")
    p.add_argument("--outlets",       default="TH,TOI,TIE,IT,NDTV")
    p.add_argument("--day-workers",   type=int, default=4,  help="Parallel days")
    p.add_argument("--fetch-workers", type=int, default=16, help="Parallel HTML fetches per day")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(
        start_date=args.start_date,
        end_date=args.end_date,
        outlets=[o.strip().upper() for o in args.outlets.split(",")],
        day_workers=args.day_workers,
        fetch_workers=args.fetch_workers,
    )


if __name__ == "__main__":
    main()
