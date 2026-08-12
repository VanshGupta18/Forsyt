"""Data access layer for Forsyt product API (DB with CSV fallbacks)."""

from __future__ import annotations

import logging
import math
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

from gpr_index.scripts.paths import INDIA_GPR_INDEX_START  # noqa: E402
from news_dataset import db  # noqa: E402

logger = logging.getLogger(__name__)

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
    csv_payload = _csv_current_payload()
    if row and csv_payload:
        db_date = str(row.get("date"))[:10]
        csv_date = csv_payload["date"]
        db_gpr = row.get("gpr_index")
        csv_gpr = csv_payload.get("gpr_index")
        if csv_date > db_date:
            return csv_payload
        if (
            csv_date == db_date
            and db_gpr is not None
            and csv_gpr is not None
            and abs(float(db_gpr) - float(csv_gpr)) > 0.5
        ):
            return csv_payload
    if row:
        return serialize_rows([row])[0]
    return csv_payload


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


def get_corridors() -> dict:
    try:
        latest, rows = db.get_corridors_latest()
        if rows:
            return {
                "date": _serialize(latest),
                "index_start": INDIA_GPR_INDEX_START.isoformat(),
                "corridors": serialize_rows(rows),
            }
    except Exception:
        logger.exception("corridor db read failed; falling back to CSV")
    frame = _load_corridor_csv()
    if frame.empty:
        return {
            "date": None,
            "index_start": INDIA_GPR_INDEX_START.isoformat(),
            "corridors": [],
        }
    latest_date = frame["date"].max()
    day = frame[frame["date"] == latest_date].sort_values("corridor_risk", ascending=False)
    corridors = []
    for _, row in day.iterrows():
        corridors.append(
            {
                "corridor": row["corridor"],
                "corridor_name": row.get("corridor_name", row["corridor"]),
                "corridor_risk": float(row["corridor_risk"]),
                "threat_index": float(row.get("threat_index", 0)),
                "energy_risk": float(row.get("energy_risk", 0)),
                "goods_risk": float(row.get("goods_risk", 0)),
                "date": latest_date.strftime("%Y-%m-%d"),
            }
        )
    return {
        "date": latest_date.strftime("%Y-%m-%d"),
        "index_start": INDIA_GPR_INDEX_START.isoformat(),
        "corridors": corridors,
    }


def get_corridor_history(corridor_id: str, start: str | None = None, end: str | None = None) -> list[dict]:
    rows = db.get_corridor_history(corridor_id, start=start, end=end)
    if rows:
        return serialize_rows(list(reversed(rows)))
    frame = _load_corridor_csv()
    if frame.empty:
        return []
    frame = frame[frame["corridor"] == corridor_id]
    if start:
        frame = frame[frame["date"] >= pd.Timestamp(start)]
    if end:
        frame = frame[frame["date"] <= pd.Timestamp(end)]
    return serialize_rows(
        [
            {
                "date": row["date"],
                "corridor": row["corridor"],
                "corridor_name": row.get("corridor_name", row["corridor"]),
                "corridor_risk": row["corridor_risk"],
            }
            for _, row in frame.iterrows()
        ]
    )


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


def _top_corridor() -> str | None:
    payload = get_corridors()
    corridors = payload.get("corridors") or []
    if not corridors:
        return None
    top = corridors[0]
    return top.get("corridor_name") or top.get("corridor")


def _driving_events(limit: int = 3) -> list[dict]:
    rows = db.get_recent_news(limit=limit)
    out = []
    for row in rows:
        themes = row.get("nlp_themes") or ""
        if not themes and row.get("matched_keywords"):
            try:
                import json
                kw = row.get("matched_keywords")
                if isinstance(kw, str):
                    kw = json.loads(kw)
                if isinstance(kw, list):
                    themes = ", ".join(str(k) for k in kw if k)
                elif isinstance(kw, dict):
                    themes = ", ".join(f"{k}: {v}" for k, v in kw.items())
                else:
                    themes = str(kw)
            except Exception:
                themes = str(row.get("matched_keywords") or "")
        out.append(
            {
                "title": row.get("title"),
                "source": row.get("source"),
                "link": row.get("link"),
                "nlp_themes": themes,
                "nlp_locations": row.get("nlp_locations"),
                "published_at": _serialize(row.get("published_at") or row.get("scraped_at")),
            }
        )
    return out


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
    return False


def build_dual_signal_payload(*, refresh: bool = False) -> dict:
    if not refresh:
        cached = db.get_dual_signal()
        if cached and not _dual_signal_cache_stale(cached):
            return _normalize_dual_signal(cached)

    from forsyt_gpr import data, dual_signal

    gf = gpr_frame_from_db_or_csv()
    nifty = data.load_price("NIFTY")
    payload = dual_signal.build_dual_signal(
        gf,
        nifty,
        top_corridor=_top_corridor(),
        driving_events=_driving_events(),
    )
    as_of = payload["geopolitical"]["as_of"]
    db.upsert_dual_signal(as_of, payload)
    return _normalize_dual_signal(payload)
