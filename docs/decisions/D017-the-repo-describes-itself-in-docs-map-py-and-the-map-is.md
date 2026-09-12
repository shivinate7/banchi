## D17 — The repo describes itself in `docs/map.py`, and the map is audited

Two questions kept costing a full search to answer: *what is built and what is TBD*, and *which settled decisions govern the file I am about to edit*. Both were already answered in prose — `docs/GATES.md` has the build order, this file has the rulings — but prose has to be read whole before it can be trusted, and the first question alone cost a subagent sweep and roughly 285k tokens in one session.

`docs/map.py` answers both in one Read: build-order status, gate status, and per-component `does` / `status` / `governed_by` / `tested_by`. Pure literals, no imports, read with `ast.literal_eval` by everything that consumes it.

**Data, not another markdown section, because it has three consumers.** A human or agent reading it once; `scripts/docs-audit.py`'s repo-map check, which verifies every claim in it — named rather than numbered, because a positional index re-drifts every time a check is added, and this one already had; and `scripts/decision-context.py`, the `PreToolUse` hook that names the governing decisions before a file is edited. Prose serves the first well and the other two not at all.

**It is audited exactly as hard as it is trusted.** An index that drifts is worse than no index, because it is believed. The repo-map check fails when a `built` path is missing, when a `planned` path has quietly arrived, when `governed_by` cites a decision with no heading, when gate status disagrees with `docs/GATES.md`, and — the rule that does the real work — when a source file exists that no entry mentions. Adding a module without touching the map fails the commit. That orphan rule is the difference between a map and a stale map.

**`governed_by` is a superset of the citations in the file's own comments,** enforced in the same check. The code already said `D9` in `pipeline/pricing.py`; the map may add D8, which the file never names but which decides where its prices come from. It may never know *less* than the code does.

**The hook is advisory and silent by default.** `scripts/decision-context.py` exits 0 unconditionally — bad input, missing map, its own bugs — and prints nothing for files no entry covers. It summarizes each decision by lifting the entry's own bolded lead-in sentences out of this file, so a summary cannot drift from the decision it summarizes; nothing is restated by hand. It emits `additionalContext`, never `permissionDecision`: `"allow"` would auto-approve every Write and Edit in the project.

Precedent for the caution: the opsec `PreToolUse` guard over-triggered and was disabled within a day. A hook that speaks on every edit gets muted, and a muted hook protects nothing. The first draft of this one merged each package's decisions into every module and told you `pipeline/pricing.py` was governed by D2, Haiku vision — true of `pipeline/`, useless there. Module entries now stand alone.

**Known limit.** The hook depends on a payload shape that has moved between Claude Code releases. If a release ignores `additionalContext` the JSON is printed instead, so the failure mode is a lost nudge and never a blocked edit — and `CLAUDE.md` points at `docs/map.py` directly, which needs no hook at all.
