---
name: merge-cleanup
description: PRをsquash mergeした後のローカルクリーンアップ。worktreeの削除・ブランチ削除・mainのgit pullをまとめて実行する。「PRマージしたのでクリーンアップして」「issue 3のブランチ消してmainをpullして」「squash mergeしたのでブランチ削除して」「WMCP-5のworktreeを片付けて」のような場面で使う。
---

# Merge Cleanup

squash merge後のローカル環境を整理する。worktree削除→ブランチ削除→main pull の3ステップ。

---

## Step 1: 対象ブランチの特定

ユーザーは `WMCP-<number>` の形式で指定する（例: `WMCP-1`）。

bareリポジトリのパスを取得し、その番号で始まるブランチを検索する:

```bash
git --git-dir=<bare-path> branch | grep "WMCP-<number>-"
```

例: `WMCP-1` と指定されたら `WMCP-1-docs-backend-architecture` などがヒットする。

複数マッチした場合はユーザーに確認する。1件だけマッチした場合はそのまま進む。

bareリポジトリのパスは `git rev-parse --git-common-dir` で取得する。

## Step 2: Worktreeの削除

このプロジェクトはgit worktree構成のため、ブランチに対応するworktreeディレクトリがある。
worktreeを先に外してからブランチを削除する必要がある。

```bash
git --git-dir=<bare-path> worktree remove <project-root>/worktrees/<branch-name>
```

worktreeに未コミットの変更が残っている場合は `--force` は使わず、ユーザーに確認する。

## Step 3: ローカルブランチの削除

squash mergeされたブランチはmainにマージ済みでないと判定されるため `-D`（強制削除）を使う。

```bash
git --git-dir=<bare-path> branch -D <branch-name>
```

## Step 4: mainで git pull

```bash
git -C <project-root>/main pull origin main
```

完了したら削除したブランチ名と最新のmain HEADをユーザーに伝える。

---

## 注意事項

- このプロジェクトは `git clone --bare` ベースのworktree構成。bareリポジトリのパスは動的に取得する
- worktrees/ 配下にないブランチ（mainなど）は絶対に削除しない
- worktreeに未保存の変更があれば削除前にユーザーに確認する
- squash mergeは通常の merge commit を作らないため `-d` では削除できない。`-D` を使う
