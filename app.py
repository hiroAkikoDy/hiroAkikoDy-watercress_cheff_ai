import json
import os
import sys
import time
import threading
import uuid

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, session, stream_with_context
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_neo4j import Neo4jVector
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import OpenAI
from tool_selector import (
    load_keyword_patterns, classify,
    get_type0_response, get_type1_response
)
from dialog_engine import (
    get_next_question, extract_condition,
    build_rag_query, get_current_question_key, is_complete
)
from persona_engine import generate_multi_persona_report

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
type0_map = {}
type1_map = {}
report_cache = {}
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
RETRIEVER_K = int(os.getenv("RETRIEVER_K", "3"))
MODEL_NAME = os.getenv("LLM_MODEL", "GLM-4.7-Flash")

# OpenAI互換APIクライアント（ストリーミング用）
zai_client = OpenAI(
    api_key=os.getenv("ZAI_API_KEY"),
    base_url="https://api.z.ai/api/paas/v4/",
    timeout=LLM_TIMEOUT,
)

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
    global db, retriever, rag_chain, type0_map, type1_map

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

        retriever = db.as_retriever(search_kwargs={"k": RETRIEVER_K})
        print("✓ Retriever作成完了")

        print("LLMを初期化中...")
        llm = ChatOpenAI(
            model=MODEL_NAME,
            openai_api_key=os.getenv("ZAI_API_KEY"),
            openai_api_base="https://api.z.ai/api/paas/v4/",
            temperature=0.7,
            timeout=LLM_TIMEOUT,
            max_tokens=LLM_MAX_TOKENS,
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

        neo4j_driver = db._driver
        db_name = os.getenv("NEO4J_USERNAME")
        type0_map, type1_map = load_keyword_patterns(neo4j_driver, db_name)
        print(f"✓ Tool Selector辞書読み込み完了 "
              f"(TYPE_0: {len(type0_map)}件, TYPE_1: {len(type1_map)}件)")

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
    session["session_id"] = str(uuid.uuid4())
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

        max_retries = int(os.getenv("LLM_MAX_RETRIES", "4"))
        assistant_message = None
        source_docs = []

        for attempt in range(max_retries):
            try:
                t0 = time.time()
                source_docs = retriever.invoke(user_message)
                response = rag_chain.invoke(user_message)
                elapsed = time.time() - t0
                print(f"LLM応答取得: {elapsed:.2f}s")

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


@app.route("/chat_stream", methods=["POST"])
def chat_stream():
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
        user_message = (data.get("message", "") if data else "").strip()
        if not user_message:
            return jsonify({"error": "メッセージが空です"}), 400

        if "messages" not in session:
            session["messages"] = []

        messages = session["messages"]
        if len(messages) > 10:
            messages = messages[-10:]

        messages.append({"role": "user", "content": user_message})

        # Tool Selectorで分類（INV_7〜INV_10）
        tool_type = classify(user_message, type0_map, type1_map)
        print(f"Tool Selector: {tool_type} ← 「{user_message[:20]}」")

        if tool_type == "TYPE_0":
            response_text = get_type0_response(user_message, type0_map)
            messages.append({"role": "assistant", "content": response_text})
            session["messages"] = messages
            session.modified = True
            def generate_type0():
                yield f"data: {response_text}\n\n"
            return Response(
                generate_type0(),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        if tool_type == "TYPE_1":
            neo4j_driver = db._driver
            db_name = os.getenv("NEO4J_USERNAME")
            type1_response = get_type1_response(
                user_message, type1_map, neo4j_driver, db_name
            )
            if type1_response:
                messages.append({"role": "assistant", "content": type1_response})
                session["messages"] = messages
                session.modified = True
                def generate_type1():
                    for char in type1_response:
                        yield f"data: {char}\n\n"
                return Response(
                    generate_type1(),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

        # TYPE_3: 対話型絞り込み（INV_11〜INV_14）
        if tool_type not in ("TYPE_0", "TYPE_1"):
            dialog_conditions = session.get("dialog_conditions", {})
            dialog_turn = session.get("dialog_turn", 0)

            current_key = get_current_question_key(dialog_conditions)
            if current_key and dialog_turn > 0:
                dialog_conditions[current_key] = extract_condition(
                    current_key, user_message
                )

            dialog_turn += 1
            session["dialog_conditions"] = dialog_conditions
            session["dialog_turn"] = dialog_turn
            session.modified = True

            if not is_complete(dialog_conditions, dialog_turn):
                next_q = get_next_question(dialog_conditions)
                messages.append({"role": "assistant", "content": next_q})
                session["messages"] = messages
                session.modified = True

                def generate_question():
                    yield f"data: {next_q}\n\n"

                return Response(
                    generate_question(),
                    mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    },
                )

            rag_query = build_rag_query(dialog_conditions)
            print(f"TYPE_3 RAG検索クエリ: {rag_query}")

            session["dialog_conditions"] = dialog_conditions
            session["dialog_turn"] = 0
            session.modified = True

            try:
                source_docs = retriever.invoke(rag_query)
                rag_context = format_docs(source_docs)
            except Exception as e:
                print(f"TYPE_3 RAG検索エラー: {e}")
                rag_context = "（データ取得に失敗しました）"

            conditions_json = json.dumps(
                {"rag_context": rag_context, "conditions": dialog_conditions},
                ensure_ascii=False
            )

            def generate_report_start():
                yield "data: __START_REPORT__\n\n"
                yield f"data: {conditions_json}\n\n"

            return Response(
                generate_report_start(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

    except Exception as e:
        error_message = f"エラーが発生しました: {str(e)}"
        print(f"Error in /chat_stream: {error_message}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": error_message}), 500


@app.route("/start_report", methods=["POST"])
def start_report():
    """
    非同期レポート生成を開始する（INV_15）
    即座にgeneratingを返し、バックグラウンドでレポートを生成する
    """
    data = request.json or {}
    rag_context = data.get("rag_context", "")
    conditions = data.get("conditions", {})
    sid = session.get("session_id", str(uuid.uuid4()))

    def generate_in_background():
        try:
            report_cache[sid] = {"status": "generating", "report": ""}
            full_text = []
            for chunk in generate_multi_persona_report(rag_context, conditions):
                token = chunk.replace("data: ", "").replace("\n\n", "")
                full_text.append(token)
            report = "".join(full_text).strip()
            report_cache[sid] = {"status": "done", "report": report}
            print(f"レポート生成完了: session_id={sid[:8]}...")
        except Exception as e:
            report_cache[sid] = {"status": "failed", "report": str(e)}
            print(f"レポート生成失敗: {e}")

    thread = threading.Thread(target=generate_in_background, daemon=True)
    thread.start()

    return jsonify({"status": "generating", "session_id": sid})


@app.route("/report_status", methods=["GET"])
def report_status():
    """
    レポートの生成状態を返す（INV_15・INV_18）
    フロントエンドが5秒ごとにポーリングする
    """
    sid = session.get("session_id", "")
    cache_entry = report_cache.get(sid, {})
    status = cache_entry.get("status", "not_found")
    report = cache_entry.get("report", "")

    if status == "done":
        del report_cache[sid]

    return jsonify({"status": status, "report": report})


@app.route("/interviewer", methods=["POST"])
def interviewer_endpoint():
    """
    インタビュアーAIエンドポイント（INV_17）
    レポート生成中のみ動作し、最大2問の追加質問を行う
    """
    from interviewer_engine import (
        INTERVIEW_QUESTIONS,
        get_next_interview_question,
        generate_interviewer_response,
    )

    data = request.json or {}
    user_answer = data.get("answer", "").strip()
    last_question_id = data.get("last_question_id", "")

    interview_conditions = session.get("interview_conditions", {})
    base_conditions = session.get("dialog_conditions", {})

    if user_answer and last_question_id:
        for q in INTERVIEW_QUESTIONS:
            if q["id"] == last_question_id:
                interview_conditions[q["condition_key"]] = user_answer
                break

    session["interview_conditions"] = interview_conditions
    session.modified = True

    sid = session.get("session_id", "")
    cache_entry = report_cache.get(sid, {})
    is_generating = cache_entry.get("status") == "generating"

    if not is_generating:
        return jsonify({
            "status": "report_done",
            "message": "レポートが完成しました！"
        })

    next_q = get_next_interview_question(interview_conditions)

    if not next_q:
        return jsonify({
            "status": "interview_done",
            "message": "ありがとうございます🌿レポートの準備ができたらお知らせします！"
        })

    bridge = ""
    if user_answer and last_question_id:
        bridge = generate_interviewer_response(
            last_question_id, user_answer, interview_conditions
        )

    return jsonify({
        "status": "interviewing",
        "bridge": bridge,
        "next_question": next_q["question"],
        "next_question_id": next_q["id"],
    })


@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    session["messages"] = []
    return jsonify({"status": "ok"})


def neo4j_keepalive():
    time.sleep(30)
    while True:
        try:
            if db is not None:
                db._driver.verify_connectivity()
                print("Neo4j keepalive: OK")
        except Exception as e:
            print(f"Neo4j keepalive error: {e}")
            initialize_rag_system()
        time.sleep(270)


def start_keepalive():
    """Gunicorn・Flaskの両方でkeepaliveを起動する"""
    keepalive_thread = threading.Thread(
        target=neo4j_keepalive, daemon=True
    )
    keepalive_thread.start()
    print("Neo4j keepaliveスレッド開始")


# モジュール読み込み時に実行（Gunicornでも動く）
start_keepalive()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\nFlaskアプリを起動します (ポート: {port})")

    # RAGシステムの初期化
    initialize_rag_system()

    app.run(host="0.0.0.0", port=port, debug=False)

