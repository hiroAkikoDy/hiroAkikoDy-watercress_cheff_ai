"""
#1 レシピ構造化エージェント（StagedChange版）

既存の Chunk ノードからレシピ情報を抽出し、
StagedChange に積む（本番グラフを直接書き換えない）。

承認時のアクション名: "create_recipe"
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.base import ask_llm_openai, get_driver, parse_json_response, stage, DB_NAME

SYSTEM_PROMPT = """あなたはレシピ構造化エディタです。
以下のクレソン料理テキストから、指定スキーマに沿ってJSONを抽出してください。

## 抽出スキーマ
{
  "recipe_name": "料理名（簡潔に）",
  "description": "料理の説明（1〜2文）",
  "cuisine": "料理ジャンル（例：和食・フランス料理・韓国料理）",
  "confidence": 0.0〜1.0,
  "needs_review": true/false（confidence < 0.7 の場合はtrue）,
  "ingredients": [
    {"name": "食材名", "is_required": true/false, "note": "分量や備考"}
  ],
  "cooking_methods": ["炒め", "茹で", "サラダ", "スープ", "和え", "蒸し", "揚げ", "生食", "焼き", "発酵"],
  "intents": ["余り活用", "時短", "健康", "おもてなし", "酒の肴", "お弁当", "ダイエット"],
  "region": "地域",
  "season": "季節"
}

## ルール
- 食材は調味料・油・だし類も含めて最大8件まで抽出すること
- intentは複数選んでよい（7種から選択）
- テキストに調理の背景や食文化の説明がある場合はdescriptionに含める
- クレソンは全レシピ共通なので食材リストから除外すること
- confidence < 0.5 の場合は抽出を断念してよい
- 出典がない情報を捏造することは禁止
- JSONのみ返すこと（説明文不要）"""


def get_unprocessed_chunks(driver, limit: int = 10) -> list[dict]:
    """StagedChangeにまだ積まれていないChunkを取得する"""
    with driver.session(database=DB_NAME) as session:
        result = session.run(
            """
            MATCH (c:Chunk)
            WHERE NOT (c)-[:DESCRIBES]->(:Recipe)
              AND NOT EXISTS {
                MATCH (s:StagedChange {status: 'pending'})
                WHERE s.payload CONTAINS c.text[..30]
              }
            RETURN c.text AS text,
                   c.region AS region,
                   c.season AS season,
                   c.use_case AS use_case,
                   elementId(c) AS chunk_id
            LIMIT $limit
            """,
            limit=limit,
        )
        return [dict(r) for r in result]


def run(driver, *, source_chunk_id: str, chunk_text: str,
        region: str = "", season: str = "", use_case: str = "") -> str | None:
    """
    Chunk1件を処理してStagedChangeに積む。

    Returns:
        作成した StagedChange の id（失敗時は None）
    """
    raw = ask_llm_openai(
        SYSTEM_PROMPT,
        f"テキスト：{chunk_text}\n地域：{region}\n季節：{season}\n用途：{use_case}",
    )

    try:
        data = parse_json_response(raw)
    except Exception as e:
        print(f"  ⚠️ JSONパースエラー: {e}")
        return None

    confidence = data.get("confidence", 0.0)
    if confidence < 0.5:
        print(f"  ⏭️ confidence={confidence:.2f} で採用不可 → スキップ")
        return None

    payload = {
        **data,
        "source_chunk_id": source_chunk_id,
    }

    staged_id = stage(
        driver,
        agent="recipe_extractor",
        action="create_recipe",
        payload=payload,
        confidence=confidence,
        evidence=[f"chunk:{source_chunk_id}"],
    )
    return staged_id


def run_batch(limit: int = 10) -> None:
    """未処理Chunkをバッチ処理してStagedChangeに積む"""
    driver = get_driver()
    chunks = get_unprocessed_chunks(driver, limit=limit)

    if not chunks:
        print("✅ 処理対象のChunkがありません")
        driver.close()
        return

    print(f"処理対象: {len(chunks)}件")
    success = 0

    for i, chunk in enumerate(chunks, 1):
        print(f"\n[{i}/{len(chunks)}] {chunk['text'][:50]}...")
        time.sleep(1)

        staged_id = run(
            driver,
            source_chunk_id=chunk["chunk_id"],
            chunk_text=chunk["text"],
            region=chunk.get("region", ""),
            season=chunk.get("season", ""),
            use_case=chunk.get("use_case", ""),
        )

        if staged_id:
            print(f"  ✓ StagedChange作成: {staged_id[:8]}...")
            success += 1
        else:
            print("  ✗ スキップ")

    driver.close()
    print(f"\n完了: {success}/{len(chunks)}件をStagingに積みました")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    run_batch(limit=args.limit)
