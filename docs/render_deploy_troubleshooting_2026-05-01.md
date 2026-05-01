# Render デプロイ失敗の記録と対処（2026-05-01）

## 1. 現象

デプロイログに以下が出て、プロセスが終了する。

- `Running 'gunicorn app_v1:app'`
- `ModuleNotFoundError: No module named 'app_v1'`

## 2. 原因

本リポジトリ（[hiroAkikoDy/hiroAkikoDy-watercress_cheff_ai](https://github.com/hiroAkikoDy/hiroAkikoDy-watercress_cheff_ai)）の Flask エントリポイントは **`app.py` の `app` インスタンス**です。  
そのため、Gunicorn は **`app:app`** を指定する必要があります。

Render 側の **Start Command** が、別プロジェクト名（`app_v1`）のまま残っていると、モジュールが存在せず起動に失敗します。

## 3. 対処（最短）

Render ダッシュボードで対象 Web Service の **Settings → Start Command** を次に変更する。

```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 120
```

保存後、再デプロイする。

## 4. Blueprint（`render.yaml`）とのズレに注意

このリポジトリの `render.yaml` は **`gunicorn app:app`** を前提にしています。  
Blueprint で作った後にダッシュボードで Start Command を手動変更すると、リポジトリ設定と実際の運用がずれやすいです。

## 5. 補足: Python バージョン

ログによっては Python 3.14 系で動く表示になることがあります。安定運用のため、`PYTHON_VERSION=3.11.9`（例）を環境変数として明示する運用が安全です（`render.yaml` にも同値の例を入れています）。

## 6. 参考

- [Render: Troubleshooting deploys](https://render.com/docs/troubleshooting-deploys)
