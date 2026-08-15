"""Data access layer for Forsyt product API (DB with CSV fallbacks)."""

from __future__ import annotations

import logging
import math
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
NIFTY_DIR = REPO_ROOT / "nifty-50"
GPR_OUTPUT = REPO_ROOT / "gpr_index" / "outputs"

if str(NIFTY_DIR) not in sys.path:
    sys.path.insert(0, str(NIFTY_DIR))

from gpr_index.scripts.corridor_index import CORRIDOR_SCORE_DISCLAIMER  # noqa: E402
from gpr_index.scripts.corridors import corridor_metadata  # noqa: E402
from gpr_index.scripts.paths import INDIA_GPR_INDEX_START  # noqa: E402
from news_dataset import db  # noqa: E402

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_MINUTES = 60
_STALE_AFTER = timedelta(hours=24)


def _allow_csv_fallback() -> bool:
    return os.environ.get("ALLOW_CSV_FALLBACK", "").strip().lower() in ("1", "true", "yes")


def _database_configured() -> bool:
    return bool(os.environ.get("DATABASE_URL", "").strip())


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stale_warning_for_date(value) -> str | None:
    if not value:
        return "No index data available"
    try:
        day = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    age = datetime.now(timezone.utc) - datetime.combine(day, time.max, tzinfo=timezone.utc)
    if age > _STALE_AFTER:
        return f"Data through {day.isoformat()} is more than 24h old"
    return None


def _with_refresh_meta(payload: dict, *, data_source: str, as_of_date=None) -> dict:
    out = {**payload}
    out["data_source"] = data_source
    out["updated_at"] = _utc_now_iso()
    out["refresh_interval_minutes"] = REFRESH_INTERVAL_MINUTES
    warning = _stale_warning_for_date(as_of_date or out.get("date"))
    if warning:
        out["stale_warning"] = warning
    return out


def _serialize_pipeline_run(row: dict | None) -> dict | None:
    if not row:
        return None
    out = dict(row)
    run_at = out.get("run_at")
    if hasattr(run_at, "isoformat"):
        out["run_at"] = run_at.isoformat()
    return out

_INDEX_START_TS = pd.Timestamp(INDIA_GPR_INDEX_START)


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _valid_gpr_index(value) -> bool:
    if value is None:
        return False
    try:
        num = float(value)
    except (TypeError, ValueError):
        return False
    return not (math.isnan(num) or math.isinf(num))


def serialize_rows(rows: list[dict]) -> list[dict]:
    return [{key: _serialize(val) for key, val in row.items()} for row in rows]


def _load_gpr_csv() -> pd.DataFrame:
    path = GPR_OUTPUT / "gpr_daily_index.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    return frame[frame.index >= _INDEX_START_TS]


def _load_corridor_csv() -> pd.DataFrame:
    path = GPR_OUTPUT / "gpr_corridor_daily.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, parse_dates=["date"])
    return frame[frame["date"] >= _INDEX_START_TS]


def _csv_current_payload() -> dict | None:
    csv = _load_gpr_csv()
    if csv.empty:
        return None
    latest = csv.iloc[-1]
    idx = csv.index[-1]
    return {
        "date": idx.strftime("%Y-%m-%d"),
        "gpr_index": float(latest["gpr_index"]),
        "gpr_7ma": float(latest.get("gpr_7ma", latest["gpr_index"])),
        "gpr_30ma": float(latest.get("gpr_30ma", latest["gpr_index"])),
        "gpr_acts_index": float(latest.get("gpr_acts_index", 0)),
        "gpr_threats_index": float(latest.get("gpr_threats_index", 0)),
        "total_articles": int(latest.get("total_articles", 0)),
        "positive_share": float(latest.get("positive_share", 0)),
    }


def _prefer_csv_gpr(db_frame: pd.DataFrame, csv_frame: pd.DataFrame) -> bool:
    """Prefer pipeline CSV when Postgres is missing days or still has CI 100 artifacts."""
    if _database_configured() and not _allow_csv_fallback():
        return False
    if csv_frame.empty:
        return False
    if db_frame.empty:
        return True
    if csv_frame.index.max() > db_frame.index.max():
        return True
    overlap = db_frame.index.intersection(csv_frame.index)
    for day in overlap:
        db_val = float(db_frame.loc[day, "gpr"])
        csv_val = float(csv_frame.loc[day, "gpr"])
        if abs(db_val - csv_val) > 0.5:
            return True
    return False


