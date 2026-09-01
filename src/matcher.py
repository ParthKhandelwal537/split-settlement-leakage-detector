import sqlite3
import pandas as pd
from typing import List, Dict, Any
from src.rule_engine import get_applicable_rate

def run_matcher(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Computes expected settlement amounts for each order using point-in-time rates
    (commission, TCS, TDS) + logistics, accounting for refunds, and compares
    against actual settlements.
    
    Returns a DataFrame containing per-order matching details and deltas.
    """
    orders_df = pd.read_sql_query("SELECT * FROM orders", conn)
    settlements_df = pd.read_sql_query("SELECT * FROM settlements", conn)
    refunds_df = pd.read_sql_query("SELECT * FROM refunds", conn)
    
    # Aggregate refunds by order_id if any
    if not refunds_df.empty:
        refund_agg = refunds_df.groupby("order_id")["refund_amount"].sum().reset_index()
    else:
        refund_agg = pd.DataFrame(columns=["order_id", "refund_amount"])

    # Merge orders with settlements and refunds
    merged = pd.merge(orders_df, settlements_df, on="order_id", how="left")
    merged = pd.merge(merged, refund_agg, on="order_id", how="left")
    merged["refund_amount"] = merged["refund_amount"].fillna(0.0)

    results = []
    
    for _, row in merged.iterrows():
        order_id = row["order_id"]
        vendor_id = row["vendor_id"]
        order_date = row["order_date"]
        gross_amount = float(row["gross_amount"])
        is_split_eligible = int(row["is_split_eligible"])
        
        # Point-in-time rates based on order_date
        comm_rate = get_applicable_rate(conn, vendor_id, order_date, "commission")
        tcs_rate = get_applicable_rate(conn, None, order_date, "TCS")
        tds_rate = get_applicable_rate(conn, None, order_date, "TDS")
        
        # Standard expected logistics
        expected_logistics = 100.0
        
        expected_comm = round(gross_amount * comm_rate, 2)
        expected_tcs = round(gross_amount * tcs_rate, 2)
        expected_tds = round(gross_amount * tds_rate, 2)
        refund_amt = float(row["refund_amount"])
        
        # Expected net payout = gross - comm - tcs - tds - logistics - refund
        expected_payout = round(gross_amount - (expected_comm + expected_tcs + expected_tds + expected_logistics + refund_amt), 2)
        
        actual_payout = float(row["amount"]) if pd.notnull(row["amount"]) else 0.0
        actual_comm = float(row["commission_deducted"]) if pd.notnull(row["commission_deducted"]) else 0.0
        actual_tcs = float(row["tcs_deducted"]) if pd.notnull(row["tcs_deducted"]) else 0.0
        actual_tds = float(row["tds_deducted"]) if pd.notnull(row["tds_deducted"]) else 0.0
        actual_logistics = float(row["logistics_deducted"]) if pd.notnull(row["logistics_deducted"]) else 0.0
        
        # Delta = |expected_payout - actual_payout| or component deltas
        payout_delta = round(actual_payout - expected_payout, 2)
        comm_delta = round(actual_comm - expected_comm, 2)
        tcs_delta = round(actual_tcs - expected_tcs, 2)
        tds_delta = round(actual_tds - expected_tds, 2)
        
        results.append({
            "order_id": order_id,
            "vendor_id": vendor_id,
            "order_date": order_date,
            "settlement_date": row["settlement_date"],
            "gross_amount": gross_amount,
            "is_split_eligible": is_split_eligible,
            "comm_rate": comm_rate,
            "expected_comm": expected_comm,
            "actual_comm": actual_comm,
            "comm_delta": comm_delta,
            "expected_tcs": expected_tcs,
            "actual_tcs": actual_tcs,
            "tcs_delta": tcs_delta,
            "expected_tds": expected_tds,
            "actual_tds": actual_tds,
            "tds_delta": tds_delta,
            "expected_logistics": expected_logistics,
            "actual_logistics": actual_logistics,
            "refund_amount": refund_amt,
            "expected_payout": expected_payout,
            "actual_payout": actual_payout,
            "payout_delta": payout_delta,
            "has_delta": abs(payout_delta) > 0.001 or not is_split_eligible
        })
        
    return pd.DataFrame(results)
