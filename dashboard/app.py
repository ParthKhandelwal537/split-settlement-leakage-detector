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

# ───────────────── HIGH-END FINTECH DARK THEME CSS ─────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --bg-main: #060b14;
        --bg-card: #0b1324;
        --bg-surface: #111d35;
        --border-subtle: rgba(148, 163, 184, 0.12);
        --border-glow: rgba(14, 165, 233, 0.4);
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
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
        background: linear-gradient(135deg, #071226 0%, #0c234b 50%, #07356b 100%);
        border-radius: 18px;
        padding: 26px 36px;
        margin-bottom: 24px;
        border: 1px solid rgba(14, 165, 233, 0.28);
        box-shadow: 0 12px 36px -12px rgba(14, 165, 233, 0.25);
        position: relative;
        overflow: hidden;
    }
    .hero-banner::after {
        content: '';
        position: absolute;
        top: -40%;
        right: -10%;
        width: 480px;
        height: 480px;
        background: radial-gradient(circle, rgba(14, 165, 233, 0.15) 0%, transparent 70%);
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
    .hero-title {
        font-size: 1.85rem;
        font-weight: 900;
        letter-spacing: -0.04em;
        margin: 0;
        background: linear-gradient(135deg, #ffffff 20%, #cbd5e1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 0.90rem;
        margin-top: 6px;
        max-width: 760px;
        line-height: 1.55;
    }

    /* ── LIVE STATUS BADGE ── */
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
        70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    /* ── TOP KPI TILES ── */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 14px;
        margin-bottom: 24px;
    }
    @media (max-width: 1024px) {
        .kpi-container { grid-template-columns: repeat(2, 1fr); }
    }
    .kpi-card {
        background: #0b1324;
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 18px 20px;
        position: relative;
        overflow: hidden;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: var(--border-glow);
    }
    .kpi-card .top-stripe {
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
    }
    .kpi-label {
        font-size: 0.70rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748b;
        margin-bottom: 6px;
    }
    .kpi-val {
        font-size: 1.80rem;
        font-weight: 900;
        letter-spacing: -0.03em;
        line-height: 1.15;
    }
    .kpi-sub {
        font-size: 0.74rem;
        color: #94a3b8;
        margin-top: 6px;
        font-weight: 500;
    }

    /* ── DIAGNOSTIC WATERFALL & CARDS ── */
    .waterfall-card {
        background: #0b1324;
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 18px;
    }
    .waterfall-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 6px;
        background: #101a30;
        font-size: 0.84rem;
    }
    .waterfall-item.highlight {
        background: rgba(244, 63, 94, 0.12);
        border: 1px solid rgba(244, 63, 94, 0.35);
    }
    .waterfall-item.highlight-green {
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .waterfall-item.total {
        background: #172440;
        font-weight: 700;
        font-size: 0.92rem;
        margin-top: 12px;
        border: 1px solid rgba(14, 165, 233, 0.3);
    }

    /* ── FORMAL DEBIT NOTE VOUCHER ── */
    .voucher-card {
        background: #0b1324;
        border: 1px solid rgba(14, 165, 233, 0.35);
        border-radius: 12px;
        padding: 20px;
        font-size: 0.82rem;
        margin-top: 12px;
        line-height: 1.6;
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .voucher-header {
        border-bottom: 1px solid rgba(148, 163, 184, 0.15);
        padding-bottom: 10px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

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

    /* ── SECTION HEADINGS ── */
    .sec-header {
        font-size: 1.15rem;
        font-weight: 800;
        color: var(--text-primary);
        margin: 22px 0 12px 0;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: -0.02em;
    }

    /* ── APP FOOTER ── */
    .app-footer {
        text-align: center;
        padding: 30px 0 10px 0;
        color: #64748b;
        font-size: 0.78rem;
        border-top: 1px solid rgba(148, 163, 184, 0.1);
        margin-top: 40px;
    }
    .app-footer a { color: var(--brand-blue); text-decoration: none; }
</style>
""", unsafe_allow_html=True)


# ───────────────── PIPELINE EXECUTION HELPERS ─────────────────
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

# Initialize DB if not present
if not os.path.exists(DB_PATH):
    regenerate_all_data()


# ───────────────── SIDEBAR CONTROLLER ─────────────────
with st.sidebar:
    st.markdown("## ⚡ SplitGuard AI")
    st.caption("Autonomous Marketplace Settlement Engine")
    st.divider()

    st.markdown("#### ⚙️ Pipeline Control Center")
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
    - **Point-in-Time Contract Engine:** `Active`
    - **Nodal Integrity Guard:** `Auto-Halt on Deficit`
    - **Statutory Rules:** `Sec 52 TCS • Sec 194-O TDS`
    - **Stopping Threshold:** `< 0.70 Conf → Human Ops`
    - **Architecture:** `ACID Relational Engine`
    """)
    st.divider()
    st.caption("Razorpay AI Buildathon 2026 Submission")


# ───────────────── DATA FETCHING ─────────────────
conn = sqlite3.connect(DB_PATH)
report = generate_reconciliation_report(conn)
audit_df = get_audit_trail(conn)
matcher_df = run_matcher(conn)


# ───────────────── HERO HEADER ─────────────────
st.markdown("""
<div class="hero-banner">
    <div class="hero-row">
        <div>
            <div class="hero-title">
                <span>⚡ SplitGuard AI</span>
                <span style="font-size: 0.95rem; font-weight: 600; color: #38bdf8; background: rgba(14,165,233,0.15); padding: 4px 10px; border-radius: 12px; border: 1px solid rgba(14,165,233,0.3);">Enterprise Recon</span>
            </div>
            <div class="hero-subtitle">
                Autonomous settlement integrity agent for multi-vendor marketplaces. Reconstructs point-in-time commission contracts, intercepts over-clawed refunds, filters GSTR-8 tax timing lags, and enforces strict nodal escrow solvency guards.
            </div>
        </div>
        <div>
            <span class="live-badge"><div class="pulse-dot"></div> RECONCILIATION AGENT ACTIVE</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ───────────────── TOP KPI METRICS ─────────────────
esc_count = report['status_counts'].get('escalated', 0)
rev_count = report['status_counts'].get('needs-review', 0)
auto_count = report['status_counts'].get('auto-cleared', 0)

st.markdown(f"""
<div class="kpi-container">
    <div class="kpi-card">
        <div class="top-stripe" style="background: linear-gradient(90deg, #3b82f6, #0ea5e9);"></div>
        <div class="kpi-label">Reconciliation Match</div>
        <div class="kpi-val" style="color: #60a5fa;">{report['match_rate']}%</div>
        <div class="kpi-sub">{report['clean_orders']} of {report['total_orders']} orders clean</div>
    </div>
    <div class="kpi-card">
        <div class="top-stripe" style="background: linear-gradient(90deg, #f43f5e, #e11d48);"></div>
        <div class="kpi-label">Settlement Leakage</div>
        <div class="kpi-val" style="color: #fb7185;">₹{report['total_settlement_leakage_inr']:,.0f}</div>
        <div class="kpi-sub">Direct math & slab losses</div>
    </div>
    <div class="kpi-card">
        <div class="top-stripe" style="background: linear-gradient(90deg, #f59e0b, #d97706);"></div>
        <div class="kpi-label">Structural Exposure</div>
        <div class="kpi-val" style="color: #fbbf24;">₹{report['total_structural_exposure_inr']:,.0f}</div>
        <div class="kpi-sub">Nodal deficit & blocked splits</div>
    </div>
    <div class="kpi-card">
        <div class="top-stripe" style="background: linear-gradient(90deg, #8b5cf6, #7c3aed);"></div>
        <div class="kpi-label">Escalated to Ops</div>
        <div class="kpi-val" style="color: #a78bfa;">{esc_count}</div>
        <div class="kpi-sub">Halted for human intervention</div>
    </div>
    <div class="kpi-card">
        <div class="top-stripe" style="background: linear-gradient(90deg, #10b981, #059669);"></div>
        <div class="kpi-label">Self-Skepticism Index</div>
        <div class="kpi-val" style="color: #34d399;">{report['tax_timing_pct']}%</div>
        <div class="kpi-sub">Filtered non-leakage (GSTR-8)</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ───────────────── 5 ENTERPRISE PRODUCTION TABS ─────────────────
tab_overview, tab_triage, tab_diagnostic, tab_simulator, tab_audit = st.tabs([
    "📊 Executive Analytics",
    "🔍 Exception Triage",
    "🔬 Order Diagnostic & Recovery",
    "🧮 Vendor 360° & Policy Simulator",
    "📜 Regulatory Audit Trail"
])


# ════════════════════════════════════════════════════════════════
# TAB 1: EXECUTIVE ANALYTICS & RISK RADAR
# ════════════════════════════════════════════════════════════════
with tab_overview:
    st.markdown('<div class="sec-header">📊 Settlement Variance Risk Radar</div>', unsafe_allow_html=True)

    c_chart1, c_chart2 = st.columns([1, 2])

    with c_chart1:
        # Donut Chart - Exception Buckets
        type_data = pd.DataFrame([
            {"Classification": k, "Count": v} for k, v in report["type_counts"].items()
        ])
        if not type_data.empty:
            donut = alt.Chart(type_data).mark_arc(innerRadius=60, outerRadius=95, strokeWidth=2, stroke="#0b1324").encode(
                theta=alt.Theta("Count:Q"),
                color=alt.Color("Classification:N", scale=alt.Scale(
                    domain=["settlement-math", "tax-timing", "structural/compliance"],
                    range=["#f43f5e", "#06b6d4", "#f59e0b"]
                ), legend=alt.Legend(title=None, orient="bottom", labelColor="#94a3b8", labelFontSize=11)),
                tooltip=["Classification:N", "Count:Q"]
            ).properties(
                width=280, height=270,
                title=alt.Title("Variance by Classification Bucket", color="#f8fafc", fontSize=13)
            ).configure_view(strokeWidth=0).configure(background="#0b1324")
            st.altair_chart(donut, use_container_width=True)

    with c_chart2:
        # Bar Chart - Impact by Vendor
        exc_df = report["exceptions_df"].copy()
        orders_map = pd.read_sql_query("SELECT order_id, vendor_id FROM orders", conn)
        exc_vendor = pd.merge(exc_df, orders_map, on="order_id", how="left")
        exc_vendor["vendor_id"] = exc_vendor["vendor_id"].fillna("NODAL-LEDGER")
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
                         axis=alt.Axis(labelColor="#94a3b8", labelAngle=-25, labelFontSize=11)),
                y=alt.Y("rupee_impact:Q", title="₹ Financial Exposure",
                         axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8", format=",.0f")),
                tooltip=[alt.Tooltip("vendor_id:N", title="Entity"),
                         alt.Tooltip("rupee_impact:Q", title="₹ Exposure", format=",.2f")]
            ).properties(
                width="container", height=270,
                title=alt.Title("Top Financial Exposure by Vendor / Escrow (₹)", color="#f8fafc", fontSize=13)
            ).configure_view(strokeWidth=0).configure(background="#0b1324")
            st.altair_chart(bar, use_container_width=True)

    # Nodal Escrow Timeline
    st.markdown('<div class="sec-header">📈 Daily Nodal Account Solvency Monitor (RBI Directions)</div>', unsafe_allow_html=True)
    nodal_df = pd.read_sql_query("SELECT date, opening_balance, collected, settled, closing_balance FROM nodal_account_ledger ORDER BY date", conn)
    nodal_df["expected_closing"] = round(nodal_df["opening_balance"] + nodal_df["collected"] - nodal_df["settled"], 2)

    nodal_melted = pd.melt(nodal_df, id_vars=["date"], value_vars=["closing_balance", "expected_closing"],
                           var_name="Account Metric", value_name="Balance")
    nodal_melted["Account Metric"] = nodal_melted["Account Metric"].map({
        "closing_balance": "Actual Nodal Closing",
        "expected_closing": "Mathematical Expected Closing"
    })

    nodal_line = alt.Chart(nodal_melted).mark_line(strokeWidth=2.2).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(labelColor="#94a3b8", format="%b %d", labelFontSize=11)),
        y=alt.Y("Balance:Q", title="Balance (₹ INR)",
                 axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8", format=",.0f"),
                 scale=alt.Scale(zero=False)),
        color=alt.Color("Account Metric:N", scale=alt.Scale(
            domain=["Actual Nodal Closing", "Mathematical Expected Closing"],
            range=["#0ea5e9", "#64748b"]
        ), legend=alt.Legend(title=None, orient="top-right", labelColor="#94a3b8")),
        strokeDash=alt.StrokeDash("Account Metric:N", scale=alt.Scale(
            domain=["Actual Nodal Closing", "Mathematical Expected Closing"],
            range=[[0], [6, 4]]
        ), legend=None),
        tooltip=["date:T", "Account Metric:N", alt.Tooltip("Balance:Q", format="₹,.2f")]
    ).properties(
        width="container", height=280,
        title=alt.Title("62-Day Continuous Escrow Balance Audit (Detects ₹50,000 Deficit on Aug 14)", color="#f8fafc", fontSize=13)
    ).configure_view(strokeWidth=0).configure(background="#0b1324")
    st.altair_chart(nodal_line, use_container_width=True)


