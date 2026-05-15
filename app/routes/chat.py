import json
import logging
import os
import time
import uuid

from flask import Blueprint, Response, jsonify, render_template, request, session

from app.rag import (
    db, retriever, rag_chain, type0_map, type1_map,
    ensure_rag_system_initialized, format_docs,
)
from tool_selector import (
    classify, get_type0_response, get_type1_response,
)
from dialog_engine import (
    get_next_question, extract_condition,
    build_rag_query, get_current_question_key, is_complete,
)

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)

MAX_INPUT_LENGTH = 500


@chat_bp.route("/")
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


@chat_bp.route("/chat", methods=["POST"])
def chat():
    try:
        if not ensure_rag_system_initialized():
            return (
                jsonify({"error": "RAGシステムの初期化に失敗しました。"}),
                500,
            )
        data = request.json
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "メッセージが空です"}), 400
        if len(user_message) > MAX_INPUT_LENGTH:
            return jsonify({"error": f"メッセージは{MAX_INPUT_LENGTH}文字以内で入力してください"}), 400

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
                context_str = format_docs(source_docs)
                from app.rag import rag_chain as _chain
                response = _chain.invoke(user_message)
                elapsed = time.time() - t0
                logger.info("LLM応答取得: %.2fs", elapsed)

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
                    wait_time = min(2 ** (attempt + 2), 30) if is_rate_limit else min(2 ** attempt, 8)
                    logger.warning(
                        "リトライ %d/%d: %s",
                        attempt + 1, max_retries, error_str,
                    )
                    time.sleep(wait_time)
                else:
                    if is_rate_limit:
                        raise Exception("API レート制限に達しました。しばらく待ってから再度お試しください。")
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
        logger.error("Error in /chat: %s", str(e))
        return jsonify({"error": f"エラーが発生しました: {str(e)}"}), 500


@chat_bp.route("/chat_stream", methods=["POST"])
def chat_stream():
    try:
        if not ensure_rag_system_initialized():
            return jsonify({"error": "RAGシステムの初期化に失敗しました。"}), 500

        data = request.json
        user_message = (data.get("message", "") if data else "").strip()
        if not user_message:
            return jsonify({"error": "メッセージが空です"}), 400
        if len(user_message) > MAX_INPUT_LENGTH:
            return jsonify({"error": f"メッセージは{MAX_INPUT_LENGTH}文字以内で入力してください"}), 400

        if "messages" not in session:
            session["messages"] = []

        messages = session["messages"]
        if len(messages) > 10:
            messages = messages[-10:]

        messages.append({"role": "user", "content": user_message})

        from app.rag import type0_map as _t0, type1_map as _t1
        tool_type = classify(user_message, _t0, _t1)
        logger.info("Tool Selector: %s ← 「%s」", tool_type, user_message[:20])

        if tool_type == "TYPE_0":
            response_text = get_type0_response(user_message, _t0)
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
            from app.rag import db as _db
            neo4j_driver = _db._driver
            db_name = os.getenv("NEO4J_USERNAME")
            type1_response = get_type1_response(
                user_message, _t1, neo4j_driver, db_name
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
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            rag_query = build_rag_query(dialog_conditions)
            logger.info("TYPE_3 RAG検索クエリ: %s", rag_query)

            session["dialog_conditions"] = dialog_conditions
            session["dialog_turn"] = 0
            session.modified = True

            try:
                from app.rag import retriever as _retriever
                source_docs = _retriever.invoke(rag_query)
                rag_context = format_docs(source_docs)
            except Exception as e:
                logger.error("TYPE_3 RAG検索エラー: %s", e)
                rag_context = "（データ取得に失敗しました）"

            conditions_json = json.dumps(
                {"rag_context": rag_context, "conditions": dialog_conditions},
                ensure_ascii=False
            )

            session["pending_report"] = {
                "rag_context": rag_context,
                "conditions": dialog_conditions,
            }
            session.modified = True

            def generate_report_start():
                yield "data: __START_REPORT__\n\n"
                yield f"data: {conditions_json}\n\n"

            return Response(
                generate_report_start(),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    except Exception as e:
        logger.error("Error in /chat_stream: %s", str(e))
        return jsonify({"error": f"エラーが発生しました: {str(e)}"}), 500


@chat_bp.route("/reset", methods=["POST"])
def reset():
    from app.cache import report_cache
    sid = session.get("session_id", "")
    if sid:
        report_cache.delete(sid)
    session.clear()
    session["messages"] = []
    return jsonify({"status": "ok"})
