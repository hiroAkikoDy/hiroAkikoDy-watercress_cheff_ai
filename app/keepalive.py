import logging
import threading
import time

logger = logging.getLogger(__name__)


def neo4j_keepalive():
    import app.rag as rag_module
    time.sleep(30)
    max_retries = 5
    consecutive_failures = 0
    while True:
        try:
            _db = rag_module.db
            if _db is not None:
                _db._driver.verify_connectivity()
                logger.info("Neo4j keepalive: OK")
                consecutive_failures = 0
            else:
                logger.warning("Neo4j db が未初期化、初期化を試みます")
                rag_module.initialize_rag_system()
        except Exception as e:
            consecutive_failures += 1
            if consecutive_failures > max_retries:
                logger.error("Neo4j keepalive: 最大リトライ到達、待機を継続: %s", e)
                consecutive_failures = max_retries
            else:
                wait = min(2 ** consecutive_failures, 300)
                logger.warning(
                    "Neo4j keepalive error (試行 %d/%d): %s — %ds後にリトライ",
                    consecutive_failures, max_retries, e, wait,
                )
                time.sleep(wait)
                continue
        time.sleep(270)


def start_keepalive():
    keepalive_thread = threading.Thread(
        target=neo4j_keepalive, daemon=True
    )
    keepalive_thread.start()
    logger.info("Neo4j keepaliveスレッド開始")
