from flask import Blueprint, jsonify, request

from .. import auth, repo

bp = Blueprint("profile", __name__, url_prefix="/api/profile")

REQUIRED_FIELDS = ["dca", "goal4m", "fear", "give", "want", "patterns"]


@bp.get("")
@auth.login_required
def get_profile():
    acc = auth.current_account()
    profile = repo.get_profile(acc["id"])
    return jsonify({"profile": profile})


@bp.post("")
@auth.login_required
@auth.csrf_protect
def save_profile():
    acc = auth.current_account()
    data = request.get_json(silent=True) or {}

    fields = {k: (data.get(k) or "").strip() for k in REQUIRED_FIELDS}
    agreed = bool(data.get("agreed"))

    if any(not v for v in fields.values()) or not agreed:
        return jsonify({"error": "لازم تعبي كل الحقول وتوافق على الشروط"}), 400

    fields["agreed"] = agreed
    repo.upsert_profile(acc["id"], fields)
    return jsonify({"status": "ok"})
