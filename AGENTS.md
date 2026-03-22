# AGENTS.md

このファイルは Codex (および他の AI エージェント) 向けのプロジェクトガイド。
内容は `CLAUDE.md` と同一。詳細は `CLAUDE.md` を参照すること。

<!-- 以下は CLAUDE.md と同内容 -->

# CLAUDE.md

早稲田大学シラバス MCP サーバープロジェクトの開発ガイド。
Claude Code (および Codex) が自律的に作業するために必要なコンテキストをまとめる。

---

## プロジェクト概要

早稲田大学のシラバス情報を MCP (Model Context Protocol) 経由で LLM から参照できるようにするサーバー。
クローラーがシラバスサイトからデータを収集し、FastAPI で検索 API を提供し、MCP サーバー経由で Claude 等の LLM から利用できるようにする。

**主要ユーザー**: 早稲田大学の学生（履修計画のサポート）

---

## リポジトリ構造

```
waseda-syllabus-mcp/
├── .bare/                      # Bare リポジトリ（直接変更しない）
├── main/                       # main ブランチ worktree
│   ├── CLAUDE.md               # Claude Code 向けガイド
│   ├── AGENTS.md               # このファイル（Codex 向けガイド）
│   ├── README.md
│   ├── apps/
│   │   ├── backend/            # Python uv workspace
│   │   │   ├── pyproject.toml  # workspace 設定・開発依存
│   │   │   ├── uv.lock
│   │   │   └── packages/
│   │   │       ├── api/        # FastAPI アプリ (waseda-api)
│   │   │       ├── mcp-server/ # MCP プロトコル実装 (waseda-mcp)
│   │   │       └── libs/       # 共通ライブラリ・クローラー (waseda-libs)
│   │   └── frontend/           # Next.js アプリ (pnpm)
│   │       ├── package.json
│   │       ├── pnpm-lock.yaml
│   │       └── src/
│   │           ├── app/        # App Router
│   │           ├── components/ # UI コンポーネント
│   │           ├── lib/        # API クライアント
│   │           └── types/      # 型定義
│   ├── docs/
│   │   └── design/             # 設計ドキュメント
│   └── scripts/
│       └── wt.sh               # worktree 移動コマンド
└── worktrees/                  # issue 作業用 worktree（main と分離）
    └── WMCP-<N>-<prefix>-<slug>/
```

---

## アーキテクチャ

### データフロー

```
早稲田シラバスサイト (wsl.waseda.jp)
    ↓ Playwright + httpx (クローラー)
libs (waseda-libs) → PostgreSQL
    ↓
api (waseda-api / FastAPI)  ←→  frontend (Next.js)
    ↓ HTTP (httpx)
mcp-server (waseda-mcp)
    ↓ MCP protocol (stdio)
LLM クライアント (Claude Desktop, Cursor 等)
```

### パッケージ依存関係

```
mcp-server → api → libs
```

循環依存なし。`libs` が唯一の共通基盤。

### 技術スタック

| レイヤー | 技術 |
|----------|------|
| パッケージ管理 (Python) | uv workspace |
| Web フレームワーク | FastAPI + uvicorn |
| MCP サーバー | Python MCP SDK (Anthropic) |
| クローラー | Playwright (pKey 収集) + httpx (詳細取得) |
| HTML パーサー | BeautifulSoup4 |
| データモデル | Pydantic v2 |
| データベース | PostgreSQL (pg_trgm + tsvector 全文検索) |
| マイグレーション | Alembic |
| ORM | SQLAlchemy 2.0 (asyncio) |
| フロントエンド | Next.js (App Router) + pnpm |
| Lint / Format | ruff |
| 型チェック | mypy |
| テスト | pytest + pytest-asyncio |

---

## 開発コマンド

### バックエンド (uv workspace)

