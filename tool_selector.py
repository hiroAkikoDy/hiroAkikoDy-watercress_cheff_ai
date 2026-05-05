import os
import spacy
from neo4j import GraphDatabase
from typing import Literal

try:
    nlp = spacy.load("ja_core_news_sm")
except OSError:
    raise RuntimeError(
        "ja_core_news_smが見つかりません。"
        "python -m spacy download ja_core_news_sm を実行してください。"
    )


def load_keyword_patterns(driver, db_name):
    type0_map = {}
    type1_map = {}
    with driver.session(database=db_name) as session:
        result = session.run("""
            MATCH (r:ResponseTemplate)
            RETURN r.keywords AS keywords, r.response AS response
        """)
        for rec in result:
            for kw in rec["keywords"]:
                type0_map[kw] = rec["response"]
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

    for token in tokens:
        if token in type0_map:
            return "TYPE_0"

    for token in tokens:
        if token in type1_map:
            return "TYPE_1"

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