# ════════════════════════════════════════════════════════════════
# TAB 2: SMART EXCEPTION TRIAGE & LEDGER
# ════════════════════════════════════════════════════════════════
with tab_triage:
    st.markdown('<div class="sec-header">🔍 Filterable Exception Ledger (₹ Impact Ranked)</div>', unsafe_allow_html=True)

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

    st.caption(f"Displaying **{len(exc_merged)}** filtered exceptions (Total exposure in view: **₹{exc_merged['rupee_impact'].sum():,.2f}**)")


# ════════════════════════════════════════════════════════════════
# TAB 3: INTERACTIVE ORDER DIAGNOSTIC & RECOVERY HUB
# ════════════════════════════════════════════════════════════════
with tab_diagnostic:
    st.markdown('<div class="sec-header">🔬 Interactive Order Diagnostic & Recovery Hub</div>', unsafe_allow_html=True)
    st.caption("Perform deep forensic audit of any transaction, compare mathematical waterfall breakdowns, and trigger 1-click remediation actions.")

    all_order_ids = sorted(matcher_df["order_id"].tolist())

    col_sel1, col_sel2 = st.columns([2, 3])
    with col_sel1:
        target_order = st.selectbox(
            "Select Order for Forensic Audit",
            options=all_order_ids,
            index=all_order_ids.index("ORD-001") if "ORD-001" in all_order_ids else 0,
            help="Choose any order to inspect line-by-line settlement math and statutory tax deductions."
        )

    # Fetch order match details
    order_detail = matcher_df[matcher_df["order_id"] == target_order].iloc[0]
    
    # Check if there is an exception record
    exc_match = report["exceptions_df"][report["exceptions_df"]["order_id"] == target_order]
    has_exception = not exc_match.empty
    exc_info = exc_match.iloc[0] if has_exception else None

    with col_sel2:
        if has_exception:
            exc_t = exc_info["exception_type"]
            chip_class = "chip-math" if exc_t == "settlement-math" else ("chip-timing" if exc_t == "tax-timing" else "chip-compliance")
            st.markdown(f"""
            <div style="padding: 10px 16px; background: #101a30; border-radius: 10px; border: 1px solid var(--border-subtle); margin-top: 4px;">
                <span class="badge-chip {chip_class}">{exc_t}</span>
                <span class="badge-chip chip-escalated" style="margin-left:6px;">Status: {exc_info['status'].upper()}</span>
                <span style="float: right; font-weight: 700; color: #f43f5e; font-size: 0.95rem;">Variance: ₹{order_detail['payout_delta']:,.2f}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="padding: 10px 16px; background: rgba(16,185,129,0.1); border-radius: 10px; border: 1px solid rgba(16,185,129,0.3); margin-top: 4px;">
                <span class="badge-chip chip-cleared">✓ CLEAN RECONCILIATION</span>
                <span style="float: right; font-weight: 700; color: #34d399; font-size: 0.95rem;">Delta: ₹0.00</span>
            </div>
            """, unsafe_allow_html=True)

    # 2 Column Forensic Layout: Left Waterfall, Right Diagnosis & Recovery
    diag_c1, diag_c2 = st.columns([1, 1])

    with diag_c1:
        st.markdown("##### 🧮 Financial Waterfall Breakdown (Expected vs Settled)")
        
        gross_val = order_detail["gross_amount"]
        exp_comm = order_detail["expected_comm"]
        act_comm = order_detail["actual_comm"]
        comm_delta = order_detail["comm_delta"]

        exp_tcs = order_detail["expected_tcs"]
        act_tcs = order_detail["actual_tcs"]
        tcs_delta = order_detail["tcs_delta"]

        exp_tds = order_detail["expected_tds"]
        act_tds = order_detail["actual_tds"]
        tds_delta = order_detail["tds_delta"]

        refund_val = order_detail["refund_amount"]
        exp_payout = order_detail["expected_payout"]
        act_payout = order_detail["actual_payout"]
        payout_delta = order_detail["payout_delta"]

        # Commission delta highlight
        comm_cls = "highlight" if abs(comm_delta) > 0.01 else ""
        tcs_cls = "highlight" if abs(tcs_delta) > 0.01 else ""
        tds_cls = "highlight" if abs(tds_delta) > 0.01 else ""
        payout_cls = "highlight" if abs(payout_delta) > 0.01 else "highlight-green"

        st.markdown(f"""
        <div class="waterfall-card">
            <div class="waterfall-item">
                <span><strong>Gross Order Value</strong></span>
                <span class="mono" style="font-weight:700;">₹{gross_val:,.2f}</span>
            </div>
            <div class="waterfall-item {comm_cls}">
                <span>Marketplace Commission ({order_detail['comm_rate']*100:.1f}%)</span>
                <span>Expected: <span class="mono">₹{exp_comm:,.2f}</span> | Actual: <span class="mono">₹{act_comm:,.2f}</span> (Δ ₹{comm_delta:,.2f})</span>
            </div>
            <div class="waterfall-item {tcs_cls}">
                <span>TCS Withholding (Sec 52 - 1.0%)</span>
                <span>Expected: <span class="mono">₹{exp_tcs:,.2f}</span> | Actual: <span class="mono">₹{act_tcs:,.2f}</span> (Δ ₹{tcs_delta:,.2f})</span>
            </div>
            <div class="waterfall-item {tds_cls}">
                <span>TDS Withholding (Sec 194-O)</span>
                <span>Expected: <span class="mono">₹{exp_tds:,.2f}</span> | Actual: <span class="mono">₹{act_tds:,.2f}</span> (Δ ₹{tds_delta:,.2f})</span>
            </div>
            <div class="waterfall-item">
                <span>Logistics & Delivery Fee</span>
                <span><span class="mono">₹100.00</span></span>
            </div>
            <div class="waterfall-item">
                <span>Customer Refund / Clawback</span>
                <span><span class="mono">-₹{refund_val:,.2f}</span></span>
            </div>
            <div class="waterfall-item total {payout_cls}">
                <span>FINAL NET VENDOR PAYOUT</span>
                <span>Expected: <span class="mono">₹{exp_payout:,.2f}</span> | Settled: <span class="mono">₹{act_payout:,.2f}</span> (Δ ₹{payout_delta:,.2f})</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with diag_c2:
        st.markdown("##### 🤖 Autonomous Root-Cause Diagnosis & Remediation")
        
        if has_exception:
            st.info(f"**Diagnostic Summary:** {exc_info['reason']}")
            
            st.markdown("###### ⚡ 1-Click Operations Actions:")
            
            # Action based on type
            if exc_info["exception_type"] == "settlement-math":
                if st.button("📝 Generate Official Debit Note to Aggregator", key="btn_debit_note", type="primary", use_container_width=True):
                    dn_res = generate_debit_note(conn, target_order, "Razorpay Aggregator", "Next Settlement Cycle (T+1)")
                    st.markdown(f"""
                    <div class="voucher-card">
                        <div class="voucher-header">
                            <strong style="color:#38bdf8;">OFFICIAL DEBIT NOTE VOUCHER</strong>
                            <span class="mono" style="color:#a78bfa;">{dn_res['note_id']}</span>
                        </div>
                        <strong>Order Ref:</strong> {target_order}<br>
                        <strong>Target Entity:</strong> {dn_res['target_entity']}<br>
                        <strong>Recovery Amount:</strong> <span style="font-weight:800; color:#f43f5e;">₹{dn_res['amount_inr']:,.2f}</span><br>
                        <strong>Recovery Term:</strong> {dn_res['recovery_schedule']}<br>
                        <strong>Timestamp:</strong> {dn_res['issued_at']}<br>
                        <em>Status: {dn_res['status']}</em>
                    </div>
                    """, unsafe_allow_html=True)
            elif exc_info["exception_type"] == "tax-timing":
                if st.button("⏳ Queue for GSTR-8 Auto-Release Sync", key="btn_gstr8_sync", type="primary", use_container_width=True):
                    tax_res = schedule_gstr8_sync(conn, target_order, order_detail["vendor_id"], "2026-08-20")
                    st.success(f"✅ Order **{target_order}** queued for automated tax clearance upon GSTR-8 portal filing verification.")
            else:
                if st.button("🚨 Dispatch Compliance Freeze Alert to Banking Escrow", key="btn_escrow_freeze", type="primary", use_container_width=True):
                    esc_res = trigger_escrow_freeze(conn, order_detail["order_date"], order_detail["gross_amount"])
                    st.warning(f"⚠️ Freeze notification dispatched to Escrow Banking Ops for **{target_order}**.")

            with st.expander("🛠️ Manual Override / Dispute Status Update"):
                new_st = st.selectbox("Update Resolution Status", ["auto-cleared", "needs-review", "escalated"], key="override_status")
                override_note = st.text_input("Resolution Note", placeholder="e.g. Approved by Head of FinOps after vendor audit", key="override_note")
                if st.button("Save Override", key="btn_save_override"):
                    update_dispute_status(conn, target_order, new_st, override_note)
                    st.toast(f"Status for {target_order} updated to {new_st}!", icon="✅")
                    st.rerun()
        else:
            st.success("✅ **Zero Financial Variance Found:** Point-in-time commission contract, statutory tax deductions (TCS/TDS), and logistics fees perfectly reconcile against bank settlement payout.")


# ════════════════════════════════════════════════════════════════
# TAB 4: VENDOR 360° & "WHAT-IF" POLICY SIMULATOR
# ════════════════════════════════════════════════════════════════
with tab_simulator:
    st.markdown('<div class="sec-header">🧮 Vendor 360° Profile & What-If Policy Simulator</div>', unsafe_allow_html=True)
    st.caption("Simulate rate changes, test retroactive commission revisions, and project marketplace revenue & withholding shifts.")

    sim_col1, sim_col2 = st.columns([1, 1])

    with sim_col1:
        st.markdown("##### 🏢 Vendor 360° Profile Explorer")
        all_vendors = sorted(pd.read_sql_query("SELECT DISTINCT vendor_id FROM orders", conn)["vendor_id"].tolist())
        target_vendor = st.selectbox("Select Marketplace Vendor", all_vendors, key="v360_vendor")

        # Vendor metrics
        v_orders = pd.read_sql_query("SELECT * FROM orders WHERE vendor_id = ?", conn, params=(target_vendor,))
        v_settlements = pd.read_sql_query("SELECT s.* FROM settlements s JOIN orders o ON s.order_id = o.order_id WHERE o.vendor_id = ?", conn, params=(target_vendor,))
        v_slabs = pd.read_sql_query("SELECT * FROM commission_slabs WHERE vendor_id = ? ORDER BY effective_from", conn, params=(target_vendor,))

        total_v_gross = v_orders["gross_amount"].sum()
        total_v_payout = v_settlements["amount"].sum()
        total_v_comm = v_settlements["commission_deducted"].sum()

        st.markdown(f"""
        <div class="waterfall-card">
            <div class="waterfall-item">
                <span><strong>Total Gross Merchandise Value (GMV)</strong></span>
                <span class="mono" style="font-weight:700; color:#38bdf8;">₹{total_v_gross:,.2f}</span>
            </div>
            <div class="waterfall-item">
                <span>Total Settled Net Payout</span>
                <span class="mono" style="color:#34d399;">₹{total_v_payout:,.2f}</span>
            </div>
            <div class="waterfall-item">
                <span>Marketplace Commission Collected</span>
                <span class="mono" style="color:#a78bfa;">₹{total_v_comm:,.2f}</span>
            </div>
            <div class="waterfall-item">
                <span>Order Volume</span>
                <span class="mono">{len(v_orders)} Orders</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("###### 📜 Active Commission Slabs History")
        st.dataframe(
            v_slabs[["effective_from", "effective_to", "rate"]],
            column_config={
                "effective_from": "Effective From",
                "effective_to": "Effective To",
                "rate": st.column_config.NumberColumn("Commission Rate", format="%.2f%%", help="Point-in-time contracted commission rate")
            },
            use_container_width=True,
            hide_index=True
        )

    with sim_col2:
        st.markdown("##### 🎛️ Interactive \"What-If\" Policy Simulator")
        st.caption("Simulate prospective policy or tax changes on the entire marketplace batch:")

        sim_comm_adj = st.slider("Commission Adjustment (%)", min_value=-5.0, max_value=5.0, value=0.0, step=0.5,
                                  help="Simulate increasing or decreasing commission slabs across all vendors.")
        sim_tds_rate = st.select_slider("TDS Tax Rate Regime (Sec 194-O)", options=[0.001, 0.0075, 0.010, 0.020], value=0.0075,
                                         format_func=lambda x: f"{x*100:.2f}%")

        # Run pure simulation using src.simulator module
        sim_res = simulate_policy_shift(conn, commission_adj_pct=sim_comm_adj, tds_rate=sim_tds_rate)

        net_rev_shift = sim_res["platform_revenue_shift"]

        st.markdown(f"""
        <div class="waterfall-card" style="border-color: rgba(139,92,246,0.35);">
            <div style="font-size: 0.82rem; font-weight: 700; color: #a78bfa; margin-bottom: 8px;">SIMULATION PROJECTIONS (PORTFOLIO WIDE)</div>
            <div class="waterfall-item">
                <span>Total Portfolio GMV Analyzed</span>
                <span class="mono">₹{sim_res['total_gmv']:,.2f}</span>
            </div>
            <div class="waterfall-item">
                <span>Projected Platform Revenue</span>
                <span class="mono" style="font-weight:700; color:#38bdf8;">₹{sim_res['projected_platform_commission']:,.2f}</span>
            </div>
            <div class="waterfall-item">
                <span>Platform Revenue Shift</span>
                <span class="mono" style="font-weight:700; color:{'#34d399' if net_rev_shift >= 0 else '#fb7185'};">
                    {'+' if net_rev_shift >= 0 else ''}₹{net_rev_shift:,.2f}
                </span>
            </div>
            <div class="waterfall-item">
                <span>Projected TDS Withholding Volume</span>
                <span class="mono">₹{sim_res['projected_tds_withheld']:,.2f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# TAB 5: REGULATORY COMPLIANCE & AUDIT TRAIL
# ════════════════════════════════════════════════════════════════
with tab_audit:
    st.markdown('<div class="sec-header">📜 Immutable Regulatory Compliance Audit Trail</div>', unsafe_allow_html=True)
    st.caption("Full chronological trace recording every point-in-time calculation, variance detection, and automated stopping rule enforcement.")

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


# ───────────────── GLOBAL FOOTER ─────────────────
st.markdown("""
<div class="app-footer">
    <strong>SplitGuard AI</strong> — Autonomous Split-Settlement Reconciliation & Escrow Integrity Engine<br>
    Built for <a href="https://razorpay.com" target="_blank">Razorpay AI Buildathon 2026</a> · Compliant with RBI Nodal Directions & Section 52/194-O Statutory Withholdings<br>
    <a href="https://github.com/ParthKhandelwal537/split-settlement-leakage-detector" target="_blank">View GitHub Repository</a>
</div>
""", unsafe_allow_html=True)

conn.close()
