# CLAUDE.md

早稲田大学シラバス MCP サーバー。シラバスをクローリングして DB に保存し、MCP 経由で LLM から検索できるようにする。

## リポジトリ構造

```
waseda-syllabus-mcp/
├── .bare/              # Bare リポジトリ（直接変更しない）
├── main/               # main ブランチ worktree
│   ├── apps/
│   │   ├── backend/    # Python uv workspace → apps/backend/CLAUDE.md 参照
│   │   └── frontend/   # Next.js (pnpm)      → apps/frontend/CLAUDE.md 参照
│   └── docs/design/    # 設計ドキュメント
└── worktrees/          # issue 作業用（main/ と分離）
```

## Git Worktree ワークフロー

このリポジトリは `git clone --bare` ベースの worktree 構成。

**新規 worktree 作成:**
```bash
BARE=$(git rev-parse --git-common-dir)
ROOT=$(dirname "$BARE")
git --git-dir="$BARE" worktree add "$ROOT/worktrees/WMCP-<N>-<prefix>-<slug>" -b WMCP-<N>-<prefix>-<slug>
```

**ブランチ命名:** `WMCP-<issue番号>-<prefix>-<slug>`
prefix: `feature` / `fix` / `docs` / `refactor`

**worktree 間移動 (`wt` コマンド):**
```bash
source scripts/wt.sh  # ~/.bashrc に追記して使う
wt main   # main worktree へ
wt 14     # WMCP-14-... worktree へ
```

## PR・コミット規則

- コミットメッセージに `Closes #N` を含める
- PR は `.github/pull_request_template.md` に従う
- `gh pr create --head <branch> --base main`
