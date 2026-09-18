"""India-native oil geopolitical-risk index (gpr_oil), Caldara-style.

Caldara & Iacoviello's GPR_OIL is the GPR text-frequency index computed on the
*oil-related subset* of news (not a formula). We replicate that idea on Indian
news using the corridor pipeline's already-normalized per-route threat: gpr_oil
is the **crude-import-weighted average geopolitical threat across India's
oil-supply chokepoints** (Strait of Hormuz, Red Sea/Suez, Cape of Good Hope,
Danish Straits/Baltic).

Built entirely from `gpr_corridor_daily.csv` — **no raw-news / corpus scan.**
That file already carries, per corridor per day, a `threat_index` (0-100,
~100 = baseline, split-era normalized exactly like the main GPR index) and an
`energy_exposure` (fraction of India's crude imports routed through that
corridor, e.g. Hormuz 0.336). So:

    gpr_oil_t = Σ_c energy_risk_{c,t} / Σ_c energy_exposure_c
              = Σ_c (threat_index_{c,t} · exposure_c) / Σ_c exposure_c

i.e. the exposure-weighted mean threat, on the same ~100 baseline as the main
index. `energy_risk` in the CSV is already `threat_index · energy_exposure`.

Validated (not backtested — India history is short) by co-movement with the
Caldara `GPR_OIL` benchmark and with Brent oil returns.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .paths import OUTPUT_DIR

CORRIDOR_CSV = OUTPUT_DIR / "gpr_corridor_daily.csv"
OIL_CSV = OUTPUT_DIR / "gpr_oil_daily.csv"
VALIDATION_CSV = OUTPUT_DIR / "validation" / "oil_index_validation.csv"
# repo_root/nifty-50/data — OUTPUT_DIR is gpr_index/outputs, so parents[2] = repo root
_REPO_ROOT = OUTPUT_DIR.parents[1]
CALDARA_CSV = _REPO_ROOT / "nifty-50" / "data" / "ai_gpr_data_daily.csv"
BRENT_CSV = _REPO_ROOT / "nifty-50" / "data" / "BRENT.csv"

_OIL_COLUMNS = ["date", "gpr_oil_index", "gpr_oil_7ma", "gpr_oil_30ma", "n_corridors"]


def build_oil_index(
    df: pd.DataFrame | None = None,
    corridor_csv: Path = CORRIDOR_CSV,
) -> pd.DataFrame:
    """Exposure-weighted oil-chokepoint threat -> daily gpr_oil index."""
    if df is None:
        df = pd.read_csv(corridor_csv, parse_dates=["date"])
    else:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

    energy = df[(df["energy_exposure"].fillna(0) > 0) & (df["score_status"] == "ok")].copy()
    if energy.empty:
        return pd.DataFrame(columns=_OIL_COLUMNS)

    energy["_num"] = energy["threat_index"].astype(float) * energy["energy_exposure"].astype(float)
    g = (
        energy.groupby("date")
        .agg(_num=("_num", "sum"), _den=("energy_exposure", "sum"), n_corridors=("corridor", "nunique"))
        .reset_index()
        .sort_values("date")
    )
    g["gpr_oil_index"] = (g["_num"] / g["_den"]).where(g["_den"] > 0, 0.0)
    g["gpr_oil_7ma"] = g["gpr_oil_index"].rolling(7, min_periods=1).mean()
    g["gpr_oil_30ma"] = g["gpr_oil_index"].rolling(30, min_periods=1).mean()
    g["n_corridors"] = g["n_corridors"].astype(int)
    return g[_OIL_COLUMNS].reset_index(drop=True)


def _second_col_price(path: Path) -> pd.DataFrame:
    """Read a Date,<price> CSV (NIFTY.csv shape) positionally -> date, price."""
    raw = pd.read_csv(path)
    out = pd.DataFrame({
        "date": pd.to_datetime(raw.iloc[:, 0], errors="coerce"),
        "price": pd.to_numeric(raw.iloc[:, 1], errors="coerce"),
    }).dropna()
    return out.sort_values("date")


def validate_oil_index(oil: pd.DataFrame) -> pd.DataFrame:
    """Co-movement of gpr_oil with the Caldara GPR_OIL benchmark and Brent."""
    rows: list[dict] = []

    if CALDARA_CSV.exists():
        cal = pd.read_csv(CALDARA_CSV, usecols=["Date", "GPR_OIL"])
        cal = cal.rename(columns={"Date": "date", "GPR_OIL": "caldara_gpr_oil"})
        cal["date"] = pd.to_datetime(cal["date"], errors="coerce")
        m = oil.merge(cal, on="date", how="inner").dropna(subset=["gpr_oil_index", "caldara_gpr_oil"])
        if len(m) >= 5:
            rows.append({
                "benchmark": "caldara_gpr_oil",
                "n": len(m),
                "pearson": round(m["gpr_oil_index"].corr(m["caldara_gpr_oil"]), 4),
                "pearson_7ma": round(m["gpr_oil_7ma"].corr(m["caldara_gpr_oil"]), 4),
            })

    if BRENT_CSV.exists():
        b = _second_col_price(BRENT_CSV)
        b["brent_ret"] = b["price"].pct_change() * 100
        m = oil.merge(b[["date", "brent_ret"]], on="date", how="inner").dropna(subset=["gpr_oil_index", "brent_ret"])
        if len(m) >= 5:
            rows.append({
                "benchmark": "brent_ret_same_day",
                "n": len(m),
                "pearson": round(m["gpr_oil_index"].corr(m["brent_ret"]), 4),
                "pearson_7ma": round(m["gpr_oil_7ma"].corr(m["brent_ret"]), 4),
            })
            # oil-risk leading next-day Brent move
            mn = m.copy()
            mn["brent_ret_next"] = mn["brent_ret"].shift(-1)
            mn = mn.dropna(subset=["brent_ret_next"])
            if len(mn) >= 5:
                rows.append({
                    "benchmark": "brent_ret_next_day",
                    "n": len(mn),
                    "pearson": round(mn["gpr_oil_index"].corr(mn["brent_ret_next"]), 4),
                    "pearson_7ma": round(mn["gpr_oil_7ma"].corr(mn["brent_ret_next"]), 4),
                })
    return pd.DataFrame(rows)


def run(corridor_csv: Path = CORRIDOR_CSV, out_csv: Path = OIL_CSV) -> pd.DataFrame:
    oil = build_oil_index(corridor_csv=corridor_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    oil.to_csv(out_csv, index=False)
    print(f"[OIL] wrote {len(oil):,} rows -> {out_csv}")
    val = validate_oil_index(oil)
    if not val.empty:
        VALIDATION_CSV.parent.mkdir(parents=True, exist_ok=True)
        val.to_csv(VALIDATION_CSV, index=False)
        print(f"[OIL] validation -> {VALIDATION_CSV}")
        print(val.to_string(index=False))
    else:
        print("[OIL] no overlapping benchmark data for validation (need Caldara/Brent).")
    return oil


def demo() -> None:
    """Self-check on synthetic corridor rows (no I/O)."""
    def row(date, corridor, threat, exp):
        return {"date": date, "corridor": corridor, "threat_index": threat,
                "energy_exposure": exp, "energy_risk": threat * exp, "score_status": "ok"}

    df = pd.DataFrame([
        row("2026-01-01", "strait_of_hormuz", 100.0, 0.336),
        row("2026-01-01", "red_sea_suez", 100.0, 0.271),   # both hot -> ~100
        row("2026-01-02", "strait_of_hormuz", 0.0, 0.336),
        row("2026-01-02", "red_sea_suez", 0.0, 0.271),     # calm -> 0
        row("2026-01-03", "strait_of_hormuz", 100.0, 0.336),
        row("2026-01-03", "red_sea_suez", 0.0, 0.271),     # only big-exposure route hot
    ])
    oil = build_oil_index(df).set_index("date")["gpr_oil_index"]
    hot = oil.loc["2026-01-01"]
    calm = oil.loc["2026-01-02"]
    mixed = oil.loc["2026-01-03"]
    assert abs(hot - 100.0) < 1e-9, hot
    assert calm == 0.0, calm
    assert calm < mixed < hot, (calm, mixed, hot)
    # exposure weighting: Hormuz (0.336) hot alone -> 0.336/(0.336+0.271) of 100
    assert abs(mixed - 100 * 0.336 / (0.336 + 0.271)) < 1e-9, mixed
    print("oil_index self-check OK:", {"hot": round(hot, 2), "mixed": round(mixed, 2), "calm": calm})


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corridor-csv", default=str(CORRIDOR_CSV))
    p.add_argument("--output-csv", default=str(OIL_CSV))
    p.add_argument("--self-check", action="store_true", help="run synthetic asserts and exit")
    # accepted for parity with other subcommands; index is date-driven, not range-built
    p.add_argument("--start-date", default=None)
    p.add_argument("--end-date", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_check:
        demo()
        return
    run(Path(args.corridor_csv), Path(args.output_csv))


if __name__ == "__main__":
    main()
