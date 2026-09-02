"""نقطة نهاية للفحص الدوري (مثلاً أسبوعياً) — تستدعى من خدمة cron خارجية مجانية
(GitHub Actions schedule, cron-job.org, Render Cron...) لأن Flask نفسه ما عنده
جدولة مدمجة بدون عملية إضافية. راجع README لطريقة الربط."""
from flask import Blueprint, current_app, jsonify, request

from .. import repo
from ..email_service import notify_leadership

bp = Blueprint("cron", __name__, url_prefix="/cron")


def _run_weekly_check() -> dict:
    all_members = [m for m in repo.list_all_members_status() if m["role"] == "member"]
    missing_profile = [m for m in all_members if not m["submitted_at"]]

    all_accounts = repo.list_accounts()
    needs_review = [a for a in all_accounts if a["status"] == "locked_pending_review"]
    frozen = [a for a in all_accounts if a["status"] == "frozen"]

    if not missing_profile and not needs_review and not frozen:
        return {"sent": False, "reason": "no_gaps"}

    lines = []
    if missing_profile:
        lines.append("<b>لسا ما قدّموا فورم البروفايل:</b><ul>" + "".join(
            f"<li>{m['name']}</li>" for m in missing_profile
        ) + "</ul>")
    if needs_review:
        lines.append("<b>حسابات مقفولة بانتظار قرار القيادة:</b><ul>" + "".join(
            f"<li>{a['name']} — {a.get('status_note') or ''}</li>" for a in needs_review
        ) + "</ul>")
    if frozen:
        lines.append("<b>حسابات مجمّدة حالياً:</b><ul>" + "".join(
            f"<li>{a['name']} حتى {a.get('frozen_until') or 'غير محدد'}</li>" for a in frozen
        ) + "</ul>")

    html = "<h2>تقرير متابعة وفرة 888</h2>" + "".join(lines)
    for m in missing_profile + [
        {"account_id": a["id"], "name": a["name"]} for a in (needs_review + frozen)
    ]:
        repo.add_notification("commitment_gap", m.get("account_id"), f"فحص دوري: {m['name']} يحتاج متابعة")

    sent = notify_leadership("متابعة وفرة 888 — يحتاج انتباه", html)
    return {"sent": sent, "missing_profile": len(missing_profile), "needs_review": len(needs_review), "frozen": len(frozen)}


@bp.route("/weekly-check", methods=["GET", "POST"])
def weekly_check():
    secret = current_app.config.get("CRON_SECRET")
    provided = request.args.get("token") or request.headers.get("X-Cron-Secret")
    if not secret or provided != secret:
        return jsonify({"error": "unauthorized"}), 401
    result = _run_weekly_check()
    return jsonify(result)
