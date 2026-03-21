---
name: worktree-issue
description: GitHubのissue番号を受け取ってworktreeを作成し、実装後にcommit/pushしてPRを作るまでの一連のワークフロー。「issue 3のworktreeを作って」「issue #5でブランチを切って」「このworktreeをcommitしてPRを作って」「issue 2の実装が終わったのでPR作りたい」のような場面で使う。git worktreeベースの開発フローを自動化する。
---

# GitHub Issue Worktree Workflow

git worktreeを使ったissueベースの開発フローを2フェーズで管理する。

---

## フェーズ1: Worktreeの作成

### Step 1: Issue情報の取得

```bash
gh issue view <number> --json number,title,labels,body
```

タイトルとラベルからブランチのprefixを判定する:

| 条件 | prefix |
|------|--------|
| ラベル `bug` / タイトルに "fix" "バグ" "修正" | `fix` |
| ラベル `documentation` / タイトルに "doc" "ドキュメント" | `docs` |
| それ以外 | `feature` |

### Step 2: ブランチ名の生成

```
<prefix>-<issue-number>-<title-slug>
```

title-slugのルール:
- 英数字とハイフンのみ（記号・日本語は除去）
- スペース・アンダースコアはハイフンに変換
- 小文字に統一
- 連続するハイフンは1つに
- 最大40文字

例:
- #1 "Design Doc: Backend Architecture (uv workspace + FastAPI)" → `feature-1-backend-architecture-uv-workspace-fastapi`
- #7 "Setup: Development Environment (Docker + PostgreSQL)" → `feature-7-development-environment-docker-postgresql`

### Step 3: Bare リポジトリとプロジェクトルートの特定

現在のworktreeからbareリポジトリのパスを取得する:

```bash
git rev-parse --git-common-dir
```

このコマンドが返すパス（例: `/home/tksch/waseda-syllabus-mcp/.bare`）がbareリポジトリ。
その親ディレクトリがプロジェクトルートになる。

### Step 4: Worktreeの作成

```bash
git --git-dir=<bare-path> worktree add <project-root>/<branch-name> -b <branch-name>
```

作成後、ユーザーに以下を伝える:
- 作成したworktreeのパス
- ブランチ名
- 「実装が終わったら同じissue番号を伝えてください」

---

## フェーズ2: Commit & PR作成

ユーザーが「issue Nの実装が終わった」「このworktreeをcommitしてPR作って」などと言ったら開始する。

### Step 1: Worktreeの特定

issue番号から対応するworktreeディレクトリを特定する。

```bash
git --git-dir=<bare-path> worktree list
```

または現在のディレクトリが対象のworktreeであれば、そこで作業する。

### Step 2: 変更内容の確認

```bash
git -C <worktree-path> status
git -C <worktree-path> diff
```

変更ファイルをユーザーに見せて、問題がないか確認する。

### Step 3: Add & Commit

```bash
git -C <worktree-path> add -A
git -C <worktree-path> commit -m "$(cat <<'EOF'
<変更内容を表すコミットメッセージ>

Closes #<issue-number>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

コミットメッセージはissueのタイトルと変更内容から適切に生成する。

### Step 4: Push

```bash
git -C <worktree-path> push -u origin <branch-name>
```

### Step 5: PR作成

```bash
gh pr create \
  --title "<PRタイトル>" \
  --body "$(cat <<'EOF'
## Summary

<変更内容の要約を箇条書きで>

## Related Issue

Closes #<issue-number>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

PRのタイトルはissueのタイトルをベースにする。

---

## 注意事項

- このプロジェクトは `git clone --bare` ベースのworktree構成。通常の `git worktree add` ではなく必ず `git --git-dir=<bare-path> worktree add` を使う
- bareリポジトリのパスは `git rev-parse --git-common-dir` で動的に取得する（ハードコードしない）
- `git add -A` の前に必ず `git status` で変更内容を確認する
- コミットメッセージに `Closes #N` を含めてissueの自動クローズを有効にする
