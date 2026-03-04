"""
Page 2 — Portfolio Risk Checker.
User enters stock tickers + weights; we call POST /portfolio/analyse and visualise results.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.api_client import analyse_portfolio

st.set_page_config(page_title="Portfolio Risk — India AI-GPR", page_icon="📊", layout="wide")

st.markdown("""
<style>
[data-testid="metric-container"] { background:#1a1d27; border:1px solid #2d3047; border-radius:10px; padding:16px; }
.risk-card { padding:12px 16px; border-radius:10px; background:#1a1d27; border:1px solid #2d3047; margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 📊 Portfolio Risk Checker")
st.markdown("Enter your Nifty stock holdings below. We'll calculate your geopolitical risk exposure by sector using our live GPR index and OLS-estimated sector betas.")
st.divider()

# ── Preset examples ────────────────────────────────────────────────────────────
PRESETS = {
    "Balanced India Portfolio": [
        ("HDFCBANK", 0.25), ("INFY", 0.20), ("RELIANCE", 0.20),
        ("SUNPHARMA", 0.15), ("TATASTEEL", 0.10), ("BHARTIARTL", 0.10),
    ],
    "IT Heavy": [
        ("TCS", 0.30), ("INFY", 0.25), ("WIPRO", 0.20), ("HCLTECH", 0.15), ("HDFCBANK", 0.10),
    ],
    "Energy Concentrated": [
        ("RELIANCE", 0.35), ("ONGC", 0.30), ("COALINDIA", 0.20), ("SBIN", 0.15),
    ],
}

col_input, col_results = st.columns([1, 1.5])

with col_input:
    st.markdown("#### 🏦 Enter Your Holdings")

    preset = st.selectbox("Quick-load a sample portfolio", ["Custom"] + list(PRESETS.keys()))

    if preset != "Custom":
        default_holdings = PRESETS[preset]
    else:
        default_holdings = [("HDFCBANK", 0.30), ("INFY", 0.25), ("RELIANCE", 0.25), ("SUNPHARMA", 0.20)]

    st.markdown("")
    holdings = []
    tickers_used = set()

    n_rows = st.number_input("Number of holdings", min_value=1, max_value=15,
                              value=len(default_holdings))

    for i in range(int(n_rows)):
        c1, c2 = st.columns([2, 1])
        default_ticker = default_holdings[i][0] if i < len(default_holdings) else ""
        default_weight = default_holdings[i][1] if i < len(default_holdings) else 0.10
        ticker = c1.text_input(f"Ticker {i+1}", value=default_ticker,
                                key=f"ticker_{i}", placeholder="e.g. INFY").upper().strip()
        weight = c2.number_input(f"Weight", min_value=0.01, max_value=1.0,
                                  value=float(default_weight), step=0.05,
                                  key=f"weight_{i}", format="%.2f")
        if ticker:
            holdings.append({"ticker": ticker, "weight": weight})

    total_w = sum(h["weight"] for h in holdings)
    if abs(total_w - 1.0) > 0.02:
        st.warning(f"⚠️ Weights sum to {total_w:.2f} — they should sum to 1.00")
    else:
        st.success(f"✅ Weights sum to {total_w:.2f}")

    run = st.button("🔍 Analyse Portfolio", type="primary", use_container_width=True)

with col_results:
    st.markdown("#### 📈 Risk Exposure Analysis")

    if run or (preset != "Custom"):
        if not holdings:
            st.info("Enter at least one holding to analyse.")
        elif abs(total_w - 1.0) > 0.02:
            st.error("Please fix weights to sum to 1.0 before analysing.")
        else:
            with st.spinner("Analysing portfolio..."):
                result = analyse_portfolio(holdings)

            score    = result.get("portfolio_gpr_score", 0)
            signal   = result.get("signal", "LOW_VOL")
            sectors  = result.get("sector_breakdown", [])
            unknown  = result.get("unrecognised_tickers", [])

            # ── Score + signal ────────────────────────────────────────────────
            m1, m2, m3 = st.columns(3)
            m1.metric("Portfolio GPR Score", f"{score:+.3f}")
            m2.metric("Risk Signal", signal.replace("_", " "))
            m3.metric("GPR Date", result.get("gpr_date", "—"))

            if unknown:
                st.warning(f"Unrecognised tickers (excluded): {', '.join(unknown)}")

            st.divider()

            if sectors:
                df = pd.DataFrame(sectors)

                # ── Donut chart: sector weight distribution ────────────────────
                col_donut, col_bar = st.columns(2)
                with col_donut:
                    st.markdown("**Sector Allocation**")
                    fig_donut = px.pie(
                        df, names="sector", values="total_weight",
                        hole=0.55,
                        color_discrete_sequence=px.colors.qualitative.Set2,
                    )
                    fig_donut.update_layout(
                        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=0, r=0, t=10, b=0), height=240,
                        legend=dict(orientation="h", y=-0.15),
                        showlegend=True,
                    )
                    st.plotly_chart(fig_donut, use_container_width=True)

                with col_bar:
                    st.markdown("**Risk Contribution by Sector**")
                    df_sorted = df.dropna(subset=["risk_contribution"]).sort_values(
                        "risk_contribution", ascending=True)
                    COLOURS = df_sorted["risk_contribution"].apply(
                        lambda x: "#ff4b4b" if x > 0.5 else ("#ffa500" if x > 0.2 else "#21c354")
                    )
                    fig_bar = go.Figure(go.Bar(
                        x=df_sorted["risk_contribution"], y=df_sorted["sector"],
                        orientation="h",
                        marker_color=COLOURS.tolist(),
                        hovertemplate="<b>%{y}</b><br>Risk contribution: %{x:.4f}<extra></extra>",
                    ))
                    fig_bar.update_layout(
                        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)", height=240,
                        margin=dict(l=0, r=0, t=10, b=0),
                        xaxis_title="Risk Contribution (weight × beta × GPR)",
                        yaxis=dict(gridcolor="#2d3047"),
                        xaxis=dict(gridcolor="#2d3047"),
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                # ── Detail table ──────────────────────────────────────────────
                st.markdown("**Full Breakdown**")
                display = df.rename(columns={
                    "sector": "Sector", "total_weight": "Weight",
                    "gpr_beta": "GPR β", "risk_contribution": "Risk Contribution",
                }).copy()
                display["Weight"] = display["Weight"].map("{:.1%}".format)
                display["GPR β"]  = display["GPR β"].map(
                    lambda x: f"{x:.3f}" if x is not None else "—")
                display["Risk Contribution"] = display["Risk Contribution"].map(
                    lambda x: f"{x:.4f}" if x is not None else "—")

                def highlight_risk(row):
                    try:
                        rc = float(row["Risk Contribution"])
                        if rc > 0.5: return ["background-color: #ff4b4b22"] * len(row)
                        if rc > 0.2: return ["background-color: #ffa50022"] * len(row)
                    except:
                        pass
                    return [""] * len(row)

                st.dataframe(
                    display.style.apply(highlight_risk, axis=1),
                    use_container_width=True, hide_index=True,
                )

                # ── Recommendation ────────────────────────────────────────────
                top_risk_sector = df.dropna(subset=["risk_contribution"]).sort_values(
                    "risk_contribution", ascending=False).iloc[0]["sector"]
                if score > 1.0:
                    st.error(
                        f"🚨 **High geopolitical risk.** Your largest exposure is **{top_risk_sector}**. "
                        f"Consider hedging or reducing this sector's weight."
                    )
                elif score > 0.3:
                    st.warning(
                        f"⚠️ **Moderate risk.** Monitor **{top_risk_sector}** sector closely."
                    )
                else:
                    st.success("✅ Portfolio has low geopolitical risk exposure.")
            else:
                st.info("No sector data returned — tickers may not be in the sector map.")
    else:
        st.info("👈 Configure your portfolio and click **Analyse Portfolio**.")
