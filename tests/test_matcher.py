import sqlite3
import os
import pytest
import sys
import pandas as pd

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.matcher import run_matcher

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()

def test_matcher_dataframe_structure(db_conn):
    """
    Verify matcher outputs complete DataFrame with all required financial delta fields.
    """
    df = run_matcher(db_conn)
    assert not df.empty, "Matcher must return processed orders"
    
    expected_columns = [
        "order_id", "vendor_id", "order_date", "settlement_date", "gross_amount",
        "is_split_eligible", "comm_rate", "expected_comm", "actual_comm", "comm_delta",
        "expected_tcs", "actual_tcs", "tcs_delta", "expected_tds", "actual_tds",
        "tds_delta", "expected_logistics", "actual_logistics", "refund_amount",
        "expected_payout", "actual_payout", "payout_delta", "has_delta"
    ]
    for col in expected_columns:
        assert col in df.columns, f"Missing required column '{col}' in matcher output"

def test_matcher_expected_payout_calculation(db_conn):
    """
    Verify expected net payout math: gross - (comm + tcs + tds + logistics + refund)
    """
    df = run_matcher(db_conn)
    for _, row in df.iterrows():
        calc_expected = round(
            row["gross_amount"] - (
                row["expected_comm"] + 
                row["expected_tcs"] + 
                row["expected_tds"] + 
                row["expected_logistics"] + 
                row["refund_amount"]
            ), 
            2
        )
        assert abs(row["expected_payout"] - calc_expected) < 0.01, (
            f"Expected payout math error for {row['order_id']}: {row['expected_payout']} vs {calc_expected}"
        )

def test_matcher_catches_retroactive_commission_leakage(db_conn):
    """
    Verify matcher catches ₹300 commission variance on ORD-001.
    """
    df = run_matcher(db_conn)
    row = df[df["order_id"] == "ORD-001"].iloc[0]
    # In July, comm_rate = 10% on ₹10,000 = ₹1,000 expected
    # Aggregator deducted August 7% = ₹700 actual
    assert row["expected_comm"] == 1000.0
    assert row["actual_comm"] == 700.0
    assert row["comm_delta"] == -300.0
    assert row["has_delta"] == True

def test_matcher_catches_refund_clawback_variance(db_conn):
    """
    Verify matcher catches ₹1,500 over-clawback on ORD-015.
    """
    df = run_matcher(db_conn)
    row = df[df["order_id"] == "ORD-015"].iloc[0]
    assert row["refund_amount"] == 2000.0
    # Expected payout was ₹4,780, actual payout was ₹3,280 (delta = -1500.0)
    assert row["payout_delta"] == -1500.0
    assert row["has_delta"] == True

def test_matcher_handles_empty_orders_gracefully():
    """
    Verify matcher returns empty dataframe without crashing if orders table is empty.
    """
    mem_conn = sqlite3.connect(":memory:")
    cur = mem_conn.cursor()
    cur.execute("""
        CREATE TABLE orders (order_id TEXT, vendor_id TEXT, order_date TEXT, gross_amount REAL, category TEXT, is_split_eligible INT);
    """)
    cur.execute("""
        CREATE TABLE settlements (settlement_id TEXT, order_id TEXT, settlement_date TEXT, amount REAL, commission_deducted REAL, tcs_deducted REAL, tds_deducted REAL, logistics_deducted REAL);
    """)
    cur.execute("""
        CREATE TABLE refunds (refund_id TEXT, order_id TEXT, vendor_id TEXT, refund_amount REAL, refund_date TEXT);
    """)
    cur.execute("""
        CREATE TABLE audit_log (log_id INTEGER PRIMARY KEY, timestamp TEXT, stage TEXT, action TEXT, detail TEXT);
    """)
    mem_conn.commit()
    
    empty_df = run_matcher(mem_conn)
    assert empty_df.empty
    assert "has_delta" in empty_df.columns
    mem_conn.close()
