"""
MD section A -- "higher geopolitical risk correlates with a higher probability of
severe economic downturns and LARGER DOWNSIDE RISKS".

A mean regression cannot test that claim: risk can leave the average return
untouched while fattening the left tail. So we use QUANTILE regression --
the same 'growth-at-risk' logic Adrian-Boyarchenko-Giannone apply to GDP,
applied here to forward equity returns.

    Q_tau(r_{t+1..t+h} | GPR_t) = a(tau) + b(tau) * log GPR_t

The claim predicts b(tau) < 0 and steeply negative in the LEFT tail (tau = 0.05,
0.10) while b(0.5) is near zero. That pattern -- and not the mean -- is the
signature of geopolitical risk as a disaster/tail risk.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)


def forward_return(price: pd.Series, horizon: int) -> pd.Series:
    """Log return (%) over the NEXT `horizon` trading days -- unknown at t."""
    lr = np.log(price).diff()
    return (lr.shift(-1).rolling(horizon).sum().shift(-(horizon - 1)) * 100)


def quantile_curve(gf: pd.DataFrame, price: pd.Series, horizon: int = 21,
                   quantiles=QUANTILES, controls: pd.DataFrame | None = None,
                   spec: str = "shock", ma: int = 22):
    """Fit Q_tau(forward return) on GPR at each tau.

    spec="shock" (DEFAULT, correct)  regressor = log1p(GPR) - its own `ma`-day
        mean, i.e. an innovation. Caldara & Iacoviello's negative equity effect
        comes from GPR *shocks*; a high but STABLE level of risk is already
        priced and should carry no forward return effect.

    spec="level" (DIAGNOSTIC ONLY)  regressor = log1p(GPR). Reproduces the naive
        specification and is badly confounded on post-2007 samples: the GFC and
        COVID were LOW-GPR, worst-return events, so they anchor the left tail at
        low GPR and force b(0.05) strongly POSITIVE -- an artifact, not a
        finding. On NIFTY this inflates b(0.05) from +2.4 to +6.0.

    `controls` (e.g. trailing vol) are extra regressors common across quantiles.
    """
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
    """Is GPR a TAIL risk rather than a level risk?

    Compares the left-tail slope with the median slope. A large negative gap is
    the 'disaster risk' signature the MD describes.
    """
    left = curve.loc[[q for q in curve.index if q <= 0.10], "beta_gpr"].mean()
    med = curve.loc[0.50, "beta_gpr"] if 0.50 in curve.index else np.nan
    right = curve.loc[[q for q in curve.index if q >= 0.90], "beta_gpr"].mean()
    return {"left_tail_beta": left, "median_beta": med, "right_tail_beta": right,
            "left_minus_median": left - med, "asymmetry": left - right}
