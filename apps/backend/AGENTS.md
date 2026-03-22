# Backend CLAUDE.md

Python uv workspace。`mcp-server → api → libs` の依存チェーン。

## パッケージ構成

| パッケージ | モジュール名 | 役割 |
|-----------|-------------|------|
| `packages/libs` | `waseda_libs` | クローラー・Pydantic モデル・DB アクセス |
| `packages/api` | `waseda_api` | FastAPI (シラバス検索 HTTP API) |
| `packages/mcp-server` | `waseda_mcp` | MCP stdio サーバー (`search_syllabus` ツール) |

## DB 管理 (sqlc)

スキーマとクエリは `sqlc/` で管理し、Python コードを自動生成する。

```
sqlc/
├── schema.sql          # テーブル定義・インデックス・トリガー（正規のスキーマ）
├── queries/
│   └── syllabuses.sql  # SQL クエリ定義
└── sqlc.yaml           # 生成設定 → packages/libs/src/db/gen/ に出力
```

**生成コード (`packages/libs/src/db/gen/`) は手動編集禁止。** `sqlc generate` で再生成する。

```bash
# クエリ・スキーマを変更したら実行
cd apps/backend/sqlc
sqlc generate
```

## コマンド

```bash
# 依存関係インストール
uv sync

# DB 起動（ルートの .env を用意してから）
cp .env.example .env  # POSTGRES_PASSWORD を設定
docker compose up -d

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
```

## 環境変数

ルートの `.env.example` をコピーして `.env` を作成する。

| 変数 | デフォルト | 用途 |
|------|----------|------|
| `POSTGRES_DB` | `waseda_syllabus` | DB 名 |
| `POSTGRES_USER` | `postgres` | DB ユーザー |
| `POSTGRES_PASSWORD` | — | **必須**、設定が必要 |
| `POSTGRES_PORT` | `5432` | ホスト側ポート |
| `WASEDA_API_BASE_URL` | `http://localhost:8000` | MCP サーバーの API 接続先 |

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
- スキーマ変更は `sqlc/schema.sql` を編集 → `sqlc generate` → コンテナ再作成
- 設計詳細: `docs/design/backend-architecture.md`, `mcp-server-design.md`, `database-schema.md`, `crawler-design.md`
