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

## Stage 2: Point-in-Time Rule Engine
- Implemented `src/rule_engine.py` with `get_applicable_rate()`.
- Added unit tests in `tests/test_rule_engine.py` covering retroactive slab changes and tax rate transitions.
- All 4 unit tests passing.

## Stage 3: Matcher + Classifier
- Implemented `src/matcher.py` (point-in-time calculation vs actual settlement diffs).
- Implemented `src/classifier.py` (3-bucket classification: `settlement-math`, `tax-timing`, `structural/compliance`).
- Evaluated GSTR-8 filing dates vs settlement dates for TCS tax-timing recognition.

### Checkpoint 2 Verification (Stage 3)
- **ORD-001**: Caught as `settlement-math` exception (Commission slab mismatch ₹300.00).
- **ORD-015**: Caught as `settlement-math` exception (Refund clawback disparity ₹1,500.00).
- **ORD-028**: Caught as `tax-timing` exception (Pending GSTR-8 filing, impact ₹100.00).
- **NODAL-2026-08-14**: Caught as `structural/compliance` exception (Nodal account balance break ₹50,000.00).
- Ineligible split orders (`ORD-010`, `ORD-020`, `ORD-030`, `ORD-040`, `ORD-050`, `ORD-060`) correctly classified as `structural/compliance`.
- Status: **VERIFIED & MATCHES SPEC**.

## Stage 4: Stopping Rules & Escalation
- Implemented `src/escalation.py` with strict compliance rules:
  - Any nodal ledger break or structural/compliance exception unconditionally sets status to `escalated` and writes a halt record to `audit_log`.
  - Confidence < 0.70 flags as `needs-review`.
  - Point-in-time deterministic exceptions auto-cleared.
- Tested in `tests/test_escalation.py` (3/3 passing).

## Stage 5: Audit Trail
- Fully instrumented stages with structured `audit_log` writes (Stage name, timestamp, action type, and human-readable detail).
- Built `src/audit_report.py` for chronological trail reporting.

## Stage 6: Reporting Layer
- Implemented `src/report.py` outputting match rate (81.67%), ₹-ranked exception list, 3-bucket breakdowns, self-skepticism index (8.33% tax-timing vs real leakage), and 4/4 Seed Manifest passes.

## Stage 7: Streamlit Dashboard
- Implemented `dashboard/app.py` featuring:
  - Top integrity metric tiles (Match rate, ₹ leakage, Escalated count, Needs-review, Auto-cleared).
  - Seeded Edge Cases verification panel (color-coded pass badges for all 4 cases).
  - Multi-dimensional filterable exception table (by vendor, exception type, escalation status).
  - Real-time audit trail viewer.
  - Interactive "Re-run Pipeline Live" button for live end-to-end demo execution.

## Stage 8: System Documentation & Retrospective
- Completed `ARCHITECTURE.md` with full data flow diagrams, SQLite relational rationale, 3-bucket taxonomy explanation, and compliant escalation design.
- Full test suite: 7/7 tests passing (`pytest tests/ -v`).

### What Broke & How It Was Resolved (Raw Pitch Material)
1. **Windows Shell Codepage UTF-8 Symbol Crash**: Direct console logging of rupee symbols (`₹`) encountered character mapping errors under Windows standard `cp1252` encoding. Resolved cleanly using `sys.stdout.reconfigure(encoding="utf-8")` and standardized currency formats.
2. **Point-in-Time Date Straddling**: In the retroactive commission slab test, orders placed before the 1st of the month needed exact inclusive/exclusive timestamp boundary handling (`effective_from <= order_date <= effective_to`). Handled via SQL `COALESCE/IS NULL` logic for open-ended active rules.



