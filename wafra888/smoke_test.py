"""اختبار دخان يدوي بالـ Flask test client — بيغطي تسجيل الدخول، تغيير كلمة السر،
حفظ البروفايل، لوحة الأعضاء، ولوحة القيادة. بيعمل mock لنداءات Anthropic عشان ما
يحتاج مفتاح API حقيقي أو اتصال إنترنت."""
import sys

from wafra888 import ai, create_app, repo
from wafra888.security import slugify


def mock_call_anthropic(messages, system, max_tokens):
    last = messages[-1]["content"] if messages else ""
    if "محلل أنماط" in system or "محلل أنماط" in last or max_tokens == 60:
        return "لا يوجد نمط جديد ملحوظ"
    return "رد تجريبي من الكيان بخصوص: " + last[:30]


ai._call_anthropic = mock_call_anthropic

app = create_app()
app.config.update(TESTING=True)


def check(cond, label):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {label}")
    if not cond:
        sys.exit(1)


with app.test_client() as c:
    # 1) login with wrong password
    r = c.post("/login", data={"name": "فيصل", "password": "wrong"})
    check(r.status_code == 401, "login rejects wrong password")

    # 2) login with default password -> forced to change-password
    r = c.post("/login", data={"name": "فيصل", "password": "0000"}, follow_redirects=False)
    check(r.status_code == 302 and "change-password" in r.headers["Location"], "login redirects to change-password on first login")

    r = c.post("/change-password", data={"password1": "newpass123", "password2": "newpass123"}, follow_redirects=False)
    check(r.status_code == 302, "change password succeeds")

    r = c.get("/api/profile")
    check(r.status_code == 200, "get profile after login")
    csrf = c.get("/").request  # placeholder

    # fetch csrf token from session via a leadership-free endpoint: read cookie session
    with c.session_transaction() as sess:
        token = sess.get("csrf_token")
    check(bool(token), "csrf token present in session after login")

    # 3) save profile without csrf -> rejected
    r = c.post("/api/profile", json={
        "dca": "a", "goal4m": "b", "fear": "c", "give": "d", "want": "e", "patterns": "f", "agreed": True
    })
    check(r.status_code == 403, "profile save without csrf token is rejected")

    # 4) save profile with csrf
    r = c.post("/api/profile", json={
        "dca": "a", "goal4m": "b", "fear": "c", "give": "d", "want": "e", "patterns": "f", "agreed": True
    }, headers={"X-CSRF-Token": token})
    check(r.status_code == 200, f"profile save with csrf token succeeds ({r.status_code} {r.get_data(as_text=True)})")

    # 5) board shows submitted
    r = c.get("/api/board")
    data = r.get_json()
    faisal = next(m for m in data["members"] if m["name"] == "فيصل")
    check(faisal["submitted"] is True, "board reflects submitted profile")

    # 6) chat send (mocked AI) + pattern extraction in background thread
    r = c.post("/api/chat/send", json={"text": "مرحبا"}, headers={"X-CSRF-Token": token})
    check(r.status_code == 200, f"chat send works ({r.get_data(as_text=True)})")

    # 7) member cannot access leadership routes
    r = c.get("/api/leadership/profiles")
    check(r.status_code == 403, "member forbidden from leadership routes")

    c.post("/logout")

    # 8) leadership login flow
    r = c.post("/login", data={"name": "زهير الصباغ", "password": "0000"})
    c.post("/change-password", data={"password1": "leaderpass1", "password2": "leaderpass1"})
    with c.session_transaction() as sess:
        ltoken = sess.get("csrf_token")

    r = c.get("/api/leadership/profiles")
    check(r.status_code == 200, "leadership can list profiles")
    profs = r.get_json()["profiles"]
    check(any(p["name"] == "فيصل" for p in profs), "leadership sees faisal's submitted profile")

    r = c.get("/api/leadership/members")
    check(r.status_code == 200, "leadership can list all members incl. not-yet-submitted")

    r = c.post("/api/leadership/report", headers={"X-CSRF-Token": ltoken})
    check(r.status_code == 200, f"leadership report generation works ({r.get_data(as_text=True)[:80]})")

    r = c.post("/api/leadership/chat/send", json={"text": "شو وضع المجموعة؟"}, headers={"X-CSRF-Token": ltoken})
    check(r.status_code == 200, "leadership free chat works")

    # 9) meetings + attendance -> auto lock on unexcused absence
    r = c.post("/api/leadership/meetings", json={"meeting_date": "2026-09-06", "notes": "لقاء دوري"}, headers={"X-CSRF-Token": ltoken})
    meeting_id = r.get_json()["id"]
    check(r.status_code == 200 and meeting_id, "create meeting works")

    faisal_id = next(m["account_id"] for m in repo.list_all_members_status() if m["name"] == "فيصل")
    r = c.post(f"/api/leadership/meetings/{meeting_id}/attendance", json={
        "records": [{"account_id": faisal_id, "status": "absent_unexcused"}]
    }, headers={"X-CSRF-Token": ltoken})
    check(r.status_code == 200, "submit attendance works")

    faisal_acc = repo.get_account_by_id(faisal_id)
    check(faisal_acc["status"] == "locked_pending_review", "unexcused absence auto-locks the account")

    r = c.get("/api/leadership/notifications")
    notifs = r.get_json()["notifications"]
    check(any(n["type"] == "auto_lock" for n in notifs), "auto-lock notification created")

    # 10) leadership resolves the lock
    r = c.post(f"/api/leadership/accounts/{faisal_id}/resolve", json={"decision": "reactivate", "note": "تواصل واعتذر"}, headers={"X-CSRF-Token": ltoken})
    check(r.status_code == 200, "resolve locked account works")
    faisal_acc = repo.get_account_by_id(faisal_id)
    check(faisal_acc["status"] == "active", "account reactivated after leadership decision")

    # 11) DCA request flow: force a mocked reply containing the tag
    def mock_with_dca(messages, system, max_tokens):
        if max_tokens == 60:
            return "لا يوجد نمط جديد ملحوظ"
        return "تمام، فهمت. [DCA_REQUEST]هدف جديد تجريبي[/DCA_REQUEST]"

    ai._call_anthropic = mock_with_dca
    c.post("/logout")
    c.post("/login", data={"name": "فيصل", "password": "newpass123"})
    with c.session_transaction() as sess:
        ftoken = sess.get("csrf_token")
    r = c.post("/api/chat/send", json={"text": "بدي غيّر الـDCA"}, headers={"X-CSRF-Token": ftoken})
    body = r.get_json()
    check(body.get("dca_request_created") is True, "DCA change request detected and created")
    check("[DCA_REQUEST]" not in body["reply"], "DCA tag stripped from member-visible reply")

    c.post("/logout")
    c.post("/login", data={"name": "زهير الصباغ", "password": "leaderpass1"})
    with c.session_transaction() as sess:
        ltoken2 = sess.get("csrf_token")
    r = c.get("/api/leadership/requests?status=pending")
    reqs = r.get_json()["requests"]
    check(any(x["requested_dca"] == "هدف جديد تجريبي" for x in reqs), "pending DCA request visible to leadership")

print("\nALL SMOKE TESTS PASSED")
