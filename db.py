import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "inmocrm.db")

# Si existe DATABASE_URL (en Render/Neon) usamos Postgres; si no, SQLite local.
DATABASE_URL = os.environ.get("DATABASE_URL")
IS_PG = bool(DATABASE_URL)

if IS_PG:
    import psycopg
    from psycopg.rows import dict_row


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Conn:
    """Envoltorio fino para que el resto del código funcione igual en SQLite y Postgres.
    Las consultas se escriben con '?' y acá se traducen a '%s' cuando es Postgres."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        if IS_PG:
            sql = sql.replace("?", "%s")
        return self.raw.execute(sql, params)

    def insert_id(self, sql, params=()):
        """INSERT que devuelve el id de la fila nueva (compatible con ambas bases)."""
        if IS_PG:
            sql = sql.replace("?", "%s") + " RETURNING id"
            cur = self.raw.execute(sql, params)
            return cur.fetchone()["id"]
        cur = self.raw.execute(sql, params)
        return cur.lastrowid

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()


def get_db():
    if IS_PG:
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return Conn(raw)
    raw = sqlite3.connect(DB_PATH)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    return Conn(raw)


def init_db():
    id_col = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS clients (
            id {id_col},
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS properties (
            id {id_col},
            client_id INTEGER NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            title TEXT,
            price TEXT,
            image TEXT,
            bedrooms TEXT,
            area TEXT,
            location TEXT,
            description TEXT,
            position INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pendiente',
            comment TEXT,
            responded_at TEXT,
            expenses TEXT,
            visited_at TEXT,
            visit_comment TEXT,
            created_at TEXT NOT NULL
        )
        """,
    ]
    conn = get_db()
    for s in statements:
        conn.execute(s)
    _ensure_column(conn, "properties", "expenses", "TEXT")
    _ensure_column(conn, "properties", "visited_at", "TEXT")
    _ensure_column(conn, "properties", "visit_comment", "TEXT")
    conn.commit()
    conn.close()


def _ensure_column(conn, table, col, coltype):
    """Agrega una columna si falta (para bases ya creadas). Compatible SQLite/Postgres."""
    if IS_PG:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {coltype}")
        return
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
