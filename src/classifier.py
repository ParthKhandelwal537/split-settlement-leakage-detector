import sqlite3
import pandas as pd
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.matcher import run_matcher


def _compute_confidence(delta: float, gross: float, has_corroboration: bool, is_structural: bool) -> float:
    """
    Dynamic confidence scoring based on:
    - Delta as % of gross amount (larger relative delta = higher confidence it's real)
    - Whether corroborating evidence exists (e.g., filed_date confirms timing)
    - Structural exceptions get a floor of 0.90
    Returns a score clamped to [0.50, 1.00].
    """
    if is_structural:
        return round(min(1.0, 0.90 + abs(delta) / max(gross, 1) * 0.1), 3)
    
    # Base: ratio of delta to gross
    ratio = abs(delta) / max(gross, 1)
    base = 0.60 + ratio * 3.0  # small ratios stay low, big ratios push high
    if has_corroboration:
        base += 0.12
    return round(min(1.0, max(0.50, base)), 3)


def classify_exceptions(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Classifies discrepancies into exactly 3 buckets:
    1. settlement-math exception (real leakage: slab error, refund miscalculation, rounding)
    2. tax-timing exception (waiting on GSTR-8, not real leakage)
    3. structural/compliance exception (nodal break, ineligible split, unmapped beneficiary)
    
    Writes classified exceptions to the exceptions table with status = 'pending'.
    """
    diff_df = run_matcher(conn)
    cursor = conn.cursor()
    
    # Clear existing exceptions for a clean run
    cursor.execute("DELETE FROM exceptions")
    
    exceptions = []
    exc_idx = 1
    
    # 1. Check Nodal Ledger Integrity first (Day-by-day balance break)
    nodal_df = pd.read_sql_query("SELECT * FROM nodal_account_ledger ORDER BY date", conn)
    for _, row in nodal_df.iterrows():
        d_str = row["date"]
        opening = float(row["opening_balance"])
        collected = float(row["collected"])
        settled = float(row["settled"])
        closing = float(row["closing_balance"])
        
        expected_closing = round(opening + collected - settled, 2)
        diff = round(closing - expected_closing, 2)
        
        if abs(diff) > 0.01:
            exception_id = f"EXC-NODAL-{d_str}"
            exc_obj = {
                "exception_id": exception_id,
                "order_id": f"NODAL-{d_str}",
                "exception_type": "structural/compliance",
                "reason": f"Nodal account balance integrity break on {d_str}: closing balance ₹{closing:,.2f} != opening (₹{opening:,.2f}) + collected (₹{collected:,.2f}) - settled (₹{settled:,.2f}). Deficit/Imbalance: ₹{abs(diff):,.2f}.",
                "confidence_score": 1.0,
                "status": "pending",
                "rupee_impact": abs(diff),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            exceptions.append(exc_obj)

    # 2. Query GST Filings for tax-timing verification
    gst_filings_df = pd.read_sql_query("SELECT * FROM gst_filings", conn)

    # 3. Classify per-order exceptions
    for _, row in diff_df.iterrows():
        order_id = row["order_id"]
        vendor_id = row["vendor_id"]
        order_date = row["order_date"]
        settlement_date = row["settlement_date"]
        payout_delta = float(row["payout_delta"])
        comm_delta = float(row["comm_delta"])
        tcs_delta = float(row["tcs_delta"])
        tds_delta = float(row["tds_delta"])
        is_split_eligible = int(row["is_split_eligible"])
        refund_amt = float(row["refund_amount"])
        
        # Check Compliance/Structural: Split eligibility
        if is_split_eligible == 0:
            exception_id = f"EXC-{exc_idx:03d}"
            exc_idx += 1
            split_impact = float(row["gross_amount"])
            exc_obj = {
                "exception_id": exception_id,
                "order_id": order_id,
                "exception_type": "structural/compliance",
                "reason": f"Order {order_id} flagged as ineligible for split settlement under marketplace compliance rules.",
                "confidence_score": _compute_confidence(split_impact, split_impact, True, True),
                "status": "pending",
                "rupee_impact": split_impact,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            exceptions.append(exc_obj)
            continue
            
        if abs(payout_delta) < 0.01:
            continue
            
        # Case Analysis:
        # Check if TCS timing is the primary root cause
        # An apparent TCS gap occurs when actual_tcs == 0 or != expected_tcs
        is_tax_timing = False
        if abs(tcs_delta) > 0.01:
            # Check GSTR-8 filing month (derived from order/settlement month)
            filing_month = order_date[:7]
            filing_row = gst_filings_df[
                (gst_filings_df["vendor_id"] == vendor_id) & 
                (gst_filings_df["filing_month"] == filing_month)
            ]
            
            filed_date = filing_row["filed_date"].values[0] if not filing_row.empty else None
            
            # If filed_date is None or filed_date > settlement_date, the GSTR-8 filing is pending!
            if filed_date is None or (settlement_date and filed_date > settlement_date):
                is_tax_timing = True
                exception_id = f"EXC-{exc_idx:03d}"
                exc_idx += 1
                reason_str = (
                    f"TCS credit of ₹{abs(tcs_delta):,.2f} missing during settlement on {settlement_date} "
                    f"due to pending GSTR-8 filing (filed on {filed_date or 'PENDING'}). Timing difference, not leakage."
                )
                tax_conf = _compute_confidence(abs(tcs_delta), float(row["gross_amount"]),
                                               has_corroboration=(filed_date is not None), is_structural=False)
                exc_obj = {
                    "exception_id": exception_id,
                    "order_id": order_id,
                    "exception_type": "tax-timing",
                    "reason": reason_str,
                    "confidence_score": tax_conf,
                    "status": "pending",
                    "rupee_impact": abs(tcs_delta),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                exceptions.append(exc_obj)

        # If not pure tax timing, check Settlement Math (Slab change or refund clawback or calculation errors)
        if not is_tax_timing:
            exception_id = f"EXC-{exc_idx:03d}"
            exc_idx += 1
            
            # Diagnose specific settlement math reason
            if abs(comm_delta) > 0.01:
                reason_str = (
                    f"Commission slab mismatch on order placed {order_date}: "
                    f"Expected ₹{row['expected_comm']:,.2f} ({row['comm_rate']*100:.1f}%), "
                    f"Actual deducted ₹{row['actual_comm']:,.2f}. Commission leakage: ₹{abs(comm_delta):,.2f}."
                )
                impact = abs(comm_delta)
            elif refund_amt > 0 and abs(payout_delta) > 0.01:
                reason_str = (
                    f"Refund clawback disparity: Refund logged was ₹{refund_amt:,.2f}, "
                    f"but payout delta indicates excessive clawback of ₹{abs(payout_delta):,.2f}."
                )
                impact = abs(payout_delta)
            else:
                reason_str = f"Settlement payout math mismatch: Expected ₹{row['expected_payout']:,.2f}, Actual ₹{row['actual_payout']:,.2f} (Delta ₹{payout_delta:,.2f})."
                impact = abs(payout_delta)

            math_conf = _compute_confidence(impact, float(row["gross_amount"]),
                                             has_corroboration=(abs(comm_delta) > 0.01 or refund_amt > 0),
                                             is_structural=False)
            exc_obj = {
                "exception_id": exception_id,
                "order_id": order_id,
                "exception_type": "settlement-math",
                "reason": reason_str,
                "confidence_score": math_conf,
                "status": "pending",
                "rupee_impact": impact,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            exceptions.append(exc_obj)

    # Insert into exceptions table
    cursor.executemany("""
        INSERT INTO exceptions (
            exception_id, order_id, exception_type, reason,
            confidence_score, status, rupee_impact, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [(
        e["exception_id"], e["order_id"], e["exception_type"], e["reason"],
        e["confidence_score"], e["status"], e["rupee_impact"], e["created_at"]
    ) for e in exceptions])
    
    # Audit log entry for Classifier stage
    type_counts = {}
    for e in exceptions:
        t = e["exception_type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    
    cursor.execute(
        "INSERT INTO audit_log (timestamp, stage, action, detail) VALUES (?, ?, ?, ?)",
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Stage 3",
            "EXCEPTION_CLASSIFICATION",
            f"Classified {len(exceptions)} discrepancies into 3 buckets: settlement-math ({type_counts.get('settlement-math', 0)}), tax-timing ({type_counts.get('tax-timing', 0)}), structural/compliance ({type_counts.get('structural/compliance', 0)})."
        )
    )
    
    conn.commit()
    return exceptions


def main():
    import os
    # Fix Windows console UTF-8 encoding if needed
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")
    conn = sqlite3.connect(db_path)
    try:
        exceptions = classify_exceptions(conn)
        print("\n=======================================================")
        print("          EXCEPTION CLASSIFICATION SUMMARY             ")
        print("=======================================================")
        print(f"Total Exceptions Classified: {len(exceptions)}")
        for e in exceptions:
            print(f"[{e['exception_type'].upper():<22}] {e['order_id']:<18} | Impact: INR {e['rupee_impact']:>9,.2f} | Conf: {e['confidence_score']:.2f}")
            print(f"  Reason: {e['reason']}\n")
        print("=======================================================\n")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
