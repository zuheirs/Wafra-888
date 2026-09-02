from flask import Blueprint, jsonify

from .. import auth, repo

bp = Blueprint("board", __name__, url_prefix="/api/board")


@bp.get("")
@auth.login_required
def get_board():
    """قائمة الأعضاء العامة: بس الاسم + هل قدّم الفورم + تاريخ آخر تحديث — بدون أي
    تفاصيل عن محتوى إجاباتهم."""
    members = repo.list_all_members_status()
    result = [
        {
            "name": m["name"],
            "submitted": bool(m["submitted_at"]),
            "submitted_at": m["submitted_at"],
        }
        for m in members
    ]
    return jsonify({"members": result})
