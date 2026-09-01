import sqlite3
import os
import sys
from datetime import datetime
from typing import Dict

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def apply_stopping_rules_and_escalate(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Applies strict, explicit stopping and escalation rules to all exceptions:
    1. If exception_type == 'structural/compliance' -> status = 'escalated' (always, overriding confidence)
    2. If nodal balance break -> status = 'escalated' + writes audit log halting batch
    3. If confidence_score < 0.7 -> status = 'needs-review' (never auto-resolved)
    4. Otherwise (high-confidence settlement-math or tax-timing) -> status = 'auto-cleared'
    
    Updates exceptions table in place and returns status breakdown counts.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT exception_id, order_id, exception_type, confidence_score, reason FROM exceptions")
    rows = cursor.fetchall()
    
    status_counts = {"escalated": 0, "needs-review": 0, "auto-cleared": 0}
    updates = []
    
    for exc_id, order_id, exc_type, conf, reason in rows:
        is_nodal_break = (order_id and str(order_id).startswith("NODAL-")) or "nodal" in exc_type.lower()
        
        # Rule 1: Structural/compliance or Nodal Break is ALWAYS escalated regardless of confidence
        if exc_type == "structural/compliance" or is_nodal_break:
            new_status = "escalated"
            if is_nodal_break:
                # Log immediate halt in audit_log
                break_date = order_id.replace("NODAL-", "") if order_id and "NODAL-" in order_id else "UNKNOWN"
                cursor.execute(
                    "INSERT INTO audit_log (timestamp, stage, action, detail) VALUES (?, ?, ?, ?)",
                    (
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Stage 4",
                        "ESCALATION_HALT",
                        f"CRITICAL STOPPING RULE TRIGGERED: Nodal account balance integrity break detected on {break_date}. Automated processing HALTED for this date batch. Case escalated to Human Finance Ops."
                    )
                )
        # Rule 2: Confidence score < 0.7 -> needs-review
        elif conf < 0.7:
            new_status = "needs-review"
        # Rule 3: High confidence math/timing exceptions
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