def gpr_frame_from_db_or_csv() -> pd.DataFrame:
    """Canonical GPR frame for dual-signal and charts."""
    from forsyt_gpr.data import as_gpr_frame

    rows = db.get_gpr_history(limit=5000)
    csv = _load_gpr_csv()
    csv_frame = (
        as_gpr_frame(
            csv,
            gpr="gpr_index",
            threats="gpr_threats_index",
            acts="gpr_acts_index",
        )
        if not csv.empty
        else pd.DataFrame()
    )

    if rows:
        frame = pd.DataFrame(rows)
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date").sort_index()
        db_frame = as_gpr_frame(
            frame,
            gpr="gpr_index",
            threats="gpr_threats_index",
            acts="gpr_acts_index",
        )
        if _prefer_csv_gpr(db_frame, csv_frame):
            if csv_frame.empty:
                raise ValueError(
                    f"No India GPR index on or after {INDIA_GPR_INDEX_START.isoformat()}. "
                    "Run daily_index and export.to_db first."
                )
            return csv_frame
        return db_frame

    if csv_frame.empty:
        raise ValueError(
            f"No India GPR index on or after {INDIA_GPR_INDEX_START.isoformat()}. "
            "Run daily_index and export.to_db first."
        )
    return csv_frame


def get_gpr_current() -> dict | None:
    row = db.get_gpr_current()
    csv_payload = _csv_current_payload() if _allow_csv_fallback() or not _database_configured() else None
    if row and csv_payload and _allow_csv_fallback():
        db_date = str(row.get("date"))[:10]
        csv_date = csv_payload["date"]
        db_gpr = row.get("gpr_index")
        csv_gpr = csv_payload.get("gpr_index")
        if csv_date > db_date:
            return _with_refresh_meta(csv_payload, data_source="csv", as_of_date=csv_date)
        if (
            csv_date == db_date
            and db_gpr is not None
            and csv_gpr is not None
            and abs(float(db_gpr) - float(csv_gpr)) > 0.5
        ):
            return _with_refresh_meta(csv_payload, data_source="csv", as_of_date=csv_date)
    if row:
        serialized = serialize_rows([row])[0]
        return _with_refresh_meta(serialized, data_source="postgres", as_of_date=serialized.get("date"))
    if csv_payload:
        return _with_refresh_meta(csv_payload, data_source="csv", as_of_date=csv_payload.get("date"))
    return None


def _gpr_history_from_csv(
    start: str | None = None,
    end: str | None = None,
    limit: int = 500,
) -> list[dict]:
    csv = _load_gpr_csv()
    if csv.empty or "gpr_index" not in csv.columns:
        return []
    csv = csv.dropna(subset=["gpr_index"])
    csv = csv[csv.index >= _INDEX_START_TS]
    if start:
        csv = csv[csv.index >= pd.Timestamp(start)]
    if end:
        csv = csv[csv.index <= pd.Timestamp(end)]
    csv = csv.tail(limit)
    out = []
    for idx, row in csv.iterrows():
        gpr = row.get("gpr_index")
        if not _valid_gpr_index(gpr):
            continue
        out.append(
            {
                "date": idx.strftime("%Y-%m-%d"),
                "gpr_index": float(gpr),
                "gpr_7ma": float(row["gpr_7ma"]) if _valid_gpr_index(row.get("gpr_7ma")) else None,
                "gpr_30ma": float(row["gpr_30ma"]) if _valid_gpr_index(row.get("gpr_30ma")) else None,
            }
        )
    return out


def get_gpr_history(start: str | None = None, end: str | None = None, limit: int = 500) -> list[dict]:
    csv_history = _gpr_history_from_csv(start=start, end=end, limit=limit)
    rows = db.get_gpr_history(start=start, end=end, limit=limit)
    if rows:
        ordered = list(reversed(rows))
        cleaned = [row for row in ordered if _valid_gpr_index(row.get("gpr_index"))]
        if cleaned:
            if csv_history:
                from forsyt_gpr.data import as_gpr_frame

                db_frame = pd.DataFrame(cleaned)
                db_frame["date"] = pd.to_datetime(db_frame["date"])
                db_frame = as_gpr_frame(
                    db_frame.set_index("date"),
                    gpr="gpr_index",
                    threats="gpr_threats_index",
                    acts="gpr_acts_index",
                )
                csv = _load_gpr_csv()
                if not csv.empty:
                    csv_frame = as_gpr_frame(
                        csv,
                        gpr="gpr_index",
                        threats="gpr_threats_index",
                        acts="gpr_acts_index",
                    )
                    if _prefer_csv_gpr(db_frame, csv_frame):
                        return csv_history
            return serialize_rows(cleaned)
    return csv_history


