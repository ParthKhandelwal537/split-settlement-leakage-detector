# Architecture & System Design: Split-Settlement Leakage Detector

## Overview
A high-integrity financial reconciliation agent built for Indian multi-vendor marketplace payment-aggregator settlements. It detects split-settlement leakages, classifies anomalies across 3 distinct buckets (Settlement Math, Tax Timing, Structural/Compliance), enforces stopping and escalation rules, and records an immutable audit trail.

## Data Flow Diagram
```
┌─────────────────────────────────────────────────────────────┐
│ 1. Synthetic Generator & DB (reconciliation.db - 9 Tables)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Point-in-Time Rule Engine (get_applicable_rate)          │
│    - Versioned commission slabs (effective_from/to)        │
│    - Tax rules (TCS/TDS rate transitions)                   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Matcher & 3-Bucket Classifier (src/matcher & classifier) │
│    - Compute expected vs actual settlement deltas           │
│    - Cross-reference GSTR-8 gst_filings (tax-timing vs real)│
│    - Verify nodal ledger day-over-day mathematical integrity│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Stopping Rules & Compliant Escalation (src/escalation)   │
│    - Confidence < 0.70  ==> needs-review                    │
│    - Structural/Compliance / Nodal Break ==> escalated     │
│    - Halts automated processing on nodal discrepancy dates  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Audit Trail & Reporting (src/audit_report & src/report)  │
│    - Queryable audit_log for stage-by-stage explainability   │
│    - Match rate, ₹-ranked exceptions, seed verification     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Interactive Streamlit Dashboard (dashboard/app.py)       │
│    - Metrics, filters, seeded edge case badges, live rerun  │
└─────────────────────────────────────────────────────────────┘
```

## Architectural Decisions

### 1. Why SQLite over Postgres or MongoDB?
- **Real SQL Joins & Date Constraints**: Point-in-time rule resolution requires robust range joins (`effective_from <= order_date AND (effective_to >= order_date OR effective_to IS NULL)`). SQL relational algebra guarantees correct interval evaluation.
- **Zero-Setup & Portability**: Evaluators and judges can clone and execute `python dashboard/app.py` instantly with zero Docker or network database dependencies.
- **ACID & Foreign Key Integrity**: Multi-table relational dependencies between `orders`, `settlements`, `refunds`, and `gst_filings` remain strictly enforced.

### 2. Why the 3-Bucket Classification Scheme?
Financial errors in payment settlements stem from different operational layers and must not be treated identically:
1. **`settlement-math` (Real Financial Leakage)**: Slab change miscalculations, incorrect volume tier deductions, or excessive refund clawbacks. These represent actual money lost or over-credited that requires automated ledger adjustments.
2. **`tax-timing` (Non-Leakage / Operational Timing Lag)**: Apparent TCS credit gaps arising because settlements occur before monthly GSTR-8 return filings. Classifying this separately prevents false alerts and avoids unwarranted disputes with vendors.
3. **`structural/compliance` (Severe Compliance / Accounting Breaks)**: Nodal account balance integrity breaks (`closing != opening + collected - settled`), split-ineligible marketplace orders, or unmapped beneficiaries.

### 3. Edge Cases & Scope

#### Seeded Edge Cases Handled:
1. **Retroactive commission-slab change (`ORD-001`)**: Vendor crosses volume tier mid-cycle; reconciliation confirms rates active at *order time*, avoiding retroactive over-deduction.
2. **Partial refund clawback on multi-vendor order (`ORD-015`)**: Partial line item return claws back only that vendor's share, detecting excessive clawbacks.
3. **TCS-filing-timing exception (`ORD-028`)**: Discrepancy reconciled against `gst_filings.filed_date` vs settlement date to identify GSTR-8 filing lag.
4. **Nodal-balance integrity break (`NODAL-2026-08-14`)**: Daily closing balance deficit halts automated batch processing and escalates immediately to human finance ops.

#### Explicitly Out of Scope (Future Roadmap):
- **Weekly-batch unbundling**: Grouping multiple asynchronous order settlements into combined payout batches.
- **Cross-currency FX volatility**: Multi-currency dynamic forex rate adjustments.
- **Multi-party chargeback splits**: Dispute resolution logic across payment gateway, platform, and vendor.
- **Pre-funding cashflow detection**: Working capital advance interest deduction reconciliations.

### 4. Stopping Rules & Compliant Escalation
To align with regulatory and finance ops compliance ("Compliant Escalation"):
- Any structural break or nodal balance break **overrides confidence** and is unconditionally marked as `escalated`.
- Low-confidence classifications (< 0.70) are flagged as `needs-review` rather than auto-resolved.
- Every escalation event logs an immutable halting entry into `audit_log`.

