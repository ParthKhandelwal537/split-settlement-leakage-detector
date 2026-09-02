import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

def generate_debit_note(
    conn: sqlite3.Connection,
    order_id: str,
    target_entity: str = "Payment Aggregator",
    recovery_schedule: str = "Next Settlement Cycle (T+1)"
) -> Dict[str, Any]:
    """
    Generates a formal financial Debit Note for an over-deducted or miscalculated order,
    and logs the action in the immutable audit trail.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT rupee_impact, reason FROM exceptions WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"No exception record found for order '{order_id}' to generate debit note.")
    
    impact = float(row[0])
    reason = str(row[1])
    
    note_id = f"DN-{order_id}-{datetime.now().strftime('%Y%m%d%H%M')}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Record in audit log
    cursor.execute(
        "INSERT INTO audit_log (timestamp, stage, action, detail) VALUES (?, ?, ?, ?)",
        (
            timestamp,
            "Remediation",
            "DEBIT_NOTE_ISSUED",
            f"Issued Debit Note {note_id} against {target_entity} for order {order_id}. Amount: INR {impact:,.2f}. Recovery schedule: {recovery_schedule}."
        )
    )
    conn.commit()
    
    return {
        "note_id": note_id,
        "order_id": order_id,
        "amount_inr": impact,
        "target_entity": target_entity,
        "recovery_schedule": recovery_schedule,
        "issued_at": timestamp,
        "reason": reason,
        "status": "ISSUED_PENDING_SETTLEMENT_CREDIT"
    }

def schedule_gstr8_sync(
    conn: sqlite3.Connection,
    order_id: str,
    vendor_id: str,
    expected_filing_date: str
) -> Dict[str, Any]:
    """
    Schedules an automated tax clearance trigger once the vendor's GSTR-8 is confirmed filed.
    """
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute(
        "INSERT INTO audit_log (timestamp, stage, action, detail) VALUES (?, ?, ?, ?)",
        (
            timestamp,
            "Remediation",
            "GSTR8_SYNC_QUEUED",
            f"Queued Order {order_id} (Vendor {vendor_id}) for automated TCS credit release upon GSTR-8 portal filing on {expected_filing_date}."
        )
    )
    conn.commit()
    
    return {
        "order_id": order_id,
        "vendor_id": vendor_id,
        "expected_filing_date": expected_filing_date,
        "queued_at": timestamp,
        "status": "QUEUED_FOR_TAX_PORTAL_SYNC"
    }

def trigger_escrow_freeze(
    conn: sqlite3.Connection,
    date_str: str,
    deficit_amount_inr: float
) -> Dict[str, Any]:
    """
    Triggers an urgent escrow freeze notification for banking ops on a nodal balance integrity break.
    """
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute(
        "INSERT INTO audit_log (timestamp, stage, action, detail) VALUES (?, ?, ?, ?)",
        (
            timestamp,
            "Remediation",
            "ESCROW_FREEZE_DISPATCHED",
            f"CRITICAL ESCROW FREEZE ALERT: Dispatched emergency hold on Nodal Settlement Batch for {date_str} due to unexplained balance deficit of INR {deficit_amount_inr:,.2f}."
        )
    )
    conn.commit()
    
    return {
        "date": date_str,
        "deficit_amount_inr": deficit_amount_inr,
        "dispatched_at": timestamp,
        "status": "ESCROW_PAYOUT_HALTED_BANK_OPS_ALERTED"
    }

def update_dispute_status(
    conn: sqlite3.Connection,
    order_id: str,
    new_status: str,
    notes: str = ""
) -> bool:
    """
    Updates exception resolution status with human ops review notes.
    """
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("UPDATE exceptions SET status = ? WHERE order_id = ?", (new_status, order_id))
    cursor.execute(
        "INSERT INTO audit_log (timestamp, stage, action, detail) VALUES (?, ?, ?, ?)",
        (
            timestamp,
            "Human Ops",
            "STATUS_OVERRIDE",
            f"Exception for {order_id} updated to '{new_status}'. Notes: {notes or 'No operational notes provided.'}"
        )
    )
    conn.commit()
    return True
