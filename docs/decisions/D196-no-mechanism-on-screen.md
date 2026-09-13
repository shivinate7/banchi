## D196 — No user-visible string may name a decision, a repository path, or a pipeline-internal noun

**The owner's ruling, 2026-09-13:** the front end has to be minimal and must never explain
mechanism on screen. Read beside the "hard rules" section's own standing instruction —
*"every rule for all time, anything that can be mechanically enforced, should be mechanically
enforced"* — this is that instruction applied to a design rule rather than a process rule: the
front end is either minimal in this one checkable sense or it is not, and a session should not
have to remember to look.

**The line is drawn at what the operator holds versus what this codebase is built from.**
`docs/DESIGN.md`'s Register section and CLAUDE.md's screen table are written entirely in the
operator's own words — a card, a box, a run, an export, a listing, TCGplayer — and that
vocabulary is untouched by this rule; nothing above names them. What this rule removes is the
OTHER vocabulary that has been drifting onto screen beside it: a decision citation (`D134`,
`(D-<slug>)`, `C7`) is a fact about an argument this codebase settled, never a fact about a
card; a repository path (`inventory/prices.json`, `runs/<n>/…`) is a fact about where bytes sit
on one Mac; and a pipeline-internal noun — "the pipeline", "the resolver", "the model", "the
server sent", "the join", "the corpus", "the ledger" — names an implementation component
instead of the outcome it produces. `scripts/docs-audit.py`'s `NO_MECHANISM_WORDS` is the
single place that word list is kept, with a comment on every entry saying which internal
component it is and why it is not the operator's word.

**One exemption stands on purpose, and it is not a hole in the rule: `Notice`'s `code` prop.**
CLAUDE.md's Register paragraph already says "the pipeline's own string stays available on
hover and in the run log" — that is a designated channel for exactly the raw machine string
this rule removes from everywhere else, and the row does not read that prop.

### Mechanized

`scripts/docs-audit.py`'s `no mechanism on screen` row, `MECHANICAL`. It shells out to
`scripts/user-strings.mjs`, which walks `app/src`'s `.tsx` files through
`app/node_modules/typescript` — the compiler the app itself builds with, not a second regex
opinion about what TypeScript means — and extracts JSX text nodes, the JSX attributes `title`,
`aria-label`, `placeholder`, `label`, `alt` and `body`, literals reachable through the ternary /
`??` / `&&` / `+` shapes this tree actually builds a sentence with, and the `title` / `body` /
`action.label` fields of a `toast()` call. Code comments, `console.*` arguments, `data-*`
attributes, class names and import specifiers are never JSX text or a tracked attribute, so
none of them is filtered out after the fact — they are structurally unreachable by the walk.

The row is **expected red on this branch right now**: three sessions are editing
`app/src/*.tsx` copy concurrently with the one that built it, and the count this row prints —
23 hits at last measurement, mostly "the ledger" in `Codes.tsx` and `Orders.tsx` — is a
snapshot of the tree at that moment, cleared by those sessions rather than by this one.

### Not mechanized

**Whether a rewritten sentence still explains mechanism without naming it.** A screen could
satisfy this row by paraphrasing "the pipeline found no row" as "found no row" — mechanism
still explained, word deleted — and no machine here can tell that apart from a sentence that
genuinely stopped being about the pipeline. What is checked is the vocabulary; whether the
explaining stopped is a person's read, the same limit `no-bandaids` names for the "fix the
cause" rule one register up.

**A string reached only through a helper function.** `{formatStatus(x)}` cannot be traced back
to the literal `formatStatus` returns without data-flow analysis the AST alone does not carry,
so the count this row prints is a floor and not a census — the same word
`docs/specs/corpus-pruning.md` uses for its own undercount, for the identical reason: what is
missed understates the defect, never invents one.
