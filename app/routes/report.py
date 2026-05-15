import json
import logging
import os
import threading
import uuid

from flask import Blueprint, jsonify, request, session

from app.cache import report_cache
from app.rag import ensure_rag_system_initialized
from persona_engine import generate_multi_persona_report

logger = logging.getLogger(__name__)

report_bp = Blueprint("report", __name__)

MAX_INPUT_LENGTH = 500


@report_bp.route("/start_report", methods=["POST"])
def start_report():
    pending = session.get("pending_report")
    if not pending:
        return jsonify({"error": "レポート対象が見つかりません"}), 400
    rag_context = pending.get("rag_context", "")
    conditions = pending.get("conditions", {})
    session.pop("pending_report", None)
    session.modified = True

    sid = session.get("session_id", str(uuid.uuid4()))

    def generate_in_background():
        try:
            report_cache.set(sid, {"status": "generating", "report": ""})
            full_text = []
            for chunk in generate_multi_persona_report(rag_context, conditions):
                token = chunk.replace("data: ", "").replace("\n\n", "")
                full_text.append(token)
            report = "".join(full_text).strip()
            report_cache.set(sid, {"status": "done", "report": report})
            logger.info("レポート生成完了: session_id=%s...", sid[:8])
        except Exception as e:
            report_cache.set(sid, {"status": "failed", "report": str(e)})
            logger.error("レポート生成失敗: %s", e)

    thread = threading.Thread(target=generate_in_background, daemon=True)
    thread.start()

    return jsonify({"status": "generating", "session_id": sid})


@report_bp.route("/report_status", methods=["GET"])
def report_status():
    sid = session.get("session_id", "")
    cache_entry = report_cache.get(sid, {})
    status = cache_entry.get("status", "not_found")
    report = cache_entry.get("report", "")

    if status == "done":
        report_cache.delete(sid)

    return jsonify({"status": status, "report": report})


@report_bp.route("/interviewer", methods=["POST"])
def interviewer_endpoint():
    from interviewer_engine import (
        INTERVIEW_QUESTIONS,
        get_next_interview_question,
        generate_interviewer_response,
    )

    data = request.json or {}
    user_answer = data.get("answer", "").strip()
    last_question_id = data.get("last_question_id", "")

    if len(user_answer) > MAX_INPUT_LENGTH:
        return jsonify({"error": f"回答は{MAX_INPUT_LENGTH}文字以内で入力してください"}), 400
    if len(last_question_id) > 64:
        return jsonify({"error": "無効なパラメータです"}), 400

    interview_conditions = session.get("interview_conditions", {})

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
