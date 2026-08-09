"""Dual-signal product layer: geopolitical risk + NIFTY vol side by side."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from . import data, vol_model
from .data import forward_realized_vol, realized_vol

BASELINE_GPR_MEAN = 100.0
BASELINE_GPR_STD = 35.0
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


def geo_regime(gf: pd.DataFrame) -> dict[str, Any]:
    """Build the geopolitical half of the dual signal."""
    data.validate_gpr_frame(gf)
    gpr = gf["gpr"].astype(float)
    as_of = gpr.index[-1]
    gpr_today = float(gpr.iloc[-1])
    gpr_7ma = float(gpr.tail(min(7, len(gpr))).mean())
    gpr_30ma = float(gpr.tail(min(30, len(gpr))).mean())
    z = (gpr_today - BASELINE_GPR_MEAN) / BASELINE_GPR_STD
    change_7d_pct = 0.0
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
        "change_7d_pct": change_7d_pct,
        "geo_percentile": round(_percentile(gpr, gpr_today), 1),
    }
    if "gpr_threats" in gf.columns:
        out["gpr_threats"] = round(float(gf["gpr_threats"].iloc[-1]), 2)
    if "gpr_acts" in gf.columns:
        out["gpr_acts"] = round(float(gf["gpr_acts"].iloc[-1]), 2)
    return out


def nifty_vol_signal(gf: pd.DataFrame, nifty: pd.Series, horizon: int = 5) -> dict[str, Any]:
    """Market-only NIFTY volatility signal (no GPR in the forecast)."""
    forecast = vol_model.latest_forecast(gf, nifty, horizon=horizon)
    market = forecast["market_only"]
    trailing = realized_vol(nifty, 22)
    trailing_val = float(trailing.dropna().iloc[-1]) if trailing.notna().any() else None
    return {
        "as_of": forecast["as_of"],
        "horizon_days": forecast["horizon_days"],
        "vol_forecast_5d": market["vol_forecast"],
        "high_vol_prob": market["high_vol_prob"],
        "high_vol_threshold": forecast["high_vol_threshold"],
        "target_resolves_on": forecast.get("target_resolves_on"),
        "regime": _vol_regime(market["high_vol_prob"]),
        "trailing_vol_22d": round(trailing_val, 2) if trailing_val is not None else None,
        "model": "market_only",
    }


def joint_stress(geo: dict[str, Any], nifty: dict[str, Any]) -> dict[str, Any]:
    """Transparent composite stress score (60% geo, 40% vol percentile)."""
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
    """What NIFTY did on past days with similar GPR levels."""
    gpr = gf["gpr"].astype(float).reindex(nifty.index, method="ffill")
    fwd_vol = forward_realized_vol(nifty, horizon)
    fwd_ret = _forward_return_pct(nifty, horizon)
    frame = pd.DataFrame({"gpr": gpr, "fwd_vol": fwd_vol, "fwd_ret": fwd_ret}).dropna()
    if frame.empty:
        return {"sample_days": 0, "query": f"GPR within ±{tolerance} of {gpr_today:.1f}"}

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
    nifty_sig = nifty_vol_signal(gf, nifty, horizon=horizon)
    trailing = realized_vol(nifty, 22)
    nifty_sig["vol_percentile"] = round(
        _percentile(trailing.dropna(), float(trailing.dropna().iloc[-1])), 1
    ) if trailing.notna().any() else 50.0

    analog = historical_analog(gf, nifty, geo["gpr_index"])
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
        "disclaimer": (
            "NIFTY vol signal uses market data only. GPR is shown separately. "
            "Not investment advice."
        ),
    }
