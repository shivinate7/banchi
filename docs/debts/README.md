# Known gaps, deliberately unfixed

Each file here is one finding. A finding is recorded and not repaired. It says what is wrong,
what it costs, and why nobody fixed it. A green `make docs-audit` means only that the checks
which exist have passed. These entries name what those checks do not cover.

This is not a backlog to burn down on sight. An entry leaves when someone argues that it
should. A closed entry is deleted, and history lives in version control. A number is never
reused, so the gaps in the sequence are deleted entries: 5, 15, 18, 28, 35, 42, 45, 47 and 53.
Two closed entries stay because something still reads them. `detector standing` reads the
figures in DEBT6. Decision D7 cites DEBT37.

## How to find one

- **By id.** A file is named `<zero-padded number>-<slug>.md`, and a glob sorts it into
  corpus order. Entry 11 is `011-...`. Cite an entry as `DEBT<n>`, never by path and never as
  a bare `§<n>`.
- **By the index below.** `make docs-audit` reconciles it against the files, in both
  directions.

## How to add one

A branch writes `DEBT-<slug>.md` under this folder. The file starts with
`## DEBT-<slug> — <title>`, and the branch cites it as `DEBT-<slug>`. `make merge` claims the
number, renames the file, rewrites every citation, and rewrites the index. A branch never picks
its own number.

## Index

```
DEBT1 The reverse direction: five checks walk docs→code and never back
DEBT2 The map's reach
DEBT3 The claim chain
DEBT4 Criteria and evidence: nine ways a row goes quiet
DEBT6 ~~Measured against one rig, or not at all~~ — CLOSED 2026-09-09, on the owner's word
DEBT7 The preview crops the card, and the one check that looks at a photo cannot see it
DEBT8 Recorded and correctly unfixed
DEBT9 The sigil check matches text, so a renamed local walks past it
DEBT10 An order arriving mid-pass is walked but never counted, and a tab outlives its sitting
DEBT11 The capture server bounds concurrent requests, not threads, and a Playwright fleet is what finds out
DEBT12 Ten decision entries are over budget on purpose, and the budget was the thing that had drifted
DEBT13 The commit gate was measured, and it is the checks OFF it that are worth knowing about
DEBT14 A pooled card reaches the pricing table and the box walk, and `located` suppresses the label everywhere and the photograph nowhere
DEBT16 The browser fleet is locked and the rest of the load is not, and only one of those was measured
DEBT17 Four blocks still ask the viewport a question only their column can answer
DEBT19 The revert guard is exact, and three shapes of reversal walk past it
DEBT20 Two liveness oracles read a pid, and a recycled one lies to both
DEBT21 The double-click guard cannot see a run started in a terminal
DEBT22 A control shrunk inside its own sticky bar is invisible to the thumb-floor sweep
DEBT23 A sale fixture that moves after the press is only wrong sometimes, so no check can flag it
DEBT24 A zero reading cannot tell a sold-out listing from an import sitting in Staged
DEBT25 A cited section number still resolves when it is the wrong section, and no check can read what a sentence is about
DEBT26 The Intelligent Mail barcode encoder is written, correct against the Postal Service's own examples, and parked on a branch
DEBT27 `Fulfillment.tsx`'s store-wide `GET /inventory` browse is argued and left
DEBT29 The drawer's tap sweep is skipped, because it races itself on a slower runner
DEBT30 The copies panel flash guard is shelved, on the owner's own word
DEBT31 Twelve decisions are cited by path, one of them dead, and the path guard never reads code
DEBT32 The archive sweep stays a press, and the owner intends to schedule it eventually
DEBT33 An answered queue entry can never resurface, even when it is wrong
DEBT34 The catalogue cache never expires, on a membership claim this store cannot re-check on its own
DEBT36 A layout read taken while the page still moves is wrong
DEBT37 ~~under `--cap`, a pending copy and an unseen live copy can both be out~~ — CLOSED 2026-09-27, on the owner's word
DEBT38 a section move's receipt names no owed cards and no next capture
DEBT39 the public demo refuses every box map move
DEBT40 a divider save can move a divider past departed records
DEBT41 Pricing never offers "Make this the rule"
DEBT43 the merge-speed guard counts SQLite ticks only, and a pure-Python loop is invisible to it
DEBT44 pokemontcg.io is deprecated (ends 2027-03-01), and `pipeline/stockimages.py` does not call it today
DEBT46 a search with a typo finds nothing, and no near match is offered
DEBT48 code-side mechanization left open after PR #379 / PR #380
DEBT49 `_copies_out` and `_committed_keys` cost a full-table pass per call
DEBT50 git and gh CLI traps hit from this checkout
DEBT51 A guard or probe can pass for the wrong reason
DEBT52 Claude Code multi-agent and worktree session traps
DEBT54 the 13th-row undo walk times out under load
DEBT55 the audit self-test crashes when app/node_modules is missing
DEBT56 the worktree-provision selftest's race case fails
DEBT57 an emit over a buried box made ghost cards and phantom copies
DEBT58 the Lane H palette record is on a branch, not in main
DEBT59 an unreadable live claim has no way out on screen
DEBT60 the demo builds with Hide unpullable forced off
DEBT-advances-carryover eight build proposals from the 2026-08-31 review are still open
DEBT-demo-assets-lfs the demo photos are 171 MB of plain git, and the owner wants them in Git LFS
```
