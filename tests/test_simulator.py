import sqlite3
import os
import pytest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.simulator import simulate_policy_shift

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()

def test_simulator_zero_delta(db_conn):
    """
    Test that 0% commission adjustment produces 0 revenue shift.
    """
    res = simulate_policy_shift(db_conn, commission_adj_pct=0.0, tds_rate=0.0075)
    assert res["total_gmv"] > 0
    assert res["platform_revenue_shift"] == 0.0
    assert res["projected_platform_commission"] == res["actual_commission_total"]

def test_simulator_positive_commission_shift(db_conn):
    """
    Test that +2% commission adjustment increases platform revenue.
    """
    res = simulate_policy_shift(db_conn, commission_adj_pct=2.0, tds_rate=0.0075)
    assert res["platform_revenue_shift"] > 0
    assert res["projected_platform_commission"] > res["actual_commission_total"]

def test_simulator_tds_variation(db_conn):
    """
    Test that higher TDS withholding rate yields proportionally higher TDS withholding.
    """
    res_low = simulate_policy_shift(db_conn, commission_adj_pct=0.0, tds_rate=0.001)
    res_high = simulate_policy_shift(db_conn, commission_adj_pct=0.0, tds_rate=0.010)
    assert res_high["projected_tds_withheld"] > res_low["projected_tds_withheld"]