def _corridor_action_label(risk: float | None, score_status: str | None = None) -> str:
    if score_status == "insufficient_history":
        return "Calibrating"
    value = float(risk or 0)
    if value >= 50:
        return "Avoid new bookings"
    if value >= 20:
        return "Monitor closely"
    return "Normal operations"


def _enrich_corridor_row(row: dict) -> dict:
    meta = corridor_metadata().get(str(row.get("corridor") or ""), {})
    operational = row.get("corridor_risk_7ma")
    if operational is None:
        operational = row.get("corridor_risk")
    out = {**row, **meta}
    out["operational_risk"] = operational
    out["action_label"] = _corridor_action_label(operational, row.get("score_status"))
    return out


def _corridors_payload(date_val, rows: list[dict], *, data_source: str = "postgres") -> dict:
    enriched = [_enrich_corridor_row(dict(row)) for row in rows]
    base = {
        "date": _serialize(date_val),
        "index_start": INDIA_GPR_INDEX_START.isoformat(),
        "disclaimer": CORRIDOR_SCORE_DISCLAIMER,
        "metadata": corridor_metadata(),
        "corridors": serialize_rows(enriched),
    }
    return _with_refresh_meta(base, data_source=data_source, as_of_date=base.get("date"))


def get_corridors() -> dict:
    if _database_configured():
        try:
            latest, rows = db.get_corridors_latest()
            if rows:
                return _corridors_payload(latest, rows, data_source="postgres")
        except Exception:
            logger.exception("corridor db read failed")
            if not _allow_csv_fallback():
                empty = {
                    "date": None,
                    "index_start": INDIA_GPR_INDEX_START.isoformat(),
                    "disclaimer": CORRIDOR_SCORE_DISCLAIMER,
                    "metadata": corridor_metadata(),
                    "corridors": [],
                }
                out = _with_refresh_meta(empty, data_source="postgres", as_of_date=None)
                out["stale_warning"] = "Postgres corridor data unavailable"
                return out

    if not _allow_csv_fallback() and _database_configured():
        empty = {
            "date": None,
            "index_start": INDIA_GPR_INDEX_START.isoformat(),
            "disclaimer": CORRIDOR_SCORE_DISCLAIMER,
            "metadata": corridor_metadata(),
            "corridors": [],
        }
        return _with_refresh_meta(empty, data_source="postgres", as_of_date=None)

    frame = _load_corridor_csv()
    if frame.empty:
        empty = {
            "date": None,
            "index_start": INDIA_GPR_INDEX_START.isoformat(),
            "disclaimer": CORRIDOR_SCORE_DISCLAIMER,
            "metadata": corridor_metadata(),
            "corridors": [],
        }
        return _with_refresh_meta(empty, data_source="csv", as_of_date=None)
    latest_date = frame["date"].max()
    day = frame[frame["date"] == latest_date].sort_values("corridor_risk", ascending=False)
    corridors = []
    for _, row in day.iterrows():
        corridors.append(
            _enrich_corridor_row(
                {
                    "corridor": row["corridor"],
                    "corridor_name": row.get("corridor_name", row["corridor"]),
                    "corridor_risk": float(row["corridor_risk"]) if pd.notna(row.get("corridor_risk")) else None,
                    "corridor_risk_7ma": float(row["corridor_risk_7ma"]) if pd.notna(row.get("corridor_risk_7ma")) else None,
                    "corridor_risk_30ma": float(row["corridor_risk_30ma"]) if pd.notna(row.get("corridor_risk_30ma")) else None,
                    "threat_index": float(row.get("threat_index", 0)) if pd.notna(row.get("threat_index")) else None,
                    "energy_risk": float(row.get("energy_risk", 0)) if pd.notna(row.get("energy_risk")) else None,
                    "goods_risk": float(row.get("goods_risk", 0)) if pd.notna(row.get("goods_risk")) else None,
                    "corridor_hit_count": int(row["corridor_hit_count"]) if pd.notna(row.get("corridor_hit_count")) else 0,
                    "gpr_sum": float(row["gpr_sum"]) if pd.notna(row.get("gpr_sum")) else None,
                    "energy_exposure": float(row["energy_exposure"]) if pd.notna(row.get("energy_exposure")) else None,
                    "goods_exposure": float(row["goods_exposure"]) if pd.notna(row.get("goods_exposure")) else None,
                    "score_status": row.get("score_status"),
                    "date": latest_date.strftime("%Y-%m-%d"),
                }
            )
        )
    base = {
        "date": latest_date.strftime("%Y-%m-%d"),
        "index_start": INDIA_GPR_INDEX_START.isoformat(),
        "disclaimer": CORRIDOR_SCORE_DISCLAIMER,
        "metadata": corridor_metadata(),
        "corridors": serialize_rows(corridors),
    }
    return _with_refresh_meta(base, data_source="csv", as_of_date=base["date"])


