"""Dual-signal product layer: geopolitical risk + NIFTY vol side by side.

BEGINNER NOTE -- this is the file that actually powers the live dashboard.
Everything above it in this package (`data.py`, `features.py`,
`vol_model.py`) is plumbing and research machinery; this file is where it
gets turned into the actual JSON payload the React frontend renders (see
`GET /api/market/dual-signal`, wired up in
`news_dataset/api/gpr_service.py::build_dual_signal_payload()`).

The product idea, in plain language: rather than claiming "geopolitical risk
X means NIFTY will do Y" (a claim the research in `vol_model.py` shows isn't
actually supported out-of-sample), the dashboard instead shows TWO
independent readings side by side -- how tense does the geopolitical news
look right now, and how turbulent does the market look right now -- plus a
combined "how worried should I be, overall" score. `build_dual_signal()` at
the bottom of this file assembles all four pieces below into that one
payload.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from . import data, vol_model
from .data import forward_realized_vol, realized_vol

BASELINE_GPR_MEAN = 100.0
BASELINE_GPR_STD = 35.0
IN_SAMPLE_BASELINE_MIN_DAYS = 2
CALDARA_BASELINE_MIN_DAYS = 60
ANALOG_TOLERANCE = 10.0
ANALOG_HORIZON = 5

NOTABLE_EVENTS = {
    "2008-11": "26/11 Mumbai",
    "2019-02": "Pulwama / Balakot",
    "2020-06": "Galwan",
    "2025-05": "2025 Pakistan flare-up",
}


def _regime_from_z(z: float) -> str:
    if z < 0:
        return "LOW"
    if z < 1:
        return "MODERATE"
    if z < 2:
        return "ELEVATED"
    return "HIGH"


def _vol_regime(high_vol_prob: float) -> str:
    if high_vol_prob >= 0.5:
        return "HIGH_VOL"
    if high_vol_prob >= 0.25:
        return "ELEVATED"
    return "NORMAL"


def _percentile(series: pd.Series, value: float, window: int = 252) -> float:
    history = series.dropna().tail(window)
    if history.empty:
        return 50.0
    return float(100.0 * (history <= value).mean())


def _gpr_baseline(gpr: pd.Series) -> tuple[float, float, str]:
    """Caldara-scale baseline for long history; fixed 100/35 during India index ramp."""
    clean = gpr.dropna()
    if len(clean) >= CALDARA_BASELINE_MIN_DAYS:
        return BASELINE_GPR_MEAN, BASELINE_GPR_STD, "caldara"
    if len(clean) >= IN_SAMPLE_BASELINE_MIN_DAYS:
        return BASELINE_GPR_MEAN, BASELINE_GPR_STD, "caldara_ramp"
    return BASELINE_GPR_MEAN, BASELINE_GPR_STD, "caldara"


def _gpr_moving_average(gf: pd.DataFrame, gpr: pd.Series, column: str, window: int) -> float:
    if column in gf.columns and pd.notna(gf[column].iloc[-1]):
        return float(gf[column].iloc[-1])
    return float(gpr.tail(min(window, len(gpr))).mean())


def geo_regime(gf: pd.DataFrame) -> dict[str, Any]:
    """Build the geopolitical half of the dual signal.

    In plain language: this takes today's GPR risk reading and asks "is
    that actually high, historically speaking, or just a normal day?" It
    does this by converting the raw index value into a z-score (how many
    standard deviations away from a baseline average it is -- the Caldara
    benchmark's own long-run average of 100 and spread of 35, since
    Forsyt's own India index doesn't have enough history yet to compute a
    reliable average of its own -- see `_gpr_baseline()`), then buckets that
    z-score into a plain-English regime label (LOW / MODERATE / ELEVATED /
    HIGH). It also reports a percentile (what fraction of all known days
    were calmer than today), a 7-day % change, and the raw
    threats/acts sub-scores when available. This whole function only ever
    looks BACKWARD at history that has already happened -- it is not making
    any prediction about the future.
    """
    data.validate_gpr_frame(gf)
    gpr = gf["gpr"].astype(float)
    as_of = gpr.index[-1]
    gpr_today = float(gpr.iloc[-1])
    gpr_7ma = _gpr_moving_average(gf, gpr, "gpr_7ma", 7)
    gpr_30ma = _gpr_moving_average(gf, gpr, "gpr_30ma", 30)
    baseline_mean, baseline_std, baseline_mode = _gpr_baseline(gpr)
    z = (gpr_today - baseline_mean) / baseline_std
    index_days = int(len(gpr))
    change_7d_pct: float | None = None
    if len(gpr) >= 8:
        prior = float(gpr.iloc[-8])
        if prior:
            change_7d_pct = round((gpr_today / prior - 1.0) * 100.0, 2)

    out: dict[str, Any] = {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "gpr_index": round(gpr_today, 2),
        "gpr_7ma": round(gpr_7ma, 2),
        "gpr_30ma": round(gpr_30ma, 2),
        "regime": _regime_from_z(z),
        "z_score": round(z, 3),
        "baseline_mode": baseline_mode,
        "index_days": index_days,
        "change_7d_pct": change_7d_pct,
        "geo_percentile": round(_percentile(gpr, gpr_today, window=len(gpr)), 1),
        "geo_percentile_confidence": "low" if index_days < 8 else "normal",
    }
    if "gpr_threats" in gf.columns:
        out["gpr_threats"] = round(float(gf["gpr_threats"].iloc[-1]), 2)
    if "gpr_acts" in gf.columns:
        out["gpr_acts"] = round(float(gf["gpr_acts"].iloc[-1]), 2)
    return out


def _trailing_vol_fallback(nifty: pd.Series, horizon: int, reason: str) -> dict[str, Any]:
    """Naive forecast when the XGB market model cannot run."""
    trailing = realized_vol(nifty, 22)
    if not trailing.notna().any():
        raise ValueError(reason)
    trailing_val = float(trailing.dropna().iloc[-1])
    hist = trailing.dropna().tail(252)
    median = float(hist.median()) if not hist.empty else trailing_val
    p75 = float(hist.quantile(0.75)) if len(hist) >= 22 else trailing_val
    if trailing_val >= p75:
        high_vol_prob = 0.55
    elif trailing_val >= median:
        high_vol_prob = 0.25
    else:
        high_vol_prob = 0.08
    return_7d = None
    if len(nifty) >= 8:
        return_7d = round(float((nifty.iloc[-1] / nifty.iloc[-8] - 1) * 100), 2)
    as_of = nifty.index[-1]
    return {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "horizon_days": horizon,
        "high_vol_threshold": round(p75, 2),
        "target_resolves_on": None,
        "market_only": {
            "vol_forecast": round(trailing_val, 2),
            "high_vol_prob": round(high_vol_prob, 3),
        },
        "model": "trailing_vol",
        "fallback_reason": reason,
        "trailing_vol_22d": round(trailing_val, 2),
        "return_7d_pct": return_7d,
        "vol_percentile": round(_percentile(trailing.dropna(), trailing_val), 1),
    }


def nifty_vol_signal(gf: pd.DataFrame, nifty: pd.Series, horizon: int = 5) -> dict[str, Any]:
    """Market-only NIFTY volatility signal (GPR is shown separately).

    In plain language: this is the "how choppy is the stock market likely
    to be over the next 5 trading days?" half of the dashboard. It tries
    the real forecasting model first (`vol_model.latest_market_forecast()`,
    market-data-only -- see that function's docstring for why GPR is
    deliberately excluded from this forecast), and if that model can't run
    for any reason (not enough price history, etc. -- it raises
    `ValueError`), it silently falls back to a much simpler rule based on
    trailing volatility (`_trailing_vol_fallback()`), so the dashboard
    always has SOMETHING to show rather than an error. Either way, the
    result also includes a plain trailing-volatility reading and a
    percentile, and buckets the forecast's HIGH_VOL probability into a
    NORMAL / ELEVATED / HIGH_VOL label for the "vol dial" on the dashboard.
    """
    trailing = realized_vol(nifty, 22)
    trailing_val = float(trailing.dropna().iloc[-1]) if trailing.notna().any() else None
    return_7d = None
    if len(nifty) >= 8:
        return_7d = round(float((nifty.iloc[-1] / nifty.iloc[-8] - 1) * 100), 2)

    try:
        forecast = vol_model.latest_market_forecast(nifty, horizon=horizon)
    except ValueError as exc:
        forecast = _trailing_vol_fallback(nifty, horizon, str(exc))

    market = forecast["market_only"]
    vol_pct = None
    if trailing_val is not None and trailing.notna().any():
        vol_pct = round(_percentile(trailing.dropna(), trailing_val), 1)

    out: dict[str, Any] = {
        "as_of": forecast["as_of"],
        "available": True,
        "horizon_days": forecast["horizon_days"],
        "vol_forecast_5d": market["vol_forecast"],
        "high_vol_prob": market["high_vol_prob"],
        "high_vol_threshold": forecast.get("high_vol_threshold"),
        "target_resolves_on": forecast.get("target_resolves_on"),
        "regime": _vol_regime(market["high_vol_prob"]),
        "trailing_vol_22d": round(trailing_val, 2) if trailing_val is not None else None,
        "return_7d_pct": return_7d,
        "vol_percentile": vol_pct,
        "model": forecast.get("model", "market_only"),
    }
    if forecast.get("fallback_reason"):
        out["fallback_reason"] = forecast["fallback_reason"]
    return out


def joint_stress(geo: dict[str, Any], nifty: dict[str, Any]) -> dict[str, Any]:
    """Transparent composite stress score (60% geo, 40% vol percentile).

    In plain language: this blends the two independent readings above
    (geopolitical percentile and market-volatility percentile) into ONE
    "how worried should I be right now, overall" number between 0 and 100,
    weighted 60% geopolitics / 40% market volatility -- an intentionally
    simple, fixed, and fully transparent formula (no machine learning here
    at all), so anyone reading the dashboard can recompute it by hand from
    the two percentiles shown elsewhere on the page. The narrative text is
    just a plain-English gloss on the same numbers -- e.g. calling out when
    geopolitics is elevated but markets are still calm, which is arguably
    the most useful case to flag (a risk that hasn't yet shown up in prices).
    "Percentile" here means "higher than what % of days on record" -- e.g.
    a geo_percentile of 90 means today's geopolitical reading is tenser than
    90% of days in the available history.
    """
    geo_pct = float(geo.get("geo_percentile", 50.0))
    vol_pct = float(nifty.get("vol_percentile", 50.0))
    score = round(0.6 * geo_pct + 0.4 * vol_pct, 1)
    if score >= 75:
        regime, narrative = "HIGH_STRESS", "Geopolitical risk and market volatility both elevated."
    elif score >= 50:
        regime = "WATCH"
        if geo_pct >= 60 and vol_pct < 50:
            narrative = (
                "Geopolitical risk elevated while market vol is moderate — "
                "geo-market gap worth monitoring."
            )
        elif vol_pct >= 60 and geo_pct < 50:
            narrative = "Market volatility elevated with calmer geopolitical news flow."
        else:
            narrative = "One or both signals above median."
    else:
        regime, narrative = "CALM", "Normal conditions on both signals."

    return {
        "stress_score": score,
        "stress_regime": regime,
        "geo_percentile": round(geo_pct, 1),
        "vol_percentile": round(vol_pct, 1),
        "narrative": narrative,
    }


def historical_analog(
    gf: pd.DataFrame,
    nifty: pd.Series,
    gpr_today: float,
    tolerance: float = ANALOG_TOLERANCE,
    horizon: int = ANALOG_HORIZON,
) -> dict[str, Any]:
    """What NIFTY did on past days with similar GPR levels (native index days only).

    In plain language: this answers "the last time geopolitical risk looked
    about like it does today, what actually happened to NIFTY afterwards?"
    It searches history for days where the GPR reading was within
    `tolerance` (default +/-10) of today's value, then reports the MEDIAN
    (the middle value, resistant to a couple of extreme outlier days
    skewing the picture) forward volatility and forward return over the
    next `horizon` (default 5) trading days across all of those matching
    days. This is a purely descriptive, look-up-the-history-books exercise
    -- NOT a model and NOT a prediction -- which is why it's presented
    separately from `nifty_vol_signal()`'s actual forecast. If any of the
    matched days fall in a month with a well-known past crisis (see
    `NOTABLE_EVENTS` above, e.g. Pulwama/Balakot or Galwan), that event's
    name is surfaced too, purely for context. "Native index days only" means
    this only looks at days where Forsyt's own GPR index actually has a
    real reading -- it does not borrow or extrapolate from the benchmark.
    """
    gpr_native = gf["gpr"].astype(float)
    fwd_vol = forward_realized_vol(nifty, horizon).reindex(gpr_native.index)
    fwd_ret = _forward_return_pct(nifty, horizon).reindex(gpr_native.index)
    frame = pd.DataFrame(
        {"gpr": gpr_native, "fwd_vol": fwd_vol, "fwd_ret": fwd_ret}
    ).dropna()
    if frame.empty:
        return {
            "sample_days": 0,
            "query": f"GPR within ±{tolerance} of {gpr_today:.1f}",
            "note": "No overlapping NIFTY forward returns on India GPR index days yet.",
        }

    mask = frame["gpr"].sub(gpr_today).abs() <= tolerance
    sample = frame.loc[mask]
    notable = [
        label
        for ym, label in NOTABLE_EVENTS.items()
        if any(pd.Timestamp(f"{ym}-01") <= idx <= idx + pd.offsets.MonthEnd(0) for idx in sample.index)
    ]
    return {
        "query": f"Days when GPR was within ±{tolerance} of {gpr_today:.1f}",
        "sample_days": int(len(sample)),
        "index_days": int(len(gpr_native)),
        "nifty_vol_median": round(float(sample["fwd_vol"].median()), 2) if len(sample) else None,
        "nifty_return_median": round(float(sample["fwd_ret"].median()), 2) if len(sample) else None,
        "notable_events": notable,
    }


def _forward_return_pct(price: pd.Series, horizon: int) -> pd.Series:
    lr = np.log(price).diff()
    return lr.shift(-1).rolling(horizon).sum().shift(-(horizon - 1)) * 100.0


def build_dual_signal(
    gf: pd.DataFrame,
    nifty: pd.Series,
    *,
    horizon: int = 5,
    top_corridor: str | None = None,
    driving_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the full dual-signal payload for API/dashboard."""
    geo = geo_regime(gf)
    market_unavailable: str | None = None
    try:
        nifty_sig = nifty_vol_signal(gf, nifty, horizon=horizon)
        trailing = realized_vol(nifty, 22)
        nifty_sig["vol_percentile"] = round(
            _percentile(trailing.dropna(), float(trailing.dropna().iloc[-1])), 1
        ) if trailing.notna().any() else 50.0
    except ValueError as exc:
        market_unavailable = str(exc)
        trailing = realized_vol(nifty, 22)
        trailing_val = float(trailing.dropna().iloc[-1]) if trailing.notna().any() else None
        return_7d = None
        if len(nifty) >= 8:
            return_7d = round(float((nifty.iloc[-1] / nifty.iloc[-8] - 1) * 100), 2)
        nifty_sig = {
            "available": False,
            "reason": market_unavailable,
            "model": "market_only",
            "vol_percentile": None,
            "trailing_vol_22d": round(trailing_val, 2) if trailing_val is not None else None,
            "return_7d_pct": return_7d,
        }

    analog = historical_analog(gf, nifty, geo["gpr_index"])
    if market_unavailable:
        joint = {
            "stress_score": None,
            "stress_regime": "UNAVAILABLE",
            "geo_percentile": round(float(geo.get("geo_percentile", 50.0)), 1),
            "vol_percentile": None,
            "narrative": (
                "Geopolitical signal live; NIFTY vol forecast unavailable "
                f"({market_unavailable})."
            ),
        }
    else:
        joint = joint_stress(geo, nifty_sig)

    if top_corridor:
        geo["top_corridor"] = top_corridor
    if driving_events:
        geo["driving_events"] = driving_events

    return {
        "geopolitical": geo,
        "nifty_volatility": nifty_sig,
        "joint_stress": joint,
        "historical_analog": analog,
        "index_start": gf.index.min().strftime("%Y-%m-%d") if len(gf) else None,
        "disclaimer": (
            "NIFTY vol signal uses market data only. GPR is shown separately. "
            "Not investment advice."
        ),
    }
