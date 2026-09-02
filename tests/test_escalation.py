import sqlite3
import os
import pytest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.classifier import classify_exceptions
from src.escalation import apply_stopping_rules_and_escalate

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")

@pytest.fixture
def test_db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()

def test_nodal_balance_always_escalated(test_db):
    """
    Verify that nodal account balance break is strictly escalated,
    never auto-cleared, and logs the batch halt.
    """
    classify_exceptions(test_db)
    counts = apply_stopping_rules_and_escalate(test_db)
    
    cursor = test_db.cursor()
    cursor.execute("SELECT status, reason FROM exceptions WHERE order_id = 'NODAL-2026-08-14'")
    row = cursor.fetchone()
    assert row is not None, "Nodal exception row must exist"
    status, reason = row
    assert status == "escalated", f"Expected status 'escalated', got '{status}'"
    
    # Check that audit log contains the halt message
    cursor.execute("SELECT detail FROM audit_log WHERE action = 'ESCALATION_HALT'")
    audit_rows = cursor.fetchall()
    assert len(audit_rows) > 0, "Audit log must record batch halt for nodal break"
    assert "2026-08-14" in audit_rows[-1][0]

def test_structural_compliance_exceptions_escalated(test_db):
    """
    Verify that any structural/compliance exception (e.g. split ineligible)
    is always escalated regardless of confidence score.
    """
    classify_exceptions(test_db)
    apply_stopping_rules_and_escalate(test_db)
    
    cursor = test_db.cursor()
    cursor.execute("SELECT status FROM exceptions WHERE exception_type = 'structural/compliance'")
    statuses = [r[0] for r in cursor.fetchall()]
    assert all(s == "escalated" for s in statuses), "All structural/compliance exceptions must be escalated"

def test_status_breakdown_consistency(test_db):
    """
    Confirm status breakdown has nonzero counts and covers all exceptions.
    """
    classify_exceptions(test_db)
    counts = apply_stopping_rules_and_escalate(test_db)
    assert counts["escalated"] > 0
    assert counts["needs-review"] > 0
    assert counts["auto-cleared"] > 0

def test_settlement_math_leakage_requires_review(test_db):
    """
    Verify real financial leakage (ORD-001 commission slab error and ORD-015 refund clawback)
    is routed to 'needs-review' rather than being silently auto-cleared.
    """
    classify_exceptions(test_db)
    apply_stopping_rules_and_escalate(test_db)
    
    cursor = test_db.cursor()
    cursor.execute("SELECT status FROM exceptions WHERE order_id = 'ORD-001'")
    assert cursor.fetchone()[0] == "needs-review"

    cursor.execute("SELECT status FROM exceptions WHERE order_id = 'ORD-015'")
    assert cursor.fetchone()[0] == "needs-review"
