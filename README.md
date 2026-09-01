# Split-Settlement Leakage Detector

Reconciliation agent for Indian marketplace payment-aggregator settlements. Closes one finance-ops loop across synthetic transaction batches, catching settlement math errors, tax timing discrepancies (GSTR-8 filing lag), and nodal account balance breaks.

## Repository Layout
- `data/`: SQLite database `reconciliation.db` and `seed_manifest.json`
- `src/`: Python pipeline modules (`data_generator.py`, `rule_engine.py`, `matcher.py`, `classifier.py`, `escalation.py`, `audit_report.py`, `report.py`)
- `tests/`: Automated unit & reconciliation test suites
- `dashboard/`: Streamlit dashboard (`app.py`)
- `SPEC.md`: Full project specification and schema definition
- `DEVLOG.md`: Development log and human checkpoint records
- `ARCHITECTURE.md`: Technical architectural decisions and pipeline flow

## Getting Started
```bash
# Install dependencies
pip install pandas streamlit pytest

# Run tests
pytest

# Launch dashboard
streamlit run dashboard/app.py
```
