"""
Step 1 動作確認スクリプト。
ダミーのChunkテキストを渡してStagedChangeが1件作成されることを確認する。
"""
import os
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.base import get_driver, DB_NAME
from agents import recipe_extractor

DUMMY_CHUNK = {
    "chunk_id": "test-chunk-001",
    "chunk_text": "クレソンのバターソテーはフライパンでバターを溶かし、クレソンをさっと炒める。"
                  "塩・コショウで味を調え、にんにくを加えると風味が増す。簡単に作れる副菜。",
    "region": "熊本",
    "season": "春",
    "use_case": "副菜",
}

def test():
    driver = get_driver()

    print("=" * 50)
    print("🧪 Step 1 動作確認")
    print("=" * 50)
    print(f"\n入力テキスト: {DUMMY_CHUNK['chunk_text'][:60]}...")

    staged_id = recipe_extractor.run(
        driver,
        source_chunk_id=DUMMY_CHUNK["chunk_id"],
        chunk_text=DUMMY_CHUNK["chunk_text"],
        region=DUMMY_CHUNK["region"],
        season=DUMMY_CHUNK["season"],
        use_case=DUMMY_CHUNK["use_case"],
    )

    if not staged_id:
        print("\n❌ StagedChange の作成に失敗しました")
        driver.close()
        return

    import json
    with driver.session(database=DB_NAME) as session:
        result = session.run(
            "MATCH (s:StagedChange {id: $id}) RETURN s",
            id=staged_id,
        ).single()

        if result:
            s = dict(result["s"])
            payload = json.loads(s.get("payload", "{}"))
            print(f"\n✅ StagedChange 作成成功")
            print(f"   id:         {s['id'][:8]}...")
            print(f"   agent:      {s['agent']}")
            print(f"   action:     {s['action']}")
            print(f"   confidence: {s['confidence']}")
            print(f"   status:     {s['status']}")
            print(f"   料理名:     {payload.get('recipe_name', '不明')}")
            print(f"   食材:       {[i['name'] for i in payload.get('ingredients', [])]}")

        session.run(
            "MATCH (s:StagedChange {id: $id}) DELETE s",
            id=staged_id,
        )
        print(f"\n🧹 テストノードを削除しました")

    driver.close()
    print("\n🎉 Step 1 動作確認 OK")

if __name__ == "__main__":
    test()
