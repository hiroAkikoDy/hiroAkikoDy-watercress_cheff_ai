## watercress_cheff_ai

Neo4j Aura（既存DB）＋ Z.ai（GLM-4.7）を使った、クレソン料理RAGチャット（Flask）です。

## 必要な環境変数

- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `ZAI_API_KEY`
- `SECRET_KEY`

ローカル実行では `.env` を利用できます。本番（Render）では Render の Environment Variables に設定してください（`.env` はコミットしません）。

## ローカル起動

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

ブラウザで `http://localhost:5000/` を開いてください。

## Neo4j Aura の前提（インデックス確認）

このアプリは Neo4j 上の既存インデックスを利用します。

- ベクトル: `watercress_index`
- キーワード: `watercress_keyword_index`

Neo4j Browser / Aura Query で次を実行して、存在するか確認してください。

```cypher
SHOW INDEXES;
```

存在しない場合は、別途インデックス/データ投入が必要です（例: 旧プロジェクトの `langchain_neo4j_setup.py` 相当を実行）。

## Render デプロイ

### 推奨（Blueprint）

このリポジトリには `render.yaml` を含めています。Renderで「New +」→「Blueprint」から読み込むと、サービス設定が自動作成されます。

**注意（重要）**: Blueprint から作成した Web Service でも、後から Render ダッシュボードで **Start Command** を手動変更すると、リポジトリの `render.yaml` と齟齬が出ます。  
以下のエラーは、その典型例です。

- `ModuleNotFoundError: No module named 'app_v1'`  
  → Render が `gunicorn app_v1:app` を起動しようとしているが、本リポジトリのエントリポイントは **`app.py`（`app:app`）** です。

### 手動設定する場合

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 120`
- **Environment Variables**:
  - `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
  - `ZAI_API_KEY`
  - `SECRET_KEY`（長いランダム文字列推奨）
  - （任意）`PYTHON_VERSION`（例: `3.11.9`）

### Render ダッシュボードでの修正手順（`app_v1` エラー対策）

1. Render の対象 Web Service を開く  
2. **Settings** → **Start Command** を確認  
3. 次のいずれかに揃える  
   - **推奨**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 120`  
4. **Environment** に `PYTHON_VERSION=3.11.9` が入っているか確認（未設定だと、ログ上は Python 3.14 系で動くことがあります）  
5. **Manual Deploy**（または **Save Changes** 後の再デプロイ）を実行

参考: [Render: Troubleshooting deploys](https://render.com/docs/troubleshooting-deploys)

