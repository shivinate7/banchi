# Known gaps, deliberately unfixed

**THE ENTRIES ARE IN `docs/debts/`, ONE FILE EACH, AND THIS FILE IS A POINTER.** It was one
174 KB document until 2026-09-16. Nothing reads it. `scripts/debts_corpus.py` reads the
directory and hands every checker the same bytes it used to get from here. It builds the
same seam `scripts/decisions_corpus.py` built for `docs/DECISIONS.md` under D160.

**CITE BY ID, `§<n>`, NEVER BY PATH.** The parent-level rule
(`~/Developer/claude-settings/CLAUDE.md`: "Give each record its own file, one folder per
kind. Cite by id, never by path.") applies here exactly as D160 already applied it to
decisions. `§11` is the id. `docs/DEBTS.md §11`, `` `docs/DEBTS.md`'s section 11 ``,
`docs/DEBTS.md #11` and every other path-plus-number spelling are the path form, and this
split retires all of them repo-wide. A bare reference to this file with no number — "read
`docs/DEBTS.md` first" — is not a record citation. It is unaffected: it points at this stub
exactly as `docs/DECISIONS.md` still does for decisions.

Findings recorded rather than repaired. Each says what is wrong, what it costs, and why it
is not fixed. This file exists so a green `make docs-audit` is not read as "the auditor is
complete". It means the checks that exist, passed.

Not a backlog to burn down on sight. An entry leaves when someone argues it should, the way
`docs/decisions/` entries are argued.

## How to find one

- **By id** — the files are named `<zero-padded n>-<slug>.md` under `docs/debts/`. They
  sort into corpus order, so a glob and `ls` agree without anybody sorting.
- **By the index** — the fenced block below, reconciled against the corpus in both
  directions by `make docs-audit`'s `debt index` row.
- **§15 is a deliberate gap, not a missing file.** It left 2026-09-07 (D120 answered it) and
  its number is not reused. `docs/map.py` uses the same rule for its own step ids: a
  renumber leaves every citation pointing at a real entry that is not the one meant.

## Why it is a directory

**Same argument as D160's, applied to this file rather than re-derived for it.** Two pull
requests appending a finding to one 2,444-line file collide, exactly as two pull requests
appending a decision did. `scripts/split-debts.py` performed the move. It is proved lossless
by its own `--verify`/`--selftest`, which reassemble the directory and diff it against the
original bytes — byte-identical, not merely fact-preserving.

## Index

```
§1  The reverse direction: five checks walk docs→code and never back
§2  The map's reach
§3  The claim chain
§4  Criteria and evidence: nine ways a row goes quiet
§5  The departed card on screen
§6  ~~Measured against one rig, or not at all~~ — CLOSED 2026-09-09, on the owner's word
§7  The preview crops the card, and the one check that looks at a photo cannot see it
§8  Recorded and correctly unfixed
§9  The sigil check matches text, so a renamed local walks past it
§10 An order arriving mid-pass is walked but never counted, and a tab outlives its sitting
§11 The capture server bounds concurrent requests, not threads, and a Playwright fleet is what finds out
§12 Ten decision entries are over budget on purpose, and the budget was the thing that had drifted
§13 The commit gate was measured, and it is the checks OFF it that are worth knowing about
§14 A pooled card reaches the pricing table and the box walk, and `located` suppresses the label everywhere and the photograph nowhere
§16 The browser fleet is locked and the rest of the load is not, and only one of those was measured
§17 Four blocks still ask the viewport a question only their column can answer
§18 ~~The suite fetches three typefaces from Google Fonts on every page load~~ — CLOSED 2026-09-08
§19 The revert guard is exact, and three shapes of reversal walk past it
§20 Two liveness oracles read a pid, and a recycled one lies to both
§21 The double-click guard cannot see a run started in a terminal
§22 A control shrunk inside its own sticky bar is invisible to the thumb-floor sweep
§23 A sale fixture that moves after the press is only wrong sometimes, so no check can flag it
§24 A zero reading cannot tell a sold-out listing from an import sitting in Staged
§25 A cited section number still resolves when it is the wrong section, and no check can read what a sentence is about
§26 The Intelligent Mail barcode encoder is written, correct against the Postal Service's own examples, and parked on a branch
§27 Two `GET /inventory` call sites were store-wide; site 1 is closed, site 2 is argued and left
§28 `pkmnscan rescue` is reachable from no screen, and the screen that needs it names a command
```
