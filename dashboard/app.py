import streamlit as st
import sqlite3
import pandas as pd
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

# Page Config
st.set_page_config(
    page_title="SplitSettlement AI | Autonomous Leakage Detector",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-End Modern Fintech Theme & Glassmorphic CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    * {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    code, pre, .mono {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3rem;
        max-width: 95% !important;
    }

    /* App Header Banner */
    .hero-banner {
        background: linear-gradient(135deg, #0c1a30 0%, #0f274a 50%, #0284c7 100%);
        border-radius: 18px;
        padding: 28px 36px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px -10px rgba(2, 132, 199, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.12);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
    }
    
    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin: 0;
        background: linear-gradient(180deg, #FFFFFF 0%, #E2E8F0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .hero-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-top: 6px;
        font-weight: 500;
        max-width: 650px;
        line-height: 1.5;
    }

    .badge-agent {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.4);
        color: #34d399;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 20px;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    .pulse-dot {
        width: 8px;
        height: 8px;
        background: #10b981;
        border-radius: 50%;
        box-shadow: 0 0 10px #10b981;
    }

    /* Metric Cards Glassmorphism */
    .stat-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        position: relative;
        overflow: hidden;
    }
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.06);
    }
    .stat-label {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #64748b;
        margin-bottom: 4px;
    }
    .stat-value {
        font-size: 1.85rem;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.02em;
    }
    .stat-sub {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-top: 4px;
        font-weight: 500;
    }
    
    /* Seed Cards */
    .seed-card {
        background: #ffffff;
        border-radius: 14px;
        border: 1px solid #e2e8f0;
        padding: 18px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .seed-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 10px;
    }
    .seed-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #1e293b;
        line-height: 1.3;
    }
    .seed-badge-pass {
        background: #ecfdf5;
        color: #059669;
        border: 1px solid #a7f3d0;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.72rem;
        font-weight: 700;
    }
    .seed-body {
        font-size: 0.82rem;
        color: #475569;
        line-height: 1.45;
        margin-bottom: 12px;
    }
    .seed-meta {
        background: #f8fafc;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 0.76rem;
        color: #334155;
        border: 1px solid #f1f5f9;
    }

    /* Section Titles */
    .section-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: #0f172a;
        margin: 28px 0 14px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Deployment & Agent Info Box */
    .info-callout {
        background: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 12px;
        padding: 14px 18px;
        color: #0369a1;
        font-size: 0.85rem;
        line-height: 1.5;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

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

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.image("https://images.seeklogo.com/logo-png/43/2/razorpay-logo-png_seeklogo-434057.png", width=160)
    st.markdown("### 🤖 Agentic Engine Controller")
    st.markdown("""
    **Autonomous Loop Mode:** `ACTIVE`
    
    This agent continuously intercepts split settlements, reconstructs point-in-time rates, detects mathematical/timing anomalies, and triggers stopping rules.
    """)
    
    st.divider()
    
    st.markdown("#### ⚙️ Simulation Actions")
    if st.button("⚡ Run Autonomous Cycle", type="primary", use_container_width=True):
        with st.spinner("Agent evaluating batch against point-in-time engine..."):
            time.sleep(0.3)
            execute_pipeline()
            st.toast("Reconciliation cycle finished!", icon="✅")
            st.rerun()

    if st.button("🎲 Reset & Re-Seed Batch (60 Orders)", use_container_width=True):
        with st.spinner("Generating fresh synthetic batch & injecting 4 edge cases..."):
            regenerate_all_data()
            st.toast("Fresh synthetic batch seeded!", icon="🌱")
            st.rerun()

    st.divider()
    st.markdown("#### 🌐 Runtime & Deployment Status")
    st.markdown("""
    - **Execution Environment:** `Local Host / Edge Node`
    - **Port:** `8501` (Active)
    - **DB State:** `reconciliation.db (SQLite ACID)`
    - **Stopping Rules Engine:** `Enabled`
    - **Deployment Target:** Can be pushed to *Streamlit Community Cloud*, *AWS ECS*, or *Railway* in 1-click via GitHub.
    """)

# ----------------- MAIN HEADER BANNER -----------------
st.markdown("""
<div class="hero-banner">
    <div>
        <div class="hero-title">
            <span>⚡ Split-Settlement Leakage Detector</span>
        </div>
        <div class="hero-subtitle">
            Autonomous multi-vendor marketplace reconciliation agent. Unveils hidden slab mismatches, over-clawed refunds, and nodal integrity breaks before payouts clear.
        </div>
    </div>
    <div>
        <span class="badge-agent"><div class="pulse-dot"></div> AGENT LIVE & MONITORING</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Fetch Data
conn = sqlite3.connect(DB_PATH)
report_data = generate_reconciliation_report(conn)
audit_df = get_audit_trail(conn)

# ----------------- TOP INTEGRITY METRICS -----------------
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.markdown(f"""
    <div class="stat-card" style="border-left: 4px solid #3b82f6;">
        <div class="stat-label">Reconciliation Match</div>
        <div class="stat-value" style="color: #2563eb;">{report_data['match_rate']}%</div>
        <div class="stat-sub">{report_data['clean_orders']}/{report_data['total_orders']} clean orders</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="stat-card" style="border-left: 4px solid #ef4444;">
        <div class="stat-label">Settlement Leakage</div>
        <div class="stat-value" style="color: #dc2626;">₹{report_data['total_settlement_leakage_inr']:,.0f}</div>
        <div class="stat-sub">Real financial loss found</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="stat-card" style="border-left: 4px solid #f59e0b;">
        <div class="stat-label">Structural Exposure</div>
        <div class="stat-value" style="color: #d97706;">₹{report_data['total_structural_exposure_inr']:,.0f}</div>
        <div class="stat-sub">Nodal deficit & split blocks</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="stat-card" style="border-left: 4px solid #8b5cf6;">
        <div class="stat-label">Compliant Escalated</div>
        <div class="stat-value" style="color: #7c3aed;">{report_data['status_counts'].get('escalated', 0)}</div>
        <div class="stat-sub">Halted for Human Ops</div>
    </div>
    """, unsafe_allow_html=True)

with c5:
    st.markdown(f"""
    <div class="stat-card" style="border-left: 4px solid #10b981;">
        <div class="stat-label">Self-Skepticism Index</div>
        <div class="stat-value" style="color: #059669;">{report_data['tax_timing_pct']}%</div>
        <div class="stat-sub">Filtered non-leakage (GSTR-8)</div>
    </div>
    """, unsafe_allow_html=True)

# ----------------- SEEDED EDGE CASES VERIFICATION -----------------
st.markdown('<div class="section-header">🎯 Seeded Edge Cases Ground Truth Verification</div>', unsafe_allow_html=True)
st.caption("Verifies that the agent deterministically identifies all 4 planted test vectors without hardcoded heuristics.")

sc1, sc2, sc3, sc4 = st.columns(4)
cols = [sc1, sc2, sc3, sc4]

for i, seed in enumerate(report_data["seed_verifications"]):
    with cols[i % 4]:
        status_color = "#10b981" if seed["verified"] else "#ef4444"
        badge_text = "VERIFIED MATCH" if seed["verified"] else "DISCREPANCY"
        
        st.markdown(f"""
        <div class="seed-card">
            <div>
                <div class="seed-header">
                    <span class="seed-title">{seed['case_name']}</span>
                    <span class="seed-badge-pass">{badge_text}</span>
                </div>
                <div class="seed-body">
                    <strong>ID:</strong> <code class="mono">{seed['order_id']}</code><br>
                    <strong>Bucket:</strong> <span style="font-weight:600; color:#0369a1;">{seed['actual_type']}</span><br>
                    <strong>Financial Impact:</strong> <span style="font-weight:700; color:#0f172a;">₹{seed['rupee_impact']:,.2f}</span>
                </div>
            </div>
            <div class="seed-meta">
                <strong>Resolution Action:</strong> <code class="mono">{seed['status'].upper()}</code>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ----------------- EXCEPTION LEDGER TABBED -----------------
st.markdown('<div class="section-header">🔍 Interactive Triage & Exceptions Ledger</div>', unsafe_allow_html=True)

# Filters Row
f1, f2, f3 = st.columns(3)
vendors_df = pd.read_sql_query("SELECT DISTINCT vendor_id FROM orders", conn)
vendor_list = ["All Vendors"] + sorted(vendors_df["vendor_id"].tolist())
type_list = ["All Types"] + sorted(list(report_data["type_counts"].keys()))
status_list = ["All Statuses"] + sorted(list(report_data["status_counts"].keys()))

with f1:
    selected_type = st.selectbox("Classification Bucket", type_list)
with f2:
    selected_status = st.selectbox("Stopping Rule Status", status_list)
with f3:
    selected_vendor = st.selectbox("Vendor ID", vendor_list)

# Filter Data
exc_df = report_data["exceptions_df"].copy()
orders_map = pd.read_sql_query("SELECT order_id, vendor_id, category, gross_amount FROM orders", conn)
exc_merged = pd.merge(exc_df, orders_map, on="order_id", how="left")
exc_merged["vendor_id"] = exc_merged["vendor_id"].fillna("LEDGER-BREAK")
exc_merged["category"] = exc_merged["category"].fillna("Nodal Ledger")

if selected_type != "All Types":
    exc_merged = exc_merged[exc_merged["exception_type"] == selected_type]
if selected_status != "All Statuses":
    exc_merged = exc_merged[exc_merged["status"] == selected_status]
if selected_vendor != "All Vendors":
    exc_merged = exc_merged[exc_merged["vendor_id"] == selected_vendor]

# Display Styled Dataframe
st.dataframe(
    exc_merged[[
        "exception_id", "order_id", "vendor_id", "category",
        "exception_type", "rupee_impact", "confidence_score", "status", "reason"
    ]],
    column_config={
        "exception_id": st.column_config.TextColumn("Exception Ref", width="small"),
        "order_id": st.column_config.TextColumn("Target ID", width="small"),
        "vendor_id": st.column_config.TextColumn("Vendor", width="small"),
        "category": st.column_config.TextColumn("Category", width="small"),
        "exception_type": st.column_config.TextColumn("Bucket", width="medium"),
        "rupee_impact": st.column_config.NumberColumn("Impact (₹)", format="₹%.2f"),
        "confidence_score": st.column_config.ProgressColumn("Confidence", min_value=0.0, max_value=1.0, format="%.2f"),
        "status": st.column_config.TextColumn("Status", width="small"),
        "reason": st.column_config.TextColumn("Agent Root Cause Explanation", width="large")
    },
    use_container_width=True,
    hide_index=True
)

# ----------------- AUDIT LOG STREAM -----------------
st.markdown('<div class="section-header">📜 Chronological Agent Audit Trail</div>', unsafe_allow_html=True)
st.caption("Immutable stage execution log for regulatory compliance and finance-ops explainability.")

col_audit_ctrl, col_audit_table = st.columns([1, 4])
with col_audit_ctrl:
    last_n = st.slider("Display depth", min_value=5, max_value=50, value=12)
    st.info("Every point-in-time calculation and batch halt is permanently persisted.")

with col_audit_table:
    recent_audit = audit_df.tail(last_n).sort_values("log_id", ascending=False)
    st.dataframe(
        recent_audit[["log_id", "timestamp", "stage", "action", "detail"]],
        column_config={
            "log_id": st.column_config.NumberColumn("#", width="small"),
            "timestamp": st.column_config.TextColumn("Timestamp", width="medium"),
            "stage": st.column_config.TextColumn("Stage", width="small"),
            "action": st.column_config.TextColumn("Action", width="medium"),
            "detail": st.column_config.TextColumn("Audit Event Detail", width="large"),
        },
        use_container_width=True,
        hide_index=True
    )

conn.close()
