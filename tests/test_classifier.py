import sqlite3
import os
import pytest
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.classifier import classify_exceptions, _compute_confidence

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()

def test_classifier_three_buckets_present(db_conn):
    """
    Verify exceptions are strictly partitioned into the 3 specified domain buckets:
    settlement-math, tax-timing, and structural/compliance.
    """
    exceptions = classify_exceptions(db_conn)
    assert len(exceptions) > 0, "Exceptions must be detected"
    
    valid_buckets = {"settlement-math", "tax-timing", "structural/compliance"}
    for exc in exceptions:
        assert exc["exception_type"] in valid_buckets, (
            f"Invalid exception type '{exc['exception_type']}' for {exc['order_id']}"
        )

def test_classifier_nodal_break_detection(db_conn):
    """
    Verify nodal ledger balance integrity break on 2026-08-14 is caught as structural/compliance.
    """
    exceptions = classify_exceptions(db_conn)
    nodal_exc = next((e for e in exceptions if e["order_id"] == "NODAL-2026-08-14"), None)
    assert nodal_exc is not None, "Nodal break exception must be classified"
    assert nodal_exc["exception_type"] == "structural/compliance"
    assert nodal_exc["rupee_impact"] == 50000.0
    assert nodal_exc["confidence_score"] == 1.0

def test_classifier_tax_timing_gstr8(db_conn):
    """
    Verify ORD-028 is classified as tax-timing due to settlement preceding GSTR-8 filing.
    """
    exceptions = classify_exceptions(db_conn)
    tax_exc = next((e for e in exceptions if e["order_id"] == "ORD-028"), None)
    assert tax_exc is not None, "ORD-028 must be classified"
    assert tax_exc["exception_type"] == "tax-timing"
    assert "GSTR-8" in tax_exc["reason"]
    assert tax_exc["rupee_impact"] == 100.0

def test_classifier_settlement_math_leakage(db_conn):
    """
    Verify ORD-001 (commission slab) and ORD-015 (refund clawback) are classified as settlement-math.
    """
    exceptions = classify_exceptions(db_conn)
    ord1_exc = next((e for e in exceptions if e["order_id"] == "ORD-001"), None)
    assert ord1_exc is not None
    assert ord1_exc["exception_type"] == "settlement-math"
    assert ord1_exc["rupee_impact"] == 300.0
    
    ord15_exc = next((e for e in exceptions if e["order_id"] == "ORD-015"), None)
    assert ord15_exc is not None
    assert ord15_exc["exception_type"] == "settlement-math"
    assert ord15_exc["rupee_impact"] == 1500.0

def test_confidence_scoring_bounds():
    """
    Verify confidence scores are strictly clamped to [0.50, 1.00].
    """
    # Structural exceptions
    score_struct = _compute_confidence(100.0, 1000.0, False, True)
    assert 0.90 <= score_struct <= 1.0

    # Low relative delta without corroboration
    score_low = _compute_confidence(1.0, 10000.0, False, False)
    assert score_low >= 0.50

    # High relative delta with corroboration
    score_high = _compute_confidence(5000.0, 10000.0, True, False)
    assert score_high <= 1.0
