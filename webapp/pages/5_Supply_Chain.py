"""
Page 5 — Supply Chain Screener (Suresh's tool).
Interactive screener for India's trade corridor geopolitical risk.
Three entry points: search by country, screen by sector, or scan all corridors.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.api_client import (
    get_corridor_risk, get_all_corridors, get_corridors_by_sector, get_gpr_latest,
)

st.set_page_config(
    page_title="Supply Chain Screener — India AI-GPR",
    page_icon="🚢", layout="wide",
)

st.markdown("""
<style>
[data-testid="metric-container"] { background:#1a1d27; border:1px solid #2d3047; border-radius:10px; padding:16px; }
.risk-card-high   { background:#ff4b4b11; border:1px solid #ff4b4b55; border-radius:10px; padding:16px; margin-bottom:10px; }
.risk-card-medium { background:#ffa50011; border:1px solid #ffa50055; border-radius:10px; padding:16px; margin-bottom:10px; }
.risk-card-low    { background:#21c35411; border:1px solid #21c35455; border-radius:10px; padding:16px; margin-bottom:10px; }
.driver-chip { display:inline-block; background:#2d3047; border-radius:20px; padding:3px 12px; margin:3px; font-size:0.8rem; color:#ccc; }
.sanction-badge { background:#ff4b4b22; color:#ff4b4b; border:1px solid #ff4b4b66; border-radius:5px; padding:2px 10px; font-size:0.8rem; font-weight:700; }
.clear-badge    { background:#21c35422; color:#21c354; border:1px solid #21c35466; border-radius:5px; padding:2px 10px; font-size:0.8rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# 🚢 Supply Chain Risk Screener")
st.markdown(
    "Check geopolitical risk across India's 15 key trade corridors. "
    "Built for **MSMEs, exporters, and procurement teams** making sourcing and routing decisions."
)
st.divider()

# ── Live GPR context ───────────────────────────────────────────────────────────
gpr_now = get_gpr_latest()
gpr_val = gpr_now.get("normalized_gpr", 0)
gpr_col = "#ff4b4b" if gpr_val > 1.5 else ("#ffa500" if gpr_val > 0.5 else "#21c354")
st.markdown(
    f'<div style="background:#1a1d27;border:1px solid #2d3047;border-radius:10px;padding:14px 20px;margin-bottom:16px;">'
    f'<span style="color:#888;font-size:0.9rem;">India AI-GPR Index right now: </span>'
    f'<span style="color:{gpr_col};font-size:1.3rem;font-weight:700;">{gpr_val:+.2f}</span>'
    f'<span style="color:#666;font-size:0.85rem;"> &nbsp;—&nbsp; All corridor scores below are calibrated to this baseline</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Mode selector ──────────────────────────────────────────────────────────────
mode = st.radio(
    "How do you want to screen?",
    ["🌍 Search by Country", "🏭 Screen by Sector/Supply Chain", "📊 Full Corridor Dashboard"],
    horizontal=True,
)
st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# MODE 1 — Country search
# ══════════════════════════════════════════════════════════════════════════════
if mode == "🌍 Search by Country":
    st.markdown("### Search a Specific Trade Corridor")

    ALL_COUNTRIES = [
        "China", "USA", "UAE", "Russia", "Saudi Arabia", "Iraq",
        "Germany", "South Korea", "Australia", "Japan", "Iran",
        "Bangladesh", "Singapore", "Pakistan", "Nepal",
    ]

    col_search, col_compare = st.columns([1, 1])

    with col_search:
        country = st.selectbox("Select country", ALL_COUNTRIES, index=3)
        if st.button("🔍 Get Risk Profile", type="primary", use_container_width=True):
            with st.spinner(f"Fetching corridor risk for {country}..."):
                data = get_corridor_risk(country)
            st.session_state["corridor_result"] = data

    # Show result
    if "corridor_result" in st.session_state:
        data = st.session_state["corridor_result"]
        rl   = data.get("risk_level", "LOW")
        card_cls = {"HIGH": "risk-card-high", "MEDIUM": "risk-card-medium", "LOW": "risk-card-low"}.get(rl, "risk-card-low")
        icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(rl, "🟢")
        sanct = data.get("sanctions", False)

        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("GPR Score", f"{data['gpr']:.1f}", f"{rl} risk")
        k2.metric("Annual Trade", f"${data['trade_volume_bn']:.1f}B", f"Rank #{data['trade_rank']}")
        k3.metric("Sanctions", "Active ⚠️" if sanct else "Clear ✅")
        k4.metric("Sanctions type", data.get("sanctions_type", "None"))

        # Detail card
        st.markdown(
            f'<div class="{card_cls}">'
            f'<h4>{icon} {data["country"]} — {rl} RISK CORRIDOR</h4>'
            f'<p style="color:#bbb;">{data.get("corridor_note","")}</p>'
            f'<hr style="border-color:#333;">'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">'
            f'<div><b style="color:#888;font-size:0.8rem;">INDIA EXPORTS</b><br>'
            + " · ".join(f'<span style="color:#e0e0e0">{g}</span>' for g in data.get("primary_exports", [])) +
            f'</div>'
            f'<div><b style="color:#888;font-size:0.8rem;">INDIA IMPORTS</b><br>'
            + " · ".join(f'<span style="color:#e0e0e0">{g}</span>' for g in data.get("primary_imports", [])) +
            f'</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Risk drivers
        st.markdown("**⚡ Risk Drivers**")
        drivers_html = "".join(
            f'<span class="driver-chip">⚠️ {d}</span>'
            for d in data.get("risk_drivers", [])
        )
        st.markdown(drivers_html, unsafe_allow_html=True)

        # Sectors exposed
        st.markdown("**🏭 Exposed Sectors in India**")
        sectors_html = "".join(
            f'<span class="driver-chip" style="background:#1f2d47;color:#4f8ef7;">📦 {s}</span>'
            for s in data.get("sectors_exposed", [])
        )
        st.markdown(sectors_html, unsafe_allow_html=True)

        # Recommendation box
        st.markdown("")
        if rl == "HIGH":
            st.error(
                f"🚨 **Action recommended:** Audit {data['country']}-dependent supply chains. "
                f"{'Sanctions create payment/compliance risk. ' if sanct else ''}"
                f"Consider alternative sourcing or hedging import costs."
            )
        elif rl == "MEDIUM":
            st.warning(
                f"⚠️ **Monitor closely.** {data['country']} poses moderate risk. "
                f"Set price and supply alerts for goods: {', '.join(data.get('primary_imports', [])[:2])}."
            )
        else:
            st.success(
                f"✅ **Low risk corridor.** {data['country']} is a stable trade partner. "
                f"No immediate action required."
            )


# ══════════════════════════════════════════════════════════════════════════════
# MODE 2 — Sector screener
# ══════════════════════════════════════════════════════════════════════════════
elif mode == "🏭 Screen by Sector/Supply Chain":
    st.markdown("### Screen by Your Industry Sector")
    st.markdown("Select your industry to see which trade corridors create geopolitical exposure for your supply chain.")

    SECTORS = ["Energy", "IT", "Pharma", "Electronics", "Defence",
               "Fertilisers", "Auto", "Textiles", "Mining"]
    SECTOR_ICONS = {
        "Energy": "⛽", "IT": "💻", "Pharma": "💊", "Electronics": "🔌",
        "Defence": "🛡️", "Fertilisers": "🌾", "Auto": "🚗",
        "Textiles": "🧵", "Mining": "⛏️",
    }

    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        sector = st.selectbox(
            "Your sector",
            SECTORS,
            format_func=lambda s: f"{SECTOR_ICONS.get(s,'')} {s}",
        )
        st.markdown(f"**{SECTOR_ICONS.get(sector,'')} {sector} sector** — exposed corridors:")

    with st.spinner(f"Screening {sector} corridors..."):
        result = get_corridors_by_sector(sector)
        corridors = result.get("corridors", [])

    if corridors:
        with col_s2:
            # Gauge-style bar chart
            df_sec = pd.DataFrame(corridors).sort_values("gpr", ascending=True)
            COLOUR = df_sec["gpr"].apply(
                lambda g: "#ff4b4b" if g >= 2.5 else ("#ffa500" if g >= 1.5 else "#21c354")
            ).tolist()
            fig = go.Figure(go.Bar(
                x=df_sec["gpr"], y=df_sec["country"],
                orientation="h",
                marker_color=COLOUR,
                text=df_sec["gpr"].map(lambda g: f"GPR {g:.1f}"),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>GPR: %{x:.1f}<extra></extra>",
            ))
            fig.add_vline(x=1.5, line_dash="dash", line_color="#ffa500",
                          annotation_text="Medium threshold", annotation_font_color="#ffa500")
            fig.add_vline(x=2.5, line_dash="dash", line_color="#ff4b4b",
                          annotation_text="High threshold", annotation_font_color="#ff4b4b")
            fig.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)", height=max(220, len(corridors)*60),
                margin=dict(l=0, r=60, t=10, b=0),
                xaxis=dict(title="India-centric GPR Score", range=[0, 5], gridcolor="#2d3047"),
                yaxis=dict(gridcolor="#2d3047"),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Risk summary cards
        high_c   = [c for c in corridors if c["risk_level"] == "HIGH"]
        medium_c = [c for c in corridors if c["risk_level"] == "MEDIUM"]

        if high_c:
            st.error(
                f"🚨 **{len(high_c)} HIGH-RISK corridor{'s' if len(high_c)>1 else ''} for {sector}:** "
                + ", ".join(c["country"] for c in high_c) +
                ". Consider supply chain diversification."
            )
        if medium_c:
            st.warning(
                f"⚠️ **{len(medium_c)} medium-risk corridor{'s' if len(medium_c)>1 else ''}:** "
                + ", ".join(c["country"] for c in medium_c) + "."
            )
        if not high_c and not medium_c:
            st.success(f"✅ All {sector} corridors are currently low risk.")

        # Detail table
        st.markdown("**Corridor detail**")
        df_disp = pd.DataFrame(corridors)
        df_disp["sanctions"] = df_disp["sanctions"].map({True: "⚠️ Active", False: "✅ Clear"})
        df_disp = df_disp.rename(columns={
            "country": "Country", "gpr": "GPR Score",
            "risk_level": "Risk Level", "sanctions": "Sanctions",
        })
        st.dataframe(df_disp[["Country", "GPR Score", "Risk Level", "Sanctions"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info(f"No corridor data found for sector: {sector}")


# ══════════════════════════════════════════════════════════════════════════════
# MODE 3 — Full dashboard
# ══════════════════════════════════════════════════════════════════════════════
elif mode == "📊 Full Corridor Dashboard":
    st.markdown("### All 15 Trade Corridors — Ranked by Risk")

    with st.spinner("Loading all corridors..."):
        all_c = get_all_corridors()

    if not all_c:
        st.error("No corridor data available.")
        st.stop()

    df = pd.DataFrame(all_c)

    # ── Summary row ────────────────────────────────────────────────────────────
    n_high   = (df["risk_level"] == "HIGH").sum()
    n_sanct  = df["sanctions"].sum()
    top_5_vol = df.nlargest(5, "trade_volume_bn")["trade_volume_bn"].sum()
    high_vol  = df[df["risk_level"] == "HIGH"]["trade_volume_bn"].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total corridors",           len(df))
    m2.metric("🔴 High-risk corridors",    int(n_high))
    m3.metric("⚠️ Active sanctions",       int(n_sanct))
    m4.metric("Trade at risk (HIGH only)", f"${high_vol:.0f}B",
              help="Annual bilateral trade with HIGH-risk corridors")

    st.divider()

    # ── Bubble chart: trade volume vs GPR ──────────────────────────────────────
    col_bub, col_rank = st.columns([1.5, 1])

    with col_bub:
        st.markdown("#### Risk vs Trade Volume")
        COLOUR_MAP = {"HIGH": "#ff4b4b", "MEDIUM": "#ffa500", "LOW": "#21c354"}
        df["colour"] = df["risk_level"].map(COLOUR_MAP)
        df["sanctions_label"] = df["sanctions"].map({True: "⚠️ Sanctions", False: ""})

        fig_bub = go.Figure()
        for level, col in COLOUR_MAP.items():
            sub = df[df["risk_level"] == level]
            fig_bub.add_trace(go.Scatter(
                x=sub["trade_volume_bn"],
                y=sub["gpr"],
                mode="markers+text",
                name=level,
                marker=dict(
                    size=sub["trade_volume_bn"] ** 0.42 * 3.5,
                    color=col, opacity=0.85,
                    line=dict(color="white", width=0.5),
                ),
                text=sub["country"],
                textposition="top center",
                textfont=dict(size=10, color="#ccc"),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Trade: $%{x:.1f}B<br>"
                    "GPR: %{y:.2f}<extra></extra>"
                ),
            ))

        fig_bub.add_hrect(y0=2.5, y1=5.0, fillcolor="red",    opacity=0.05, line_width=0)
        fig_bub.add_hrect(y0=1.5, y1=2.5, fillcolor="orange", opacity=0.05, line_width=0)
        fig_bub.add_hrect(y0=0.0, y1=1.5, fillcolor="green",  opacity=0.04, line_width=0)
        fig_bub.add_hline(y=2.5, line_dash="dash", line_color="#ff4b4b55")
        fig_bub.add_hline(y=1.5, line_dash="dash", line_color="#ffa50055")

        fig_bub.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", height=420,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(title="Annual Bilateral Trade ($B)", gridcolor="#2d3047"),
            yaxis=dict(title="India-centric GPR Score", gridcolor="#2d3047"),
            legend=dict(title="Risk Level"),
        )
        st.plotly_chart(fig_bub, use_container_width=True)
        st.caption(
            "Bubble size = trade volume. **Top-right quadrant = highest priority** "
            "(high trade AND high risk — where diversification matters most)."
        )

    with col_rank:
        st.markdown("#### Risk Leaderboard")
        df_sorted = df.sort_values("gpr", ascending=False).reset_index(drop=True)
        for _, row in df_sorted.iterrows():
            icon  = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(row["risk_level"], "⚪")
            sanct = " ⚠️" if row["sanctions"] else ""
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:8px 12px;background:#1a1d27;border-radius:8px;margin-bottom:5px;">'
                f'<span>{icon} <b>{row["country"]}</b>{sanct}</span>'
                f'<span style="color:#888;">{row["gpr"]:.1f} &nbsp; ${row["trade_volume_bn"]:.0f}B</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Sanctions-only view ────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### ⚠️ Sanctions-Active Corridors — Compliance Risk")
    sanct_df = df[df["sanctions"]].sort_values("gpr", ascending=False)
    if sanct_df.empty:
        st.success("No active sanctions on current corridors.")
    else:
        for _, row in sanct_df.iterrows():
            icon = {"HIGH": "🔴", "MEDIUM": "🟡"}.get(row["risk_level"], "🟡")
            st.markdown(
                f'<div class="risk-card-high">'
                f'<b>{icon} {row["country"]}</b> &nbsp;'
                f'<span style="color:#ff4b4b;font-size:0.85rem;">GPR {row["gpr"]:.1f} — SANCTIONS ACTIVE</span><br>'
                f'<span style="color:#888;font-size:0.85rem;">Annual trade: ${row["trade_volume_bn"]:.1f}B</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Full data table ────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 📋 Full Corridor Data Table")
    display_df = df[["country", "gpr", "risk_level", "sanctions", "trade_volume_bn", "trade_rank"]].copy()
    display_df["sanctions"]       = display_df["sanctions"].map({True: "⚠️ Active", False: "✅ Clear"})
    display_df["trade_volume_bn"] = display_df["trade_volume_bn"].map("${:.1f}B".format)
    display_df["gpr"]             = display_df["gpr"].map("{:.1f}".format)
    display_df = display_df.rename(columns={
        "country": "Country", "gpr": "GPR Score", "risk_level": "Risk Level",
        "sanctions": "Sanctions", "trade_volume_bn": "Annual Trade", "trade_rank": "Rank",
    }).sort_values("Rank")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ── Download ───────────────────────────────────────────────────────────────
    from datetime import date
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download corridor data as CSV",
        data=csv,
        file_name=f"india_trade_corridors_{date.today().isoformat()}.csv",
        mime="text/csv",
    )
