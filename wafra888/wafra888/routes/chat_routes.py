from flask import Blueprint, jsonify, request

from .. import auth, repo
from ..ai import AIError, chat_with_member

bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@bp.get("/history")
@auth.login_required
def history():
    acc = auth.current_account()
    return jsonify({"messages": repo.get_chat_history(acc["id"])})


@bp.post("/send")
@auth.login_required
@auth.csrf_protect
def send():
    acc = auth.current_account()
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "الرسالة فاضية"}), 400
    try:
        result = chat_with_member(acc, text)
    except AIError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify(result)
