from flask import Blueprint, jsonify, request

from .. import auth, repo
from ..ai import AIError, leadership_chat, leadership_report

bp = Blueprint("leadership", __name__, url_prefix="/api/leadership")


# ---------------------------- profiles / patterns ----------------------------

@bp.get("/profiles")
@auth.leadership_required
def profiles():
    return jsonify({"profiles": repo.list_profiles_with_names()})


@bp.get("/members")
@auth.leadership_required
def members():
    """كل الأعضاء (حتى يلي لسا ما قدّموا) — للاستخدام بشاشات الحضور والتذكيرات."""
    return jsonify({"members": repo.list_all_members_status()})


@bp.post("/members/<int:account_id>/phone")
@auth.leadership_required
@auth.csrf_protect
def set_phone(account_id: int):
    data = request.get_json(silent=True) or {}
    phone = (data.get("phone") or "").strip() or None
    repo.set_account_phone(account_id, phone)
    return jsonify({"status": "ok"})


@bp.get("/patterns")
@auth.leadership_required
def patterns():
    return jsonify({"patterns": repo.list_patterns_grouped()})


# ---------------------------- DCA change requests ----------------------------

@bp.get("/requests")
@auth.leadership_required
def dca_requests():
    status = request.args.get("status")
    return jsonify({"requests": repo.list_dca_requests(status)})


@bp.post("/requests/<int:request_id>/decide")
@auth.leadership_required
@auth.csrf_protect
def decide_request(request_id: int):
    data = request.get_json(silent=True) or {}
    approve = bool(data.get("approve"))
    req = repo.get_dca_request(request_id)
    if not req:
        return jsonify({"error": "not_found"}), 404
    actor = auth.current_account()
    repo.decide_dca_request(request_id, approve, actor["id"])
    if approve:
        profile = repo.get_profile(req["account_id"]) or {}
        fields = {
            "dca": req["requested_dca"],
            "goal4m": profile.get("goal4m") or "",
            "fear": profile.get("fear") or "",
            "give": profile.get("give") or "",
            "want": profile.get("want") or "",
            "patterns": profile.get("patterns") or "",
            "agreed": True,
        }
        repo.upsert_profile(req["account_id"], fields)
    return jsonify({"status": "ok"})


# ---------------------------- AI report & free chat ----------------------------

@bp.post("/report")
@auth.leadership_required
@auth.csrf_protect
def generate_report():
    records = repo.list_profiles_with_names()
    if not records:
        return jsonify({"report": "لا يوجد أعضاء مسجلين بعد."})
    try:
        report = leadership_report(records)
    except AIError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"report": report})


@bp.get("/chat/history")
@auth.leadership_required
def leader_chat_history():
    acc = auth.current_account()
    return jsonify({"messages": repo.get_leader_chat_history(acc["id"])})


@bp.post("/chat/send")
@auth.leadership_required
@auth.csrf_protect
def leader_chat_send():
    acc = auth.current_account()
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "الرسالة فاضية"}), 400
    records = repo.list_profiles_with_names()
    try:
        reply = leadership_chat(acc, text, records)
    except AIError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"reply": reply})


# ---------------------------- meetings & attendance ----------------------------

@bp.get("/meetings")
@auth.leadership_required
def meetings():
    return jsonify({"meetings": repo.list_meetings()})


@bp.post("/meetings")
@auth.leadership_required
@auth.csrf_protect
def create_meeting():
    data = request.get_json(silent=True) or {}
    meeting_date = (data.get("meeting_date") or "").strip()
    notes = (data.get("notes") or "").strip()
    if not meeting_date:
        return jsonify({"error": "لازم تاريخ الاجتماع"}), 400
    acc = auth.current_account()
    meeting_id = repo.create_meeting(meeting_date, notes, acc["id"])
    return jsonify({"id": meeting_id})


@bp.get("/meetings/<int:meeting_id>/attendance")
@auth.leadership_required
def meeting_attendance(meeting_id: int):
    meeting = repo.get_meeting(meeting_id)
    if not meeting:
        return jsonify({"error": "not_found"}), 404
    existing = {a["account_id"]: a for a in repo.list_attendance_for_meeting(meeting_id)}
    all_members = repo.list_all_members_status()
    rows = []
    for m in all_members:
        att = existing.get(m["account_id"])
        rows.append(
            {
                "account_id": m["account_id"],
                "name": m["name"],
                "status": att["status"] if att else None,
                "note": att["note"] if att else None,
            }
        )
    return jsonify({"meeting": meeting, "attendance": rows})


VALID_ATTENDANCE_STATUSES = {
    "present", "absent_excused", "absent_unexcused", "left_early", "frequent_excuse"
}


