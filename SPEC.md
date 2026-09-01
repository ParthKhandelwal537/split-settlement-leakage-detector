# Project Spec: Split-Settlement Leakage Detector

## Goal
Reconciliation agent for Indian marketplace payment-aggregator settlements.
Closes one finance-ops loop across a 50+ record synthetic batch.
Must report: match rate, ₹-value-ranked exception list, audit trail,
stopping rules, compliant escalation.

## Database
SQLite (single file: reconciliation.db). Tables:
- orders(order_id, vendor_id, order_date, gross_amount, category, is_split_eligible)
- commission_slabs(vendor_id, effective_from, effective_to, rate)
- tax_rules(rule_type, rate, effective_from, effective_to)  -- TCS and TDS, versioned
- settlements(settlement_id, order_id, settlement_date, amount,
  commission_deducted, tcs_deducted, tds_deducted, logistics_deducted)
- refunds(refund_id, order_id, vendor_id, refund_amount, refund_date)
- gst_filings(vendor_id, filing_month, filed_date)  -- GSTR-8 filing dates
- nodal_account_ledger(date, opening_balance, collected, settled, closing_balance)
- exceptions(exception_id, order_id, exception_type, reason, confidence_score,
  status, rupee_impact, created_at)
- audit_log(log_id, timestamp, stage, action, detail)

## Seeded edge cases (exactly 4, known order_ids, in seed_manifest.json)
1. Retroactive commission-slab change — vendor crosses volume tier mid-cycle;
   orders reconcile against the rate live at order time, not current rate.
2. Partial refund clawback on multi-vendor order — refund on one line item
   claws back only that vendor's share.
3. TCS-filing-timing exception — a "missing" TCS credit that is actually
   pending GSTR-8 filing (compare settlement date to gst_filings.filed_date),
   not real leakage.
4. Nodal-balance integrity break — a day where
   closing_balance != opening_balance + collected - settled.

## Exception classification (3 buckets)
- settlement-math exception (real leakage: slab error, refund miscalculation, rounding)
- tax-timing exception (waiting on GSTR-8, not real leakage)
- structural/compliance exception (nodal break, ineligible split, unmapped beneficiary)

Every exception gets: reason (plain text), confidence_score (0-1),
status (auto-cleared / needs-review / escalated).

## Stopping rules (explicit, not implicit)
- confidence_score < 0.7 → status = needs-review, do NOT auto-resolve
- exception_type = structural/compliance → status = escalated, always,
  regardless of confidence
- Any nodal_account_ledger integrity break → escalated, halt further
  automated action on that date's batch

## Audit trail
Every pipeline stage writes to audit_log: what ran, what it found, what
decision was made and why. Must be queryable, not just print statements.

## Required outputs
- Match rate: % of orders that reconcile cleanly with no exception
- ₹-value-ranked exception list (sorted by rupee_impact descending)
- Breakdown: count of exceptions by type, count escalated, count
  needs-review, count auto-cleared
- Confirmation the 4 seeded edge cases were each caught by name
- Streamlit dashboard surfacing all of the above with filters
  (vendor, category, exception type, status)
