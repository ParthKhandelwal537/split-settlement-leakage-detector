import sqlite3
import os
import pytest
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.reconciliation_auditor import run_two_pass_reconciliation, run_pass1_propose_matches, run_pass2_independent_audit

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()

def test_two_pass_integrity_total_records_in_equals_out(db_conn):
    """
    CRITICAL CONSTRAINT: Total record count in MUST equal total record count out.
    Zero records dropped, zero records summarized away.
    """
    result = run_two_pass_reconciliation(db_conn)
    assert result["total_records_in"] == result["total_records_out"]
    assert result["total_records_in"] == 60
    assert len(result["audited_records"]) == 60

def test_two_pass_strict_output_schema(db_conn):
    """
    Every record must strictly adhere to the defined 8-field schema:
    [record_id, expected_amount, actual_amount, status, variance_delta, confidence_score, exception_category, reason]
    """
    result = run_two_pass_reconciliation(db_conn)
    required_fields = [
        "record_id", "expected_amount", "actual_amount", "status",
        "variance_delta", "confidence_score", "exception_category", "reason"
    ]
    for r in result["audited_records"]:
        for field in required_fields:
            assert field in r, f"Field '{field}' missing from audited record {r.get('record_id')}"
        assert r["status"] in {"MATCHED", "VARIANCE", "UNRESOLVED"}

def test_two_pass_catches_all_seeded_cases(db_conn):
    """
    Confirm all 4 seeded edge cases are strictly caught under the two-pass architecture.
    """
    result = run_two_pass_reconciliation(db_conn)
    exceptions_by_id = {e["record_id"]: e for e in result["all_exceptions"]}
    
    # 1. Retroactive slab change
    assert "ORD-001" in exceptions_by_id
    assert exceptions_by_id["ORD-001"]["status"] == "VARIANCE"
    assert exceptions_by_id["ORD-001"]["exception_category"] == "settlement-math"
    assert abs(exceptions_by_id["ORD-001"]["variance_delta"]) == 300.0

    # 2. Partial refund clawback
    assert "ORD-015" in exceptions_by_id
    assert exceptions_by_id["ORD-015"]["status"] == "VARIANCE"
    assert exceptions_by_id["ORD-015"]["exception_category"] == "settlement-math"
    assert abs(exceptions_by_id["ORD-015"]["variance_delta"]) == 1500.0

    # 3. TCS timing
    assert "ORD-028" in exceptions_by_id
    assert exceptions_by_id["ORD-028"]["status"] == "VARIANCE"
    assert exceptions_by_id["ORD-028"]["exception_category"] == "tax-timing"

    # 4. Nodal balance break
    assert "NODAL-2026-08-14" in exceptions_by_id
    assert exceptions_by_id["NODAL-2026-08-14"]["status"] == "VARIANCE"
    assert exceptions_by_id["NODAL-2026-08-14"]["exception_category"] == "structural/compliance"

def test_pass2_veto_power(db_conn):
    """
    Simulate Pass 1 proposing a false MATCHED status for an order with a variance,
    and verify Pass 2 vetoes it unconditionally.
    """
    proposals = [
        {
            "record_id": "ORD-TEST-CORRUPT",
            "vendor_id": "VEND-001",
            "order_date": "2026-07-25",
            "settlement_date": "2026-08-02",
            "gross_amount": 10000.0,
            "expected_amount": 8700.0,
            "actual_amount": 9000.0,  # ₹300 mismatch
            "proposed_status": "MATCHED",  # Compromised or hallucinatory Pass 1
            "variance_delta": 300.0,
            "category": "clean",
            "reason": "Pass 1 erroneously claimed a match.",
            "is_split_eligible": 1,
            "comm_delta": 300.0,
            "tcs_delta": 0.0,
            "tds_delta": 0.0,
            "refund_amount": 0.0
        }
    ]
    audited = run_pass2_independent_audit(db_conn, proposals)
    assert len(audited) == 1
    # Pass 2 MUST VETO and downgrade to VARIANCE
    assert audited[0]["status"] == "VARIANCE"
    assert audited[0]["exception_category"] == "settlement-math"
