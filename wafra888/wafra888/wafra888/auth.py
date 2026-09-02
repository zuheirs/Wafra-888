"""جلسات الدخول، الحماية (login_required / leadership_required)، وحماية CSRF.
كل التحقق من الهوية يصير من طرف الخادم فقط — لا كلمة سر ولا مفتاح API بالـ frontend."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import jsonify, redirect, request, session, url_for

from . import repo
from .security import new_csrf_token

MAX_FAILED_ATTEMPTS = 6
LOCKOUT_MINUTES = 10


def current_account() -> dict | None:
    account_id = session.get("account_id")
    if not account_id:
        return None
    acc = repo.get_account_by_id(account_id)
    if not acc or acc["status"] == "deleted":
        session.clear()
        return None
    return acc


def login(account: dict) -> None:
    session.clear()
    session.permanent = True
    session["account_id"] = account["id"]
    session["csrf_token"] = new_csrf_token()


def logout() -> None:
    session.clear()


def is_locked_out(account: dict) -> bool:
    until = account.get("failed_login_until")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > datetime.now(timezone.utc)
    except ValueError:
        return False


def register_failed_attempt(account: dict) -> None:
    count = (account.get("failed_login_count") or 0) + 1
    until = None
    if count >= MAX_FAILED_ATTEMPTS:
        until = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
    repo.record_login_failure(account["id"], count, until)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        acc = current_account()
        if not acc:
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("auth.login_page"))
        return view(*args, **kwargs)

    return wrapped


def leadership_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        acc = current_account()
        if not acc:
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("auth.login_page"))
        if acc["role"] != "leadership":
            return jsonify({"error": "forbidden"}), 403
        return view(*args, **kwargs)

    return wrapped


def csrf_protect(view):
    """يتطلب X-CSRF-Token مطابق للتوكن يلي انولّد وقت تسجيل الدخول — يحمي من CSRF
    على أي طلب POST/PUT/DELETE يغيّر حالة."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.headers.get("X-CSRF-Token")
            expected = session.get("csrf_token")
            if not expected or not sent or sent != expected:
                return jsonify({"error": "csrf_failed"}), 403
        return view(*args, **kwargs)

    return wrapped
