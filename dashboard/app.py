import streamlit as st
import sqlite3
import pandas as pd
import json
import os
import sys
from datetime import datetime

# Ensure project root is available in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_generator import main as run_data_generator
from src.classifier import classify_exceptions
from src.escalation import apply_stopping_rules_and_escalate
from src.report import generate_reconciliation_report
from src.audit_report import get_audit_trail

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_manifest.json")

# Set Page Config
st.set_page_config(
    page_title="Split-Settlement Leakage Detector | Razorpay Buildathon",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0c2340;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #556b82;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .status-escalated {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .status-cleared {
        background-color: #dcfce7;
        color: #166534;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .status-review {
        background-color: #fef9c3;
        color: #854d0e;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
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

# Header
col_title, col_btn = st.columns([3, 1])
with col_title:
    st.markdown('<div class="main-header">💳 Split-Settlement Leakage Detector</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Automated Reconciliation Agent for Multi-Vendor Marketplace Aggregator Settlements</div>', unsafe_allow_html=True)

with col_btn:
    st.write("")
    if st.button("🔄 Re-run Pipeline Live", type="primary", use_container_width=True):
        with st.spinner("Executing point-in-time matching, 3-bucket classification & stopping rules..."):
            execute_pipeline()
            st.toast("Pipeline executed successfully!", icon="✅")

# Database Connection
if not os.path.exists(DB_PATH):
    st.warning("Database not found. Initializing with synthetic data generator...")
    regenerate_all_data()

conn = sqlite3.connect(DB_PATH)
report_data = generate_reconciliation_report(conn)
audit_df = get_audit_trail(conn)

# Top Metrics Row
st.markdown("### 📊 Key Performance & Integrity Metrics")
m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.metric(
        label="Match Rate",
        value=f"{report_data['match_rate']}%",
        help="% of orders cleanly reconciled without exceptions"
    )

with m2:
    st.metric(
        label="Settlement Leakage",
        value=f"₹{report_data['total_settlement_leakage_inr']:,.2f}",
        delta=f"-{len(report_data['exceptions_df'][report_data['exceptions_df']['exception_type']=='settlement-math'])} items",
        delta_color="inverse",
        help="Real monetary leakage from slab mismatches and excessive refund clawbacks"
    )

with m3:
    st.metric(
        label="Escalated Exceptions",
        value=report_data['status_counts'].get('escalated', 0),
        help="Mandatory Human Ops escalation for compliance breaks / nodal breaks"
    )

with m4:
    st.metric(
        label="Needs-Review (<0.70)",
        value=report_data['status_counts'].get('needs-review', 0),
        help="Low confidence exceptions flagged for audit review"
    )

with m5:
    st.metric(
        label="Auto-Cleared Exceptions",
        value=report_data['status_counts'].get('auto-cleared', 0),
        help="Deterministic exceptions automatically cleared by point-in-time rule engine"
    )

st.divider()

# Seeded Edge Cases Section
st.markdown("### 🎯 Seeded Edge Cases Verification")
st.caption("Verifies that all 4 deliberately planted edge cases are caught by name and accurately classified.")

sc1, sc2, sc3, sc4 = st.columns(4)
columns = [sc1, sc2, sc3, sc4]

for idx, seed in enumerate(report_data["seed_verifications"]):
    with columns[idx % 4]:
        with st.container(border=True):
            if seed["verified"]:
                st.success(f"**{seed['case_name']}**")
            else:
                st.error(f"**{seed['case_name']}**")
            
            st.markdown(f"**ID:** `{seed['order_id']}`")
            st.markdown(f"**Type:** `{seed['actual_type']}`")
            st.markdown(f"**Impact:** `₹{seed['rupee_impact']:,.2f}`")
            st.markdown(f"**Status:** `{seed['status']}`")

st.divider()

# Filterable Exception Table
st.markdown("### 🔍 Exception Ledger & Triage (Ranked by ₹ Impact)")

# Fetch vendor list for filter
vendors_df = pd.read_sql_query("SELECT DISTINCT vendor_id FROM orders", conn)
vendor_list = ["All Vendors"] + sorted(vendors_df["vendor_id"].tolist())
type_list = ["All Types"] + sorted(list(report_data["type_counts"].keys()))
status_list = ["All Statuses"] + sorted(list(report_data["status_counts"].keys()))

f_col1, f_col2, f_col3 = st.columns(3)
with f_col1:
    selected_type = st.selectbox("Filter by Exception Type", type_list)
with f_col2:
    selected_status = st.selectbox("Filter by Escalation Status", status_list)
with f_col3:
    selected_vendor = st.selectbox("Filter by Vendor", vendor_list)

# Filter logic
exc_df = report_data["exceptions_df"].copy()

# Join vendor_id for orders
orders_map = pd.read_sql_query("SELECT order_id, vendor_id, category FROM orders", conn)
exc_merged = pd.merge(exc_df, orders_map, on="order_id", how="left")
exc_merged["vendor_id"] = exc_merged["vendor_id"].fillna("LEDGER")
exc_merged["category"] = exc_merged["category"].fillna("N/A")

if selected_type != "All Types":
    exc_merged = exc_merged[exc_merged["exception_type"] == selected_type]
if selected_status != "All Statuses":
    exc_merged = exc_merged[exc_merged["status"] == selected_status]
if selected_vendor != "All Vendors":
    exc_merged = exc_merged[exc_merged["vendor_id"] == selected_vendor]

# Display table
st.dataframe(
    exc_merged[[
        "exception_id", "order_id", "vendor_id", "category",
        "exception_type", "rupee_impact", "confidence_score", "status", "reason"
    ]],
    column_config={
        "rupee_impact": st.column_config.NumberColumn("Impact (₹)", format="₹%.2f"),
        "confidence_score": st.column_config.ProgressColumn("Confidence", min_value=0.0, max_value=1.0, format="%.2f"),
        "reason": st.column_config.TextColumn("Reason / Root Cause", width="large")
    },
    use_container_width=True,
    hide_index=True
)

st.divider()

# Audit Trail Viewer
st.markdown("### 📜 Real-Time Audit Trail")
st.caption("Immutable chronological record of pipeline stages, batch evaluations, and stopping rule halts.")

last_n = st.slider("Show Last N Audit Events", min_value=5, max_value=50, value=15)
recent_audit = audit_df.tail(last_n).sort_values("log_id", ascending=False)

st.dataframe(
    recent_audit[["log_id", "timestamp", "stage", "action", "detail"]],
    column_config={
        "log_id": st.column_config.NumberColumn("Event #", width="small"),
        "timestamp": st.column_config.TextColumn("Timestamp", width="medium"),
        "stage": st.column_config.TextColumn("Stage", width="small"),
        "action": st.column_config.TextColumn("Action", width="medium"),
        "detail": st.column_config.TextColumn("Detail / Audit Explanation", width="large"),
    },
    use_container_width=True,
    hide_index=True
)

conn.close()
