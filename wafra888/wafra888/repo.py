"""طبقة الوصول لبيانات كل كيان (accounts, profiles, chat...) — SQL موحّد يشتغل
على SQLite و Postgres عن طريق wafra888.db."""
from __future__ import annotations

from datetime import datetime, timezone

from . import db


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------- accounts ----------------------------

def get_account_by_slug(slug: str) -> dict | None:
    return db.query_one("SELECT * FROM accounts WHERE slug = ?", (slug,))


def get_account_by_id(account_id: int) -> dict | None:
    return db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))


def create_account(slug: str, name: str, role: str, password_hash: str) -> int:
    ts = now_iso()
    return db.insert_returning_id(
        "accounts",
        {
            "slug": slug,
            "name": name,
            "role": role,
            "password_hash": password_hash,
            "must_change_password": 1,
            "status": "active",
            "failed_login_count": 0,
            "created_at": ts,
            "updated_at": ts,
        },
    )


def list_accounts() -> list[dict]:
    return db.query("SELECT * FROM accounts ORDER BY name")


def update_password(account_id: int, password_hash: str) -> None:
    db.execute(
        "UPDATE accounts SET password_hash = ?, must_change_password = 0, updated_at = ? WHERE id = ?",
        (password_hash, now_iso(), account_id),
    )


def record_login_success(account_id: int) -> None:
    db.execute(
        "UPDATE accounts SET failed_login_count = 0, failed_login_until = NULL WHERE id = ?",
        (account_id,),
    )


def record_login_failure(account_id: int, count: int, until: str | None) -> None:
    db.execute(
        "UPDATE accounts SET failed_login_count = ?, failed_login_until = ? WHERE id = ?",
        (count, until, account_id),
    )


def set_account_status(account_id: int, status: str, note: str | None = None, frozen_until: str | None = None) -> None:
    db.execute(
        "UPDATE accounts SET status = ?, status_note = ?, frozen_until = ?, updated_at = ? WHERE id = ?",
        (status, note, frozen_until, now_iso(), account_id),
    )


def set_account_phone(account_id: int, phone: str | None) -> None:
    db.execute("UPDATE accounts SET phone = ?, updated_at = ? WHERE id = ?", (phone, now_iso(), account_id))


def log_status_change(account_id: int, action: str, actor_id: int | None, detail: str | None) -> None:
    db.insert_returning_id(
        "account_status_log",
        {
            "account_id": account_id,
            "action": action,
            "actor_id": actor_id,
            "detail": detail,
            "created_at": now_iso(),
        },
    )


# ---------------------------- profiles ----------------------------

def get_profile(account_id: int) -> dict | None:
    return db.query_one("SELECT * FROM profiles WHERE account_id = ?", (account_id,))


