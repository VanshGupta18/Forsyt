"""Platform accuracy and quality metrics for API/dashboard."""

from __future__ import annotations

import csv
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "gpr_index" / "outputs" / "validation"
VOL_CACHE = VALIDATION_DIR / "vol_metrics_cache.json"
QUALITY_REPORT_CACHE = VALIDATION_DIR / "quality_report_cache.json"
CALDARA_DAILY_CSV = VALIDATION_DIR / "caldara_daily_correlation.csv"
CORRIDOR_LEAKAGE_CSV = VALIDATION_DIR / "corridor_parent_leakage.csv"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

NIFTY_DIR = REPO_ROOT / "nifty-50"
if str(NIFTY_DIR) not in sys.path:
    sys.path.insert(0, str(NIFTY_DIR))

logger = logging.getLogger(__name__)


def _pct(num: float, den: float) -> float | None:
    if not den:
        return None
    return round(100.0 * num / den, 1)


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _corridor_fixture_accuracy(*, refresh: bool = False) -> dict:
    from news_dataset.api.cache import _MISSING, cache_get, cache_set

    if not refresh:
        hit = cache_get("metrics:corridor_fixtures", ttl_seconds=86400)
        if hit is not _MISSING:
            return hit

    from gpr_index.tests.corridor_fixtures import LABELED_CORRIDOR_ARTICLES
    from gpr_index.scripts.corridors import tag_corridors
    from news_dataset.nlp.locations import extract_locations

    passed = 0
    cases = []
    for case in LABELED_CORRIDOR_ARTICLES:
        v2 = extract_locations(case["title"], case["body"])
        actual = set(tag_corridors(v2))
        missing = case["expected"] - actual
        forbidden = case["forbidden"] & actual
        ok = not missing and not forbidden
        if ok:
            passed += 1
        cases.append({"label": case["label"], "pass": ok})
    total = len(LABELED_CORRIDOR_ARTICLES)
    result = {
        "passed": passed,
        "total": total,
        "pass_rate_pct": _pct(passed, total),
        "cases": cases,
        "description": "Hand-labelled corridor articles — location tagging accuracy",
    }
    cache_set("metrics:corridor_fixtures", result)
    return result


def _ingestion_metrics() -> dict:
    from news_dataset import db

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM articles")
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM articles WHERE tier IS NOT NULL AND duplicate_of IS NULL"
    )
    tier_total = cur.fetchone()[0]
    cur.execute(
        """SELECT COUNT(*) FROM articles WHERE tier IS NOT NULL AND duplicate_of IS NULL
           AND nlp_themes IS NOT NULL AND nlp_themes <> '' AND nlp_extracted_at IS NOT NULL"""
    )
    nlp_complete = cur.fetchone()[0]
    cur.execute(
        """SELECT COALESCE(SUM(fetched_count), 0), COALESCE(SUM(ingested_count), 0),
                  COALESCE(SUM(discarded_count), 0)
           FROM geo_cycle_stats
           WHERE run_at >= NOW() - INTERVAL '7 days'"""
    )
    fetched, ingested, discarded = cur.fetchone()
    cur.execute(
        """SELECT stage, status, COUNT(*) FROM pipeline_runs
           WHERE run_at >= NOW() - INTERVAL '30 days'
           GROUP BY stage, status ORDER BY stage, status"""
    )
    pipeline_rows = [{"stage": r[0], "status": r[1], "count": r[2]} for r in cur.fetchall()]
    cur.execute("SELECT COUNT(*) FROM gpr_daily")
    gpr_days = cur.fetchone()[0]
    cur.execute("SELECT MAX(date), MAX(updated_at) FROM gpr_daily")
    latest_gpr_date, latest_gpr_updated = cur.fetchone()
    cur.close()
    db.release_connection(conn)

    feed = db.get_geo_feed_health()
    healthy = sum(1 for h in feed.values() if (h.get("consecutive_failures") or 0) == 0)
    unhealthy = len(feed) - healthy

    return {
        "total_articles": total,
        "tier_articles": tier_total,
        "ingest_yield_7d_pct": _pct(float(ingested), float(fetched)) if fetched else None,
        "discard_rate_7d_pct": _pct(float(discarded), float(fetched)) if fetched else None,
        "fetched_7d": int(fetched),
        "ingested_7d": int(ingested),
        "sources_healthy": healthy,
        "sources_total": len(feed),
        "sources_unhealthy": unhealthy,
        "feed_health": {
            k: {
                "consecutive_failures": v.get("consecutive_failures"),
                "last_success": v.get("last_success").isoformat() if v.get("last_success") else None,
                "last_error": v.get("last_error"),
            }
            for k, v in feed.items()
        },
        "pipeline_runs_30d": pipeline_rows,
        "gpr_index_days": gpr_days,
        "gpr_latest_date": latest_gpr_date.isoformat() if latest_gpr_date else None,
        "gpr_updated_at": latest_gpr_updated.isoformat() if latest_gpr_updated else None,
        "description": "RSS scrape yield and source health (7d window for yield)",
    }


