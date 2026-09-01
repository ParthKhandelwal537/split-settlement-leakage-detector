import sqlite3
import json
import os
import random
from datetime import datetime, date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_manifest.json")

def create_schema(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.executescript("""
    PRAGMA foreign_keys = ON;

    DROP TABLE IF EXISTS audit_log;
    DROP TABLE IF EXISTS exceptions;
    DROP TABLE IF EXISTS nodal_account_ledger;
    DROP TABLE IF EXISTS gst_filings;
    DROP TABLE IF EXISTS refunds;
    DROP TABLE IF EXISTS settlements;
    DROP TABLE IF EXISTS tax_rules;
    DROP TABLE IF EXISTS commission_slabs;
    DROP TABLE IF EXISTS orders;

    CREATE TABLE orders (
        order_id TEXT PRIMARY KEY,
        vendor_id TEXT NOT NULL,
        order_date TEXT NOT NULL,
        gross_amount REAL NOT NULL,
        category TEXT NOT NULL,
        is_split_eligible INTEGER NOT NULL CHECK (is_split_eligible IN (0, 1))
    );

    CREATE TABLE commission_slabs (
        vendor_id TEXT NOT NULL,
        effective_from TEXT NOT NULL,
        effective_to TEXT,
        rate REAL NOT NULL,
        PRIMARY KEY (vendor_id, effective_from)
    );

    CREATE TABLE tax_rules (
        rule_type TEXT NOT NULL,
        rate REAL NOT NULL,
        effective_from TEXT NOT NULL,
        effective_to TEXT,
        PRIMARY KEY (rule_type, effective_from)
    );

    CREATE TABLE settlements (
        settlement_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        settlement_date TEXT NOT NULL,
        amount REAL NOT NULL,
        commission_deducted REAL NOT NULL,
        tcs_deducted REAL NOT NULL,
        tds_deducted REAL NOT NULL,
        logistics_deducted REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    );

    CREATE TABLE refunds (
        refund_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        vendor_id TEXT NOT NULL,
        refund_amount REAL NOT NULL,
        refund_date TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    );

    CREATE TABLE gst_filings (
        vendor_id TEXT NOT NULL,
        filing_month TEXT NOT NULL,
        filed_date TEXT,
        PRIMARY KEY (vendor_id, filing_month)
    );

    CREATE TABLE nodal_account_ledger (
        date TEXT PRIMARY KEY,
        opening_balance REAL NOT NULL,
        collected REAL NOT NULL,
        settled REAL NOT NULL,
        closing_balance REAL NOT NULL
    );

    CREATE TABLE exceptions (
        exception_id TEXT PRIMARY KEY,
        order_id TEXT,
        exception_type TEXT NOT NULL,
        reason TEXT NOT NULL,
        confidence_score REAL NOT NULL,
        status TEXT NOT NULL,
        rupee_impact REAL NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE audit_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        stage TEXT NOT NULL,
        action TEXT NOT NULL,
        detail TEXT NOT NULL
    );
    """)
    conn.commit()

def generate_data(conn: sqlite3.Connection):
    random.seed(42)
    cursor = conn.cursor()

    # 1. Tax Rules (TCS & TDS) over 2-month window: 2026-07-01 to 2026-08-31
    # Tax transition for TDS: was 0.010 (1.0%) till 2026-07-31, updated to 0.0075 (0.75%) from 2026-08-01
    tax_rules = [
        ("TCS", 0.010, "2026-07-01", None),
        ("TDS", 0.010, "2026-07-01", "2026-07-31"),
        ("TDS", 0.0075, "2026-08-01", None),
    ]
    cursor.executemany(
        "INSERT INTO tax_rules (rule_type, rate, effective_from, effective_to) VALUES (?, ?, ?, ?)",
        tax_rules
    )

    # 2. Vendors & Commission Slabs (12 vendors)
    # VEND-001 crosses tier on 2026-08-01 (Rate drops from 10% to 7% due to volume threshold crossing)
    vendors = [f"VEND-{i:03d}" for i in range(1, 13)]
    slabs = []
    for v in vendors:
        if v == "VEND-001":
            # Slab change: 10% in July, 7% starting Aug 1
            slabs.append((v, "2026-07-01", "2026-07-31", 0.100))
            slabs.append((v, "2026-08-01", None, 0.070))
        elif v == "VEND-002":
            slabs.append((v, "2026-07-01", None, 0.080))
        elif v == "VEND-003":
            slabs.append((v, "2026-07-01", None, 0.120))
        elif v == "VEND-004":
            slabs.append((v, "2026-07-01", None, 0.050))
        else:
            slabs.append((v, "2026-07-01", None, 0.090))

    cursor.executemany(
        "INSERT INTO commission_slabs (vendor_id, effective_from, effective_to, rate) VALUES (?, ?, ?, ?)",
        slabs
    )

    # 3. GST Filings (July 2026 filings filed on Aug 10, August 2026 filings filed on Sept 10)
    # For VEND-004 (Edge Case 3), July filing was delayed/pending past settlement date!
    gst_filings = []
    for v in vendors:
        if v == "VEND-004":
            # July filing delayed (not filed yet during settlement on Aug 5)
            gst_filings.append((v, "2026-07", "2026-08-20"))
            gst_filings.append((v, "2026-08", None))
        else:
            gst_filings.append((v, "2026-07", "2026-08-10"))
            gst_filings.append((v, "2026-08", "2026-09-10"))

    cursor.executemany(
        "INSERT INTO gst_filings (vendor_id, filing_month, filed_date) VALUES (?, ?, ?)",
        gst_filings
    )

    # 4. Generate 60 Orders
    categories = ["Electronics", "Apparel", "Home & Living", "Beauty", "Books", "Sports"]
    start_date = date(2026, 7, 1)
    
    orders = []
    settlements = []
    refunds = []

    # Map for rates lookup during synthetic generation
    def get_commission_rate(v_id, o_date_str):
        if v_id == "VEND-001":
            return 0.100 if o_date_str <= "2026-07-31" else 0.070
        elif v_id == "VEND-002":
            return 0.080
        elif v_id == "VEND-003":
            return 0.120
        elif v_id == "VEND-004":
            return 0.050
        return 0.090

    def get_tds_rate(o_date_str):
        return 0.010 if o_date_str <= "2026-07-31" else 0.0075

    tcs_rate = 0.010

    # Specific Edge Case Order IDs:
    # 1. ORD-001: Retroactive commission slab change (Order placed July 25 at 10%, settled Aug 2 with mistaken 7% current rate)
    # 2. ORD-015: Partial refund clawback on multi-vendor / split order (Refund ₹2,000 clawed back ₹3,500 over-deduction)
    # 3. ORD-028: TCS filing timing exception (Order placed July 28, settled Aug 5; TCS credit missing because GSTR-8 filed Aug 20)
    # 4. ORD-040: Standard order, but day 2026-08-14 will have Nodal Integrity Break

    seed_manifest = [
        {
            "order_id": "ORD-001",
            "case_name": "Retroactive commission-slab change",
            "description": "Order placed on 2026-07-25 (effective slab 10%), settled on 2026-08-02 where aggregator incorrectly applied current August slab of 7% resulting in ₹300 commission leakage."
        },
        {
            "order_id": "ORD-015",
            "case_name": "Partial refund clawback on multi-vendor order",
            "description": "Customer returned partial item worth ₹2,000 on 2026-07-20, but aggregator settlement clawed back full ₹3,500 from vendor's payout (₹1,500 over-clawback leakage)."
        },
        {
            "order_id": "ORD-028",
            "case_name": "TCS-filing-timing exception",
            "description": "Settled on 2026-08-05 before GSTR-8 filing on 2026-08-20; apparent ₹100 TCS gap is timing difference, not actual leakage."
        },
        {
            "order_id": "NODAL-2026-08-14",
            "case_name": "Nodal-balance integrity break",
            "description": "On 2026-08-14, closing balance has an unexplained deficit of ₹50,000 (closing_balance != opening_balance + collected - settled)."
        }
    ]

    for i in range(1, 61):
        order_id = f"ORD-{i:03d}"
        v_idx = (i % 12) + 1
        vendor_id = f"VEND-{v_idx:03d}"
        
        # Distribute dates across July and August 2026
        day_offset = int((i - 1) * (58 / 60))
        o_date = start_date + timedelta(days=day_offset)
        o_date_str = o_date.strftime("%Y-%m-%d")
        
        # Specific overrides for seeded cases
        if order_id == "ORD-001":
            vendor_id = "VEND-001"
            o_date_str = "2026-07-25"
            gross_amount = 10000.0
            category = "Electronics"
            is_split_eligible = 1
        elif order_id == "ORD-015":
            vendor_id = "VEND-003"
            o_date_str = "2026-07-15"
            gross_amount = 8000.0
            category = "Apparel"
            is_split_eligible = 1
        elif order_id == "ORD-028":
            vendor_id = "VEND-004"
            o_date_str = "2026-07-28"
            gross_amount = 10000.0
            category = "Home & Living"
            is_split_eligible = 1
        else:
            gross_amount = round(random.uniform(1500, 15000), 2)
            category = categories[i % len(categories)]
            is_split_eligible = 1 if i % 10 != 0 else 0

        orders.append((order_id, vendor_id, o_date_str, gross_amount, category, is_split_eligible))

        # Settlement creation (typically settled 3 to 7 days after order)
        s_date = datetime.strptime(o_date_str, "%Y-%m-%d").date() + timedelta(days=random.randint(3, 7))
        s_date_str = s_date.strftime("%Y-%m-%d")
        settlement_id = f"SETT-{i:03d}"

        comm_rate = get_commission_rate(vendor_id, o_date_str)
        tds_rate = get_tds_rate(o_date_str)
        logistics = 100.0

        comm_deducted = round(gross_amount * comm_rate, 2)
        tcs_deducted = round(gross_amount * tcs_rate, 2)
        tds_deducted = round(gross_amount * tds_rate, 2)
        
        expected_settlement_amount = round(gross_amount - (comm_deducted + tcs_deducted + tds_deducted + logistics), 2)
        actual_settlement_amount = expected_settlement_amount

        # Ordinary refunds: ORD-005 and ORD-032 have legitimate refunds that are
        # correctly reflected in both the refunds table AND the settlement amount.
        # This means the matcher should find ZERO delta for these (clean reconciliation).
        if order_id == "ORD-005":
            refund_amt_normal = 500.0
            refunds.append(("REF-002", order_id, vendor_id, refund_amt_normal, "2026-07-10"))
            actual_settlement_amount = round(actual_settlement_amount - refund_amt_normal, 2)
        elif order_id == "ORD-032":
            refund_amt_normal = 1200.0
            refunds.append(("REF-003", order_id, vendor_id, refund_amt_normal, "2026-08-12"))
            actual_settlement_amount = round(actual_settlement_amount - refund_amt_normal, 2)

        # Apply specific seeded corruptions for edge cases
        if order_id == "ORD-001":
            # Seeded Case 1: Settlement applied August rate (7%) instead of July rate (10%)
            # Expected commission = 10000 * 0.10 = 1000. Actual deducted = 10000 * 0.07 = 700.
            # Settled payout was higher by ₹300 (leakage to aggregator)
            s_date_str = "2026-08-02"
            comm_deducted = 700.0  # Erroneous 7%
            actual_settlement_amount = round(gross_amount - (comm_deducted + tcs_deducted + tds_deducted + logistics), 2)
        
        elif order_id == "ORD-015":
            # Seeded Case 2: Partial refund of ₹2000, but settlement clawed back ₹3500
            refund_id = "REF-001"
            refund_amount = 2000.0
            refund_date = "2026-07-20"
            refunds.append((refund_id, order_id, vendor_id, refund_amount, refund_date))
            # Actual settlement deducted ₹3500 instead of ₹2000 refund
            actual_settlement_amount = round(expected_settlement_amount - 3500.0, 2)

        elif order_id == "ORD-028":
            # Seeded Case 3: TCS not credited/deducted at settlement date because GSTR-8 pending
            s_date_str = "2026-08-05"
            tcs_deducted = 0.0  # Missing TCS deduction in actual settlement record
            actual_settlement_amount = round(gross_amount - (comm_deducted + tcs_deducted + tds_deducted + logistics), 2)

        settlements.append((
            settlement_id, order_id, s_date_str, actual_settlement_amount,
            comm_deducted, tcs_deducted, tds_deducted, logistics
        ))


    cursor.executemany(
        "INSERT INTO orders (order_id, vendor_id, order_date, gross_amount, category, is_split_eligible) VALUES (?, ?, ?, ?, ?, ?)",
        orders
    )
    cursor.executemany(
        "INSERT INTO settlements (settlement_id, order_id, settlement_date, amount, commission_deducted, tcs_deducted, tds_deducted, logistics_deducted) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        settlements
    )
    cursor.executemany(
        "INSERT INTO refunds (refund_id, order_id, vendor_id, refund_amount, refund_date) VALUES (?, ?, ?, ?, ?)",
        refunds
    )

    # 5. Daily Nodal Account Ledger (62 days from 2026-07-01 to 2026-08-31)
    nodal_ledger = []
    current_balance = 500000.0  # Starting opening balance
    cur_d = date(2026, 7, 1)
    end_d = date(2026, 8, 31)

    while cur_d <= end_d:
        d_str = cur_d.strftime("%Y-%m-%d")
        opening = current_balance
        collected = round(random.uniform(30000, 75000), 2)
        settled = round(random.uniform(25000, 65000), 2)
        
        # Edge Case 4: Nodal balance integrity break on 2026-08-14
        if d_str == "2026-08-14":
            closing = round(opening + collected - settled - 50000.0, 2)  # ₹50,000 deficit break!
        else:
            closing = round(opening + collected - settled, 2)

        nodal_ledger.append((d_str, opening, collected, settled, closing))
        current_balance = closing
        cur_d += timedelta(days=1)

    cursor.executemany(
        "INSERT INTO nodal_account_ledger (date, opening_balance, collected, settled, closing_balance) VALUES (?, ?, ?, ?, ?)",
        nodal_ledger
    )

    # Initial audit log entry
    cursor.execute(
        "INSERT INTO audit_log (timestamp, stage, action, detail) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Stage 1", "DATA_GENERATION", "Generated synthetic dataset with 60 orders, 12 vendors, tax rules, settlements, refunds, nodal ledger and 4 seeded edge cases.")
    )

    conn.commit()

    # Write Seed Manifest JSON
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(seed_manifest, f, indent=2)

def print_summary(conn: sqlite3.Connection):
    cursor = conn.cursor()
    tables = [
        "orders", "commission_slabs", "tax_rules", "settlements",
        "refunds", "gst_filings", "nodal_account_ledger", "exceptions", "audit_log"
    ]
    print("\n=======================================================")
    print("       DATABASE GENERATION & SEEDING SUMMARY           ")
    print("=======================================================")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        print(f"Table: {t:<25} | Row Count: {count}")

    cursor.execute("SELECT MIN(order_date), MAX(order_date), COUNT(*) FROM orders")
    min_d, max_d, total_orders = cursor.fetchone()
    print(f"\nOrder Range: {min_d} to {max_d} ({total_orders} total orders)")

    cursor.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM nodal_account_ledger")
    n_min, n_max, n_days = cursor.fetchone()
    print(f"Nodal Ledger Range: {n_min} to {n_max} ({n_days} days)")

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    print("\n---------------- SEED MANIFEST ------------------------")
    print(json.dumps(manifest, indent=2))
    print("=======================================================\n")

def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        generate_data(conn)
        print_summary(conn)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
