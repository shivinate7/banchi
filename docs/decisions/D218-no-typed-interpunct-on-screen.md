## D218 — A typed dot is a defect wherever it is typed, and the reader is the mechanism this time, not the sweep

**The owner's ruling, 2026-09-19: "this typed dot needs to be removed everywhere it exists."**

### What D41 already decided, and what it did not reach

D41 deleted the dot-joined address string from `#/inventory`, `#/review`, and `#/capture`. Every other owner site had the same string. It rendered `Box 2 · Section 1 · Card 14` as one line. D41 did not restyle the separator. It removed the separator.

Where a seam is still wanted, CSS draws it now. `.boxops-identity-part::before { content: '·' }` is one example. Five siblings work the same way, in `Orders.css`, `BoxBrowse.css`, `RunPanel.css`, `CardLocations.css`, and `Pricing.css`. Each paints a dot BESIDE a fact. None types a dot INTO one.

That is the distinction this entry generalises. **A separator is a style property of the layout. A fact is a string a component holds.** D41 settled this for one string. The rest of the app kept typing the same character into hundreds of others. Nothing had ever said the pattern. Only the instance was fixed.

A survey ran the day of the ruling. It found roughly 200 typed middle dots (U+00B7) still reaching the screen, across every route. Each was built the same way `Box 2 · Section 1 · Card 14` used to be. A list of parts, joined with `' · '`, handed straight to JSX.

Two sites re-type the address specifically. That is what makes them roots, not instances. `PositionLabel.tsx`'s `whole()` fallback is one: `parts.join(' · ')`, at three call sites, lines 159, 167, and 213. `Fulfillment.tsx`'s `sellable()` and `pickSellable()` are the other. They build a card's `about` field the same way, `about.join(' · ')`, at lines 182 and 223, for `PlaceText` to read back later. Every `#/pricing`, `#/orders`, or `#/capture` sentence that joins two facts with a dot repeats the same pattern, at a smaller scale.

### What this rule protects, and what protected it before

**Structure over strings: a fact is an element. A separator is a style.** A typed `' · '` inside a built string is a decision made once, in source code. It fixes how two facts will always be joined. It cannot be themed. It cannot be dropped at a breakpoint without an `if`.

It is also invisible to anything that reads structure rather than pixels. A screen reader hears the dot as an extra word. The `no mechanism on screen` row, and this one, both have to parse through it, not around it.

D41 is the worked example of what removing it buys. It leaves a two-line stacked path with no seam at all. Once the parts are elements, not words in one string, there is nothing left to join.

Before this entry, nothing protected the pattern once D41 shipped. Only the one string was protected.

### The ratchet, and why a cliff was refused

The sweep that removes the hits below is a separate task, one screen at a time. The owner named it explicitly. It is not this task's job.

A row that failed on every existing hit would be red the day it landed. That teaches a session to ignore red, rather than trust it. D194's own header makes the same argument, for the word-count ceiling.

So this is a RATCHET, mirroring D194's `copy-budget.json` discipline exactly. `scripts/typed-interpunct.json` pins the count `node scripts/typed-interpunct-pin.mjs --pin` last measured. It is `make docs-audit`'s `typed interpunct` row, in `scripts/docs-audit.py:check_typed_interpunct`. D18 forbids it writing, since it sits on the commit path.

- A count at or below the pin is silent. The row prints it and passes. It asks no question of anyone who did not just add a dot.
- A count above the pin fails. It names the rise, and every current hit, by file and line.
- **The pin never moves except by `--pin`, run by a person, on purpose.** Nothing lowers it automatically as the sweep lands. A quiet assumption is the failure a ratchet exists to prevent. The diff to `typed-interpunct.json` records who accepted a new number, and when.

### What the reader can see, and what it cannot

The extraction is `scripts/user-strings.mjs`'s existing AST walk. It is the same one `no mechanism on screen` (D196) uses. This row runs it with two widenings, scoped to itself alone. `TYPED_INTERPUNCT_EXTRACT_ARGS`, in `scripts/docs-audit.py`, passes `--join-literals --include-code-attr` to the script. D196's own fixtures, and its documented exemption, stay exactly as they were.

