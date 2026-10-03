## D196 — No screen string names a mechanism

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
instead of the outcome it produces. `scripts/docs_audit/strings.py`'s `NO_MECHANISM_WORDS` is the
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
D177's prune measurement uses for its own undercount, for the identical reason: what is
missed understates the defect, never invents one.

Reasoning stays in the decision, screens state facts; a note about zero does not draw.

### Two named exceptions: the engine picks' hover tooltips

The owner's word: plain words on the engine control, with each pick's model name in its hover tooltip.
`docs/specs/identify-engine-pick.md` section 6 draws the control. These are the only exceptions to the rule.

- The exempt strings are `HAIKU_NAME_TOOLTIP` and `MATCHER_NAME_TOOLTIP`, both exported from `app/src/engines.ts`.
- The exception covers the word-list hit only. A decision id, a repository path or a CLI string inside that text still fails the row.
- The control writes `title={MATCHER_NAME_TOOLTIP}`. The AST walk cannot read an identifier at the use site.
  So the row reads each constant's declared text from its file and checks that text as a string a person reads.
- The row exempts a string only when the whole string equals one of the two constants. A longer string that holds one is caught.
- A third model string needs its own constant, its own owner word and its own record here.
- Each constant is declared on one line, with one pair of quotes, no backslash and no `${`. Any other shape is a finding.
- `Haiku` and `Marqo` are on the word list in `scripts/machine-words.json`. Any other string that names a model is caught.
- If the file or a constant is absent, nothing is exempt for it.
- The label on each pick stays in plain words. Only the two tooltips name a model.
