"""
Neo4j に Cypher ファイルを実行するユーティリティスクリプト。

使い方：
    python scripts/run_cypher.py scripts/init_evolution_schema.cypher

既存の app/rag.py と同じ環境変数・接続方式を使う。
"""
import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

def run_cypher_file(filepath: str) -> None:
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    db_name = username

    if not all([uri, username, password]):
        print("❌ 環境変数 NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD が未設定です")
        sys.exit(1)

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    statements = [
        "\n".join(
            line for line in s.split("\n")
            if line.strip() and not line.strip().startswith("//")
        ).strip()
        for s in content.split(";")
    ]
    statements = [s for s in statements if s]

    driver = GraphDatabase.driver(uri, auth=(username, password))

    try:
        with driver.session(database=db_name) as session:
            for i, stmt in enumerate(statements, 1):
                if not stmt:
                    continue
                try:
                    session.run(stmt)
                    print(f"✓ [{i}/{len(statements)}] 実行成功: {stmt[:60]}...")
                except Exception as e:
                    print(f"  スキップ（既存の可能性あり）: {e}")
        print(f"\n✅ {filepath} の実行完了")
    finally:
        driver.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python scripts/run_cypher.py <cypherファイルパス>")
        sys.exit(1)
    run_cypher_file(sys.argv[1])
