# Developer Log (DEVLOG.md)

## Stage 0: Repository & Environment Setup
- Initialized workspace structure (`data/`, `src/`, `tests/`, `dashboard/`).
- Created core documentation: `SPEC.md`, `DEVLOG.md`, `ARCHITECTURE.md`, `README.md`.
- Verified Python 3.14 environment with `pandas`, `streamlit`, and `pytest`.
- Tested Streamlit hello world component.

## Stage 1: Data Generator + Database Schema
- Implemented `src/data_generator.py` generating SQLite database `data/reconciliation.db` with all 9 tables.
- Generated 60 orders across 12 vendors, versioned commission slabs, TDS/TCS tax rules, settlements, refunds, GST filings, and 62-day daily nodal ledger.
- Exported `data/seed_manifest.json` mapping all 4 edge cases.

### Checkpoint 1 Verification (Stage 1)
- **ORD-001 (Slab Change)**: Order placed 2026-07-25 (July slab 10% = ₹1000 commission). Settlement on 2026-08-02 mistakenly applied August slab (7% = ₹700 commission, payout ₹9000 vs expected ₹8700). Straddles rate transition date cleanly.
- **ORD-015 (Partial Refund Clawback)**: Order ₹8000, partial refund ₹2000 on 2026-07-20. Settlement erroneously clawed back ₹3500 (payout ₹3280 vs expected ₹4780).
- **ORD-028 (TCS Filing Timing)**: Settled 2026-08-05 before GSTR-8 filed date on 2026-08-20. Missing TCS deduction of ₹100 due to filing lag.
- **NODAL-2026-08-14 (Nodal Ledger Break)**: On 2026-08-14, closing balance ₹749,061.43 vs expected ₹799,061.43 (exact ₹50,000 deficit).
- Status: **VERIFIED & MATCHES SPEC**.

