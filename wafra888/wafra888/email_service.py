"""إيميلات تلقائية عبر Resend (HTTP API مباشرة عن طريق requests — بدون مكتبة خارجية
إضافية). لو RESEND_API_KEY مو مضبوط، الدالة بترجع False بهدوء والتطبيق يستمر عادي —
التنبيه بيضل يظهر بلوحة القيادة برضه."""
from __future__ import annotations

import logging

import requests
from flask import current_app

logger = logging.getLogger("wafra888.email")


def send_email(to: list[str], subject: str, html: str) -> bool:
    api_key = current_app.config.get("RESEND_API_KEY")
    if not api_key or not to:
        return False
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": current_app.config.get("RESEND_FROM"),
                "to": to,
                "subject": subject,
                "html": html,
            },
            timeout=20,
        )
        if resp.status_code >= 300:
            logger.error("Resend error %s: %s", resp.status_code, resp.text[:400])
            return False
        return True
    except requests.RequestException:
        logger.exception("failed to send email via Resend")
        return False


def notify_leadership(subject: str, html: str) -> bool:
    emails = current_app.config.get("LEADERSHIP_EMAILS") or []
    return send_email(emails, subject, html)