def _nlp_metrics(*, refresh_corridor: bool = False) -> dict:
    from news_dataset import db
    from news_dataset.nlp.run_extraction import NLP_MODEL_VERSION

    pending = db.count_articles_pending_nlp(NLP_MODEL_VERSION)
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM articles WHERE tier IS NOT NULL AND duplicate_of IS NULL"
    )
    tier_total = cur.fetchone()[0]
    cur.close()
    db.release_connection(conn)
    complete = max(0, tier_total - pending)
    corridor = _corridor_fixture_accuracy(refresh=refresh_corridor)
    return {
        "tier_articles": tier_total,
        "nlp_complete": complete,
        "nlp_pending": pending,
        "coverage_pct": _pct(complete, tier_total),
        "corridor_tagging": corridor,
        "description": "NLP coverage on geo-tier articles; corridor pass rate from labelled fixtures",
    }


def _gpr_benchmark_metrics() -> dict:
    rows = _read_csv_rows(CALDARA_DAILY_CSV)
    benchmarks = []
    for row in rows:
        try:
            r = float(row.get("pearson_r", "nan"))
        except ValueError:
            r = None
        benchmarks.append({
            "comparison": row.get("comparison"),
            "pearson_r": round(r, 3) if r is not None else None,
            "pass": row.get("pass") == "YES",
            "target": row.get("target"),
            "days_overlap": int(row.get("days_overlap") or 0),
        })
    ma30 = next((b for b in benchmarks if b["comparison"] == "ma30"), None)
    return {
        "benchmarks": benchmarks,
        "primary_metric": "MA30 vs Caldara GPRD_MA30",
        "caldara_ma30_r": ma30["pearson_r"] if ma30 else None,
        "caldara_ma30_pass": ma30["pass"] if ma30 else None,
        "target_r": 0.50,
        "description": "Forsyt GPR vs Caldara-Iacoviello academic benchmark (offline validation CSV)",
        "source_file": str(CALDARA_DAILY_CSV.relative_to(REPO_ROOT)) if CALDARA_DAILY_CSV.exists() else None,
    }


def _corridor_index_metrics() -> dict:
    rows = _read_csv_rows(CORRIDOR_LEAKAGE_CSV)
    passed = sum(1 for r in rows if r.get("pass") == "YES")
    total = len(rows)
    corridors = [
        {
            "corridor": r.get("corridor"),
            "parent_correlation": round(float(r["parent_correlation"]), 3),
            "pass": r.get("pass") == "YES",
        }
        for r in rows
        if r.get("corridor")
    ]
    return {
        "corridors_validated": total,
        "parent_leakage_pass_rate_pct": _pct(passed, total),
        "parent_leakage_passed": passed,
        "corridors": corridors,
        "description": "Corridor threat scores should not mirror parent GPR (>0.95 = leakage)",
        "source_file": str(CORRIDOR_LEAKAGE_CSV.relative_to(REPO_ROOT)) if CORRIDOR_LEAKAGE_CSV.exists() else None,
    }


def _compute_vol_metrics(refresh: bool = False) -> dict:
    from news_dataset.api.cache import _MISSING, cache_get, cache_set

    fallback = {
        "market_only_roc_auc": 0.831,
        "market_plus_gpr_roc_auc": 0.815,
        "gpr_incremental_roc_auc": -0.016,
        "market_only_r2_vs_persistence": None,
        "horizon_days": 5,
        "source": "published_research",
        "note": "Use GET /api/pages/quality?refresh=1 to recompute walk-forward backtest",
        "description": "Purged walk-forward HIGH_VOL classification (top 25% forward vol)",
    }

    if not refresh:
        hit = cache_get("metrics:vol", ttl_seconds=86400)
        if hit is not _MISSING:
            return hit
        if VOL_CACHE.exists():
            try:
                payload = json.loads(VOL_CACHE.read_text())
                cache_set("metrics:vol", payload)
                return payload
            except Exception:
                pass
        return fallback

    try:
        from forsyt_gpr import data, vol_model
        from news_dataset.api.gpr_service import gpr_frame_from_db_or_csv

        gf = gpr_frame_from_db_or_csv()
        nifty = data.load_price("NIFTY")
        _, clf, _ = vol_model.run_vol_experiment(
            gf, nifty, horizon=5, min_train=750, refit_every=21, verbose=False
        )
        mo = float(clf.loc["XGB[market_only]", "ROC_AUC"])
        mg = float(clf.loc["XGB[market+gpr]", "ROC_AUC"])
        payload = {
            "market_only_roc_auc": round(mo, 3),
            "market_plus_gpr_roc_auc": round(mg, 3),
            "gpr_incremental_roc_auc": round(mg - mo, 3),
            "market_only_r2_vs_persistence": None,
            "horizon_days": 5,
            "source": "walk_forward_backtest",
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "description": fallback["description"],
            "note": "Incremental GPR AUC = market+gpr minus market_only (honest geo value-add test)",
        }
        VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
        VOL_CACHE.write_text(json.dumps(payload, indent=2))
        cache_set("metrics:vol", payload)
        return payload
    except Exception as exc:
        logger.exception("vol metrics computation failed")
        note = fallback["note"]
        if "only" in str(exc) and "aligned rows" in str(exc):
            from gpr_index.scripts.paths import INDIA_GPR_INDEX_START

            note = (
                f"India GPR index starts {INDIA_GPR_INDEX_START.isoformat()}; "
                "walk-forward vol backtest needs longer aligned history. "
                "Use published_research figures until more index days exist."
            )
        out = {**fallback, "error": str(exc), "note": note}
        return out


