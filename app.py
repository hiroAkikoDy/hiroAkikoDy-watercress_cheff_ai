import os
import sys
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_neo4j import Neo4jVector
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# .envファイルから環境変数を読み込む（Render本番ではEnvironment Variablesを利用）
load_dotenv()

print("=" * 80)
print("【Neo4j RAGシステムを初期化中...】")
print("=" * 80)

# Flask アプリケーションの設定
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or os.urandom(24)

if os.getenv("RENDER"):
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

# グローバル変数としてRAGコンポーネントを保持
db = None
retriever = None
rag_chain = None

# BtoC向けSystemプロンプト
SYSTEM_PROMPT_TEMPLATE = """あなたは「ナナカファームのクレソン料理アドバイザー」です。
熊本の清らかな水で育てたクレソンを手に取ったあなたに、
今夜の食卓で使いこなせるレシピをご提案します。

【得意なこと】
・家庭で作れる具体的なレシピと調理のポイント
・冷蔵庫にある食材とクレソンの組み合わせ提案
・余ったクレソンの翌日活用法
・クレソンの栄養・保存方法のアドバイス
・世界19ジャンル190品超のクレソン料理の知識

【回答スタイル】
・家庭料理レベルでわかりやすく説明する
・材料は身近なスーパーで手に入るものを使う
・クレソン料理に関係ない質問には
  「クレソンの使い方についてお気軽にどうぞ😊」と答える

【参考データ】
{context}

質問: {question}

回答:"""


def format_docs(docs):
    """Neo4jから取得したDocumentを整形する"""
    formatted = []
    for i, doc in enumerate(docs, 1):
        formatted.append(f"{i}. {doc.page_content}")
        formatted.append(f"   - 地域: {doc.metadata.get('region', '不明')}")
        formatted.append(f"   - 季節: {doc.metadata.get('season', '不明')}")
        formatted.append(f"   - 用途: {doc.metadata.get('use_case', '不明')}")
    return "\n".join(formatted)


def initialize_rag_system():
    """アプリ起動時に1回だけ実行されるRAGシステムの初期化"""
    global db, retriever, rag_chain

    try:
        print("Neo4jに接続中...")
        db = Neo4jVector.from_existing_index(
            OpenAIEmbeddings(),
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            index_name="watercress_index",
            keyword_index_name="watercress_keyword_index",
            search_type="hybrid",
            database=os.getenv("NEO4J_USERNAME"),  # Aura Free特有の設定
        )
        print("✓ Neo4j接続成功")

        retriever = db.as_retriever(search_kwargs={"k": 3})
        print("✓ Retriever作成完了")

        print("LLMを初期化中...")
        llm = ChatOpenAI(
            model="glm-4.7",
            openai_api_key=os.getenv("ZAI_API_KEY"),
            openai_api_base="https://api.z.ai/api/paas/v4/",
            temperature=0.7,
            timeout=60.0,
            max_tokens=4096,  # GLM-4.7の推論モード対策
        )
        print("✓ LLM初期化完了")

        prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT_TEMPLATE)

        print("RAGチェーンを構築中...")
        rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
        print("✓ RAGチェーン構築完了")

        print("=" * 80)
        print("【Neo4j RAGシステムの初期化が完了しました】")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"✗ RAGシステムの初期化に失敗しました: {str(e)}")
        import traceback

        print(traceback.format_exc())
        return False


def ensure_rag_system_initialized():
    """RAGが未初期化なら初期化する（起動時のハング回避のため遅延初期化）"""
    global rag_chain, retriever
    if rag_chain is not None and retriever is not None:
        return True
    return initialize_rag_system()


@app.route("/")
def index():
    session.clear()
    session["messages"] = []
    if not ensure_rag_system_initialized():
        return (
            "RAGシステムの初期化に失敗しました。環境変数とNeo4jインデックスをご確認ください。",
            500,
        )
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    try:
        if not ensure_rag_system_initialized():
            return (
                jsonify(
                    {
                        "error": "RAGシステムの初期化に失敗しました。環境変数とNeo4jインデックスをご確認ください。"
                    }
                ),
                500,
            )
        data = request.json
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "メッセージが空です"}), 400

        if "messages" not in session:
            session["messages"] = []

        messages = session["messages"]

        if len(messages) > 10:
            messages = messages[-10:]

        messages.append({"role": "user", "content": user_message})

        max_retries = 5
        assistant_message = None
        source_docs = []

        for attempt in range(max_retries):
            try:
                source_docs = retriever.invoke(user_message)
                response = rag_chain.invoke(user_message)

                if hasattr(response, "content"):
                    assistant_message = response.content or getattr(
                        response, "reasoning_content", None
                    )
                else:
                    assistant_message = response

                if assistant_message:
                    break

            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "Rate limit" in error_str

                if attempt < max_retries - 1:
                    if is_rate_limit:
                        wait_time = min(2 ** (attempt + 2), 30)
                        print(
                            f"レート制限エラー検出、{wait_time}秒待機後にリトライします... (試行 {attempt + 1}/{max_retries})"
                        )
                    else:
                        wait_time = min(2**attempt, 8)
                        print(
                            f"エラーが発生、{wait_time}秒待機後にリトライします... (試行 {attempt + 1}/{max_retries}): {error_str}"
                        )

                    time.sleep(wait_time)
                else:
                    if is_rate_limit:
                        raise Exception(
                            "API レート制限に達しました。しばらく待ってから再度お試しください。"
                        )
                    raise

        if not assistant_message:
            raise ValueError("AIからの応答を取得できませんでした")

        messages.append({"role": "assistant", "content": assistant_message})

        session["messages"] = messages
        session.modified = True

        sources = []
        for doc in source_docs:
            sources.append(
                {
                    "content": doc.page_content,
                    "region": doc.metadata.get("region", "不明"),
                    "season": doc.metadata.get("season", "不明"),
                    "use_case": doc.metadata.get("use_case", "不明"),
                }
            )

        return jsonify(
            {"reply": assistant_message, "sources": sources, "message_count": len(messages)}
        )

    except Exception as e:
        error_message = f"エラーが発生しました: {str(e)}"
        print(f"Error in /chat: {error_message}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": error_message}), 500


@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    session["messages"] = []
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\nFlaskアプリを起動します (ポート: {port})")
    app.run(host="0.0.0.0", port=port, debug=False)

