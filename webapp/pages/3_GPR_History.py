"""
Page 3 — GPR History Explorer.
Interactive chart with zoom, annotations for known events, and CSV download.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.api_client import get_gpr_history

st.set_page_config(page_title="GPR History — India AI-GPR", page_icon="📈", layout="wide")

st.markdown("""
<style>
[data-testid="metric-container"] { background:#1a1d27; border:1px solid #2d3047; border-radius:10px; padding:16px; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 📈 India AI-GPR History Explorer")
st.markdown("Explore how India's geopolitical risk index evolved over time. Hover over spikes to see annotations.")
st.divider()

# ── Controls ───────────────────────────────────────────────────────────────────
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 2])

with col_ctrl1:
    period = st.selectbox("Time period", [
        "Last 30 days", "Last 90 days", "Last 1 year",
        "Last 3 years", "Last 5 years", "All history",
    ], index=2)

PERIOD_MAP = {
    "Last 30 days":  30,   "Last 90 days":  90,
    "Last 1 year":   365,  "Last 3 years":  3*365,
    "Last 5 years":  5*365, "All history":  99*365,
}
days = PERIOD_MAP[period]

with col_ctrl2:
    show_events = st.toggle("Show event annotations", value=True)

with col_ctrl3:
    show_nifty = st.toggle("Overlay Nifty volatility proxy", value=False)

# ── Known historical events ────────────────────────────────────────────────────
KNOWN_EVENTS = [
    {"date": "2008-11-26", "label": "26/11 Mumbai attacks",      "gpr": 3.8,  "color": "#ff4b4b"},
    {"date": "2016-09-18", "label": "Uri attack — surgical strike","gpr": 2.9, "color": "#ff4b4b"},
    {"date": "2019-02-14", "label": "Pulwama attack",             "gpr": 3.1,  "color": "#ff4b4b"},
    {"date": "2019-02-26", "label": "Balakot airstrike",          "gpr": 2.8,  "color": "#ff9500"},
    {"date": "2020-06-15", "label": "Galwan Valley clash",        "gpr": 3.4,  "color": "#ff4b4b"},
    {"date": "2022-02-24", "label": "Russia-Ukraine war begins",   "gpr": 2.1, "color": "#ffa500"},
    {"date": "2023-05-09", "label": "India-Pakistan ceasefire talks","gpr": 1.8,"color": "#4f8ef7"},
]

# ── Fetch data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading GPR history..."):
    history = get_gpr_history(days=min(days, 99*365))

if not history:
    st.error("No history data available.")
    st.stop()

df = pd.DataFrame(history)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

# ── Summary metrics ────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Data points",    f"{len(df):,}")
m2.metric("Period mean GPR", f"{df['normalized_gpr'].mean():+.3f}")
m3.metric("Period max GPR",  f"{df['normalized_gpr'].max():+.3f}")
m4.metric("Days above Z>2",  str((df["normalized_gpr"] > 2.0).sum()))

st.divider()

# ── Main chart ─────────────────────────────────────────────────────────────────
fig = go.Figure()

# Risk zone shading
fig.add_hrect(y0=2.0, y1=6.0,  fillcolor="red",    opacity=0.06, line_width=0,
              annotation_text="Critical", annotation_position="top left",
              annotation_font_color="#ff4b4b", annotation_font_size=10)
fig.add_hrect(y0=1.0, y1=2.0,  fillcolor="orange", opacity=0.06, line_width=0,
              annotation_text="Elevated", annotation_position="top left",
              annotation_font_color="#ffa500", annotation_font_size=10)
fig.add_hrect(y0=0.0, y1=1.0,  fillcolor="yellow", opacity=0.02, line_width=0)
fig.add_hrect(y0=-6.0, y1=0.0, fillcolor="green",  opacity=0.04, line_width=0,
              annotation_text="Below average", annotation_position="bottom left",
              annotation_font_color="#21c354", annotation_font_size=10)

# Zero line
fig.add_hline(y=0, line_dash="dot", line_color="#44444488", line_width=1)

# GPR line with fill
fig.add_trace(go.Scatter(
    x=df["date"], y=df["normalized_gpr"],
    mode="lines",
    name="India AI-GPR Index",
    line=dict(color="#4f8ef7", width=2),
    fill="tozeroy",
    fillcolor="rgba(79,142,247,0.08)",
    hovertemplate="<b>%{x|%b %d, %Y}</b><br>GPR: %{y:.3f}<extra></extra>",
))

# Event annotations
if show_events:
    for ev in KNOWN_EVENTS:
        ev_dt = pd.Timestamp(ev["date"])
        if df["date"].min() <= ev_dt <= df["date"].max():
            fig.add_vline(
                x=ev_dt, line_dash="dash",
                line_color=ev["color"], line_width=1.5, opacity=0.6,
            )
            fig.add_annotation(
                x=ev_dt, y=ev["gpr"],
                text=ev["label"],
                showarrow=True, arrowhead=2, arrowcolor=ev["color"],
                font=dict(color=ev["color"], size=10),
                bgcolor="#0f1117", bordercolor=ev["color"], borderwidth=1,
                ax=40, ay=-40,
            )

fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    height=480,
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis_title="Normalised GPR (Z-score)",
    xaxis=dict(gridcolor="#2d3047", rangeslider=dict(visible=True)),
    yaxis=dict(gridcolor="#2d3047"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    hovermode="x unified",
)

st.plotly_chart(fig, use_container_width=True)

# ── Event timeline table ───────────────────────────────────────────────────────
if show_events:
    st.divider()
    st.markdown("#### 📌 Major Event Annotations")
    ev_df = pd.DataFrame(KNOWN_EVENTS)[["date", "label", "gpr"]].rename(columns={
        "date": "Date", "label": "Event", "gpr": "Est. GPR at Peak"
    })
    ev_df["Date"] = pd.to_datetime(ev_df["Date"]).dt.strftime("%d %b %Y")
    st.dataframe(ev_df, use_container_width=True, hide_index=True)

# ── Stats ──────────────────────────────────────────────────────────────────────
st.divider()
st.markdown("#### 📊 Distribution Statistics")

col_a, col_b = st.columns(2)

with col_a:
    import plotly.express as px
    fig_hist = px.histogram(
        df, x="normalized_gpr", nbins=60,
        title="GPR Score Distribution",
        color_discrete_sequence=["#4f8ef7"],
    )
    fig_hist.add_vline(x=1.0, line_dash="dash", line_color="#ffa500",
                       annotation_text="Elevated threshold")
    fig_hist.add_vline(x=2.0, line_dash="dash", line_color="#ff4b4b",
                       annotation_text="Critical threshold")
    fig_hist.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", height=280,
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig_hist, use_container_width=True)

with col_b:
    st.markdown("**Summary Statistics**")
    stats = df["normalized_gpr"].describe().rename({
        "count": "N", "mean": "Mean", "std": "Std Dev",
        "min": "Min", "25%": "25th Pct", "50%": "Median",
        "75%": "75th Pct", "max": "Max"
    })
    st.dataframe(stats.map(lambda x: f"{x:.4f}"), use_container_width=True)

# ── Download ───────────────────────────────────────────────────────────────────
st.divider()
csv = df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download as CSV", data=csv,
    file_name=f"india_ai_gpr_{date.today().isoformat()}.csv",
    mime="text/csv",
)
