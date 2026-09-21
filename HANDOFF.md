# Handoff — rot-reduction session, 2026-09-20

Branch `claude/docs-audit-line-refs-1bc6c4`, 16 commits, `make check` green, tree clean.
NOT pushed and NOT merged. The owner ruled: keep accumulating, one PR at the end.

The session stopped on a monthly spend limit. Two subagents died mid-flight; their work was
recovered or confirmed empty before stopping. Nothing is lost.

## What landed

| Change | Measured result |
|---|---|
| `line anchors` row reads the `:N` in a citation | 69.7% of checkable code anchors pointed at the wrong line |
| `derived numbers` registry + generator | tree-describing figures cannot rot; 3 were already wrong |
| `Report.as_json()` withholds a clean summary beside findings | `views exposure` had published "no manifest view can draw a stored photo" next to 7 saying it can |
| 15 guard self-tests path-gated (`scripts/guard-scope.py`) | `make check` 163.85s to 116.7s |
| harness dropped from turn end (`scripts/stop-gate.sh`) | 24.85s to 0.006s per turn |
| `commit path` reads the AST, not a declared `writes` field | claim now backed by code, both directions |
| id claimer recognises an unclaimed heading by the complement | 3 heading shapes escaped the old pattern |
| 9 false CLAUDE.md claims corrected | incl. `cards.cid` marked NOT BUILT while shipping |
| code cards folded to one rules file, marked dormant | `code-card-fork/CLAUDE.md` is now a symlink |

## Owner rulings NOT yet executed

1. **Sanitize every grandfathered record repo-wide** to the parent config's prose discipline.
   359 markdown records, 4.16 MB: decisions 2.16 MB (244 files), specs 1.69 MB (41), debts
   187 KB (31), gates 124 KB (43). The 20 over-budget decision entries were dispatched and the
   agent died at the very start with nothing written. **Measurements, dates, commit hashes,
   file names, symbols and citations are evidence and are never cut — only narration goes.**
   Gate record numbers are evidence twice over and are never rewritten.
2. **Shrink CLAUDE.md drastically**, by the parent config's prose rules, no numeric target.
   Candidates measured: the Commands block duplicates `make help`, the screens table
   duplicates `ROUTES`, the decision index is 236 one-line glosses.
3. **Turn the `views exposure` advisory off** and note it in CLAUDE.md's dormant code-card
   section so it is turned back on when code-card work resumes. **Leave `scripts/guard-opsec.sh`
   ARMED** — it refuses a real code-card photo into a commit and protects real money.
4. **Allowlist `game coverage`'s One Piece SR/TR pair** with the reason.
5. **Document `reap`, `janitor-install` and `merge`** in CLAUDE.md's Commands block, and fix
   `make help`'s false claim that `catalog-index-selftest` is in `check`.
6. **Delete `make orient-selftest`** — it fails on the live tree, asserting against
   `WalkGroups`, deleted weeks ago, and nothing noticed because it sits outside `make check`.

## Open findings nobody has actioned

- `docs/specs/store-scaling/02-per-box-read.md` says "Nothing below is built" while D192 shipped it.
- `docs/specs/revenue-next.md` says "Nothing here is built" while its finding 1 is fixed in `app/src/Revenue.tsx`.
- CLAUDE.md's `one-process.md` roster line reads as contradicting that spec's own BUILT status.
- `doc hygiene` is a fifth permanent advisory nobody counted. The real total is 42, not 32.
- `breakpoint columns` is genuinely actionable, but the owner has column work in another
  session. **Prose only, do not touch the CSS.**
- `entry budget` still reports 20. The owner overruled the earlier "they are fine" judgement.

## Coverage, stated honestly

The second-pass audit of `docs-audit`'s 106 rows read 15 function bodies line by line and
skimmed the rest at their `report.add` site only. Those are unknown, not clean. The specs
audit checked 29 of 41 against code and found zero false status claims. 19 of the 21
`mechanization-backlog.md` ranks were never sampled.

## Before any cleanup

`.claude/worktrees/agent-ac9e8483a19d6d29e` was recovered into commit `394f2abb`.
`agent-add21e3335090faf3` held nothing. Both may now be reaped safely.
