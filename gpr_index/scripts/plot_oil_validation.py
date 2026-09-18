"""Plot the India-native gpr_oil index against the Caldara GPR_OIL benchmark.

Two panels: (1) the two series over their overlapping window with a twin axis,
(2) a scatter with an OLS fit line and the Pearson correlation annotated. This
is the validation visual — India history is short, so we show co-movement with
the established benchmark rather than a long backtest.

Run:  python gpr_index/main.py plot-oil   (or: python -m gpr_index.scripts.plot_oil_validation)
Out:  gpr_index/outputs/figures/oil_validation.png
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .oil_index import CALDARA_CSV, OIL_CSV
from .paths import OUTPUT_DIR

FIG_PATH = OUTPUT_DIR / "figures" / "oil_validation.png"
INDIA_C = "#1f77b4"
CALDARA_C = "#d62728"


def _merged() -> pd.DataFrame:
    oil = pd.read_csv(OIL_CSV, parse_dates=["date"])[["date", "gpr_oil_index", "gpr_oil_7ma"]]
    cal = pd.read_csv(CALDARA_CSV, usecols=["Date", "GPR_OIL"]).rename(
        columns={"Date": "date", "GPR_OIL": "caldara_gpr_oil"}
    )
    cal["date"] = pd.to_datetime(cal["date"], errors="coerce")
    m = oil.merge(cal, on="date", how="inner").dropna(subset=["gpr_oil_index", "caldara_gpr_oil"])
    return m.sort_values("date")


def main() -> None:
    m = _merged()
    if len(m) < 5:
        raise SystemExit("Not enough overlapping days between gpr_oil and Caldara GPR_OIL.")

    r = m["gpr_oil_index"].corr(m["caldara_gpr_oil"])
    r7 = m["gpr_oil_7ma"].corr(m["caldara_gpr_oil"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Panel 1: overlaid time series, twin axes (different native scales).
    ax1.plot(m["date"], m["gpr_oil_index"], color=INDIA_C, lw=1.4, label="India gpr_oil (native)")
    ax1.set_ylabel("India gpr_oil index", color=INDIA_C)
    ax1.tick_params(axis="y", labelcolor=INDIA_C)
    axr = ax1.twinx()
    axr.plot(m["date"], m["caldara_gpr_oil"], color=CALDARA_C, lw=1.4, alpha=0.85, label="Caldara GPR_OIL")
    axr.set_ylabel("Caldara GPR_OIL (benchmark)", color=CALDARA_C)
    axr.tick_params(axis="y", labelcolor=CALDARA_C)
    ax1.set_title(f"Co-movement over {len(m)} overlapping days")
    ax1.set_xlabel("Date")
    for lbl in ax1.get_xticklabels():
        lbl.set_rotation(30)
        lbl.set_ha("right")

    # Panel 2: scatter + OLS fit.
    x = m["gpr_oil_index"].to_numpy()
    y = m["caldara_gpr_oil"].to_numpy()
    ax2.scatter(x, y, s=14, color=INDIA_C, alpha=0.6, edgecolor="none")
    b, a = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 100)
    ax2.plot(xs, a + b * xs, color=CALDARA_C, lw=1.6, label="OLS fit")
    ax2.set_xlabel("India gpr_oil index (native)")
    ax2.set_ylabel("Caldara GPR_OIL")
    ax2.set_title(f"Pearson r = {r:.2f}  (7-day MA r = {r7:.2f})")
    ax2.legend(loc="upper left", fontsize=9)

    fig.suptitle("India-native oil GPR vs. Caldara GPR_OIL benchmark", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=140)
    print(f"[PLOT] r={r:.4f} r7ma={r7:.4f} n={len(m)} -> {FIG_PATH}")


if __name__ == "__main__":
    main()
