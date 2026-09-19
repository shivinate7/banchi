## D-no-typed-interpunct-on-screen — A typed dot is a defect wherever it is typed, and the reader is the mechanism this time, not the sweep

**The owner's ruling, 2026-09-19: "this typed dot needs to be removed everywhere it exists."**

### What D41 already decided, and what it did not reach

D41 deleted the dot-joined address string from `#/inventory`, `#/review`, `#/capture` and every other owner site that used to render `Box 2 · Section 1 · Card 14` as one line, and it did not restyle the separator — it removed it. Where a seam is still wanted, it is drawn by CSS now: `.boxops-identity-part::before { content: '·' }` and five siblings just like it (`Orders.css`, `BoxBrowse.css`, `RunPanel.css`, `CardLocations.css`, `Pricing.css`) paint a dot BESIDE a fact, never INTO one. That is the distinction this entry generalises: **a separator is a style property of the layout. A fact is a string a component holds.** D41 settled it for one string. The rest of the app kept typing the same character into hundreds of others, because nothing had ever said the pattern, only the instance.

A survey run the day of the ruling found roughly 200 typed middle dots (U+00B7) still reaching the screen across every route, built the same way `Box 2 · Section 1 · Card 14` used to be — a list of parts, joined with `' · '`, handed straight to JSX. Two sites re-type the address specifically, which is what makes them roots rather than instances: `PositionLabel.tsx`'s `whole()` fallback (`parts.join(' · ')`, three call sites — lines 159, 167, 213) and `Fulfillment.tsx`'s `sellable()`/`pickSellable()`, which build a card's `about` field the same way (`about.join(' · ')`, lines 182 and 223) for `PlaceText` to read back later. Every `#/pricing`, `#/orders`, `#/capture` sentence that joins two facts with a dot is the same pattern at a smaller scale.

### What this rule protects, and what protected it before

**Structure over strings: a fact is an element. A separator is a style.** A typed `' · '` inside a string a component builds is a decision made once, in source, about how two facts will always be joined. It cannot be themed. It cannot be dropped at a breakpoint without an `if`. And it is invisible to anything that reads the STRUCTURE of what is on screen rather than its rendered pixels — a screen reader gets an extra dot as a word, and the `no mechanism on screen` row and this one both have to parse THROUGH it rather than around it. D41 is the worked example of what removing it buys: a two-line stacked path with no seam at all, because once the parts are elements rather than words in one string, there is nothing left to join. Before this entry, nothing protected the pattern once D41 shipped. Only the one string was protected.

### The ratchet, and why a cliff was refused

The sweep that removes the measured hits below is a separate, per-screen task. The owner named it explicitly as not this one's job. A row that failed on every existing hit would be permanently red the day it landed. That teaches a session to ignore red rather than to trust it — the same argument D194's own header makes for the word-count ceiling. So this is a RATCHET, mirroring D194's `copy-budget.json` discipline exactly: `scripts/typed-interpunct.json` pins the count `node scripts/typed-interpunct-pin.mjs --pin` last measured. The row (`make docs-audit`'s `typed interpunct` row, `scripts/docs-audit.py:check_typed_interpunct`) only ever READS that pin. D18 forbids it writing, since it sits on the commit path. And:

- a count AT OR BELOW the pin is silent. The row prints it and passes. No finding, no question asked of anyone who did not just add a dot.
- a count ABOVE the pin FAILS, naming the rise and every current hit by file:line and string.
- **the pin never moves except by `--pin`, run by a person, on purpose.** Nothing lowers it automatically when the sweep starts landing, because "quietly assumed" is exactly the failure a ratchet exists to prevent. The diff to `typed-interpunct.json` is the record of who chose to accept a new number, and when.

### What the reader can see, and what it cannot

The extraction is `scripts/user-strings.mjs`'s existing AST walk — the same one `no mechanism on screen` (D196) uses — run with two widenings scoped to THIS row alone (`TYPED_INTERPUNCT_EXTRACT_ARGS` in `scripts/docs-audit.py`, `--join-literals --include-code-attr` in the script). D196's own fixtures and its documented exemption stay exactly as they were:

