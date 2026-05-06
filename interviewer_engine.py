"""
Phase 4b インタビュアーエンジン（INV_17）
レポート生成中のみ動作し、最大2問の追加質問を行う
質問テーマ優先順位：アレルギー → 調理時間 or 冷蔵庫食材
"""

import os
from openai import OpenAI

persona_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=30,
)

INTERVIEW_QUESTIONS = [
    {
        "id": "allergy",
        "question": "アレルギーや苦手な食材はありますか？（例：卵・ナッツ・なし）",
        "condition_key": "allergy",
    },
    {
        "id": "cooking_time",
        "question": "調理時間はどのくらいかけられますか？（例：15分・30分・1時間）",
        "condition_key": "cooking_time",
    },
]


def get_next_interview_question(interview_conditions: dict) -> dict | None:
    """
    未収集のインタビュー条件のうち最初の1つを返す。
    全条件収集済みまたは2問完了の場合はNoneを返す（INV_17）。
    """
    asked_count = len(interview_conditions)
    if asked_count >= 2:
        return None

    for q in INTERVIEW_QUESTIONS:
        if q["condition_key"] not in interview_conditions:
            return q
    return None


def build_enhanced_conditions(
    base_conditions: dict,
    interview_conditions: dict
) -> dict:
    """
    基本条件とインタビュー条件をマージして
    レポート生成に渡す強化版条件を構築する
    """
    enhanced = base_conditions.copy()
    enhanced.update(interview_conditions)
    return enhanced


def generate_interviewer_response(
    question: str,
    user_answer: str,
    interview_conditions: dict
) -> str:
    """
    ユーザーの回答に対して自然な橋渡しコメントを生成する
    次の質問への導線として使用する
    """
    asked_count = len(interview_conditions)
    if asked_count >= 2:
        return "ありがとうございます🌿レポートの準備ができたらお知らせします！"

    response = persona_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": """あなたはクレソン料理AIのインタビュアーです。
ユーザーの回答に対して、1〜2文の自然なコメントをしてください。
明るく親しみやすいトーンで、次の質問への橋渡しをしてください。
絵文字を1つ使ってください。"""
        }, {
            "role": "user",
            "content": f"質問：{question}\nユーザーの回答：{user_answer}"
        }],
        max_tokens=100,
        temperature=0.7,
    )
    return response.choices[0].message.content or "なるほど！ありがとうございます🌿"
