"""
MD section A -- quantile regression downside risk (research only).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)


def forward_return(price: pd.Series, horizon: int) -> pd.Series:
    lr = np.log(price).diff()
    return (lr.shift(-1).rolling(horizon).sum().shift(-(horizon - 1)) * 100)


def quantile_curve(gf: pd.DataFrame, price: pd.Series, horizon: int = 21,
                   quantiles=QUANTILES, controls: pd.DataFrame | None = None,
                   spec: str = "shock", ma: int = 22):
    if spec not in {"shock", "level"}:
        raise ValueError("spec must be 'shock' or 'level'")
    y = forward_return(price, horizon).rename("y")
    g = np.log1p(gf["gpr"].astype(float)).reindex(price.index, method="ffill")
    x = (g if spec == "level" else g - g.rolling(ma).mean()).rename("gpr_x")
    parts = [y, x]
    if controls is not None:
        parts.append(controls)
    df = pd.concat(parts, axis=1).dropna()

    extra = "" if controls is None else " + " + " + ".join(controls.columns)
    rows = []
    for tau in quantiles:
        m = smf.quantreg(f"y ~ gpr_x{extra}", df).fit(q=tau)
        rows.append({"quantile": tau, "beta_gpr": m.params["gpr_x"],
                     "se": m.bse["gpr_x"], "t": m.tvalues["gpr_x"],
                     "p": m.pvalues["gpr_x"]})
    out = pd.DataFrame(rows).set_index("quantile")
    out.attrs.update(n=len(df), horizon=horizon, spec=spec)
    return out


def tail_asymmetry(curve: pd.DataFrame) -> dict:
    left = curve.loc[[q for q in curve.index if q <= 0.10], "beta_gpr"].mean()
    med = curve.loc[0.50, "beta_gpr"] if 0.50 in curve.index else np.nan
    right = curve.loc[[q for q in curve.index if q >= 0.90], "beta_gpr"].mean()
    return {"left_tail_beta": left, "median_beta": med, "right_tail_beta": right,
            "left_minus_median": left - med, "asymmetry": left - right}