- **`--include-code-attr`** tracks `Notice`'s own `code` prop. It is exempt from D196's mechanism-naming policy on purpose (CLAUDE.md: "the pipeline's own string stays available on hover and in the run log"), but it is not exempt from THIS rule. A typed dot inside it still reaches a person, on hover and in the run log, which is the only fact this rule cares about.
- **`--join-literals`** reads the literal separator argument of any `<expr>.join(<literal>)` call, wherever the call's return value travels — a local helper's parameter (`PositionLabel.tsx`'s `whole(parts.join(' · '))`), or an object field read back by a different component (`Fulfillment.tsx`'s `about: about.join(' · ')`) — rather than only where the call is itself the JSX child. This is what makes the two roots visible starting today, instead of waiting for the sweep to touch them first.

**What is still invisible, named rather than hidden behind a clean run:**

- A helper that assembles a separator WITHOUT `.join` — string concatenation into a `const`, or a template literal, returned by a named function and interpolated elsewhere by reference (`{formatThing(x)}`) — is the same data-flow gap `no mechanism on screen`'s own docstring names for itself, one call shape narrower. Tracing it needs real data-flow analysis the AST alone does not carry.
- **CSS is never read.** The walk is `.tsx` only. `ReviewQueue.css:772` types a WHOLE SENTENCE into a `content:` property — `content: 'Parked · under the threshold'` — a different and worse defect than a bare separator (D41's own CSS rules paint only `'·'`, nothing else). It is invisible to this row no matter how the extractor is widened, because `content:` never becomes a `.tsx` AST node. Recorded here for the sweep to find by hand.
- **Server-side strings are a different language.** `pipeline/join.py`'s `Position.label`, `pooled_label`, `departed_label` and `place_text` all still compose `' · '`-joined text, and D41 keeps every one of them exactly as they are. They are the accessible name a screen reader announces. The rule this entry states is that a CLIENT stops rendering them VERBATIM, never that the server stops emitting them. A Python string is not something this row, or `scripts/user-strings.mjs`, can or should reach.

### The scoreboard, so the sweep has a starting line

Counted by hand the day of the survey, by file, before this row existed to recount them precisely:

| Screen / file | Survey's count |
|---|---|
| Pricing | ~35 |
| Runs (five files) | ~30 |
| BoxBrowse | ~22 |
| Orders | ~20 |
| Capture | ~16 |
| Review | ~15 |
| Fulfillment | ~12 |
| Home | 11 |
| Codes | 11 |
| CardLocations | 7 |
| position.ts | 7 |

Plus `ReviewQueue.css:772` and the four `pipeline/join.py` functions named above. Both kinds are out of this row's reach, named above under "what it cannot see."

**The row's own number is the record now, not this table.** `scripts/typed-interpunct.json` pins **249** as measured the day this entry landed. That is higher than the survey's rough 200, because `--join-literals` and `--include-code-attr` see two whole channels — the two re-typing roots, and `Notice`'s `code` prop — that the hand survey had no reason to isolate. Whoever runs the sweep should re-pin as each screen's count reaches zero, watching the total fall through `git diff scripts/typed-interpunct.json`, never by editing the number by hand.

### Governed by

D41: the worked example this rule generalises. The address string's dot was removed, not restyled, and the separator moved into CSS. D194: the ratchet discipline this row's pin mirrors exactly. A ceiling only a person moves, never a cliff nobody can pass on day one. D196: the same extractor, `scripts/user-strings.mjs`, and the same discipline of keeping a widened notion of "visible" off a rule that was not asked for it. This row's two extractor flags stay off `no mechanism on screen`'s own call, by construction, so D196's fixtures and its `Notice`-`code` exemption are untouched. D18: `scripts/docs-audit.py`'s row never writes. `scripts/typed-interpunct-pin.mjs` is the one generator allowed to, run by hand, never on the commit path. D173: the mechanism is `make docs-audit`'s `typed interpunct` row, cited by name in CLAUDE.md's Hard rules.

---