def get_corridor_history(corridor_id: str, start: str | None = None, end: str | None = None) -> list[dict]:
    rows = db.get_corridor_history(corridor_id, start=start, end=end)
    if rows:
        return serialize_rows([_enrich_corridor_row(dict(row)) for row in reversed(rows)])
    frame = _load_corridor_csv()
    if frame.empty:
        return []
    frame = frame[frame["corridor"] == corridor_id]
    if start:
        frame = frame[frame["date"] >= pd.Timestamp(start)]
    if end:
        frame = frame[frame["date"] <= pd.Timestamp(end)]
    out = []
    for _, row in frame.sort_values("date").iterrows():
        out.append(
            _enrich_corridor_row(
                {
                    "date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])[:10],
                    "corridor": row["corridor"],
                    "corridor_name": row.get("corridor_name", row["corridor"]),
                    "corridor_risk": float(row["corridor_risk"]) if pd.notna(row.get("corridor_risk")) else None,
                    "corridor_risk_7ma": float(row["corridor_risk_7ma"]) if pd.notna(row.get("corridor_risk_7ma")) else None,
                    "corridor_risk_30ma": float(row["corridor_risk_30ma"]) if pd.notna(row.get("corridor_risk_30ma")) else None,
                    "threat_index": float(row["threat_index"]) if pd.notna(row.get("threat_index")) else None,
                    "energy_risk": float(row["energy_risk"]) if pd.notna(row.get("energy_risk")) else None,
                    "goods_risk": float(row["goods_risk"]) if pd.notna(row.get("goods_risk")) else None,
                    "corridor_hit_count": int(row["corridor_hit_count"]) if pd.notna(row.get("corridor_hit_count")) else 0,
                    "score_status": row.get("score_status"),
                }
            )
        )
    return serialize_rows(out)


def get_events_feed(limit=100, theme=None, corridor=None, tier=None, start=None, end=None, tagged_only=False) -> list[dict]:
    start_dt = datetime.combine(date.fromisoformat(start), time.min, tzinfo=timezone.utc) if start else None
    end_dt = datetime.combine(date.fromisoformat(end), time.min, tzinfo=timezone.utc) if end else None
    rows = db.get_recent_news(
        limit=limit,
        theme=theme,
        corridor=corridor,
        tier=int(tier) if tier else None,
        start=start_dt,
        end=end_dt,
        tagged_only=tagged_only,
    )
    return serialize_rows(rows)


def get_news_stats() -> dict:
    total = db.get_total_count()
    recent = db.get_recent_news(limit=1)
    tagged = db.get_recent_news(limit=1, tagged_only=True)
    return {
        "total_articles": total,
        "latest_article_at": recent[0].get("published_at") or recent[0].get("scraped_at") if recent else None,
        "has_tagged_events": bool(tagged),
        "source": "postgresql",
    }


