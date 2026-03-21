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
