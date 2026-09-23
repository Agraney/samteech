import sqlite3
import json
from contextlib import contextmanager
from typing import Generator, Any, List, Dict
from app.config import DB_PATH

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT NOT NULL,
    notes TEXT,
    summary_json TEXT
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rating TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    material_name TEXT NOT NULL,
    material_type TEXT,
    size TEXT,
    unit TEXT,
    min_reorder_level REAL DEFAULT 0.0,
    CONSTRAINT uq_material UNIQUE (rating, sheet_name, material_name)
);

CREATE TABLE IF NOT EXISTS stock_master_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    material_id INTEGER NOT NULL REFERENCES materials(id),
    opening_balance REAL DEFAULT 0.0,
    received_qty REAL DEFAULT 0.0,
    rate REAL DEFAULT 0.0,
    value REAL DEFAULT 0.0,
    issued_qty REAL DEFAULT 0.0,
    closing_balance REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS stock_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    material_id INTEGER NOT NULL REFERENCES materials(id),
    s_no INTEGER,
    date TEXT,
    opening_balance REAL DEFAULT 0.0,
    received_qty REAL DEFAULT 0.0,
    rate REAL DEFAULT 0.0,
    value REAL DEFAULT 0.0,
    supplier_name TEXT,
    invoice_no TEXT,
    issued_qty REAL DEFAULT 0.0,
    issued_to_section TEXT,
    closing_balance REAL DEFAULT 0.0,
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS production_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    section TEXT NOT NULL,
    rating TEXT NOT NULL,
    units_produced REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS consumption_norms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    rating TEXT NOT NULL,
    material_name TEXT NOT NULL,
    qty_per_transformer REAL DEFAULT 0.0,
    unit TEXT
);

CREATE TABLE IF NOT EXISTS production_monthly_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    rating TEXT NOT NULL,
    month TEXT NOT NULL,
    target_units REAL DEFAULT 0.0,
    actual_units REAL DEFAULT 0.0,
    variance_units REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS bom_specifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    rating TEXT NOT NULL,
    material_name TEXT NOT NULL,
    material_type TEXT,
    size TEXT,
    pieces_count REAL DEFAULT 1.0,
    qty_per_coil REAL DEFAULT 0.0,
    qty_per_transformer REAL DEFAULT 0.0,
    unit TEXT
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sql_query TEXT,
    sql_results_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_master_snap ON stock_master_snapshots(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_stock_trans_snap ON stock_transactions(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_stock_trans_mat ON stock_transactions(material_id);
CREATE INDEX IF NOT EXISTS idx_stock_trans_date ON stock_transactions(date);
CREATE INDEX IF NOT EXISTS idx_prod_entries_snap ON production_entries(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_prod_entries_date ON production_entries(date);
CREATE INDEX IF NOT EXISTS idx_prod_entries_sec ON production_entries(section);
CREATE INDEX IF NOT EXISTS idx_materials_rating ON materials(rating);
CREATE INDEX IF NOT EXISTS idx_prod_monthly_snap ON production_monthly_targets(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_bom_spec_snap ON bom_specifications(snapshot_id);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db() -> None:
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)

def query_all(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]

def query_one(query: str, params: tuple = ()) -> Dict[str, Any] | None:
    with get_db() as conn:
        cur = conn.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None

def execute_write(query: str, params: tuple = ()) -> int:
    with get_db() as conn:
        cur = conn.execute(query, params)
        return cur.lastrowid