def get_platform_status() -> dict:
    news = get_news_stats()
    gpr = get_gpr_current()
    corridors = get_corridors()

    corridor_date = corridors.get("date")
    gpr_date = gpr.get("date") if gpr else None
    warnings = [
        w
        for w in (
            corridors.get("stale_warning"),
            gpr.get("stale_warning") if gpr else None,
        )
        if w
    ]
    stale_warning = warnings[0] if warnings else None

    last_platform = db.get_last_pipeline_run("platform_refresh")
    last_daily = db.get_last_pipeline_run("daily_index")
    last_catch_up = db.get_last_pipeline_run("catch_up_range")

    dual_cached = db.get_dual_signal()
    dual_as_of = None
    if dual_cached:
        raw_as_of = dual_cached.get("as_of") or (dual_cached.get("geopolitical") or {}).get("as_of")
        if hasattr(raw_as_of, "isoformat"):
            dual_as_of = raw_as_of.isoformat()
        elif raw_as_of:
            dual_as_of = str(raw_as_of)

    return {
        "database_configured": _database_configured(),
        "allow_csv_fallback": _allow_csv_fallback(),
        "refresh_interval_minutes": REFRESH_INTERVAL_MINUTES,
        "latest_dates": {
            "corridor": corridor_date,
            "gpr": gpr_date,
            "news": news.get("latest_article_at"),
            "dual_signal": dual_as_of,
        },
        "data_sources": {
            "corridors": corridors.get("data_source"),
            "gpr": gpr.get("data_source") if gpr else None,
            "news": news.get("source"),
        },
        "updated_at": {
            "corridors": corridors.get("updated_at"),
            "gpr": gpr.get("updated_at") if gpr else None,
        },
        "last_pipeline_runs": {
            "platform_refresh": _serialize_pipeline_run(last_platform),
            "daily_index": _serialize_pipeline_run(last_daily),
            "catch_up_range": _serialize_pipeline_run(last_catch_up),
        },
        "stale_warning": stale_warning,
        "news_total_articles": news.get("total_articles"),
    }


def _top_corridor() -> str | None:
    payload = get_corridors()
    corridors = payload.get("corridors") or []
    if not corridors:
        return None
    top = corridors[0]
    return top.get("corridor_name") or top.get("corridor")


def _driving_events(limit: int = 8, top_corridor: str | None = None) -> tuple[list[dict], dict]:
    from news_dataset.api.stress_news import select_driving_events

    rows = db.get_recent_news(limit=60, tagged_only=True)
    events, meta = select_driving_events(rows, limit=limit, top_corridor=top_corridor)
    for ev in events:
        if ev.get("published_at") is not None:
            ev["published_at"] = _serialize(ev["published_at"])
    return events, meta


def _normalize_dual_signal(payload: dict) -> dict:
    geo = payload.get("geopolitical") or {}
    events = geo.get("driving_events") or []
    for ev in events:
        if ev.get("themes") and not ev.get("nlp_themes"):
            ev["nlp_themes"] = ev.pop("themes")
    return payload


def _dual_signal_cache_stale(cached: dict) -> bool:
    geo = cached.get("geopolitical") or {}
    as_of = geo.get("as_of") or cached.get("as_of")
    if not as_of:
        return True
    try:
        if date.fromisoformat(str(as_of)[:10]) < INDIA_GPR_INDEX_START:
            return True
    except ValueError:
        return True
    vol = cached.get("nifty_volatility") or {}
    if vol.get("available") is False:
        return True
    current = get_gpr_current()
    if not current:
        return False
    cur_date = str(current.get("date"))[:10]
    cache_date = str(as_of)[:10]
    if cur_date > cache_date:
        return True
    cached_gpr = geo.get("gpr_index")
    db_gpr = current.get("gpr_index")
    if cached_gpr is not None and db_gpr is not None:
        if abs(float(cached_gpr) - float(db_gpr)) > 0.5:
            return True
    index_days = geo.get("index_days")
    change_7d = geo.get("change_7d_pct")
    if index_days is not None and index_days < 8 and (change_7d == 0.0 or change_7d is None):
        return True
    if not geo.get("driving_events_meta"):
        return True
    return False


def build_dual_signal_payload(*, refresh: bool = False) -> dict:
    if not refresh:
        cached = db.get_dual_signal()
        if cached and not _dual_signal_cache_stale(cached):
            return _normalize_dual_signal(cached)

    from forsyt_gpr import data, dual_signal

    gf = gpr_frame_from_db_or_csv()
    nifty = data.load_price("NIFTY")
    top_corridor = _top_corridor()
    driving, driving_meta = _driving_events(top_corridor=top_corridor)
    payload = dual_signal.build_dual_signal(
        gf,
        nifty,
        top_corridor=top_corridor,
        driving_events=driving,
    )
    payload["driving_events_meta"] = driving_meta
    as_of = payload["geopolitical"]["as_of"]
    db.upsert_dual_signal(as_of, payload)
    return _normalize_dual_signal(payload)
