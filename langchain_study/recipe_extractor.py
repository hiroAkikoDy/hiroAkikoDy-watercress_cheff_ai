"""
#1 レシピ構造化エージェント（Recipe Extractor）
既存のChunkノードからRecipe・Ingredient・CookingMethodを抽出し
実体グラフとして追加する。

設計原則：
- 既存Chunkノードは絶対に変更しない
- MERGE文でべき等性を保証する
- 信頼度(confidence)が0.7未満の抽出はneeds_review=Trueフラグを立てる
- Human-in-the-loopを基本とする（バッチサイズ5件ずつ確認）
"""
import os
import sys
import json
import time
from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'watercress_cheff_ai', '.env'))

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)
DB_NAME = os.getenv("NEO4J_USERNAME")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EXTRACTION_PROMPT = """あなたはレシピ構造化エディタです。
以下のクレソン料理テキストから、指定スキーマに沿ってJSONを抽出してください。

テキスト：
{chunk_text}

メタデータ：
- 地域: {region}
- 季節: {season}
- 用途: {use_case}

## 抽出スキーマ

```json
{{
  "recipe_name": "料理名（簡潔に）",
  "description": "料理の説明（1〜2文）",
  "confidence": 0.0〜1.0（抽出の確信度）,
  "needs_review": true/false（confidence < 0.7 の場合はtrue）,
  "ingredients": [
    {{
      "name": "食材名",
      "is_required": true/false,
      "note": "分量や備考（任意）"
    }}
  ],
  "cooking_methods": ["調理法1", "調理法2"],
  "intents": ["余り活用", "時短", "健康", "おもてなし", "酒の肴"],
  "cuisine": "料理ジャンル（例：和食・ベトナム料理・韓国料理）",
  "region": "地域",
  "season": "季節"
}}
```

## ルール
- 食材は最低2つ抽出すること
- 調理法は「炒め」「茹で」「サラダ」「スープ」「和え」「蒸し」「揚げ」「生食」から選ぶ
- intentは本文から推測できるもののみ記載（確信がなければ空配列）
- recipe_nameはテキストの最初に出てくる料理名を使う
- クレソンは食材として含めない（すべてのレシピに共通のため）
- 食材は調味料・油・だし類も含めて最大8件まで抽出すること
  例：ごま油・醤油・みりん・塩・だし・砂糖・酢・オリーブオイル
- intentは以下から複数選んでよい：
  「余り活用」「時短」「健康」「おもてなし」「酒の肴」「お弁当」「ダイエット」
- テキストに調理の背景や食文化の説明がある場合はdescriptionに含める
- JSONのみ返すこと（説明文不要）"""


def get_unprocessed_chunks(limit: int = 5) -> list[dict]:
    with driver.session(database=DB_NAME) as session:
        result = session.run("""
            MATCH (c:Chunk)
            WHERE NOT (c)-[:DESCRIBES]->(:Recipe)
            RETURN c.text AS text,
                   c.region AS region,
                   c.season AS season,
                   c.use_case AS use_case,
                   elementId(c) AS chunk_id
            LIMIT $limit
        """, limit=limit)
        return [dict(r) for r in result]


def count_unprocessed() -> int:
    with driver.session(database=DB_NAME) as session:
        result = session.run("""
            MATCH (c:Chunk)
            WHERE NOT (c)-[:DESCRIBES]->(:Recipe)
            RETURN count(c) AS cnt
        """)
        return result.single()["cnt"]


def create_recipe_subgraph(tx, chunk_id: str, data: dict):
    tx.run("""
        MATCH (c:Chunk) WHERE elementId(c) = $chunk_id
        MERGE (r:Recipe {name: $recipe_name})
        SET r.description = $description,
            r.cuisine = $cuisine,
            r.region = $region,
            r.season = $season,
            r.confidence = $confidence,
            r.needs_review = $needs_review,
            r.created_at = datetime()
        MERGE (c)-[:DESCRIBES]->(r)
    """,
        chunk_id=chunk_id,
        recipe_name=data["recipe_name"],
        description=data.get("description", ""),
        cuisine=data.get("cuisine", ""),
        region=data.get("region", ""),
        season=data.get("season", ""),
        confidence=data["confidence"],
        needs_review=data["needs_review"]
    )

    for ing in data.get("ingredients", []):
        tx.run("""
            MERGE (i:Ingredient {name: $name})
            WITH i
            MATCH (r:Recipe {name: $recipe_name})
            MERGE (r)-[:USES {is_required: $is_required, note: $note}]->(i)
        """,
            name=ing["name"],
            recipe_name=data["recipe_name"],
            is_required=ing.get("is_required", True),
            note=ing.get("note", "")
        )

    for method in data.get("cooking_methods", []):
        tx.run("""
            MERGE (m:CookingMethod {name: $name})
            WITH m
            MATCH (r:Recipe {name: $recipe_name})
            MERGE (r)-[:COOKED_BY]->(m)
        """,
            name=method,
            recipe_name=data["recipe_name"]
        )

    for intent in data.get("intents", []):
        tx.run("""
            MERGE (t:Intent {label: $label})
            WITH t
            MATCH (r:Recipe {name: $recipe_name})
            MERGE (r)-[:HAS_INTENT]->(t)
        """,
            label=intent,
            recipe_name=data["recipe_name"]
        )


