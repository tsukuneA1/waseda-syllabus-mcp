# 設計ドキュメント: Backend Architecture (uv workspace + FastAPI)

## 概要

早稲田大学シラバス MCP サーバーのバックエンドアーキテクチャ。
Python の uv workspace を使ってモノレポ構成を管理し、FastAPI で MCP プロトコルを実装する。

## 目標

- **主要な目標**
  - uv workspace によるモノレポ管理で依存関係を統一する
  - 責務ごとにパッケージを分離し、独立したテスト・デプロイを可能にする
  - FastAPI + MCP プロトコルで LLM から利用可能な API を提供する

- **非目標**
  - フロントエンド・データベーススキーマの設計（別設計ドキュメントで扱う）
  - 本番インフラの構成（別途 ops ドキュメントで扱う）

## 背景

早稲田大学のシラバス情報は Web 上に分散しており、LLM から直接参照するには不便。
MCP (Model Context Protocol) サーバーを構築することで、Claude などの LLM がシラバス情報を検索・参照できるようにする。

Python のパッケージ管理には `uv` を採用。高速な依存解決と workspace 機能により、モノレポでの複数パッケージ管理が容易になる。

## 設計

### ディレクトリ構造

リポジトリルートの下に `apps/backend/` を置き、その中で uv workspace を管理する。

```
waseda-syllabus-mcp/          # リポジトリルート
├── apps/
│   └── backend/              # uv workspace root
│       ├── pyproject.toml    # workspace 設定
│       └── packages/
│           ├── api/          # FastAPI アプリ
│           ├── mcp-server/   # MCP プロトコル実装
│           └── libs/         # 共通ライブラリ (型定義・クローラー等)
└── docs/
```

### アーキテクチャ

データフロー:

```
LLM (Claude等)
    ↓ MCP protocol
mcp-server  ←→  api (FastAPI)
                    ↓
                libs (型定義・クローラー)
                    ↓
                crawler → 早稲田シラバスサイト
                    ↓
                PostgreSQL
```

### パッケージ構成と責務

#### `packages/libs`

共通の型定義・ユーティリティ・クローラーをまとめたライブラリパッケージ。
独立したパッケージを切るほどでもない処理はここに集約する。

```
libs/
├── pyproject.toml
└── src/
    └── waseda_libs/
        ├── models.py       # Pydantic モデル (Course, Instructor, Schedule 等)
        ├── exceptions.py   # 共通例外クラス
        ├── crawler/
        │   ├── client.py   # HTTP クライアント (httpx)
        │   ├── parser.py   # HTML パーサー (BeautifulSoup)
        │   └── scraper.py  # スクレイピングロジック
        └── db/
            └── storage.py  # DB への保存
```

**依存関係**: 外部ライブラリのみ（pydantic, httpx, beautifulsoup4, sqlalchemy 等）

#### `packages/api`

FastAPI アプリケーション。シラバス検索・参照の HTTP API を提供する。

```
api/
├── pyproject.toml
└── src/
    └── waseda_api/
        ├── main.py         # FastAPI アプリ起動
        ├── routers/
        │   ├── courses.py  # /courses エンドポイント
        │   └── search.py   # /search エンドポイント
        ├── deps.py         # 依存性注入 (DB セッション等)
        └── schemas.py      # レスポンス用スキーマ
```

**依存関係**: `libs`, fastapi, uvicorn, sqlalchemy, asyncpg

#### `packages/mcp-server`

MCP プロトコルの実装。`api` パッケージの機能を MCP ツールとして公開する。

```
mcp-server/
├── pyproject.toml
└── src/
    └── waseda_mcp/
        ├── server.py       # MCP サーバー起動
        ├── tools/
        │   ├── search.py   # search_courses ツール
        │   └── get.py      # get_course_detail ツール
        └── resources/      # MCP リソース定義
```

**依存関係**: `libs`, `api`, mcp (Anthropic MCP SDK)

### 依存関係グラフ

```
mcp-server → api → libs
```

循環依存なし。`libs` が唯一の共通基盤。

### pyproject.toml 構成例

**workspace ルート** (`apps/backend/pyproject.toml`):

```toml
[tool.uv.workspace]
members = [
    "packages/api",
    "packages/mcp-server",
    "packages/libs",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "mypy>=1.10",
]
```

**各パッケージ** (例: `packages/api/pyproject.toml`):

```toml
[project]
name = "waseda-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "waseda-libs",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
]

[tool.uv.sources]
waseda-libs = { workspace = true }
```

## 開発フロー

### セットアップ

```bash
cd apps/backend

# 依存関係を全パッケージ分まとめてインストール
uv sync

# 特定パッケージの依存のみインストール
uv sync --package waseda-api
```

### 開発サーバー起動

```bash
# API サーバー
uv run --package waseda-api uvicorn waseda_api.main:app --reload

# MCP サーバー
uv run --package waseda-mcp python -m waseda_mcp.server

# クローラー実行
uv run --package waseda-libs python -m waseda_libs.crawler.scraper
```

### テスト

```bash
# 全パッケージのテスト
uv run pytest

# 特定パッケージのテスト
uv run pytest packages/api/tests/

# カバレッジ付き
uv run pytest --cov=packages/
```

### Lint / 型チェック

```bash
uv run ruff check .
uv run ruff format .
uv run mypy packages/
```

### 依存関係の追加

```bash
# 特定パッケージに依存を追加
uv add --package waseda-api httpx

# 開発依存を追加 (workspace 全体)
uv add --dev pytest-mock
```

## 検討した代替案

| 案 | 採用しなかった理由 |
|---|---|
| Poetry workspace | uv より低速、workspace サポートが実験的 |
| pip + requirements.txt | パッケージ間依存の管理が複雑になる |
| crawler を独立パッケージにする | 独立デプロイ・独立テストの必要性が低く over-engineering |
| Django | シラバス検索 API には over-engineering、FastAPI の非同期処理が適切 |

## 未解決の質問

- [ ] クローラーの実行頻度・スケジューリング方法 (cron vs Celery vs GitHub Actions)
- [ ] MCP サーバーのデプロイ形態 (stdio vs HTTP transport)
- [ ] 早稲田シラバスサイトのレート制限・robots.txt の確認

## セキュリティ/プライバシーの考慮事項

- シラバス情報は公開情報のため、個人情報は含まない
- クローラーは適切な User-Agent を設定し、過剰なリクエストを避ける
- API キーは環境変数で管理 (`python-dotenv`)

## テスト戦略

- **Unit テスト**: 各パッケージの純粋関数・ビジネスロジック
- **Integration テスト**: API エンドポイント + 実 DB (PostgreSQL)
- **E2E テスト**: MCP ツール呼び出し → DB 参照までの一連フロー
- クローラーのテストにはシラバスサイトのモック HTML を使用

## 参考資料

- [uv workspace 公式ドキュメント](https://docs.astral.sh/uv/concepts/workspaces/)
- [FastAPI 公式ドキュメント](https://fastapi.tiangolo.com/)
- [MCP Python SDK](https://github.com/anthropics/mcp)
- [早稲田大学シラバス検索](https://www.wsl.waseda.jp/syllabus/JAA101.php)
