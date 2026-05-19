import logging
import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_neo4j import Neo4jVector
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

logger = logging.getLogger(__name__)

db = None
retriever = None
rag_chain = None
type0_map = {}
type1_map = {}

LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
RETRIEVER_K = int(os.getenv("RETRIEVER_K", "3"))
MODEL_NAME = os.getenv("LLM_MODEL", "GLM-4.7-Flash")

SYSTEM_PROMPT_TEMPLATE = """あなたは「ナナカファームのクレソン料理アドバイザー」です。
熊本の清らかな水で育てたクレソンを手に取ったあなたに、
今夜の食卓で使いこなせるレシピをご提案します。

【得意なこと】
・家庭で作れる具体的なレシピと調理のポイント
・冷蔵庫にある食材とクレソンの組み合わせ提案
・余ったクレソンの翌日活用法
・クレソンの栄養・保存方法のアドバイス
・世界19ジャンル190品超のクレソン料理の知識

【回答スタイル】
・家庭料理レベルでわかりやすく説明する
・材料は身近なスーパーで手に入るものを使う
・クレソン料理に関係ない質問には
  「クレソンの使い方についてお気軽にどうぞ😊」と答える

【参考データ】
{context}

質問: {question}

回答:"""


def format_docs(docs):
    formatted = []
    for i, doc in enumerate(docs, 1):
        formatted.append(f"{i}. {doc.page_content}")
        formatted.append(f"   - 地域: {doc.metadata.get('region', '不明')}")
        formatted.append(f"   - 季節: {doc.metadata.get('season', '不明')}")
        formatted.append(f"   - 用途: {doc.metadata.get('use_case', '不明')}")
        validated = doc.metadata.get("validated")
        if validated is not None:
            score = doc.metadata.get("final_score", 0)
            mark = "★実食検証済" if validated else ""
            formatted.append(f"   - 検証スコア: {score:.2f} {mark}")
    return "\n".join(formatted)


def rerank_by_final_score(docs, driver=None, db_name=None):
    if not docs:
        return docs
    if driver is None and db is None:
        return docs
    _driver = driver or db._driver
    _db_name = db_name or os.getenv("NEO4J_USERNAME")
    try:
        scores = {}
        with _driver.session(database=_db_name) as session:
            for doc in docs:
                chunk_text = doc.page_content[:80]
                result = session.run(
                    """
                    MATCH (c:Chunk)-[:DESCRIBES]->(r:Recipe)
                    WHERE c.text STARTS WITH $prefix
                    RETURN r.final_score AS fs, r.validated AS v
                    LIMIT 1
                    """,
                    prefix=chunk_text,
                )
                record = result.single()
                if record and record["fs"] is not None:
                    scores[id(doc)] = record["fs"]
                else:
                    scores[id(doc)] = 0.45
        return sorted(docs, key=lambda d: scores.get(id(d), 0.45), reverse=True)
    except Exception as e:
        logger.warning("rerank_by_final_score error: %s", e)
        return docs


def initialize_rag_system():
    global db, retriever, rag_chain, type0_map, type1_map

    try:
        logger.info("Neo4jに接続中...")
        db = Neo4jVector.from_existing_index(
            OpenAIEmbeddings(),
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            index_name="watercress_index",
            keyword_index_name="watercress_keyword_index",
            search_type="hybrid",
            database=os.getenv("NEO4J_USERNAME"),
        )
        logger.info("Neo4j接続成功")

        retriever = db.as_retriever(search_kwargs={"k": RETRIEVER_K})
        logger.info("Retriever作成完了")

        llm = ChatOpenAI(
            model=MODEL_NAME,
            openai_api_key=os.getenv("ZAI_API_KEY"),
            openai_api_base="https://api.z.ai/api/paas/v4/",
            temperature=0.7,
            timeout=LLM_TIMEOUT,
            max_tokens=LLM_MAX_TOKENS,
        )
        logger.info("LLM初期化完了")

        prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT_TEMPLATE)

        _rerank = RunnableLambda(lambda docs: rerank_by_final_score(docs))

        rag_chain = (
            {"context": retriever | _rerank | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
        logger.info("RAGチェーン構築完了")

        from tool_selector import load_keyword_patterns
        neo4j_driver = db._driver
        db_name = os.getenv("NEO4J_USERNAME")
        type0_map, type1_map = load_keyword_patterns(neo4j_driver, db_name)
        logger.info(
            "Tool Selector辞書読み込み完了 "
            f"(TYPE_0: {len(type0_map)}件, TYPE_1: {len(type1_map)}件)"
        )

        return True

    except Exception as e:
        logger.error("RAGシステムの初期化に失敗しました: %s", str(e))
        return False


def ensure_rag_system_initialized():
    if rag_chain is not None and retriever is not None:
        return True
    return initialize_rag_system()