def extract_recipe(chunk: dict) -> dict | None:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT.format(
                    chunk_text=chunk["text"],
                    region=chunk.get("region", "不明"),
                    season=chunk.get("season", "不明"),
                    use_case=chunk.get("use_case", "不明"),
                )
            }],
            temperature=0.1,
            max_tokens=1000,
        )
        content = response.choices[0].message.content or ""
        clean = content.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        print(f"  ⚠️ 抽出エラー: {e}")
        return None


def run_batch(batch_size: int = 5, auto_approve: bool = False):
    total_unprocessed = count_unprocessed()
    print(f"\n未処理Chunk: {total_unprocessed}件")

    if total_unprocessed == 0:
        print("✅ 全件処理済みです")
        return

    chunks = get_unprocessed_chunks(limit=batch_size)
    print(f"\n今回の処理: {len(chunks)}件")
    print("=" * 60)

    approved = []
    skipped = []

    for i, chunk in enumerate(chunks, 1):
        print(f"\n[{i}/{len(chunks)}] 抽出中...")
        print(f"  テキスト: {chunk['text'][:60]}...")

        time.sleep(1)
        data = extract_recipe(chunk)

        if not data:
            print("  ❌ 抽出失敗 → スキップ")
            skipped.append(chunk)
            continue

        print(f"  📌 料理名: {data['recipe_name']}")
        print(f"  🥬 食材: {[i['name'] for i in data.get('ingredients', [])]}")
        print(f"  🍳 調理法: {data.get('cooking_methods', [])}")
        print(f"  🎯 用途: {data.get('intents', [])}")
        print(f"  📊 信頼度: {data['confidence']:.2f}")

        if data["needs_review"]:
            print("  ⚠️ 信頼度低 → needs_review=True")

        if auto_approve:
            if data["confidence"] >= 0.7:
                approved.append((chunk, data))
                print("  ✅ 自動承認")
            else:
                skipped.append(chunk)
                print("  ⏭️ 信頼度不足でスキップ")
        else:
            ans = input("  承認しますか？ [y/n/s(skip)]: ").strip().lower()
            if ans == "y":
                approved.append((chunk, data))
                print("  ✅ 承認")
            else:
                skipped.append(chunk)
                print("  ⏭️ スキップ")

    if approved:
        print(f"\n\nNeo4jに書き込み中... ({len(approved)}件)")
        with driver.session(database=DB_NAME) as session:
            for chunk, data in approved:
                try:
                    session.execute_write(
                        create_recipe_subgraph,
                        chunk["chunk_id"],
                        data
                    )
                    print(f"  ✓ {data['recipe_name']}")
                except Exception as e:
                    print(f"  ✗ {data['recipe_name']}: {e}")

    print("\n" + "=" * 60)
    print(f"承認・書き込み: {len(approved)}件")
    print(f"スキップ:       {len(skipped)}件")
    remaining = count_unprocessed()
    print(f"残り未処理:     {remaining}件")

    if remaining > 0:
        cont = input(f"\n次の{batch_size}件を処理しますか？ [y/n]: ").strip().lower()
        if cont == "y":
            run_batch(batch_size=batch_size, auto_approve=auto_approve)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Recipe Extractor Agent")
    parser.add_argument("--batch", type=int, default=5, help="バッチサイズ（デフォルト5）")
    parser.add_argument("--auto", action="store_true", help="自動承認モード（confidence>=0.7）")
    args = parser.parse_args()

    print("=" * 60)
    print("🌿 Recipe Extractor Agent 起動")
    print(f"   バッチサイズ: {args.batch}")
    print(f"   モード: {'自動承認' if args.auto else 'Human-in-the-loop'}")
    print("=" * 60)

    run_batch(batch_size=args.batch, auto_approve=args.auto)
    driver.close()
    print("\n✅ 完了")
