"""Data access layer for Forsyt product API (DB with CSV fallbacks).

Beginner note — what is a "service layer"?
    api/server.py only wires HTTP routes to functions; it doesn't know how to
    actually fetch or compute anything. This file is where that real work
    happens: reading rows from Postgres (via news_dataset/db.py), and falling
    back to reading the GPR pipeline's raw CSV output files directly when
    Postgres doesn't have what's needed yet (or is unavailable, if
    ALLOW_CSV_FALLBACK is set — meant for offline/local development only,
    never production). Every function in this file returns plain Python
    dicts/lists that api/server.py just hands to jsonify() unchanged.
"""

from __future__ import annotations

import logging
import math
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from datetime import time as dt_time
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
from news_dataset.api.cache import cache_get, cache_set, _MISSING  # noqa: E402
from news_dataset.api.explain import additive_explanation, term  # noqa: E402

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
    age = datetime.now(timezone.utc) - datetime.combine(day, dt_time.max, tzinfo=timezone.utc)
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


_GPR_CSV_CACHE: tuple[float, pd.DataFrame] | None = None
_CORRIDOR_CSV_CACHE: tuple[float, pd.DataFrame] | None = None
_CSV_CACHE_TTL = 300.0


def _load_gpr_csv() -> pd.DataFrame:
    global _GPR_CSV_CACHE
    now = time.monotonic()
    if _GPR_CSV_CACHE and now - _GPR_CSV_CACHE[0] < _CSV_CACHE_TTL:
        return _GPR_CSV_CACHE[1]
    path = GPR_OUTPUT / "gpr_daily_index.csv"
    if not path.exists():
        frame = pd.DataFrame()
    else:
        frame = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
        frame = frame[frame.index >= _INDEX_START_TS]
    _GPR_CSV_CACHE = (now, frame)
    return frame


def _load_corridor_csv() -> pd.DataFrame:
    global _CORRIDOR_CSV_CACHE
    now = time.monotonic()
    if _CORRIDOR_CSV_CACHE and now - _CORRIDOR_CSV_CACHE[0] < _CSV_CACHE_TTL:
        return _CORRIDOR_CSV_CACHE[1]
    path = GPR_OUTPUT / "gpr_corridor_daily.csv"
    if not path.exists():
        frame = pd.DataFrame()
    else:
        frame = pd.read_csv(path, parse_dates=["date"])
        frame = frame[frame["date"] >= _INDEX_START_TS]
    _CORRIDOR_CSV_CACHE = (now, frame)
    return frame


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


def get_gpr_current(*, skip_cache: bool = False) -> dict | None:
    """Return today's (or the most recent) India GPR risk score as a dict, or None if no data exists yet.

    Tries the in-memory cache first, then Postgres, then falls back to the
    GPR pipeline's CSV output if Postgres is missing/stale and CSV fallback
    is allowed. This is what /api/pages/home and /api/pages/macro show as
    the headline risk number.
    """
    if not skip_cache:
        hit = cache_get("gpr:current", ttl_seconds=300)
        if hit is not _MISSING:
            return hit
    try:
        row = db.get_gpr_current()
    except Exception:
        # DB unreachable (e.g. local run without Postgres) — fall back to CSV.
        logger.exception("gpr current db read failed; falling back to CSV")
        row = None
    csv_payload = _csv_current_payload() if _allow_csv_fallback() or not _database_configured() else None
    if row and csv_payload and _allow_csv_fallback():
        db_date = str(row.get("date"))[:10]
        csv_date = csv_payload["date"]
        db_gpr = row.get("gpr_index")
        csv_gpr = csv_payload.get("gpr_index")
        if csv_date > db_date:
            result = _with_refresh_meta(csv_payload, data_source="csv", as_of_date=csv_date)
            cache_set("gpr:current", result)
            return result
        if (
            csv_date == db_date
            and db_gpr is not None
            and csv_gpr is not None
            and abs(float(db_gpr) - float(csv_gpr)) > 0.5
        ):
            result = _with_refresh_meta(csv_payload, data_source="csv", as_of_date=csv_date)
            cache_set("gpr:current", result)
            return result
    if row:
        serialized = serialize_rows([row])[0]
        result = _with_refresh_meta(serialized, data_source="postgres", as_of_date=serialized.get("date"))
        cache_set("gpr:current", result)
        return result
    if csv_payload:
        result = _with_refresh_meta(csv_payload, data_source="csv", as_of_date=csv_payload.get("date"))
        cache_set("gpr:current", result)
        return result
    cache_set("gpr:current", None)
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


