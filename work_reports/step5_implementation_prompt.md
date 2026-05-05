## 作業依頼：Phase 3b Tool Selector実装（Issue #8）

### 前提確認
作業開始前に以下を確認すること：
1. AGENTS.md の INV_7〜INV_10 を読む
2. langchain_study/tool_selector.als の3チェックが
   No counterexample であることを確認（WORK_REPORT_20260505_1400.md参照）
3. Issue #6（spaCy動作確認）が完了していること

### Step A：Neo4jノードの準備
langchain_study/setup_tool_selector.py を新規作成して実行する。

```python
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

def setup(tx):
    # ResponseTemplateノード（TYPE_0）
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

    # QueryPatternノード（TYPE_1）
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
```

実行：
cd langchain_study
python setup_tool_selector.py

### Step B：tool_selector.py の作成
watercress_cheff_ai/tool_selector.py を新規作成する。

```python
import os
import spacy
from neo4j import GraphDatabase
from typing import Literal

# spaCyモデル読み込み
try:
    nlp = spacy.load("ja_core_news_sm")
except OSError:
    raise RuntimeError(
        "ja_core_news_smが見つかりません。"
        "python -m spacy download ja_core_news_sm を実行してください。"
    )

# Neo4jからキーワード辞書を読み込む
def load_keyword_patterns(driver, db_name):
    type0_map = {}
    type1_map = {}
    with driver.session(database=db_name) as session:
        # TYPE_0
        result = session.run("""
            MATCH (r:ResponseTemplate)
            RETURN r.keywords AS keywords, r.response AS response
        """)
        for rec in result:
            for kw in rec["keywords"]:
                type0_map[kw] = rec["response"]
        # TYPE_1
        result = session.run("""
            MATCH (q:QueryPattern)
            RETURN q.keywords AS keywords,
                   q.node_type AS node_type,
                   q.param AS param
        """)
        for rec in result:
            for kw in rec["keywords"]:
                type1_map[kw] = {
                    "node_type": rec["node_type"],
                    "param": rec["param"]
                }
    return type0_map, type1_map


def classify(
    question: str,
    type0_map: dict,
    type1_map: dict
) -> Literal["TYPE_0", "TYPE_1", "TYPE_2"]:
    """
    INV_7: 排他的に1つのTypeを返す
    INV_8: TYPE_0にはRAGを適用しない
    INV_9: キーワードなしはTYPE_2へフォールバック
    """
    doc = nlp(question)
    tokens = [token.text for token in doc]
    tokens += [token.lemma_ for token in doc]

    # TYPE_0チェック（優先）
    for token in tokens:
        if token in type0_map:
            return "TYPE_0"

    # TYPE_1チェック
    for token in tokens:
        if token in type1_map:
            return "TYPE_1"

    # TYPE_2フォールバック（INV_9）
    return "TYPE_2"


def get_type0_response(question: str, type0_map: dict) -> str:
    doc = nlp(question)
    tokens = [token.text for token in doc]
    tokens += [token.lemma_ for token in doc]
    for token in tokens:
        if token in type0_map:
            return type0_map[token]
    return "クレソンの使い方についてお気軽にどうぞ😊"


def get_type1_response(question: str, type1_map: dict, driver, db_name: str) -> str:
    doc = nlp(question)
    tokens = [token.text for token in doc]
    tokens += [token.lemma_ for token in doc]

    matched = None
    for token in tokens:
        if token in type1_map:
            matched = type1_map[token]
            break

    if not matched:
        return None

    node_type = matched["node_type"]
    param = matched["param"]

    with driver.session(database=db_name) as session:
        if node_type == "Region":
            result = session.run("""
                MATCH (c:Chunk)
                WHERE c.region = $param
                RETURN c.text AS text, c.season AS season, c.use_case AS use_case
                LIMIT 3
            """, param=param)
        elif node_type == "season":
            result = session.run("""
                MATCH (c:Chunk)
                WHERE c.season CONTAINS $param
                RETURN c.text AS text, c.region AS region, c.use_case AS use_case
                LIMIT 3
            """, param=param)
        elif node_type == "use_case":
            result = session.run("""
                MATCH (c:Chunk)
                WHERE c.use_case CONTAINS $param
                RETURN c.text AS text, c.region AS region, c.season AS season
                LIMIT 3
            """, param=param)
        else:
            return None

        records = list(result)
        if not records:
            return None

        lines = [f"「{param}」に関するクレソン料理をご紹介します🌿\n"]
        for i, rec in enumerate(records, 1):
            lines.append(f"{i}. {rec['text']}")
        return "\n".join(lines)
```

