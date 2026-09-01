import sqlite3
from typing import Optional

def get_applicable_rate(
    conn: sqlite3.Connection,
    vendor_id: Optional[str],
    date_str: str,
    rule_type: str
) -> float:
    """
    Looks up the point-in-time rate in effect on a specific date (date_str: YYYY-MM-DD).
    
    If rule_type == 'commission', it queries commission_slabs for the specified vendor_id.
    If rule_type in ('TCS', 'TDS'), it queries tax_rules for that tax type.
    
    Condition: effective_from <= date_str AND (effective_to >= date_str OR effective_to IS NULL)
    """
    cursor = conn.cursor()
    
    if rule_type.lower() == "commission":
        if not vendor_id:
            raise ValueError("vendor_id must be provided when rule_type is 'commission'")
        
        query = """
            SELECT rate 
            FROM commission_slabs
            WHERE vendor_id = ?
              AND effective_from <= ?
              AND (effective_to >= ? OR effective_to IS NULL)
            ORDER BY effective_from DESC
            LIMIT 1
        """
        cursor.execute(query, (vendor_id, date_str, date_str))
        row = cursor.fetchone()
        if row is not None:
            return float(row[0])
        raise ValueError(f"No commission slab found for vendor '{vendor_id}' on date '{date_str}'")

    elif rule_type.upper() in ("TCS", "TDS"):
        query = """
            SELECT rate 
            FROM tax_rules
            WHERE rule_type = ?
              AND effective_from <= ?
              AND (effective_to >= ? OR effective_to IS NULL)
            ORDER BY effective_from DESC
            LIMIT 1
        """
        cursor.execute(query, (rule_type.upper(), date_str, date_str))
        row = cursor.fetchone()
        if row is not None:
            return float(row[0])
        raise ValueError(f"No tax rule found for '{rule_type}' on date '{date_str}'")
        
    else:
        raise ValueError(f"Unsupported rule_type: '{rule_type}'. Must be 'commission', 'TCS', or 'TDS'.")
