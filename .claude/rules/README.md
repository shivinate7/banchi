---
paths:
  - ".claude/rules/**"
---

# Rules

A rule that matters only under one folder lives here as `<topic>.md` with a `paths:` list of globs.
Each rule covers whole folders (`<folder>/**`). Codex reads no `.claude/rules/`, so each folder a rule covers holds
a relative symlink `AGENTS.md` to its rule file, so `app/AGENTS.md` is a link to `app.md`. A folder takes one rule.
The `agent links` row of `make docs-audit` reconciles the links with the `paths:` lists.

- `app.md`: `app/`. The front end, design system, shell and browser storage.
- `server.md`: `server/`. The threaded capture server, ports, photograph reclaim.
- `pipeline.md`: `pipeline/`, `cli/`, `identify/`. Join, pricing, emit, the paid read.
- `store.md`: `store/`. The one SQLite file, boxes, sections.
- `code-cards.md`: `codes/`, `code-card-fork/`. The dormant feature's rules.
