## D132 — Sold is folded away by default

**Settled 2026-09-10, on the owner's four asks about `#/inventory` and their three answers.** Their words were these. *"There is no point in me scrolling through them in positioning."* *"WB1 R1 is how i actually know it by."* *"Sort them by most recently clicked, followed by a secondary sort (tie-breaker) of quantity of cards."* *"I want Section 6 RARES rather than just section 6."* Every one of these is a screen answering to the person walking the boxes rather than to the store's own keys.

### What is built

1. **`Hide sold`, one chip on the walk's status bar, ticked by default.** The state is the route's (`Inventory.tsx`) so one press reaches both the walk (`BoxBrowse`) and the copies list (`CardLocations:OwnerRows`). Hidden, a sold or retired row is not drawn. The chip's count says how many. The copies list adds a line, `N sold copies hidden`.
   **Unticked, departed rows SINK under the live ones** within their own section in the walk. A sold card still belongs to the part of the box it sat in. In the copies panel they sink across the list. They never sit in place. The owner chose sinking over leaving them where they were.

   **The row the walk stands on is never folded away**, whatever its state. `selectedRow` is found in the visible list. A sale must leave its receipt where it was pressed (D118, D119). A walk-to from the copies list may land on a sold copy (D45). A just-sold copy in the copies list is kept for the same reason while its optimistic `soldKeys` overlay stands. The row goes the moment the walk steps off it.

   **The walk's sections are keyed by box and section number now**, not by their first row. With sold rows folded away, a section's first row could be a different record. That happened whenever its first card had left. Every fold then closed on the press. A section number survives a sale (D58's wire keeps `section` on a departed record) and survives the toggle.

   **`CardLocations` rule 1 is amended.** It read *"none is dropped for being far away, sold or spoken for"*. Sold is now the exception, on the owner's word. The comment says so.

2. **The address leads with the box's NAME.** `PositionLabel` takes `boxName`. The first path part's VALUE becomes the name (`BOX WB1 R1`), and the index moves into the note beside it (`Box 3`). The location card's corner used to say the name. It says `Box 3` now, and only when there is a name. An unnamed box already reads `BOX 3` in the address. The copies rows do the same (`boxName` in place of `boxNote`), on the owner's answer that the two panels should agree. **The server string is still never edited**: `aria-label` carries it verbatim. That is the property every spec asserts. It is the reason this is a rendering and not a write.

3. **The rail draws no box numbers and is ordered by the hand.** `.browse-boxcell-num` is gone. The name column already fell back to `Box N` for an unnamed box. Every cell's accessible name still says `Box N`. So nothing is lost to a screen reader or a locator. Boxes sort by **when this browser last opened them**, newest first. Then they sort by **cards on hand**, most first. The sort uses `on_hand` and not `cards`. A box full of sold records is not a box worth reaching for. "Quantity of cards" was read that way on purpose. Then they sort by number, the last thing the owner thinks in. The collapsed rail's 36px tiles draw the first word of the name, four characters at most. They draw the number only where there is no name.

   **Recency is device-local** — `banchi.inventory.box-recency` in `deviceMemory.ts`, put to the owner and chosen over a server field. It is `banchi.orders.last-check`'s kind of fact: when THIS device did something. The phone in the garage and the laptop at the desk are looking for different boxes. A store write for every press, for a sort order, would be D13's one truth carrying a habit. It is bumped from a rail press and from a walk-to, and **never from the `?box=` landing** — a page load must not reorder the rail. Capped at fifty. `banchi.inventory.hide-sold` is the other new key, the chip's memory. CLAUDE.md's roster says eight now. `make docs-audit`'s `storage keys` row holds it.

4. **A section can be named.** `store/master.py:Box.section_names` had existed since D83's move-cards work. It was keyed by the divider INDEX a section starts at, persisted in the box's JSON payload. Nothing read it, and only the demo seed wrote it. Now `PUT /boxes/<box>` takes `section_names` keyed by **ordinal**, the number every screen prints. `Inventory.set_section_names` joins ordinal to divider index. It does so the way `do_put_box` already maps a count-space layout to indices. An ordinal past the layout refuses as `section_unknown`; a blank clears. `sections_detail[].name` and every `place.section_name` are joined at read time. This follows D56's rule: never written into a run directory, so a rename reaches every label. The walk's headers read `Section 6 · Rares · #101–#153`. The bar's sentence reads `Section 6 · Rares · card 54 of 153 so far`. `PositionLabel` draws the name as a note on the `SECTION 6` part. The editor is a **Name sections** row in the Manage box sheet, one field per section. `section_named` carries both maps, by ordinal, for `set_name`'s reason.

   **The name rides the divider, and `set_sections` is where that is kept true.** Keyed by index, a divider nudged one card later would leave its name on an index no section starts at. T7 found exactly that on the first run. A layout with the SAME number of dividers is read as the same dividers moved. Every name goes with its divider. A layout that adds or drops one keeps names by exact index only. Nothing can say which new divider is "the same" one. A name on the wrong plastic is worse than a name lost with its layout on the `resectioned` line.

### What is recorded rather than re-litigated

**`LocationCard` existed in `Inventory.tsx` while this was built, and D119 says it was deleted.** This paragraph said, until 2026-09-11, that it *"stays, as the owner is using it"*. It read their screenshot of 2026-09-10 as a wish to keep it. That was wrong on the evidence. The screenshot showed it because `9439765` had put it back by accident. Nobody had asked for it back. The owner's ruling in D119 stood the whole time.
**The deletion is re-applied and D119 is amended with the account** (its final section). What this entry changed on the card survives on the copies row the walk stands on. That is the corner saying `Box 3` and the address leading with the name. D119 says the address is drawn there.

### Amended 2026-09-11: a search lands on the fullest section, and the index is said once

**Three corrections on the owner's first day with it, each on their word.**

**A search never lands on a sold copy.** Their screenshot: a search "pulled up a sold listing as the front runner" while copies were in stock. The walk kept the box it was on, because that box had *a* match, the sold one. It landed on the only row it had. The live copies were in the next box. Under a query a box now counts only if one of its matches is still on hand.

**The order is the largest quantity of the answer, by section.** Repeated back and confirmed: *"the largest quantity of whatever I searched by section is the order"*. The copies list groups by box and section. It draws the section holding the most live copies first. Within a section, the server's card order holds. The rail under a query ranks a box by its **fullest section**, not by its total. Three in one section outranks one-plus-two across two. So the rail, the list and the landing agree. A fresh answer moves the walk to the first live row of that section, in that box. A rail press under the same query lands in *that* box's fullest section. A copy sold from this screen still counts for its section while its receipt stands, so the press moves no row (D118). With nothing live anywhere the older rules stand.

**The index is said once on the location card.** `BOX WB1 R2  Box 4` beside a corner also saying `Box 4` was the same fact twice. `PositionLabel`'s `indexNote` is off there. The copies rows have no corner and keep the note.
**Overtaken the same day by D119's re-application**: the location card is deleted again. So there is no corner and no second saying of it. Every row keeps the note. `indexNote` is gone with its only caller.

### What is not built

Not built: server-side recency, a first-listed stamp, and name uniqueness for sections. A section is never addressed by its name the way a box is (D20 amended). The Fulfiller's screens are untouched. His list is his order, and his place labels are plain text. None of the four asks was about him.

**Amended 2026-09-29 (owner's word, A1).** Under a search, a tie on section density now breaks by the box's natural name, the same as the Orders walk. The no-search order is unchanged. `docs/specs/order-walk-plan.md` §17 states how each screen ranks a search.
