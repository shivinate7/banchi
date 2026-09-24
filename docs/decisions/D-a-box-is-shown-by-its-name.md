## D-a-box-is-shown-by-its-name — A box is shown only by its name, and a box with no name gets a stored default name

**The owner's ruling, 2026-09-23.** The owner's words:

```
I don't want to see "Box 4" part at all, those box numbers are arbitrary index values that
you get to keep on the back end, having a count of boxes is great, having each box labeled
with a number is not ok. If I choose to not name a box, it can default to count+1 Box as a
default name
```

So:

1. **A box is shown only by its name, everywhere.** That covers screens, place labels, departed
   labels, receipts and pickers. The box number and the `bid` stay inside the store.
2. **A count of boxes may show.** "5 boxes" is fine. "Box 4" as a label is not.
3. **A new box with no name gets a stored default name,** "Box" and the count plus one. It is a
   name, so it never renumbers. When that name is taken, the next free one is used. D20 (a box
   is an object) keeps names unique.

This overrides the orchestrator's earlier call on the box label ("Mixed Singles, Box 4"). The
record is `docs/reviews/ux-2026-09-23/`, file `RULINGS.md`.

### The premises that no longer hold

**D145 (a box has an index nobody sees)** made `bid` the identity and left the number as a
label: "every screen still says `Box 1`". The owner now rules that the label is the name alone.
The number is one more internal value, like `bid`.

**D68 (a departed card's label names the record)** spells a departed card as
`Box 3 · departed · B3 #96`. D92 (a bare `#` is the count, the key carries a sigil) gave the key
its `B` sigil so that it reads apart from a count. Both put the box number on the screen.

### What each decision protected, and what protects it now

- **D145** protects a run and a buried card from a reused number. The `bid` does that, and it
  was never on the screen. Nothing changes there.
- **D20** protects a unique name for every box. The stored default name keeps that. A default
  name never moves, so a later box never takes an old box's label.
- **D68** protects a departed record that names itself, apart from any live card. The owner
  ruled its new form. The label reads the box name, the section and the card's number within the
  section, so the place stays. A visual mark, not the word "sold" or "departed", shows that the
  card has left. The store key leaves the screen. `join.departed_label` stays the one composer.
- **D92** protects one `#` per card on a screen. Section-relative numbers now carry their section
  in the same label (slug `a-card-is-counted-in-its-section`). The key sigil leaves the screen,
  so the collision it guarded cannot happen there.

### What must change

- Every server-composed place label uses the box name. `sayPlace()` in `app/src/position.ts`
  carries it to text and to accessible names.
- Every picker, rail, receipt and toast draws the name only.
- A box created with no name gets its default name at creation, in the store, not at render
  time.
- The existing boxes with no name get a one-time backfill, by the owner's ruling. Each gets the
  stored name "Box" and its number today. So nothing visible changes, and the physical labels
  still match. The owner can rename any of them after. The backfill is a store write, so it
  previews first.

### What is still open

- How a departed card from a box that was later deleted names its box. The record keeps the
  name it had. The composer must not read the name from a registry row that is gone.

### What is built

BUILT in the locating lane, server half:

- `pipeline/join.py:Position.label` reads `<box name>, Section <n>, Card <m>`. The card counts
  within its section. The parts are joined by a comma, so no separator dot is typed (D218). A
  caller with no registry gets `Box <number>`, which is the name the backfill stores.
- `join.departed_label` gives the same shape: the place the card left, with the number it would
  take going back (`Position.was_card`). The store key and the word `departed` leave the
  string. A screen draws the departure from `Place.slot` being null.
- `store/master.py:Inventory.ensure_box` stores `Box <count+1>` for a new box with no name, or
  the next free `Box <n>`.
- The backfill is a press that previews first:

  ```
  ./pkmnscan boxes names            # preview: which box gets which name
  ./pkmnscan boxes names --write    # one transaction; a second run changes nothing
  ```

- A cleared name stores the default name `Box <count+1>`, the next free one. It is never
  None, so no box falls back to a bare number (the orchestrator's call on the locating review,
  2026-09-24). The box's own name does not count as taken, so a box that already has that
  default keeps it.
- The backfill gives each unnamed box its own `Box <number>` where that name is free, and
  only then moves the boxes that clash. A clash never pushes a later box off a free name.
- A server refusal that names a box or a card says the box's name, and for a card its section
  and card in the section, through `pipeline/join.py:said_place`. The store's own refusals use
  `store/master.py:Inventory.box_title`. Both read `store/numbers.py:box_title`. The error
  codes do not change.

T7's `check_box_names_and_place_labels` asserts the label, the departed place, the default
name, the clear, the refusal wording and the backfill.

**Two departed copies at one place may look the same (the owner's ruling, 2026-09-24).** Two
copies of one card that left from next to each other read the same place, because they left
the same place. The owner accepted this: no date and no key tell them apart. Nothing on screen
claims otherwise.

**Still open.** Two refusals still name a box by its number:
`store/master.py:Inventory.box_disowns_run` (a box number deleted and used again after a run,
so the number is the subject), and the server's "No box N" refusals for a box that does not
exist (it has no name to say).
