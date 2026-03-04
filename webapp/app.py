"""
India AI-GPR Intelligence Platform — Streamlit Web App
Entry point: streamlit run webapp/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="India AI-GPR Platform",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #0f1117; }
    [data-testid="stSidebar"] * { color: #e0e0e0 !important; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: #1a1d27;
        border: 1px solid #2d3047;
        border-radius: 10px;
        padding: 16px;
    }

    /* Risk badge colours */
    .badge-high   { background:#ff4b4b22; color:#ff4b4b; border:1px solid #ff4b4b; border-radius:6px; padding:4px 12px; font-weight:700; }
    .badge-medium { background:#ffa50022; color:#ffa500; border:1px solid #ffa500; border-radius:6px; padding:4px 12px; font-weight:700; }
    .badge-low    { background:#21c35422; color:#21c354; border:1px solid #21c354; border-radius:6px; padding:4px 12px; font-weight:700; }

    /* Section headers */
    .section-header { font-size:1.1rem; font-weight:600; color:#a0aec0; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:8px; }

    /* Event rows */
    .event-row { padding:10px 14px; border-left:4px solid; border-radius:0 8px 8px 0; margin-bottom:8px; background:#1a1d27; }
    .event-high   { border-color:#ff4b4b; }
    .event-medium { border-color:#ffa500; }
    .event-low    { border-color:#21c354; }

    /* Hide default streamlit footer */
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/en/4/41/Flag_of_India.svg", width=48)
    st.markdown("## **India AI-GPR**\nIntelligence Platform")
    st.divider()
    st.markdown("""
    **Navigation**
    - 🏠 Dashboard
    - 📊 Portfolio Risk
    - 📈 GPR History
    - 🌍 Trade Risk Map
    """)
    st.divider()

    # Live health check
    from webapp.api_client import get_health
    health = get_health()
    status_color = "🟢" if health.get("status") == "ok" else ("🟡" if health.get("status") == "degraded" else "⚪")
    st.markdown(f"**System Status** {status_color}")
    st.caption(f"API: {health.get('status', 'Demo mode')}")
    st.caption(f"DB: {health.get('postgres', '—')}")
    st.caption(f"Cache: {health.get('redis', '—')}")

# ── Landing page content ───────────────────────────────────────────────────────
st.markdown("# 🇮🇳 India AI-GPR Intelligence Platform")
st.markdown(
    "Real-time geopolitical risk intelligence for Indian financial markets. "
    "Built on GDELT + FinBERT + GPT-4o-mini + XGBoost."
)
st.info("👈 **Use the sidebar to navigate between pages**, or select a page from the top of the navigation.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("🏠 Dashboard",       "Live GPR score + today's events")
col2.metric("📊 Portfolio Risk",  "Check your stock exposure")
col3.metric("📈 GPR History",     "Interactive time-series explorer")
col4.metric("🌍 Trade Risk",      "Country-level corridor risk")