```bash
cd apps/backend

# 全依存関係インストール
uv sync

# API サーバー起動
uv run --package waseda-api uvicorn waseda_api.main:app --reload

# MCP サーバー起動
uv run --package waseda-mcp python -m waseda_mcp.server

# クローラー実行
uv run --package waseda-libs python -m waseda_libs.crawler.scraper

# テスト（全パッケージ）
uv run pytest

# 特定パッケージのテスト
uv run pytest packages/api/tests/

# Lint / フォーマット
uv run ruff check .
uv run ruff format .

# 型チェック
uv run mypy packages/

# 依存関係の追加
uv add --package waseda-api <package>   # 特定パッケージ
uv add --dev <package>                  # 開発依存（workspace 全体）
```

### フロントエンド (pnpm)

```bash
cd apps/frontend

# 依存関係インストール
pnpm install

# 開発サーバー起動（要: .env.local に API_URL=http://localhost:8000）
pnpm dev
```

### マイグレーション (Alembic)

```bash
cd apps/backend

# マイグレーション実行
alembic upgrade head

# ダウングレード
alembic downgrade base
```

---

## Git Worktree ワークフロー

このリポジトリは `git clone --bare` ベースの worktree 構成。

### ディレクトリ規則

- `main/` — main ブランチ専用。直接作業しない
- `worktrees/WMCP-<N>-<prefix>-<slug>/` — issue 作業用

### ブランチ命名規則

```
WMCP-<issue-number>-<prefix>-<title-slug>
```

prefix:
- `fix` — バグ修正
- `docs` — ドキュメント
- `refactor` — リファクタリング
- `feature` — それ以外

---

## 設計ドキュメント

詳細は `docs/design/` を参照:

| ファイル | 内容 |
|----------|------|
| `backend-architecture.md` | uv workspace 構成・パッケージ責務・依存関係グラフ |
| `mcp-server-design.md` | MCP ツール定義・エラーハンドリング・クライアント設定方法 |
| `database-schema.md` | PostgreSQL スキーマ・インデックス戦略・全文検索実装 |
| `crawler-design.md` | Playwright によるpKey収集・httpx による詳細取得・レート制限 |
| `frontend-architecture.md` | Next.js App Router 構成・FastAPI との連携 |

---

## 主要データモデル

### `CourseSummary` (MCP ツールの出力)

```python
class CourseSummary(BaseModel):
    pkey: str              # シラバス識別子 (28文字固定)
    title: str             # 科目名
    title_en: str | None   # 英語科目名
    instructors: list[str] # 担当教員名
    semester: str          # 'spring' | 'fall' | 'full' | 'unknown'
    credits: int | None    # 単位数
    department: str | None # 学部・研究科名
    year: int              # 対象年度
```

### `syllabuses` テーブル (PostgreSQL)

主キー: `pkey` (CHAR(28))
全文検索: `search_vector` (TSVECTOR, トリガーで自動更新) + `pg_trgm` インデックス（日本語）

---

## 環境変数

| 変数 | 用途 | デフォルト |
|------|------|----------|
| `WASEDA_API_BASE_URL` | MCP サーバーから API への接続先 | `http://localhost:8000` |
| `API_URL` | フロントエンドから API への接続先 | — (`apps/frontend/.env.local` に記載) |
| DB 接続情報 | SQLAlchemy 接続文字列 | — (環境変数で管理、ハードコード禁止) |

---

## MCP クライアント設定 (Claude Desktop 等)

```json
{
  "mcpServers": {
    "waseda-syllabus": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/waseda-syllabus-mcp/apps/backend",
        "--package", "waseda-mcp",
        "python", "-m", "waseda_mcp.server"
      ],
      "env": {
        "WASEDA_API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

API サーバーは別途起動が必要:
```bash
cd apps/backend
uv run --package waseda-api uvicorn waseda_api.main:app --reload
```

---

## PR・コミット規則

- コミットメッセージに `Closes #N` を含めて issue を自動クローズする
- PR は `.github/pull_request_template.md` のテンプレートに従う

---

## 注意事項

- `libs` パッケージ内にクローラーを含む。クローラーは 1req/s のレート制限を守る
- MCP サーバーは stdio トランスポートのみ（初期実装）。DB への直接アクセスは行わず、必ず `api` 経由
- DB 接続情報・API キーは環境変数で管理し、ソースコードにハードコードしない
- シラバス情報は公開情報のため個人情報は含まないが、クローラーは適切な User-Agent を設定すること
