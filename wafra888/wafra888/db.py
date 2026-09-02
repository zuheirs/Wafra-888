"""
طبقة قاعدة بيانات حقيقية تدعم SQLite (افتراضي، صفر إعداد) أو Postgres
(لو حطيت DATABASE_URL — مثلاً مشروع Supabase). كل الكود فوقها بيستخدم نفس
الواجهة بغض النظر عن المحرّك.

- SQLite: بيتنشئ الجداول تلقائياً أول ما التطبيق يشتغل (init_db).
- Postgres: لازم تشغّل migrations/postgres_schema.sql مرة وحدة يدوياً
  (مثلاً بـ SQL editor تبع Supabase) قبل ما تشغّل التطبيق — راجع README.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

try:  # pragma: no cover - optional dependency, only needed for Postgres
    import psycopg
    from psycopg.rows import dict_row

    HAS_PSYCOPG = True
except ImportError:  # pragma: no cover
    HAS_PSYCOPG = False


def init_app(app):
    app.teardown_appcontext(_close_conn)
    with app.app_context():
        if not _is_postgres():
            init_sqlite_schema()


def _is_postgres() -> bool:
    return bool(current_app.config.get("DATABASE_URL"))


def get_conn():
    if "db_conn" not in g:
        if _is_postgres():
            if not HAS_PSYCOPG:
                raise RuntimeError(
                    "DATABASE_URL مضبوط لكن مكتبة psycopg مو مثبتة. "
                    "شيل التعليق عن psycopg[binary] بملف requirements.txt وثبّتها."
                )
            g.db_conn = psycopg.connect(
                current_app.config["DATABASE_URL"], row_factory=dict_row
            )
        else:
            root = Path(current_app.root_path).resolve().parent
            path = current_app.config.get("SQLITE_PATH", "wafra888.db")
            full_path = path if Path(path).is_absolute() else str(root / path)
            conn = sqlite3.connect(full_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            g.db_conn = conn
    return g.db_conn


def _close_conn(exc=None):
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


def _adapt_sql(sql: str) -> str:
    """يحوّل placeholders '?' إلى '%s' لما نكون على Postgres."""
    if _is_postgres():
        return sql.replace("?", "%s")
    return sql


def _row_to_dict(row) -> dict:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return dict(row)  # sqlite3.Row supports dict()


@contextmanager
def _cursor():
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()


def execute(sql: str, params: tuple = ()) -> None:
    conn = get_conn()
    with _cursor() as cur:
        cur.execute(_adapt_sql(sql), params)
    conn.commit()


def insert_returning_id(table: str, values: dict) -> int:
    """INSERT سطر واحد ويرجّع الـ id تبعه، بيشتغل على SQLite و Postgres."""
    cols = list(values.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    conn = get_conn()
    if _is_postgres():
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) RETURNING id"
        with _cursor() as cur:
            cur.execute(_adapt_sql(sql), tuple(values.values()))
            new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id
    else:
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
        with _cursor() as cur:
            cur.execute(sql, tuple(values.values()))
            new_id = cur.lastrowid
        conn.commit()
        return new_id


def query(sql: str, params: tuple = ()) -> list[dict]:
    with _cursor() as cur:
        cur.execute(_adapt_sql(sql), params)
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]


def query_one(sql: str, params: tuple = ()) -> dict | None:
    with _cursor() as cur:
        cur.execute(_adapt_sql(sql), params)
        row = cur.fetchone()
        return _row_to_dict(row)


# ===================== SQLite bootstrap =====================

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    role TEXT NOT NULL CHECK(role IN ('member','leadership')),
    password_hash TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active','locked_pending_review','frozen','deleted')),
    status_note TEXT,
    frozen_until TEXT,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    failed_login_until TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    account_id INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    dca TEXT, goal4m TEXT, fear TEXT, give TEXT, want TEXT, patterns TEXT,
    agreed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leader_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pattern_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dca_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    current_dca TEXT,
    requested_dca TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
    decided_by INTEGER REFERENCES accounts(id),
    decided_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_date TEXT NOT NULL,
    notes TEXT,
    created_by INTEGER REFERENCES accounts(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(
        status IN ('present','absent_excused','absent_unexcused','left_early','frequent_excuse')
    ),
    note TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(meeting_id, account_id)
);

CREATE TABLE IF NOT EXISTS account_status_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    actor_id INTEGER REFERENCES accounts(id),
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


def init_sqlite_schema():
    conn = get_conn()
    conn.executescript(SQLITE_SCHEMA)
    conn.commit()
