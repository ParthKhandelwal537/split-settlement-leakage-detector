# Split-Settlement Leakage Detector — Full Action Plan
### Razorpay AI Buildathon — Individual Submission, Due Friday

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Database | SQLite | Real SQL joins/constraints for versioned rules, zero setup, judge can clone-and-run instantly |
| Logic | Python + pandas | Fast to express reconciliation math and rule lookups |
| Presentation | Streamlit dashboard | This is the "how do I present a backend tool" answer — a real clickable interactive layer |
| Build tool | Google Antigravity | Manager view for parallel agent stages, Editor view for hands-on work |
| Model | Claude (via Antigravity) | More literal/careful rule-following for financial logic |
| Version control | GitHub (public repo — required deliverable) | |

---

## Stage 0 — Repository & Environment Setup (manual, ~15–20 min)

1. Create GitHub repo `split-settlement-leakage-detector` (must be public)
2. Clone locally, open in Antigravity
3. Folder structure:
   ```
   /data              (generated DB + seed manifest)
   /src               (all Python logic modules)
   /tests             (agent-written test files)
   /dashboard         (Streamlit app)
   SPEC.md
   DEVLOG.md
   ARCHITECTURE.md
   README.md
   ```
4. Set up Python venv; install `pandas`, `streamlit`, `pytest` (sqlite3 is stdlib)
5. Run a trivial Streamlit "hello world" once to confirm the environment works
6. Write `SPEC.md` in full — schema, 4 edge cases, classification rules, stopping rules, required outputs (full content below)
7. Initialize git, first commit: "project scaffold + spec"

### SPEC.md — paste this in full

```markdown
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
```

---

## Stage 1 — Data Generator + Database Schema

**Builds:** `src/data_generator.py`

**Requirements:**
- Creates `data/reconciliation.db` with all 9 tables, proper types + foreign keys
- ~60 synthetic orders, 12 vendors, 2-month window
- Commission slabs with at least one vendor crossing a tier mid-cycle
- Tax rules with a rate transition
- Settlements, refunds, gst_filings, full nodal ledger for every day in range
- Deliberately seeds all 4 edge cases at specific order_ids
- Writes `data/seed_manifest.json`: `{order_id, case_name, description}` per case
- Prints run summary: row counts, date range, seed confirmation

**Antigravity prompt:**
```
Read SPEC.md in this repo fully before doing anything.

Build src/data_generator.py that:
1. Creates the SQLite database reconciliation.db with all tables from SPEC.md
2. Generates 60 synthetic orders across 12 vendors with realistic dates
   over a 2-month window
3. Generates matching commission_slabs, tax_rules (with a rate transition),
   settlements, refunds, gst_filings, and a 60-day nodal_account_ledger
4. Deliberately seeds all 4 edge cases from SPEC.md at specific order_ids
   you choose
5. Writes seed_manifest.json recording exactly which order_id maps to
   which of the 4 seeded cases, with a one-line description of what makes
   each one an edge case
6. Writes a summary printout when run: total orders, date range, tables
   created, row counts

Do not build the matcher or classifier yet — only the generator and schema.
After building, run it and show me the seed_manifest.json contents and
the row counts.
```

**✅ HUMAN CHECKPOINT 1 (do not skip):** Open the DB yourself (Python REPL query or SQLite browser). Manually inspect the 4 seeded rows against `seed_manifest.json`. Confirm the numbers actually represent what they claim (e.g., the slab-change order really straddles the rate change date). Log the result in `DEVLOG.md`. Commit.

---

## Stage 2 — Point-in-Time Rule Engine

**Builds:** `src/rule_engine.py`, `tests/test_rule_engine.py`

**Requirements:**
- `get_applicable_rate(conn, vendor_id, date, rule_type)` — returns the rate in effect on that exact date, handling open-ended ranges (`effective_to IS NULL` = current)
- Tests confirming the slab-change and tax-transition seeded cases resolve correctly on each side of the change

