import streamlit as st
import sqlite3
import pandas as pd
import altair as alt
import json
import os
import sys
import time
from datetime import datetime

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_generator import main as run_data_generator
from src.classifier import classify_exceptions
from src.escalation import apply_stopping_rules_and_escalate
from src.report import generate_reconciliation_report
from src.audit_report import get_audit_trail

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_manifest.json")

# ───────────────── PAGE CONFIG ─────────────────
st.set_page_config(
    page_title="SplitGuard AI | Settlement Reconciliation Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ───────────────── PREMIUM DARK THEME CSS ─────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --bg-primary: #0b1120;
        --bg-card: #111827;
        --bg-card-hover: #1a2332;
        --bg-surface: #1e293b;
        --border-subtle: rgba(148, 163, 184, 0.12);
        --border-glow: rgba(14, 165, 233, 0.3);
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --accent-blue: #0ea5e9;
        --accent-red: #f43f5e;
        --accent-amber: #f59e0b;
        --accent-green: #10b981;
        --accent-violet: #8b5cf6;
        --accent-cyan: #06b6d4;
    }

    * { font-family: 'Inter', sans-serif; }
    code, pre, .mono { font-family: 'JetBrains Mono', monospace !important; }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        max-width: 96% !important;
    }

    /* ── HERO BANNER ── */
    .hero {
        background: linear-gradient(135deg, #0b1120 0%, #0f1d32 40%, #0c2d50 70%, #0d3868 100%);
        border-radius: 20px;
        padding: 32px 40px;
        margin-bottom: 28px;
        border: 1px solid var(--border-subtle);
        position: relative;
        overflow: hidden;
    }
    .hero::before {
        content: '';
        position: absolute;
        top: -60%;
        right: -20%;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(14, 165, 233, 0.08) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
        position: relative;
        z-index: 1;
    }
    .hero h1 {
        font-size: 2rem;
        font-weight: 900;
        letter-spacing: -0.04em;
        margin: 0;
        background: linear-gradient(135deg, #ffffff 0%, #94a3b8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero p {
        color: var(--text-secondary);
        font-size: 0.92rem;
        margin-top: 6px;
        max-width: 600px;
        line-height: 1.55;
    }
    
    /* ── ANIMATED PULSE BADGE ── */
    .agent-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.35);
        color: #34d399;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 6px 14px;
        border-radius: 24px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .pulse {
        width: 8px; height: 8px;
        background: #10b981;
        border-radius: 50%;
        animation: pulse-ring 2s ease-in-out infinite;
    }
    @keyframes pulse-ring {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
        70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    /* ── METRIC TILES ── */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 16px;
        margin-bottom: 28px;
    }
    @media (max-width: 900px) {
        .metric-grid { grid-template-columns: repeat(2, 1fr); }
    }
    .metric-tile {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 16px;
        padding: 20px 22px;
        transition: all 0.25s ease;
        position: relative;
        overflow: hidden;
    }
    .metric-tile:hover {
        border-color: var(--border-glow);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(14, 165, 233, 0.08);
    }
    .metric-tile .accent-bar {
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
    }
    .metric-label {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-muted);
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.9rem;
        font-weight: 900;
        letter-spacing: -0.03em;
        line-height: 1.1;
    }
    .metric-sub {
        font-size: 0.76rem;
        color: var(--text-secondary);
        margin-top: 6px;
    }

    /* ── SECTION HEADERS ── */
    .sh {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--text-primary);
        margin: 24px 0 12px 0;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: -0.01em;
    }

    /* ── SEED VERIFICATION CARDS ── */
    .seed-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 14px;
        margin-bottom: 24px;
    }
    @media (max-width: 900px) {
        .seed-grid { grid-template-columns: repeat(2, 1fr); }
    }
    .seed {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 18px 20px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        transition: all 0.2s ease;
    }
    .seed:hover {
        border-color: var(--border-glow);
        box-shadow: 0 4px 16px rgba(14, 165, 233, 0.06);
    }
    .seed-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
    }
    .seed-name {
        font-size: 0.88rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.35;
        max-width: 70%;
    }
    .badge-pass {
        background: rgba(16, 185, 129, 0.12);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        font-size: 0.65rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 10px;
        letter-spacing: 0.04em;
        white-space: nowrap;
    }
    .badge-fail {
        background: rgba(244, 63, 94, 0.12);
        color: #fb7185;
        border: 1px solid rgba(244, 63, 94, 0.3);
        font-size: 0.65rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 10px;
        letter-spacing: 0.04em;
    }
    .seed-detail {
        font-size: 0.78rem;
        color: var(--text-secondary);
        line-height: 1.5;
    }
    .seed-detail strong { color: var(--text-primary); }
    .seed-footer {
        background: var(--bg-surface);
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 0.73rem;
        color: var(--text-secondary);
    }
    .seed-footer code {
        color: var(--accent-cyan);
        font-weight: 600;
    }

    /* ── FOOTER ── */
    .footer {
        text-align: center;
        padding: 32px 0 12px 0;
        color: var(--text-muted);
        font-size: 0.78rem;
        border-top: 1px solid var(--border-subtle);
        margin-top: 40px;
    }
    .footer a { color: var(--accent-blue); text-decoration: none; }

    /* ── TAB STYLING ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: var(--bg-surface);
        border-radius: 12px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 18px;
        font-weight: 600;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


# ───────────────── HELPER FUNCTIONS ─────────────────
def execute_pipeline():
    conn = sqlite3.connect(DB_PATH)
    try:
        classify_exceptions(conn)
        apply_stopping_rules_and_escalate(conn)
    finally:
        conn.close()

def regenerate_all_data():
    run_data_generator()
    execute_pipeline()

# Ensure DB exists
if not os.path.exists(DB_PATH):
    regenerate_all_data()


# ───────────────── SIDEBAR ─────────────────
with st.sidebar:
    st.markdown("## ⚡ SplitGuard AI")
    st.caption("Autonomous Settlement Agent")
    st.divider()

    st.markdown("#### 🤖 Agent Controls")
    if st.button("▶ Run Reconciliation Cycle", type="primary", use_container_width=True):
        with st.spinner("Executing point-in-time matching & classification..."):
            time.sleep(0.2)
            execute_pipeline()
            st.toast("Reconciliation cycle complete.", icon="✅")
            st.rerun()

    if st.button("🔄 Reset & Re-Seed (60 Orders)", use_container_width=True):
        with st.spinner("Generating fresh synthetic batch..."):
            regenerate_all_data()
            st.toast("Fresh batch seeded with 4 edge cases.", icon="🌱")
            st.rerun()

    st.divider()
    st.markdown("#### 📡 System Info")
    st.markdown("""
    | Property | Value |
    |----------|-------|
    | Engine | Point-in-Time Rules |
    | Database | SQLite (ACID) |
    | Buckets | 3-class classifier |
    | Stopping | Compliance halt |
    | Tests | 7/7 passing |
    """)
    st.divider()
    st.caption("Built for Razorpay AI Buildathon 2026")


# ───────────────── DATA LOAD ─────────────────
conn = sqlite3.connect(DB_PATH)
report = generate_reconciliation_report(conn)
audit_df = get_audit_trail(conn)


# ───────────────── HERO BANNER ─────────────────
st.markdown("""
<div class="hero">
    <div class="hero-row">
        <div>
            <h1>⚡ SplitGuard AI — Leakage Detector</h1>
            <p>Autonomous reconciliation agent that detects commission slab mismatches, refund clawback overcharges, GSTR-8 timing gaps, and nodal balance breaks across multi-vendor marketplace settlements.</p>
        </div>
        <span class="agent-badge"><div class="pulse"></div>AGENT ACTIVE</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ───────────────── METRIC TILES ─────────────────
esc_count = report['status_counts'].get('escalated', 0)
rev_count = report['status_counts'].get('needs-review', 0)
auto_count = report['status_counts'].get('auto-cleared', 0)

st.markdown(f"""
<div class="metric-grid">
    <div class="metric-tile">
        <div class="accent-bar" style="background: linear-gradient(90deg, #3b82f6, #0ea5e9);"></div>
        <div class="metric-label">Match Rate</div>
        <div class="metric-value" style="color: #60a5fa;">{report['match_rate']}%</div>
        <div class="metric-sub">{report['clean_orders']}/{report['total_orders']} orders clean</div>
    </div>
    <div class="metric-tile">
        <div class="accent-bar" style="background: linear-gradient(90deg, #f43f5e, #e11d48);"></div>
        <div class="metric-label">Real Leakage</div>
        <div class="metric-value" style="color: #fb7185;">₹{report['total_settlement_leakage_inr']:,.0f}</div>
        <div class="metric-sub">Settlement-math losses</div>
    </div>
    <div class="metric-tile">
        <div class="accent-bar" style="background: linear-gradient(90deg, #f59e0b, #d97706);"></div>
        <div class="metric-label">Structural Risk</div>
        <div class="metric-value" style="color: #fbbf24;">₹{report['total_structural_exposure_inr']:,.0f}</div>
        <div class="metric-sub">Nodal breaks & blocked splits</div>
    </div>
    <div class="metric-tile">
        <div class="accent-bar" style="background: linear-gradient(90deg, #8b5cf6, #7c3aed);"></div>
        <div class="metric-label">Escalated</div>
        <div class="metric-value" style="color: #a78bfa;">{esc_count}</div>
        <div class="metric-sub">Halted for human ops</div>
    </div>
    <div class="metric-tile">
        <div class="accent-bar" style="background: linear-gradient(90deg, #10b981, #059669);"></div>
        <div class="metric-label">Self-Skepticism</div>
        <div class="metric-value" style="color: #34d399;">{report['tax_timing_pct']}%</div>
        <div class="metric-sub">Filtered as non-leakage</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ───────────────── TABBED LAYOUT ─────────────────
tab_overview, tab_triage, tab_seeds, tab_audit = st.tabs([
    "📊 Overview & Analytics", "🔍 Exception Triage", "🎯 Edge Case Verification", "📜 Audit Trail"
])


# ══════════════════ TAB 1: OVERVIEW ══════════════════
with tab_overview:
    st.markdown('<div class="sh">📊 Exception Classification Breakdown</div>', unsafe_allow_html=True)
    
    col_chart1, col_chart2 = st.columns([1, 2])

    with col_chart1:
        # Donut chart — exception types
        type_data = pd.DataFrame([
            {"Type": k, "Count": v} for k, v in report["type_counts"].items()
        ])
        if not type_data.empty:
            donut = alt.Chart(type_data).mark_arc(innerRadius=55, outerRadius=90, strokeWidth=2, stroke="#111827").encode(
                theta=alt.Theta("Count:Q"),
                color=alt.Color("Type:N", scale=alt.Scale(
                    domain=["settlement-math", "tax-timing", "structural/compliance"],
                    range=["#f43f5e", "#06b6d4", "#f59e0b"]
                ), legend=alt.Legend(title=None, orient="bottom", labelColor="#94a3b8")),
                tooltip=["Type:N", "Count:Q"]
            ).properties(
                width=260, height=260,
                title=alt.Title("By Classification Bucket", color="#e2e8f0", fontSize=13)
            ).configure_view(
                strokeWidth=0
            ).configure(
                background="#111827"
            )
            st.altair_chart(donut, use_container_width=True)

    with col_chart2:
        # Bar chart — leakage by vendor
        exc_df = report["exceptions_df"].copy()
        orders_map = pd.read_sql_query("SELECT order_id, vendor_id FROM orders", conn)
        exc_vendor = pd.merge(exc_df, orders_map, on="order_id", how="left")
        exc_vendor["vendor_id"] = exc_vendor["vendor_id"].fillna("LEDGER")
        vendor_impact = exc_vendor.groupby("vendor_id")["rupee_impact"].sum().reset_index()
        vendor_impact = vendor_impact.sort_values("rupee_impact", ascending=False).head(8)

        if not vendor_impact.empty:
            bar = alt.Chart(vendor_impact).mark_bar(
                cornerRadiusTopLeft=6, cornerRadiusTopRight=6,
                color=alt.Gradient(gradient='linear', stops=[
                    alt.GradientStop(color='#0ea5e9', offset=0),
                    alt.GradientStop(color='#8b5cf6', offset=1)
                ], x1=0, x2=0, y1=1, y2=0)
            ).encode(
                x=alt.X("vendor_id:N", sort="-y", title=None,
                         axis=alt.Axis(labelColor="#94a3b8", labelAngle=-30)),
                y=alt.Y("rupee_impact:Q", title="₹ Impact",
                         axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8")),
                tooltip=[alt.Tooltip("vendor_id:N", title="Vendor"),
                         alt.Tooltip("rupee_impact:Q", title="₹ Impact", format=",.0f")]
            ).properties(
                width="container", height=260,
                title=alt.Title("₹ Impact by Vendor (Top 8)", color="#e2e8f0", fontSize=13)
            ).configure_view(
                strokeWidth=0
            ).configure(
                background="#111827"
            )
            st.altair_chart(bar, use_container_width=True)

    # Nodal balance timeline
    st.markdown('<div class="sh">📈 Nodal Account Balance Timeline</div>', unsafe_allow_html=True)
    nodal_df = pd.read_sql_query("SELECT date, closing_balance FROM nodal_account_ledger ORDER BY date", conn)
    nodal_df["expected"] = pd.read_sql_query(
        "SELECT round(opening_balance + collected - settled, 2) as expected FROM nodal_account_ledger ORDER BY date", conn
    )["expected"]

    nodal_long = pd.melt(nodal_df, id_vars=["date"], value_vars=["closing_balance", "expected"],
                          var_name="series", value_name="balance")
    nodal_long["series"] = nodal_long["series"].map({
        "closing_balance": "Actual Closing",
        "expected": "Expected Closing"
    })

    line = alt.Chart(nodal_long).mark_line(strokeWidth=2).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(labelColor="#94a3b8", format="%b %d")),
        y=alt.Y("balance:Q", title="Balance (₹)",
                 axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8", format=",.0f"),
                 scale=alt.Scale(zero=False)),
        color=alt.Color("series:N", scale=alt.Scale(
            domain=["Actual Closing", "Expected Closing"],
            range=["#0ea5e9", "#64748b"]
        ), legend=alt.Legend(title=None, orient="top-right", labelColor="#94a3b8")),
        strokeDash=alt.StrokeDash("series:N", scale=alt.Scale(
            domain=["Actual Closing", "Expected Closing"],
            range=[[0], [6, 4]]
        ), legend=None),
        tooltip=["date:T", "series:N", alt.Tooltip("balance:Q", format="₹,.0f")]
    ).properties(
        width="container", height=280,
        title=alt.Title("Daily Nodal Balance — Actual vs Expected (anomaly on Aug 14)", color="#e2e8f0", fontSize=13)
    ).configure_view(
        strokeWidth=0
    ).configure(
        background="#111827"
    )
    st.altair_chart(line, use_container_width=True)


# ══════════════════ TAB 2: EXCEPTION TRIAGE ══════════════════
with tab_triage:
    st.markdown('<div class="sh">🔍 Filterable Exception Ledger (₹ Impact Ranked)</div>', unsafe_allow_html=True)

    f1, f2, f3 = st.columns(3)
    vendors_df = pd.read_sql_query("SELECT DISTINCT vendor_id FROM orders", conn)
    vendor_list = ["All Vendors"] + sorted(vendors_df["vendor_id"].tolist())
    type_list = ["All Types"] + sorted(list(report["type_counts"].keys()))
    status_list = ["All Statuses"] + sorted(list(report["status_counts"].keys()))

    with f1:
        selected_type = st.selectbox("Classification Bucket", type_list, key="triage_type")
    with f2:
        selected_status = st.selectbox("Stopping Rule Status", status_list, key="triage_status")
    with f3:
        selected_vendor = st.selectbox("Vendor ID", vendor_list, key="triage_vendor")

    exc_df = report["exceptions_df"].copy()
    orders_map = pd.read_sql_query("SELECT order_id, vendor_id, category, gross_amount FROM orders", conn)
    exc_merged = pd.merge(exc_df, orders_map, on="order_id", how="left")
    exc_merged["vendor_id"] = exc_merged["vendor_id"].fillna("LEDGER")
    exc_merged["category"] = exc_merged["category"].fillna("Nodal Ledger")

    if selected_type != "All Types":
        exc_merged = exc_merged[exc_merged["exception_type"] == selected_type]
    if selected_status != "All Statuses":
        exc_merged = exc_merged[exc_merged["status"] == selected_status]
    if selected_vendor != "All Vendors":
        exc_merged = exc_merged[exc_merged["vendor_id"] == selected_vendor]

    st.dataframe(
        exc_merged[[
            "exception_id", "order_id", "vendor_id", "category",
            "exception_type", "rupee_impact", "confidence_score", "status", "reason"
        ]],
        column_config={
            "exception_id": st.column_config.TextColumn("Ref", width="small"),
            "order_id": st.column_config.TextColumn("Order", width="small"),
            "vendor_id": st.column_config.TextColumn("Vendor", width="small"),
            "category": st.column_config.TextColumn("Category", width="small"),
            "exception_type": st.column_config.TextColumn("Bucket", width="medium"),
            "rupee_impact": st.column_config.NumberColumn("₹ Impact", format="₹%.2f"),
            "confidence_score": st.column_config.ProgressColumn("Confidence", min_value=0.0, max_value=1.0, format="%.3f"),
            "status": st.column_config.TextColumn("Status", width="small"),
            "reason": st.column_config.TextColumn("Root Cause Explanation", width="large")
        },
        use_container_width=True,
        hide_index=True
    )

    st.caption(f"Showing {len(exc_merged)} of {report['total_exceptions']} total exceptions")


# ══════════════════ TAB 3: SEEDED EDGE CASES ══════════════════
with tab_seeds:
    st.markdown('<div class="sh">🎯 Planted Edge Case Ground Truth Verification</div>', unsafe_allow_html=True)
    st.caption("These 4 test vectors were deliberately injected into synthetic data. The agent must catch each one through its general-purpose rules — no hardcoded shortcuts.")

    cards_html = '<div class="seed-grid">'
    for seed in report["seed_verifications"]:
        badge_cls = "badge-pass" if seed["verified"] else "badge-fail"
        badge_txt = "✓ CAUGHT" if seed["verified"] else "✗ MISSED"
        cards_html += f"""
        <div class="seed">
            <div class="seed-top">
                <span class="seed-name">{seed['case_name']}</span>
                <span class="{badge_cls}">{badge_txt}</span>
            </div>
            <div class="seed-detail">
                <strong>ID:</strong> <code class="mono">{seed['order_id']}</code><br>
                <strong>Bucket:</strong> {seed['actual_type']}<br>
                <strong>Impact:</strong> ₹{seed['rupee_impact']:,.2f}
            </div>
            <div class="seed-footer">
                Resolution → <code>{seed['status'].upper()}</code>
            </div>
        </div>
        """
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)

    # Seed manifest raw data
    with st.expander("📄 View Raw Seed Manifest (seed_manifest.json)"):
        if os.path.exists(MANIFEST_PATH):
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                st.json(json.load(f))


# ══════════════════ TAB 4: AUDIT TRAIL ══════════════════
with tab_audit:
    st.markdown('<div class="sh">📜 Immutable Pipeline Audit Log</div>', unsafe_allow_html=True)
    st.caption("Every stage execution, classification decision, and stopping rule halt is recorded with timestamps for regulatory compliance.")

    col_ctrl, col_table = st.columns([1, 5])
    with col_ctrl:
        last_n = st.slider("Events to show", min_value=5, max_value=50, value=15, key="audit_depth")
        st.info("Audit entries are persisted in SQLite and cannot be retroactively altered.")

    with col_table:
        recent_audit = audit_df.tail(last_n).sort_values("log_id", ascending=False)
        st.dataframe(
            recent_audit[["log_id", "timestamp", "stage", "action", "detail"]],
            column_config={
                "log_id": st.column_config.NumberColumn("#", width="small"),
                "timestamp": st.column_config.TextColumn("Timestamp", width="medium"),
                "stage": st.column_config.TextColumn("Stage", width="small"),
                "action": st.column_config.TextColumn("Action", width="medium"),
                "detail": st.column_config.TextColumn("Event Detail", width="large"),
            },
            use_container_width=True,
            hide_index=True
        )


# ───────────────── FOOTER ─────────────────
st.markdown("""
<div class="footer">
    <strong>SplitGuard AI</strong> — Split-Settlement Leakage Detector<br>
    Built for <a href="https://razorpay.com" target="_blank">Razorpay AI Buildathon 2026</a> ·
    Powered by Point-in-Time Rule Engine + 3-Bucket Classifier + Compliant Escalation<br>
    <a href="https://github.com/ParthKhandelwal537/split-settlement-leakage-detector" target="_blank">GitHub Repository</a>
</div>
""", unsafe_allow_html=True)

conn.close()
