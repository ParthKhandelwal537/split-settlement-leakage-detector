import sqlite3
import os
import pytest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.classifier import classify_exceptions
from src.escalation import apply_stopping_rules_and_escalate
from src.remediation import generate_debit_note, schedule_gstr8_sync, trigger_escrow_freeze, update_dispute_status

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    classify_exceptions(conn)
    apply_stopping_rules_and_escalate(conn)
    yield conn
    conn.close()

def test_generate_debit_note(db_conn):
    """
    Verify debit note generation records into audit_log and returns structured receipt.
    """
    res = generate_debit_note(db_conn, "ORD-001", "Razorpay Aggregator", "Next Settlement Cycle")
    assert res["note_id"].startswith("DN-ORD-001-")
    assert res["amount_inr"] > 0
    assert res["status"] == "ISSUED_PENDING_SETTLEMENT_CREDIT"
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT action FROM audit_log WHERE action = 'DEBIT_NOTE_ISSUED'")
    assert cursor.fetchone() is not None

def test_schedule_gstr8_sync(db_conn):
    """
    Verify GSTR-8 tax portal sync scheduler logs action.
    """
    res = schedule_gstr8_sync(db_conn, "ORD-028", "VEND-004", "2026-08-20")
    assert res["status"] == "QUEUED_FOR_TAX_PORTAL_SYNC"
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT action FROM audit_log WHERE action = 'GSTR8_SYNC_QUEUED'")
    assert cursor.fetchone() is not None

def test_trigger_escrow_freeze(db_conn):
    """
    Verify escrow freeze trigger logs emergency halt.
    """
    res = trigger_escrow_freeze(db_conn, "2026-08-14", 50000.0)
    assert res["status"] == "ESCROW_PAYOUT_HALTED_BANK_OPS_ALERTED"
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT action FROM audit_log WHERE action = 'ESCROW_FREEZE_DISPATCHED'")
    assert cursor.fetchone() is not None

def test_update_dispute_status(db_conn):
    """
    Verify manual dispute status override updates exceptions table and records human ops note.
    """
    update_dispute_status(db_conn, "ORD-001", "needs-review", "Under review with vendor finance team")
    cursor = db_conn.cursor()
    cursor.execute("SELECT status FROM exceptions WHERE order_id = 'ORD-001'")
    assert cursor.fetchone()[0] == "needs-review"
