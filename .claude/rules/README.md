---
paths:
  - ".claude/rules/**"
---

# Rules

A rule that matters only under one folder lives here as `<topic>.md` with a `paths:` list of globs.
Root `CLAUDE.md`'s `## Folder rules` section names each file. `make docs-audit`'s `rule enforcement`
row reconciles that roster with this folder.

Codex reads none of this folder. Root `CLAUDE.md`'s `## Folder rules` section names each folder that
holds an `AGENTS.md` symlink to its rule file. `server/AGENTS.md` is a composed file: the bodies of `server.md` and `pipeline.md`, frontmatter
stripped and the second one's headings demoted. After you edit either body, run
`python3 scripts/agents_gen.py --write`. The `agent links` row fails until you do.