- **`--include-code-attr`** tracks `Notice`'s own `code` prop. D196 exempts this prop from its mechanism-naming policy on purpose. CLAUDE.md says the pipeline's own string stays available on hover and in the run log. This rule does not exempt it. A typed dot inside it still reaches a person, on hover and in the run log. That is the only fact this rule cares about.
- **`--join-literals`** reads the literal separator argument of any `<expr>.join(<literal>)` call. It reads the value wherever the call's return travels. That includes a local helper's parameter, or an object field read back by a different component. `PositionLabel.tsx`'s `whole(parts.join(' · '))` is one shape. `Fulfillment.tsx`'s `about: about.join(' · ')` is the other. Neither call is itself a JSX child, so the base walk misses both. This widening makes the two roots visible today, instead of waiting for the sweep to reach them first.

**What is still invisible, named rather than hidden behind a clean run:**

- A helper can build a separator without `.join`. It might use string concatenation into a `const`. It might return a template literal. Either way, if it is read elsewhere by reference, `{formatThing(x)}`, this walk cannot see it. `no mechanism on screen`'s own docstring names this same gap for itself. This rule narrows it by one call shape, and no further. Tracing it needs real data-flow analysis, which an AST alone does not carry.
- **CSS is never read.** The walk covers `.tsx` files only. `ReviewQueue.css:772` types a whole sentence into a `content:` property: `content: 'Parked · under the threshold'`. That is a different, and worse, defect than a bare separator. D41's own CSS rules paint only `'·'`, nothing else. No widening of this extractor can see it, because `content:` never becomes a `.tsx` AST node. It is recorded here for the sweep to find by hand.
- **Server-side strings are a different language.** `pipeline/join.py`'s `Position.label`, `pooled_label`, `departed_label`, and `place_text` all still compose `' · '`-joined text. D41 keeps every one of them exactly as it is. They are the accessible name a screen reader announces. This entry's rule is that a CLIENT stops rendering them verbatim. It is not that the server stops emitting them. A Python string is not something this row, or `scripts/user-strings.mjs`, can or should reach.

### The scoreboard, so the sweep has a starting line

The survey counted these by hand, the day of the ruling, before this row existed to recount them precisely.

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

Two more items sit outside this table: `ReviewQueue.css:772`, and the four `pipeline/join.py` functions named above. Both are out of this row's reach, named above under "what it cannot see."

**The row's own number is the record now, not this table.** `scripts/typed-interpunct.json` pins **249**, as measured the day this entry landed. That is higher than the survey's rough 200. `--join-literals` and `--include-code-attr` see two whole channels the hand survey had no reason to isolate: the two re-typing roots, and `Notice`'s `code` prop. Whoever runs the sweep should re-pin as each screen's count reaches zero. Watch the total fall through `git diff scripts/typed-interpunct.json`. Never edit the number by hand.

### Governed by

D41 is the worked example this rule generalises. The address string's dot was removed, not restyled, and the separator moved into CSS.

D194 is the ratchet discipline this row's pin mirrors exactly. A ceiling only a person moves, never a cliff nobody can pass on day one.

D196 is the same extractor, `scripts/user-strings.mjs`, under the same discipline. A widened notion of "visible" stays off a rule that never asked for it. This row's two extractor flags stay off `no mechanism on screen`'s own call, by construction. D196's fixtures, and its `Notice`-`code` exemption, are untouched.

D18 is why `scripts/docs-audit.py`'s row never writes. `scripts/typed-interpunct-pin.mjs` is the one generator allowed to write, run by hand, never on the commit path.

D173 names the mechanism: `make docs-audit`'s `typed interpunct` row, cited by name in CLAUDE.md's Hard rules.

### Superseded in part 2026-09-24 — `D280`

**The ratchet is gone. The rule stays.** A typed middle dot or bullet in a user-visible string is still a defect. The owner retired every pinned count. The `typed interpunct` row now fails on each typed dot that `scripts/typed-interpunct-allow.json` does not list, by file and by string. It also fails on a stale entry, and on growth over the list at the merge-base. `scripts/typed-interpunct.json` and `scripts/typed-interpunct-pin.mjs` are deleted.

**What is kept.** The rule, the two extractor widenings, and every gap this entry names. The scoreboard above is history. The list is the record now.

---
