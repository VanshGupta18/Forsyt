"""Dual-signal product layer: geopolitical risk + NIFTY vol side by side."""

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
    """Caldara-scale baseline for long history; in-sample mean/std for India index ramp."""
    clean = gpr.dropna()
    if len(clean) >= CALDARA_BASELINE_MIN_DAYS:
        return BASELINE_GPR_MEAN, BASELINE_GPR_STD, "caldara"
    if len(clean) >= IN_SAMPLE_BASELINE_MIN_DAYS:
        std = float(clean.std())
        return float(clean.mean()), max(std, 1.0), "in_sample"
    return BASELINE_GPR_MEAN, BASELINE_GPR_STD, "caldara"


def geo_regime(gf: pd.DataFrame) -> dict[str, Any]:
    """Build the geopolitical half of the dual signal."""
    data.validate_gpr_frame(gf)
    gpr = gf["gpr"].astype(float)
    as_of = gpr.index[-1]
    gpr_today = float(gpr.iloc[-1])
    gpr_7ma = float(gpr.tail(min(7, len(gpr))).mean())
    gpr_30ma = float(gpr.tail(min(30, len(gpr))).mean())
    baseline_mean, baseline_std, baseline_mode = _gpr_baseline(gpr)
    z = (gpr_today - baseline_mean) / baseline_std
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
        "index_days": int(len(gpr)),
        "change_7d_pct": change_7d_pct,
        "geo_percentile": round(_percentile(gpr, gpr_today, window=len(gpr)), 1),
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
    """Market-only NIFTY volatility signal (GPR is shown separately)."""
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
    """What NIFTY did on past days with similar GPR levels (native index days only)."""
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
