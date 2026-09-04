import pytest
import os
import tempfile
import json
from core.interceptor import (
    FinancialActionSchema,
    validate_and_queue_action,
    record_hitl_decision,
    read_audit_log_entries,
)


def test_valid_action_queuing():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        log_path = tf.name

    try:
        valid_payload = {
            "action_type": "DEBIT_NOTE_ISSUANCE",
            "target_account": "ACC-AGGREGATOR-ESCROW",
            "amount": 1500.0,
            "invoice_id": "ORD-001",
            "vendor_id": "VEND-001"
        }
        res = validate_and_queue_action(valid_payload, ledger_balance=5000.0, log_file=log_path)
        assert res["status"] == "QUEUED_FOR_HITL_APPROVAL"
        assert res["passed_checks"] is True
        assert res["payload"]["amount"] == 1500.0

        # Check audit log was written
        entries = read_audit_log_entries(log_file=log_path)
        assert len(entries) == 1
        assert entries[0]["event_type"] == "ACTION_QUEUED_FOR_HITL"
        assert entries[0]["details"]["payload"]["invoice_id"] == "ORD-001"
    finally:
        if os.path.exists(log_path):
            os.remove(log_path)


def test_insufficient_ledger_balance():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        log_path = tf.name

    try:
        payload = {
            "action_type": "ESCROW_DISBURSEMENT",
            "target_account": "ACC-VENDOR-PRIMARY",
            "amount": 10000.0,
            "invoice_id": "ORD-002",
            "vendor_id": "VEND-002"
        }
        res = validate_and_queue_action(payload, ledger_balance=500.0, log_file=log_path)
        assert res["status"] == "REJECTED"
        assert res["passed_checks"] is False
        assert "Insufficient Ledger Balance" in res["reason"]

        entries = read_audit_log_entries(log_file=log_path)
        assert len(entries) == 1
        assert entries[0]["event_type"] == "INTERCEPTOR_REJECTED"
    finally:
        if os.path.exists(log_path):
            os.remove(log_path)


def test_zero_or_negative_amount():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        log_path = tf.name

    try:
        payload = {
            "action_type": "REBATE_ADJUSTMENT",
            "target_account": "ACC-VENDOR-PRIMARY",
            "amount": 0.0,
            "invoice_id": "ORD-003",
            "vendor_id": "VEND-003"
        }
        res = validate_and_queue_action(payload, ledger_balance=5000.0, log_file=log_path)
        assert res["status"] == "REJECTED"
        assert "greater than zero" in res["reason"]

        payload["amount"] = -250.0
        res_neg = validate_and_queue_action(payload, ledger_balance=5000.0, log_file=log_path)
        assert res_neg["status"] == "REJECTED"
        assert "greater than zero" in res_neg["reason"]
    finally:
        if os.path.exists(log_path):
            os.remove(log_path)


def test_invalid_schema_extra_fields_or_missing_fields():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        log_path = tf.name

    try:
        # Missing vendor_id
        broken_payload = {
            "action_type": "FEE_REVERSAL",
            "target_account": "ACC-VENDOR",
            "amount": 200.0,
            "invoice_id": "ORD-004"
        }
        res = validate_and_queue_action(broken_payload, ledger_balance=1000.0, log_file=log_path)
        assert res["status"] == "REJECTED"
        assert "Schema Validation Error" in res["reason"]

        # Extra forbidden field
        broken_payload2 = {
            "action_type": "FEE_REVERSAL",
            "target_account": "ACC-VENDOR",
            "amount": 200.0,
            "invoice_id": "ORD-004",
            "vendor_id": "VEND-004",
            "hallucinated_field": "some_ai_hallucination"
        }
        res2 = validate_and_queue_action(broken_payload2, ledger_balance=1000.0, log_file=log_path)
        assert res2["status"] == "REJECTED"
        assert "Schema Validation Error" in res2["reason"]
    finally:
        if os.path.exists(log_path):
            os.remove(log_path)


def test_hitl_approval_and_rejection():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        log_path = tf.name

    try:
        payload = {
            "action_type": "DEBIT_NOTE",
            "target_account": "ACC-AGGREGATOR",
            "amount": 300.0,
            "invoice_id": "ORD-001",
            "vendor_id": "VEND-001"
        }
        # Approve
        app_entry = record_hitl_decision(
            payload, decision="APPROVED", reviewer="Lead Auditor", notes="Verified against contract", log_file=log_path
        )
        assert app_entry["event_type"] == "HITL_ACTION_APPROVED"
        assert app_entry["details"]["decision"] == "APPROVED"

        # Reject
        rej_entry = record_hitl_decision(
            payload, decision="REJECTED", reviewer="Lead Auditor", notes="Vendor dispute pending", log_file=log_path
        )
        assert rej_entry["event_type"] == "HITL_ACTION_REJECTED"
        assert rej_entry["details"]["decision"] == "REJECTED"

        entries = read_audit_log_entries(log_file=log_path)
        assert len(entries) == 2
    finally:
        if os.path.exists(log_path):
            os.remove(log_path)
