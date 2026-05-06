# ナナカファーム クレソンAI — CLAUDE.md

このファイルはClaude Codeが毎回自動で読む「プロジェクト説明書」です。
すべての作業指示より優先されます。

---

## プロジェクト概要

熊本県産クレソンを生産するナナカファーム（古閑弘晃）が運営する、
個人客（BtoC）向けのクレソン料理アドバイザーWebアプリ。

クレソンを手に取った個人客が「今夜どう使うか」を質問できる
Neo4j Graph RAG × Z.ai GLM-4.7-Flash チャットボット。

---

## システム目標（KAOS形式）

```
Achieve: クレソンを手に取った個人客が料理法を見つけられる
  Achieve: 質問からTTFB 20秒以内に最初の回答文字が届く
    Achieve: GLM-4.7-Flashで推論モードなしの高速応答を実現する
    Achieve: Neo4j keepaliveで接続切れを防ぎリトライコストをゼロにする
  Achieve: 回答はNeo4jのデータに根拠を持つ
    Achieve: Hybrid Search（ベクトル+キーワード）で関連料理を検索する
    Achieve: 出典ドキュメントをUIに表示して根拠を明示する
  Achieve: 190品超の世界のクレソン料理知識を提供できる
    Achieve: Neo4j Aura FreeにDishノードが190件以上存在する
    Achieve: Notionデータベースと同期できる仕組みを持つ
  Avoid: クレソン料理と無関係な回答を返す
    Avoid: ガードレール外の質問にクレソン情報を混入させる
  Avoid: 本番環境でアプリが無応答（0バイト）になる
    Avoid: GLM-4.7の推論トークンが回答トークンを枯渇させる
    Avoid: Neo4j接続切れが未処理のままユーザーに届く
```

---

## 不変条件（実装上の制約）

以下は**いかなる修正でも変えてはいけない**制約です。

```
INV_1: max_tokens >= 2048
        GLM-4.7の推論モード（thinking mode）対策。
        reasoning_contentが先にトークンを消費するため、
        1024では回答トークンが枯渇し0バイトレスポンスになる。

INV_2: database = os.getenv("NEO4J_USERNAME")
        Neo4j Aura FreeではDB名=ユーザー名（acd55d1e）。
        通常のNeo4jと異なるAura Free固有の仕様。

INV_3: .envファイルは絶対にGitにpushしない
        ZAI_API_KEY, NEO4J_PASSWORD, OPENAI_API_KEY等の
        秘密情報を含む。.gitignoreに必ず記載されていること。

INV_4: gunicornは --workers 1 で起動する
        Neo4jVectorの接続はモジュールレベルで1回だけ初期化する設計。
        workers=2以上にするとRender無料プランのメモリ上限を超える。

INV_5: keepaliveスレッドはモジュールレベルで起動する
        if __name__ == "__main__": の中に書くとGunicornで動かない。
        start_keepalive()をモジュールレベルで呼ぶこと。

INV_6: GLM-4.7のcontentが空の場合のフォールバック
        response.content or getattr(response, 'reasoning_content', None)
        このパターンで空レスポンスを回避すること。

INV_7: Tool SelectorはTYPE_0・TYPE_1・TYPE_3の
        いずれか1つに質問を分類する（排他性）
        同時に複数のTypeに分類することはできない。
        Alloy検証（ExclusiveClassification）で証明済み。
        → tool_selector.als参照

INV_8: TYPE_0（挨拶・定型応答）にはRAGを適用しない
        ResponseTemplateノードからの固定文返却のみ許可する。
        Alloy検証（NoRAGForGreeting）で証明済み。
        GLM-4.7-Flashの呼び出しコストをゼロにすること。

INV_9: キーワードが検出されない質問はTYPE_3（対話）に落とす
        Tool Selectorが分類不能な質問をエラーにしてはいけない。
        Alloy検証（EmptyKeywordFallsToRAG）で証明済み。
        フォールバック経路としてTYPE_3パイプラインを維持する。

INV_10: Tool Selectorのキーワード辞書はNeo4jのQueryPatternノードで管理する
        Pythonコードにキーワードをハードコードしない。
        キーワードの追加・変更はNeo4jへのノード追加のみで行う。
        コードのデプロイなしにキーワード更新が可能であること。

INV_11: TYPE_3はTYPE_0・TYPE_1に分類されない全ての質問を受け持つ
        TYPE_0・TYPE_1に確実に当てはまらないものは全てTYPE_3へ。
        「分類できない」をエラーにしない。エキスパートシステム化を避ける。
        Alloy検証（NoInfiniteDialog）で証明済み。
        → phase4_dialog.als参照

INV_12: TYPE_3の対話は基本2往復・最大3往復で完了する
        3往復目終了時点で条件が不足していても
        RAG検索＋マルチペルソナレポートを強制出力する。
        ユーザーを待たせない設計を優先する。
        Alloy検証（ForceCompleteWorks）で証明済み。

INV_13: マルチペルソナはMC→Chef→Nutritionist→MCの順で
        チャット画面内にストリーミング出力する。
        各ペルソナの発言は300字以内を目安にする。
        Alloy検証（MCLeadsAndCloses・ExpertsInMiddle）で証明済み。

INV_14: TYPE_2は廃止しTYPE_3に統合する
        従来のRAG Hybrid SearchはTYPE_3の
        条件収集完了後の内部処理として継続使用する。
```

