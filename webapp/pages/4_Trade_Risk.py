"""
Page 4 — Trade Risk Map.
India's top trade partners colour-coded by current GPR + sanctions status.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.api_client import get_gpr_latest

st.set_page_config(page_title="Trade Risk — India AI-GPR", page_icon="🌍", layout="wide")

st.markdown("""
<style>
[data-testid="metric-container"] { background:#1a1d27; border:1px solid #2d3047; border-radius:10px; padding:16px; }
.country-card { padding:12px 16px; background:#1a1d27; border:1px solid #2d3047; border-radius:10px; margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 🌍 India Trade Corridor Risk Map")
st.markdown("Real-time geopolitical risk along India's key trade corridors. GPR scores are India-centric — measuring risk to Indian trade, not global risk of the partner country.")
st.divider()

# ── Trade partner database ─────────────────────────────────────────────────────
# GPR scores here are illustrative (in production, pulled from country-specific CAMEO data)
TRADE_PARTNERS = [
    {"country": "China",       "iso": "CHN", "lat": 35.9,  "lon": 104.2,
     "trade_usd_bn": 136.2, "gpr": 2.8, "sanctions": "Active",
     "primary_goods": "Electronics, Machinery", "risk_note": "LAC border tensions, tech decoupling"},
    {"country": "USA",         "iso": "USA", "lat": 37.1,  "lon": -95.7,
     "trade_usd_bn": 120.0, "gpr": 1.2, "sanctions": "None",
     "primary_goods": "Services, Pharma",       "risk_note": "Visa restrictions on IT workers"},
    {"country": "UAE",         "iso": "ARE", "lat": 23.4,  "lon": 53.8,
     "trade_usd_bn": 84.5,  "gpr": 0.8, "sanctions": "None",
     "primary_goods": "Gold, Petroleum",        "risk_note": "Low risk corridor"},
    {"country": "Russia",      "iso": "RUS", "lat": 61.5,  "lon": 105.3,
     "trade_usd_bn": 65.7,  "gpr": 3.6, "sanctions": "Active",
     "primary_goods": "Crude Oil, Defence",     "risk_note": "Western sanctions pressure on India"},
    {"country": "Saudi Arabia","iso": "SAU", "lat": 23.9,  "lon": 45.1,
     "trade_usd_bn": 52.8,  "gpr": 1.4, "sanctions": "None",
     "primary_goods": "Crude Oil",             "risk_note": "OPEC+ supply decisions"},
    {"country": "Iraq",        "iso": "IRQ", "lat": 33.2,  "lon": 43.7,
     "trade_usd_bn": 34.0,  "gpr": 2.4, "sanctions": "Partial",
     "primary_goods": "Crude Oil",             "risk_note": "Regional instability"},
    {"country": "Germany",     "iso": "DEU", "lat": 51.2,  "lon": 10.5,
     "trade_usd_bn": 30.1,  "gpr": 0.6, "sanctions": "None",
     "primary_goods": "Machinery, Chemicals",  "risk_note": "Stable corridor"},
    {"country": "South Korea", "iso": "KOR", "lat": 35.9,  "lon": 127.8,
     "trade_usd_bn": 28.3,  "gpr": 1.1, "sanctions": "None",
     "primary_goods": "Electronics",           "risk_note": "N.Korea risk overhang"},
    {"country": "Singapore",   "iso": "SGP", "lat": 1.4,   "lon": 103.8,
     "trade_usd_bn": 35.6,  "gpr": 0.4, "sanctions": "None",
     "primary_goods": "Refined Products",      "risk_note": "Financial hub — very low risk"},
    {"country": "Australia",   "iso": "AUS", "lat": -25.3, "lon": 133.8,
     "trade_usd_bn": 25.1,  "gpr": 0.5, "sanctions": "None",
     "primary_goods": "Coal, Gold",            "risk_note": "Stable; China-AU tensions have indirect effect"},
    {"country": "Japan",       "iso": "JPN", "lat": 36.2,  "lon": 138.3,
     "trade_usd_bn": 22.4,  "gpr": 0.7, "sanctions": "None",
     "primary_goods": "Electronics, Automobiles","risk_note": "Japan-China tensions minor spillover"},
    {"country": "Iran",        "iso": "IRN", "lat": 32.4,  "lon": 53.7,
     "trade_usd_bn": 8.2,   "gpr": 3.2, "sanctions": "Active",
     "primary_goods": "Crude Oil",             "risk_note": "US secondary sanctions risk for India"},
    {"country": "Bangladesh",  "iso": "BGD", "lat": 23.7,  "lon": 90.4,
     "trade_usd_bn": 14.0,  "gpr": 1.3, "sanctions": "None",
     "primary_goods": "Garments",              "risk_note": "Stable trade relationship"},
    {"country": "Pakistan",    "iso": "PAK", "lat": 30.4,  "lon": 69.3,
     "trade_usd_bn": 0.9,   "gpr": 3.8, "sanctions": "None",
     "primary_goods": "N/A (informal)",        "risk_note": "LoC tensions, near-zero formal trade"},
]

df = pd.DataFrame(TRADE_PARTNERS)

def risk_level(gpr):
    if gpr >= 2.5: return "High",   "#ff4b4b"
    if gpr >= 1.5: return "Medium", "#ffa500"
    return "Low", "#21c354"

df["risk_level"], df["colour"] = zip(*df["gpr"].map(risk_level))

# ── Summary cards ──────────────────────────────────────────────────────────────
high_risk  = df[df["risk_level"] == "High"]
sanct      = df[df["sanctions"] == "Active"]
total_high = high_risk["trade_usd_bn"].sum()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Countries tracked",      len(df))
m2.metric("🔴 High-risk corridors", len(high_risk))
m3.metric("⚠️ Sanctions active",    len(sanct))
m4.metric("Trade at elevated risk", f"${total_high:.0f}B",
          help="Annual bilateral trade with GPR ≥ 2.5 countries")

st.divider()

# ── Choropleth world map ───────────────────────────────────────────────────────
col_map, col_table = st.columns([1.8, 1])

with col_map:
    st.markdown("#### 🗺️ Trade Partner Risk Map")

    fig_map = go.Figure()

    # World base layer
    fig_map = px.choropleth(
        df, locations="iso",
        color="gpr",
        hover_name="country",
        hover_data={"gpr": ":.2f", "trade_usd_bn": ":,.1f",
                    "sanctions": True, "primary_goods": True, "risk_note": True},
        color_continuous_scale=[
            [0.0, "#21c354"], [0.35, "#4caf50"],
            [0.5, "#ffa500"], [0.7, "#ff6b35"],
            [1.0, "#ff1a1a"],
        ],
        range_color=(0, 4),
        labels={"gpr": "GPR Score", "trade_usd_bn": "Trade ($B)"},
    )

    # India highlight
    fig_map.add_trace(go.Choropleth(
        locations=["IND"],
        z=[0],
        colorscale=[[0, "#4f8ef7"], [1, "#4f8ef7"]],
        showscale=False,
        hoverinfo="skip",
        marker_line_color="#4f8ef7",
        marker_line_width=2,
    ))

    # Bubble overlay sized by trade volume
    fig_map.add_trace(go.Scattergeo(
        lat=df["lat"], lon=df["lon"],
        mode="markers",
        marker=dict(
            size=df["trade_usd_bn"] ** 0.45 * 2.5,
            color=df["gpr"],
            colorscale="RdYlGn_r",
            cmin=0, cmax=4,
            line=dict(color="white", width=0.5),
            opacity=0.85,
        ),
        text=df.apply(
            lambda r: f"<b>{r['country']}</b><br>"
                      f"Trade: ${r['trade_usd_bn']:.1f}B<br>"
                      f"GPR: {r['gpr']:.1f} ({r['risk_level']})<br>"
                      f"Sanctions: {r['sanctions']}<br>"
                      f"<i>{r['risk_note']}</i>",
            axis=1,
        ),
        hoverinfo="text",
        name="Trade volume",
    ))

    fig_map.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        geo=dict(
            bgcolor="rgba(0,0,0,0)",
            showframe=False,
            showcoastlines=True, coastlinecolor="#2d3047",
            showland=True, landcolor="#1a1d27",
            showocean=True, oceancolor="#0f1117",
            showlakes=True, lakecolor="#0f1117",
            showborders=True, bordercolor="#2d3047",
            projection_type="natural earth",
        ),
        height=480,
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_colorbar=dict(title="GPR", tickvals=[0,1,2,3,4],
                                ticktext=["0\nNone","1\nLow","2\nMed","3\nHigh","4\nCritical"]),
    )
    st.plotly_chart(fig_map, use_container_width=True)
    st.caption("Bubble size = bilateral trade volume. Colour = India-centric GPR risk score.")

# ── Country risk table ─────────────────────────────────────────────────────────
with col_table:
    st.markdown("#### 🔢 Risk Rankings")

    filter_level = st.selectbox("Filter by risk", ["All", "High", "Medium", "Low"])
    df_show = df if filter_level == "All" else df[df["risk_level"] == filter_level]
    df_show = df_show.sort_values("gpr", ascending=False)

    for _, row in df_show.iterrows():
        icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}[row["risk_level"]]
        sanct_badge = "⚠️ Sanctions" if row["sanctions"] == "Active" else ""
        st.markdown(
            f'<div class="country-card">'
            f'<div style="display:flex;justify-content:space-between;">'
            f'<span style="font-weight:700;">{icon} {row["country"]}</span>'
            f'<span style="color:#888;font-size:0.85rem;">${row["trade_usd_bn"]:.1f}B/yr</span>'
            f'</div>'
            f'<div style="color:#aaa;font-size:0.83rem;">GPR: <b>{row["gpr"]:.1f}</b> &nbsp; '
            f'{sanct_badge}</div>'
            f'<div style="color:#666;font-size:0.78rem;">{row["risk_note"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── Risk decomposition bar ─────────────────────────────────────────────────────
st.divider()
st.markdown("#### 💰 Trade-Weighted Risk Exposure")

df["trade_risk"] = df["gpr"] * df["trade_usd_bn"] / df["trade_usd_bn"].sum()
df_sorted = df.sort_values("trade_risk", ascending=True)

fig_risk = go.Figure(go.Bar(
    x=df_sorted["trade_risk"],
    y=df_sorted["country"],
    orientation="h",
    marker_color=df_sorted["gpr"].apply(
        lambda g: "#ff4b4b" if g >= 2.5 else ("#ffa500" if g >= 1.5 else "#21c354")
    ).tolist(),
    hovertemplate="<b>%{y}</b><br>Trade-weighted risk: %{x:.3f}<extra></extra>",
))
fig_risk.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    height=380, margin=dict(l=0, r=0, t=10, b=0),
    xaxis_title="Trade-weighted GPR contribution",
    xaxis=dict(gridcolor="#2d3047"), yaxis=dict(gridcolor="#2d3047"),
)
st.plotly_chart(fig_risk, use_container_width=True)
st.caption("Trade-weighted risk = (GPR score × bilateral trade) / total trade. Identifies where volume meets risk.")
