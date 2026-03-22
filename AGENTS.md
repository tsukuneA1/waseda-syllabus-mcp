# AGENTS.md

`CLAUDE.md` と同内容。詳細はそちらを参照。

---

早稲田大学シラバス MCP サーバー。シラバスをクローリングして DB に保存し、MCP 経由で LLM から検索できるようにする。

## リポジトリ構造

```
waseda-syllabus-mcp/
├── .bare/              # Bare リポジトリ（直接変更しない）
├── main/               # main ブランチ worktree
│   ├── apps/
│   │   ├── backend/    # Python uv workspace → apps/backend/AGENTS.md 参照
│   │   └── frontend/   # Next.js (pnpm)      → apps/frontend/AGENTS.md 参照
│   └── docs/design/    # 設計ドキュメント
└── worktrees/          # issue 作業用（main/ と分離）
```

## Git Worktree ワークフロー

**新規 worktree 作成:**
```bash
BARE=$(git rev-parse --git-common-dir)
ROOT=$(dirname "$BARE")
git --git-dir="$BARE" worktree add "$ROOT/worktrees/WMCP-<N>-<prefix>-<slug>" -b WMCP-<N>-<prefix>-<slug>
```

**ブランチ命名:** `WMCP-<issue番号>-<prefix>-<slug>`
prefix: `feature` / `fix` / `docs` / `refactor`

## PR・コミット規則

- コミットメッセージに `Closes #N` を含める
- PR は `.github/pull_request_template.md` に従う
