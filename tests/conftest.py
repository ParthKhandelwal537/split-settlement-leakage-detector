import os
import sqlite3
import pytest
from src.data_generator import main as generate_data
from src.classifier import classify_exceptions
from src.escalation import apply_stopping_rules_and_escalate

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reconciliation.db")

@pytest.fixture(scope="session", autouse=True)
def ensure_database_ready():
    """
    Session-level fixture ensuring that data/reconciliation.db is populated
    on a fresh repository clone before any unit or integration tests run.
    """
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)
    
    # If the database file is missing or has zero bytes, generate schema and seed data
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        generate_data()
        conn = sqlite3.connect(DB_PATH)
        try:
            classify_exceptions(conn)
            apply_stopping_rules_and_escalate(conn)
        finally:
            conn.close()
    yield DB_PATH
