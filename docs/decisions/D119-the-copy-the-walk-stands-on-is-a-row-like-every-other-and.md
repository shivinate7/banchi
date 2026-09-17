## D119 — The copy the walk stands on is a row like every other, and the receipt lands where the sale was pressed

**Built 2026-09-07, on the owner's verdict about their own screen.** `#/inventory`'s card
detail drew the copy the walk was standing on **twice**, about 150px apart, in two different
registers: a `LOCATION` hero panel with a 40px address, its own position bar and a solid
`Mark sold`; and again as the first row of *Every copy of this card*, where its bar was
deliberately suppressed so the two lenses would not read as a rendering fault.

Their words: *"I actually really hate this new setup where it highlights the current card in
picture separately from the other copies. It's unintuitive. I want for Card 1 to have the exact
same layout as cards 36 and 91 below it, frankly the entire top right blurb box can be
deleted."*

**The code had already conceded it.** `Inventory.tsx`'s own comment called the duplication "the
trade", and what the trade bought was emphasis on a copy the UI elsewhere refuses to recommend
— `CardLocations.css` says the current row's rail is neutral "deliberately not *take this
one*". Emphasis nobody asked for, paid for in a second register.

### What the deletion is, and what it is not

`LocationCard` is gone. `noBar` drops its `current` term, so the copy the walk stands on draws
its bar like every other row; **`goesTo` keeps its `current` term** (D45 — a walk-to on the row
the walk already stands on goes nowhere). What marks that row is a `Viewing` pill in the cell
every other row uses for its own pills, and a neutral rail. **The pill and the rail were put to the owner and kept**: with no hero, they are the only thing tying the ~450px photograph on the
left to a row, and they change no part of the row's shape.

**Nothing the hero drew is lost.** The `Wanted` claim, the pooled marker, `Mark sold` and
`Retire` were already on every row; the box name moved from a separate element into the
address itself, as `PositionLabel`'s `boxNote` — which is what every other row has always
drawn. The missing-position-label `Notice` was **dropped rather than relocated**, and only
after checking it could fire: `do_inventory` omits the flat label and the `place` block
together, so that record arrives as `place === undefined`, which the lone-copy branch already
names by key.

### The card with no SKU and no name is a one-copy list, not a second panel

`GET /search` matches on SKU or name and refuses an empty query, so a card the pipeline has
never identified cannot be reached at all — that branch rendered the hero and a bare notice,
and deleting the hero would have left it an explanation with no address, no bar and no doors.
It builds the group instead: `Inventory.tsx:loneGroup`, shaped **field for field to be the answer `capture_server.py:do_search`'s own loose branch would have given** over a bag of one.
`listable` stays what the server would send and is **not** rewritten to 0 — the client does not
get to disagree with the store about a number the store computes. What changes is the
**sentence**: a group with no SKU draws no live figure and no `Pushed · Staged · headroom`
line, because `emit` has written no listing record and every one of those numbers is a
structural zero under a `Room for 1 more live` nothing can keep. Derived from `sku` rather than
passed as a prop, so it also reaches the 65 name-but-no-SKU cards already arriving through the
search path's loose bag.

**The measurement that decided the shape of this, and it corrects a stale one.**
`app/tests/inventory.spec.ts` carried *"629 of 682 records are captured-and-never-identified —
92% — … the branch 92% of the store draws through"*, and argued for coverage on it. Read out of
`inventory/store.sqlite` on 2026-09-07: **1,625 cards, 1,553 carrying a SKU, 65 with a name and no SKU, and 7 with neither** — four tenths of one percent. The figure was true when written,
against a store the pipeline had not yet run over. The branch is a real edge case and still
worth its case; what it is not is the common screen, and the spec's title and comment now say
the measured thing.

### The undo lands where the sale was pressed, and it fits the slot D118 reserved

A sale's undo — the draining twenty-second clock and the `Undo` — was the hero's alone; the row got a bare `Undo` with no clock. With the hero gone the row is where a sale is taken back, so the clock came with it (the owner: *"it'd be a shame to lose that animation work"*).

**What could not come with it is the panel, and D118 is why.** That entry reserved `.card-locations-action` at the button pair's own 137x28 precisely so a press cannot resize the slot it lands in. The kit's `.bn-receipt` is ~268px wide and 36px tall and fits neither way, and both were measured on this branch rather than reasoned about: **given a grid row of its own it grew the row from 175px to 213px on the press** — main's own stability case caught it by name — and put in the action cell it grows the cell and shoves the address, which `CardLocations.css` forbids against D40's 231px wrap point.

**So the row draws the clock and the button, at the size the buttons already were.** The sentence is not lost and is not duplicated: the state pill two cells to its left already reads `Sold`, and the toast this sale posted carries `Marked sold.` with the same clock and the same `Undo`. The drain's track is a **token** here where `kit.css` paints it as a white alpha — correct on an inverted panel, invisible on a row sitting on `--bn-surface`.

`primary` survives as a **size**, not a shape, and it is now exactly one thing: the phone's sticky action bar, which has no state pill beside it and so still draws the whole receipt.

**This is the second design this branch built for the receipt.** The first — a grid row under `:has(.bn-receipt)` — was written, looked at, and shipped nothing, because D118 landed on main while this branch was open and made it a defect. The measurement that killed it is recorded above rather than the design being quietly replaced.

### What was measured and refused

