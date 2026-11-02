---
paths:
  - ".claude/rules/**"
---

# Rules

A rule that matters only under one folder lives here as `<topic>.md` with a `paths:` list of globs.
Root `CLAUDE.md`'s `## Folder rules` section names each file. `make docs-audit`'s `rule enforcement`
row reconciles that roster with this folder.

Codex reads none of this folder. Root `AGENTS.md` is generated from root `CLAUDE.md`, then each rule
file's body in the order `AGENT_RULE_ORDER` (`scripts/docs_audit/hygiene.py`) gives: frontmatter stripped,
headings demoted one level. This README is not a rule and is not composed. After you edit a body, or add
a rule file and its `AGENT_RULE_ORDER` entry, run `python3 scripts/agents_gen.py --write`. The `agent links`
row fails until you do.
