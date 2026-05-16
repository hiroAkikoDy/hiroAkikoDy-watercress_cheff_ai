"""抽出結果を確認するCypherクエリ集"""
import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'watercress_cheff_ai', '.env'))

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)
DB_NAME = os.getenv("NEO4J_USERNAME")

queries = {
    "ノード数確認": """
        MATCH (n)
        RETURN labels(n) AS label, count(n) AS count
        ORDER BY count DESC
    """,
    "Recipe一覧（上位10件）": """
        MATCH (r:Recipe)
        RETURN r.name, r.cuisine, r.confidence, r.needs_review
        ORDER BY r.confidence DESC
        LIMIT 10
    """,
    "Ingredient頻度ランキング": """
        MATCH (r:Recipe)-[:USES]->(i:Ingredient)
        RETURN i.name, count(r) AS recipe_count
        ORDER BY recipe_count DESC
        LIMIT 15
    """,
    "CookingMethod分布": """
        MATCH (r:Recipe)-[:COOKED_BY]->(m:CookingMethod)
        RETURN m.name, count(r) AS count
        ORDER BY count DESC
    """,
    "Intent分布": """
        MATCH (r:Recipe)-[:HAS_INTENT]->(t:Intent)
        RETURN t.label, count(r) AS count
        ORDER BY count DESC
    """,
    "ChunkとRecipeの接続確認": """
        MATCH (c:Chunk)-[:DESCRIBES]->(r:Recipe)
        RETURN count(c) AS connected_chunks
    """,
    "未接続Chunk数": """
        MATCH (c:Chunk)
        WHERE NOT (c)-[:DESCRIBES]->(:Recipe)
        RETURN count(c) AS unprocessed
    """,
    "レビュー必要なRecipe": """
        MATCH (r:Recipe {needs_review: true})
        RETURN r.name, r.confidence
        ORDER BY r.confidence ASC
        LIMIT 10
    """,
}

with driver.session(database=DB_NAME) as session:
    for title, cypher in queries.items():
        print(f"\n{'='*50}")
        print(f"📊 {title}")
        print('='*50)
        try:
            result = session.run(cypher)
            for record in result:
                print("  ", dict(record))
        except Exception as e:
            print(f"  エラー: {e}")

driver.close()
