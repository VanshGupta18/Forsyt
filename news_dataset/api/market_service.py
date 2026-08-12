"""Live market quotes via yfinance with TTL cache and NIFTY CSV fallback."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
NIFTY_CSV = REPO_ROOT / "nifty-50" / "data" / "NIFTY.csv"

IST = ZoneInfo("Asia/Kolkata")

SYMBOLS: dict[str, dict[str, str]] = {
    "nifty": {"label": "NIFTY 50", "ticker": "^NSEI", "currency": "INR"},
    "sensex": {"label": "SENSEX", "ticker": "^BSESN", "currency": "INR"},
    "india_vix": {"label": "INDIA VIX", "ticker": "^INDIAVIX", "currency": ""},
    "usd_inr": {"label": "USD/INR", "ticker": "INR=X", "currency": "INR"},
    "brent": {"label": "Brent Crude", "ticker": "BZ=F", "currency": "USD"},
}

# Alternate Yahoo tickers when the primary symbol returns empty history.
ALT_TICKERS: dict[str, list[str]] = {
    "usd_inr": ["USDINR=X"],
    "brent": ["CL=F"],
}

PERIODS = frozenset({"1mo", "3mo", "6mo", "1y"})

_cache: dict[str, dict] = {}
_yf = None
_yf_checked = False


def _get_yfinance():
    """Return yfinance module if installed, else None."""
    global _yf, _yf_checked
    if _yf_checked:
        return _yf
    _yf_checked = True
    try:
        import yfinance as yf  # noqa: PLC0415

        _yf = yf
    except ImportError:
        logger.warning("yfinance not installed — market quotes will use CSV fallbacks where available")
        _yf = None
    return _yf


def _cache_ttl_seconds() -> int:
    now = datetime.now(IST).time()
    market_open = time(9, 15)
    market_close = time(15, 30)
    if market_open <= now <= market_close:
        return 15 * 60
    return 60 * 60


def _cache_valid(key: str) -> bool:
    entry = _cache.get(key)
    if not entry:
        return False
    age = (datetime.now(timezone.utc) - entry["fetched_at"]).total_seconds()
    return age < _cache_ttl_seconds()


def _nifty_from_csv() -> dict | None:
    if not NIFTY_CSV.exists():
        return None
    try:
        df = pd.read_csv(NIFTY_CSV)
        df = df.rename(columns={df.columns[0]: "Date"})
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        if len(df) < 2:
            return None
        close_col = df.columns[1]
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(latest[close_col])
        prev_price = float(prev[close_col])
        change = price - prev_price
        change_pct = (change / prev_price * 100) if prev_price else 0.0
        as_of = latest["Date"]
        return {
            "key": "nifty",
            "label": SYMBOLS["nifty"]["label"],
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": "INR",
            "as_of": as_of.strftime("%Y-%m-%d"),
            "stale": True,
            "source": "csv",
        }
    except Exception as exc:
        logger.warning("NIFTY CSV fallback failed: %s", exc)
        return None


def _tickers_for_key(key: str) -> list[str]:
    meta = SYMBOLS[key]
    alts = ALT_TICKERS.get(key, [])
    return list(dict.fromkeys([meta["ticker"], *alts]))


def _history_for_ticker(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Extract OHLCV history for one ticker from yf.download output."""
    if frame is None or frame.empty:
        return pd.DataFrame()
    if isinstance(frame.columns, pd.MultiIndex):
        if ticker not in frame.columns.get_level_values(0):
            return pd.DataFrame()
        sub = frame[ticker].dropna(how="all")
        return sub if not sub.empty and "Close" in sub.columns else pd.DataFrame()
    if "Close" in frame.columns:
        return frame.dropna(how="all")
    return pd.DataFrame()


def _quote_from_history(key: str, meta: dict, hist: pd.DataFrame, *, source: str = "yfinance") -> dict:
    latest = hist.iloc[-1]
    price = float(latest["Close"])
    as_of = hist.index[-1]
    if hasattr(as_of, "strftime"):
        as_of_str = as_of.strftime("%Y-%m-%d")
    else:
        as_of_str = str(as_of)[:10]

    prev_price = float(hist.iloc[-2]["Close"]) if len(hist) >= 2 else price
    change = price - prev_price
    change_pct = (change / prev_price * 100) if prev_price else 0.0

    return {
        "key": key,
        "label": meta["label"],
        "price": round(price, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "currency": meta["currency"],
        "as_of": as_of_str,
        "stale": source != "yfinance",
        "source": source,
    }


def _quote_from_fast_info(key: str, meta: dict, ticker: str) -> dict | None:
    yf = _get_yfinance()
    if yf is None:
        return None

    try:
        info = yf.Ticker(ticker).fast_info
        price = info.get("lastPrice") or info.get("regularMarketPrice")
        prev = info.get("previousClose")
        if price is None:
            return None
        price = float(price)
        prev_price = float(prev) if prev is not None else price
        change = price - prev_price
        change_pct = (change / prev_price * 100) if prev_price else 0.0
        return {
            "key": key,
            "label": meta["label"],
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": meta["currency"],
            "as_of": datetime.now(IST).strftime("%Y-%m-%d"),
            "stale": False,
            "source": "yfinance",
        }
    except Exception as exc:
        logger.debug("fast_info failed for %s (%s): %s", key, ticker, exc)
        return None


def _quote_for_key(key: str, batch_frame: pd.DataFrame | None) -> dict:
    meta = SYMBOLS[key]
    yf = _get_yfinance()

    if yf is not None:
        for ticker in _tickers_for_key(key):
            hist = _history_for_ticker(batch_frame, ticker) if batch_frame is not None else pd.DataFrame()
            if hist.empty or "Close" not in hist.columns:
                try:
                    hist = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=True)
                except Exception as exc:
                    logger.debug("history failed for %s (%s): %s", key, ticker, exc)
                    hist = pd.DataFrame()
            if not hist.empty and "Close" in hist.columns:
                return _quote_from_history(key, meta, hist)

            fast = _quote_from_fast_info(key, meta, ticker)
            if fast:
                return fast

    if key == "nifty":
        fallback = _nifty_from_csv()
        if fallback:
            return fallback

    if yf is None:
        raise ValueError(f"{key}: yfinance not installed (uv pip install yfinance)")

    raise ValueError(f"no quote data for {key}")


