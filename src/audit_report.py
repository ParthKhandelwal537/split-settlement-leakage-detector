import sqlite3
import os
import sys
import pandas as pd

def get_audit_trail(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Reads the full chronological audit trail from the audit_log table.
    """
    return pd.read_sql_query("SELECT log_id, timestamp, stage, action, detail FROM audit_log ORDER BY log_id ASC", conn)

def print_audit_report(conn: sqlite3.Connection):
    """
    Prints a clean, formatted chronological summary of the entire reconciliation pipeline execution.
    """
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
            
    df = get_audit_trail(conn)
    print("\n=========================================================================================")
    print("                    SPLIT-SETTLEMENT RECONCILIATION AUDIT TRAIL                          ")
    print("=========================================================================================")
    if df.empty:
        print("No audit log entries recorded.")
    else:
        for _, row in df.iterrows():
            print(f"[{row['log_id']:02d}] {row['timestamp']} | {row['stage']:<10} | {row['action']:<25}")
            print(f"     Detail: {row['detail']}\n")
    print("=========================================================================================\n")

def main():
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")
    conn = sqlite3.connect(db_path)
    try:
        print_audit_report(conn)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
