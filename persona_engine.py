"""
Phase 4 マルチペルソナエンジン（INV_13）
発言順序: シェフ(Chef) → 栄養士(Nutritionist)
各ペルソナ指定字数以内・チャット画面内にストリーミング出力
"""

import os
import time
from openai import OpenAI

persona_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=120,
)
PERSONA_MODEL = "gpt-4o-mini"

PERSONAS = [
    {
        "id": "chef",
        "name": "👨‍🍳 シェフからのアドバイス",
        "system": """あなたはプロのシェフです。
ユーザーの条件に合ったクレソン料理を1品選び、
料理名・材料・作り方・調理のポイントを
200字以内で具体的に説明してください。
家庭で作れるレベルで、明るく親しみやすいトーンで。""",
    },
    {
        "id": "nutritionist",
        "name": "🥗 栄養士からのひとこと",
        "system": """あなたは管理栄養士です。
シェフが紹介した料理について、
クレソンの栄養価（ビタミンC・K・鉄分）と
健康メリットを100字以内で一言添えてください。
簡潔に、ポジティブなトーンで。""",
    },
]


def generate_persona_stream(persona: dict, context: str):
    """1つのペルソナのストリーミング発言を生成するジェネレータ"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            stream = persona_client.chat.completions.create(
                model=PERSONA_MODEL,
                messages=[
                    {"role": "system", "content": persona["system"]},
                    {"role": "user", "content": context},
                ],
                stream=True,
                temperature=0.7,
                max_tokens=400,
            )
            for event in stream:
                if not event or not getattr(event, "choices", None):
                    continue
                delta = getattr(event.choices[0], "delta", None)
                token = getattr(delta, "content", None) if delta else None
                if token:
                    yield token
            return
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 3
                print(f"ペルソナ生成リトライ {attempt+1}/{max_retries}: {e}")
                time.sleep(wait)
            else:
                yield f"（コメントの取得に失敗しました。もう一度お試しください）"
                print(f"ペルソナ生成失敗: {persona['id']} - 最大リトライ到達")


def generate_multi_persona_report(rag_context: str, conditions: dict):
    """
    INV_13: Chef→Nutritionistの順でストリーミング出力する
    各ペルソナの発言をSSE形式で逐次yieldする
    """
    condition_text = ""
    if conditions.get("person_count"):
        condition_text += f"人数：{conditions['person_count']}人分。"
    if conditions.get("genre"):
        condition_text += f"ジャンル：{conditions['genre']}。"
    if conditions.get("usage"):
        condition_text += f"用途：{conditions['usage']}。"

    context = f"""
ユーザーの条件：{condition_text}

クレソン料理データベースの参考情報：
{rag_context}
"""

    # レポート作成中メッセージを最初に送信
    yield "data: 🌿 **レポートを作成中です...少々お待ちください**\n\n"
    yield "data: \n\n"
    time.sleep(1)

    for i, persona in enumerate(PERSONAS):
        header = f"\n\n**{persona['name']}**\n"
        yield f"data: {header}\n\n"

        for token in generate_persona_stream(persona, context):
            yield f"data: {token}\n\n"

        if i < len(PERSONAS) - 1:
            time.sleep(5)