def get_gpr_history(
    start: str | None = None,
    end: str | None = None,
    limit: int = 500,
    *,
    skip_cache: bool = False,
) -> list[dict]:
    """Return a list of past daily GPR scores (newest-first from the DB, reversed to oldest-first here) for chart lines.

    Powers the risk-over-time chart on the Macro and News dashboard pages.
    """
    cache_key = f"gpr:history:{start}:{end}:{limit}"
    if not skip_cache:
        hit = cache_get(cache_key, ttl_seconds=900)
        if hit is not _MISSING:
            return hit
    csv_history = _gpr_history_from_csv(start=start, end=end, limit=limit)
    try:
        rows = db.get_gpr_history(start=start, end=end, limit=limit)
    except Exception:
        logger.exception("gpr history db read failed; falling back to CSV")
        rows = []
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
                        cache_set(cache_key, csv_history)
                        return csv_history
            result = serialize_rows(cleaned)
            cache_set(cache_key, result)
            return result
    cache_set(cache_key, csv_history)
    return csv_history


# --- Extra GPR analytics panels (portfolio page) ---------------------------
# Small, read-only summaries built straight from the pipeline's CSV outputs:
# what's driving risk (event-type mix), forward-looking threats vs realized
# acts, and the India oil-GPR channel. All cheap file reads; each sub-block is
# independent so a missing file just hides that one panel.
_EVENT_LABELS = {
    "sum_military_conflict": "Military",
    "sum_terrorism": "Terrorism",
    "sum_diplomatic_tension": "Diplomatic",
    "sum_nuclear_threat": "Nuclear",
    "sum_sanctions": "Sanctions",
    "sum_coup_regime": "Coup/Regime",
    "sum_civil_war": "Civil war",
    "sum_other": "Other",
}


