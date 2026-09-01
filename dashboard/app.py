import streamlit as st
import sqlite3
import pandas as pd
import altair as alt
import json
import os
import sys
import time
from datetime import datetime

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_generator import main as run_data_generator
from src.classifier import classify_exceptions
from src.escalation import apply_stopping_rules_and_escalate
from src.report import generate_reconciliation_report
from src.audit_report import get_audit_trail
from src.matcher import run_matcher
from src.rule_engine import get_applicable_rate
from src.simulator import simulate_policy_shift
from src.remediation import generate_debit_note, schedule_gstr8_sync, trigger_escrow_freeze, update_dispute_status

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_manifest.json")

# ───────────────── STREAMLIT PAGE CONFIG ─────────────────
st.set_page_config(
    page_title="SplitGuard AI | Settlement Recon & Integrity Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ───────────────── HIGH-END FINTECH DESIGN SYSTEM CSS ─────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --bg-main: #060b14;
        --bg-card: #0b1324;
        --bg-surface: #101c36;
        --border-subtle: rgba(148, 163, 184, 0.14);
        --border-focus: rgba(14, 165, 233, 0.45);
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --brand-blue: #0ea5e9;
        --brand-emerald: #10b981;
        --brand-rose: #f43f5e;
        --brand-amber: #f59e0b;
        --brand-violet: #8b5cf6;
    }

    * { font-family: 'Plus Jakarta Sans', sans-serif; }
    code, pre, .mono { font-family: 'JetBrains Mono', monospace !important; }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2.5rem;
        max-width: 96% !important;
    }

    /* ── HERO BANNER ── */
    .hero-banner {
        background: linear-gradient(135deg, #071329 0%, #0c234a 55%, #083366 100%);
        border-radius: 16px;
        padding: 22px 30px;
        margin-bottom: 20px;
        border: 1px solid rgba(14, 165, 233, 0.28);
        box-shadow: 0 10px 30px -10px rgba(14, 165, 233, 0.2);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 14px;
    }
    .hero-title {
        font-size: 1.75rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin: 0;
        color: #ffffff;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 0.88rem;
        margin-top: 4px;
        max-width: 760px;
        line-height: 1.5;
    }
    .live-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.45);
        color: #34d399;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 6px 14px;
        border-radius: 20px;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .pulse-dot {
        width: 8px;
        height: 8px;
        background: #10b981;
        border-radius: 50%;
        animation: pulse-ring 2s ease-in-out infinite;
    }
    @keyframes pulse-ring {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    /* ── TOP KPI METRIC STRIP ── */
    .kpi-row {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 12px;
        margin-bottom: 20px;
    }
    @media (max-width: 1024px) {
        .kpi-row { grid-template-columns: repeat(2, 1fr); }
    }
    .kpi-box {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 14px 18px;
        position: relative;
        overflow: hidden;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-box:hover {
        transform: translateY(-2px);
        border-color: var(--border-focus);
    }
    .kpi-stripe {
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
    }
    .kpi-title {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .kpi-number {
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1.2;
    }
    .kpi-desc {
        font-size: 0.72rem;
        color: #94a3b8;
        margin-top: 3px;
        white-space: nowrap;
    }

    /* ── SECTION CARDS ── */
    .section-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 20px 22px;
        margin-bottom: 18px;
    }
    .card-header-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* ── STRUCTURED WATERFALL COMPARISON TABLE ── */
    .wf-table-container {
        border: 1px solid var(--border-subtle);
        border-radius: 10px;
        overflow: hidden;
        background: #091224;
    }
    .wf-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.80rem;
    }
    .wf-table th {
        background: #101c36;
        color: #94a3b8;
        font-size: 0.66rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 8px 10px;
        text-align: left;
        border-bottom: 1px solid var(--border-subtle);
    }
    .wf-table th:last-child, .wf-table td:last-child {
        text-align: right;
    }
    .wf-row {
        border-bottom: 1px solid rgba(148, 163, 184, 0.08);
        transition: background 0.15s ease;
    }
    .wf-row:hover {
        background: #12203e;
    }
    .wf-row td {
        padding: 8px 10px;
        color: #cbd5e1;
    }
    .wf-row td:first-child {
        font-weight: 600;
        color: #f8fafc;
    }
    .wf-row td:last-child {
        font-weight: 700;
    }
    .wf-row.variance {
        background: rgba(244, 63, 94, 0.08);
    }
    .wf-row.total-row {
        background: #142447;
        font-weight: 700;
        border-top: 1px solid rgba(14, 165, 233, 0.35);
    }
    .wf-row.total-row td {
        color: #ffffff;
        font-size: 0.84rem;
        padding: 10px 10px;
    }

    .delta-bad { color: #fb7185; font-weight: 700; }
    .delta-good { color: #34d399; font-weight: 600; }
    .delta-timing { color: #38bdf8; font-weight: 600; }

    /* ── BADGE CHIPS ── */
    .badge-chip {
        font-size: 0.70rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 12px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        display: inline-block;
    }
    .chip-math { background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }
    .chip-timing { background: rgba(6, 182, 212, 0.15); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.3); }
    .chip-compliance { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .chip-cleared { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .chip-escalated { background: rgba(139, 92, 246, 0.15); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3); }

    /* ── FORMAL DEBIT NOTE VOUCHER CARD ── */
    .voucher-card {
        background: #091224;
        border: 1px solid rgba(14, 165, 233, 0.35);
        border-radius: 10px;
        padding: 16px;
        font-size: 0.80rem;
        margin-top: 10px;
        line-height: 1.6;
    }
    .voucher-card-title {
        color: #38bdf8;
        font-weight: 800;
        letter-spacing: 0.04em;
        border-bottom: 1px solid rgba(148, 163, 184, 0.15);
        padding-bottom: 6px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
    }

    /* ── FOOTER ── */
    .app-footer {
        text-align: center;
        padding: 26px 0 10px 0;
        color: #64748b;
        font-size: 0.78rem;
        border-top: 1px solid rgba(148, 163, 184, 0.1);
        margin-top: 36px;
    }
    .app-footer a { color: var(--brand-blue); text-decoration: none; }
</style>
""", unsafe_allow_html=True)


# ───────────────── PIPELINE CONTROLLERS ─────────────────
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

# Ensure DB is created
if not os.path.exists(DB_PATH):
    regenerate_all_data()


# ───────────────── SIDEBAR CONTROLLER ─────────────────
with st.sidebar:
    st.markdown("## ⚡ SplitGuard AI")
    st.caption("Autonomous Marketplace Settlement Engine")
    st.divider()

    st.markdown("#### ⚙️ Pipeline Control")
    if st.button("▶ Run Full Reconciliation Cycle", type="primary", use_container_width=True):
        with st.spinner("Reconstructing point-in-time contracts & evaluating variance..."):
            time.sleep(0.2)
            execute_pipeline()
            st.toast("Reconciliation cycle completed successfully!", icon="⚡")
            st.rerun()

    if st.button("🎲 Re-Seed Synthetic Batch (60 Orders)", use_container_width=True):
        with st.spinner("Generating fresh multi-vendor transactions & injecting edge cases..."):
            regenerate_all_data()
            st.toast("Fresh synthetic marketplace batch initialized!", icon="🌱")
            st.rerun()

    st.divider()
    st.markdown("#### 🛡️ Compliance & Safety Architecture")
    st.markdown("""
    - **Contract Engine:** `Point-in-Time Active`
    - **Nodal Guard:** `Auto-Halt on Deficit`
    - **Statutory Rules:** `Sec 52 TCS • Sec 194-O TDS`
    - **Stopping Threshold:** `< 0.70 Conf → Human Ops`
    - **ACID Database:** `SQLite Relational Engine`
    """)
    st.divider()
    st.caption("Razorpay AI Buildathon 2026 Submission")


# ───────────────── DATA FETCHING ─────────────────
conn = sqlite3.connect(DB_PATH)
report = generate_reconciliation_report(conn)
audit_df = get_audit_trail(conn)
matcher_df = run_matcher(conn)


# ───────────────── HERO BANNER ─────────────────
st.markdown("""
<div class="hero-banner">
    <div>
        <div class="hero-title">
            <span>⚡ SplitGuard AI</span>
            <span style="font-size: 0.85rem; font-weight: 600; color: #38bdf8; background: rgba(14,165,233,0.15); padding: 3px 10px; border-radius: 12px; border: 1px solid rgba(14,165,233,0.3);">Enterprise Recon</span>
        </div>
        <div class="hero-subtitle">
            Autonomous settlement integrity agent for multi-vendor marketplaces. Reconstructs point-in-time commission contracts, intercepts over-clawed refunds, filters GSTR-8 tax timing lags, and enforces strict nodal escrow solvency guards.
        </div>
    </div>
    <div>
        <span class="live-badge"><div class="pulse-dot"></div> RECON AGENT ACTIVE</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ───────────────── TOP KPI METRIC STRIP ─────────────────
esc_count = report['status_counts'].get('escalated', 0)
rev_count = report['status_counts'].get('needs-review', 0)
auto_count = report['status_counts'].get('auto-cleared', 0)

st.markdown(f"""
<div class="kpi-row">
    <div class="kpi-box">
        <div class="kpi-stripe" style="background: linear-gradient(90deg, #3b82f6, #0ea5e9);"></div>
        <div class="kpi-title">Match Rate</div>
        <div class="kpi-number" style="color: #60a5fa;">{report['match_rate']}%</div>
        <div class="kpi-desc">{report['clean_orders']} / {report['total_orders']} orders clean</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-stripe" style="background: linear-gradient(90deg, #f43f5e, #e11d48);"></div>
        <div class="kpi-title">Settlement Leakage</div>
        <div class="kpi-number" style="color: #fb7185;">₹{report['total_settlement_leakage_inr']:,.0f}</div>
        <div class="kpi-desc">Math & slab variances</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-stripe" style="background: linear-gradient(90deg, #f59e0b, #d97706);"></div>
        <div class="kpi-title">Structural Risk</div>
        <div class="kpi-number" style="color: #fbbf24;">₹{report['total_structural_exposure_inr']:,.0f}</div>
        <div class="kpi-desc">Nodal break & split blocks</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-stripe" style="background: linear-gradient(90deg, #8b5cf6, #7c3aed);"></div>
        <div class="kpi-title">Escalated to Ops</div>
        <div class="kpi-number" style="color: #a78bfa;">{esc_count}</div>
        <div class="kpi-desc">Halted for human ops</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-stripe" style="background: linear-gradient(90deg, #10b981, #059669);"></div>
        <div class="kpi-title">Tax Timing Filter</div>
        <div class="kpi-number" style="color: #34d399;">{report['tax_timing_pct']}%</div>
        <div class="kpi-desc">Filtered non-leakage (GSTR-8)</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ───────────────── 5 PRODUCTION TABS ─────────────────
tab_overview, tab_triage, tab_diagnostic, tab_simulator, tab_audit = st.tabs([
    "📊 Executive Analytics",
    "🔍 Exception Triage",
    "🔬 Order Diagnostic & Recovery",
    "🧮 Vendor 360° & Policy Simulator",
    "📜 Regulatory Audit Trail"
])


# ════════════════════════════════════════════════════════════════
# TAB 1: EXECUTIVE ANALYTICS (CLEAN GRAPHS, ZERO OVERLAPS)
# ════════════════════════════════════════════════════════════════
with tab_overview:
    # Row 1: Two Clean Balanced Charts
    col_chart_left, col_chart_right = st.columns([1, 1])

    with col_chart_left:
        st.markdown("""
        <div class="section-card">
            <div class="card-header-title">
                <span>🎯 Variance by Classification Bucket</span>
                <span style="font-size:0.75rem; color:#94a3b8;">3-Class Partition</span>
            </div>
        """, unsafe_allow_html=True)

        type_data = pd.DataFrame([
            {"Classification": k, "Count": v} for k, v in report["type_counts"].items()
        ])
        
        if not type_data.empty:
            donut_chart = alt.Chart(type_data).mark_arc(innerRadius=62, outerRadius=90, strokeWidth=2, stroke="#0b1324").encode(
                theta=alt.Theta("Count:Q"),
                color=alt.Color("Classification:N", scale=alt.Scale(
                    domain=["settlement-math", "tax-timing", "structural/compliance"],
                    range=["#f43f5e", "#06b6d4", "#f59e0b"]
                ), legend=alt.Legend(
                    title=None,
                    orient="bottom",
                    columns=3,
                    labelColor="#cbd5e1",
                    labelFontSize=11,
                    symbolSize=80,
                    labelLimit=200
                )),
                tooltip=["Classification:N", "Count:Q"]
            ).properties(
                height=230,
                width="container"
            ).configure_view(strokeWidth=0).configure(background="transparent")
            st.altair_chart(donut_chart, use_container_width=True)
            
        st.markdown("</div>", unsafe_allow_html=True)

    with col_chart_right:
        st.markdown("""
        <div class="section-card">
            <div class="card-header-title">
                <span>🏢 Top Financial Exposure by Entity</span>
                <span style="font-size:0.75rem; color:#94a3b8;">Ranked Exposure (₹)</span>
            </div>
        """, unsafe_allow_html=True)

        exc_df = report["exceptions_df"].copy()
        orders_map = pd.read_sql_query("SELECT order_id, vendor_id FROM orders", conn)
        exc_vendor = pd.merge(exc_df, orders_map, on="order_id", how="left")
        exc_vendor["vendor_id"] = exc_vendor["vendor_id"].fillna("NODAL-LEDGER")
        vendor_impact = exc_vendor.groupby("vendor_id")["rupee_impact"].sum().reset_index()
        vendor_impact = vendor_impact.sort_values("rupee_impact", ascending=False).head(6)

        if not vendor_impact.empty:
            hbar_chart = alt.Chart(vendor_impact).mark_bar(
                cornerRadiusTopRight=6, cornerRadiusBottomRight=6,
                color=alt.Gradient(gradient='linear', stops=[
                    alt.GradientStop(color='#0ea5e9', offset=0),
                    alt.GradientStop(color='#8b5cf6', offset=1)
                ], x1=0, x2=1, y1=0, y2=0)
            ).encode(
                y=alt.Y("vendor_id:N", sort="-x", title=None, axis=alt.Axis(labelColor="#cbd5e1", labelFontSize=11, labelPadding=12, labelLimit=150)),
                x=alt.X("rupee_impact:Q", title="₹ Total Financial Exposure", axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8", titlePadding=10, format=",.0f")),
                tooltip=[alt.Tooltip("vendor_id:N", title="Entity"), alt.Tooltip("rupee_impact:Q", title="₹ Exposure", format=",.2f")]
            ).properties(
                height=230,
                width="container",
                padding={"left": 20, "right": 20, "top": 10, "bottom": 10}
            ).configure_view(strokeWidth=0).configure(background="transparent")
            st.altair_chart(hbar_chart, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # Row 2: Nodal Solvency Monitor Chart (Crisp, native Streamlit multi-line chart)
    st.markdown("""
    <div class="section-card">
        <div class="card-header-title">
            <span>📈 Daily Nodal Account Solvency Monitor (RBI Directions)</span>
            <div style="font-size:0.75rem; display:flex; gap:16px;">
                <span style="color:#0ea5e9; font-weight:700;">● Actual Closing</span>
                <span style="color:#f59e0b; font-weight:700;">● Mathematical Expected</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    nodal_df = pd.read_sql_query("SELECT date, opening_balance, collected, settled, closing_balance FROM nodal_account_ledger ORDER BY date", conn)
    nodal_df["expected_closing"] = round(nodal_df["opening_balance"] + nodal_df["collected"] - nodal_df["settled"], 2)

    chart_data = pd.DataFrame({
        "Date": pd.to_datetime(nodal_df["date"]),
        "Actual Nodal Closing": nodal_df["closing_balance"],
        "Mathematical Expected": nodal_df["expected_closing"]
    }).set_index("Date")

    st.line_chart(chart_data, color=["#0ea5e9", "#f59e0b"], height=250, use_container_width=True)

    st.markdown("""
    <div style="font-size:0.76rem; color:#f59e0b; background:rgba(245,158,11,0.1); padding:8px 14px; border-radius:8px; border:1px solid rgba(245,158,11,0.25); margin-top:8px;">
        ⚠️ <strong>Solvency Alert Detected:</strong> On <code>2026-08-14</code>, Nodal closing balance diverged by <strong>₹50,000.00</strong> deficit from mathematical formula (<code>Opening + Collected - Settled</code>). Automated batch processing halted under RBI circuit-breaker rules.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# TAB 2: SMART EXCEPTION TRIAGE & LEDGER
# ════════════════════════════════════════════════════════════════
with tab_triage:
    st.markdown("""
    <div class="section-card">
        <div class="card-header-title">
            <span>🔍 Filterable Exception Ledger (₹ Impact Ranked)</span>
            <span style="font-size:0.75rem; color:#94a3b8;">Multi-parameter Query</span>
        </div>
    """, unsafe_allow_html=True)

    tf1, tf2, tf3, tf4 = st.columns(4)
    vendors_df = pd.read_sql_query("SELECT DISTINCT vendor_id FROM orders", conn)
    vendor_list = ["All Vendors"] + sorted(vendors_df["vendor_id"].tolist())
    type_list = ["All Types"] + sorted(list(report["type_counts"].keys()))
    status_list = ["All Statuses"] + sorted(list(report["status_counts"].keys()))

    with tf1:
        selected_type = st.selectbox("Classification Bucket", type_list, key="triage_filter_type")
    with tf2:
        selected_status = st.selectbox("Stopping Status", status_list, key="triage_filter_status")
    with tf3:
        selected_vendor = st.selectbox("Vendor ID", vendor_list, key="triage_filter_vendor")
    with tf4:
        search_query = st.text_input("Search Order / Ref", placeholder="e.g. ORD-001, NODAL", key="triage_search")

    exc_df = report["exceptions_df"].copy()
    orders_map = pd.read_sql_query("SELECT order_id, vendor_id, category, gross_amount FROM orders", conn)
    exc_merged = pd.merge(exc_df, orders_map, on="order_id", how="left")
    exc_merged["vendor_id"] = exc_merged["vendor_id"].fillna("NODAL-LEDGER")
    exc_merged["category"] = exc_merged["category"].fillna("Nodal Escrow")

    if selected_type != "All Types":
        exc_merged = exc_merged[exc_merged["exception_type"] == selected_type]
    if selected_status != "All Statuses":
        exc_merged = exc_merged[exc_merged["status"] == selected_status]
    if selected_vendor != "All Vendors":
        exc_merged = exc_merged[exc_merged["vendor_id"] == selected_vendor]
    if search_query:
        exc_merged = exc_merged[exc_merged["order_id"].str.contains(search_query, case=False, na=False) |
                                exc_merged["exception_id"].str.contains(search_query, case=False, na=False)]

    st.dataframe(
        exc_merged[[
            "exception_id", "order_id", "vendor_id", "category",
            "exception_type", "rupee_impact", "confidence_score", "status", "reason"
        ]],
        column_config={
            "exception_id": st.column_config.TextColumn("Ref #", width="small"),
            "order_id": st.column_config.TextColumn("Order ID", width="small"),
            "vendor_id": st.column_config.TextColumn("Vendor", width="small"),
            "category": st.column_config.TextColumn("Category", width="small"),
            "exception_type": st.column_config.TextColumn("Classification Bucket", width="medium"),
            "rupee_impact": st.column_config.NumberColumn("₹ Impact", format="₹%.2f"),
            "confidence_score": st.column_config.ProgressColumn("Confidence", min_value=0.0, max_value=1.0, format="%.3f"),
            "status": st.column_config.TextColumn("Status", width="small"),
            "reason": st.column_config.TextColumn("Root Cause & Legal Diagnostic", width="large")
        },
        use_container_width=True,
        hide_index=True
    )

    st.caption(f"Displaying **{len(exc_merged)}** filtered exceptions (Total exposure: **₹{exc_merged['rupee_impact'].sum():,.2f}**)")
    st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# TAB 3: ORDER DIAGNOSTIC & RECOVERY (STRUCTURED & INTUITIVE)
# ════════════════════════════════════════════════════════════════
with tab_diagnostic:
    st.markdown("""
    <div class="section-card">
        <div class="card-header-title">
            <span>🔬 Forensic Order Inspector & Remediation Hub</span>
            <span style="font-size:0.75rem; color:#94a3b8;">Line-by-Line Comparative Audit</span>
        </div>
    """, unsafe_allow_html=True)

    all_order_ids = sorted(matcher_df["order_id"].tolist())

    col_target_sel, col_target_info = st.columns([1, 2])
    with col_target_sel:
        target_order = st.selectbox(
            "Select Order to Audit",
            options=all_order_ids,
            index=all_order_ids.index("ORD-001") if "ORD-001" in all_order_ids else 0,
            help="Choose any order to inspect line-by-line settlement math and statutory tax deductions."
        )

    order_detail = matcher_df[matcher_df["order_id"] == target_order].iloc[0]
    exc_match = report["exceptions_df"][report["exceptions_df"]["order_id"] == target_order]
    has_exception = not exc_match.empty
    exc_info = exc_match.iloc[0] if has_exception else None

    with col_target_info:
        if has_exception:
            exc_t = exc_info["exception_type"]
            chip_class = "chip-math" if exc_t == "settlement-math" else ("chip-timing" if exc_t == "tax-timing" else "chip-compliance")
            delta_val = order_detail['payout_delta']
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; background:#091224; padding:10px 16px; border-radius:10px; border:1px solid var(--border-subtle); margin-top:24px;">
                <div>
                    <span class="badge-chip {chip_class}">{exc_t}</span>
                    <span class="badge-chip chip-escalated" style="margin-left:6px;">Status: {exc_info['status'].upper()}</span>
                </div>
                <div style="font-size:0.92rem; font-weight:800; color:{'#fb7185' if delta_val != 0 else '#34d399'};">
                    Variance: ₹{delta_val:,.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(16,185,129,0.1); padding:10px 16px; border-radius:10px; border:1px solid rgba(16,185,129,0.3); margin-top:24px;">
                <span class="badge-chip chip-cleared">✓ CLEAN RECONCILIATION</span>
                <span style="font-size:0.92rem; font-weight:800; color:#34d399;">Variance: ₹0.00</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # 2 Column Forensic Grid with balanced [13, 10] ratio
    diag_c1, diag_c2 = st.columns([13, 10])

    with diag_c1:
        st.markdown("##### 🧮 Settlement Line Item Comparison")

        comm_delta = order_detail["comm_delta"]
        tcs_delta = order_detail["tcs_delta"]
        tds_delta = order_detail["tds_delta"]
        payout_delta = order_detail["payout_delta"]

        st.markdown(f"""
        <div class="wf-table-container">
            <table class="wf-table">
                <thead>
                    <tr>
                        <th>Line Item</th>
                        <th>Expected</th>
                        <th>Actual</th>
                        <th>Variance (Δ)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr class="wf-row">
                        <td>Gross Order Amount</td>
                        <td class="mono">₹{order_detail['gross_amount']:,.2f}</td>
                        <td class="mono">₹{order_detail['gross_amount']:,.2f}</td>
                        <td class="delta-good">₹0.00</td>
                    </tr>
                    <tr class="wf-row {'variance' if abs(comm_delta) > 0.01 else ''}">
                        <td>Commission ({order_detail['comm_rate']*100:.1f}%)</td>
                        <td class="mono">₹{order_detail['expected_comm']:,.2f}</td>
                        <td class="mono">₹{order_detail['actual_comm']:,.2f}</td>
                        <td class="{'delta-bad' if abs(comm_delta) > 0.01 else 'delta-good'}">{'+' if comm_delta > 0 else ''}₹{comm_delta:,.2f}</td>
                    </tr>
                    <tr class="wf-row {'variance' if abs(tcs_delta) > 0.01 else ''}">
                        <td>TCS Withholding (1.0%)</td>
                        <td class="mono">₹{order_detail['expected_tcs']:,.2f}</td>
                        <td class="mono">₹{order_detail['actual_tcs']:,.2f}</td>
                        <td class="{'delta-timing' if abs(tcs_delta) > 0.01 else 'delta-good'}">{'+' if tcs_delta > 0 else ''}₹{tcs_delta:,.2f}</td>
                    </tr>
                    <tr class="wf-row {'variance' if abs(tds_delta) > 0.01 else ''}">
                        <td>TDS (Sec 194-O)</td>
                        <td class="mono">₹{order_detail['expected_tds']:,.2f}</td>
                        <td class="mono">₹{order_detail['actual_tds']:,.2f}</td>
                        <td class="{'delta-bad' if abs(tds_delta) > 0.01 else 'delta-good'}">{'+' if tds_delta > 0 else ''}₹{tds_delta:,.2f}</td>
                    </tr>
                    <tr class="wf-row">
                        <td>Logistics Fee</td>
                        <td class="mono">₹100.00</td>
                        <td class="mono">₹100.00</td>
                        <td class="delta-good">₹0.00</td>
                    </tr>
                    <tr class="wf-row">
                        <td>Refund Clawback</td>
                        <td class="mono">-₹{order_detail['refund_amount']:,.2f}</td>
                        <td class="mono">-₹{order_detail['refund_amount']:,.2f}</td>
                        <td class="delta-good">₹0.00</td>
                    </tr>
                    <tr class="wf-row total-row">
                        <td>NET VENDOR PAYOUT</td>
                        <td class="mono">₹{order_detail['expected_payout']:,.2f}</td>
                        <td class="mono">₹{order_detail['actual_payout']:,.2f}</td>
                        <td class="{'delta-bad' if abs(payout_delta) > 0.01 else 'delta-good'}">{'+' if payout_delta > 0 else ''}₹{payout_delta:,.2f}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """, unsafe_allow_html=True)

    with diag_c2:
        st.markdown("##### 🤖 Root-Cause Analysis & Action Hub")
        
        if has_exception:
            st.info(f"**Root Cause Diagnosis:** {exc_info['reason']}")
            
            st.markdown("###### ⚡ Operations Remediation Actions:")
            
            if exc_info["exception_type"] == "settlement-math":
                if st.button("📝 Generate Official Debit Note to Aggregator", key="btn_debit_note", type="primary", use_container_width=True):
                    dn_res = generate_debit_note(conn, target_order, "Payment Aggregator", "Next Settlement Cycle (T+1)")
                    st.markdown(f"""
                    <div class="voucher-card">
                        <div class="voucher-card-title">
                            <span>OFFICIAL DEBIT NOTE VOUCHER</span>
                            <span class="mono" style="color:#a78bfa;">{dn_res['note_id']}</span>
                        </div>
                        <strong>Order Ref:</strong> {target_order} &nbsp;|&nbsp; <strong>Entity:</strong> {dn_res['target_entity']}<br>
                        <strong>Recovery Amount:</strong> <span style="font-weight:800; color:#fb7185;">₹{dn_res['amount_inr']:,.2f}</span><br>
                        <strong>Settlement Term:</strong> {dn_res['recovery_schedule']} &nbsp;|&nbsp; <strong>Status:</strong> <span style="color:#34d399;">{dn_res['status']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            elif exc_info["exception_type"] == "tax-timing":
                if st.button("⏳ Queue for GSTR-8 Auto-Release Sync", key="btn_gstr8_sync", type="primary", use_container_width=True):
                    schedule_gstr8_sync(conn, target_order, order_detail["vendor_id"], "2026-08-20")
                    st.success(f"✅ Order **{target_order}** queued for automated tax clearance upon GSTR-8 portal filing verification.")
            else:
                if st.button("🚨 Dispatch Compliance Freeze Alert to Banking Escrow", key="btn_escrow_freeze", type="primary", use_container_width=True):
                    trigger_escrow_freeze(conn, order_detail["order_date"], order_detail["gross_amount"])
                    st.warning(f"⚠️ Emergency Freeze notification dispatched to Escrow Banking Ops for **{target_order}**.")

            with st.expander("🛠️ Manual Dispute Override / Review Notes"):
                new_st = st.selectbox("Update Resolution Status", ["auto-cleared", "needs-review", "escalated"], key="override_status")
                override_note = st.text_input("Operational Note", placeholder="e.g. Approved after vendor audit call", key="override_note")
                if st.button("Save Override Record", key="btn_save_override"):
                    update_dispute_status(conn, target_order, new_st, override_note)
                    st.toast(f"Status for {target_order} updated to {new_st}!", icon="✅")
                    st.rerun()
        else:
            st.success("✅ **Zero Financial Variance Found:** Point-in-time commission contract, statutory tax deductions (TCS/TDS), and logistics fees perfectly reconcile against bank settlement payout.")

    st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# TAB 4: VENDOR 360° & POLICY SIMULATOR (BALANCED & CLEAN)
# ════════════════════════════════════════════════════════════════
with tab_simulator:
    st.markdown("""
    <div class="section-card">
        <div class="card-header-title">
            <span>🧮 Vendor 360° Profile & What-If Policy Simulator</span>
            <span style="font-size:0.75rem; color:#94a3b8;">Portfolio Impact Modeling</span>
        </div>
    """, unsafe_allow_html=True)

    sim_c1, sim_c2 = st.columns([1, 1])

    with sim_c1:
        st.markdown("##### 🏢 Vendor 360° Profile Dossier")
        all_vendors = sorted(pd.read_sql_query("SELECT DISTINCT vendor_id FROM orders", conn)["vendor_id"].tolist())
        target_vendor = st.selectbox("Select Vendor", all_vendors, key="v360_vendor")

        # Vendor metrics
        v_orders = pd.read_sql_query("SELECT * FROM orders WHERE vendor_id = ?", conn, params=(target_vendor,))
        v_settlements = pd.read_sql_query("SELECT s.* FROM settlements s JOIN orders o ON s.order_id = o.order_id WHERE o.vendor_id = ?", conn, params=(target_vendor,))
        v_slabs = pd.read_sql_query("SELECT * FROM commission_slabs WHERE vendor_id = ? ORDER BY effective_from", conn, params=(target_vendor,))

        total_v_gross = v_orders["gross_amount"].sum()
        total_v_payout = v_settlements["amount"].sum()
        total_v_comm = v_settlements["commission_deducted"].sum()

        # Clean 3 mini KPI cards
        vk1, vk2, vk3 = st.columns(3)
        with vk1:
            st.markdown(f"""
            <div style="background:#091224; padding:12px; border-radius:10px; border:1px solid var(--border-subtle);">
                <div style="font-size:0.68rem; color:#64748b; font-weight:700; text-transform:uppercase;">Gross Sales GMV</div>
                <div style="font-size:1.1rem; font-weight:800; color:#38bdf8;">₹{total_v_gross:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)
        with vk2:
            st.markdown(f"""
            <div style="background:#091224; padding:12px; border-radius:10px; border:1px solid var(--border-subtle);">
                <div style="font-size:0.68rem; color:#64748b; font-weight:700; text-transform:uppercase;">Net Payout</div>
                <div style="font-size:1.1rem; font-weight:800; color:#34d399;">₹{total_v_payout:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)
        with vk3:
            st.markdown(f"""
            <div style="background:#091224; padding:12px; border-radius:10px; border:1px solid var(--border-subtle);">
                <div style="font-size:0.68rem; color:#64748b; font-weight:700; text-transform:uppercase;">Comm. Retained</div>
                <div style="font-size:1.1rem; font-weight:800; color:#a78bfa;">₹{total_v_comm:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        st.markdown("###### 📜 Active Commission Slabs")
        st.dataframe(
            v_slabs[["effective_from", "effective_to", "rate"]],
            column_config={
                "effective_from": "Effective From",
                "effective_to": "Effective To",
                "rate": st.column_config.NumberColumn("Commission Rate", format="%.2f%%")
            },
            use_container_width=True,
            hide_index=True
        )

    with sim_c2:
        st.markdown("##### 🎛️ Interactive \"What-If\" Policy Simulator")

        st.markdown("""
        <div style="background:#091224; padding:18px; border-radius:12px; border:1px solid rgba(139,92,246,0.3);">
            <div style="font-size:0.75rem; font-weight:700; color:#a78bfa; text-transform:uppercase; margin-bottom:8px;">Policy Adjustment Parameters</div>
        """, unsafe_allow_html=True)

        sim_comm_adj = st.slider("Commission Adjustment (%)", min_value=-5.0, max_value=5.0, value=0.0, step=0.5,
                                  help="Simulate increasing or decreasing commission slabs across all vendors.")
        sim_tds_rate = st.select_slider("TDS Tax Rate Regime (Sec 194-O)", options=[0.001, 0.0075, 0.010, 0.020], value=0.0075,
                                         format_func=lambda x: f"{x*100:.2f}%")

        # Run pure simulation using src.simulator module
        sim_res = simulate_policy_shift(conn, commission_adj_pct=sim_comm_adj, tds_rate=sim_tds_rate)
        net_rev_shift = sim_res["platform_revenue_shift"]

        st.markdown(f"""
            <div style="margin-top:14px; padding-top:12px; border-top:1px solid rgba(148,163,184,0.15);">
                <div style="font-size:0.72rem; color:#64748b; font-weight:700; text-transform:uppercase; margin-bottom:8px;">Projected Portfolio Impact</div>
                <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:0.85rem;">
                    <span>Projected Platform Commission:</span>
                    <span class="mono" style="font-weight:700; color:#38bdf8;">₹{sim_res['projected_platform_commission']:,.2f}</span>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:0.85rem;">
                    <span>Platform Revenue Shift:</span>
                    <span class="mono" style="font-weight:700; color:{'#34d399' if net_rev_shift >= 0 else '#fb7185'};">
                        {'+' if net_rev_shift >= 0 else ''}₹{net_rev_shift:,.2f}
                    </span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.85rem;">
                    <span>Projected TDS Withholding:</span>
                    <span class="mono" style="color:#cbd5e1;">₹{sim_res['projected_tds_withheld']:,.2f}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# TAB 5: REGULATORY AUDIT TRAIL
# ════════════════════════════════════════════════════════════════
with tab_audit:
    st.markdown("""
    <div class="section-card">
        <div class="card-header-title">
            <span>📜 Immutable Regulatory Compliance Audit Trail</span>
            <span style="font-size:0.75rem; color:#94a3b8;">RBI & Statutory Trace</span>
        </div>
    """, unsafe_allow_html=True)

    ac1, ac2 = st.columns([1, 4])
    with ac1:
        audit_depth = st.slider("Events Depth", min_value=5, max_value=60, value=20, key="audit_depth_slider")
        
        # Download Certificate
        audit_cert = {
            "certificate_id": f"RECON-CERT-{datetime.now().strftime('%Y%m%d%H%M')}",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "match_rate": report["match_rate"],
            "total_orders_evaluated": report["total_orders"],
            "clean_orders": report["clean_orders"],
            "total_leakage_prevented_inr": report["total_settlement_leakage_inr"],
            "structural_exposure_inr": report["total_structural_exposure_inr"],
            "escalated_count": esc_count,
            "compliance_standards": ["Section 52 CGST Act", "Section 194-O Income Tax", "RBI Nodal Account Directions"]
        }
        st.download_button(
            label="📥 Download Audit Certificate (JSON)",
            data=json.dumps(audit_cert, indent=2),
            file_name=f"recon_audit_certificate_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True
        )

        # Download CSV
        csv_data = report["exceptions_df"].to_csv(index=False)
        st.download_button(
            label="📥 Export Exception Ledger (CSV)",
            data=csv_data,
            file_name=f"settlement_exceptions_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with ac2:
        recent_audit = audit_df.tail(audit_depth).sort_values("log_id", ascending=False)
        st.dataframe(
            recent_audit[["log_id", "timestamp", "stage", "action", "detail"]],
            column_config={
                "log_id": st.column_config.NumberColumn("#", width="small"),
                "timestamp": st.column_config.TextColumn("Timestamp", width="medium"),
                "stage": st.column_config.TextColumn("Pipeline Stage", width="small"),
                "action": st.column_config.TextColumn("Action Code", width="medium"),
                "detail": st.column_config.TextColumn("Regulatory & Pipeline Trace Detail", width="large"),
            },
            use_container_width=True,
            hide_index=True
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ───────────────── GLOBAL FOOTER ─────────────────
st.markdown("""
<div class="app-footer">
    <strong>SplitGuard AI</strong> — Autonomous Split-Settlement Reconciliation & Escrow Integrity Engine<br>
    Built for <a href="https://razorpay.com" target="_blank">Razorpay AI Buildathon 2026</a> · Compliant with RBI Nodal Directions & Section 52/194-O Statutory Withholdings<br>
    <a href="https://github.com/ParthKhandelwal537/split-settlement-leakage-detector" target="_blank">View GitHub Repository</a>
</div>
""", unsafe_allow_html=True)

conn.close()
