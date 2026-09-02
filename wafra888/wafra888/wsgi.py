"""نقطة دخول للتشغيل بالإنتاج عبر gunicorn:
    gunicorn wsgi:app --bind 0.0.0.0:$PORT
"""
from wafra888 import create_app

app = create_app()
