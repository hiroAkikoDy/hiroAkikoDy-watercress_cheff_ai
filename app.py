"""
下位互換用エントリポイント。
本番では wsgi.py を使用する（render.yaml で gunicorn wsgi:app）。
"""
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY環境変数が設定されていません。本番環境では必須です。")

from flask import Flask, render_template, session
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

csrf = CSRFProtect(app)

if os.getenv("RENDER"):
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

from app.rag import ensure_rag_system_initialized
from app.cache import report_cache
from app.routes.chat import chat_bp
from app.routes.report import report_bp

app.register_blueprint(chat_bp)
app.register_blueprint(report_bp)

from app.keepalive import start_keepalive

start_keepalive()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    port = int(os.environ.get("PORT", 5000))
    ensure_rag_system_initialized()
    app.run(host="0.0.0.0", port=port, debug=False)