def build_accuracy_metrics(*, refresh_vol: bool = False) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ingestion": _ingestion_metrics(),
        "nlp": _nlp_metrics(refresh_corridor=refresh_vol),
        "gpr_index": _gpr_benchmark_metrics(),
        "corridors": _corridor_index_metrics(),
        "nifty_volatility": _compute_vol_metrics(refresh=refresh_vol),
        "disclaimer": (
            "Metrics mix live DB telemetry with offline benchmark validation. "
            "They measure pipeline health and research-backed accuracy — not investment performance."
        ),
    }


# ---------------------------------------------------------------------------
# Quality report (trust-first schema for /api/quality)
# ---------------------------------------------------------------------------

STATISTICAL_PROPERTIES_CSV = VALIDATION_DIR / "statistical_properties_ma30.csv"
EVENT_SPIKE_CSV = VALIDATION_DIR / "event_spike_analysis.csv"
CORRIDOR_EVENT_CSV = VALIDATION_DIR / "corridor_event_response.csv"
CORRIDOR_DISCRIMINATION_CSV = VALIDATION_DIR / "corridor_discrimination.csv"
GAP_IMPUTATION_CSV = VALIDATION_DIR / "gap_imputation_report.csv"

METHODOLOGY_STEPS = [
    {
        "step": 1,
        "title": "Source ingestion",
        "body": "RSS and GDELT geo-tier articles, deduplicated and tier-scored daily.",
        "layer": "source",
    },
    {
        "step": 2,
        "title": "NLP classification",
        "body": "Event themes, locations, and corridor tagging across 12 India-relevant trade routes.",
        "layer": "processing",
    },
    {
        "step": 3,
        "title": "Index construction",
        "body": "India GPR daily index plus corridor threat × exposure scores (energy and goods vectors).",
        "layer": "index",
    },
    {
        "step": 4,
        "title": "Validation",
        "body": "Caldara benchmark, event spikes, corridor fixture tests, and walk-forward NIFTY vol backtest.",
        "layer": "validation",
    },
]

QUALITY_DISCLAIMER = (
    "Metrics mix live DB telemetry with offline benchmark validation. "
    "They measure pipeline health and research-backed accuracy — not investment performance."
)


def _csv_source(path: Path) -> dict | None:
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return {
        "type": "csv",
        "path": str(path.relative_to(REPO_ROOT)),
        "updated_at": mtime.isoformat(),
    }


def _pass_flag_to_status(flag: str | None) -> str:
    if flag is None or str(flag).strip().upper() in {"", "N/A", "NA"}:
        return "na"
    return "pass" if str(flag).strip().upper() == "YES" else "fail"



def _make_check(
    *,
    id: str,
    category: str,
    title: str,
    value: str | float | int | None,
    threshold: str,
    status: str,
    why: str,
    tier: str = "detail",
    freshness: str = "offline",
    validated_at: str | None = None,
    source: dict | None = None,
    detail: dict | None = None,
) -> dict:
    return {
        "id": id,
        "category": category,
        "title": title,
        "value": value,
        "threshold": threshold,
        "status": status,
        "why": why,
        "tier": tier,
        "freshness": freshness,
        "validated_at": validated_at,
        "source": source,
        "detail": detail,
    }


def _validation_artifacts_as_of() -> str | None:
    mtimes: list[float] = []
    for path in (
        CALDARA_DAILY_CSV,
        CORRIDOR_LEAKAGE_CSV,
        STATISTICAL_PROPERTIES_CSV,
        EVENT_SPIKE_CSV,
        CORRIDOR_EVENT_CSV,
        CORRIDOR_DISCRIMINATION_CSV,
        GAP_IMPUTATION_CSV,
        VOL_CACHE,
    ):
        if path.exists():
            mtimes.append(path.stat().st_mtime)
    if not mtimes:
        return None
    return datetime.fromtimestamp(max(mtimes), tz=timezone.utc).isoformat()


