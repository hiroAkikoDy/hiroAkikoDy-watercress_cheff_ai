import os, json, time, re
from dotenv import load_dotenv
from openai import OpenAI
import sys

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'watercress_cheff_ai', '.env'))

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)

PERSONAS = [
    {
        "id": "housewife",
        "name": "主婦（30代）",
        "description": "30代の主婦。夕食の献立に迷っている。家族の好みと栄養バランスを気にしており、冷蔵庫の残り物も活用したい。"
    },
    {
        "id": "solo",
        "name": "一人暮らし（20代）",
        "description": "20代の一人暮らしの社会人。初めてクレソンを買った。調理経験が浅く、簡単で失敗しないレシピを探している。"
    },
    {
        "id": "senior",
        "name": "シニア（60代）",
        "description": "60代の健康志向のシニア。血圧やコレステロールが気になっており、体に良い食材を積極的に取り入れている。"
    },
    {
        "id": "restaurant",
        "name": "飲食店スタッフ",
        "description": "飲食店でメニュー開発を担当するスタッフ。旬の食材を使った新メニューを考案中。お客様に喜ばれる一品を作りたい。"
    },
    {
        "id": "tourist",
        "name": "観光客",
        "description": "熊本を旅行中の観光客。地元の食材を使ったお土産レシピを探している。家に帰ってからも再現できるものが良い。"
    },
]

PROMPT_TEMPLATE = """あなたはクレソン料理AIチャットボットのシナリオ設計者です。

ペルソナ設定：
{description}

このペルソナがチャットボットに送る「TYPE_3（絞り込み対話）」の質問シナリオを5つ作成してください。

TYPE_3とは：
- TYPE_0（挨拶・感謝・保存方法・栄養）にもTYPE_1（地域・季節・用途の明確キーワード）にも当てはまらない質問
- 曖昧で、AIがユーザーの意図を絞り込むために追加質問が必要なもの
- 例：「クレソンで何か作りたい」「おすすめの料理を教えて」「子どもが食べられるもの」

各シナリオには以下を含めてください：
1. initial_question: ペルソナの最初の質問（TYPE_3に分類されるもの）
2. ai_question_1: AIが返す1つ目の絞り込み質問
3. user_answer_1: ユーザーの想定回答
4. ai_question_2: AIが返す2つ目の絞り込み質問（必要なければ空文字）
5. user_answer_2: ユーザーの想定回答（ai_question_2が空なら空文字）
6. rag_query: 条件収集完了後のRAG検索クエリ（キーワードをスペース区切り）
7. chef_angle: 料理研究家ペルソナの発言の方向性（50字以内）
8. nutritionist_angle: 栄養士ペルソナの発言の方向性（50字以内）

必ずJSONのみ返してください（説明文・コードブロック不要）：
{{"scenarios":[{{"initial_question":"...","ai_question_1":"...","user_answer_1":"...","ai_question_2":"...","user_answer_2":"...","rag_query":"...","chef_angle":"...","nutritionist_angle":"..."}}]}}"""


def extract_json(text):
    text = text.replace("```json", "").replace("```", "").strip()
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return json.loads(match.group())
    return json.loads(text)


def call_with_retry(messages, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
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


all_scenarios = []

for i, persona in enumerate(PERSONAS):
    print(f"\n[{i+1}/5] {persona['name']} のシナリオを生成中...", flush=True)
    if i > 0:
        time.sleep(15)

    parsed = call_with_retry([{
        "role": "user",
        "content": PROMPT_TEMPLATE.format(description=persona["description"])
    }])

    if parsed and "scenarios" in parsed:
        for s in parsed["scenarios"]:
            s["persona_id"] = persona["id"]
            s["persona"] = persona["name"]
            all_scenarios.append(s)
            print(f"  Q: {s['initial_question']}", flush=True)
            print(f"    → RAG: {s['rag_query']}", flush=True)
    else:
        print(f"  スキップ: レスポンス解析失敗", flush=True)

output_path = os.path.join(os.path.dirname(__file__), "phase4_scenarios.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump({"scenarios": all_scenarios}, f, ensure_ascii=False, indent=2)

persona_counts = {}
for s in all_scenarios:
    p = s["persona"]
    persona_counts[p] = persona_counts.get(p, 0) + 1

print(f"\n=== 収集完了 ===")
print(f"総シナリオ数: {len(all_scenarios)}")
for name, count in persona_counts.items():
    print(f"  {name}: {count}件")
print(f"保存先: {output_path}")
