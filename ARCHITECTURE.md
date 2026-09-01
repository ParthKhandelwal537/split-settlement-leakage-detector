# Architecture & System Design: Split-Settlement Leakage Detector

## Overview
A financial reconciliation agent designed for Indian marketplace payment-aggregator settlements. It detects split-settlement leakages, classifies anomalies across 3 distinct buckets (Settlement Math, Tax Timing, Structural/Compliance), enforces stopping and escalation rules, and records an auditable trail.

## Tech Stack Decisions
- **Database (SQLite)**: Real SQL joins, explicit foreign keys, point-in-time versioned rule queries, zero-setup portability.
- **Logic (Python + pandas)**: High performance reconciliation math, rate lookup routines, and rule validation.
- **Presentation (Streamlit)**: Live interactive UI with metrics, filterable exception tables, seeded edge case verification, and audit logs.

## Pipeline Architecture
```
[ Synthetic Data / DB (reconciliation.db) ]
                     │
                     ▼
        [ Rule Engine (Point-in-Time) ]
                     │
                     ▼
          [ Matcher & Classifier ]
                     │
                     ▼
     [ Stopping Rules & Escalation Logic ]
                     │
                     ▼
       [ Audit Trail & Reporting Layer ]
                     │
                     ▼
        [ Streamlit Interactive App ]
```
