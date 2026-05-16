import logging
import logging.config
import os

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY環境変数が設定されていません。本番環境では必須です。")

from flask import Flask
from flask_wtf.csrf import CSRFProtect

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["default"],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)

csrf = CSRFProtect()


def create_app():
    _app = Flask(__name__)
    _app.secret_key = os.getenv("SECRET_KEY")

    if os.getenv("RENDER"):
        _app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
        )

    csrf.init_app(_app)

    from app.routes.chat import chat_bp
    from app.routes.report import report_bp
    _app.register_blueprint(chat_bp)
    _app.register_blueprint(report_bp)

    return _app


app = create_app()

from app.rag import ensure_rag_system_initialized
from app.keepalive import start_keepalive

ensure_rag_system_initialized()
start_keepalive()
