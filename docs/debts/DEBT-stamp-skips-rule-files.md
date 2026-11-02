## DEBT-stamp-skips-rule-files — the number claim skips `.claude/rules/`, so a pending cite there turns main red

**What.** The number claim in `make merge` does not rewrite a pending cite (a `D-<slug>` or `DEBT-<slug>` cite whose number is not yet claimed) inside `.claude/rules/*.md`, because `.github/stamp.json` sets `walk.skipDotDirs` to `true` and its `cite.glossFirstUse` lists only `CLAUDE.md`.

**Outcome at risk.** A lane that cites its pending slug in a rule file merges on green checks, then the `decision ids` row of `make docs-audit` goes red on main. That row fails a cited id with no entry. A cite in `.claude/rules/server.md` or `.claude/rules/pipeline.md` also lands in the composed `server/AGENTS.md`, which the walk does rewrite, so the `agent links` row goes red too. The failure shows on main, so it is loud, not silent.

**Evidence.** Code read, not run. The walk logic is in claude-settings `actions/stamp/formats/heading.mjs` and `textFiles`. The config is this repo's `.github/stamp.json`. Likely in normal work. Frequency unmeasured.

**Fix.** Let the walk enter `.claude/rules/`, and add the rule files to `cite.glossFirstUse`.

**Closes when.** The walk enters `.claude/rules/` and the rule files are listed in `cite.glossFirstUse`.

**Owner.** shivinate7. Fix by 2026-12-01.
