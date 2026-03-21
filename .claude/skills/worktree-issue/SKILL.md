---
name: worktree-issue
description: GitHubのissue番号を受け取り、worktree作成→実装→commit/push→PR作成まで自律的に完結させるワークフロー。「issue 3をやって」「issue #5を実装して」「worktree-issue 7」のような場面で使う。git worktreeベースの開発フローを全自動化する。
---

# GitHub Issue Worktree Workflow

issue番号を受け取り、worktree作成から実装・PR作成まで**エージェントが自律的に完結**させる。
判断に迷う場合のみユーザーに確認する。

---

## Step 1: Issue情報の取得

```bash
gh issue view <number> --json number,title,labels,body
```

タイトルとラベルからブランチのprefixを判定する:

| 条件 | prefix |
|------|--------|
| ラベル `bug` / タイトルに "fix" "バグ" "修正" | `fix` |
| ラベル `documentation` / タイトルに "doc" "ドキュメント" | `docs` |
| それ以外 | `feature` |

## Step 2: ブランチ名の生成

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

## Step 3: Bareリポジトリとプロジェクトルートの特定

```bash
git rev-parse --git-common-dir
```

このコマンドが返すパス（例: `/home/tksch/waseda-syllabus-mcp/.bare`）がbareリポジトリ。
その親ディレクトリがプロジェクトルート。

**注意**: bareリポジトリ外で実行するとエラーになる場合がある。
その場合は `.bare` ディレクトリを探してbareパスとして使う。

## Step 4: Worktreeの作成

```bash
git --git-dir=<bare-path> worktree add <project-root>/<branch-name> -b <branch-name>
```

## Step 5: 実装

issueのbodyに書かれたタスクをworktreeディレクトリ内で実装する。

- issueのbodyを読み、必要なファイルを作成・編集する
- 既存のコード・ドキュメントを参照して文脈に合わせる
- **判断に迷う場合のみ**ユーザーに確認する。それ以外は自律的に進める
- 実装が完了したら次のステップへ進む（ユーザーの確認は不要）

## Step 6: Add & Commit

```bash
git -C <worktree-path> status
git -C <worktree-path> add -A
git -C <worktree-path> commit -m "$(cat <<'EOF'
<変更内容を表すコミットメッセージ>

Closes #<issue-number>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

コミットメッセージはissueのタイトルと変更内容から適切に生成する。

## Step 7: Push

```bash
git -C <worktree-path> push -u origin <branch-name>
```

## Step 8: PR作成

```bash
gh pr create \
  --title "<PRタイトル>" \
  --head <branch-name> \
  --base main \
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
完了したらPRのURLをユーザーに伝える。

---

## 注意事項

- このプロジェクトは `git clone --bare` ベースのworktree構成。必ず `git --git-dir=<bare-path> worktree add` を使う
- bareリポジトリのパスは動的に取得する（ハードコードしない）。取得できない場合は `.bare` ディレクトリを探す
- `gh pr create` は `--head` と `--base` を明示する（省略するとエラーになる場合がある）
- コミットメッセージに `Closes #N` を含めてissueの自動クローズを有効にする
- **ユーザーへの確認は最小限に**。実装方針が複数あって判断できない場合のみ質問する