## D74 — A document is checked as a document, and every markdown file is linted rather than the four a session loads

**Prose checking is scoped to what a file is, not to how much of it a session reads.** Ruled 2026-08-30, after a sweep of `docs/` found two defect classes that no row of `make docs-audit` was structurally able to see.

**`make vale` ran over four files while `.vale.ini` always said `[*.md]`.** The target was the narrow half of that disagreement, so `docs/specs/` and `docs/design-refs/` had never been linted: **35 `AmericanSpelling` errors** had accumulated there, none reachable by any check in this repo. The file list is now `git ls-files '*.md'`, so a new document is linted the day it is committed rather than the day somebody remembers to add it to a target.

**D60's scope is an argument about density, never a license to leave prose unspelled.** That entry rules on the four docs because they were `@`-loaded and cost tokens on every turn. Spelling costs nothing to check and is wrong in the same way everywhere, so the two scopes were never the same scope and the target had silently conflated them.

**The vocabulary grew by 140 terms and was reviewed rather than blanket-accepted**, the way its first block was. Two candidates were checked in context before being let in — `evid` and `src` are shorthand names inside an algorithm description, and `moded` is a deliberate verbing — and the 35 spelling errors were fixed rather than accepted, which is what happened to `rasterizes` the first time round.

### The one label that was itself misspelled

**`raw color` became `raw color` on the owner's instruction, and the rename stopped at the row.** A row label is published prose — it is printed by `make docs-audit`, cited in `docs/DEBTS.md`, and named in the comments the `numbering in code` row polices — so a label spelled against the rule this entry sets was the rule contradicting itself in its own report. The label, `check_raw_color`, `_RAW_COLOR_RE`, the row's summary and its self-test messages all moved together.

**It stopped there deliberately.** `color` appears about 120 times across 29 source files, in comments and identifiers, and `.vale.ini` already records that widening the spelling rule to source *"would split the spelling inside single files and is a decision nobody has argued"*. This is not that widening: it is one published label brought into line with the report it appears in. `COLOUR`, the token-kind discriminator at `scripts/docs-audit.py`, is untouched — it is compared with `==` and never reaches a message, so it is not prose.

### `doc hygiene`, and what it is for

**Every other row reads a document's assertions; this one reads the file.** It is advisory, and it asks three questions decidable on the committed tree alone: a line that reads as an instruction to an editor, a second level-1 heading, and a `path:line` citation past the end of its file.

**It exists because two real defects were invisible to a green audit for eight days.** `docs/specs/capture-server.md` carried *"Leave lines 37-38 exactly as they are. Insert a blank line and this blockquote after line 38"* inside a paragraph — and the paste that put it there deleted the sentence it was preserving, leaving a decapitated clause. `docs/specs/ui-research.md` was two documents in one file. Neither is a false claim about the code, so no row asked.

**Advisory rather than blocking, and the second condition is why.** All three are provably true of the tree, which is D16's test for a blocking row, but *true* and *wrong* part company on a duplicate title: a file that deliberately carries two is a judgement, and a blocking row would settle it by fiat. What would earn a promotion is a second instance of the instruction case reaching main.

**Mutation-tested three ways** — the committed instruction, the second heading, and a citation past a file's end — each caught, and the row green when all three are reverted.

### The check that was prototyped and refused

**A `reachability claims` row was built, measured, and thrown out the same hour.** It would have paired a registered route from `ROUTES` with a nearby not-built phrase, and it was aimed at the sharpest staleness this sweep found: `docs/specs/shipping-export.md` said no route, client function or screen reached its modules on the same day D69 gave them all three.

**It fired 13 times and every one was a false positive.** Sentences like *"No history on `#/inventory` — that is the ruling above, not an omission"* are claims about a feature inside a route, not about the route's reachability, and nothing separates the two without reading the sentence. **A permanently-lit advisory is worse than a silent check**, on this repo's own finding from the committed-staleness row it dropped for the same reason: one row stuck on teaches sessions to skip exit 2 against every row that uses it.

**The staleness it was aimed at is a process fact rather than a tree fact.** Both of this sweep's worst findings — that one and D73's route count — came from two branches landing on one day, each correct against a tree the other had already moved. Nothing readable from a single commit can see that, which is why it is recorded here and in `docs/DEBTS.md` rather than guarded.

### What this is not

**It is not a claim that the docs are now current.** It is two mechanisms and one sweep. `docs/DEBTS.md` cluster 1 still holds the five docs-to-code checks that walk one way, and this entry does not touch them — they are blocked on a decision about advisory severity that this row's existence does not settle.

---
