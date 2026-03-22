#!/bin/bash
# wt: worktree間のディレクトリ遷移コマンド
#
# 使い方:
#   wt main          → main worktreeへ移動
#   wt <番号>        → WMCP-<番号>-... のworktreeへ移動
#   wt WMCP-<番号>   → WMCP-<番号>-... のworktreeへ移動
#
# セットアップ:
#   以下を ~/.bashrc または ~/.zshrc に追記する:
#   source /path/to/scripts/wt.sh
#
# このファイルはシェル関数として source して使う。
# スクリプトとして直接実行しても cd は現在のシェルに反映されない。

_wt_find_project_root() {
  local dir
  dir=$(git rev-parse --git-common-dir 2>/dev/null)
  if [[ -z "$dir" ]]; then
    echo "Error: gitリポジトリが見つかりません" >&2
    return 1
  fi
  # .bare の親ディレクトリがプロジェクトルート
  dirname "$dir"
}

wt() {
  local arg="${1:?使い方: wt <main|番号|WMCP-番号>}"
  local project_root
  project_root=$(_wt_find_project_root) || return 1

  # main の場合
  if [[ "$arg" == "main" ]]; then
    cd "$project_root/main" || return 1
    return 0
  fi

  # 番号または WMCP-番号 の場合
  local issue_num
  if [[ "$arg" =~ ^WMCP-([0-9]+)$ ]]; then
    issue_num="${BASH_REMATCH[1]}"
  elif [[ "$arg" =~ ^[0-9]+$ ]]; then
    issue_num="$arg"
  else
    echo "Error: 引数は main, 番号, または WMCP-番号 の形式で指定してください" >&2
    return 1
  fi

  local worktrees_dir="$project_root/worktrees"
  local matches=()
  while IFS= read -r -d '' dir; do
    matches+=("$dir")
  done < <(find "$worktrees_dir" -maxdepth 1 -type d -name "WMCP-${issue_num}-*" -print0 2>/dev/null)

  if [[ ${#matches[@]} -eq 0 ]]; then
    echo "Error: WMCP-${issue_num} に対応するworktreeが見つかりません" >&2
    echo "  worktrees/: $(ls "$worktrees_dir" 2>/dev/null)" >&2
    return 1
  fi

  if [[ ${#matches[@]} -gt 1 ]]; then
    echo "Error: 複数のworktreeがマッチしました:" >&2
    for m in "${matches[@]}"; do
      echo "  $(basename "$m")" >&2
    done
    return 1
  fi

  cd "${matches[0]}" || return 1
}
