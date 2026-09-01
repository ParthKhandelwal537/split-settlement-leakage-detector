import sqlite3
import os
import json
import sys
import pandas as pd
from typing import Dict, Any

def generate_reconciliation_report(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Generates structured summary metrics and detailed exception reports.
    """
    cursor = conn.cursor()
    
    # 1. Total Orders & Match Rate
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    
    # Count orders with at least one exception
    cursor.execute("SELECT COUNT(DISTINCT order_id) FROM exceptions WHERE order_id NOT LIKE 'NODAL-%'")
    orders_with_exceptions = cursor.fetchone()[0]
    clean_orders = max(0, total_orders - orders_with_exceptions)
    match_rate = (clean_orders / total_orders * 100.0) if total_orders > 0 else 0.0
    
    # 2. Exceptions ranked by rupee_impact descending
    exceptions_df = pd.read_sql_query(
        "SELECT exception_id, order_id, exception_type, reason, confidence_score, status, rupee_impact, created_at "
        "FROM exceptions ORDER BY rupee_impact DESC", 
        conn
    )
    
    # 3. Counts by Type & Status
    type_counts = exceptions_df["exception_type"].value_counts().to_dict()
    status_counts = exceptions_df["status"].value_counts().to_dict()
    
    total_leakage_inr = exceptions_df[exceptions_df["exception_type"] == "settlement-math"]["rupee_impact"].sum()
    total_structural_inr = exceptions_df[exceptions_df["exception_type"] == "structural/compliance"]["rupee_impact"].sum()
    total_timing_inr = exceptions_df[exceptions_df["exception_type"] == "tax-timing"]["rupee_impact"].sum()
    
    # Self-skepticism metric: proportion of exceptions that are harmless tax-timing
    tax_timing_count = type_counts.get("tax-timing", 0)
    total_exceptions_count = len(exceptions_df)
    tax_timing_pct = (tax_timing_count / total_exceptions_count * 100.0) if total_exceptions_count > 0 else 0.0
    
    # 4. Verification against Seed Manifest
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "data", "seed_manifest.json")
    seed_verifications = []
    
    expected_type_map = {
        "ORD-001": "settlement-math",
        "ORD-015": "settlement-math",
        "ORD-028": "tax-timing",
        "NODAL-2026-08-14": "structural/compliance"
    }
    
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
            
        for seed in manifest_data:
            oid = seed["order_id"]
            expected_type = expected_type_map.get(oid, "unknown")
            matching_exc = exceptions_df[exceptions_df["order_id"] == oid]
            
            if not matching_exc.empty:
                actual_type = matching_exc.iloc[0]["exception_type"]
                passed = (actual_type == expected_type)
                seed_verifications.append({
                    "order_id": oid,
                    "case_name": seed["case_name"],
                    "expected_type": expected_type,
                    "actual_type": actual_type,
                    "rupee_impact": float(matching_exc.iloc[0]["rupee_impact"]),
                    "status": matching_exc.iloc[0]["status"],
                    "verified": passed
                })
            else:
                seed_verifications.append({
                    "order_id": oid,
                    "case_name": seed["case_name"],
                    "expected_type": expected_type,
                    "actual_type": "MISSING",
                    "rupee_impact": 0.0,
                    "status": "NOT_FOUND",
                    "verified": False
                })

    return {
        "total_orders": total_orders,
        "clean_orders": clean_orders,
        "match_rate": round(match_rate, 2),
        "total_exceptions": total_exceptions_count,
        "total_settlement_leakage_inr": round(total_leakage_inr, 2),
        "total_structural_exposure_inr": round(total_structural_inr, 2),
        "tax_timing_pct": round(tax_timing_pct, 2),
        "type_counts": type_counts,
        "status_counts": status_counts,
        "exceptions_df": exceptions_df,
        "seed_verifications": seed_verifications
    }

def print_full_report(conn: sqlite3.Connection):
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
            
    rep = generate_reconciliation_report(conn)
    
    print("\n=========================================================================================")
    print("                 SPLIT-SETTLEMENT LEAKAGE DETECTOR: RECONCILIATION REPORT                ")
    print("=========================================================================================")
    print(f"Total Orders Evaluated:       {rep['total_orders']}")
    print(f"Clean Reconciled Orders:      {rep['clean_orders']}")
    print(f"Reconciliation Match Rate:    {rep['match_rate']}%\n")
    
    print(f"Total Real Settlement Leakage: INR {rep['total_settlement_leakage_inr']:,.2f}")
    print(f"Total Structural Exposure:     INR {rep['total_structural_exposure_inr']:,.2f}")
    print(f"Self-Skepticism Index:         {rep['tax_timing_pct']}% of exceptions are timing lags (GSTR-8), not true leakage.\n")
    
    print("--- Exceptions Breakdown by Type ---")
    for k, v in rep["type_counts"].items():
        print(f"  • {k:<25}: {v}")
        
    print("\n--- Exceptions Breakdown by Escalation Status ---")
    for k, v in rep["status_counts"].items():
        print(f"  • {k:<25}: {v}")
        
    print("\n========================= SEEDED EDGE CASES VERIFICATION ===============================")
    for sv in rep["seed_verifications"]:
        tag = "[PASS]" if sv["verified"] else "[FAIL]"
        print(f"{tag} {sv['order_id']:<18} | {sv['case_name']:<40}")
        print(f"       Expected: {sv['expected_type']:<22} | Actual: {sv['actual_type']:<22}")
        print(f"       Status:   {sv['status']:<12} | Impact: INR {sv['rupee_impact']:,.2f}\n")
        
    print("========================= INR-RANKED EXCEPTION LEDGER ===================================")
    for _, row in rep["exceptions_df"].iterrows():
        print(f"[{row['exception_type'].upper():<21}] {row['order_id']:<18} | Impact: INR {row['rupee_impact']:>10,.2f} | Status: {row['status']}")
        print(f"  Reason: {row['reason']}\n")
    print("=========================================================================================\n")

def main():
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")
    conn = sqlite3.connect(db_path)
    try:
        print_full_report(conn)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
