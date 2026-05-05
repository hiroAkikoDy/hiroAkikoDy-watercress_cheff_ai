import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'watercress_cheff_ai', '.env'))

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

def setup(tx):
    templates = [
        ("greeting",  ["こんにちは","こんばんは","はじめまして","よろしく","おはよう"],
         "こんにちは！ナナカファームのクレソン料理AIです🌿クレソンの使い方についてお気軽にどうぞ！"),
        ("thanks",    ["ありがとう","ありがとうございます","助かりました","参考になりました"],
         "お役に立てて嬉しいです🌿また気軽に聞いてくださいね！"),
        ("storage",   ["保存","日持ち","冷凍","鮮度","保管"],
         "クレソンは湿らせたキッチンペーパーで包み冷蔵庫の野菜室で保存すると3〜5日持ちます🌿"),
        ("nutrition", ["栄養","カロリー","ビタミン","ミネラル","健康"],
         "クレソンはビタミンC・K・カルシウムが豊富で鉄分も含まれます。特に抗酸化作用が高い野菜です🌿"),
    ]
    for pid, keywords, response in templates:
        tx.run("""
            MERGE (r:ResponseTemplate {pattern_id: $pid})
            SET r.keywords = $keywords,
                r.response = $response,
                r.tool_type = 'TYPE_0'
        """, pid=pid, keywords=keywords, response=response)

    patterns = [
        ("region_kumamoto", "Region", "熊本", ["熊本"]),
        ("region_tokyo",    "Region", "東京", ["東京","ねぎま"]),
        ("region_vietnam",  "Region", "ベトナム", ["ベトナム","ベトナム風"]),
        ("region_korea",    "Region", "韓国", ["韓国","キムチ"]),
        ("region_france",   "Region", "フランス", ["フランス","フレンチ"]),
        ("region_india",    "Region", "南インド", ["インド","南インド","カレー"]),
        ("season_spring",   "season", "春",  ["春","春向け"]),
        ("season_summer",   "season", "夏",  ["夏","夏向け"]),
        ("season_autumn",   "season", "秋",  ["秋","秋向け"]),
        ("season_winter",   "season", "冬",  ["冬","冬向け"]),
        ("season_year",     "season", "通年", ["通年","年中"]),
        ("use_nabe",        "use_case", "鍋料理",    ["鍋","鍋料理","すき焼き"]),
        ("use_salad",       "use_case", "サラダ",    ["サラダ"]),
        ("use_soup",        "use_case", "スープ",    ["スープ","汁物"]),
        ("use_izakaya",     "use_case", "居酒屋前菜", ["居酒屋","おつまみ","前菜"]),
        ("use_washoku",     "use_case", "和食",      ["和食","和風","和え物"]),
        ("use_omotenashi",  "use_case", "おもてなし", ["おもてなし","パーティー"]),
    ]
    for pid, ntype, param, keywords in patterns:
        tx.run("""
            MERGE (q:QueryPattern {pattern_id: $pid})
            SET q.node_type = $ntype,
                q.param = $param,
                q.keywords = $keywords,
                q.tool_type = 'TYPE_1'
        """, pid=pid, ntype=ntype, param=param, keywords=keywords)

with driver.session(database=os.getenv("NEO4J_USERNAME")) as session:
    session.execute_write(setup)
    print("✅ ResponseTemplate・QueryPatternノード作成完了")

driver.close()
