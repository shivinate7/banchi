# D74 — Docs are linted as documents

**Prose checking is scoped to what a file is, not to how much of it a session reads.** A sweep of `docs/` found two defect classes. No row of `make docs-audit` could see either one.

**Vale ran over four files, while `.vale.ini` said `[*.md]`.** So `docs/specs/` and the design references were never linted. **35 `AmericanSpelling` errors** had built up there, and no check reached them. The file list is now `git ls-files '*.md'`. A new document is linted the day it is committed.

**D60's scope is about density, not a license to leave prose unspelled.** D60 rules on the four docs that were `@`-loaded and cost tokens on every turn. Spelling costs nothing to check. The two scopes were never the same, and the target had merged them.

**The vocabulary grew by 140 terms, reviewed rather than blanket-accepted.** Two candidates were checked in context before they were admitted. `evid` and `src` are shorthand inside an algorithm description. `moded` is a deliberate verb. The 35 spelling errors were fixed, not accepted.

### The one label that was itself misspelled

**`raw color` became `raw color` on the owner's instruction, and the rename stopped at the row.** A row label is published prose. `make docs-audit` prints it, the debts record cites it, and the `numbering in code` row polices the comments that name it. A label spelled against the rule this entry sets would contradict that rule in its own report. The label, `check_raw_color`, `_RAW_COLOR_RE`, the row's summary and its self-test messages all moved together.

**The rename stopped there on purpose.** `color` appears about 120 times across 29 source files, in comments and identifiers. `.vale.ini` recorded that widening the spelling rule to source "would split the spelling inside single files and is a decision nobody has argued." This change does not widen the rule. It brings one published label into line with its report. `COLOUR`, the token-kind discriminator at `scripts/docs-audit.py`, is untouched. It is compared with `==` and never reaches a message, so it is not prose.

### `doc hygiene`, and what it is for

**Every other row reads a document's assertions. This one reads the file.** It is advisory. It asks three questions that the committed tree alone can decide. The three checks are: an instruction to an editor, a second level-1 heading, and a `path:line` citation past the end of its file.

It exists because two real defects stayed invisible to a green audit for eight days. `docs/specs/capture-server.md` carried "Leave lines 37-38 exactly as they are. Insert a blank line and this blockquote after line 38" inside a paragraph. The paste that put it there deleted the sentence it was preserving, leaving a decapitated clause. A UI research spec was two documents in one file. Neither is a false claim about the code, so no row asked.

It is advisory, not blocking, and the second condition is why. All three are provably true of the tree. That is D16's test for a blocking row. But "true" and "wrong" part company on a duplicate title. A file that deliberately carries two is a judgment. A blocking row would settle it by fiat. A second instance of the instruction case reaching main would earn a promotion.

It was mutation-tested three ways: the committed instruction, the second heading, and a citation past a file's end. Each was caught. The row was green when all three were reverted.

### Refused: a reachability check

A `reachability claims` row was built, measured and dropped within the hour. It paired a registered route from `ROUTES` with a nearby not-built phrase. It aimed at the sharpest staleness in this sweep. `docs/specs/shipping-export.md` said no route, client function or screen reached its modules, on the day D69 gave them all three.

It fired 13 times, and every firing was a false positive. Sentences such as "No history on `#/inventory` — that is the ruling above, not an omission" are claims about a feature inside a route. They are not claims about the route's reachability. Nothing separates the two without reading the sentence. A permanently lit advisory is worse than a silent check. The committed-staleness row was dropped for the same reason. One row stuck on teaches sessions to skip exit 2 against every row.

The staleness it aimed at is a process fact, not a tree fact. Both of this sweep's worst findings came from two branches landing on one day. Those findings are that one and D73's route count. Each branch was correct against a tree the other had already moved. No single commit can show that. It is recorded here and as a debt, not guarded.

### What this is not

It is not a claim that the docs are current. It is two mechanisms and one sweep. The debts record's cluster 1 still holds the five docs-to-code checks that walk one way. This entry does not touch them. They are blocked on a decision about advisory severity that this row does not settle.

### Vale retired

Vale is retired. The ruling (L3): retire it, and keep American spelling in `docs-audit`. The `identifier spelling` row reads code, as it always has. It does not yet read markdown prose for spelling. That half is lane L2, which waits on the owner. Until L2 lands, markdown prose has no spelling reader. Vale's advisory watch over `.md` files is gone, and nothing has replaced it.
