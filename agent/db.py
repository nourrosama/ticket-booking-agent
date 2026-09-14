"""
Single-file SQLite, no ORM: each call opens a connection, runs its
query, and closes it. Fine at this scale (single user, local file) —
no pooling needed.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "travel.sqlite"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn