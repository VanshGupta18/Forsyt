"""
Page 1 — Dashboard: Live GPR score, volatility signal, today's events, 30-day trend.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.api_client import get_gpr_latest, get_signal_latest, get_events, get_gpr_history

st.set_page_config(page_title="Dashboard — India AI-GPR", page_icon="🏠", layout="wide")

# ── Custom CSS (shared) ────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="metric-container"] { background:#1a1d27; border:1px solid #2d3047; border-radius:10px; padding:16px; }
.badge-high   { background:#ff4b4b22; color:#ff4b4b; border:1px solid #ff4b4b; border-radius:6px; padding:4px 14px; font-weight:700; font-size:1.1rem; }
.badge-medium { background:#ffa50022; color:#ffa500; border:1px solid #ffa500; border-radius:6px; padding:4px 14px; font-weight:700; font-size:1.1rem; }
.badge-low    { background:#21c35422; color:#21c354; border:1px solid #21c354; border-radius:6px; padding:4px 14px; font-weight:700; font-size:1.1rem; }
.event-row { padding:10px 14px; border-left:4px solid; border-radius:0 8px 8px 0; margin-bottom:8px; background:#1a1d27; }
.event-high   { border-color:#ff4b4b; }
.event-medium { border-color:#ffa500; }
.event-low    { border-color:#21c354; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 🏠 Dashboard")
st.caption(f"Last updated: {date.today().strftime('%B %d, %Y')}")
st.divider()

# ── Fetch data ─────────────────────────────────────────────────────────────────
with st.spinner("Fetching live data..."):
    gpr_data    = get_gpr_latest()
    signal_data = get_signal_latest()
    events      = get_events(min_severity=0.25)
    history     = get_gpr_history(days=30)

# ── Top KPI row ────────────────────────────────────────────────────────────────
gpr_score = gpr_data.get("normalized_gpr", 0)
gpr_flag  = gpr_data.get("data_quality_flag", "OK")
signal    = signal_data.get("signal", "LOW_VOL")
prob      = signal_data.get("high_vol_probability", 0)

def gpr_label(score):
    if score > 2.0:   return "CRITICAL", "high"
    if score > 1.0:   return "ELEVATED", "medium"
    if score > 0.0:   return "MODERATE", "medium"
    return "LOW", "low"

label, level = gpr_label(gpr_score)
signal_level = "high" if signal == "HIGH_VOL" else "low"

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("GPR Index (Z-score)", f"{gpr_score:+.2f}", label)
with col2:
    badge_cls = f"badge-{level}"
    st.markdown(f"**Risk Level**")
    st.markdown(f'<span class="{badge_cls}">{label}</span>', unsafe_allow_html=True)
with col3:
    st.metric("Volatility Signal", signal.replace("_", " "), f"{prob*100:.0f}% probability")
with col4:
    flag_icon = "⚠️" if gpr_flag != "OK" else "✅"
    st.metric("Data Quality", f"{flag_icon} {gpr_flag}", gpr_data.get("source", "—"))

st.divider()

# ── GPR trend chart ────────────────────────────────────────────────────────────
col_chart, col_events = st.columns([2, 1])

with col_chart:
    st.markdown("#### 📈 GPR Trend — Last 30 Days")

    df = pd.DataFrame(history)
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        fig = go.Figure()

        # Shaded risk zones
        fig.add_hrect(y0=2.0, y1=5.0, fillcolor="red",   opacity=0.07, line_width=0)
        fig.add_hrect(y0=1.0, y1=2.0, fillcolor="orange", opacity=0.07, line_width=0)
        fig.add_hrect(y0=-1.0, y1=1.0, fillcolor="green", opacity=0.05, line_width=0)

        # GPR line
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["normalized_gpr"],
            mode="lines", name="GPR Index",
            line=dict(color="#4f8ef7", width=2.5),
            hovertemplate="<b>%{x|%b %d}</b><br>GPR: %{y:.3f}<extra></extra>",
        ))

        # Today marker
        fig.add_vline(x=str(date.today()), line_dash="dot", line_color="#ffffff44")

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=320,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis_title="Z-Score",
            showlegend=False,
            xaxis=dict(gridcolor="#2d3047"),
            yaxis=dict(gridcolor="#2d3047", zeroline=True, zerolinecolor="#666"),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Risk zone legend
        lc1, lc2, lc3 = st.columns(3)
        lc1.markdown("🔴 **Critical** (Z > 2.0)")
        lc2.markdown("🟡 **Elevated** (Z 1–2)")
        lc3.markdown("🟢 **Normal** (Z < 1)")
    else:
        st.info("No history data available")

# ── Today's events ─────────────────────────────────────────────────────────────
with col_events:
    st.markdown("#### 🔔 Today's Top Events")

    def severity_class(s):
        if s >= 0.7: return "event-high",   "🔴"
        if s >= 0.4: return "event-medium", "🟡"
        return "event-low", "🟢"

    if events:
        shown = 0
        for ev in events[:6]:
            sev = ev.get("severity", 0)
            cls, icon = severity_class(sev)
            text  = ev.get("raw_text", ev.get("event_type", "—"))
            etype = ev.get("event_type", "").replace("_", " ").title()
            st.markdown(
                f'<div class="event-row {cls}">'
                f'{icon} <strong>{etype}</strong><br>'
                f'<small style="color:#aaa;">{text[:90]}{"..." if len(text)>90 else ""}</small><br>'
                f'<small>Severity: <b>{sev:.2f}</b> &nbsp;|&nbsp; Exposure: <b>{ev.get("india_exposure",0):.2f}</b></small>'
                f'</div>',
                unsafe_allow_html=True
            )
            shown += 1
        if shown == 0:
            st.info("No events above threshold today")
    else:
        st.info("No events found")

st.divider()

# ── SHAP top drivers ───────────────────────────────────────────────────────────
st.markdown("#### 🔍 Top ML Signal Drivers")
drivers = signal_data.get("top_drivers", [])
if drivers:
    cols = st.columns(min(len(drivers), 3))
    for i, driver in enumerate(drivers[:3]):
        feat  = driver.get("feature", "—").replace("_", " ")
        shap  = driver.get("shap_value", 0)
        color = "#ff4b4b" if shap > 0 else "#21c354"
        arrow = "▲ pushes HIGH VOL" if shap > 0 else "▼ reduces risk"
        cols[i].markdown(
            f'<div style="background:#1a1d27;border:1px solid #2d3047;border-radius:10px;padding:14px">'
            f'<div style="font-size:0.85rem;color:#888;">Driver #{i+1}</div>'
            f'<div style="font-weight:700;font-size:1rem;">{feat.title()}</div>'
            f'<div style="color:{color};font-size:1.1rem;font-weight:700;">SHAP {shap:+.3f}</div>'
            f'<div style="color:#888;font-size:0.8rem;">{arrow}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
