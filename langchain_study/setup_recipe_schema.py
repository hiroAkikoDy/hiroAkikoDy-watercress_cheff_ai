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

def setup_schema(tx):
    constraints = [
        """CREATE CONSTRAINT recipe_name IF NOT EXISTS
           FOR (r:Recipe) REQUIRE r.name IS UNIQUE""",
        """CREATE CONSTRAINT ingredient_name IF NOT EXISTS
           FOR (i:Ingredient) REQUIRE i.name IS UNIQUE""",
        """CREATE CONSTRAINT cookingmethod_name IF NOT EXISTS
           FOR (m:CookingMethod) REQUIRE m.name IS UNIQUE""",
        """CREATE CONSTRAINT intent_label IF NOT EXISTS
           FOR (t:Intent) REQUIRE t.label IS UNIQUE""",
        """CREATE CONSTRAINT cuisine_name IF NOT EXISTS
           FOR (c:Cuisine) REQUIRE c.name IS UNIQUE""",
    ]
    for cypher in constraints:
        try:
            tx.run(cypher)
            print(f"✓ 制約作成: {cypher[:50]}...")
        except Exception as e:
            print(f"  スキップ（既存）: {e}")

with driver.session(database=DB_NAME) as session:
    session.execute_write(setup_schema)
    print("\n✅ スキーマ制約作成完了")

with driver.session(database=DB_NAME) as session:
    result = session.run("SHOW CONSTRAINTS")
    print("\n現在の制約一覧:")
    for record in result:
        print(f"  {record['name']}: {record['labelsOrTypes']}")

driver.close()