def _canonical_live_gpr() -> dict:
    """Align quality page GPR stats with dashboard canonical frame."""
    out = {
        "gpr_latest_date": None,
        "gpr_index_days": 0,
        "live_gpr_source": None,
    }
    try:
        from news_dataset.api.gpr_service import get_gpr_current, gpr_frame_from_db_or_csv

        current = get_gpr_current()
        if current and current.get("date"):
            out["gpr_latest_date"] = str(current["date"])[:10]
            out["live_gpr_source"] = current.get("data_source") or "db"
        try:
            frame = gpr_frame_from_db_or_csv()
            if not frame.empty:
                out["gpr_index_days"] = int(len(frame))
                if not out["gpr_latest_date"]:
                    out["gpr_latest_date"] = frame.index.max().strftime("%Y-%m-%d")
        except Exception:
            pass
    except Exception as exc:
        logger.warning("canonical gpr stats unavailable: %s", exc)
    return out


def _apply_staleness(checks: list[dict], *, live_index_through: str | None, artifacts_as_of: str | None) -> list[dict]:
    if not live_index_through or not artifacts_as_of:
        return checks
    try:
        live_day = datetime.fromisoformat(str(live_index_through)[:10]).date()
        artifact_day = datetime.fromisoformat(str(artifacts_as_of)[:10]).date()
        stale = artifact_day < live_day
    except ValueError:
        stale = False
    if not stale:
        return checks
    updated = []
    for c in checks:
        row = dict(c)
        if row.get("freshness") == "offline" and row.get("tier") == "headline":
            row["freshness"] = "stale"
            if row.get("status") == "pass":
                row["status"] = "warn"
        updated.append(row)
    return updated


def _build_report_meta(*, live_gpr: dict, cached_at: str | None = None) -> dict:
    artifacts_as_of = _validation_artifacts_as_of()
    live_through = live_gpr.get("gpr_latest_date")
    is_stale = False
    stale_reason = None
    if artifacts_as_of and live_through:
        try:
            a = datetime.fromisoformat(artifacts_as_of.replace("Z", "+00:00"))
            l = datetime.fromisoformat(str(live_through)[:10])
            if a.date() < l.date():
                is_stale = True
                stale_reason = (
                    "Offline benchmarks predate the current index. "
                    "Re-run validate after index rebuild."
                )
        except ValueError:
            pass
    return {
        "cached_at": cached_at,
        "validation_artifacts_as_of": artifacts_as_of,
        "live_index_through": live_through,
        "live_gpr_source": live_gpr.get("live_gpr_source"),
        "is_stale": is_stale,
        "stale_reason": stale_reason,
    }


def _checks_from_caldara() -> list[dict]:
    rows = _read_csv_rows(CALDARA_DAILY_CSV)
    if not rows:
        return []
    source = _csv_source(CALDARA_DAILY_CSV)
    labels = {
        "ma30": ("Caldara MA30 correlation", "Primary academic benchmark — 30-day moving average vs Caldara GPRD_MA30", "headline"),
        "ma7": ("Caldara MA7 correlation", "Short-horizon tracking vs Caldara GPRD_MA7", "detail"),
        "raw_daily": ("Caldara raw daily correlation", "Unsmoothed daily series — expected to underperform; smoothing is intentional", "informational"),
    }
    checks = []
    for row in rows:
        comp = row.get("comparison", "")
        label, why, tier = labels.get(comp, (f"Caldara {comp}", "Pearson correlation vs Caldara-Iacoviello benchmark", "detail"))
        try:
            r_val = float(row.get("pearson_r", "nan"))
            value = round(r_val, 3) if r_val == r_val else None
        except ValueError:
            value = None
        validated = source.get("updated_at") if source else None
        checks.append(
            _make_check(
                id=f"gpr_caldara_{comp}",
                category="gpr",
                title=label,
                value=value,
                threshold=str(row.get("target") or "> 0.50"),
                status=_pass_flag_to_status(row.get("pass")),
                why=why,
                tier=tier,
                freshness="offline",
                validated_at=validated,
                source=source,
                detail={"comparison": comp, "days_overlap": row.get("days_overlap"), "spearman_r": row.get("spearman_r")},
            )
        )
    return checks


