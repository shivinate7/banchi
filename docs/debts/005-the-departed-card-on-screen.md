## 5 — The departed card on screen

**Unblocked, two files, parallel with everything.** Both are D68's residue.

### ~~The copies list says the state twice on every departed row~~ — CLOSED 2026-09-05

**The Banchi rebuild closed this and nobody came back to say so.** `app/src/Inventory.tsx`'s
`Action` returns `primary || copy.state !== 'sold' ? <Pill>Sold</Pill> : null`, and the same
shape for `retired` — so a NON-primary copy whose state is already `sold` draws nothing, which
is exactly the departed row in the copies list. The comment above it states the reasoning:
a copy row's own state pill says the word once the re-read lands, so only the location card and
an optimistic sale still in flight draw one here. The per-call-site fix this item asked for is
what shipped, and the D57 ruling it was waiting on was answered by building it.

**The location card was the other site that sentence named, and D119 deleted it** (2026-09-07).
`primary` is now the phone action bar alone, which has no state pill beside it and so still
always draws one; the copy row is unchanged and still draws its second `Sold` only for an
optimistic sale in flight. The closure is unaffected — there is one call site fewer. What moved
into the row with the deletion is the RECEIPT, on a line of its own beneath it.

**The original entry is kept below** because its argument is still the reason the code is
shaped this way, and because a reader who greps for the duplication should find out where it
went rather than finding nothing.

### ~~The copies list says the state twice on every departed row~~ (the original entry)

Each departed row draws the word twice at 11px about 40px apart: `.card-locations-state` in
`app/src/CardLocations.tsx`, which is `copy.state` verbatim, and `app/src/Inventory.tsx:Action`'s
fallback, which prints the same word for the door the copy left by. **They can never disagree,
because the second is derived from the first** — `sold`/`sold`, `retired`/`retired` — which is
what makes it a duplication rather than two facts that coincide. Confirmed unchanged
2026-08-30.

**Why it is a question and not a wire.** The state span is the pipeline's own word on the
screen where grepping what you saw is worth a machine string. The action slot is D57's — it
becomes `Undo` for twenty seconds after a sale, and the word is the fallback. And `Action`'s
**other** call site, the lone-copy branch, has no state span beside it, so nulling the fallback
loses the fact on the 92% of the store with no group. The honest fix is per-call-site and it is
a D57 ruling. **The Fulfiller's skin already does the other thing** (`sold ? null :`), so the
two skins disagree today.

### ~~The component gallery has no departed case~~ — CLOSED 2026-09-05

`app/src/Gallery.tsx` now carries `DEPARTED` (`slot: null`) and `POOLED` (`located: false`)
fixtures and draws both in the copies group, and `app/tests/gallery.spec.ts` asserts the
departed row's classes, its single state pill and its empty action cell. Proven by mutation:
give `DEPARTED` a numeric slot and `isDeparted` goes false, the classes drop, the count goes
to zero.

**One clause of the original was wrong and is corrected rather than carried over.** It
described the departed rendering as "plain label, demoted store key, absent bar" — the absent
bar named code that no longer exists. The rendering is a plain label and a `.is-nobar` row.

**The general point stands and is not closed**: nothing checks that the gallery is COMPLETE.
Two cases were added because someone noticed they were missing; a third omission would be just
as invisible. A docs-audit row would be the wrong instrument — re-implementing `isDeparted` in
Python goes green against a fixture that renders nothing — so this stays a thing a person
notices.

### ~~The gallery drew the rows in a layout no screen produces~~ — CLOSED 2026-09-05

**Found by looking at the sheet at 390, which is the only way it could have been found.** The
two fixtures above were added and asserted, and both were drawn in the wrong shape.
`app/src/CardLocations.css` answers to `@container copies` in four places, and the widest is
not the interesting one: `(max-width: 619px)` is the entire narrow layout — the address on its
own line, the state and the action beneath it — which that file's own comment calls *"most of
the time, because the pane is one column of a three-column screen"*.

**`container-name: copies` was established in exactly one place in this app**, `Inventory.css`'s
`.inventory-detail`, the pane beside the photograph. `#/gallery` is not inside it, so all four
rules were dead on the sheet and the specimen drew the base grid at every width. At 390 the
address collapsed to one word a line and `ME01 commons` clipped to `M…`; the header's SKU line
truncated for the same reason. **The product cannot produce that shape at any width**, which
makes it the same defect the item above is about, one level down: the row was on the page, and
it was the wrong row.

`app/src/Gallery.tsx` wraps the owner specimen in `.kit-copies`, a `copies` query container
declared in `Gallery.css`. **Owner only, deliberately** — every `@container copies` rule is
scoped to `.card-locations-owner`, and the Fulfiller's skin establishes no such container in the
product either, so naming one on that specimen would invent a context that view does not have.

**Guarded, and observed red.** `app/tests/gallery.spec.ts` sets a 400px viewport and compares
the row's computed `grid-template-areas` against the narrow form. Comparing the resolved
cascade rather than asserting a class is the point: a class can be present while the rule that
reads it never matches, and that was the defect. Mutation: drop `container-name` from
`.kit-copies` and it reports `"place state action" "bar bar bar"` — the base grid — while the
four class-based cases beside it stay green, which is why they could not have caught this.

**What is NOT closed is the general form of it.** Nothing checks that a component rendered on
the sheet is rendered in a context resembling the one it ships in. `copies` was found because
someone looked; `pane` (`BoxBrowse.css`) and `pricing` (`Pricing.css`) are two more named
containers, and whether any specimen of theirs is on this sheet at all has not been asked.

### ~~One of the four `copies` bands cannot fire in the product, and it misses by four pixels~~ — CLOSED 2026-09-05

**Found while checking the fix above, and NOT fixed — the remedy is a design decision.**
`CardLocations.css:233` opens `@container copies (min-width: 760px)`, the widest layout, where
the position bar moves up into the row: `'place bar state action'`. Measured on this tree at
viewport widths of 1440, 1920 and 2560, `.inventory-detail` — the only element in this app that
establishes the `copies` container — is **608px, 756px and 756px**. It does not grow past 756
because the chain above it is fixed: `.bn-page` caps at 1600, `.browse-body` takes 1536 as
`300px + 1fr` with a 20px gap, and `.browse-band`'s `minmax(220px, 34%) minmax(0, 1fr)` leaves
the pane 756.164px at every width beyond that. **So that rule is unreachable, by four pixels,
at every viewport a person can open.**

The product's copies pane is in the NARROW band at 1440 (608px), which is the CSS comment's own
claim — *"most of the time, because the pane is one column of a three-column screen"* — measured
rather than asserted for the first time here.

**Three remedies, and the owner picked the third after seeing both layouts rendered.** The rule
is DELETED, and a comment carrying these measurements stands where it was.

**The renders are why, and they reversed the recommendation.** Forced to 820px the unreachable
layout squeezes the position bar into a narrow middle column between the address and the two
controls, with `#40 of 250 · 16% in` above it and `Section 2 · card 15 of 25 slots` below it, all
inside that column. The band that actually ships gives the bar the full width of the row. **The
design nobody had ever seen was the worse one**, so lowering the threshold would have put a
downgrade on screen at 1920 and up — which is what the first draft of this entry was leaning
toward before anyone looked. Deleting it loses nothing that was ever on screen and removes the
only breakpoint in that file with no measurement behind it.

**What a session must still NOT do is retune a number here quietly.** The three surviving bands
— 479, 619 and 470 — each carry their measurement in a comment, and the pane's 608-to-756 range
is now written down beside them.

---