---

## 技術スタック

```
【Webフレームワーク】
  Flask 3.1.0 + Gunicorn 23.0.0
  セッション: Flask Session（user/assistantのみ、最新10件）
  Systemプロンプト: Sessionには含めない（毎回API呼び出し時に注入）

【LLM】
  Z.ai GLM-4.7-Flash（デフォルト）
  base_url: https://api.z.ai/api/paas/v4/
  temperature: 0.7（回答生成）/ 0.0（Cypher生成）
  max_tokens: 2048（INV_1参照）
  timeout: 120秒

【ベクトル検索・RAG】
  LangChain Neo4j（langchain-neo4j==0.9.0）
  Neo4jVector Hybrid Search
  index_name: watercress_index
  keyword_index_name: watercress_keyword_index
  retriever: k=3

【Embedding】
  OpenAI text-embedding-3-small
  ※ Z.aiではなくOpenAIのEmbeddingを使用（コスト最小）

【データベース】
  Neo4j Aura Free
  URI: neo4j+s://acd55d1e.databases.neo4j.io
  USERNAME: acd55d1e（DB名と同じ: INV_2参照）

【デプロイ】
  Render 有料プラン（スリープなし）
  自動デプロイ: GitHub mainブランチへのpushで起動
  起動コマンド: gunicorn app:app --timeout 120 --workers 1
```

---

## ファイル構成

```
watercress_cheff_ai/
├── app.py                    # Flaskメインアプリ（本番稼働中）
├── templates/
│   └── index.html            # BtoC向けチャットUI
├── requirements.txt          # 依存パッケージ
├── render.yaml               # Renderデプロイ設定
├── .env                      # 環境変数（Gitに含めない: INV_3）
└── CLAUDE.md                 # このファイル

langchain_study/              # 学習・実験用スクリプト（本番とは別）
├── langchain_neo4j_setup.py  # クレソンデータ投入
├── langchain_neo4j_search.py # ベクトル・ハイブリッド検索
├── langchain_neo4j_rag.py    # RAGチェーン
├── langchain_text2cypher.py  # Text2Cypher（GraphCypherQAChain）
└── compare_text2cypher_vs_rag.py
```

---

## 非機能要求

```
【性能】
  TTFB（最初のチャンク）: < 20秒
  LLM完了: < 30秒
  ストリーミング応答: /chat_stream エンドポイントを使用
  フォールバック: /chat_stream 失敗時は /chat にフォールバック

【可用性】
  keepaliveスレッド: 270秒（4分30秒）ごとに接続確認
  Neo4j接続切れ時: initialize_rag_system()で自動再接続
  最大リトライ: LLM_MAX_RETRIES=3（指数バックオフ）

【セキュリティ】
  本番環境: SESSION_COOKIE_SECURE=True
  SESSION_COOKIE_HTTPONLY=True
  SESSION_COOKIE_SAMESITE=Lax
  環境変数: Renderのダッシュボードで管理（コードに書かない）

【コスト管理】
  LLMモデル: GLM-4.7-Flash（推論モードなし・高速・安価）
  Embedding: text-embedding-3-small（$0.02/100万トークン）
  Neo4j: Aura Free（無料枠内）
  Render: 有料プラン（月$7）
```

