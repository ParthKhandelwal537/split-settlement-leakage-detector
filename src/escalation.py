import sqlite3
import os
import sys
from datetime import datetime
from typing import Dict

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def get_halted_nodal_dates(conn: sqlite3.Connection):
    """
    Returns list of dates (YYYY-MM-DD) with nodal account ledger balance breaks.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date FROM nodal_account_ledger
        WHERE abs(closing_balance - (opening_balance + collected - settled)) > 0.01
    """)
    return [r[0] for r in cursor.fetchall()]

def apply_stopping_rules_and_escalate(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Applies strict, explicit stopping and escalation rules to all exceptions:
    1. If exception_type == 'structural/compliance' or nodal break -> status = 'escalated' (always)
    2. If order settled on a date with a nodal break -> status = 'escalated' (HALT further automated action)
    3. If confidence_score < 0.7 -> status = 'needs-review' (never auto-resolved)
    4. If exception_type == 'settlement-math' (real leakage!) -> status = 'needs-review' (requires human ops / debit note recovery)
    5. If exception_type == 'tax-timing' (non-leakage GSTR-8 timing lag, conf >= 0.7) -> status = 'auto-cleared'
    
    Updates exceptions table in place and returns status breakdown counts.
    """
    cursor = conn.cursor()
    halted_dates = set(get_halted_nodal_dates(conn))
    
    # Query settlement dates for orders to enforce batch halting
    order_settlement_dates = {}
    cursor.execute("SELECT order_id, settlement_date FROM settlements")
    for oid, s_date in cursor.fetchall():
        order_settlement_dates[oid] = s_date
        
    cursor.execute("SELECT exception_id, order_id, exception_type, confidence_score, reason FROM exceptions")
    rows = cursor.fetchall()
    
    status_counts = {"escalated": 0, "needs-review": 0, "auto-cleared": 0}
    updates = []
    
    for exc_id, order_id, exc_type, conf, reason in rows:
        is_nodal_break = (order_id and str(order_id).startswith("NODAL-")) or "nodal" in exc_type.lower()
        order_settled_on_halted_date = order_settlement_dates.get(order_id) in halted_dates
        
        # Rule 1: Structural/compliance, Nodal Break, or batch settled on a broken nodal date is ALWAYS escalated
        if exc_type == "structural/compliance" or is_nodal_break or order_settled_on_halted_date:
            new_status = "escalated"
            if is_nodal_break:
                break_date = order_id.replace("NODAL-", "") if order_id and "NODAL-" in order_id else "UNKNOWN"
                cursor.execute(
                    "INSERT INTO audit_log (timestamp, stage, action, detail) VALUES (?, ?, ?, ?)",
                    (
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Stage 4",
                        "ESCALATION_HALT",
                        f"CRITICAL STOPPING RULE TRIGGERED: Nodal account balance integrity break detected on {break_date}. Automated processing HALTED for this date batch. All associated orders locked from auto-clearing."
                    )
                )
        # Rule 2: Low confidence (< 0.70) must never auto-resolve
        elif conf < 0.7:
            new_status = "needs-review"
        # Rule 3: Real financial loss (settlement-math) cannot be silently auto-cleared; requires human ops / debit note
        elif exc_type == "settlement-math":
            new_status = "needs-review"
        # Rule 4: Harmless tax-timing differences (confidence >= 0.70) safely queued for GSTR-8 portal auto-sync
        else:
            new_status = "auto-cleared"
            
        status_counts[new_status] = status_counts.get(new_status, 0) + 1
        updates.append((new_status, exc_id))
        
    cursor.executemany("UPDATE exceptions SET status = ? WHERE exception_id = ?", updates)
    
    # Audit log entry for escalation summary
    cursor.execute(
        "INSERT INTO audit_log (timestamp, stage, action, detail) VALUES (?, ?, ?, ?)",
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Stage 4",
            "STOPPING_RULES_EVALUATED",
            f"Evaluated stopping rules across {len(rows)} exceptions. Escalated: {status_counts['escalated']}, Needs-Review: {status_counts['needs-review']}, Auto-Cleared: {status_counts['auto-cleared']}."
        )
    )
    
    conn.commit()
    return status_counts

def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
            
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")
    conn = sqlite3.connect(db_path)
    try:
        counts = apply_stopping_rules_and_escalate(conn)
        print("\n=======================================================")
        print("          ESCALATION & STOPPING RULES SUMMARY          ")
        print("=======================================================")
        print(f"Escalated (Mandatory Ops Intervention): {counts.get('escalated', 0)}")
        print(f"Needs-Review (Low Confidence < 0.70):   {counts.get('needs-review', 0)}")
        print(f"Auto-Cleared (Deterministic Rules):     {counts.get('auto-cleared', 0)}")
        print("=======================================================\n")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
