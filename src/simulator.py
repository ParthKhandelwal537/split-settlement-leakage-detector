import sqlite3
import pandas as pd
from typing import Dict, Any

def simulate_policy_shift(
    conn: sqlite3.Connection,
    commission_adj_pct: float = 0.0,
    tds_rate: float = 0.0075,
    tcs_rate: float = 0.010
) -> Dict[str, Any]:
    """
    Simulates portfolio-wide financial shifts under hypothetical commission,
    TDS, and TCS policy modifications.
    
    Args:
        conn: SQLite connection
        commission_adj_pct: Delta percentage adjustment to commission (e.g. +1.5% or -1.0%)
        tds_rate: New Section 194-O TDS withholding rate
        tcs_rate: Section 52 TCS withholding rate
        
    Returns:
        Structured simulation forecast including projected GMV, platform revenue shift,
        vendor payout shifts, and tax withholding volumes.
    """
    orders_df = pd.read_sql_query("SELECT * FROM orders", conn)
    settlements_df = pd.read_sql_query("SELECT * FROM settlements", conn)
    
    total_gmv = float(orders_df["gross_amount"].sum()) if not orders_df.empty else 0.0
    actual_commission_total = float(settlements_df["commission_deducted"].sum()) if not settlements_df.empty else 0.0
    actual_payout_total = float(settlements_df["amount"].sum()) if not settlements_df.empty else 0.0
    
    # Calculate projected revenue shift
    commission_delta_inr = total_gmv * (commission_adj_pct / 100.0)
    projected_platform_commission = max(0.0, actual_commission_total + commission_delta_inr)
    
    projected_tds_withheld = total_gmv * tds_rate
    projected_tcs_withheld = total_gmv * tcs_rate
    
    projected_vendor_payout = max(0.0, total_gmv - (projected_platform_commission + projected_tds_withheld + projected_tcs_withheld + (len(orders_df) * 100.0)))
    vendor_payout_shift = projected_vendor_payout - actual_payout_total
    
    return {
        "total_gmv": round(total_gmv, 2),
        "total_orders_count": len(orders_df),
        "actual_commission_total": round(actual_commission_total, 2),
        "projected_platform_commission": round(projected_platform_commission, 2),
        "platform_revenue_shift": round(commission_delta_inr, 2),
        "projected_tds_withheld": round(projected_tds_withheld, 2),
        "projected_tcs_withheld": round(projected_tcs_withheld, 2),
        "projected_vendor_payout": round(projected_vendor_payout, 2),
        "vendor_payout_shift": round(vendor_payout_shift, 2)
    }
