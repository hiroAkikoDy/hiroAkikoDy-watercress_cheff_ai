"""
自己進化グラフ エージェント共通基盤

全エージェントが使う：
- ask_llm(): Z.ai GLM-4.7-Flash 呼び出し
- ask_llm_openai(): OpenAI gpt-4o-mini 呼び出し（精度が必要な場合）
- stage(): StagedChange ノードへの書き込み
"""
import json
import os
import sys
import uuid
from datetime import datetime

from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

zai_client = OpenAI(
    api_key=os.getenv("ZAI_API_KEY"),
    base_url="https://api.z.ai/api/paas/v4/",
    timeout=60,
)

openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=60,
)


def ask_llm_zai(system: str, user: str, max_tokens: int = 2048) -> str:
    """Z.ai GLM-4.7-Flash でJSON形式の回答を取得する"""
    response = zai_client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "GLM-4.7-Flash"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def ask_llm_openai(system: str, user: str, max_tokens: int = 2048) -> str:
    """OpenAI gpt-4o-mini でJSON形式の回答を取得する"""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.1,
    )
    return response.choices[0].message.content or ""


def get_driver():
    """Neo4j ドライバーを返す（INV_2: database=NEO4J_USERNAME）"""
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
    )


DB_NAME = os.getenv("NEO4J_USERNAME")


def stage(
    driver,
    *,
    agent: str,
    action: str,
    payload: dict,
    confidence: float,
    evidence: list[str],
) -> str:
    """
    StagedChange ノードに提案を書き込む。
    エージェントは本番グラフを直接書き換えない（Human-in-the-loop設計）。

    Returns:
        作成した StagedChange の id
    """
    staged_id = str(uuid.uuid4())
    with driver.session(database=DB_NAME) as session:
        session.run(
            """
            CREATE (s:StagedChange {
                id: $id,
                agent: $agent,
                action: $action,
                payload: $payload,
                confidence: $confidence,
                evidence: $evidence,
                created_at: datetime(),
                status: 'pending'
            })
            """,
            id=staged_id,
            agent=agent,
            action=action,
            payload=json.dumps(payload, ensure_ascii=False),
            confidence=confidence,
            evidence=evidence,
        )
    return staged_id


def parse_json_response(raw: str) -> dict:
    """LLMの応答からJSONを安全にパースする"""
    clean = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)
