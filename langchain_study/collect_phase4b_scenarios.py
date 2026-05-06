import os, json, time, re
from dotenv import load_dotenv
from openai import OpenAI
import sys

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'watercress_cheff_ai', '.env'))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PERSONAS = [
    {
        "id": "housewife",
        "name": "主婦（30代・家族4人）",
        "base_conditions": {"person_count": "4人分", "genre": "和食"},
        "description": "家族4人分の和食を作りたい。子どもがいるので辛いものは避けたい。"
    },
    {
        "id": "single",
        "name": "一人暮らし（20代）",
        "base_conditions": {"person_count": "1人分", "genre": "洋食"},
        "description": "一人暮らしで洋食を作りたい。時短料理が好き。冷蔵庫に卵と牛乳がある。"
    },
    {
        "id": "senior",
        "name": "シニア（60代・健康志向）",
        "base_conditions": {"person_count": "2人分", "genre": "和食"},
        "description": "夫婦2人分の和食を作りたい。塩分控えめ・消化に良いものが好き。"
    },
    {
        "id": "restaurant",
        "name": "飲食店スタッフ（メニュー開発）",
        "base_conditions": {"person_count": "大人数", "genre": "エスニック"},
        "description": "エスニック料理のメニュー開発中。珍しい食材との組み合わせを探している。"
    },
    {
        "id": "tourist",
        "name": "観光客（熊本旅行中）",
        "base_conditions": {"person_count": "2人分", "genre": "郷土料理"},
        "description": "熊本旅行中で地元の料理を作ってみたい。調理器具が少ない宿泊先。"
    },
]

PROMPT_TEMPLATE = """あなたはクレソン料理AIのインタビュアーです。

ユーザー情報：{description}
収集済み条件：人数={person_count}、ジャンル={genre}

このユーザーに対して、より良いレシピを提案するための
追加情報を引き出すインタビューシナリオを3パターン作成してください。

各パターンでは：
1. インタビュアーが聞く追加質問（1問目）
2. ユーザーの想定回答
3. インタビュアーが聞く追加質問（2問目）
4. ユーザーの想定回答
5. この追加情報がレポートにどう活きるか（1行）

JSONのみ返してください（説明文不要）：
{{"scenarios": [
  {{
    "interviewer_q1": "質問1",
    "user_a1": "回答1",
    "interviewer_q2": "質問2",
    "user_a2": "回答2",
    "report_impact": "レポートへの影響"
  }}
]}}

質問のテーマ例（全部使わなくていい）：
- アレルギー・苦手食材
- 調理時間の制約
- 冷蔵庫にある食材
- 辛さの好み
- 特別な目的（お弁当・おもてなし等）
- 調理器具の制約"""


def extract_json(text):
    text = text.replace("```json", "").replace("```", "").strip()
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return json.loads(match.group())
    return json.loads(text)


results = []

for i, persona in enumerate(PERSONAS):
    print(f"\n[{i+1}/{len(PERSONAS)}] {persona['name']} のシナリオを生成中...", flush=True)
    if i > 0:
        time.sleep(3)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": PROMPT_TEMPLATE.format(
                    description=persona["description"],
                    person_count=persona["base_conditions"]["person_count"],
                    genre=persona["base_conditions"]["genre"],
                )
            }],
            temperature=0.7,
            max_tokens=1500,
        )

        content = response.choices[0].message.content or ""
        parsed = extract_json(content)

        for scenario in parsed["scenarios"]:
            scenario["persona_id"] = persona["id"]
            scenario["persona_name"] = persona["name"]
            scenario["base_genre"] = persona["base_conditions"]["genre"]
            results.append(scenario)
            print(f"  Q1: {scenario['interviewer_q1']}", flush=True)
            print(f"  Q2: {scenario['interviewer_q2']}", flush=True)

    except Exception as e:
        print(f"  エラー: {e}", flush=True)

output_path = os.path.join(os.path.dirname(__file__), "phase4b_scenarios.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump({"scenarios": results, "total": len(results)}, f,
              ensure_ascii=False, indent=2)

print(f"\n=== 収集完了 ===")
print(f"総シナリオ数: {len(results)}")
print(f"保存先: {output_path}")

q1_themes = [s["interviewer_q1"][:20] for s in results]
print("\n【Q1パターン一覧】")
for q in q1_themes:
    print(f"  - {q}...")
