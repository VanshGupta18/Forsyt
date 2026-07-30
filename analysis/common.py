"""Shared helpers for the AI-GPR reproduction and India extension."""
import numpy as np
import pandas as pd

DATA = "analysis/data"


def load_price(name):
    """Load a cached daily close series, robust to yfinance's header quirks."""
    df = pd.read_csv(f"{DATA}/{name}.csv")
    # first col is the date, second is the price (header may be 'Close'/ticker)
    df = df.rename(columns={df.columns[0]: "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    price = pd.to_numeric(df[df.columns[1]], errors="coerce")
    s = pd.Series(price.values, index=df["Date"], name=name).dropna()
    return s.sort_index()


def monthly_from_daily_price(price):
    """From a daily price series build a month-indexed frame with:
       ret   = monthly log return (%)
       rvol  = realized volatility = std of daily log returns in month, annualized (%)
    """
    lr = np.log(price).diff().dropna()
    grp = lr.groupby(lr.index.to_period("M"))
    rvol = grp.std() * np.sqrt(252) * 100
    ret = grp.sum() * 100
    out = pd.DataFrame({"ret": ret, "rvol": rvol})
    out.index = out.index.to_timestamp()
    return out


def load_gpr_monthly():
    df = pd.read_csv("ai_gpr_data_monthly.csv")
    df["Date"] = pd.to_datetime(df["Date"])
    return df.set_index("Date")


def load_country_monthly():
    df = pd.read_csv("ai_gpr_country_monthly.csv")
    df["Date"] = pd.to_datetime(df["Date"])
    return df.set_index("Date")


def load_indpro():
    ip = pd.read_csv(f"{DATA}/INDPRO.csv")
    ip.columns = ["Date", "INDPRO"]
    ip["Date"] = pd.to_datetime(ip["Date"])
    ip = ip.set_index("Date")
    ip["ip_growth"] = np.log(ip["INDPRO"]).diff() * 100
    return ip
