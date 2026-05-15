# 🌿 ナナカファーム クレソン料理AI

> 熊本県産クレソンを手に取ったあなたに、今夜の食卓で使いこなせるレシピをご提案します。

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.0-green)](https://flask.palletsprojects.com)
[![LangChain](https://img.shields.io/badge/LangChain-Neo4j-orange)](https://python.langchain.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**デモ：** https://hiroakikody-watercress-cheff-ai.onrender.com

---

## 概要

熊本でクレソンを栽培するナナカファームが開発した、
個人客（BtoC）向けのクレソン料理アドバイザーWebアプリです。

「クレソンを買ってきたけど今夜どう使おう」
「すき焼きで余ったクレソンどうしよう」

そんな疑問に、世界19ジャンル190品超のクレソン料理データベースから
Neo4j Graph RAGが最適なレシピを提案します。

---

## スクリーンショット

| チャットUI | 出典展開 | レポート完成 |
|---|---|---|
| ![チャットUI](docs/screenshots/chat-ui.png) | ![出典展開](docs/screenshots/sources-expanded.png) | ![レポート完成](docs/screenshots/report-complete.png) |

> スクリーンショットは準備中です。実際の画面はデモをご覧ください。

---

## 特徴

- **Graph RAG**：Neo4j Aura + LangChain Hybrid Search（ベクトル＋キーワード）
- **ストリーミング応答**：回答が生成されるたびにリアルタイム表示
- **出典表示**：Neo4jのデータに基づいた根拠ある回答
- **BtoC設計**：家庭料理レベルでわかりやすい説明
- **スマートフォン対応**：直売会でその場で使えるUI

---

## アーキテクチャ

```
ユーザーの質問
    ↓
Flask（/chat_stream）
    ↓
Tool Selector（TYPE_0/TYPE_1/TYPE_3）
    ↓
LangChain Hybrid Search
  ├── ベクトル検索（OpenAI Embeddings）
  └── キーワード検索（Neo4j全文インデックス）
    ↓
Neo4j Aura Free（190品のクレソン料理グラフ）
    ↓
Z.ai GLM-4.7-Flash（回答生成）
    ↓
ストリーミングレスポンス
```

---

## 技術スタック

| カテゴリ | 技術 |
|---|---|
| Webフレームワーク | Flask 3.1.0 + Gunicorn 23.0.0 |
| LLM | Z.ai GLM-4.7-Flash |
| RAGフレームワーク | LangChain Neo4j |
| ベクトルDB | Neo4j Aura Free |
| Embedding | OpenAI text-embedding-3-small |
| デプロイ | Render Free Plan（15分アクセスなしでスリープ） |
| コーディングエージェント | Kilo Code × Z.ai BYOK |

---

## セットアップ

### 前提条件

- Python 3.11+
- Neo4j Aura Freeアカウント（[無料登録](https://neo4j.com/cloud/aura-free/)）
- Z.ai APIキー（[Z.ai](https://z.ai)）
- OpenAI APIキー（Embedding + ペルソナ生成・$5チャージで数年分）

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/hiroAkikoDy/hiroAkikoDy-watercress_cheff_ai.git
cd hiroAkikoDy-watercress_cheff_ai

# 仮想環境を作成
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# パッケージをインストール
pip install -r requirements.txt
```

### 環境変数の設定

`.env` ファイルをプロジェクトルートに作成：

```env
ZAI_API_KEY=あなたのZ.aiAPIキー
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=xxxxxxxx
NEO4J_PASSWORD=あなたのNeo4jパスワード
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
SECRET_KEY=任意のランダム文字列
```

> ⚠️ `.env` は絶対にGitにコミットしないでください

### 環境変数一覧

| 変数名 | 必須 | デフォルト | 用途 |
|---|---|---|---|
| `ZAI_API_KEY` | ✅ | - | Z.ai GLM-4.7-Flash APIキー |
| `NEO4J_URI` | ✅ | - | Neo4j Aura接続URI |
| `NEO4J_USERNAME` | ✅ | - | Neo4jユーザー名（Aura FreeではDB名と同じ） |
| `NEO4J_PASSWORD` | ✅ | - | Neo4jパスワード |
| `OPENAI_API_KEY` | ✅ | - | OpenAI APIキー（Embedding + ペルソナ生成） |
| `SECRET_KEY` | ✅ | - | Flask セッション暗号化キー |
| `LLM_TIMEOUT` | 任意 | `120` | LLM API タイムアウト（秒） |
| `LLM_MAX_TOKENS` | 任意 | `4096` | LLM 最大トークン数 |
| `LLM_MAX_RETRIES` | 任意 | `4` | LLM リトライ回数 |
| `LLM_MODEL` | 任意 | `GLM-4.7-Flash` | LLM モデル名 |
| `RETRIEVER_K` | 任意 | `3` | RAG 検索件数 |
| `PORT` | 任意 | `5000` | ローカル起動ポート |

### Neo4jデータの投入

```bash
cd langchain_study
python notion_to_neo4j.py   # Notionからデータ取得
python langchain_neo4j_setup.py  # Neo4jに190品を投入
```

### アプリの起動

```bash
python app.py
# http://localhost:5000 を開く
```

---

## ファイル構成

```
hiroAkikoDy-watercress_cheff_ai/
├── app.py                         # Flaskメインアプリ
├── tool_selector.py               # Tool Selector（TYPE_0/TYPE_1/TYPE_3分類）
├── dialog_engine.py               # TYPE_3対話エンジン
├── persona_engine.py              # マルチペルソナ生成
├── interviewer_engine.py          # インタビュアーAI
├── templates/
│   └── index.html                 # BtoC向けチャットUI
├── requirements.txt               # 依存パッケージ
├── render.yaml                    # Renderデプロイ設定
├── SECURITY.md                    # 脆弱性報告ポリシー
├── AGENTS.md                      # Kilo Code用プロジェクト説明書
├── docs/
│   └── screenshots/               # スクリーンショット
├── work_reports/                  # 作業レポート
└── langchain_study/               # 学習・実験スクリプト
    ├── langchain_neo4j_setup.py   # クレソンデータ投入
    ├── langchain_neo4j_search.py  # ベクトル検索
    ├── langchain_neo4j_rag.py     # RAGチェーン
    ├── langchain_text2cypher.py   # Text2Cypher
    └── notion_to_neo4j.py         # Notion→Neo4j連携
```

---

## 開発の記録（Zennブログシリーズ）

農家エンジニアがゼロからAIチャットボットを公開するまでの全記録です。

| 弾 | タイトル | 内容 |
|---|---|---|
| Vol.1 | [参考書のサンプルコードをZ.aiで動かした](https://zenn.dev/hiroakikody/articles/e6ed27a649fcec) | Z.ai GLM-4.7-Flash × OpenAI互換API |
| Vol.2 | [熊本のクレソン農家がAIチャットボットを作った](https://zenn.dev/hiroakikody/articles/ed0332b4c0f292) | Systemプロンプトのカスタマイズ・Flask化 |
| Vol.3 | [LLMのAPIを「概念と構造」で理解する](https://zenn.dev/hiroakikody/articles/0de29fff1522f5) | temperature・RAG・Session・10問クイズ |
| Vol.4 | [Claude Code×Render デプロイ5時間の記録](https://zenn.dev/hiroakikody/articles/73047160d069b8) | GLM-4.7推論モードエラー・Gunicornの罠 |
| Vol.5 | [Neo4j × LangChain × Z.aiでRAGを作った](https://zenn.dev/hiroakikody/articles/d553384e195f0b) | Graph RAG・Hybrid Search・keepalive |
| Vol.6 | 執筆中 | Phase 4 マルチペルソナ×対話型絞り込み |

---

## 実装上の重要な知見

本プロジェクトで発見したZ.ai・Neo4j固有の挙動です。

### GLM-4.7の推論モード対策

```python
# GLM-4.7はデフォルトで推論モード（thinking mode）が有効
# reasoning_contentが先にトークンを消費するため
# max_tokens=4096以上が必須

response = client.chat.completions.create(
    model="GLM-4.7-Flash",
    messages=messages,
    max_tokens=4096  # これがないと0バイトになる
)

# contentが空のときのフォールバック
answer = (
    response.choices[0].message.content
    or getattr(response.choices[0].message, 'reasoning_content', None)
)
```

### Neo4j Aura Free固有の設定

```python
# Aura FreeではDB名=ユーザー名
db = Neo4jVector.from_existing_index(
    ...
    database=os.getenv("NEO4J_USERNAME"),  # 必須
)
```

### Gunicornでスレッドを動かす

```python
# __main__の外（モジュールレベル）で起動する
start_keepalive()  # Gunicornでも動く

if __name__ == "__main__":
    app.run()
```

---

## ロードマップ

```
✅ Phase 1:  Flask + Z.ai → Renderデプロイ
✅ Phase 2:  Neo4j RAG + Hybrid Search → BtoC版本番公開
✅ Phase 3:  Tool Selector（3ツール自動選択）
✅ Phase 4:  マルチペルソナ × 対話型絞り込み + 非同期レポート
⏳ Phase 5:  半自動営業ツール化
```

> Phase 2の番号欠番について：当初Phase 2はGraph RAGの実験フェーズでした。
> Phase 1（Flask基盤）→ Phase 2（RAG実験）→ Phase 3（Tool Selector）→ Phase 4（対話型）と進行しました。
> 番号を詰めず、実験の軌跡を残すために欠番のままとしています。

---

## 関連ドキュメント

- [AGENTS.md](AGENTS.md) — 不変条件（INV_1〜INV_18）・技術スタック・コーディング規約
- [SECURITY.md](SECURITY.md) — 脆弱性報告ポリシー
- [docs/screenshots/](docs/screenshots/) — スクリーンショット
- [work_reports/](work_reports/) — 作業レポート

---

## 開発環境

本プロジェクトは以下のAI駆動開発ツールで構築されています：

- **Kilo Code**（VSCode拡張）× **Z.ai GLM-4.7 BYOK**
- コミットメッセージに `Co-Authored-By: Kilo Code` を記録

---

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照してください。

自由に使用・改変・再配布できます。
著作権表示と免責事項の保持をお願いします。

---

## 作者

**古閑 弘晃（こが ひろあき）**
ナナカファーム（熊本県）クレソン農家 × 大学院生

- 🌿 農場サイト：[nanaka-farm.com](https://nanaka-farm.com)
- 📝 Zenn：[@hiroakikody](https://zenn.dev/hiroakikody)
- 🤖 デモアプリ：[クレソン料理AI](https://hiroakikody-watercress-cheff-ai.onrender.com)

> 「農家がAIを使いこなせる時代を、実装で証明する」
