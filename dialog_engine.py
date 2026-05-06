"""
Phase 4 対話エンジン（INV_11〜INV_12）
TYPE_3: TYPE_0・TYPE_1に当てはまらない全ての質問を担当
最大3往復で条件を収集し、RAG検索クエリを返す
"""

from typing import Optional

CONDITION_KEYS = ["person_count", "genre", "usage"]

QUESTIONS = {
    "person_count": "今夜は何人分ですか？（例：1人、2人、4人）",
    "genre": "和食・洋食・エスニックなど、お好みのジャンルはありますか？",
    "usage": "メインのおかず・副菜・スープなど、どんな料理にしたいですか？",
}


def get_next_question(conditions: dict) -> Optional[str]:
    """
    未収集の条件のうち最初の1つを質問として返す。
    全条件収集済みの場合はNoneを返す。
    INV_12: 最大3往復（条件3つ）で完了する設計
    """
    for key in CONDITION_KEYS:
        if key not in conditions or not conditions[key]:
            return QUESTIONS[key]
    return None


def extract_condition(question_key: str, user_answer: str) -> str:
    """ユーザーの回答から条件値を抽出する（シンプルにそのまま使う）"""
    return user_answer.strip()


def build_rag_query(conditions: dict) -> str:
    """
    収集した条件からRAG検索クエリを構築する。
    条件が不足していても強制的にクエリを生成する（INV_12）。
    """
    parts = []
    if conditions.get("genre"):
        parts.append(conditions["genre"])
    if conditions.get("usage"):
        parts.append(conditions["usage"])
    if not parts:
        parts.append("クレソン料理")
    return " ".join(parts)


def get_current_question_key(conditions: dict) -> Optional[str]:
    """現在収集しようとしている条件のキーを返す"""
    for key in CONDITION_KEYS:
        if key not in conditions or not conditions[key]:
            return key
    return None


def is_complete(conditions: dict, turn: int) -> bool:
    """
    条件収集が完了しているかを判定する。
    INV_12: 3往復目は強制的にCompleteとする。
    """
    if turn >= 3:
        return True
    return get_next_question(conditions) is None
