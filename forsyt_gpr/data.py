"""
Data loaders for the Forsyt GPR pipeline.

THE PLUGGABLE CONTRACT
----------------------
Every modelling module in this package consumes a *GPR frame*: a pandas
DataFrame indexed by a DatetimeIndex (daily or monthly) with these columns

    gpr          (required)  benchmark geopolitical risk index
    gpr_threats  (optional)  GPRT -- anticipated conflict  (MD section 1)
    gpr_acts     (optional)  GPRA -- realized conflict      (MD section 1)
    gpr_oil      (optional)  oil-supply-disruption sub-index

Nothing downstream cares where those numbers came from. `load_aigpr_daily()`
returns the Caldara/Iacoviello AI-GPR in this shape; when the Forsyt scraper's
India index is ready, wrap it with `as_gpr_frame()` and every model, backtest
and figure in this package works unchanged.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

DATA = "analysis/data"
REQUIRED = "gpr"


# --------------------------------------------------------------- contract
def as_gpr_frame(df: pd.DataFrame, gpr="gpr", threats=None, acts=None,
                 oil=None) -> pd.DataFrame:
    """Coerce an arbitrary frame into the canonical GPR frame.

    Point `gpr=`/`threats=`/`acts=` at whatever the source calls those columns.
    This is the single seam where the Forsyt index plugs in, e.g.

        forsyt = pd.read_sql("select day, india_gpr, threats, acts from gpr_index", con)
        gf = as_gpr_frame(forsyt.set_index("day"), gpr="india_gpr",
                          threats="threats", acts="acts")
    """
    out = pd.DataFrame(index=pd.DatetimeIndex(df.index).normalize())
    out["gpr"] = pd.to_numeric(df[gpr], errors="coerce").values
    for name, col in [("gpr_threats", threats), ("gpr_acts", acts), ("gpr_oil", oil)]:
        if col is not None:
            out[name] = pd.to_numeric(df[col], errors="coerce").values
    out = out[~out.index.duplicated(keep="last")].sort_index()
    validate_gpr_frame(out)
    return out


def validate_gpr_frame(gf: pd.DataFrame) -> None:
    """Fail loudly rather than silently modelling garbage."""
    if not isinstance(gf.index, pd.DatetimeIndex):
        raise TypeError("GPR frame must have a DatetimeIndex")
    if REQUIRED not in gf.columns:
        raise ValueError(f"GPR frame must contain a '{REQUIRED}' column; got {list(gf.columns)}")
    if not gf.index.is_monotonic_increasing:
        raise ValueError("GPR frame index must be sorted ascending")
    if gf.index.has_duplicates:
        raise ValueError("GPR frame index has duplicate dates")
    if gf["gpr"].isna().all():
        raise ValueError("'gpr' column is entirely NaN")
    if (gf["gpr"].dropna() < 0).any():
        raise ValueError("'gpr' must be non-negative")
    # NB: zeros ARE allowed. Sub-indices legitimately hit 0 on quiet days (the
    # AI-GPR oil index does so on 8124 of 24258 days), and a daily India index
    # built from a narrower news corpus will do so far more often. Everything
    # downstream uses log1p, never log, so a zero day is a floor and not -inf.


# --------------------------------------------------------------- loaders
def load_aigpr_daily() -> pd.DataFrame:
    """Caldara/Iacoviello AI-GPR, daily, in canonical form. GPRT/GPRA included."""
    df = pd.read_csv("ai_gpr_data_daily.csv", parse_dates=["Date"]).set_index("Date")
    return as_gpr_frame(df, gpr="GPR_AI", threats="THREATS_GPR_AI",
                        acts="ACTS_GPR_AI", oil="GPR_OIL")


def load_aigpr_monthly() -> pd.DataFrame:
    df = pd.read_csv("ai_gpr_data_monthly.csv", parse_dates=["Date"]).set_index("Date")
    return as_gpr_frame(df, gpr="GPR_AI", threats="THREATS_GPR_AI",
                        acts="ACTS_GPR_AI", oil="GPR_OIL")


def load_country_gpr_monthly(country="India") -> pd.DataFrame:
    """Country GPR (GPRHC) with network roles. MONTHLY ONLY -- see README note."""
    df = pd.read_csv("ai_gpr_country_monthly.csv", parse_dates=["Date"]).set_index("Date")
    cols = {f"{country}_all": "gpr"}
    for r in ["initiator", "respondent", "spillover"]:
        if f"{country}_{r}" in df.columns:
            cols[f"{country}_{r}"] = f"gpr_{r}"
    out = df[list(cols)].rename(columns=cols)
    validate_gpr_frame(out)
    return out


def load_price(name: str) -> pd.Series:
    """Cached daily close series (see analysis/data/)."""
    df = pd.read_csv(f"{DATA}/{name}.csv")
    df = df.rename(columns={df.columns[0]: "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    s = pd.Series(pd.to_numeric(df[df.columns[1]], errors="coerce").values,
                  index=df["Date"], name=name).dropna()
    return s.sort_index()


def load_fred(fid: str) -> pd.Series:
    df = pd.read_csv(f"{DATA}/{fid}.csv")
    df.columns = ["Date", fid]
    df["Date"] = pd.to_datetime(df["Date"])
    return pd.Series(pd.to_numeric(df[fid], errors="coerce").values,
                     index=df["Date"], name=fid).dropna()


# --------------------------------------------------------------- vol utils
def realized_vol(price: pd.Series, window: int) -> pd.Series:
    """Trailing annualized realized vol (%) over `window` trading days."""
    lr = np.log(price).diff()
    return lr.rolling(window).std() * np.sqrt(252) * 100


def forward_realized_vol(price: pd.Series, horizon: int) -> pd.Series:
    """FORWARD annualized realized vol (%) over the NEXT `horizon` trading days.

    Value at date t uses returns from t+1 .. t+horizon, so it is strictly
    unknown at t -- this is the prediction target (MD section 2: "next 5 days").
    """
    lr = np.log(price).diff()
    fwd = lr.shift(-1).rolling(horizon).std().shift(-(horizon - 1))
    return fwd * np.sqrt(252) * 100
