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

BEGINNER NOTE -- why "pluggable" matters here
----------------------------------------------
This file deliberately does NOT `import` anything from `gpr_index/` (the
package that actually builds Forsyt's own India risk index from news
articles). That is on purpose, not an oversight:

  * `gpr_index` and `forsyt_gpr` can be developed, tested, and even reused by
    someone else's project independently -- neither one needs to know the
    other exists.
  * Right now this package is developed and tested against the public
    Caldara/Iacoviello "AI-GPR" benchmark (a well-known, already-published
    geopolitical risk index -- see `load_aigpr_daily()` below), simply
    because it has decades of history and is easy to trust. The real India
    index is much newer and shorter.
  * The moment the India index has enough daily history, someone flips the
    input by calling `as_gpr_frame()` on THAT data instead (see the worked
    example in `forsyt_gpr/README.md`). Every model, feature, and chart in
    this package keeps working unchanged, because they all only ever look at
    the four standardised column names above -- never at where the numbers
    came from. This is the actual "hand-off" described in
    `nifty-50/docs/INTEGRATION.md`.

If you are new to pandas: a `DatetimeIndex` just means "the row labels are
dates instead of row numbers 0, 1, 2, ...", which lets us use calendar-aware
operations like `.rolling()` (a moving window over the last N days) later on.
"""
from __future__ import annotations
import functools
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
REQUIRED = "gpr"


# --------------------------------------------------------------- contract
def as_gpr_frame(df: pd.DataFrame, gpr="gpr", threats=None, acts=None,
                 oil=None) -> pd.DataFrame:
    """Coerce an arbitrary frame into the canonical GPR frame.

    "Coerce" here just means: take whatever column names the source data
    happens to use (e.g. a database might call the risk column `gpr_index`,
    a CSV might call it `GPR_AI`) and copy them into a new DataFrame that
    always uses OUR names (`gpr`, `gpr_threats`, `gpr_acts`, `gpr_oil`).
    Every other function in this package only ever looks for those four
    names, so this is the one place a new data source has to be translated.

    Point `gpr=`/`threats=`/`acts=` at whatever the source calls those columns.
    This is the single seam where the Forsyt index plugs in, e.g.

        forsyt = pd.read_sql("select day, india_gpr, threats, acts from gpr_index", con)
        gf = as_gpr_frame(forsyt.set_index("day"), gpr="india_gpr",
                          threats="threats", acts="acts")
    """
    # Build a brand-new, empty frame whose index is the same dates as the
    # input but guaranteed to be a proper DatetimeIndex, and "normalized"
    # (time-of-day stripped, e.g. 2026-01-01 09:30 -> 2026-01-01). That way
    # two sources that timestamp things slightly differently still line up.
    out = pd.DataFrame(index=pd.DatetimeIndex(df.index).normalize())
    # `pd.to_numeric(..., errors="coerce")` means "convert to numbers, and
    # turn anything that isn't a valid number (blank cells, stray text) into
    # NaN (Not-a-Number) instead of crashing." NaN is pandas's way of saying
    # "missing" -- most numeric operations just skip over it.
    out["gpr"] = pd.to_numeric(df[gpr], errors="coerce").values
    for name, col in [("gpr_threats", threats), ("gpr_acts", acts), ("gpr_oil", oil)]:
        if col is not None:
            out[name] = pd.to_numeric(df[col], errors="coerce").values
    # If the source already computed 7-day/30-day moving averages, carry them
    # over too (used by dual_signal.py so it doesn't have to recompute them).
    for extra in ("gpr_7ma", "gpr_30ma"):
        if extra in df.columns:
            out[extra] = pd.to_numeric(df[extra], errors="coerce").values
    # Real-world feeds sometimes contain the same date twice (e.g. a
    # late-arriving correction). Keep only the LAST value for a repeated date,
    # then make sure dates run oldest-to-newest -- both are required by
    # validate_gpr_frame() below and by every rolling-window calculation that
    # follows.
    out = out[~out.index.duplicated(keep="last")].sort_index()
    validate_gpr_frame(out)
    return out


def validate_gpr_frame(gf: pd.DataFrame) -> None:
    """Fail loudly rather than silently modelling garbage.

    Plain-language version of each check below: if any of these are wrong,
    every downstream chart and model would still "run" -- it just wouldn't
    mean anything. Raising an exception here turns a silent, hard-to-notice
    data bug into an obvious crash at the moment the bad data is loaded,
    which is far easier to debug than a weird-looking result three steps
    later.
    """
    if not isinstance(gf.index, pd.DatetimeIndex):
        raise TypeError("GPR frame must have a DatetimeIndex")
    if REQUIRED not in gf.columns:
        raise ValueError(f"GPR frame must contain a '{REQUIRED}' column; got {list(gf.columns)}")
    # "Monotonic increasing" = each date is later than the one before it.
    # Rolling averages and "forward" (future) calculations assume this.
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
    #
    # Why this matters (plain language): log(0) is undefined ("negative
    # infinity"), and just one such value can silently wreck an entire
    # calculation -- pandas will drop every row touched by it. `log1p(x)`
    # computes `log(1 + x)` instead of `log(x)`, so a zero input safely maps
    # to `log(1) = 0` rather than blowing up. This one substitution is the
    # difference between a feature column with thousands of usable rows and
    # one that silently collapses to almost nothing (see features.py).


# --------------------------------------------------------------- loaders
# These four functions read the raw CSVs in `data/` and hand back either a
# canonical GPR frame (via as_gpr_frame) or a plain price/macro series. They
# are intentionally "dumb": all the validation logic lives in
# validate_gpr_frame(), not repeated here.

def load_aigpr_daily() -> pd.DataFrame:
    """Caldara/Iacoviello AI-GPR, daily, in canonical form. GPRT/GPRA included.

    This is a well-known, publicly published geopolitical risk index (see
    the References in the top-level report / forsyt_gpr/README.md). We use
    it as our development/benchmark data source -- it has decades of daily
    history, which the India-specific index does not have yet.
    """
    df = pd.read_csv(DATA / "ai_gpr_data_daily.csv", parse_dates=["Date"]).set_index("Date")
    return as_gpr_frame(df, gpr="GPR_AI", threats="THREATS_GPR_AI",
                        acts="ACTS_GPR_AI", oil="GPR_OIL")


def load_aigpr_monthly() -> pd.DataFrame:
    """Same benchmark index as above, but the monthly-resolution release."""
    df = pd.read_csv(DATA / "ai_gpr_data_monthly.csv", parse_dates=["Date"]).set_index("Date")
    return as_gpr_frame(df, gpr="GPR_AI", threats="THREATS_GPR_AI",
                        acts="ACTS_GPR_AI", oil="GPR_OIL")


def load_country_gpr_monthly(country="India") -> pd.DataFrame:
    """Country GPR (GPRHC) with network roles. MONTHLY ONLY -- see README note.

    "Network roles" here means the same risk score is broken down by how the
    country was involved in the underlying news: `_all` (any mention),
    `_initiator` (the country's own actions), `_respondent` (risk aimed AT
    the country), `_spillover` (risk from a conflict elsewhere that touches
    the country indirectly, e.g. an oil-price shock). Only `_all` is required
    to exist; the others are picked up automatically if present for the
    requested country.
    """
    df = pd.read_csv(DATA / "ai_gpr_country_monthly.csv", parse_dates=["Date"]).set_index("Date")
    cols = {f"{country}_all": "gpr"}
    for r in ["initiator", "respondent", "spillover"]:
        if f"{country}_{r}" in df.columns:
            cols[f"{country}_{r}"] = f"gpr_{r}"
    out = df[list(cols)].rename(columns=cols)
    validate_gpr_frame(out)
    return out


@functools.lru_cache(maxsize=8)
def load_price(name: str) -> pd.Series:
    """Cached daily close series (see data/).

    `@functools.lru_cache` (a standard-library decorator, no custom caching
    code needed) means: the first time `load_price("NIFTY")` is called, it
    reads and parses the CSV from disk; every call after that with the same
    `name` instantly returns the same result from memory instead of hitting
    the disk again. `maxsize=8` just caps how many different names it will
    remember at once (plenty, since this package only ever loads a handful
    of price series such as "NIFTY" and "SP500").

    This function assumes the CSV's first column is the date and its second
    column is the price, regardless of what they are literally named --
    that is why it renames them positionally (`df.columns[0]`, `df.columns[1]`)
    instead of hardcoding "Date"/"Close".
    """
    df = pd.read_csv(DATA / f"{name}.csv")
    df = df.rename(columns={df.columns[0]: "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    s = pd.Series(pd.to_numeric(df[df.columns[1]], errors="coerce").values,
                  index=df["Date"], name=name).dropna()
    return s.sort_index()


def load_fred(fid: str) -> pd.Series:
    """Load a macroeconomic series from FRED (the St. Louis Fed's public
    economic-data database, e.g. `NEWORDER` = new manufacturing orders,
    `PAYEMS` = US nonfarm payrolls). These are optional macro context used
    only by research, not by the live product.
    """
    df = pd.read_csv(DATA / f"{fid}.csv")
    df.columns = ["Date", fid]
    df["Date"] = pd.to_datetime(df["Date"])
    return pd.Series(pd.to_numeric(df[fid], errors="coerce").values,
                     index=df["Date"], name=fid).dropna()


# --------------------------------------------------------------- vol utils
# "Volatility" here just means: how much did the price wobble around,
# regardless of direction? A calm market has low volatility even if it's
# slowly trending up; a market that whipsaws up and down sharply has high
# volatility even if it ends up flat. It's usually reported as an annualised
# percentage so that different time windows are comparable.

def realized_vol(price: pd.Series, window: int) -> pd.Series:
    """Trailing annualized realized vol (%) over `window` trading days.

    "Trailing" / "realized" means this looks BACKWARD: for each date, how
    much did the price actually move over the last `window` days? It is
    always computable using only information you already had -- no
    look-ahead here, unlike forward_realized_vol() below.

    How it's computed, step by step:
      1. `np.log(price).diff()` -- the day-to-day log return. Log returns are
         used (instead of simple % change) because they add up nicely across
         multiple days, which is what the standard deviation step needs.
      2. `.rolling(window).std()` -- the standard deviation (a measure of how
         spread-out/jumpy the daily returns were) over a sliding `window`-day
         window.
      3. `* sqrt(252) * 100` -- scales a *daily* standard deviation up to an
         *annualized percentage*. 252 is the standard number of trading days
         in a year; multiplying by its square root is the textbook way vol is
         "annualized" so that a 5-day window and a 66-day window produce
         numbers on the same, comparable scale.
    """
    lr = np.log(price).diff()
    return lr.rolling(window).std() * np.sqrt(252) * 100


def forward_realized_vol(price: pd.Series, horizon: int) -> pd.Series:
    """FORWARD annualized realized vol (%) over the NEXT `horizon` trading days.

    Value at date t uses returns from t+1 .. t+horizon, so it is strictly
    unknown at t -- this is the prediction target (MD section 2: "next 5 days").

    This is the single most important function to understand if you're new
    to machine learning: it is the "answer key" (the `y` / target / label)
    that vol_model.py is trying to predict. On day t we are NOT allowed to
    know this value yet -- it only becomes knowable once days t+1..t+horizon
    have actually happened. If a model were accidentally fed this as an
    input feature instead of as the target, it would look perfect in testing
    and then be useless in production, because in production the future
    genuinely hasn't happened yet. This bug is called "look-ahead bias" or
    "leakage", and guarding against it is the whole point of the
    purged-walk-forward machinery in vol_model.py.

    Mechanically, `.shift(-1)` moves each day's return one step INTO THE
    PAST relative to its row (so row t now holds day t+1's return), then
    `.rolling(horizon)` averages/std-devs the next `horizon` such shifted
    values, then the second `.shift(-(horizon - 1))` re-aligns the result so
    it lands back on row t. The net effect: row t's value summarizes what
    happens strictly AFTER day t.
    """
    lr = np.log(price).diff()
    fwd = lr.shift(-1).rolling(horizon).std().shift(-(horizon - 1))
    return fwd * np.sqrt(252) * 100
