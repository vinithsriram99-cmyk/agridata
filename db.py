"""Shared SQLite helper. SQLite is used so nothing needs installing."""
import math
import os
import sqlite3

DB_PATH = os.getenv("AGRI_DB", "agri.db")


def _sqrt(x):
    # SQLite may lack SQRT; PostgreSQL / MySQL have it built in. Returns NULL for x <= 0
    return math.sqrt(x) if x is not None and x > 0 else None


def connect():
    con = sqlite3.connect(DB_PATH)
    con.create_function("SQRT", 1, _sqrt)
    return con
