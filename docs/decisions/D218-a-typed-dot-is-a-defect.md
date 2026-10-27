# D218 — A typed dot is a defect

A typed middle dot or bullet (U+00B7, U+2022) in a user-visible string is a defect. The owner ruled that the typed dot be removed everywhere it exists.

Kind: process
Home: scripts/docs_audit/strings.py

### What D41 already decided, and what it did not reach

D41 deleted the dot-joined address string from `#/inventory`, `#/review`, and `#/capture`. Every other owner site had the same string. It rendered `Box 2 · Section 1 · Card 14` as one line. D41 did not restyle the separator. It removed the separator.

Where a seam is still wanted, CSS draws it now. `.boxops-identity-part::before { content: '·' }` is one example. Five siblings work the same way, in `Orders.css`, `BoxBrowse.css`, `RunPanel.css`, `CardLocations.css`, and `Pricing.css`. Each paints a dot BESIDE a fact. None types a dot INTO one.

That is the distinction this entry generalises. **A separator is a style property of the layout. A fact is a string a component holds.** D41 settled this for one string. The rest of the app kept typing the same character into other strings. Nothing had ever said the pattern. Only the instance was fixed.

Each typed dot is built the same way `Box 2 · Section 1 · Card 14` used to be: a list of parts, joined with `' · '`, handed straight to JSX. Two shapes re-type the address as a built string. One is a fallback that joins the parts and hands the result to a helper. The other is a card's `about` field, joined the same way for a later component to read back. Every `#/pricing`, `#/orders`, or `#/capture` sentence that joins two facts with a dot repeats the same pattern, at a smaller scale.

### What this rule protects, and what protected it before

**Structure over strings: a fact is an element. A separator is a style.** A typed `' · '` inside a built string is a decision made once, in source code. It fixes how two facts will always be joined. It cannot be themed. It cannot be dropped at a breakpoint without an `if`.

It is also invisible to anything that reads structure rather than pixels. A screen reader hears the dot as an extra word. The `no mechanism on screen` row, and this one, both have to parse through it, not around it.

D41 is the worked example of what removing it buys. It leaves a two-line stacked path with no seam at all. Once the parts are elements, not words in one string, there is nothing left to join.

Before this entry, nothing protected the pattern once D41 shipped. Only the one string was protected.

### The offender list, and why a cliff was refused

The sweep that removes the existing hits is a separate task, one screen at a time. A row that failed on every existing hit would be red the day it landed. That teaches a session to ignore red, rather than trust it. So the row names each existing hit in a shrinking list and fails on anything else (D280, offender lists replace pinned counts). A pinned count is refused: it passes a new dot when an old one leaves in the same change.

`scripts/typed-interpunct-allow.json` lists each offending string in each file, as `scripts/user-strings.mjs` extracts it. It is `make docs-audit`'s `typed interpunct` row, in `scripts/docs_audit/strings.py:check_typed_interpunct`. D18 forbids it writing, since it sits on the commit path. The row fails on three things:

- **A typed dot the list does not name**, by file and by string.
- **A stale entry.** A listed string that its file no longer holds shows the fix landed. The lane deletes the entry in the same commit.
- **Growth.** An entry that the list at the merge-base did not hold.

### What the reader can see, and what it cannot

The extraction is `scripts/user-strings.mjs`'s existing AST walk. It is the same one `no mechanism on screen` (D196) uses. This row runs it with two widenings, scoped to itself alone. `TYPED_INTERPUNCT_EXTRACT_ARGS`, in `scripts/docs_audit/strings.py`, passes `--join-literals --include-code-attr` to the script. D196's own fixtures, and its documented exemption, stay exactly as they were.

- **`--include-code-attr`** tracks `Notice`'s own `code` prop. D196 exempts this prop from its mechanism-naming policy on purpose. CLAUDE.md says the pipeline's own string stays available on hover and in the run log. This rule does not exempt it. A typed dot inside it still reaches a person, on hover and in the run log. That is the only fact this rule cares about.
- **`--join-literals`** reads the literal separator argument of any `<expr>.join(<literal>)` call. It reads the value wherever the call's return travels. That includes a local helper's parameter, or an object field read back by a different component. `whole(parts.join(' · '))` is one shape. `about: about.join(' · ')` is the other. Neither call is itself a JSX child, so the base walk misses both.

**What is still invisible, named rather than hidden behind a clean run:**

- A helper can build a separator without `.join`. It might use string concatenation into a `const`. It might return a template literal. Either way, if it is read elsewhere by reference, `{formatThing(x)}`, this walk cannot see it. `no mechanism on screen`'s own docstring names this same gap for itself. This rule narrows it by one call shape, and no further. Tracing it needs real data-flow analysis, which an AST alone does not carry.
- **CSS is never read.** The walk covers `.tsx` files only. A stylesheet that types a whole sentence into a `content:` property, such as `content: 'Parked · under the threshold'`, is a different, and worse, defect than a bare separator. D41's own CSS rules paint only `'·'`, nothing else. No widening of this extractor can see it, because `content:` never becomes a `.tsx` AST node. The sweep finds it by hand.
- **Server-side strings are a different language.** `pipeline/join.py`'s `Position.label`, `pooled_label`, `departed_label`, and `place_text` all still compose `' · '`-joined text. D41 keeps every one of them exactly as it is. They are the accessible name a screen reader announces. This entry's rule is that a CLIENT stops rendering them verbatim. It is not that the server stops emitting them. A Python string is not something this row, or `scripts/user-strings.mjs`, can or should reach.

### Governed by

D41 is the worked example this rule generalises. The address string's dot was removed, not restyled, and the separator moved into CSS.

D280 is why the row keeps a shrinking list of offenders and no pinned count.

D196 is the same extractor, `scripts/user-strings.mjs`, under the same discipline. A widened notion of "visible" stays off a rule that never asked for it. This row's two extractor flags stay off `no mechanism on screen`'s own call, by construction. D196's fixtures, and its `Notice`-`code` exemption, are untouched.

D18 is why the row in `scripts/docs_audit/strings.py` never writes.

D173 names the mechanism: `make docs-audit`'s `typed interpunct` row, cited by name in CLAUDE.md's Hard rules.

---