**Antigravity prompt:**
```
Read SPEC.md and seed_manifest.json.

Build src/rule_engine.py with a single function:
get_applicable_rate(conn, vendor_id, date, rule_type)
-> looks up commission_slabs or tax_rules and returns the rate that was
in effect on that exact date (effective_from <= date <= effective_to
or effective_to is null).

Write tests in tests/test_rule_engine.py that specifically check:
- the retroactive slab-change seeded case returns the OLD rate for
  orders before the change and the NEW rate for orders after
- the tax-rate-transition case returns the correct rate on each
  side of the transition date

Run the tests and show me the output before continuing.
```

Read the test output yourself. Commit: "point-in-time rule engine + tests."

*Why this matters: this function is reused for both commission and tax math — a concrete build-quality point for `ARCHITECTURE.md`.*

---

## Stage 3 — Matcher + Classifier

**Builds:** `src/matcher.py`, `src/classifier.py`

**Matcher:** for every order, compute expected settlement (commission + TCS + TDS + logistics via rule engine) vs actual, output the delta.

**Classifier:** bucket non-zero deltas into settlement-math / tax-timing / structural-compliance. Check `gst_filings` before concluding a TCS gap is real leakage. Every exception gets a `reason`, `confidence_score`, written to `exceptions` with `status = 'pending'`.

**Antigravity prompt:**
```
Read SPEC.md, rule_engine.py, and the DB schema.

Build src/matcher.py:
- For every order, compute the EXPECTED settlement amount using
  rule_engine.py (commission + TCS + TDS + logistics)
- Compare to the ACTUAL settlement amount from the settlements table
- Output a per-order diff (expected vs actual, delta amount)

Build src/classifier.py:
- For every order where the diff is non-zero, classify into exactly one
  of: settlement-math exception, tax-timing exception,
  structural/compliance exception, per the rules in SPEC.md
- For tax-timing specifically: check gst_filings.filed_date vs
  settlement_date before concluding it's a real math error
- Assign confidence_score and a plain-English reason string to every
  exception
- Write every exception row into the exceptions table with status
  left as 'pending' — status/stopping-rule logic comes next stage

Run this against the seeded data and show me: total exceptions found,
and specifically whether order_ids for all 4 seeded cases appear with
the correct exception_type.
```

**✅ HUMAN CHECKPOINT 2 (highest value check in the project):** Query the `exceptions` table yourself, filter to the 4 seeded order_ids, confirm each got the exception_type you expected. Log result in `DEVLOG.md`. Commit.

---

## Stage 4 — Stopping Rules & Escalation

**Builds:** `src/escalation.py`, `tests/test_escalation.py`

**Rules:**
- `confidence_score < 0.7` → `needs-review`, never auto-resolved
- `exception_type = structural/compliance` → `escalated`, always, overriding confidence
- Nodal-balance break → `escalated` + audit_log entry noting automated processing halted for that batch date
- Everything else → `auto-cleared`

**Antigravity prompt:**
```
Read SPEC.md's stopping rules section exactly.

Build src/escalation.py that updates the status field on every row in
the exceptions table:
- confidence_score < 0.7 -> needs-review
- exception_type = structural/compliance -> escalated (always,
  overriding confidence)
- any nodal_account_ledger integrity break -> escalated, and log in
  audit_log that automated processing halted for that date's batch
- everything else -> auto-cleared

This must never silently resolve a structural/compliance case regardless
of confidence. Write a test confirming the nodal-balance seeded case
ends up escalated, not auto-cleared.

Run it and show me the status breakdown (counts per status).
```

Check the status counts look sane (not 100% auto-cleared). Commit: "stopping rules + escalation logic."

*This stage is what turns a plain exception list into "compliant escalation" — Razorpay's literal wording.*

---

## Stage 5 — Audit Trail

**Builds:** instrumentation across Stages 1–4, plus `src/audit_report.py`

**Antigravity prompt:**
```
Read SPEC.md's audit trail section.

Instrument data_generator.py, matcher.py, classifier.py, and
escalation.py to each write a row to audit_log for every meaningful
action (stage started, N records processed, N exceptions found,
N escalated, stage completed) with a timestamp and a plain-English
detail string.

Build src/audit_report.py that reads audit_log and prints a clean
chronological summary of the whole pipeline run.

Run the full pipeline end-to-end and show me the audit report output.
```

Read the audit report yourself — confirm it tells a coherent story. Commit: "audit trail instrumentation + report."

