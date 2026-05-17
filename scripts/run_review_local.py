"""
レビュー画面をローカルで起動するスクリプト。
Render 本番とは独立して動作する。

使い方:
    python scripts/run_review_local.py
    → http://localhost:5001/review にアクセス
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.routes.review import bp

app = create_app()
app.register_blueprint(bp)

if __name__ == "__main__":
    print("🌿 レビュー画面を起動します")
    print("   URL: http://localhost:5001/review")
    print(f"   USER: {os.getenv('REVIEW_USER', 'admin')}")
    print("   Ctrl+C で停止")
    app.run(host="127.0.0.1", port=5001, debug=True)
