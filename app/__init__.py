import logging
import logging.config
import os

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
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY")

    if os.getenv("RENDER"):
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
        )

    csrf.init_app(app)

    from app.routes.chat import chat_bp
    from app.routes.report import report_bp
    app.register_blueprint(chat_bp)
    app.register_blueprint(report_bp)

    return app