def fetch_quotes(symbols: list[str] | None = None) -> dict:
    """Return latest quotes for configured symbols."""
    keys = symbols if symbols else list(SYMBOLS.keys())
    quotes: list[dict] = []
    errors: list[str] = []

    pending: list[str] = []
    for key in keys:
        if key not in SYMBOLS:
            errors.append(f"unknown symbol: {key}")
            continue
        cache_key = f"quote:{key}"
        if _cache_valid(cache_key):
            quotes.append(_cache[cache_key]["data"])
        else:
            pending.append(key)

    batch_frame: pd.DataFrame | None = None
    yf = _get_yfinance()
    if pending:
        if yf is None:
            errors.append("yfinance not installed — run: uv pip install yfinance")
        else:
            tickers: list[str] = []
            for key in pending:
                tickers.extend(_tickers_for_key(key))
            unique_tickers = list(dict.fromkeys(tickers))
            try:
                batch_frame = yf.download(
                    " ".join(unique_tickers),
                    period="5d",
                    interval="1d",
                    group_by="ticker",
                    auto_adjust=True,
                    progress=False,
                    threads=True,
                )
            except Exception as exc:
                logger.warning("batch yfinance download failed: %s", exc)
                batch_frame = None

    for key in pending:
        try:
            quote = _quote_for_key(key, batch_frame)
            cache_key = f"quote:{key}"
            _cache[cache_key] = {"data": quote, "fetched_at": datetime.now(timezone.utc)}
            quotes.append(quote)
        except Exception as exc:
            logger.warning("quote failed for %s: %s", key, exc)
            errors.append(f"{key}: {exc}")

    # Stable display order matching SYMBOLS definition
    order = {k: i for i, k in enumerate(SYMBOLS)}
    quotes.sort(key=lambda q: order.get(q["key"], 999))
    return {"quotes": quotes, "errors": errors}


def fetch_history(symbol: str, period: str = "3mo") -> dict:
    """Daily close history for sparklines."""
    if symbol not in SYMBOLS:
        raise ValueError(f"unknown symbol: {symbol}")

    if period not in PERIODS:
        period = "3mo"
    cache_key = f"history:{symbol}:{period}"
    if _cache_valid(cache_key):
        return _cache[cache_key]["data"]

    meta = SYMBOLS[symbol]
    yf = _get_yfinance()
    hist = pd.DataFrame()
    if yf is not None:
        try:
            hist = yf.Ticker(meta["ticker"]).history(period=period, interval="1d", auto_adjust=True)
        except Exception as exc:
            logger.warning("history fetch failed for %s: %s", symbol, exc)

    if hist.empty:
        if symbol == "nifty" and NIFTY_CSV.exists():
            df = pd.read_csv(NIFTY_CSV)
            df = df.rename(columns={df.columns[0]: "Date"})
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"]).sort_values("Date")
            days = {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252}.get(period, 66)
            tail = df.tail(days)
            points = [
                {"date": row["Date"].strftime("%Y-%m-%d"), "close": round(float(row.iloc[1]), 2)}
                for _, row in tail.iterrows()
            ]
            payload = {"symbol": symbol, "points": points, "stale": True, "source": "csv"}
            _cache[cache_key] = {"data": payload, "fetched_at": datetime.now(timezone.utc)}
            return payload
        if yf is None:
            raise ValueError("yfinance not installed — run: uv pip install yfinance")
        raise ValueError(f"no history for {symbol}")

    points = [
        {"date": idx.strftime("%Y-%m-%d"), "close": round(float(row["Close"]), 2)}
        for idx, row in hist.iterrows()
    ]
    payload = {"symbol": symbol, "points": points, "stale": False, "source": "yfinance"}
    _cache[cache_key] = {"data": payload, "fetched_at": datetime.now(timezone.utc)}
    return payload


def compute_indicators(symbol: str = "nifty") -> dict:
    """Trailing vol and 7d return from price history."""
    if symbol not in SYMBOLS:
        raise ValueError(f"unknown symbol: {symbol}")

    cache_key = f"indicators:{symbol}"
    if _cache_valid(cache_key):
        return _cache[cache_key]["data"]

    import numpy as np

    hist = fetch_history(symbol, period="3mo")
    points = hist.get("points") or []
    if len(points) < 8:
        raise ValueError(f"insufficient history for {symbol}")

    closes = pd.Series(
        [p["close"] for p in points],
        index=pd.to_datetime([p["date"] for p in points]),
    )
    lr = np.log(closes).diff()
    trailing_vol = float(lr.tail(22).std() * np.sqrt(252) * 100) if len(lr.dropna()) >= 22 else None

    return_7d = None
    if len(closes) >= 8:
        ret = (closes.iloc[-1] / closes.iloc[-8] - 1) * 100
        return_7d = round(float(ret), 2)

    payload = {
        "symbol": symbol,
        "trailing_vol_22d": round(trailing_vol, 2) if trailing_vol is not None else None,
        "return_7d_pct": return_7d,
        "as_of": points[-1]["date"],
        "stale": hist.get("stale", False),
    }
    _cache[cache_key] = {"data": payload, "fetched_at": datetime.now(timezone.utc)}
    return payload