@bp.post("/meetings/<int:meeting_id>/attendance")
@auth.leadership_required
@auth.csrf_protect
def submit_attendance(meeting_id: int):
    meeting = repo.get_meeting(meeting_id)
    if not meeting:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    records = data.get("records") or []
    actor = auth.current_account()

    for rec in records:
        account_id = rec.get("account_id")
        status = rec.get("status")
        note = (rec.get("note") or "").strip() or None
        if not account_id or status not in VALID_ATTENDANCE_STATUSES:
            continue
        repo.upsert_attendance(meeting_id, account_id, status, note)

        member = repo.get_account_by_id(account_id)
        if not member:
            continue

        if status == "absent_unexcused":
            # غياب بدون اعتذار مسبق → قفل تلقائي للحساب بانتظار قرار القيادة
            repo.set_account_status(
                account_id, "locked_pending_review",
                note=f"غياب بدون اعتذار مسبق عن اجتماع {meeting['meeting_date']}",
            )
            repo.log_status_change(
                account_id, "locked", actor["id"],
                f"غياب بدون اعتذار عن اجتماع {meeting['meeting_date']}",
            )
            repo.add_notification(
                "auto_lock", account_id,
                f"تم قفل حساب {member['name']} تلقائياً بسبب غياب بدون اعتذار مسبق "
                f"عن اجتماع {meeting['meeting_date']}. بانتظار قرارك.",
            )
        elif status in ("left_early", "frequent_excuse"):
            # تنبيه فقط، بدون قفل تلقائي
            label = "غادر الاجتماع بدري" if status == "left_early" else "كثّر الأعذار"
            repo.add_notification(
                "attendance_alert", account_id,
                f"{member['name']}: {label} — اجتماع {meeting['meeting_date']}"
                + (f" ({note})" if note else ""),
            )

    return jsonify({"status": "ok"})


# ---------------------------- account status (lock/freeze/delete) ----------------------------

@bp.get("/accounts/flagged")
@auth.leadership_required
def flagged_accounts():
    all_accounts = repo.list_accounts()
    flagged = [a for a in all_accounts if a["status"] != "active"]
    return jsonify({"accounts": flagged})


@bp.post("/accounts/<int:account_id>/resolve")
@auth.leadership_required
@auth.csrf_protect
def resolve_account(account_id: int):
    member = repo.get_account_by_id(account_id)
    if not member:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    decision = data.get("decision")
    note = (data.get("note") or "").strip() or None
    actor = auth.current_account()

    if decision == "reactivate":
        repo.set_account_status(account_id, "active", note=note)
        repo.log_status_change(account_id, "reactivated", actor["id"], note)
    elif decision == "freeze":
        freeze_until = (data.get("freeze_until") or "").strip() or None
        repo.set_account_status(account_id, "frozen", note=note, frozen_until=freeze_until)
        repo.log_status_change(account_id, "frozen", actor["id"], note)
    elif decision == "delete":
        repo.set_account_status(account_id, "deleted", note=note)
        repo.log_status_change(account_id, "deleted", actor["id"], note)
    else:
        return jsonify({"error": "decision غير معروف"}), 400

    return jsonify({"status": "ok"})


# ---------------------------- notifications ----------------------------

@bp.get("/notifications")
@auth.leadership_required
def notifications():
    unread_only = request.args.get("unread") == "1"
    return jsonify({"notifications": repo.list_notifications(unread_only)})


@bp.post("/notifications/<int:notification_id>/read")
@auth.leadership_required
@auth.csrf_protect
def mark_read(notification_id: int):
    repo.mark_notification_read(notification_id)
    return jsonify({"status": "ok"})


# ---------------------------- reminders (manual WhatsApp helper) ----------------------------

@bp.get("/reminders")
@auth.leadership_required
def reminders():
    """أعضاء يحتاجوا تذكير يدوي عالواتساب: لسا ما قدّموا الفورم، أو حسابهم موقوف/مجمّد.
    ما في حل واتساب آلي مجاني بهالحجم — القيادة ترسل يدوياً، وهاد بس بيسهّل الموضوع
    برابط wa.me جاهز لو رقم الهاتف مسجّل."""
    all_members = repo.list_all_members_status()
    all_accounts = {a["id"]: a for a in repo.list_accounts()}
    result = []
    for m in all_members:
        acc = all_accounts.get(m["account_id"], {})
        needs_reminder = (not m["submitted_at"]) or (m["status"] != "active")
        if not needs_reminder:
            continue
        phone = (acc.get("phone") or "").strip()
        wa_link = None
        if phone:
            digits = "".join(ch for ch in phone if ch.isdigit())
            text = (
                f"أهلاً {m['name']}، من وفرة 888 🌟 — بنذكّرك "
                + ("تعبّي فورم البروفايل" if not m["submitted_at"] else "تتواصل معنا بخصوص حسابك")
                + " بأقرب وقت متل ما ينفع معك 🙏"
            )
            from urllib.parse import quote

            wa_link = f"https://wa.me/{digits}?text={quote(text)}"
        result.append(
            {
                "account_id": m["account_id"],
                "name": m["name"],
                "reason": "لسا ما قدّم الفورم" if not m["submitted_at"] else f"الحساب: {m['status']}",
                "phone": phone or None,
                "wa_link": wa_link,
            }
        )
    return jsonify({"reminders": result})
