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
| タイトルに "refactor" "リファクタ" | `refactor` |
| それ以外 | `feature` |

## Step 2: ブランチ名の生成

命名規則:
```
WMCP-<issue-number>-<prefix>-<title-slug>
```

title-slugのルール:
- 英数字とハイフンのみ（記号・日本語は除去）
- スペース・アンダースコアはハイフンに変換
- 小文字に統一
- 連続するハイフンは1つに
- 最大40文字

例:
- #1 "Design Doc: Backend Architecture (uv workspace + FastAPI)" → `WMCP-1-docs-backend-architecture`
- #7 "Setup: Development Environment (Docker + PostgreSQL)" → `WMCP-7-feature-development-environment-docker`

## Step 3: Bareリポジトリとプロジェクトルートの特定

```bash
git rev-parse --git-common-dir
```

このコマンドが返すパス（例: `/home/tksch/waseda-syllabus-mcp/.bare`）がbareリポジトリ。
その親ディレクトリがプロジェクトルート。

**注意**: 取得できない場合は親ディレクトリを遡って `.bare` ディレクトリを探す。

## Step 4: Worktreeの作成

worktreeはプロジェクトルート直下の `worktrees/` ディレクトリに作成する:

```bash
mkdir -p <project-root>/worktrees
git --git-dir=<bare-path> worktree add <project-root>/worktrees/<branch-name> -b <branch-name>
```

ディレクトリ構成:
```
waseda-syllabus-mcp/
├── .bare/
├── main/           ← mainブランチ専用
└── worktrees/      ← issue作業用worktreeはここに集約
    ├── WMCP-1-docs-backend-architecture/
    ├── WMCP-2-docs-frontend-architecture/
    └── ...
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

`.github/pull_request_template.md` を読み込み、そのテンプレートに従ってPRのbodyを作成する。

テンプレートのルール（テンプレート内のコメントにも記載されている）:
- Required セクションは必ず記入する
- Optional セクションは内容がない場合はセクション全体（見出しを含む）を削除する
- セクションの順序は変更しない
- HTMLコメント (`<!-- ... -->`) は最終的なbodyからすべて除去する

```bash
# テンプレートを読み込む
cat <project-root>/main/.github/pull_request_template.md

gh pr create \
  --title "<PRタイトル>" \
  --head <branch-name> \
  --base main \
  --body "$(cat <<'EOF'
<テンプレートに従って記入したbody。HTMLコメントは除去済み>
EOF
)"
```

PRのタイトルはissueのタイトルをベースにする。
完了したらPRのURLをユーザーに伝える。

---

## 注意事項

- このプロジェクトは `git clone --bare` ベースのworktree構成。必ず `git --git-dir=<bare-path> worktree add` を使う
- worktreeは必ず `worktrees/` ディレクトリ配下に作成する（`main/` と分離するため）
- bareリポジトリのパスは動的に取得する（ハードコードしない）
- `gh pr create` は `--head` と `--base` を明示する
- コミットメッセージに `Closes #N` を含めてissueの自動クローズを有効にする
- **ユーザーへの確認は最小限に**。実装方針が複数あって判断できない場合のみ質問する
