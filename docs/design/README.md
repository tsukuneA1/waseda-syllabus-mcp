# Design Documents

This directory contains design documents for the Waseda Syllabus MCP project.

## Purpose

Design docs help us:
- Think through architectural decisions before implementing
- Document the "why" behind technical choices
- Share context with team members
- Create a historical record of decisions

## Using the Template

Copy [template.md](./template.md) when creating a new design doc:

```bash
cp docs/design/template.md docs/design/my-component.md
```

## Design Doc Process

1. **Draft**: Create design doc and open PR for feedback
2. **Review**: Get feedback from relevant stakeholders
3. **Approved**: Merge when consensus is reached
4. **Implemented**: Update doc if implementation diverges significantly

## Current Design Docs

- [template.md](./template.md) - Template for new design docs
- [backend-architecture.md](./backend-architecture.md) - Backend architecture and uv workspace setup
- [frontend-architecture.md](./frontend-architecture.md) - Frontend Next.js architecture
- [crawler-design.md](./crawler-design.md) - Web scraping and data ingestion strategy
- [mcp-server-design.md](./mcp-server-design.md) - MCP server implementation
- [database-schema.md](./database-schema.md) - Database schema and indexing strategy

## Notes

- Design docs are living documents - update them as designs evolve
- Not every feature needs a design doc - use judgment
- Keep docs concise and actionable
