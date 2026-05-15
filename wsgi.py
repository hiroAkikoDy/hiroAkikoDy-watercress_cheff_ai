import os

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY環境変数が設定されていません。本番環境では必須です。")

from app import create_app
from app.rag import ensure_rag_system_initialized
from app.keepalive import start_keepalive

app = create_app()

ensure_rag_system_initialized()
start_keepalive()
