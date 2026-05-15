import sys
from unittest.mock import MagicMock, patch

import pytest


# spacyがない環境でもtool_selectorテストを動かすためモック
_spacy_mock = MagicMock()
_doc_mock = MagicMock()
_doc_mock.__iter__ = MagicMock(return_value=iter([]))
_spacy_mock.load.return_value = _doc_mock
sys.modules.setdefault("spacy", _spacy_mock)


class TestToolSelector:
    def _make_tokens(self, text):
        token = MagicMock()
        token.text = text
        token.lemma_ = text
        return [token]

    def test_classify_type0_greeting(self):
        with patch("tool_selector.nlp") as mock_nlp:
            mock_nlp.return_value = self._make_tokens("こんにちは")
            from tool_selector import classify
            type0_map = {"こんにちは": "挨拶応答"}
            type1_map = {}
            result = classify("こんにちは！", type0_map, type1_map)
            assert result == "TYPE_0"

    def test_classify_type1_keyword(self):
        with patch("tool_selector.nlp") as mock_nlp:
            mock_nlp.return_value = self._make_tokens("熊本")
            from tool_selector import classify
            type0_map = {}
            type1_map = {"熊本": {"node_type": "Region", "param": "熊本"}}
            result = classify("熊本のクレソン料理", type0_map, type1_map)
            assert result == "TYPE_1"

    def test_classify_type2_fallback(self):
        with patch("tool_selector.nlp") as mock_nlp:
            mock_nlp.return_value = []
            from tool_selector import classify
            result = classify("クレソンパスタ", {}, {})
            assert result == "TYPE_2"

    def test_get_type0_response_known(self):
        with patch("tool_selector.nlp") as mock_nlp:
            mock_nlp.return_value = self._make_tokens("ありがとう")
            from tool_selector import get_type0_response
            type0_map = {"ありがとう": "どういたしまして！🌿"}
            result = get_type0_response("ありがとう", type0_map)
            assert "どういたしまして" in result

    def test_get_type0_response_unknown(self):
        with patch("tool_selector.nlp") as mock_nlp:
            mock_nlp.return_value = self._make_tokens("何か")
            from tool_selector import get_type0_response
            result = get_type0_response("何か変な言葉", {})
            assert "クレソン" in result


class TestDialogEngine:
    def test_get_next_question_first(self):
        from dialog_engine import get_next_question
        result = get_next_question({})
        assert result is not None
        assert "人" in result

    def test_get_next_question_all_collected(self):
        from dialog_engine import get_next_question
        conditions = {"person_count": "2", "genre": "和食", "usage": "主菜"}
        result = get_next_question(conditions)
        assert result is None

    def test_extract_condition(self):
        from dialog_engine import extract_condition
        result = extract_condition("person_count", "2人です")
        assert result == "2人です"

    def test_build_rag_query_with_conditions(self):
        from dialog_engine import build_rag_query
        conditions = {"genre": "和食", "usage": "スープ"}
        result = build_rag_query(conditions)
        assert "和食" in result
        assert "スープ" in result

    def test_build_rag_query_empty(self):
        from dialog_engine import build_rag_query
        result = build_rag_query({})
        assert "クレソン料理" in result

    def test_is_complete_turn3(self):
        from dialog_engine import is_complete
        assert is_complete({}, 3) is True

    def test_is_complete_not_yet(self):
        from dialog_engine import is_complete
        assert is_complete({}, 1) is False

    def test_is_complete_all_collected(self):
        from dialog_engine import is_complete
        conditions = {"person_count": "2", "genre": "和食", "usage": "主菜"}
        assert is_complete(conditions, 2) is True


class TestFormatDocs:
    def test_format_docs_basic(self):
        from app.rag import format_docs
        doc = MagicMock()
        doc.page_content = "クレソン炒めのレシピ"
        doc.metadata = {"region": "日本", "season": "通年", "use_case": "主菜"}
        result = format_docs([doc])
        assert "1. クレソン炒めのレシピ" in result
        assert "日本" in result

    def test_format_docs_multiple(self):
        from app.rag import format_docs
        docs = []
        for i in range(3):
            doc = MagicMock()
            doc.page_content = f"レシピ{i+1}"
            doc.metadata = {"region": "地域", "season": "春", "use_case": "副菜"}
            docs.append(doc)
        result = format_docs(docs)
        assert "1." in result
        assert "3." in result

    def test_format_docs_empty(self):
        from app.rag import format_docs
        result = format_docs([])
        assert result == ""


class TestReportCache:
    def test_cache_set_get(self):
        from app.cache import ReportCache
        cache = ReportCache()
        cache.set("key1", {"status": "done", "report": "test"})
        result = cache.get("key1")
        assert result["status"] == "done"

    def test_cache_delete(self):
        from app.cache import ReportCache
        cache = ReportCache()
        cache.set("key1", {"status": "done"})
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_cache_missing_key(self):
        from app.cache import ReportCache
        cache = ReportCache()
        assert cache.get("nonexistent") is None


class TestChatSmoke:
    def _make_app(self):
        from flask import Flask
        flask_app = Flask(__name__)
        flask_app.secret_key = "test-secret"
        from app.routes.chat import chat_bp
        flask_app.register_blueprint(chat_bp)
        return flask_app

    @patch("app.routes.chat.ensure_rag_system_initialized", return_value=True)
    def test_chat_empty_message(self, mock_init):
        app = self._make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["messages"] = []
            resp = client.post(
                "/chat",
                json={"message": ""},
            )
            assert resp.status_code == 400

    @patch("app.routes.chat.ensure_rag_system_initialized", return_value=True)
    def test_chat_message_too_long(self, mock_init):
        app = self._make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["messages"] = []
            resp = client.post(
                "/chat",
                json={"message": "あ" * 501},
            )
            assert resp.status_code == 400

    @patch("app.routes.chat.ensure_rag_system_initialized", return_value=True)
    def test_chat_stream_empty(self, mock_init):
        app = self._make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["messages"] = []
            resp = client.post(
                "/chat_stream",
                json={"message": ""},
            )
            assert resp.status_code == 400
