import os

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY環境変数が設定されていません。本番環境では必須です。")

from app import app  # noqa: E402  # __init__.pyでcreate_app + RAG初期化 + keepalive起動済み
