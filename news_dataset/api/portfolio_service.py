"""Portfolio -> GPR/geopolitical risk analysis.

Stateless: the caller hands us a holdings list (from a broker CSV export or a
paste box); we resolve each ticker to a sector, aggregate into a few macro
"channels" that geopolitical risk actually moves (broad risk-off, energy/oil
supply, trade/freight), and blend those channel exposures with the live GPR
signals this platform already produces (overall GPR level + per-corridor
threat). No user model, no persistence — that's post-hackathon (broker OAuth,
saved portfolios) and deliberately not built here.

The bridge to existing data:
  * broad pressure   = where today's GPR index sits in its own history (0-100)
  * energy pressure  = hottest threat_index among energy-exposed corridors
  * trade pressure   = hottest threat_index among goods-exposed corridors
Each sector carries signed loadings on those three channels (+ = headwind,
- = tailwind, e.g. IT exporters benefit from a weak rupee in a risk-off tape).
portfolio_risk = clamp( sum_holdings weight x (loadings . pressures) , 0..100 ).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from pathlib import Path

from news_dataset.api.explain import additive_explanation, term
from news_dataset.api.gpr_service import get_corridors, get_gpr_current, get_gpr_history
from news_dataset.api.market_service import _get_yfinance

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GPR_OIL_CSV = _REPO_ROOT / "gpr_index" / "outputs" / "gpr_oil_daily.csv"
_USDINR_CSV = _REPO_ROOT / "nifty-50" / "data" / "USDINR.csv"

# Signed loadings per (yfinance/GICS) sector on the three channels.
# Signed loadings per GICS sector on the risk channels (+ = hurt by that
# pressure, - = helped). These PRIORS are the hand-set fallback used only when
# the fitted file (nifty-50/output/sector_factors.json, produced by
# fit_sector_betas.py) is absent. When that file is present its data-estimated
# betas are used instead — see _load_factors(). Fitted channels are
# {broad, energy, fx}; the prior "trade" channel is retained for the fallback.
_PRIOR_FACTORS: dict[str, dict[str, float]] = {
    "Energy":                 {"energy": 0.8, "trade": 0.1, "broad": 0.2},
    "Utilities":              {"energy": 0.4, "trade": 0.0, "broad": 0.1},
    "Basic Materials":        {"energy": 0.4, "trade": 0.3, "broad": 0.3},
    "Consumer Cyclical":      {"energy": 0.5, "trade": 0.4, "broad": 0.4},
    "Consumer Defensive":     {"energy": 0.3, "trade": 0.2, "broad": 0.2},
    "Industrials":            {"energy": 0.2, "trade": 0.3, "broad": 0.1},
    "Financial Services":     {"energy": 0.0, "trade": 0.0, "broad": 0.4},
    "Real Estate":            {"energy": 0.0, "trade": 0.0, "broad": 0.3},
    "Communication Services": {"energy": 0.0, "trade": 0.1, "broad": 0.2},
    # Exporters: a risk-off tape weakens the rupee, which helps USD earners.
    "Technology":             {"energy": 0.1, "trade": 0.1, "broad": -0.5},
    "Healthcare":             {"energy": 0.0, "trade": 0.2, "broad": -0.2},
}
_DEFAULT_FACTORS = {"energy": 0.1, "trade": 0.1, "broad": 0.3}

_FITTED_FACTORS_PATH = _REPO_ROOT / "nifty-50" / "output" / "sector_factors.json"


def _load_factors() -> tuple[dict[str, dict[str, float]], str]:
    """Prefer data-fitted betas (fit_sector_betas.py); fall back to priors."""
    try:
        if _FITTED_FACTORS_PATH.exists():
            with open(_FITTED_FACTORS_PATH) as f:
                fitted = json.load(f)
            if fitted:
                return fitted, "fitted"
    except Exception:
        logger.warning("failed reading fitted sector factors; using priors")
    return _PRIOR_FACTORS, "prior"


SECTOR_FACTORS, BETAS_SOURCE = _load_factors()

_CHANNELS_ORDER = ["broad", "energy", "fx", "trade"]
_CHANNEL_LABEL = {"broad": "GPR", "energy": "Oil", "fx": "INR", "trade": "Trade"}


def _tilt(loading: float) -> str:
    # + loading = hurt by an adverse move (headwind); - = helped (tailwind).
    if loading > 0.12:
        return "headwind"
    if loading < -0.12:
        return "tailwind"
    return "neutral"


def sector_beta_table() -> list[dict]:
    """The fitted (or prior) sector loadings as a display table for the UI."""
    rows: list[dict] = []
    for sector, loadings in SECTOR_FACTORS.items():
        channels = [
            {"channel": ch, "label": _CHANNEL_LABEL.get(ch, ch),
             "loading": round(float(v), 3), "tilt": _tilt(float(v))}
            for ch in _CHANNELS_ORDER
            if (v := loadings.get(ch)) is not None
        ]
        dominant = max(channels, key=lambda c: abs(c["loading"]), default=None)
        rows.append({
            "sector": sector,
            "channels": channels,
            "dominant": dominant["channel"] if dominant else None,
            "tilt": dominant["tilt"] if dominant else "neutral",
        })
    return sorted(rows, key=lambda r: r["sector"])

# Offline/rate-limit hedge for the demo: seed the common NSE large caps so the
# analysis works even when yfinance's .info lookups get throttled. yfinance is
# still the general path for anything not listed here.
_SECTOR_SEED: dict[str, str] = {
    "RELIANCE": "Energy", "ONGC": "Energy", "BPCL": "Energy", "IOC": "Energy",
    "COALINDIA": "Energy", "NTPC": "Utilities", "POWERGRID": "Utilities",
    "TCS": "Technology", "INFY": "Technology", "WIPRO": "Technology",
    "HCLTECH": "Technology", "TECHM": "Technology",
    "HDFCBANK": "Financial Services", "ICICIBANK": "Financial Services",
    "SBIN": "Financial Services", "KOTAKBANK": "Financial Services",
    "AXISBANK": "Financial Services", "BAJFINANCE": "Financial Services",
    "MARUTI": "Consumer Cyclical", "TATAMOTORS": "Consumer Cyclical",
    "M&M": "Consumer Cyclical", "TITAN": "Consumer Cyclical",
    "HINDUNILVR": "Consumer Defensive", "ITC": "Consumer Defensive",
    "NESTLEIND": "Consumer Defensive", "TATACONSUM": "Consumer Defensive",
    "SUNPHARMA": "Healthcare", "DRREDDY": "Healthcare", "CIPLA": "Healthcare",
    "LT": "Industrials", "ADANIPORTS": "Industrials",
    "TATASTEEL": "Basic Materials", "JSWSTEEL": "Basic Materials",
    "HINDALCO": "Basic Materials", "ULTRACEMCO": "Basic Materials",
    "BHARTIARTL": "Communication Services",
}

_sector_cache: dict[str, str] = {}


# NSE trading-symbol series suffixes (Zerodha/Kite export as RELIANCE-EQ etc.).
_NSE_SERIES = "EQ|BE|BZ|SM|ST|IQ|GB|GS|MF|N1|N2|N3|N4|N5|N6|N7|N8|N9"


def _base_symbol(ticker: str) -> str:
    """RELIANCE.NS / RELIANCE.BO / reliance-eq / reliance -> RELIANCE for seed lookup."""
    t = re.sub(r"\.(NS|BO)$", "", ticker.strip().upper())
    return re.sub(rf"-({_NSE_SERIES})$", "", t)


def resolve_sector(ticker: str) -> str:
    base = _base_symbol(ticker)
    if base in _sector_cache:
        return _sector_cache[base]
    sector = _SECTOR_SEED.get(base)
    if sector is None:
        yf = _get_yfinance()
        if yf is not None:
            try:
                # Use the normalised Yahoo symbol (GTLINFRA.NS), not the raw
                # Zerodha tradingsymbol (gtlinfra-eq), which yfinance can't resolve.
                info = yf.Ticker(_yf_symbol(ticker)).info or {}
                sector = info.get("sector")
            except Exception:
                logger.warning("yfinance sector lookup failed for %s", ticker)
    sector = sector or "Unclassified"
    _sector_cache[base] = sector
    return sector


def parse_holdings(raw: str | list[dict]) -> list[dict]:
    """Accept a CSV/paste string or a list of dict rows -> [{ticker, value}].

    Each row may carry `value` (rupees), `qty`/`quantity`, or `weight`. A
    string is parsed as CSV/pasted lines; a header row is optional. The first
    field is the ticker; the first numeric field is the value proxy. Weights
    are normalized downstream, so the proxy's units don't matter as long as
    they're consistent.
    """
    if isinstance(raw, str):
        rows = _parse_text(raw)
    else:
        rows = raw or []

    out: list[dict] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").strip()
        if not ticker:
            continue
        proxy = _first_number(row.get("value"), row.get("qty"),
                              row.get("quantity"), row.get("weight"))
        out.append({"ticker": ticker, "value": proxy})
    return out


def _parse_text(text: str) -> list[dict]:
    rows: list[dict] = []
    reader = csv.reader(io.StringIO(text.strip()))
    for fields in reader:
        fields = [f.strip() for f in fields if f.strip() != ""]
        if not fields:
            continue
        ticker = fields[0]
        # skip an obvious header line
        if ticker.lower() in {"ticker", "symbol", "instrument", "scrip"}:
            continue
        value = None
        for f in fields[1:]:
            n = _to_float(f)
            if n is not None:
                value = n
                break
        rows.append({"ticker": ticker, "value": value})
    return rows


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return None


def _first_number(*vals) -> float | None:
    for v in vals:
        n = _to_float(v)
        if n is not None:
            return n
    return None


def _weights(holdings: list[dict]) -> list[dict]:
    """Normalize value proxies to weights summing to 1; equal-weight if absent."""
    values = [h.get("value") for h in holdings]
    total = sum(v for v in values if v and v > 0)
    n = len(holdings)
    for h in holdings:
        v = h.get("value")
        h["weight"] = (v / total) if (total > 0 and v and v > 0) else (1.0 / n if n else 0.0)
    return holdings


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _gpr_percentile(current: float, history: list[dict]) -> float:
    vals = [h["gpr_index"] for h in history if h.get("gpr_index") is not None]
    if not vals:
        # No history: map around the ~100 quiet-day baseline onto 0-100.
        return _clamp(current - 50.0)
    below = sum(1 for v in vals if v <= current)
    return _clamp(100.0 * below / len(vals))


def _read_col(path: Path, col: str) -> list[float]:
    try:
        with open(path, newline="") as f:
            return [v for row in csv.DictReader(f) if (v := _to_float(row.get(col))) is not None]
    except Exception:
        return []


def _pctile(value: float, series: list[float]) -> float | None:
    if not series:
        return None
    return _clamp(100.0 * sum(1 for v in series if v <= value) / len(series))


def _gpr_oil_pressure() -> tuple[float | None, float | None]:
    """Energy channel: percentile of the latest India-native gpr_oil index."""
    vals = _read_col(_GPR_OIL_CSV, "gpr_oil_index")
    if not vals:
        return None, None
    return _pctile(vals[-1], vals), round(vals[-1], 1)


def _fx_pressure() -> float | None:
    """FX channel: percentile of the latest 5-day USD/INR move (INR depreciation stress)."""
    close = _read_col(_USDINR_CSV, "Close")
    if len(close) < 10:
        return None
    chgs = [(close[i] - close[i - 5]) / close[i - 5] * 100 for i in range(5, len(close)) if close[i - 5]]
    return _pctile(chgs[-1], chgs) if chgs else None


def _channel_pressures() -> dict:
    """Live 0-100 pressure per channel, plus what drives them.

    broad  = percentile of today's GPR index in its history
    energy = percentile of the India-native gpr_oil index (falls back to the
             hottest energy-corridor threat if the gpr_oil CSV isn't built yet)
    fx     = percentile of the recent USD/INR move (INR depreciation stress)
    trade  = hottest goods-corridor threat (used only by the fallback priors)
    """
    gpr = get_gpr_current() or {}
    gpr_index = float(gpr.get("gpr_index") or 0.0)
    broad = _gpr_percentile(gpr_index, get_gpr_history(limit=400))

    corridors = (get_corridors() or {}).get("corridors") or []

    def _hottest(rows):
        best, val = None, 0.0
        for c in rows:
            t = float(c.get("threat_index") or 0.0)
            if best is None or t > val:
                best, val = c, t
        return best, _clamp(val)

    energy_top, energy_corr = _hottest([c for c in corridors if (c.get("energy_exposure") or 0) > 0])
    trade_top, trade = _hottest([c for c in corridors if (c.get("goods_exposure") or 0) > 0])

    oil_pressure, oil_index = _gpr_oil_pressure()
    energy = oil_pressure if oil_pressure is not None else energy_corr
    fx = _fx_pressure()
    fx = fx if fx is not None else 0.0

    return {
        "pressures": {"broad": round(broad, 1), "energy": round(energy, 1),
                      "fx": round(fx, 1), "trade": round(trade, 1)},
        "gpr_index": round(gpr_index, 1),
        "gpr_oil_index": oil_index,
        "as_of": gpr.get("date"),
        "energy_corridor": _corridor_name(energy_top),
        "trade_corridor": _corridor_name(trade_top),
    }


def _corridor_name(c: dict | None) -> str | None:
    if not c:
        return None
    return c.get("corridor_name") or c.get("corridor")


def _sector_risk(sector: str, pressures: dict) -> float:
    f = SECTOR_FACTORS.get(sector, _DEFAULT_FACTORS)
    return sum(v * pressures.get(ch, 0.0) for ch, v in f.items())


def _score(holdings: list[dict], pressures: dict) -> float:
    return _clamp(sum(h["weight"] * _sector_risk(h["sector"], pressures) for h in holdings))


def _band(score: float) -> str:
    if score >= 66:
        return "High"
    if score >= 40:
        return "Elevated"
    if score >= 18:
        return "Moderate"
    return "Low"


# --- Per-holding GPR-vs-price overlay + joint stress ------------------------
# For each holding we align the native GPR index with the stock's own price over
# the same window and return a small dual-line series (rebased to 100) plus a
# "joint stress" reading — the same 60/40 geo-vs-vol blend the nifty-50
# dual-signal uses (forsyt_gpr.dual_signal.joint_stress), applied per ticker so
# the vol half reflects THAT stock's turbulence rather than NIFTY's.
_MAX_OVERLAY_TICKERS = 16   # ponytail: bound yfinance cost — charts the biggest holdings only
_OVERLAY_POINTS = 48        # downsample the dual-line sparkline to keep the payload small


def _joint_band(score: float) -> str:
    if score >= 75:
        return "High stress"
    if score >= 50:
        return "Watch"
    return "Calm"


def _yf_symbol(ticker: str) -> str:
    """-> Yahoo symbol: keep an explicit exchange suffix (RELIANCE.NS, AAPL);
    otherwise normalise the series suffix and append '.NS' (reliance-eq -> RELIANCE.NS)."""
    t = ticker.strip().upper()
    return t if "." in t else f"{_base_symbol(ticker)}.NS"


def _gpr_series():
    """{date_str: gpr_index} for the native index window, ascending by date."""
    out: dict[str, float] = {}
    for row in get_gpr_history(limit=400) or []:
        d, g = row.get("date"), row.get("gpr_index")
        if d and g is not None:
            out[str(d)[:10]] = float(g)
    return dict(sorted(out.items()))


def _overlay(px, gpr, broad_pct, np, pd) -> dict | None:
    """Align one stock's close history with the GPR series and summarise it."""
    px = px.copy()
    px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
    df = pd.concat([gpr.rename("gpr"), px.rename("px")], axis=1).dropna()
    if len(df) < 10:
        return None

    # Correlation of daily GPR change vs daily stock return (does this holding
    # move with geopolitical risk?). +ve = tends to rise as GPR rises.
    ch = pd.concat([df["gpr"].pct_change(), df["px"].pct_change()], axis=1).dropna()
    corr = round(float(ch.iloc[:, 0].corr(ch.iloc[:, 1])), 2) if len(ch) > 5 else None

    # Realized-vol percentile (22d annualised) -> the vol half of joint stress.
    lr = np.log(df["px"]).diff()
    rv = (lr.rolling(22).std() * np.sqrt(252) * 100).dropna()
    vol_pct = round(100.0 * float((rv <= rv.iloc[-1]).mean()), 1) if len(rv) else 50.0
    joint = round(0.6 * broad_pct + 0.4 * vol_pct, 1)

    gpr_b = df["gpr"] / df["gpr"].iloc[0] * 100.0
    px_b = df["px"] / df["px"].iloc[0] * 100.0
    idx = np.unique(np.linspace(0, len(df) - 1, min(_OVERLAY_POINTS, len(df))).astype(int))
    series = [
        {"d": df.index[i].strftime("%Y-%m-%d"),
         "gpr": round(float(gpr_b.iloc[i]), 1),
         "px": round(float(px_b.iloc[i]), 1)}
        for i in idx
    ]
    return {
        "series": series,
        "corr": corr,
        "vol_percentile": vol_pct,
        "joint_stress": joint,
        "joint_band": _joint_band(joint),
        "price_change_pct": round(float(px_b.iloc[-1] - 100.0), 1),
        "gpr_change_pct": round(float(gpr_b.iloc[-1] - 100.0), 1),
    }


def _attach_overlays(holdings: list[dict], broad_pct: float) -> None:
    """Fetch price history for the top holdings and attach an `overlay` in place.

    Best-effort: if yfinance/pandas are unavailable or the download fails, every
    holding is simply left without an overlay and the rest of the analysis stands.
    """
    yf = _get_yfinance()
    if yf is None:
        return
    try:
        import numpy as np
        import pandas as pd
    except Exception:
        return

    raw_gpr = _gpr_series()
    if len(raw_gpr) < 10:
        return
    gpr = pd.Series(raw_gpr)
    gpr.index = pd.to_datetime(gpr.index).normalize()

    targets = sorted(holdings, key=lambda h: h.get("weight", 0.0), reverse=True)[:_MAX_OVERLAY_TICKERS]
    symbols = {h["ticker"]: _yf_symbol(h["ticker"]) for h in targets}
    start = gpr.index.min().strftime("%Y-%m-%d")
    end = (gpr.index.max() + pd.Timedelta(days=3)).strftime("%Y-%m-%d")

    try:
        raw = yf.download(sorted(set(symbols.values())), start=start, end=end,
                          progress=False, auto_adjust=True)
    except Exception:
        logger.warning("overlay yfinance download failed")
        return
    closes = raw["Close"] if isinstance(raw, pd.DataFrame) and "Close" in raw else raw

    for h in targets:
        sym = symbols[h["ticker"]]
        try:
            if isinstance(closes, pd.DataFrame):
                if sym not in closes.columns:
                    continue
                px = closes[sym]
            else:
                px = closes
            px = pd.to_numeric(px, errors="coerce").dropna()
            overlay = _overlay(px, gpr, broad_pct, np, pd)
            if overlay:
                h["overlay"] = overlay
        except Exception:
            logger.debug("overlay failed for %s", h["ticker"])


_EXPLAIN_CAVEAT = "Illustrative geopolitical-risk read. Not investment advice."


def _holding_explain(h: dict, pressures: dict) -> dict:
    """Exact additive breakdown of one holding's risk contribution, by channel."""
    f = SECTOR_FACTORS.get(h["sector"], _DEFAULT_FACTORS)
    terms = [
        term(
            _CHANNEL_LABEL.get(ch, ch),
            pressures.get(ch, 0.0),
            h["weight"] * loading,
            note=f"loading {loading:+.2f} × weight {h['weight'] * 100:.0f}%",
        )
        for ch, loading in f.items()
    ]
    return additive_explanation(
        h["contribution"], terms,
        "contribution = weight × Σ(loading × pressure)", _EXPLAIN_CAVEAT,
    )


def _portfolio_explain(holdings: list[dict], pressures: dict, score: float) -> dict:
    """Exact additive breakdown of the portfolio score, grouped by risk channel."""
    agg: dict[str, float] = {}
    for h in holdings:
        f = SECTOR_FACTORS.get(h["sector"], _DEFAULT_FACTORS)
        for ch, loading in f.items():
            agg[ch] = agg.get(ch, 0.0) + h["weight"] * loading
    terms = [
        term(_CHANNEL_LABEL.get(ch, ch), pressures.get(ch, 0.0), w,
             note=f"Σ weight×loading = {w:+.2f}")
        for ch, w in agg.items()
    ]
    return additive_explanation(
        score, terms,
        "risk = Σ_channel  pressure × Σ_holdings(weight × loading)", _EXPLAIN_CAVEAT,
    )


def analyze_portfolio(raw: str | list[dict]) -> dict:
    holdings = _weights(parse_holdings(raw))
    if not holdings:
        return {"error": "no holdings provided"}

    ctx = _channel_pressures()
    pressures = ctx["pressures"]

    for h in holdings:
        h["sector"] = resolve_sector(h["ticker"])
        risk = _sector_risk(h["sector"], pressures)
        h["sector_risk"] = round(risk, 1)
        h["contribution"] = round(h["weight"] * risk, 2)
        h["weight"] = round(h["weight"], 4)
        h["explain"] = _holding_explain(h, pressures)

    _attach_overlays(holdings, pressures.get("broad", 50.0))

    score = _score(holdings, pressures)

    # Sector rollup.
    sectors: dict[str, dict] = {}
    for h in holdings:
        s = sectors.setdefault(h["sector"], {"sector": h["sector"], "weight": 0.0, "contribution": 0.0})
        s["weight"] += h["weight"]
        s["contribution"] += h["contribution"]
    sector_rows = sorted(sectors.values(), key=lambda s: s["contribution"], reverse=True)
    for s in sector_rows:
        s["weight"] = round(s["weight"], 4)
        s["contribution"] = round(s["contribution"], 2)

    # Scenario deltas. An oil-supply crisis hits Indian equities mainly through
    # the rupee (fx is the dominant fitted channel for a net crude importer), so
    # the shock lifts both the energy (gpr_oil) and fx pressures together.
    shock = {**pressures, "energy": 100.0, "fx": max(pressures.get("fx", 0.0), 85.0),
             "trade": max(pressures.get("trade", 0.0), 60.0)}
    calm = {"broad": 5.0, "energy": 5.0, "fx": 5.0, "trade": 5.0}

    return {
        "as_of": ctx["as_of"],
        "gpr_index": ctx["gpr_index"],
        "gpr_oil_index": ctx.get("gpr_oil_index"),
        "betas_source": BETAS_SOURCE,
        "pressures": pressures,
        "drivers": {"energy_corridor": ctx["energy_corridor"], "trade_corridor": ctx["trade_corridor"]},
        "risk_score": round(score, 1),
        "risk_band": _band(score),
        "explain": _portfolio_explain(holdings, pressures, round(score, 1)),
        "holdings": sorted(holdings, key=lambda h: h["contribution"], reverse=True),
        "sectors": sector_rows,
        "scenarios": [
            {
                "name": f"Oil-supply crisis ({ctx['energy_corridor'] or 'Strait of Hormuz'})",
                "score": round(_score(holdings, shock), 1),
                "delta": round(_score(holdings, shock) - score, 1),
            },
            {
                "name": "Broad de-escalation",
                "score": round(_score(holdings, calm), 1),
                "delta": round(_score(holdings, calm) - score, 1),
            },
        ],
        "note": "Illustrative geopolitical-risk read. Not investment advice; "
                "holdings are analysed statelessly and not stored.",
    }


def demo() -> None:
    """Self-check: dot-product mechanics + parsing. Uses whichever factor set is
    loaded; with fitted betas, FX is the dominant channel so banks (high INR
    beta) out-risk pharma (low) under a pure FX shock."""
    fin_fx = SECTOR_FACTORS.get("Financial Services", {})
    if "fx" in fin_fx:  # fitted factors present
        p = {"broad": 0.0, "energy": 0.0, "fx": 100.0, "trade": 0.0}
        fin = _score([{"weight": 1.0, "sector": "Financial Services"}], p)
        hc = _score([{"weight": 1.0, "sector": "Healthcare"}], p)
        assert fin > hc, (fin, hc)  # banks more INR-sensitive than pharma
    else:  # prior fallback
        p = {"broad": 60.0, "energy": 70.0, "trade": 40.0}
        assert _score([{"weight": 1.0, "sector": "Energy"}], p) > \
               _score([{"weight": 1.0, "sector": "Financial Services"}], p)
    # Parsing: header skipped, value proxy picked, weights normalize to 1.
    hs = _weights(parse_holdings("Ticker,Qty\nRELIANCE.NS,10\nINFY.NS,30"))
    assert abs(sum(h["weight"] for h in hs) - 1.0) < 1e-9
    assert abs(hs[0]["weight"] - 0.25) < 1e-9, hs

    # Zerodha-style series suffixes normalise so the seed lookup + yahoo symbol work.
    assert _base_symbol("reliance-eq") == "RELIANCE", _base_symbol("reliance-eq")
    assert _base_symbol("NTPC-BE") == "NTPC"
    assert _yf_symbol("hdfcbank-eq") == "HDFCBANK.NS", _yf_symbol("hdfcbank-eq")
    assert resolve_sector("reliance-eq") == "Energy"  # was "Unclassified" before the fix

    # Explainability: per-holding channel terms must reconcile to the holding's
    # contribution (exact additive attribution — no SHAP/LIME needed here).
    p = {"broad": 60.0, "energy": 70.0, "fx": 40.0, "trade": 20.0}
    h = {"sector": "Energy", "weight": 0.5}
    h["contribution"] = round(h["weight"] * _sector_risk(h["sector"], p), 2)
    ex = _holding_explain(h, p)
    assert abs(sum(t["contribution"] for t in ex["terms"]) - h["contribution"]) < 0.05, ex

    # Overlay math (guarded — only if pandas/numpy are installed). A stock that
    # rises exactly when GPR rises must report a positive correlation, and the
    # rebased series must start at 100 for both lines.
    try:
        import numpy as np
        import pandas as pd
    except Exception:
        pd = None
    if pd is not None:
        dates = pd.date_range("2026-01-01", periods=60, freq="D")
        gpr = pd.Series(100 + np.arange(60) * 0.5, index=dates)
        px = pd.Series(200 + np.arange(60) * 1.0, index=dates)  # moves with GPR
        ov = _overlay(px, gpr, broad_pct=60.0, np=np, pd=pd)
        assert ov and ov["corr"] is not None and ov["corr"] > 0.9, ov
        assert ov["series"][0]["gpr"] == 100.0 and ov["series"][0]["px"] == 100.0, ov
        assert ov["joint_band"] in {"Calm", "Watch", "High stress"}, ov

    print("portfolio_service self-check OK:", {"betas_source": BETAS_SOURCE})


if __name__ == "__main__":
    demo()
