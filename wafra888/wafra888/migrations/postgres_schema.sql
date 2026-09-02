-- وفرة 888 — سكيما Postgres (مثلاً لمشروع Supabase)
-- شغّل هالملف كامل مرة وحدة بـ SQL editor تبع Supabase (أو أي Postgres) قبل تشغيل التطبيق
-- مع DATABASE_URL مضبوط. الأعمدة نفسها متطابقة مع نسخة SQLite يلي التطبيق ينشئها تلقائياً
-- (wafra888/db.py) عشان نفس كود التطبيق يشتغل بدون أي فرق منطقي بين المحرّكين.

CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    role TEXT NOT NULL CHECK (role IN ('member','leadership')),
    password_hash TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','locked_pending_review','frozen','deleted')),
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
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leader_chat_messages (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pattern_notes (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dca_requests (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    current_dca TEXT,
    requested_dca TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    decided_by INTEGER REFERENCES accounts(id),
    decided_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meetings (
    id SERIAL PRIMARY KEY,
    meeting_date TEXT NOT NULL,
    notes TEXT,
    created_by INTEGER REFERENCES accounts(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (
        status IN ('present','absent_excused','absent_unexcused','left_early','frequent_excuse')
    ),
    note TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (meeting_id, account_id)
);

CREATE TABLE IF NOT EXISTS account_status_log (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    actor_id INTEGER REFERENCES accounts(id),
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
