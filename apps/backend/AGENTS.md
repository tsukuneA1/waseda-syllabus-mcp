# Backend CLAUDE.md

Python uv workspace。`mcp-server → api → libs` の依存チェーン。

## パッケージ構成

| パッケージ | モジュール名 | 役割 |
|-----------|-------------|------|
| `packages/libs` | `waseda_libs` | クローラー・Pydantic モデル・DB 保存 |
| `packages/api` | `waseda_api` | FastAPI (シラバス検索 HTTP API) |
| `packages/mcp-server` | `waseda_mcp` | MCP stdio サーバー (`search_syllabus` ツール) |

## コマンド

```bash
# 依存関係インストール
uv sync

# API サーバー起動
uv run --package waseda-api uvicorn waseda_api.main:app --reload

# MCP サーバー起動
uv run --package waseda-mcp python -m waseda_mcp.server

# クローラー実行
uv run --package waseda-libs python -m waseda_libs.crawler.scraper

# テスト
uv run pytest
uv run pytest packages/api/tests/  # 特定パッケージ

# Lint / Format / 型チェック
uv run ruff check .
uv run ruff format .
uv run mypy packages/

# 依存追加
uv add --package waseda-api <pkg>
uv add --dev <pkg>  # 開発依存（workspace 全体）

# DB マイグレーション
alembic upgrade head
alembic downgrade base
```

## 環境変数

| 変数 | デフォルト | 用途 |
|------|----------|------|
| `WASEDA_API_BASE_URL` | `http://localhost:8000` | MCP サーバーの API 接続先 |
| DB 接続文字列 | — | ハードコード禁止、環境変数で管理 |

## MCP クライアント設定例

```json
{
  "mcpServers": {
    "waseda-syllabus": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/apps/backend", "--package", "waseda-mcp", "python", "-m", "waseda_mcp.server"],
      "env": { "WASEDA_API_BASE_URL": "http://localhost:8000" }
    }
  }
}
```

## 注意事項

- クローラーは 1req/s のレート制限を守る（`waseda_libs.crawler`）
- MCP サーバーは DB に直接アクセスしない。必ず `api` 経由
- 設計詳細: `docs/design/backend-architecture.md`, `mcp-server-design.md`, `database-schema.md`, `crawler-design.md`
