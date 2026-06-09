#!/usr/bin/env python3
"""
Compare MA7 of corrected GPR with Caldara MA7.
Plot both and calculate correlation.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
from pathlib import Path

# Paths
DATA_DIR = Path("data")
CORRECTED_GPR = DATA_DIR / "daily_global_gpr_final.csv"
CALDARA_GPR = DATA_DIR / "daily_global_gpr.csv"
OUTPUT_DIR = DATA_DIR / "plots"
OUTPUT_DIR.mkdir(exist_ok=True)

print("[MA7] Loading corrected GPR...")
df_corrected = pd.read_csv(CORRECTED_GPR, parse_dates=["SQLDATE"])
df_corrected = df_corrected.sort_values("SQLDATE").reset_index(drop=True)

print("[MA7] Loading Caldara GPR...")
df_caldara = pd.read_csv(CALDARA_GPR, parse_dates=["SQLDATE"])
df_caldara = df_caldara.sort_values("SQLDATE").reset_index(drop=True)

# Compute MA7 for both
df_corrected["GPR_MA7"] = df_corrected["GPR_t"].rolling(window=7, center=False, min_periods=1).mean()
df_caldara["GPR_MA7"] = df_caldara["GPR_t"].rolling(window=7, center=False, min_periods=1).mean()

print(f"\n[MA7] Corrected GPR: {len(df_corrected)} rows from {df_corrected['SQLDATE'].min()} to {df_corrected['SQLDATE'].max()}")
print(f"[MA7] Caldara GPR: {len(df_caldara)} rows from {df_caldara['SQLDATE'].min()} to {df_caldara['SQLDATE'].max()}")

# Merge on date for comparison
df_merged = df_corrected[["SQLDATE", "GPR_MA7"]].merge(
    df_caldara[["SQLDATE", "GPR_MA7"]].rename(columns={"GPR_MA7": "Caldara_MA7"}),
    on="SQLDATE",
    how="inner"
)

print(f"\n[MA7] Merged overlap: {len(df_merged)} days")

# Remove NaN pairs
df_clean = df_merged[["GPR_MA7", "Caldara_MA7"]].dropna()
print(f"[MA7] Valid pairs (non-NaN): {len(df_clean)}")

# Calculate correlation
if len(df_clean) > 2:
    corr, pval = pearsonr(df_clean["GPR_MA7"], df_clean["Caldara_MA7"])
    print(f"\n[MA7] === CORRELATION ===")
    print(f"[MA7] Pearson r: {corr:.6f}")
    print(f"[MA7] P-value: {pval:.6e}")
    print(f"[MA7] Significant: {'Yes' if pval < 0.05 else 'No'}")
else:
    print("\n[MA7] ERROR: Not enough valid pairs for correlation")
    corr = None

# Plot MA7 comparison
print("\n[MA7] Generating MA7 comparison plot...")
fig, ax = plt.subplots(figsize=(18, 7))

ax.plot(df_merged["SQLDATE"], df_merged["GPR_MA7"], 
        label="Corrected GPR (MA7)", linewidth=2.5, color="blue", alpha=0.8)
ax.plot(df_merged["SQLDATE"], df_merged["Caldara_MA7"], 
        label="Caldara GPR (MA7)", linewidth=2.5, color="green", alpha=0.8)

ax.set_xlabel("Date", fontsize=13, fontweight="bold")
ax.set_ylabel("GPR Index (MA7)", fontsize=13, fontweight="bold")
title = f"MA7 Comparison: Corrected DistilBERT vs Caldara Benchmark"
if corr is not None:
    title += f"\nPearson r = {corr:.6f} (p-value = {pval:.2e})"
ax.set_title(title, fontsize=14, fontweight="bold")
ax.legend(fontsize=12, loc="best")
ax.grid(True, alpha=0.3)
plt.xticks(rotation=45, fontsize=10)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "ma7_comparison.png", dpi=200, bbox_inches="tight")
print(f"[MA7] Saved: {OUTPUT_DIR / 'ma7_comparison.png'}")
plt.close()

# Plot scatter to show correlation visually
print("\n[MA7] Generating scatter plot...")
fig, ax = plt.subplots(figsize=(10, 10))
ax.scatter(df_clean["Caldara_MA7"], df_clean["GPR_MA7"], 
          alpha=0.6, s=50, color="purple", edgecolors="black", linewidth=0.5)

# Add trend line
if len(df_clean) > 1:
    z = np.polyfit(df_clean["Caldara_MA7"], df_clean["GPR_MA7"], 1)
    p = np.poly1d(z)
    x_line = np.linspace(df_clean["Caldara_MA7"].min(), df_clean["Caldara_MA7"].max(), 100)
    ax.plot(x_line, p(x_line), "r--", linewidth=2, label=f"Trend: y={z[0]:.4f}x+{z[1]:.4f}")

ax.set_xlabel("Caldara MA7", fontsize=13, fontweight="bold")
ax.set_ylabel("Corrected GPR MA7", fontsize=13, fontweight="bold")
title = f"MA7 Scatter Plot"
if corr is not None:
    title += f"\nr = {corr:.6f}"
ax.set_title(title, fontsize=14, fontweight="bold")
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "ma7_scatter.png", dpi=200, bbox_inches="tight")
print(f"[MA7] Saved: {OUTPUT_DIR / 'ma7_scatter.png'}")
plt.close()

# Statistics
print("\n[MA7] === STATISTICS ===")
print(f"[MA7] Corrected MA7 - Mean: {df_merged['GPR_MA7'].mean():.6f}, Std: {df_merged['GPR_MA7'].std():.6f}")
print(f"[MA7] Caldara MA7   - Mean: {df_merged['Caldara_MA7'].mean():.6f}, Std: {df_merged['Caldara_MA7'].std():.6f}")

print("\n[MA7] Done!")