def _checks_from_statistical_properties() -> list[dict]:
    rows = _read_csv_rows(STATISTICAL_PROPERTIES_CSV)
    if not rows:
        return []
    source = _csv_source(STATISTICAL_PROPERTIES_CSV)
    checks = []
    for row in rows:
        metric = row.get("metric", "")
        checks.append(
            _make_check(
                id=f"gpr_stat_{metric}",
                category="gpr",
                title=f"GPR MA30 {metric}",
                value=row.get("value"),
                threshold=str(row.get("target") or ""),
                status=_pass_flag_to_status(row.get("pass")),
                why=f"Index statistical property on {row.get('series', 'gpr_30ma')} — compared to literature targets.",
                tier="detail",
                freshness="offline",
                validated_at=source.get("updated_at") if source else None,
                source=source,
                detail=dict(row),
            )
        )
    return checks


def _checks_from_event_spikes() -> list[dict]:
    rows = _read_csv_rows(EVENT_SPIKE_CSV)
    if not rows:
        return []
    source = _csv_source(EVENT_SPIKE_CSV)
    checks = []
    for i, row in enumerate(rows):
        event = row.get("event", f"event_{i}")
        slug = re.sub(r"[^a-z0-9]+", "_", event.lower()).strip("_")[:40]
        try:
            z = float(row.get("z_score", "nan"))
            z_val = round(z, 3) if z == z else None
        except ValueError:
            z_val = None
        checks.append(
            _make_check(
                id=f"gpr_event_spike_{slug}",
                category="gpr",
                title=f"Event spike: {event}",
                value=z_val,
                threshold="z > 1.0",
                status=_pass_flag_to_status(row.get("pass")),
                why="Known high-GPR event should produce a statistically significant index spike.",
                tier="detail",
                freshness="offline",
                validated_at=source.get("updated_at") if source else None,
                source=source,
                detail=dict(row),
            )
        )
    return checks


def _checks_from_corridor_leakage() -> list[dict]:
    rows = _read_csv_rows(CORRIDOR_LEAKAGE_CSV)
    if not rows:
        return []
    source = _csv_source(CORRIDOR_LEAKAGE_CSV)
    passed = sum(1 for r in rows if r.get("pass") == "YES")
    total = len(rows)
    corridors = [
        {
            "corridor": r.get("corridor"),
            "parent_correlation": round(float(r["parent_correlation"]), 3),
            "pass": r.get("pass") == "YES",
        }
        for r in rows
        if r.get("corridor")
    ]
    return [
        _make_check(
            id="corridor_parent_leakage",
            category="corridor",
            title="Corridor parent leakage",
            value=f"{passed}/{total}",
            threshold="r < 0.95 vs parent GPR",
            status="pass" if passed == total and total else "fail",
            why="Corridor threat scores must reflect route geography, not mirror the parent India GPR index.",
            tier="headline",
            freshness="offline",
            validated_at=source.get("updated_at") if source else None,
            source=source,
            detail={"corridors": corridors},
        )
    ]


def _checks_from_corridor_events() -> list[dict]:
    rows = _read_csv_rows(CORRIDOR_EVENT_CSV)
    if not rows:
        return []
    source = _csv_source(CORRIDOR_EVENT_CSV)
    checks = []
    for i, row in enumerate(rows):
        event = row.get("event", f"event_{i}")
        slug = re.sub(r"[^a-z0-9]+", "_", event.lower()).strip("_")[:40]
        z_raw = row.get("z_score", "")
        try:
            z = float(z_raw)
            z_val = round(z, 3) if z == z else None
        except (ValueError, TypeError):
            z_val = None
        checks.append(
            _make_check(
                id=f"corridor_event_{slug}",
                category="corridor",
                title=f"Corridor event response: {event}",
                value=z_val if z_val is not None else "N/A",
                threshold="z > 1.0",
                status=_pass_flag_to_status(row.get("pass")),
                why=f"Event corridor ({row.get('corridor')}) should spike on the shock date.",
                tier="detail",
                freshness="offline",
                validated_at=source.get("updated_at") if source else None,
                source=source,
                detail=dict(row),
            )
        )
    return checks


def _checks_from_corridor_discrimination() -> list[dict]:
    rows = _read_csv_rows(CORRIDOR_DISCRIMINATION_CSV)
    if not rows:
        return []
    source = _csv_source(CORRIDOR_DISCRIMINATION_CSV)
    checks = []
    for i, row in enumerate(rows):
        event = row.get("event", f"event_{i}")
        slug = re.sub(r"[^a-z0-9]+", "_", event.lower()).strip("_")[:40]
        diff_raw = row.get("z_differential", "")
        try:
            diff = float(diff_raw)
            diff_val = round(diff, 3) if diff == diff else None
        except (ValueError, TypeError):
            diff_val = None
        checks.append(
            _make_check(
                id=f"corridor_disc_{slug}",
                category="corridor",
                title=f"Corridor discrimination: {event}",
                value=diff_val if diff_val is not None else "N/A",
                threshold="target z > strongest other",
                status=_pass_flag_to_status(row.get("pass")),
                why="The intended corridor should move more than unrelated corridors on the event day.",
                tier="detail",
                freshness="offline",
                validated_at=source.get("updated_at") if source else None,
                source=source,
                detail=dict(row),
            )
        )
    return checks