def _read_output_csv(name: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(GPR_OUTPUT / name)
        if "date" in df.columns:
            df = df.sort_values("date")
        return df
    except Exception:
        logger.warning("gpr panel CSV missing/unreadable: %s", name)
        return pd.DataFrame()


def _downsample_records(df: pd.DataFrame, cols: dict[str, str], n: int = 40) -> list[dict]:
    """df -> list of {out_name: rounded value, 'd': date}, downsampled to <=n rows."""
    if df.empty:
        return []
    if len(df) > n:
        step = len(df) / n
        df = df.iloc[[int(i * step) for i in range(n)]]
    out = []
    for _, row in df.iterrows():
        rec: dict = {"d": str(row.get("date"))[:10]}
        for src, dst in cols.items():
            v = row.get(src)
            rec[dst] = round(float(v), 1) if pd.notna(v) else None
        out.append(rec)
    return out


def _pctile(series: pd.Series, value: float) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    return round(100.0 * float((s <= value).mean()), 1)


def _risk_composition(window: int = 7) -> dict | None:
    df = _read_output_csv("gpr_event_type.csv")
    cols = [c for c in _EVENT_LABELS if c in df.columns]
    if df.empty or not cols:
        return None
    recent = df.tail(window)
    sums = {c: float(recent[c].fillna(0).sum()) for c in cols}
    total = sum(sums.values()) or 1.0
    items = [
        {"type": _EVENT_LABELS[c], "share": round(100.0 * sums[c] / total, 1), "value": round(sums[c], 1)}
        for c in cols
    ]
    items.sort(key=lambda x: x["share"], reverse=True)
    return {
        "as_of": str(df["date"].iloc[-1])[:10] if "date" in df.columns else None,
        "window_days": window,
        "items": [i for i in items if i["share"] > 0],
    }


def _threats_acts() -> dict | None:
    df = _read_output_csv("gpr_daily_index.csv")
    if df.empty or "gpr_threats_index" not in df.columns or "gpr_acts_index" not in df.columns:
        return None
    t = pd.to_numeric(df["gpr_threats_index"], errors="coerce")
    a = pd.to_numeric(df["gpr_acts_index"], errors="coerce")
    if not t.notna().any() or not a.notna().any():
        return None
    # Headline = 7d trailing mean: single days are sparse (a quiet news day can
    # read 0 threats), so smooth like the composition panel; percentile is taken
    # on the same smoothed series so the gauge and number agree.
    t7, a7 = t.rolling(7, min_periods=1).mean(), a.rolling(7, min_periods=1).mean()
    t_now, a_now = float(t7.dropna().iloc[-1]), float(a7.dropna().iloc[-1])
    return {
        "as_of": str(df["date"].iloc[-1])[:10] if "date" in df.columns else None,
        "threats_index": round(t_now, 1),
        "acts_index": round(a_now, 1),
        "threats_percentile": _pctile(t7, t_now),
        "acts_percentile": _pctile(a7, a_now),
        "spark": _downsample_records(
            df.assign(gpr_threats_index=t, gpr_acts_index=a),
            {"gpr_threats_index": "threats", "gpr_acts_index": "acts"},
        ),
    }


def _oil_gpr() -> dict | None:
    df = _read_output_csv("gpr_oil_daily.csv")
    if df.empty or "gpr_oil_index" not in df.columns:
        return None
    idx = pd.to_numeric(df["gpr_oil_index"], errors="coerce")
    if not idx.notna().any():
        return None
    clean = idx.dropna()
    now = float(clean.iloc[-1])
    prior = float(clean.iloc[-8]) if len(clean) >= 8 else None
    return {
        "as_of": str(df["date"].iloc[-1])[:10] if "date" in df.columns else None,
        "index": round(now, 1),
        "change_7d": round(now - prior, 1) if prior is not None else None,
        "percentile": _pctile(idx, now),
        "spark": _downsample_records(df.assign(gpr_oil_index=idx), {"gpr_oil_index": "v"}),
    }


def get_gpr_panels(*, skip_cache: bool = False) -> dict:
    """Event-type mix, threats-vs-acts, and oil-GPR summaries for the portfolio page."""
    cache_key = "gpr:panels"
    if not skip_cache:
        hit = cache_get(cache_key, ttl_seconds=900)
        if hit is not _MISSING:
            return hit
    panels = {
        "risk_composition": _risk_composition(),
        "threats_acts": _threats_acts(),
        "oil_gpr": _oil_gpr(),
    }
    cache_set(cache_key, panels)
    return panels


def _corridor_action_label(risk: float | None, score_status: str | None = None) -> str:
    if score_status == "insufficient_history":
        return "Calibrating"
    value = float(risk or 0)
    if value >= 50:
        return "Avoid new bookings"
    if value >= 20:
        return "Monitor closely"
    return "Normal operations"


def _corridor_operational_risk(row: dict) -> float:
    operational = row.get("corridor_risk_7ma")
    if operational is None or (isinstance(operational, float) and math.isnan(operational)):
        operational = row.get("corridor_risk")
    try:
        return float(operational or 0)
    except (TypeError, ValueError):
        return 0.0


def _sort_corridors_by_operational(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=_corridor_operational_risk, reverse=True)


def _corridor_explain(row: dict) -> dict:
    """Exact breakdown of corridor_risk = max(energy_risk, goods_risk),
    each = threat_index × India exposure. The dominant term is the risk shown."""
    ti = float(row.get("threat_index") or 0.0)
    ee = float(row.get("energy_exposure") or 0.0)
    ge = float(row.get("goods_exposure") or 0.0)
    terms = [
        term("Energy route", ti, ee, note=f"threat {ti:.0f} × energy exposure {ee:.0%}"),
        term("Goods route", ti, ge, note=f"threat {ti:.0f} × goods exposure {ge:.0%}"),
    ]
    output = row.get("corridor_risk")
    if output is None:
        output = max((t["contribution"] for t in terms), default=0.0)
    return additive_explanation(
        output, terms,
        "corridor_risk = max(energy_risk, goods_risk); each = threat_index × India exposure",
        "threat_index ≈100 = baseline news stress on this route, not a disruption probability.",
    )


def _enrich_corridor_row(row: dict) -> dict:
    meta = corridor_metadata().get(str(row.get("corridor") or ""), {})
    operational = row.get("corridor_risk_7ma")
    if operational is None:
        operational = row.get("corridor_risk")
    out = {**row, **meta}
    out["operational_risk"] = operational
    out["action_label"] = _corridor_action_label(operational, row.get("score_status"))
    out["explain"] = _corridor_explain(out)
    return out


def _corridors_payload(date_val, rows: list[dict], *, data_source: str = "postgres") -> dict:
    # Serve only corridors we still report. Postgres upserts never delete, so
    # rows written before a corridor was retired linger indefinitely; without
    # this filter they'd be returned with no matching `metadata` entry and the
    # dashboard would render a nameless row frozen at its last-written value.
    # Keying off corridor_metadata() keeps rows and metadata consistent by
    # construction, so retiring a corridor stays a one-line registry change.
    meta = corridor_metadata()
    rows = [row for row in rows if str(row.get("corridor") or "") in meta]
    enriched = [_enrich_corridor_row(dict(row)) for row in _sort_corridors_by_operational(rows)]
    base = {
        "date": _serialize(date_val),
        "index_start": INDIA_GPR_INDEX_START.isoformat(),
        "disclaimer": CORRIDOR_SCORE_DISCLAIMER,
        "metadata": meta,
        "corridors": serialize_rows(enriched),
    }
    return _with_refresh_meta(base, data_source=data_source, as_of_date=base.get("date"))


def get_corridors(*, skip_cache: bool = False) -> dict:
    """Return today's risk score for every tracked trade corridor (e.g. Suez, Malacca), sorted riskiest-first.

    Each corridor entry is enriched with display metadata (name, description)
    and an "action_label" like "Monitor closely" derived from its risk level.
    This is what the Corridor board page renders as its main table.
    """
    if not skip_cache:
        hit = cache_get("corridors:latest", ttl_seconds=300)
        if hit is not _MISSING:
            return hit
    result = _fetch_corridors()
    cache_set("corridors:latest", result)
    return result


def _fetch_corridors() -> dict:
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
    day = frame[frame["date"] == latest_date].copy()
    day["_operational"] = day.apply(
        lambda row: _corridor_operational_risk(row.to_dict()),
        axis=1,
    )
    day = day.sort_values("_operational", ascending=False)
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
    """Return one corridor's daily risk score over time — the chart line when drilling into a single corridor."""
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
    """Return a list of recent news articles (title, source, link, NLP tags), optionally filtered.

    This is the data behind /api/events/feed and the News dashboard page's
    article list.
    """
    start_dt = datetime.combine(date.fromisoformat(start), dt_time.min, tzinfo=timezone.utc) if start else None
    end_dt = datetime.combine(date.fromisoformat(end), dt_time.min, tzinfo=timezone.utc) if end else None
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


def get_platform_status(*, skip_cache: bool = False) -> dict:
    """Return a dict describing pipeline freshness: latest dates, which data source served each field, and any staleness warnings.

    This is what /api/status exposes, and get_platform_status_slim() below
    trims it down to just the fields the page bundles need.
    """
    if not skip_cache:
        hit = cache_get("platform:status", ttl_seconds=120)
        if hit is not _MISSING:
            return hit
    result = _build_platform_status()
    cache_set("platform:status", result)
    return result


def get_platform_status_slim(*, skip_cache: bool = False) -> dict:
    full = get_platform_status(skip_cache=skip_cache)
    return {
        "refresh_interval_minutes": full.get("refresh_interval_minutes"),
        "latest_dates": full.get("latest_dates"),
        "stale_warning": full.get("stale_warning"),
        "last_pipeline_runs": full.get("last_pipeline_runs"),
    }


def get_health_snapshot(*, skip_cache: bool = False) -> dict:
    """Return a simple "is everything alive" dict: total article count, latest GPR/corridor dates, last platform_refresh run.

    Backs the plain /health endpoint used for uptime monitoring.
    """
    if not skip_cache:
        hit = cache_get("platform:health", ttl_seconds=120)
        if hit is not _MISSING:
            return hit
    snap = db.get_health_snapshot()
    last_platform = db.get_last_pipeline_run("platform_refresh")
    stale = _stale_warning_for_date(snap.get("gpr_latest_date"))
    payload = {
        "status": "healthy",
        **snap,
        "database": "postgresql",
        "timestamp": _utc_now_iso(),
        "last_platform_refresh": _serialize_pipeline_run(last_platform),
        "stale_warning": stale,
    }
    cache_set("platform:health", payload)
    return payload


def _build_platform_status() -> dict:
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


def _attach_dual_explain(payload: dict) -> None:
    """Attach exact additive explanations to joint_stress and the geo regime."""
    joint = payload.get("joint_stress") or {}
    if joint.get("stress_score") is not None:
        geo_pct = float(joint.get("geo_percentile") or 0.0)
        vol_pct = float(joint.get("vol_percentile") or 0.0)
        joint["explain"] = additive_explanation(
            joint["stress_score"],
            [
                term("Geopolitics", geo_pct, 0.6, note="GPR percentile × 0.6"),
                term("Market volatility", vol_pct, 0.4, note="NIFTY vol percentile × 0.4"),
            ],
            "stress = 0.6 × geo_percentile + 0.4 × vol_percentile",
            "Transparent fixed blend — recompute it by hand from the two percentiles.",
        )

    geo = payload.get("geopolitical") or {}
    if geo.get("z_score") is not None:
        z = float(geo["z_score"])
        gpr = float(geo.get("gpr_index") or 0.0)
        geo["explain"] = additive_explanation(
            round(z, 2),
            [term("GPR vs baseline", gpr - 100.0, 1.0 / 35.0,
                  note=f"(GPR {gpr:.0f} − baseline 100) ÷ std 35")],
            "z = (gpr_index − 100) / 35  →  regime band",
            "Baseline 100/35 is the Caldara long-run mean/spread (India index history is short).",
        )


def _normalize_dual_signal(payload: dict) -> dict:
    geo = payload.get("geopolitical") or {}
    events = geo.get("driving_events") or []
    for ev in events:
        if ev.get("themes") and not ev.get("nlp_themes"):
            ev["nlp_themes"] = ev.pop("themes")
    _attach_dual_explain(payload)
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
    """Return the combined "geopolitical risk + NIFTY market volatility" reading, using a cached copy unless refresh=True.

    Combines the GPR index history with NIFTY price data (via the sibling
    forsyt_gpr package) plus a short list of "driving events" — the specific
    news articles judged most responsible for the current reading (see
    api/stress_news.py). This is the core payload behind
    /api/market/dual-signal and the stress-monitor dashboard views.
    """
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
    try:
        db.upsert_dual_signal(as_of, payload)
    except Exception:
        logger.exception("dual_signal cache write failed — returning computed payload anyway")
    return _normalize_dual_signal(payload)
