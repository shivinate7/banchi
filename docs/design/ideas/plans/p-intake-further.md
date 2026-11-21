# p-intake-further

Skip the Sort is a full loop with the Worth-It Gate folded in. The part that makes it safe is the identification check: the printed card number, a free photo match and a gate-versus-price disagreement replace the sort-order check. The first version is unsorted capture plus that check, with the gate only reporting at first.

**1. Core loop: from "bought a shoebox" to listed and shelved**
1. **Open a lot.** The owner names it and enters what they paid and where it came from. The lot gets an empty intake box.
2. **Capture unsorted.** The owner feeds the shoebox to the rig in whatever order it arrived. Each card gets a box, section and position, as now.
3. **Gate, free and local.** From the capture photo, a cheap pass reads rarity mark, foil and set symbol. Each card is marked keep or bulk. No money is spent yet.
4. **Identify keepers only.** The paid identify step runs on keep cards in batches.
5. **Cross-check.** Each identification is tested against the card's own evidence (section 3 below). Disagreements go to review with the photo.
6. **Lot summary.** The owner clears the exceptions on one screen.
7. **List.** Identified keepers go out in the next listing file.
8. **Shelve.** Keepers are the minority, so the system prints a keeper pull list in capture order. The owner pulls those cards into a stock box, and the pull order becomes their new positions. Whatever is left in the intake box is the bulk bin, kept as one counted item.

**2. States**
- **Lot summary after capture.** Counts for captured, keep, bulk, identified and unidentified. Estimated value next to the price paid. Top 10 cards by value with photos. One "close lot" action, which stays blocked while an exception is open.
- **Bulk bin with spot-check.** A grid of bulk photos, least confident first. The owner skims a sample and taps "rescue" on a card the gate got wrong. The screen shows the rescue rate per lot, which is the gate's report card.
- **Duplicate-heavy lot.** Copies of the same card collapse into one row with a quantity and its positions. If the owner holds more copies than sell before the next season, the system offers to send the extra copies to bulk, with a sell-rate note.
- **A valuable card hiding in a lot.** When the gate said bulk but a free reference match or the price says high, the card goes to the top of the summary in a warning colour. It shows the photo and the exact position, with a "pull and sleeve now" step. A valuable card never waits in the bulk bin.
- **Optional re-home list.** This appears only when moving keepers into existing sorted boxes would shorten picking. Moves are grouped by destination box, and the list shows the minutes it would save. Skipping it is the default.
- **Unidentified cards.** Each shows its photo and position, with three choices: rescan, pick by hand from close candidates, or defer. The card is never guessed and never dropped. The rest of the lot lists without waiting for it.

**3. What replaces the sort-order check**
The sort-order check used a card's neighbours as a stand-in for "is this the card it says it is". Without an order, use the card's own evidence:
- **Printed number check.** A cheap text read of the collector number and set total, for example 045/198, must match what identify named. This is the main replacement, because the card prints its own position in its set.
- **Reference image match.** A free perceptual match between the capture photo and the catalog image of the named card. A low score goes to review.
- **Gate against price.** If the gate called a card bulk and the price says valuable, or the reverse, it goes to review. This same check catches the valuable card hiding in a lot.
- **Lot coherence, as a soft signal only.** One card from a set that appears nowhere else in the lot gets a light flag, never a block.

**4. Smallest first version**
- Unsorted lot mode in capture, with identify run on every card and no gate yet.
- The printed-number check, the lot summary and the unidentified list.
- Cards stay where they were captured, so the intake box becomes a stock box. No pull list and no re-home.
- **Shadow gate.** The gate scores every card but acts on none. The summary shows what it would have saved and which cards it would have sent to bulk wrongly. The gate starts acting only once the owner trusts its rescue rate.

**5. One measure**
Owner hands-on minutes per listed card, timed from opening the shoebox to the card being listed. Compare it with the same number for the current sort-first route.

**6. Questions for the owner (none blocking)**
1. Can the rig send a card to a second tray during a run? If so, bulk separates at capture at no extra cost and the keeper pull list goes away. The code or the rig itself may already answer this.
2. Where does bulk go: sold as count lots on TCGplayer, sold elsewhere, or kept? This decides whether the bulk bin needs only a count, or its contents as well.
3. Can a keeper box stay unsorted for good, with the Fulfiller picking by position only? Or must keepers end up in sorted boxes, which would make re-home required rather than optional?