def upsert_profile(account_id: int, fields: dict) -> None:
    existing = get_profile(account_id)
    ts = now_iso()
    if existing:
        db.execute(
            """UPDATE profiles SET dca=?, goal4m=?, fear=?, give=?, want=?, patterns=?,
               agreed=?, updated_at=? WHERE account_id=?""",
            (
                fields["dca"], fields["goal4m"], fields["fear"], fields["give"],
                fields["want"], fields["patterns"], 1 if fields.get("agreed") else 0,
                ts, account_id,
            ),
        )
    else:
        db.execute(
            """INSERT INTO profiles (account_id, dca, goal4m, fear, give, want, patterns, agreed, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                account_id, fields["dca"], fields["goal4m"], fields["fear"], fields["give"],
                fields["want"], fields["patterns"], 1 if fields.get("agreed") else 0, ts,
            ),
        )


def list_profiles_with_names() -> list[dict]:
    return db.query(
        """SELECT a.id as account_id, a.name, a.role, a.status,
                  p.dca, p.goal4m, p.fear, p.give, p.want, p.patterns, p.agreed, p.updated_at
           FROM accounts a JOIN profiles p ON p.account_id = a.id
           ORDER BY p.updated_at DESC"""
    )


def list_all_members_status() -> list[dict]:
    """كل الأعضاء (حتى يلي لسا ما قدّموا الفورم) — للوحة الأعضاء العامة ولوحة القيادة."""
    return db.query(
        """SELECT a.id as account_id, a.name, a.role, a.status,
                  p.updated_at as submitted_at
           FROM accounts a LEFT JOIN profiles p ON p.account_id = a.id
           ORDER BY a.name"""
    )


# ---------------------------- chat (private, per member) ----------------------------

def get_chat_history(account_id: int, limit: int = 200) -> list[dict]:
    # لازم آخر limit رسالة (الأحدث)، بترتيب زمني تصاعدي — مو أول limit رسالة من
    # بداية المحادثة. لو المحادثة أطول من limit وما رجعنا آخر الرسائل، ممكن ننسى
    # آخر رد من الكيان (assistant) ونرسل لـ Gemini محادثة تنتهي بدور المستخدم
    # مكرر، أو حتى تنتهي بدور الكيان القديم — وGemini بيرفض هيك طلبات بخطأ 400.
    rows = db.query(
        "SELECT role, content, created_at, id FROM chat_messages WHERE account_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (account_id, limit),
    )
    rows.reverse()
    return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]} for r in rows]


def append_chat_message(account_id: int, role: str, content: str) -> None:
    db.insert_returning_id(
        "chat_messages",
        {"account_id": account_id, "role": role, "content": content, "created_at": now_iso()},
    )


# ---------------------------- leadership free chat ----------------------------

def get_leader_chat_history(account_id: int, limit: int = 200) -> list[dict]:
    rows = db.query(
        "SELECT role, content, created_at, id FROM leader_chat_messages WHERE account_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (account_id, limit),
    )
    rows.reverse()
    return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]} for r in rows]


def append_leader_chat_message(account_id: int, role: str, content: str) -> None:
    db.insert_returning_id(
        "leader_chat_messages",
        {"account_id": account_id, "role": role, "content": content, "created_at": now_iso()},
    )


# ---------------------------- patterns ----------------------------

def add_pattern_note(account_id: int, note: str) -> None:
    db.insert_returning_id(
        "pattern_notes",
        {"account_id": account_id, "note": note, "created_at": now_iso()},
    )


def list_patterns_grouped() -> list[dict]:
    rows = db.query(
        """SELECT pn.account_id, a.name, pn.note, pn.created_at
           FROM pattern_notes pn JOIN accounts a ON a.id = pn.account_id
           ORDER BY pn.account_id, pn.created_at DESC"""
    )
    grouped: dict[int, dict] = {}
    for r in rows:
        g = grouped.setdefault(r["account_id"], {"account_id": r["account_id"], "name": r["name"], "notes": []})
        g["notes"].append({"text": r["note"], "created_at": r["created_at"]})
    return list(grouped.values())


# ---------------------------- DCA requests ----------------------------

def create_dca_request(account_id: int, current_dca: str, requested_dca: str) -> int:
    return db.insert_returning_id(
        "dca_requests",
        {
            "account_id": account_id,
            "current_dca": current_dca,
            "requested_dca": requested_dca,
            "status": "pending",
            "created_at": now_iso(),
        },
    )


def list_dca_requests(status: str | None = None) -> list[dict]:
    if status:
        return db.query(
            """SELECT r.*, a.name FROM dca_requests r JOIN accounts a ON a.id = r.account_id
               WHERE r.status = ? ORDER BY r.created_at DESC""",
            (status,),
        )
    return db.query(
        """SELECT r.*, a.name FROM dca_requests r JOIN accounts a ON a.id = r.account_id
           ORDER BY r.created_at DESC"""
    )


def get_dca_request(request_id: int) -> dict | None:
    return db.query_one("SELECT * FROM dca_requests WHERE id = ?", (request_id,))


def decide_dca_request(request_id: int, approve: bool, decided_by: int) -> None:
    db.execute(
        "UPDATE dca_requests SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
        ("approved" if approve else "rejected", decided_by, now_iso(), request_id),
    )


# ---------------------------- meetings & attendance ----------------------------

def create_meeting(meeting_date: str, notes: str, created_by: int) -> int:
    return db.insert_returning_id(
        "meetings",
        {"meeting_date": meeting_date, "notes": notes, "created_by": created_by, "created_at": now_iso()},
    )


def list_meetings() -> list[dict]:
    return db.query("SELECT * FROM meetings ORDER BY meeting_date DESC")


def get_meeting(meeting_id: int) -> dict | None:
    return db.query_one("SELECT * FROM meetings WHERE id = ?", (meeting_id,))


def upsert_attendance(meeting_id: int, account_id: int, status: str, note: str | None) -> None:
    existing = db.query_one(
        "SELECT id FROM attendance WHERE meeting_id = ? AND account_id = ?", (meeting_id, account_id)
    )
    if existing:
        db.execute(
            "UPDATE attendance SET status = ?, note = ? WHERE id = ?",
            (status, note, existing["id"]),
        )
    else:
        db.insert_returning_id(
            "attendance",
            {
                "meeting_id": meeting_id, "account_id": account_id, "status": status,
                "note": note, "created_at": now_iso(),
            },
        )


def list_attendance_for_meeting(meeting_id: int) -> list[dict]:
    return db.query(
        """SELECT att.*, a.name FROM attendance att JOIN accounts a ON a.id = att.account_id
           WHERE att.meeting_id = ? ORDER BY a.name""",
        (meeting_id,),
    )


def list_attendance_for_account(account_id: int) -> list[dict]:
    return db.query(
        """SELECT att.*, m.meeting_date FROM attendance att JOIN meetings m ON m.id = att.meeting_id
           WHERE att.account_id = ? ORDER BY m.meeting_date DESC""",
        (account_id,),
    )


# ---------------------------- notifications ----------------------------

def add_notification(ntype: str, account_id: int | None, message: str) -> None:
    db.insert_returning_id(
        "notifications",
        {"type": ntype, "account_id": account_id, "message": message, "is_read": 0, "created_at": now_iso()},
    )


def list_notifications(unread_only: bool = False) -> list[dict]:
    if unread_only:
        return db.query(
            """SELECT n.*, a.name FROM notifications n LEFT JOIN accounts a ON a.id = n.account_id
               WHERE n.is_read = 0 ORDER BY n.created_at DESC"""
        )
    return db.query(
        """SELECT n.*, a.name FROM notifications n LEFT JOIN accounts a ON a.id = n.account_id
           ORDER BY n.created_at DESC LIMIT 200"""
    )


def mark_notification_read(notification_id: int) -> None:
    db.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