---

## ペルソナ・ユースケース

```
ターゲット: クレソンを手に取った個人客（BtoC）
主なシーン:
  1. 購入前: スーパーでクレソンを見て「どう使うか」を調べる
  2. 購入直後: 「今夜の献立にどう合わせるか」を聞く
  3. 使い切り: 「すき焼きで余ったクレソンをどうするか」を聞く

ガードレール:
  クレソン料理に関係ない質問 →「クレソンの使い方についてお気軽にどうぞ😊」
```

---

## 開発フェーズ進捗

```
✅ Phase 1:  Flask + Z.ai ローカル動作 → Renderデプロイ
✅ Phase 3a: Neo4j RAG + Hybrid Search → BtoC版本番公開
✅ Phase 3b: Tool Selector（3ツール自動選択）← 本番稼働中
🎯 Phase 4:  マルチペルソナ × 対話型絞り込み ← Step4 Alloy検証完了
⏳ Phase 5:  半自動営業ツール化
```

---

## スプリント計画（Sprint 3）

現在のスプリント: **2026-05-03〜**

| Issue | タイトル | 優先度 | ラベル |
|-------|---------|--------|--------|
| [#1](https://github.com/hiroAkikoDy/hiroAkikoDy-watercress_cheff_ai/issues/1) | 190品フルデータをNeo4jに投入してRAG回答精度を向上させる | 高 | `enhancement` `neo4j` |
| [#2](https://github.com/hiroAkikoDy/hiroAkikoDy-watercress_cheff_ai/issues/2) | nanaka-farm.comにクレソンAIチャットへのリンクを設置する | 中 | `enhancement` `website` |
| [#3](https://github.com/hiroAkikoDy/hiroAkikoDy-watercress_cheff_ai/issues/3) | Vol.4ブログ執筆「Claude Code×デプロイ×GLM-4.7エラー5時間の記録」 | 低 | `documentation` `blog` |

### マイルストーン
- **#1 完了条件**: Neo4j Chunkノード190件以上 + ハイブリッド検索で多様な回答
- **#2 完了条件**: nanaka-farm.comからチャットアプリへ遷移可能
- **#3 完了条件**: Zenn公開URLの取得 + 4000字以上

---

## コーディング規約

```
1. 日本語コメントを使う
2. 環境変数はos.getenv()で取得する（ハードコード禁止）
3. エラーメッセージは日本語でユーザーに表示する
4. 作業完了後はWORK_REPORT_YYYYMMDD_HHMM.mdを作成する
5. コミットメッセージはfix:/feat:/docs:のプレフィックスを使う
6. INV_1〜INV_14は変更前に必ずこのファイルを確認する
```

---

## よくあるエラーと対処法

```
【GLM-4.7のcontentが空】
  原因: 推論モードのトークン枯渇（INV_1）
  対処: max_tokens=2048以上に設定

【Neo4jVector driver_config エラー】
  原因: langchain-neo4j==0.9.0はdriver_configを受け付けない
  対処: driver_configパラメータを削除する

【keepaliveが動かない】
  原因: if __name__ == "__main__": 内に書いた（INV_5）
  対処: モジュールレベルで start_keepalive() を呼ぶ

【DatabaseNotFound】
  原因: database パラメータの指定なし（INV_2）
  対処: database=os.getenv("NEO4J_USERNAME") を追加

【UnicodeEncodeError (cp932)】
  原因: Windows環境での日本語出力
  対処: sys.stdout.reconfigure(encoding='utf-8') を追加
```

---

*最終更新: 2026-05-06*
*担当: 古閑弘晃（ナナカファーム）*
