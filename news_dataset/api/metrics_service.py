"""Platform accuracy and quality metrics for API/dashboard."""

from __future__ import annotations

import csv
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "gpr_index" / "outputs" / "validation"
VOL_CACHE = VALIDATION_DIR / "vol_metrics_cache.json"
CALDARA_DAILY_CSV = VALIDATION_DIR / "caldara_daily_correlation.csv"
CORRIDOR_LEAKAGE_CSV = VALIDATION_DIR / "corridor_parent_leakage.csv"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

NIFTY_DIR = REPO_ROOT / "nifty-50"
if str(NIFTY_DIR) not in sys.path:
    sys.path.insert(0, str(NIFTY_DIR))

logger = logging.getLogger(__name__)

_vol_cache: dict | None = None
_corridor_cache: dict | None = None


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
    global _corridor_cache
    if not refresh and _corridor_cache is not None:
        return _corridor_cache

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
    _corridor_cache = {
        "passed": passed,
        "total": total,
        "pass_rate_pct": _pct(passed, total),
        "cases": cases,
        "description": "Hand-labelled corridor articles — location tagging accuracy",
    }
    return _corridor_cache


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
    conn.close()

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
    conn.close()
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
    global _vol_cache
    if not refresh and _vol_cache:
        return _vol_cache
    if not refresh and VOL_CACHE.exists():
        try:
            _vol_cache = json.loads(VOL_CACHE.read_text())
            return _vol_cache
        except Exception:
            pass

    fallback = {
        "market_only_roc_auc": 0.831,
        "market_plus_gpr_roc_auc": 0.815,
        "gpr_incremental_roc_auc": -0.016,
        "market_only_r2_vs_persistence": None,
        "horizon_days": 5,
        "source": "published_research",
        "note": "Run GET /api/metrics/accuracy?refresh_vol=1 to recompute walk-forward backtest",
        "description": "Purged walk-forward HIGH_VOL classification (top 25% forward vol)",
    }

    if not refresh:
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
        _vol_cache = payload
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
