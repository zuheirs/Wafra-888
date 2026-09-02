import os


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-change-me")

    # DATABASE_URL: postgresql://... to use Postgres (e.g. Supabase), otherwise
    # falls back to a local SQLite file — see wafra888/db.py.
    DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
    SQLITE_PATH = os.environ.get("SQLITE_PATH", "wafra888.db")

    # Gemini API (google.dev) — اختيار المستخدم صراحة لأنه مجاني بالكامل. لاحظ إن
    # الخطة المجانية بتستخدم بياناتك لتحسين موديلات جوجل (خلافاً لـ Anthropic API
    # المدفوع يلي ما بيعمل هيك افتراضياً) — قرار واعٍ اتخذه زهير رغم توضيح هالفرق له.
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    GEMINI_API_URL_TEMPLATE = (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )

    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
    RESEND_FROM = os.environ.get("RESEND_FROM", "Wafra 888 <noreply@example.com>")
    LEADERSHIP_EMAILS = [
        e.strip() for e in os.environ.get("LEADERSHIP_EMAILS", "").split(",") if e.strip()
    ]

    CRON_SECRET = os.environ.get("CRON_SECRET", "")

    DEFAULT_PASSWORD = os.environ.get("DEFAULT_PASSWORD", "0000")

    IS_PRODUCTION = os.environ.get("FLASK_ENV", "production") == "production"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", IS_PRODUCTION)
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30  # 30 days

    # How many chat turns (user+assistant) to keep in the model context window
    CHAT_HISTORY_WINDOW = 16