### Step C：app.py の /chat_stream エンドポイントを修正

app.py の先頭付近（既存のimport群の後）に追加：

```python
from tool_selector import (
    load_keyword_patterns, classify,
    get_type0_response, get_type1_response
)
```

initialize_rag_system() の末尾に追加：

```python
# Tool Selectorのキーワード辞書を読み込む
global type0_map, type1_map
neo4j_driver = db._driver
db_name = os.getenv("NEO4J_USERNAME")
type0_map, type1_map = load_keyword_patterns(neo4j_driver, db_name)
print(f"✓ Tool Selector辞書読み込み完了 "
      f"(TYPE_0: {len(type0_map)}件, TYPE_1: {len(type1_map)}件)")
```

グローバル変数宣言に追加：

```python
type0_map = {}
type1_map = {}
```

/chat_stream エンドポイント内の
「source_docs = retriever.invoke(user_message)」の前に以下を挿入：

```python
# Tool Selectorで分類（INV_7〜INV_10）
tool_type = classify(user_message, type0_map, type1_map)
print(f"Tool Selector: {tool_type} ← 「{user_message[:20]}」")

if tool_type == "TYPE_0":
    response_text = get_type0_response(user_message, type0_map)
    messages.append({"role": "assistant", "content": response_text})
    session["messages"] = messages
    session.modified = True
    def generate_type0():
        yield f"data: {response_text}\n\n"
    return Response(
        generate_type0(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

if tool_type == "TYPE_1":
    neo4j_driver = db._driver
    db_name = os.getenv("NEO4J_USERNAME")
    type1_response = get_type1_response(
        user_message, type1_map, neo4j_driver, db_name
    )
    if type1_response:
        messages.append({"role": "assistant", "content": type1_response})
        session["messages"] = messages
        session.modified = True
        def generate_type1():
            for char in type1_response:
                yield f"data: {char}\n\n"
        return Response(
            generate_type1(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    # TYPE_1でデータが取得できなかった場合はTYPE_2にフォールバック

# TYPE_2: 既存のRAGパイプラインをそのまま使用
```

### 確認事項
- INV_7〜INV_10をすべて満たすこと
- app.pyの既存INV_1〜INV_6は変更しないこと
- spaCyのインポートエラー時は明確なメッセージを出すこと
- TYPE_1でデータが0件の場合はTYPE_2にフォールバックすること
- コミットメッセージ: feat: Phase 3b Tool Selector実装（Issue #8）
- WORK_REPORTを work_reports/ に保存すること
- git push origin mainまで実行すること

### AGENTS.mdへの追記
以下をINV_6の直後に追記すること：

INV_7: Tool SelectorはTYPE_0・TYPE_1・TYPE_2の
        いずれか1つに質問を分類する（排他性）
        Alloy検証（ExclusiveClassification）で証明済み。

INV_8: TYPE_0（挨拶・定型応答）にはRAGを適用しない
        ResponseTemplateノードからの固定文返却のみ許可する。
        Alloy検証（NoRAGForGreeting）で証明済み。

INV_9: キーワードが検出されない質問はTYPE_2（RAG）に落とす
        フォールバック経路として現在のRAGパイプラインを維持する。
        Alloy検証（EmptyKeywordFallsToRAG）で証明済み。

INV_10: Tool Selectorのキーワード辞書はNeo4jのQueryPatternノードで管理する
        Pythonコードにキーワードをハードコードしない。
