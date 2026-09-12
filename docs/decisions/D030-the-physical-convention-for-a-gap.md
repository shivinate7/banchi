## D30 — The physical convention for a gap

**Closed by D58 on 2026-08-30, and not by the marker this entry was waiting for.** The problem below is real and is stated better here than anywhere else in this file — *`Card 17` is the seventeenth slot, not the seventeenth card you can count* — and the answer turned out to be upstream of both halves: a card's number now counts the cards in the box, so selling one makes the card behind it take its number and every label stays countable by hand. There is no gap to put a marker in.

**The digital half stays built and is not deleted.** `neighbors` is still drawn and still worth having for confirming a slot.

**And the sentence about `section_gaps` was false the day it was written — the clause is now deleted outright (owner, 2026-08-30).** This paragraph read that the count "is structurally zero for a consolidated box and `placeSentence` already omits the phrase at zero, so the sentence quietly stops carrying a clause D58 made empty rather than needing a change". It is not zero. `server/capture_server.py:_company` counts the TERMINAL RECORDS between the section's bounds, so a box that has had a sale reports one per departed card — and the server's own comment beside it, *"it answers zero for a box where nothing has left"*, is true and describes the uninteresting case. **Measured on the owner's store: box 1 holds 133 records with 2 sold, so every card in it drew `· 2 slots in this section are empty`** — four times on one screen, since three copy rows and the card band each carry it.

**It had also stopped being TRUE, which is why deleting beats fixing the arithmetic.** Under D58 the box closes up over a departed card, so `Card 19` really is the nineteenth card a hand can count to. The clause's one stated job in this entry — *"the gap count says why the count came out short"* — is void, and a clause telling an operator their count will come up two short now sends them looking for slots the numbering has already absorbed.

**What it cost, measured before it went**: 15px on every copy row in any box that had ever had a sale, and it was the whole reason the line wrapped to three lines rather than one. It is gone from `server.ts:placeParts`, so it reaches no site — not the band, not the copy rows, and not the Fulfiller's card, which renders the joined sentence as visible text. `Place.section_gaps` stays on the wire and on the type, unread, because the field is a fact about the store and this is a ruling about a sentence.

**The physical half is void rather than answered**, which is why the owner never had to choose a marker: the retroactivity problem this entry names — *a convention adopted after fifty gaps exist cannot be applied to them* — is what made a marker unworkable, and it is exactly the problem a rendering does not have. Every existing gap closed the day D58 landed.

**The box audit is easier and still not built.** What is physically in a section and what the record says are the same count again, which is what that check compares.

**The neighbors are ranked rather than joined as of 2026-08-30, which is D41's move one line down.** The owner could not read the sentence this entry specifies: *"it's hard seeing galio and evelynn or between kha and poppy, maybe we make longer (y axis) for them?"*

**The cause is the catalog and not the length.** Every Riftbound name is `Champion, Epithet` — 494 of 1368 carry a comma and none carries two — so the composed sentence holds commas INSIDE names and connectives BETWEEN them, and **the strongest punctuation in the string is the one that is not a boundary**. It fires a median five characters in; the real boundary (`and`) is thirty characters later, so the reader parses grammar to find two proper nouns and then regresses left to recover where the first began.

**So the connectives are deleted rather than restyled, which is exactly what D41 already ruled for the address above it.** `after` and `before` become a muted mono key column, the two names start at one x, the champion carries the ink and the epithet demotes to muted. Finding the second name is a vertical saccade instead of a hunt for a word. `app/src/PlaceNeighbors.tsx` is the renderer and `server.ts:placeParts` is the composer.

**Setting the champions in bold inside the running sentence was the alternative, and it is the move D41 already declined.** It adds a cue on top of the parse instead of deleting the parse: having landed on `Galio`, the reader must still read the grammar to learn which side he is on.

**The keys are the composer's own two words, and that overruled the better-reading pair.** `in front` / `behind` was built first and renders better as a physical pair — and it takes the NEIGHBOR as its subject where `placeParts` takes THIS CARD, so a screen reader would have announced `before Conscription` over a row reading `BEHIND Conscription`. Two true framings of one fact, sixteen pixels apart, is the second-vocabulary drift D22 refuses for reason codes.

**One departure from D41: its payload got size and this one gets position.** Two thirty-character strings cannot take a 44px treatment, and D41's own amendment measured what that costs a list — 44px in the copies row is +86px and drops a copy below the fold.

**The owner kept both sites**, having first said the band's copy was repetitive. Offered the choice with the measurements, they chose to keep the band and the copy rows and restyle both. What that avoids is named here because it was nearly missed: `Inventory.tsx`'s lone-copy branch draws no copies row at all — its own comment puts that at 22% of the store — so a card with no name and no SKU has the band as its ONLY site, and deleting the band would have broken this entry for most of the boxes the owner walks.

**Measured at 1440x900 on box 1 card 19, the owner's own screenshot**: the copy row goes 173.2px to 177.5px, and the neighbor block from two or three lines of 10px uppercase tracked mono to two lines of 12px body. The row is +4px and its height is now CONSTANT, where it used to vary with how long two names happened to be — which is not a fact about the card.

**The Fulfiller is untouched and keeps the joined sentence**, at 20px body through `.card-locations-say`, which `app/tests/fulfillment.spec.ts` floors and D31 keeps unweakened. The firewall is the component graph rather than a selector prefix — `FulfillerCard` does not import the renderer — for the reason `PositionLabel` already records: a prefix is what a refactor drops and an import is not.

**Nothing had ever asserted any of this.** Every Playwright fixture passed `neighbors: null`, which is a real wire state the app draws as no block at all, and the four fixtures that tried to pin the gap count spelled it `gaps_in_section` — **a field that exists in no server, no type and no component** — so they set nothing and the behavior happened to match. Four cases now cover the vocabulary, the split, the single-neighbor end and the deleted clause. Three mutations were observed failing first, and the gap case had to be strengthened to earn its place: asserted against visible text alone it PASSED the re-added clause, because on this screen `said` only ever reaches an `aria-label` — it is the Fulfiller who renders that string as text.

**A hazard found and deliberately not fixed: `PlaceNeighbor.index` is the store key.** `_company` builds it from the allocator index while D58 made every drawn number a count of cards, so on a box with departures the two diverge — box 3 has 9 — and the `#41` a neighbor degrades to when nothing has identified it can name something that is not the slot a hand would count to. It is wrong exactly as it was before this change, and correcting it is a decision about what the server sends rather than about how a screen draws it.

---

The problem as it stood: D10 makes a sold position a permanent gap, and the Fulfiller creates one per order. Nothing has ever told him to leave anything behind in the slot, and nothing teaches anyone to read a position label. Once a section has holes, the slot number and the countable card number stop being the same, and every label in that section becomes uncountable by hand.

**This is retroactive, which is why it wanted settling before more sales happened.** Two halves, and only one was code:

- **Physical**: the operator leaves a marker in the slot a pulled card came out of. Which marker was the owner's call.
- **Digital, and free**: a position renders with its neighbors and its section's gap count — *Card 17, between Mantine and Thievul · 2 slots in this section are empty*. Neighbors make a label countable again without anyone learning the rule, and the gap count says why the count came out short.

**A box audit is the check that closes this loop** — count what is physically in section 2 and compare it to what the record says. Nothing has ever compared a physical box against the record, and D20's `box_fill` and `sections_for` are what make it computable.

---
