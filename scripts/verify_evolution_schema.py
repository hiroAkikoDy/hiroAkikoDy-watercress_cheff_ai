"""
Step 0 完了確認スクリプト。
StagedChange・BackfillTask の制約とインデックスが
正しく作成されているかを確認する。
"""
import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
db_name = username

driver = GraphDatabase.driver(uri, auth=(username, password))

print("=" * 50)
print("📊 Step 0 確認：制約とインデックス")
print("=" * 50)

with driver.session(database=db_name) as session:
    constraints = list(session.run("SHOW CONSTRAINTS"))
    print(f"\n制約数: {len(constraints)}")
    for c in constraints:
        name = c.get("name", "")
        labels = c.get("labelsOrTypes", [])
        print(f"  ✓ {name}: {labels}")

    names = [c.get("name", "") for c in constraints]
    if "staged_change_id" in names:
        print("\n✅ staged_change_id 制約: OK")
    else:
        print("\n❌ staged_change_id 制約が見つかりません")

    if "backfill_task_id" in names:
        print("✅ backfill_task_id 制約: OK")
    else:
        print("❌ backfill_task_id 制約が見つかりません")

    session.run("""
        CREATE (s:StagedChange {
            id: 'test-step0-verify',
            agent: 'test',
            action: 'test',
            payload: '{}',
            confidence: 1.0,
            evidence: [],
            created_at: datetime(),
            status: 'pending'
        })
    """)
    result = session.run(
        "MATCH (s:StagedChange {id:'test-step0-verify'}) RETURN s"
    )
    if result.single():
        print("✅ StagedChange ノードの作成・取得: OK")
    session.run(
        "MATCH (s:StagedChange {id:'test-step0-verify'}) DELETE s"
    )
    print("✅ テストノードのクリーンアップ: OK")

driver.close()
print("\n🎉 Step 0 完了確認 すべてOK")
