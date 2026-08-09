"""Data access layer for Forsyt product API (DB with CSV fallbacks)."""

from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
NIFTY_DIR = REPO_ROOT / "nifty-50"
GPR_OUTPUT = REPO_ROOT / "gpr_index" / "outputs"

if str(NIFTY_DIR) not in sys.path:
    sys.path.insert(0, str(NIFTY_DIR))

from news_dataset import db  # noqa: E402


def _serialize(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def serialize_rows(rows: list[dict]) -> list[dict]:
    return [{key: _serialize(val) for key, val in row.items()} for row in rows]


def _load_gpr_csv() -> pd.DataFrame:
    path = GPR_OUTPUT / "gpr_daily_index.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    return frame


def gpr_frame_from_db_or_csv() -> pd.DataFrame:
    """Canonical GPR frame for dual-signal and charts."""
    from forsyt_gpr.data import as_gpr_frame

    rows = db.get_gpr_history(limit=5000)
    if rows:
        frame = pd.DataFrame(rows)
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date").sort_index()
        return as_gpr_frame(
            frame,
            gpr="gpr_index",
            threats="gpr_threats_index",
            acts="gpr_acts_index",
        )

    csv = _load_gpr_csv()
    if csv.empty:
        from forsyt_gpr.data import load_aigpr_daily

        return load_aigpr_daily()
    return as_gpr_frame(
        csv,
        gpr="gpr_index",
        threats="gpr_threats_index",
        acts="gpr_acts_index",
    )


def get_gpr_current() -> dict | None:
    row = db.get_gpr_current()
    if row:
        return serialize_rows([row])[0]
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


def get_gpr_history(start: str | None = None, end: str | None = None, limit: int = 500) -> list[dict]:
    rows = db.get_gpr_history(start=start, end=end, limit=limit)
    if rows:
        return serialize_rows(list(reversed(rows)))
    csv = _load_gpr_csv()
    if csv.empty:
        return []
    if start:
        csv = csv[csv.index >= pd.Timestamp(start)]
    if end:
        csv = csv[csv.index <= pd.Timestamp(end)]
    csv = csv.tail(limit)
    out = []
    for idx, row in csv.iterrows():
        out.append(
            {
                "date": idx.strftime("%Y-%m-%d"),
                "gpr_index": float(row["gpr_index"]),
                "gpr_7ma": float(row.get("gpr_7ma", row["gpr_index"])),
                "gpr_30ma": float(row.get("gpr_30ma", row["gpr_index"])),
            }
        )
    return out


def get_corridors() -> dict:
    latest, rows = db.get_corridors_latest()
    if rows:
        return {"date": _serialize(latest), "corridors": serialize_rows(rows)}
    path = GPR_OUTPUT / "gpr_corridor_daily.csv"
    if not path.exists():
        return {"date": None, "corridors": []}
    frame = pd.read_csv(path, parse_dates=["date"])
    if frame.empty:
        return {"date": None, "corridors": []}
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
    return {"date": latest_date.strftime("%Y-%m-%d"), "corridors": corridors}


def get_corridor_history(corridor_id: str, start: str | None = None, end: str | None = None) -> list[dict]:
    rows = db.get_corridor_history(corridor_id, start=start, end=end)
    if rows:
        return serialize_rows(list(reversed(rows)))
    path = GPR_OUTPUT / "gpr_corridor_daily.csv"
    if not path.exists():
        return []
    frame = pd.read_csv(path, parse_dates=["date"])
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
    tagged = db.get_events_feed_tagged(limit=1)
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
    return corridors[0].get("corridor")


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
                themes = ", ".join(kw) if isinstance(kw, list) else str(kw)
            except Exception:
                themes = ""
        out.append(
            {
                "title": row.get("title"),
                "source": row.get("source"),
                "link": row.get("link"),
                "themes": themes,
                "locations": row.get("nlp_locations"),
                "published_at": _serialize(row.get("published_at") or row.get("scraped_at")),
            }
        )
    return out


def build_dual_signal_payload(*, refresh: bool = False) -> dict:
    if not refresh:
        cached = db.get_dual_signal()
        if cached:
            return cached

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
    return payload