---

## Stage 6 — Reporting Layer

**Builds:** `src/report.py`

**Outputs:** match rate, ₹-ranked exception list, counts by type/status, self-skepticism stat (e.g. "X% of exceptions are tax-timing, not real leakage"), pass/fail per seeded case.

**Antigravity prompt:**
```
Read SPEC.md's required outputs section.

Build src/report.py that queries the DB and prints/returns:
- Match rate (% of orders with zero exceptions)
- Full exception list sorted by rupee_impact descending
- Counts by exception_type and by status
- A confirmation section: for each of the 4 seed_manifest.json entries,
  state whether it appears in the exceptions table with the expected
  exception_type (pass/fail per case)

Run it and show me full output.
```

Commit: "reporting layer."

---

## Stage 7 — Streamlit Dashboard (your interaction/demo layer)

**Builds:** `dashboard/app.py`

**Requirements:**
- Top metrics row: match rate, total ₹ leakage, count escalated, count needs-review
- Filterable exception table (vendor / exception_type / status), sorted by rupee_impact
- "Seeded Edge Cases" panel — 4 cases, caught/not-caught indicator from `seed_manifest.json`
- Audit trail viewer (last N entries)
- Button to re-run the pipeline live from within the dashboard — makes your demo a live proof, not a static screenshot

**Antigravity prompt:**
```
Read report.py and the DB schema.

Build dashboard/app.py as a Streamlit app with:
- Top metrics row: match rate, total ₹ leakage, count escalated,
  count needs-review
- Filterable exception table (filter by vendor, exception_type, status),
  sorted by rupee_impact
- A dedicated "Seeded Edge Cases" section listing the 4 planted cases
  and showing each was caught, using seed_manifest.json
- A simple audit trail viewer (last N audit_log entries)
- A button to re-run the full pipeline live from the dashboard

Run it locally and confirm it loads without errors.
```

Click through it yourself before demo time. Commit: "interactive dashboard."

---

## Stage 8 — Documentation (you write this, not the agent)

**`ARCHITECTURE.md` should cover:**
- Data flow diagram (simple boxes-and-arrows is fine)
- Why SQLite over Postgres/Mongo (real joins + versioned effective-date logic + zero-setup portability)
- Why this 3-bucket classification scheme
- Why these 4 edge cases specifically, and what's explicitly out of scope (cut list: weekly-batch unbundling, cross-currency FX, chargebacks split, schema drift, pre-funding detection) framed as "what we'd add next"
- Why the escalation/stopping-rule design exists — ties to Razorpay's "compliant escalation" language

**`DEVLOG.md`** — consolidate the real issues hit at Checkpoint 1 and Checkpoint 2 into a short, honest narrative. This is your raw material for the pitch's "what broke" section.

---

## Stage 9 — Pitch Video (5 minutes)

| Segment | Time | Content |
|---|---|---|
| Problem framing | 0:30 | What split-settlement leakage is, why it's hard to catch |
| Live demo | 2:30 | Dashboard: match rate, ₹ leakage, exception table, filters, escalation working live |
| Seeded cases | 1:00 | Show all 4 planted edge cases caught by name — your strongest, most defensible moment |
| What broke | 1:00 | Pulled straight from DEVLOG.md — one real bug, how you found it, how you fixed it |

Have Streamlit already running and warmed up before recording.

---

## Time Budget

| Stage | % of total time |
|---|---|
| 0: Setup | 5% |
| 1: Data generator + Checkpoint 1 | 15% |
| 2: Rule engine | 10% |
| 3: Matcher + classifier + Checkpoint 2 | 20% |
| 4: Stopping rules + escalation | 15% |
| 5: Audit trail | 10% |
| 6: Reporting | 5% |
| 7: Dashboard | 10% |
| 8–9: Docs + pitch video | 10% |

---

## Non-Negotiable

**Exactly two human checkpoints — no more, no fewer:**
1. After Stage 1 — seed data is actually correct
2. After Stage 3 — all 4 seeded cases classified correctly

Everything else can run through Antigravity with agent-written tests as verification. These two checkpoints are what let you honestly claim, on camera, that this exception list isn't cherry-picked — which is the exact thing Razorpay says they're judging.
