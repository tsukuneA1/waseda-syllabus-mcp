# waseda-syllabus-mcp

Waseda University Syllabus MCP Server

## Development Setup

### Docker環境 (PostgreSQL)

```bash
cd apps/backend

# .envファイルを作成
cp .env.example .env
# POSTGRES_PASSWORDを設定してください

# PostgreSQLを起動
docker compose up -d

# 起動確認（healthyになるまで待つ）
docker compose ps

# 接続確認
docker compose exec db psql -U postgres -d waseda_syllabus -c '\dt'

# 停止
docker compose down
```

### Backend (uv workspace)

```bash
cd apps/backend

# 全パッケージの依存関係をインストール
uv sync
```

### Frontend (pnpm)

```bash
cd apps/frontend

# 依存関係をインストール
pnpm install

# 開発サーバー起動
pnpm dev
```

### 環境変数

`apps/frontend/.env.local` を作成:

```
API_URL=http://localhost:8000
```

## Development Workflow

This repository uses git worktrees for managing multiple branches simultaneously.

### Directory Structure

```
waseda-syllabus-mcp/
├── .bare/                          # Bare repository (don't modify directly)
├── main/                           # main branch worktree
├── feature-[issue#]-[name]/        # feature branch worktrees
└── fix-[issue#]-[name]/            # bugfix branch worktrees
```

### Working with Worktrees

See `scripts/worktree-helper.sh` for common operations.

### Worktree間の素早い移動 (`wt`)

`scripts/wt.sh` を source すると `wt` コマンドが使えるようになる。

```bash
# ~/.bashrc または ~/.zshrc に追記
source /home/tksch/waseda-syllabus-mcp/main/scripts/wt.sh
```

使い方:

```bash
wt main      # main worktreeへ移動
wt 13        # WMCP-13-... のworktreeへ移動
wt WMCP-13   # 同上
```
