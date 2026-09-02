from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from .. import auth, repo
from ..constitution import CHARTER_AGREEMENT_TEXT, CHARTER_RULES, VALUES
from ..security import hash_password, slugify, verify_password

bp = Blueprint("auth", __name__)


@bp.get("/")
def index():
    acc = auth.current_account()
    if not acc:
        return redirect(url_for("auth.login_page"))
    if acc["must_change_password"]:
        return redirect(url_for("auth.change_password_page"))
    if acc["status"] != "active":
        return render_template("locked.html", account=acc)
    return render_template(
        "app.html",
        account=acc,
        csrf_token=session.get("csrf_token"),
        charter_rules=CHARTER_RULES,
        charter_agreement_text=CHARTER_AGREEMENT_TEXT,
        values=VALUES,
    )


@bp.get("/login")
def login_page():
    if auth.current_account():
        return redirect(url_for("auth.index"))
    return render_template("login.html")


@bp.post("/login")
def login_submit():
    name = (request.form.get("name") or "").strip()
    password = request.form.get("password") or ""
    error = None

    if not name or not password:
        error = "الاسم أو كلمة السر غير صحيحة، أو اسمك مو مسجل بالماسترمايند بعد."
    else:
        slug = slugify(name)
        acc = repo.get_account_by_slug(slug)
        if not acc:
            error = "الاسم أو كلمة السر غير صحيحة، أو اسمك مو مسجل بالماسترمايند بعد."
        elif auth.is_locked_out(acc):
            error = "الحساب موقوف مؤقتاً بسبب محاولات دخول خاطئة متكررة. جرّب بعد شوي."
        elif not verify_password(password, acc["password_hash"]):
            auth.register_failed_attempt(acc)
            error = "الاسم أو كلمة السر غير صحيحة، أو اسمك مو مسجل بالماسترمايند بعد."
        elif acc["status"] == "deleted":
            error = "هالحساب مو فعّال حالياً. تواصل مع القيادة."
        else:
            repo.record_login_success(acc["id"])
            auth.login(acc)
            if acc["status"] != "active":
                return redirect(url_for("auth.index"))
            if acc["must_change_password"]:
                return redirect(url_for("auth.change_password_page"))
            return redirect(url_for("auth.index"))

    return render_template("login.html", error=error, name=name), 401 if error else 200


@bp.get("/change-password")
def change_password_page():
    acc = auth.current_account()
    if not acc:
        return redirect(url_for("auth.login_page"))
    if not acc["must_change_password"]:
        return redirect(url_for("auth.index"))
    return render_template("change_password.html", account=acc)


@bp.post("/change-password")
def change_password_submit():
    acc = auth.current_account()
    if not acc:
        return redirect(url_for("auth.login_page"))
    p1 = request.form.get("password1") or ""
    p2 = request.form.get("password2") or ""
    if not p1 or p1 != p2 or len(p1) < 4:
        return render_template(
            "change_password.html",
            account=acc,
            error="الكلمتين مو متطابقين، أو كلمة السر قصيرة كتير (لازم 4 محارف عالأقل).",
        )
    repo.update_password(acc["id"], hash_password(p1))
    return redirect(url_for("auth.index"))


@bp.post("/logout")
def logout():
    auth.logout()
    return redirect(url_for("auth.login_page"))
