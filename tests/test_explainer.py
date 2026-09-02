import sqlite3
import os
import pytest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.explainer import generate_plain_language_narrative, attach_narratives_to_records
from src.reconciliation_auditor import run_two_pass_reconciliation

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()

def test_explainer_structure_consistency(db_conn):
    """
    Every generated narrative must contain both a 1-sentence headline_summary
    and a structured 3-part full_narrative paragraph.
    """
    sample_records = [
        ("ORD-001", "VARIANCE", 8700.0, 9000.0, 300.0, "settlement-math", 0.72, "Commission slab mismatch"),
        ("ORD-015", "VARIANCE", 4780.0, 3280.0, -1500.0, "settlement-math", 0.85, "Refund clawback disparity"),
        ("ORD-028", "VARIANCE", 8600.0, 8700.0, 100.0, "tax-timing", 0.85, "TCS missing due to pending GSTR-8"),
        ("NODAL-2026-08-14", "VARIANCE", 799061.43, 749061.43, -50000.0, "structural/compliance", 1.0, "Nodal account balance break"),
        ("ORD-002", "MATCHED", 5430.0, 5430.0, 0.0, "clean", 1.0, "Mathematical match")
    ]
    
    for r_id, st, exp, act, delta, cat, conf, rsn in sample_records:
        narrative = generate_plain_language_narrative(
            record_id=r_id,
            status=st,
            expected_amount=exp,
            actual_amount=act,
            variance_delta=delta,
            exception_category=cat,
            confidence_score=conf,
            reason=rsn,
            conn=db_conn
        )
        assert "headline_summary" in narrative
        assert "full_narrative" in narrative
        assert len(narrative["headline_summary"]) > 10
        assert len(narrative["full_narrative"]) > 40
        # Check no raw field/variable names or code leaked
        assert "{" not in narrative["full_narrative"]
        assert "}" not in narrative["full_narrative"]
        assert "None" not in narrative["full_narrative"]
        assert "has_delta" not in narrative["full_narrative"]
        assert "payout_delta" not in narrative["full_narrative"]

def test_explainer_attachment_preserves_count(db_conn):
    """
    attach_narratives_to_records must preserve 100% of records without dropping any rows.
    """
    res = run_two_pass_reconciliation(db_conn)
    audited = res["audited_records"]
    enriched = attach_narratives_to_records(audited, db_conn)
    assert len(enriched) == len(audited)
    for r in enriched:
        assert "headline_summary" in r
        assert "full_narrative" in r
