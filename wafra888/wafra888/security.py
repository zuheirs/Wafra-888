"""تجزئة كلمات السر (hashing) و CSRF — بدون أي اعتماد خارجي غير مضمّن بـ Flask/Werkzeug."""
import hmac
import re
import secrets

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(plain: str) -> str:
    # pbkdf2:sha256 مضمّنة بـ Werkzeug — تجزئة حقيقية مع salt، مو نص صريح أبداً.
    return generate_password_hash(plain, method="pbkdf2:sha256:260000")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return check_password_hash(password_hash, plain)
    except Exception:
        return False


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"\s+", "-", s)
    # يسمح بحروف عربية ولاتينية وأرقام وشرطة فقط
    s = re.sub(r"[^a-z0-9؀-ۿ-]", "", s)
    return s


def new_csrf_token() -> str:
    return secrets.token_hex(20)


def csrf_tokens_match(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)
