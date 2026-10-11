## D259 — Boxes show names only

**The owner's ruling: a box is labeled by its name, never by its number.** Box numbers are internal index values. The count of boxes may show. A box with no name gets count+1 as its default name.

So:

1. **A box is shown only by its name, everywhere.** That covers screens, place labels, departed labels, receipts and pickers. The box number and the `bid` stay inside the store.
2. **A count of boxes may show.** "5 boxes" is fine. "Box 4" as a label is not.
3. **A new box with no name gets a stored default name,** "Box" and the count plus one. It is a name, so it never renumbers. When that name is taken, the next free one is used. D20 (a box is an object) keeps names unique.

This overrides the earlier label that showed both a name and a number.

### The premises that no longer hold

**D145 (a box has an index nobody sees)** made `bid` the identity and left the number as a label: "every screen still says `Box 1`". The owner now rules that the label is the name alone. The number is one more internal value, like `bid`.

**D68 (a departed card's label names the record)** spells a departed card as `Box 3 · departed · B3 #96`. D92 (a bare `#` is the count, the key carries a sigil) gave the key its `B` sigil so that it reads apart from a count. Both put the box number on the screen.

### What each decision protected, and what protects it now

- **D145** protects a run and a buried card from a reused number. The `bid` does that, and it was never on the screen. Nothing changes there.
- **D20** protects a unique name for every box. The stored default name keeps that. A default name never moves, so a later box never takes an old box's label.
- **D68** protects a departed record that names itself, apart from any live card. The label reads the box name, the section and the card's number within the section, so the place stays. A visual mark, not the word "sold" or "departed", shows that the card has left. The store key leaves the screen. `join.departed_label` stays the one composer.
- **D92** protects one `#` per card on a screen. Section-relative numbers now carry their section in the same label (slug `a-card-is-counted-in-its-section`). The key sigil leaves the screen, so the collision it guarded cannot happen there.

### What must change

- Every server-composed place label uses the box name. `sayPlace()` in `app/src/position.ts` carries it to text and to accessible names.
- Every picker, rail, receipt and toast draws the name only.
- A box created with no name gets its default name at creation, in the store, not at render time.
- The existing boxes with no name get a one-time backfill, by the owner's ruling. Each gets the stored name "Box" and its number. Nothing visible changes, and the physical labels still match. The owner can rename any of them after. The backfill is a store write, so it previews first.

### What is still open

- How a departed card from a box that was later deleted names its box. The record keeps the name it had. The composer must not read the name from a registry row that is gone.
- **A moved card names the box it came from only while that box stands.** `CardHero.movedFromFact` resolves `card.moved_from` against the live box registry at render time. Delete the old box and the fact falls back to "another box". That is correct code over a fact the store never kept. A burial line freezes `box_name` when a box is deleted, but a move carries no such freeze. The real fix is a store change: capture the source's name at move time, beside `moved_from`, so the read is a stored fact and never a live join. That is a schema change. Filed here, not fixed.

### What is built

On the server:

- `pipeline/join.py:Position.label` reads `<box name>, Section <n>, Card <m>`. The card counts within its section. The parts are joined by a comma, so no separator dot is typed (D218). A caller with no registry gets `Box <number>`, which is the name the backfill stores.
- `join.departed_label` gives the same shape: the place the card left, with the number it would take going back (`Position.was_card`). The store key and the word `departed` leave the string. A screen draws the departure from `Place.slot` being null.
- `store/master.py:Inventory.ensure_box` stores `Box <count+1>` for a new box with no name, or the next free `Box <n>`.
- The backfill is a press that previews first:

  ```
  ./banchi boxes names            # preview: which box gets which name
  ./banchi boxes names --write    # one transaction; a second run changes nothing
  ```

- A cleared name stores the default name `Box <count+1>`, the next free one. It is never None, so no box falls back to a bare number. The box's own row is not counted, so a box that already carries its default keeps it. `count` is the number of OTHER boxes standing. `Inventory.default_box_name` holds the rule: its starting count, `len(self.boxes) + 1`, once counted the box being cleared. `set_name` calls `ensure_box` first, so the row is already in the registry when the default is computed. A lone box cleared stays `Box 1`.
- The backfill gives each unnamed box its own `Box <number>` where that name is free. Only then does it move the boxes that clash. A clash never pushes a later box off a free name.
- A server refusal that names a box says the box's name. A refusal that names a card also says its section and its card in the section, through `pipeline/join.py:said_place`. The store's own refusals use `store/master.py:Inventory.box_title`. Both read `store/numbers.py:box_title`. The error codes do not change.

T7's `check_box_names_and_place_labels` asserts the label, the departed place, the default name, the clear, the refusal wording and the backfill.

**Two departed copies at one place may look the same.** Two copies of one card that left from next to each other read the same place, because they left the same place. No date and no key tells them apart. The owner accepted this. Nothing on screen claims otherwise.

**Still open.** Two refusals still name a box by its number: `store/master.py:Inventory.box_disowns_run` (a box number deleted and used again after a run, so the number is the subject), and the server's "No box N" refusals for a box that does not exist (it has no name to say).
