"""Plot GPR index charts from pipeline outputs.

Generates:
  gpr_daily.png   — daily index with 7MA / 30MA (imputed days shaded)
  gpr_monthly.png — monthly means (yearly view for single-year runs)

Usage:
  python -m scripts.plot_gpr --output-dir outputs
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


def _load_daily(output_dir: Path) -> pd.DataFrame:
    for name in ("gpr_daily_index_continuous.csv", "gpr_daily_index.csv"):
        path = output_dir / name
        if path.exists():
            df = pd.read_csv(path, parse_dates=["date"])
            return df.sort_values("date").reset_index(drop=True)
    raise FileNotFoundError(f"No daily GPR CSV in {output_dir}")


def _load_monthly(output_dir: Path) -> pd.DataFrame:
    for name in ("gpr_monthly_index_continuous.csv", "gpr_monthly_index.csv"):
        path = output_dir / name
        if path.exists():
            df = pd.read_csv(path)
            df["date"] = pd.to_datetime(df["year_month"].astype(str))
            return df.sort_values("date").reset_index(drop=True)
    raise FileNotFoundError(f"No monthly GPR CSV in {output_dir}")


def plot_daily(df: pd.DataFrame, out_path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(14, 5))

    if "is_imputed" in df.columns:
        imputed = df[df["is_imputed"] == True]  # noqa: E712
        if not imputed.empty:
            for block in _imputed_blocks(imputed):
                ax.axvspan(
                    block["date"].iloc[0], block["date"].iloc[-1],
                    color="#f0c040", alpha=0.25, label="_imputed",
                )

    ax.plot(df["date"], df["gpr_index"], color="#2563eb", linewidth=0.8, alpha=0.55, label="Daily GPR")
    if "gpr_7ma" in df.columns:
        ax.plot(df["date"], df["gpr_7ma"], color="#dc2626", linewidth=1.4, label="7-day MA")
    if "gpr_30ma" in df.columns:
        ax.plot(df["date"], df["gpr_30ma"], color="#059669", linewidth=1.8, label="30-day MA")

    ax.axhline(100, color="#6b7280", linewidth=0.8, linestyle="--", alpha=0.7, label="Baseline (100)")

    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("GPR Index")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", framealpha=0.9)

    if "is_imputed" in df.columns and df["is_imputed"].any():
        ax.text(
            0.01, 0.02, "Shaded = GKG gap (Caldara-imputed)",
            transform=ax.transAxes, fontsize=8, color="#92400e",
        )

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_monthly(df: pd.DataFrame, out_path: Path, title: str) -> None:
    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=(12, 5))

    x = df["date"]
    y = df["gpr_index"]
    has_imputed = "imputed_days" in df.columns
    colors = [
        "#f59e0b" if (has_imputed and r.imputed_days > 0) else "#2563eb"
        for _, r in df.iterrows()
    ]

    ax.bar(x, y, width=20, color=colors, alpha=0.85, edgecolor="white", linewidth=0.5)
    ax.plot(x, y, color="#1e40af", linewidth=1.5, marker="o", markersize=5, label="Monthly mean")
    ax.axhline(100, color="#6b7280", linewidth=0.8, linestyle="--", alpha=0.7, label="Baseline (100)")

    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("GPR Index (monthly mean)")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.grid(True, axis="y", alpha=0.3)

    handles = [
        Patch(facecolor="#2563eb", alpha=0.85, label="Observed month"),
        ax.get_lines()[0],
        ax.get_lines()[1],
    ]
    if has_imputed and (df["imputed_days"] > 0).any():
        handles.insert(1, Patch(facecolor="#f59e0b", alpha=0.85, label="Month incl. imputed days"))
    ax.legend(handles=handles, loc="upper right", framealpha=0.9)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _imputed_blocks(imputed: pd.DataFrame):
    """Yield consecutive imputed date blocks."""
    dates = imputed.sort_values("date")["date"].tolist()
    if not dates:
        return
    block = [dates[0]]
    for d in dates[1:]:
        if (d - block[-1]).days == 1:
            block.append(d)
        else:
            yield pd.DataFrame({"date": block})
            block = [d]
    yield pd.DataFrame({"date": block})


def run(
    output_dir: Path,
    plots_dir: Path | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> None:
    plots_dir = plots_dir or output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    daily = _load_daily(output_dir)
    monthly = _load_monthly(output_dir)

    if start_date:
        daily = daily[daily["date"] >= pd.to_datetime(start_date)]
        monthly = monthly[monthly["date"] >= pd.to_datetime(start_date)]
    if end_date:
        daily = daily[daily["date"] <= pd.to_datetime(end_date)]
        monthly = monthly[monthly["date"] <= pd.to_datetime(end_date)]

    year_label = ""
    if not daily.empty:
        y0, y1 = daily["date"].dt.year.min(), daily["date"].dt.year.max()
        year_label = str(y0) if y0 == y1 else f"{y0}–{y1}"

    daily_path  = plots_dir / "gpr_daily.png"
    monthly_path = plots_dir / "gpr_monthly.png"

    plot_daily(daily, daily_path, f"Daily GPR Index — {year_label}")
    plot_monthly(monthly, monthly_path, f"Monthly GPR Index — {year_label}")

    print(f"[PLOT] Daily chart   → {daily_path}")
    print(f"[PLOT] Monthly chart → {monthly_path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Plot GPR daily and monthly charts")
    p.add_argument("--output-dir", default="outputs")
    p.add_argument("--plots-dir",  default=None, help="Default: outputs/plots")
    p.add_argument("--start-date", default=None)
    p.add_argument("--end-date",   default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(
        output_dir=Path(args.output_dir),
        plots_dir=Path(args.plots_dir) if args.plots_dir else None,
        start_date=args.start_date,
        end_date=args.end_date,
    )


if __name__ == "__main__":
    main()
