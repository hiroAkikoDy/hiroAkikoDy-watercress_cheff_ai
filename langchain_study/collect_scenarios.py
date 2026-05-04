import os, csv, json, time, re
from dotenv import load_dotenv
from openai import OpenAI
import sys

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv("../watercress_flask/.env")

client = OpenAI(
    api_key=os.getenv("ZAI_API_KEY"),
    base_url="https://api.z.ai/api/paas/v4/",
    timeout=60,
)

PERSONAS = [
    {
        "id": "farmer",
        "name": "農家（クレソン生産者）",
        "description": "熊本でクレソンを栽培している農家。加工品開発や直売のためにレシピを探している。生産者視点でクレソンの特性をよく知っている。"
    },
    {
        "id": "chef_researcher",
        "name": "料理研究家",
        "description": "料理研究家でレシピ開発が仕事。栄養価・調理科学・世界各国の料理技法に詳しい。クレソンの新しい可能性を探っている。"
    },
    {
        "id": "teenager",
        "name": "中高生（料理初心者）",
        "description": "SNSでクレソンを使った料理を見て興味をもった中高生。料理はほぼ初心者。簡単でおしゃれなレシピを探している。"
    },
    {
        "id": "foreigner",
        "name": "外国人（英語話者）",
        "description": "日本在住の外国人。日本食に興味があり、クレソンを買ってみた。英語混じりの日本語で質問することもある。"
    },
    {
        "id": "dieter",
        "name": "ダイエット中の社会人",
        "description": "ダイエット中の30代社会人。カロリーを気にしており、低カロリーで栄養のある料理を探している。時短レシピも重視。"
    },
]

PROMPT_TEMPLATE = """あなたはクレソン料理AIチャットボット「ナナカファームのクレソン料理アドバイザー」のユーザーです。

ペルソナ設定：
{description}

このペルソナとして、チャットボットに送りそうな質問を10個作成してください。
挨拶・感謝・雑談から具体的な料理の質問まで幅広く含めてください。

必ずJSONのみ返してください（説明文・コードブロック不要）：
{{"questions":[{{"text":"質問文","type":"TYPE_0かTYPE_1かTYPE_2","reason":"分類理由20字以内","keywords":["KW1","KW2"]}}]}}

分類基準：
TYPE_0: 挨拶・感謝・雑談・保存方法・栄養など（検索不要）
TYPE_1: 地域・季節・用途などの明確なキーワードがある（例：熊本、秋、鍋料理、居酒屋）
TYPE_2: 意味的な検索が必要な曖昧な質問（例：体に良い、子どもが食べやすい、ダイエット向け）"""


def extract_json(text):
    """JSONブロックを抽出してパースする"""
    text = text.replace("```json", "").replace("```", "").strip()
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return json.loads(match.group())
    return json.loads(text)


def call_with_retry(messages, max_retries=3):
    """指数バックオフ付きリトライ"""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="GLM-4.7-Flash",
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
            )
            content = response.choices[0].message.content or ""
            if not content.strip():
                raise ValueError("空のレスポンス")
            return extract_json(content)
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"    リトライ {attempt+1}/{max_retries}: {e} ({wait}秒待機)", flush=True)
            time.sleep(wait)
    return None


results = []

for i, persona in enumerate(PERSONAS):
    print(f"\n[{i+1}/5] {persona['name']} の質問を生成中...", flush=True)
    if i > 0:
        time.sleep(15)

    parsed = call_with_retry([{
        "role": "user",
        "content": PROMPT_TEMPLATE.format(description=persona["description"])
    }])

    if parsed and "questions" in parsed:
        for q in parsed["questions"]:
            q["persona_id"] = persona["id"]
            q["persona_name"] = persona["name"]
            results.append(q)
            print(f"  [{q['type']}] {q['text']}", flush=True)
    else:
        print(f"  スキップ: レスポンス解析失敗", flush=True)

output_path = "phase3b_scenarios_kilo.csv"
with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["persona_name","text","type","reason","keywords"])
    writer.writeheader()
    for r in results:
        writer.writerow({
            "persona_name": r["persona_name"],
            "text": r["text"],
            "type": r["type"],
            "reason": r["reason"],
            "keywords": "|".join(r.get("keywords", [])),
        })

from collections import Counter
type_counts = Counter(r["type"] for r in results)
print(f"\n=== 収集完了 ===")
print(f"総質問数: {len(results)}")
print(f"TYPE_0（定型）: {type_counts.get('TYPE_0', 0)}")
print(f"TYPE_1（構造化）: {type_counts.get('TYPE_1', 0)}")
print(f"TYPE_2（意味検索）: {type_counts.get('TYPE_2', 0)}")
print(f"保存先: {output_path}")
