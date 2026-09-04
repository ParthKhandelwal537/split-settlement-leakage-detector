"""
SplitGuard AI Deterministic Interceptor & Safety Engine
Enforces strict Pydantic validation, deterministic financial arithmetic rules,
and immutable JSONL audit logging for all Human-in-the-Loop (HITL) resolution actions.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import pydantic


class FinancialActionSchema(pydantic.BaseModel):
    action_type: str
    target_account: str
    amount: float
    invoice_id: str
    vendor_id: str

    model_config = pydantic.ConfigDict(extra="forbid")


DEFAULT_AUDIT_LOG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "audit_log.jsonl")
)


def log_audit_entry(
    event_type: str,
    details: Dict[str, Any],
    log_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Appends an immutable audit event to audit_log.jsonl with UTC ISO timestamp.
    """
    target_path = log_file or DEFAULT_AUDIT_LOG_PATH
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details,
    }

    with open(target_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def validate_and_queue_action(
    agent_proposed_json: Dict[str, Any],
    ledger_balance: float,
    log_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Guarantees zero-hallucination execution by validating JSON structure 
    and executing all mathematical checks in pure Python.
    """
    # 1. Schema Validation
    try:
        validated_action = FinancialActionSchema(**agent_proposed_json)
    except pydantic.ValidationError as e:
        result = {
            "status": "REJECTED",
            "reason": f"Schema Validation Error: {e}",
            "passed_checks": False,
        }
        log_audit_entry("INTERCEPTOR_REJECTED", {
            "proposed_payload": agent_proposed_json,
            "ledger_balance": ledger_balance,
            "reason": result["reason"]
        }, log_file=log_file)
        return result

    # 2. Deterministic Financial Rule Verification (Python Execution)
    if validated_action.amount > ledger_balance:
        result = {
            "status": "REJECTED",
            "reason": f"Insufficient Ledger Balance: Requested ${validated_action.amount}, Available ${ledger_balance}",
            "passed_checks": False,
        }
        log_audit_entry("INTERCEPTOR_REJECTED", {
            "proposed_payload": validated_action.model_dump(),
            "ledger_balance": ledger_balance,
            "reason": result["reason"]
        }, log_file=log_file)
        return result

    if validated_action.amount <= 0:
        result = {
            "status": "REJECTED",
            "reason": "Transaction amount must be greater than zero.",
            "passed_checks": False,
        }
        log_audit_entry("INTERCEPTOR_REJECTED", {
            "proposed_payload": validated_action.model_dump(),
            "ledger_balance": ledger_balance,
            "reason": result["reason"]
        }, log_file=log_file)
        return result

    # 3. Queue for Human-in-the-Loop Execution
    result = {
        "status": "QUEUED_FOR_HITL_APPROVAL",
        "payload": validated_action.model_dump(),
        "passed_checks": True,
    }
    log_audit_entry("ACTION_QUEUED_FOR_HITL", {
        "payload": validated_action.model_dump(),
        "ledger_balance": ledger_balance,
        "status": result["status"]
    }, log_file=log_file)

    return result


def record_hitl_decision(
    payload: Dict[str, Any],
    decision: str,  # "APPROVED" or "REJECTED"
    reviewer: str = "Finance Controller",
    notes: str = "",
    log_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Logs explicit user Human-In-The-Loop gate execution decision.
    """
    event_type = "HITL_ACTION_APPROVED" if decision.upper() == "APPROVED" else "HITL_ACTION_REJECTED"
    details = {
        "payload": payload,
        "decision": decision.upper(),
        "reviewer": reviewer,
        "notes": notes,
        "execution_state": "DISPATCHED" if decision.upper() == "APPROVED" else "CANCELLED"
    }
    return log_audit_entry(event_type, details, log_file=log_file)


def read_audit_log_entries(limit: int = 50, log_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Reads recent entries from audit_log.jsonl.
    """
    target_path = log_file or DEFAULT_AUDIT_LOG_PATH
    if not os.path.exists(target_path):
        return []

    entries = []
    with open(target_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries[-limit:]
