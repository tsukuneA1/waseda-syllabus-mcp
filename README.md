# waseda-syllabus-mcp

Waseda University Syllabus MCP Server

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
