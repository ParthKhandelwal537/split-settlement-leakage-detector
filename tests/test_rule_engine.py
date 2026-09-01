import sqlite3
import os
import pytest
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rule_engine import get_applicable_rate

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()

def test_retroactive_commission_slab_change(db_conn):
    """
    Test that for VEND-001:
    - Before change (<= 2026-07-31): Commission is 10% (0.10)
    - On/After change (>= 2026-08-01): Commission is 7% (0.07)
    """
    rate_july = get_applicable_rate(db_conn, "VEND-001", "2026-07-25", "commission")
    assert rate_july == 0.10, f"Expected 0.10 for July order date, got {rate_july}"
    
    rate_july_end = get_applicable_rate(db_conn, "VEND-001", "2026-07-31", "commission")
    assert rate_july_end == 0.10, f"Expected 0.10 for July 31, got {rate_july_end}"
    
    rate_aug_start = get_applicable_rate(db_conn, "VEND-001", "2026-08-01", "commission")
    assert rate_aug_start == 0.07, f"Expected 0.07 for Aug 1, got {rate_aug_start}"
    
    rate_aug_later = get_applicable_rate(db_conn, "VEND-001", "2026-08-15", "commission")
    assert rate_aug_later == 0.07, f"Expected 0.07 for Aug 15, got {rate_aug_later}"

def test_tax_rate_transition(db_conn):
    """
    Test that for TDS tax rule transition:
    - In July (<= 2026-07-31): TDS is 1% (0.010)
    - In August (>= 2026-08-01): TDS is 0.75% (0.0075)
    """
    tds_july = get_applicable_rate(db_conn, None, "2026-07-15", "TDS")
    assert tds_july == 0.010, f"Expected 0.010 for July TDS, got {tds_july}"

    tds_aug = get_applicable_rate(db_conn, None, "2026-08-10", "TDS")
    assert tds_aug == 0.0075, f"Expected 0.0075 for August TDS, got {tds_aug}"

def test_tcs_rule_consistency(db_conn):
    """
    Test TCS remains 1% across all dates.
    """
    tcs_july = get_applicable_rate(db_conn, None, "2026-07-10", "TCS")
    tcs_aug = get_applicable_rate(db_conn, None, "2026-08-20", "TCS")
    assert tcs_july == 0.010
    assert tcs_aug == 0.010

def test_other_vendors(db_conn):
    """
    Test standard static commission slabs for other vendors.
    """
    v2_rate = get_applicable_rate(db_conn, "VEND-002", "2026-08-10", "commission")
    assert v2_rate == 0.08
    v3_rate = get_applicable_rate(db_conn, "VEND-003", "2026-07-15", "commission")
    assert v3_rate == 0.12