The right column loses roughly 235px flat: the hero's ~300px and its gap come out, and the
current row gains ~81px back from the bar it now draws. The photograph is unchanged. **No balance fix was taken.** Shrinking the photo column is what D32 and D38 spend the pixel budget
against — D38 *raised* it on the owner's own ask — and padding the void is the defect D40
measured at 41.99%. The visible consequence is a ragged bottom under a one-copy card at a pane
of 560px or more, which is the honest cost of removing content rather than a thing to fill.

### What D71 loses, and where it went instead

`.inventory-location-label` was one of `PositionLabel`'s site rules and **the last renderer in the product of `lead='path'` with a `.position-void`** — the combination its re-rank fires
under. The copies list, the order picker and the walk are all `lead='slot'`. Re-pointing that
assertion at the row would have compared 11px against 11px and passed for the wrong reason, so
it moved to `app/tests/gallery.spec.ts`, where the two specimens sit side by side and the kit
sheet is now the rule's only renderer. **D71 itself is not edited**: its "five sites" is a
2026-08-30 measurement, and measurements are not rewritten to match a later tree.

**Moving it found the sheet had never drawn the rule.** `.kit-poslabel` set `--pos-slot` without
the `font-size: var(--pos-slot)` every real site pairs with it, so the re-rank's `0.45em`
resolved against an inherited 14px and clamped to exactly the 11px a live path gets — the
departed specimen was drawn identically to the live one, on the page whose job is drawing the
difference. Fixed in `Gallery.css`, and now asserted.

### What is not weakened

`the copies of a card cannot be positioned by the pipeline console` guarded "the answer is above
the fold" against `.inventory-location`; the answer is the current ROW now, and it re-points.
`a copy row draws how far into the box AND how far into the section` counted **two** position
bars — one hero, one list — and the total is still two for a two-copy card, for an entirely
different reason; a total cannot tell "one per row" from "two on one row", so the claim is now
per row with the total asserted after it. Both were observed red under their mutations before
being kept, along with the two new gallery claims, the relocated re-rank, and the no-SKU list.

**One assertion was written and then removed for failing that test.** A `Walk to` count of zero
on the lone-copy branch stayed green when `onGoTo` was threaded onto it, because `OwnerRows`
suppresses the walk-to on the current row anyway and the lone copy is always the current one. It
is replaced by a comment saying so and pointing at the case that can fail: D45's real claim needs
a group with more than one copy in it.

**What would reopen this**: an operator who wants the address readable at arm's length while
standing at the boxes. That is the one thing the hero did that a 22px row does not, and it is
named here as the cost of the deletion rather than as a reason to keep a split hierarchy.

### Amended 2026-09-11 — the deletion was undone by a merge nobody read, and it is re-applied with a guard that lives outside the files it touched

**The hero came back three commits after it left, and stayed for four days.** `4bf5a44` (PR #218)
deleted it on 2026-09-07. `9439765` — PR #221, *"The cap is a ceiling on copies live"*, merged
2026-09-08 — was committed from a tree that still held the PRE-deletion copy of every file #218
had touched, and its single commit carried all of them back onto main under a message about
`--cap` wording: `Inventory.tsx` with `LocationCard`, `Inventory.css` with its rules,
`CardLocations.tsx` with the `current` term back in `noBar`, `Gallery.tsx` without the re-rank
specimen, both specs with the pre-deletion assertions, DEBT5 note, and
`docs/map.py`'s prose about all of it. `docs/DECISIONS.md` alone was not reverted — this entry
survived, and CLAUDE.md's index line for it — so for four days the record said deleted and the
tree said otherwise, which is the exact shape D16 is written against.

**Every guard the deletion had came back with the thing it guarded.** That is why nothing on the
commit path could catch it: `inventory.spec.ts`'s re-pointed cases and `gallery.spec.ts`'s
relocated re-rank were inside the revert that commit carried, so the suite that went green on 2026-09-08
was the pre-deletion suite asserting the pre-deletion screen. **And a session then ratified it.**
D132 (2026-09-11) found `LocationCard`, traced it to `9439765`, read the owner's screenshot of
the restored hero as evidence they were using it, and recorded *"it stays"*. The owner's next
question — *"didn't we have one that stopped making the first landing spot of a card be the main
header?"* — is what reopened it.

**Re-applied 2026-09-11, on the owner's word, as a three-way merge rather than a cherry-pick**:
base `9439765`, theirs `42e6d5a` (main as #218 left it), ours today's main — so D132's own work
on the same files (the sold fold, the name leading the address, the section name on the label)
is kept and the hero is not. Two fields the restored fixtures carried had left the wire in
between (`SearchGroup.cap`, D7 rewritten), and D132's seven cases that aimed at
`.inventory-location` now aim at `.card-locations-row.is-current`, which is where D132's own
address rendering already was for every other row.

**The guard is `make docs-audit`'s `recorded deletions` row, and it is deliberately not a Playwright case.**
A test that lives beside the component is reverted with it — measured above. The row is a
hand-written table in `scripts/docs-audit.py` (`RECORDED_DELETIONS`) of symbols a decision
records as deleted, checked against `app/src` on every commit; a merge that carries
`LocationCard` back fails the commit that carries it, in a file no screen change edits. Adding a
row to that table is how a deletion is declared meant to last; removing one, with the entry
amended, is how a deletion is deliberately undone.
**What it cannot see is a re-implementation under another name** — that is a design question,
and D16 leaves those to a reader.