def _check_gap_imputation() -> list[dict]:
    rows = _read_csv_rows(GAP_IMPUTATION_CSV)
    if not rows:
        return []
    source = _csv_source(GAP_IMPUTATION_CSV)
    methods = {r.get("impute_method") for r in rows if r.get("impute_method")}
    return [
        _make_check(
            id="gpr_gap_imputation",
            category="gpr",
            title="Gap imputation transparency",
            value=len(rows),
            threshold="documented method per gap day",
            status="pass",
            why=f"Missing GKG days imputed with declared method(s): {', '.join(sorted(methods)) or 'unknown'}.",
            tier="informational",
            freshness="offline",
            validated_at=source.get("updated_at") if source else None,
            source=source,
            detail={"gap_days": len(rows), "methods": sorted(methods), "sample": rows[:5]},
        )
    ]


def _checks_from_vol_metrics(vol: dict) -> list[dict]:
    source_path = VOL_CACHE if VOL_CACHE.exists() else None
    is_published = vol.get("source") == "published_research"
    freshness = "offline" if is_published else "live"
    validated = vol.get("computed_at") or (source_path and _csv_source(source_path).get("updated_at") if source_path else None)
    source = (
        {"type": "computed", "path": str(source_path.relative_to(REPO_ROOT)) if source_path else None, "updated_at": validated}
        if source_path or is_published
        else {"type": "computed", "path": None}
    )
    incr = vol.get("gpr_incremental_roc_auc")
    incr_status = "na"
    if incr is not None and not is_published:
        incr_status = "pass" if incr > 0 else "warn"
    elif is_published:
        incr_status = "na"
    suffix = " (published baseline — not live)" if is_published else ""
    checks = [
        _make_check(
            id="market_vol_market_only",
            category="market",
            title=f"NIFTY vol — market-only ROC-AUC{suffix}",
            value=vol.get("market_only_roc_auc"),
            threshold=f"{vol.get('horizon_days', 5)}d HIGH_VOL horizon",
            status="na",
            why="Baseline walk-forward classification using market features only.",
            tier="informational",
            freshness=freshness,
            validated_at=validated if isinstance(validated, str) else None,
            source=source,
            detail=vol,
        ),
        _make_check(
            id="market_vol_market_plus_gpr",
            category="market",
            title=f"NIFTY vol — market + GPR ROC-AUC{suffix}",
            value=vol.get("market_plus_gpr_roc_auc"),
            threshold=f"{vol.get('horizon_days', 5)}d HIGH_VOL horizon",
            status="na",
            why="Combined model including India GPR features.",
            tier="informational",
            freshness=freshness,
            validated_at=validated if isinstance(validated, str) else None,
            source=source,
        ),
        _make_check(
            id="market_vol_gpr_incremental",
            category="market",
            title=f"NIFTY vol — GPR incremental AUC{suffix}",
            value=incr,
            threshold="> 0 (value-add vs market-only)",
            status=incr_status,
            why="Honest test: does GPR improve HIGH_VOL classification beyond market features alone?",
            tier="headline" if not is_published else "informational",
            freshness=freshness,
            validated_at=validated if isinstance(validated, str) else None,
            source=source,
            detail={"note": vol.get("note"), "source": vol.get("source")},
        ),
    ]
    return checks


def _checks_from_pipeline(ingestion: dict, nlp: dict) -> list[dict]:
    checks = []
    unhealthy = ingestion.get("sources_unhealthy") or 0
    total_sources = ingestion.get("sources_total") or 0
    checks.append(
        _make_check(
            id="pipeline_source_health",
            category="pipeline",
            title="News source health",
            value=f"{ingestion.get('sources_healthy', 0)}/{total_sources}",
            threshold="0 failing sources",
            status="pass" if unhealthy == 0 and total_sources else ("fail" if unhealthy else "na"),
            why="All RSS/geo feeds should be ingesting without consecutive failures.",
            tier="headline",
            freshness="live",
            source={"type": "db"},
        )
    )
    yield_pct = ingestion.get("ingest_yield_7d_pct")
    checks.append(
        _make_check(
            id="pipeline_ingest_yield",
            category="pipeline",
            title="7-day ingest yield",
            value=f"{yield_pct}%" if yield_pct is not None else None,
            threshold="stable scrape yield",
            status="na",
            why=f"{ingestion.get('ingested_7d', 0)}/{ingestion.get('fetched_7d', 0)} articles ingested in the last 7 days.",
            tier="detail",
            freshness="live",
            source={"type": "db"},
        )
    )
    coverage = nlp.get("coverage_pct")
    checks.append(
        _make_check(
            id="pipeline_nlp_coverage",
            category="pipeline",
            title="NLP coverage",
            value=f"{coverage}%" if coverage is not None else None,
            threshold="≥ 95%",
            status="pass" if coverage is not None and coverage >= 95 else ("fail" if coverage is not None else "na"),
            why=f"{nlp.get('nlp_complete', 0)} / {nlp.get('tier_articles', 0)} geo-tier articles with completed NLP.",
            tier="headline",
            freshness="live",
            source={"type": "db"},
        )
    )
    corridor = nlp.get("corridor_tagging") or {}
    fixture_rate = corridor.get("pass_rate_pct")
    checks.append(
        _make_check(
            id="nlp_corridor_fixtures",
            category="nlp",
            title="Corridor fixture tagging",
            value=f"{fixture_rate}%" if fixture_rate is not None else None,
            threshold="100% on labelled cases",
            status="pass" if fixture_rate == 100 else ("fail" if fixture_rate is not None else "na"),
            why="Hand-labelled corridor articles — location tagging accuracy on the production NLP path.",
            tier="headline",
            freshness="live",
            source={"type": "computed"},
            detail={"cases": corridor.get("cases"), "passed": corridor.get("passed"), "total": corridor.get("total")},
        )
    )
    return checks


