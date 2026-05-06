"""
Phase 4 マルチペルソナエンジン（INV_13）
発言順序: 司会(MC) → シェフ(Chef) → 栄養士(Nutritionist) → 司会(MC)
各ペルソナ300字以内・チャット画面内にストリーミング出力
"""

import os
from openai import OpenAI

zai_client = OpenAI(
    api_key=os.getenv("ZAI_API_KEY"),
    base_url="https://api.z.ai/api/paas/v4/",
    timeout=120,
)
MODEL_NAME = os.getenv("LLM_MODEL", "GLM-4.7-Flash")

PERSONAS = [
    {
        "id": "mc_intro",
        "name": "🎙️ 司会",
        "system": """あなたはナナカファームのクレソン料理AIの司会者です。
ユーザーの条件に合った料理を1品選び、
「〇〇をおすすめします！専門家の意見も聞いてみましょう。」
という形で100字以内で紹介してください。""",
    },
    {
        "id": "chef",
        "name": "👨‍🍳 シェフ",
        "system": """あなたはプロのシェフです。
司会が紹介した料理について、
調理技術・下処理・火加減・味付けのポイントを
300字以内でアドバイスしてください。
家庭で作れるレベルで説明してください。""",
    },
    {
        "id": "nutritionist",
        "name": "🥗 栄養士",
        "system": """あなたは管理栄養士です。
司会が紹介した料理について、
栄養価・健康メリット・食べ合わせのポイントを
300字以内でアドバイスしてください。
クレソンの栄養素（ビタミンC・K・鉄分）に触れてください。""",
    },
    {
        "id": "mc_close",
        "name": "🎙️ 司会（まとめ）",
        "system": """あなたはナナカファームのクレソン料理AIの司会者です。
シェフと栄養士のアドバイスを踏まえて、
「今夜はぜひ〇〇を試してみてください！」
という形で100字以内でまとめてください。
明るく背中を押すようなトーンで。""",
    },
]


def generate_persona_stream(persona: dict, context: str):
    """1つのペルソナのストリーミング発言を生成するジェネレータ"""
    stream = zai_client.chat.completions.create(
        model=MODEL_NAME,
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


def generate_multi_persona_report(rag_context: str, conditions: dict):
    """
    INV_13: MC→Chef→Nutritionist→MCの順でストリーミング出力する
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

    for persona in PERSONAS:
        header = f"\n\n**{persona['name']}**\n"
        yield f"data: {header}\n\n"

        for token in generate_persona_stream(persona, context):
            yield f"data: {token}\n\n"
