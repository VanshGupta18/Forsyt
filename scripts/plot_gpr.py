"""
Caldara-style GPR Index Plot
Reads daily_gpr_final.csv and generates a publication-quality chart.
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# ── Load data ─────────────────────────────────────────────────────────────────
daily = pd.read_csv("data/daily_gpr_final.csv", parse_dates=["SQLDATE"])
daily = daily.sort_values("SQLDATE").reset_index(drop=True)

# Normalize GPR_t to mean=100 scale (Caldara convention)
mean_gpr = daily["GPR_t"].mean()
daily["GPR_index"] = (daily["GPR_t"] / mean_gpr) * 100

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 6))

# Main line
ax.plot(daily["SQLDATE"], daily["GPR_index"], color="#1a73e8", linewidth=1.8,
        label="GPR Index (smoothed)", zorder=3)

# Fill under the curve
ax.fill_between(daily["SQLDATE"], daily["GPR_index"], alpha=0.15, color="#1a73e8")

# Raw (unsmoothed) as faint background
if "GPR_t_raw" in daily.columns:
    raw_index = (daily["GPR_t_raw"] / mean_gpr) * 100
    ax.plot(daily["SQLDATE"], raw_index, color="#aaa", linewidth=0.5,
            alpha=0.5, label="GPR (raw)", zorder=2)

# Mean line
ax.axhline(y=100, color="#e8453c", linestyle="--", linewidth=1, alpha=0.7,
           label="Mean = 100")

# Styling
ax.set_title("Geopolitical Risk Index (GDELT-based, Caldara-style)",
             fontsize=16, fontweight="bold", pad=15)
ax.set_xlabel("Date", fontsize=12)
ax.set_ylabel("GPR Index (mean = 100)", fontsize=12)
ax.legend(loc="upper left", fontsize=10, framealpha=0.9)
ax.grid(True, alpha=0.3, linestyle="-")
ax.set_xlim(daily["SQLDATE"].min(), daily["SQLDATE"].max())

# Date formatting
ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
plt.xticks(rotation=45, ha="right")

# Clean up
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()

# Save
plt.savefig("data/gpr_index_plot.png", dpi=150, bbox_inches="tight")
print(f"[PLOT] Saved to data/gpr_index_plot.png")
print(f"[STATS] Date range: {daily['SQLDATE'].min()} → {daily['SQLDATE'].max()}")
print(f"[STATS] Days: {len(daily)}")
print(f"[STATS] GPR mean: {daily['GPR_index'].mean():.2f}, min: {daily['GPR_index'].min():.2f}, max: {daily['GPR_index'].max():.2f}")
print(f"[STATS] Zero days: {(daily['GPR_t'] == 0).sum()}")
plt.show()
