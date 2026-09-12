## D77 — The pipeline's rows can be the wrong card, so the export is reachable from every entry — asked for, never offered unasked

**Built 2026-08-31, and the owner found it the same way they found D46: by asking why the screen would not let them say what the card is.** *"How come in review queue there's no option to hand revise an answer? why do i only get to pick from your suggestions"* — over a screenshot of box 3 card 66.

**The entry in that screenshot is the whole argument, and it was the ONLY open entry in the store.** 152 queue entries across `review.json` and `parked.json`, 151 already cleared, one waiting — and that one could not be answered:

- read: `Nasus, Ascended`, number `8/298`, no set hint, rarity claim `Epic`;
- candidates: `Get Excited!` at `008/298` in Origins, Near Mint at $0.07 and Near Mint Foil at $0.29;
- photograph: Nasus, `046/166`, VEN;
- and the card's own row, in the same export the entry was joined against: **`9405493`, `Nasus, Ascended`, `046/166`, Near Mint Foil, Epic, $0.74.**

The number was misread, and `008/298` is a **real key** in that export belonging to a different card. So the join found rows, confidently, for something else. `rarity_claim_mismatch` is exactly the reason D23 built for this — its own comment calls it the one that catches "`051/197` for `031/197`, a CONFIDENT answer no confidence threshold fires on" — and it fired correctly. The screen then offered the operator the wrong card's two rows and nothing else.

**D46's guard was the right guard against the wrong question.** It let a human point at a catalog row only for an entry with **zero** candidates, on the reasoning that "a card the pipeline found rows for has its answer on screen already". That makes *the pipeline offered nothing* the test for whether a person may overrule it, and the test that was wanted is *the pipeline is wrong* — which is not a thing a queue entry can know about itself. The two coincided for as long as nobody looked at a card where they came apart.

**What is widened is which entries the flag reaches. What it checks is untouched.** `_answer_target` honours `from_catalog` for any entry now; every line of the guard beneath it is the same code:

- the SKU is re-read out of **this card's own export**, inside the write lock, via `_catalog_for_card`;
- the **condition comes off that row and never off the request**;
- a SKU the export does not carry refuses as `sku_not_in_catalog`.

So the property D46 protected — no string a client sends becomes a listing on its own — is unchanged, and it never depended on the candidate count. `GET /review/<box>/<index>/catalog` did not move at all: it was never gated, because searching an export the operator is already looking at was never worth refusing.

**The anti-laundering refusal stands where it always stood.** An answer that does **not** set `from_catalog` still may only name a row the pipeline offered, and still refuses as `sku_not_a_candidate`. What the flag buys is not permission to send any SKU; it is the claim *a human went and found this row*, and it is paid for by the server re-reading the row.

**D46's second argument is kept rather than overturned, and `looking` is the whole of the difference.** That entry refused to fetch a catalog beside a good list of rows: "a second, looser list beside a good one is how a screen teaches you to stop reading the first." True — and it is an argument about what is drawn **unasked**. Nothing changes on arrival at a card with rows: no fetch, no panel. The export appears only after `L`, and a list the operator pressed a key to see is one they have already decided the first list failed to answer.

**One list at a time, and that is a correctness rule rather than a layout preference.** Both lists are answered on digits, so a screen showing both would make `1` mean two rows. Opening the export **replaces** the pipeline's rows; Escape or `L` brings them back, writing nothing. The digit handler picks its list from `showCatalog` — the same flag the renderer branches on, read rather than re-derived. It read `candidates.length > 0` while the two lists could not coexist, and left as it was that is a **silent mis-write**: the operator sees the export's third row, presses `3`, and the entry's third row — a different card, which is why they went looking — lands on a real position with no refusal, because that SKU is a perfectly good candidate. Asserted as its own browser case.

**`from_catalog` on the history line stops carrying a second condition, and only now does it mean what its name says.** It was written as `from_catalog and not governing.candidates`. Under D46 those could not come apart, so the extra clause cost nothing; now it would omit the flag from precisely the answer that most needs it — the one where the pipeline had a confident offer and a human overruled it. After the write there is no other evidence which happened.

**The group route still does not pass the flag, and the REASON changed rather than the rule.** The old reason was arithmetic — a group is uniform over one shared candidate row, so a zero-candidate entry could never qualify. Widening retires that, so the real one has to be stated: a catalog row is found by a person looking at **one** photograph, and D29's group answer is a claim about a set of cards nobody is looking at individually. Applying a row found for card A to fifteen others is this guard's own failure mode arriving by the one door that skips the looking.

**`rarity_claim_mismatch` got a sentence, which it had never had.** `reasons.ts` gave it a chip label the day the reason shipped and `ReviewQueue.tsx`'s `sentence()` never got a case, so the screen drew *"a reason this screen has no sentence for"* over the one open entry in the store. It is the only reason the pipeline emits that can mean **the candidate rows themselves are the wrong card**, and nothing else on screen said so. It does not quote the claimed rarities: `QueueEntry` records the read and the candidates and not `rarity_claim`, which lives on `master.Card`, so naming them would need a schema change.

**Measured, on the card that produced this.** `_catalog_matches` run against that run's own export with the entry's read name returns **two** rows, correct one first: `9405493 · Nasus, Ascended · 046/166 · Near Mint Foil · $0.74`, then the alternate art at `046a/166 · $3.26`. The mechanism that fixes this card already worked; the only thing between the operator and it was `candidates.length === 0`. Answering the wrong offered row would have listed a $0.74 card at $0.29 under a different TCGplayer product.

**What would reopen this: `from_catalog` appearing on entries whose offered rows were right.** D46 named the same tripwire pointing the other way and it still holds — if the flag starts landing on cards a better join would have placed, the fix is upstream. This entry adds the near side of it: if the flag starts landing on entries **with** candidates at a rate that is not rare, the number read is the thing to fix, not the screen. Box 3's read is already the second measured instance of that (D55, 7 of 39 across three separators), and this is the third symptom of one defect.
