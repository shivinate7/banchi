# Known gaps, deliberately unfixed

**THE ENTRIES ARE IN `docs/debts/`, ONE FILE EACH, AND THIS FILE IS A POINTER.** It was one
174 KB document until 2026-09-16. Nothing reads it. `scripts/debts_corpus.py` reads the
directory and hands every checker the same bytes it used to get from here. It builds the
same seam `scripts/decisions_corpus.py` built for `docs/DECISIONS.md` under D160.

**CITE BY ID, `DEBT<n>`, NEVER BY PATH AND NEVER BY A BARE `§<n>`.** The parent-level rule
(`~/Developer/claude-settings/CLAUDE.md`: "Give each record its own file, one folder per
kind. Cite by id, never by path.") applies here exactly as D160 already applied it to
decisions, on D42's own precedent for a prefixed token: `DEBT11`, not `§11`.

A bare `§<n>` names no document. This repo has dozens of numbered documents. A session
reading "§11" with no prefix cannot tell DEBT11 from a spec's own eleventh section without
tracing the surrounding prose. That is D149's exact failure, reproduced once already in this
split's own first draft. `DEBT<n>` is one token. It is greppable and cannot collide with any
other document's numbering.

Every old spelling that combined this file's path with a section number is retired: the
plain form, the possessive form, and the hash form. `DEBT<n>` replaces all of them. A bare
reference to this file with no number — "read `docs/DEBTS.md` first" — is not a record
citation. It is unaffected: it points at this stub exactly as `docs/DECISIONS.md` still does
for decisions.

**Inside `docs/debts/` itself, an entry may still cite a sibling entry with a bare `§<n>`.**
That is a same-corpus self-reference, not a cross-document citation. It is what the entries
already did before the split (entry 25's own prose is one example). The rule above governs
every OTHER file in this tree.

Findings recorded rather than repaired. Each says what is wrong, what it costs, and why it
is not fixed. This file exists so a green `make docs-audit` is not read as "the auditor is
complete". It means the checks that exist, passed.

Not a backlog to burn down on sight. An entry leaves when someone argues it should, the way
`docs/decisions/` entries are argued.

## How to find one

- **By id** — the files are named `<zero-padded n>-<slug>.md` under `docs/debts/`. They
  sort into corpus order, so a glob and `ls` agree without anybody sorting. Entry 11's file
  starts with `011-`.
- **By the index** — the fenced block below, reconciled against the corpus in both
  directions by `make docs-audit`'s `debt index` row.
- **Entries 15 and 30 are deliberate gaps, not missing files.** 15 left 2026-09-07 (D120
  answered it). 30 left 2026-09-17, repaired rather than argued away: its own reading — that
  `#/orders` carried a real sub-pixel reflow — was measured and found false, the `bn-page-in`
  entry animation was what the ruler had been reading, and `app/tests/motionSettled.ts` now
  waits it out. Neither number is reused. `docs/map.py` uses the same rule for its own step ids: a
  renumber leaves every citation pointing at a real entry that is not the one meant.

## Why it is a directory

**Same argument as D160's, applied to this file rather than re-derived for it.** Two pull
requests appending a finding to one 2,444-line file collide, exactly as two pull requests
appending a decision did. `scripts/split-debts.py` performed the move. It is proved lossless
by its own `--verify`/`--selftest`, which reassemble the directory and diff it against the
original bytes — byte-identical, not merely fact-preserving.

## Index

```
DEBT1  The reverse direction: five checks walk docs→code and never back
DEBT2  The map's reach
DEBT3  The claim chain
DEBT4  Criteria and evidence: nine ways a row goes quiet
DEBT5  The departed card on screen
DEBT6  ~~Measured against one rig, or not at all~~ — CLOSED 2026-09-09, on the owner's word
DEBT7  The preview crops the card, and the one check that looks at a photo cannot see it
DEBT8  Recorded and correctly unfixed
DEBT9  The sigil check matches text, so a renamed local walks past it
DEBT10 An order arriving mid-pass is walked but never counted, and a tab outlives its sitting
DEBT11 The capture server bounds concurrent requests, not threads, and a Playwright fleet is what finds out
DEBT12 Ten decision entries are over budget on purpose, and the budget was the thing that had drifted
DEBT13 The commit gate was measured, and it is the checks OFF it that are worth knowing about
DEBT14 A pooled card reaches the pricing table and the box walk, and `located` suppresses the label everywhere and the photograph nowhere
DEBT16 The browser fleet is locked and the rest of the load is not, and only one of those was measured
DEBT17 Four blocks still ask the viewport a question only their column can answer
DEBT18 ~~The suite fetches three typefaces from Google Fonts on every page load~~ — CLOSED 2026-09-08
DEBT19 The revert guard is exact, and three shapes of reversal walk past it
DEBT20 Two liveness oracles read a pid, and a recycled one lies to both
DEBT21 The double-click guard cannot see a run started in a terminal
DEBT22 A control shrunk inside its own sticky bar is invisible to the thumb-floor sweep
DEBT23 A sale fixture that moves after the press is only wrong sometimes, so no check can flag it
DEBT24 A zero reading cannot tell a sold-out listing from an import sitting in Staged
DEBT25 A cited section number still resolves when it is the wrong section, and no check can read what a sentence is about
DEBT26 The Intelligent Mail barcode encoder is written, correct against the Postal Service's own examples, and parked on a branch
DEBT27 Two `GET /inventory` call sites were store-wide; site 1 is closed, site 2 is argued and left
DEBT28 `pkmnscan rescue` is reachable from no screen, and the screen that needs it names a command
DEBT29 The drawer's tap sweep is skipped, because it races itself on a slower runner
DEBT30 The copies panel flash guard is shelved, on the owner's own word
DEBT31 Twelve decisions are cited by path, one of them dead, and the path guard never reads code
DEBT32 The archive sweep stays a press, and the owner intends to schedule it eventually
DEBT33 An answered queue entry can never resurface, even when it is wrong
DEBT34 The catalogue cache never expires, on a membership claim this store cannot re-check on its own
DEBT35 ~~emit exits differently on one run and several runs~~ — CLOSED 2026-09-25, fixed as recommended
DEBT37 under `--cap`, a pending copy and an unseen live copy can both be out
```