def _checks_from_validation_csvs() -> list[dict]:
    checks: list[dict] = []
    checks.extend(_checks_from_caldara())
    checks.extend(_checks_from_statistical_properties())
    checks.extend(_checks_from_event_spikes())
    checks.extend(_check_gap_imputation())
    checks.extend(_checks_from_corridor_leakage())
    checks.extend(_checks_from_corridor_events())
    checks.extend(_checks_from_corridor_discrimination())
    return checks


def _compute_summary(checks: list[dict]) -> dict:
    """Full summary (all checks) — kept for technical view."""
    passing = sum(1 for c in checks if c["status"] == "pass")
    failing = sum(1 for c in checks if c["status"] == "fail")
    na = sum(1 for c in checks if c["status"] == "na")
    warn = sum(1 for c in checks if c["status"] == "warn")
    total = len(checks)
    if failing > 0:
        overall = "fail"
    elif warn > 0:
        overall = "warn"
    elif passing > 0 and failing == 0:
        overall = "pass"
    else:
        overall = "warn"
    headline = _compute_headline_summary(checks)
    return {
        "checks_total": total,
        "checks_passing": passing,
        "checks_failing": failing,
        "checks_na": na,
        "checks_warn": warn,
        "overall_status": overall,
        "headline": headline,
    }


def _compute_headline_summary(checks: list[dict]) -> dict:
    scored = [c for c in checks if c.get("tier") == "headline" and c["status"] != "na"]
    passing = sum(1 for c in scored if c["status"] == "pass")
    failing = sum(1 for c in scored if c["status"] == "fail")
    warn = sum(1 for c in scored if c["status"] == "warn")
    total = len(scored)
    if total == 0:
        overall = "warn"
    elif failing > 0:
        overall = "fail"
    elif warn > 0:
        overall = "warn"
    elif passing == total:
        overall = "pass"
    else:
        overall = "warn"
    return {
        "checks_total": total,
        "checks_passing": passing,
        "checks_failing": failing,
        "checks_warn": warn,
        "overall_status": overall,
    }


def _coverage_stats(ingestion: dict, summary: dict) -> list[dict]:
    try:
        from gpr_index.scripts.corridors import CORRIDORS

        corridor_count = len(CORRIDORS)
    except Exception:
        corridor_count = ingestion.get("corridors_validated") or 12

    headline = summary.get("headline") or summary
    return [
        {
            "id": "articles",
            "label": "Articles indexed",
            "value": ingestion.get("total_articles") or 0,
            "status": None,
        },
        {
            "id": "gpr_days",
            "label": "Days of risk data",
            "value": ingestion.get("gpr_index_days") or 0,
            "status": None,
        },
        {
            "id": "corridors",
            "label": "Trade routes",
            "value": corridor_count,
            "status": None,
        },
        {
            "id": "checks_passing",
            "label": "Key checks passing",
            "value": f"{headline.get('checks_passing', 0)}/{headline.get('checks_total', 0)}",
            "status": headline.get("overall_status"),
        },
    ]


def _write_quality_cache(report: dict) -> None:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    QUALITY_REPORT_CACHE.write_text(json.dumps(report, default=str), encoding="utf-8")


def _read_quality_cache() -> dict | None:
    if not QUALITY_REPORT_CACHE.exists():
        return None
    try:
        return json.loads(QUALITY_REPORT_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None


def warm_quality_report_cache(*, refresh: bool = False) -> dict:
    """Build and persist quality report (pipeline / manual refresh)."""
    from news_dataset.api.cache import cache_get, cache_invalidate_prefix, cache_set, _MISSING

    report = _build_quality_report_uncached(refresh=refresh)
    _write_quality_cache(report)
    cache_invalidate_prefix("quality:report")
    cache_set("quality:report", report)
    return report


def build_quality_report(*, refresh: bool = False) -> dict:
    """Trust-first quality report for the Platform Quality page."""
    from news_dataset.api.cache import cache_get, cache_set, _MISSING

    if not refresh:
        mem = cache_get("quality:report", ttl_seconds=1800)
        if mem is not _MISSING:
            return mem
        disk = _read_quality_cache()
        if disk is not None:
            cache_set("quality:report", disk)
            return disk

    try:
        report = _build_quality_report_uncached(refresh=refresh)
    except Exception:
        logger.exception("quality report build failed")
        disk = _read_quality_cache()
        if disk is not None:
            cache_set("quality:report", disk)
            return disk
        report = _quality_report_fallback(
            "Quality report could not be rebuilt — showing last known offline checks only."
        )

    _write_quality_cache(report)
    cache_set("quality:report", report)
    return report


def _quality_report_fallback(note: str) -> dict:
    checks = _checks_from_validation_csvs()
    summary = _compute_summary(checks)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": {"gpr_latest_date": None, "pipeline_last_run": None},
        "summary": summary,
        "coverage": _coverage_stats({}, summary),
        "checks": checks,
        "pipeline": {
            "ingestion": {"description": note, "total_articles": 0, "tier_articles": 0},
            "nlp": {"description": note, "tier_articles": 0, "nlp_pending": 0},
            "stages_30d": [],
        },
        "methodology": METHODOLOGY_STEPS,
        "disclaimer": QUALITY_DISCLAIMER,
    }


def _build_quality_report_uncached(*, refresh: bool = False) -> dict:
    """Assemble quality report without read-through cache."""
    try:
        ingestion = _ingestion_metrics()
    except Exception as exc:
        logger.warning("ingestion metrics unavailable: %s", exc)
        ingestion = {
            "total_articles": 0,
            "tier_articles": 0,
            "sources_healthy": 0,
            "sources_total": 0,
            "sources_unhealthy": 0,
            "feed_health": {},
            "gpr_index_days": 0,
            "gpr_latest_date": None,
            "gpr_updated_at": None,
            "pipeline_runs_30d": [],
            "description": "Database unavailable — showing offline validation only",
        }
    try:
        nlp = _nlp_metrics(refresh_corridor=refresh)
    except Exception as exc:
        logger.warning("nlp metrics unavailable: %s", exc)
        nlp = {
            "tier_articles": 0,
            "nlp_complete": 0,
            "nlp_pending": 0,
            "coverage_pct": None,
            "corridor_tagging": {"passed": 0, "total": 0, "pass_rate_pct": None, "cases": []},
            "description": "Database unavailable",
        }
    vol = _compute_vol_metrics(refresh=refresh)

    live_gpr = _canonical_live_gpr()
    if live_gpr.get("gpr_latest_date"):
        ingestion["gpr_latest_date"] = live_gpr["gpr_latest_date"]
    if live_gpr.get("gpr_index_days"):
        ingestion["gpr_index_days"] = live_gpr["gpr_index_days"]
    ingestion["live_gpr_source"] = live_gpr.get("live_gpr_source")

    checks = _checks_from_validation_csvs()
    checks.extend(_checks_from_vol_metrics(vol))
    checks.extend(_checks_from_pipeline(ingestion, nlp))

    report_meta = _build_report_meta(live_gpr=live_gpr, cached_at=datetime.now(timezone.utc).isoformat())
    checks = _apply_staleness(
        checks,
        live_index_through=report_meta.get("live_index_through"),
        artifacts_as_of=report_meta.get("validation_artifacts_as_of"),
    )

    summary = _compute_summary(checks)
    coverage = _coverage_stats(ingestion, summary)

    pipeline_last_run = ingestion.get("gpr_updated_at")
    try:
        from news_dataset import db

        last_run = db.get_last_pipeline_run("platform_refresh") or db.get_last_pipeline_run("daily_index")
        if last_run:
            pipeline_last_run = last_run.isoformat() if hasattr(last_run, "isoformat") else str(last_run)
    except Exception:
        pass

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": {
            "gpr_latest_date": ingestion.get("gpr_latest_date"),
            "pipeline_last_run": pipeline_last_run,
        },
        "report_meta": report_meta,
        "summary": summary,
        "coverage": coverage,
        "checks": checks,
        "pipeline": {
            "ingestion": ingestion,
            "nlp": nlp,
            "stages_30d": ingestion.get("pipeline_runs_30d") or [],
        },
        "methodology": METHODOLOGY_STEPS,
        "disclaimer": QUALITY_DISCLAIMER,
    }
