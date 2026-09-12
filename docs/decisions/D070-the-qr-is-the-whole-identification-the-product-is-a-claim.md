## D70 — The QR is the whole identification, the product is a claim, and the card is destroyed

Ratified 2026-08-30, by measurement and by the owner's standing instruction that the physical
cards are disposed of. The code-card track's fork decisions carry the detail — **C9** (the
decode), **C10** (the product claim) and **C11** (disposal and the channel tier) — and
`docs/specs/code-cards.md` is the spec. This entry is the singles-side record of what changed
and what it costs, because three of the changes reach files the singles track owns.

**THE REDEMPTION CODE IS THE QR's PAYLOAD, SO IDENTIFICATION ON THIS TRACK IS FREE.** Confirmed
first-party by reading the official redeemer's own JavaScript bundle: it reads a `2d_code`
parameter and feeds the value straight into the redemption form. `codes/qr.py` decodes locally,
measured at the rig's real 3840x2160 frame size.
**140 of 140 physically-possible frames, zero mis-reads, 87 ms each.** Three cases are
unrecoverable — a QR under about 40 px, a 3.5 px
defocus, and glare that clips the symbol to white — and all three were established by ablation
against eleven transforms rather than assumed. Every one returns nothing.

**A MIS-READ IS FAR WORSE THAN A REFUSAL, AND THAT ASYMMETRY IS THE ARCHITECTURE.** A refusal
costs a re-shoot. A mis-read sells a stranger something that does not work, is discovered days
later, and lands in C6 with nobody able to say whether the code was bad or the read was. The
zero is therefore the number the harness asserts, not a rate.

**THE PRODUCT IS A CAPTURE CLAIM, IN D21's EXACT SENSE, AND IT RETIRES C2's OCR.** Code cards
arrive in sealed-product batches — a booster box yields 36 identical booster codes — so the
operator declares the product once per stack while the camera never has to read a SKU line.
`product` joins `game`, `set_hint`, `metadata_finish` and `rarity_claim` on `Card`, in
`CAPTURE_CLAIM_FIELDS`, in the sidecar and on the wire; `PUT /inventory/<box>/<index>` corrects
it like any other claim. **`None` is no claim and is never defaulted**, for D21's reason
verbatim: there is no ladder that infers a product, and a write-side default would make "the
operator said booster" and "nobody was asked" the same value on disk forever.

**OPENCV WAS DECLINED A SECOND TIME, AND THE FIRST REFUSAL STANDS.** This is the part worth
keeping, because the first pass got it wrong. `requirements.txt` had already declined
`opencv-python-headless` on a measurement about card SEGMENTATION. A first pass at the decoder
reversed that and took opencv for QR decoding — on a benchmark whose frames were at most
1600 px wide, **which is not this rig**: `app/src/useCamera.ts` asks for 3840x2160. Re-measured
at that size, opencv scored 72.7% at 211 ms.
**0 of 8 on a card filling a quarter of the frame, and 0 of 8 with glare** — against
`zxing-cpp`'s 100% at 67 ms. The 46 MB stays
unspent. **The lesson is not about opencv**: a benchmark at the wrong input size produced a
confident answer and the opposite of the right one, and nothing but re-running it at the rig's
real resolution would have caught that.

**THE DECODER PIN IS LOAD-BEARING.** This repo's venv is Python 3.9.6. The `zxing-cpp` 3.x line
dropped cp39 wheels, so an unpinned install resolves 3.1.1, finds no wheel, falls back to the
sdist and dies in CMake. `zxing-cpp==2.3.0` ships a real cp39 wheel. An unpinned requirement
here is a broken clone, not a newer decoder.

**THE LEDGER'S KEY IS THE CODE, WHICH CHANGES C8's FIRST BUILD.** That build upserted by
`(box, index)`, which was right for the job it was written for — C8's dispute lookup wants the
photograph, and the position names it. Under D24 the card is destroyed, so a position whose
card no longer exists is a filing reference and the code is the identity. Only a code key can
dedupe (C3's "free dedupe and structural protection against double-selling") and only a code
key can hold a reservation. The position survives as an attribute and C8's lookup is unchanged
— the code still lands on the record's `number`, so `GET /search` finds it, including on a
partial when a character is doubtful.

**DISPOSAL HAS A PRICE, AND IT IS RECORDED RATHER THAN DISCOVERED LATER.** D24 already ruled
that the cards are destroyed once the code is extracted, and the owner reaffirmed it. Research
on 2026-08-30 established what that forecloses:

- **TCGplayer, outright.** Its own policy permits code cards *attached to a physical card* and
  prohibits *"the sale of promo codes not attached to a physical card"*. No card, no
  TCGplayer — regardless of the 1,254 code-card SKUs in its catalog and regardless of this
  repo's entire join-and-emit pipeline pointing at it.
- **eBay's dispute defense.** The Money Back Guarantee excludes *"Digital content, Intangible
  goods"* and seller protection requires evidence of physical delivery.
- **Six consumer marketplaces**, by their own digital-goods bans.

**This overturns C5**, which specified shipping the physical cards precisely to buy that
protection. C5's mechanism is unavailable and what replaces it is channel choice plus C6's
replace-don't-refund. **Every researched channel came back MARGINAL** and the buy side is
actively closing; the operating rule that survives is C11's tier — a Pokemon Center ETB code
lists at roughly **46x** a booster, so the premium tail is listed individually and the bulk
floor goes out undifferentiated. `codes/products.py:is_premium` is that rule in code, and D9's
$0.40 threshold falls between the two populations, which it predicted three months early.

**NOTHING IS BUILT AGAINST A CHANNEL, ON PURPOSE.** C7's eBay Trading API call is still live
but is now deprecated in favor of a REST Message API. No channel has been executed even once,
so `#/codes` exports a list of codes and sends nothing anywhere. The cheapest experiment that
would settle the plan is one wholesale submission and one premium listing — a week's work that
replaces six marginal verdicts with two realised prices.

**REACHABLE FROM A SCREEN, WHICH IS THE HARD RULE AND NOT A FOLLOW-UP.** `#/codes` is the
eighth route: it reads a box's QRs, draws the two lanes, names every duplicate and every
unclaimed code, and commits a lane to a named order. The commit reserves permanently. The
capture screen grew the product picker in the same change, driven by `product_game` off
`GET /games` rather than by a game key written into the app.

**AMENDED 2026-08-30 BY THE OWNER: THE PILE IS SPLIT AND ONLY HALF IS DESTROYED.**
The premium code cards are KEPT physically, in a box, at tracked locations, and
will be shipped; the bulk tier is destroyed. That reverses one of this entry's own
conclusions, and the reversal is recorded rather than quietly edited.
**That sentence was true of a destroyed card and was written as though it covered the track.**
For the retained tier TCGplayer is open, and the existing `join -> emit ->
Import to Staged` path already reaches it unchanged.

**The owner also locked the channels: eBay and TCGplayer, nothing else.** The dedicated
buylist lane is closed by that ruling, which moots the $0.01-versus-$0.05 uncertainty this
entry's research left open. Lots are ~1,000 cards, shipped physically.

**THE BINDING CONSTRAINT IS ABSORPTION, NOT PRICE.**
At ~30,000 codes the pile is larger than the annual market on both venues: TCGplayer's bulk SKU absorbs 8,694 units a year across every
seller and already carries ~19,300 standing units, and the entire premium tier absorbs 924
units and $231 gross a year marketplace-wide against a pile holding roughly a year of it,
decaying at -25%/year. No pipeline change moves that number. It is why `codes/lots.py`'s most
valuable property is the guarantee a code is never committed twice across two concurrently
listed venues.

**A PHYSICAL LOT IS THE WHOLE BOX OR IT IS REFUSED.**
Both halves of that rule were found by reading generated output rather than by argument. Scoping a physical lot by COUNT commits
one thousand codes while the operator pulls a different thousand cards. Taking 1,000 of a box's
1,003 produces a correct ledger and a packing slip that lies. And the check that catches the
second has to ask what is PHYSICALLY IN THE BOX rather than what is sellable from it — a first
version asked the latter and so missed both an unclaimed code and a code already reserved to
another lot, the second of which would have been shipped to two buyers. That case was caught on
real data, not in a test.

**Still unsettled, and named rather than assumed.**
TCGplayer's bulk-lot listing needs the seller portal's Listings-with-Photos flow, which is a manual third-party UI step CLAUDE.md
forbids inside the pipeline AND asks for photographs of code cards the opsec rule forbids.
TCGplayer's own guidance permits backs and edges only, so it is reconcilable — the owner rules.
`docs/specs/code-cards.md` sections 6.1 and 9 carry the detail.

**CORRECTED 2026-08-30 AFTER THE OWNER CHALLENGED THE PHOTO CLAIM, AND HE WAS RIGHT.**
This entry recorded that TCGplayer's code-card bulk lot "cannot be listed by CSV" because bulk
lots need Listings with Photos. First-party API reads settle it otherwise. `productId 253512`
is an ORDINARY CATALOG PRODUCT — category 56, group 2303, rarity Code Card,
`sellerListable: true`, one SKU at `productConditionId 5274046` — and 26 of its 56 live
listings are `listingType: standard` carrying no image, no title and no description, holding
**28,936 of 31,493 standing units**. A CSV row produces exactly that artifact. The photo rule
is real policy and is not a mechanism, and 92% of the inventory on that SKU ignores it.

**The lane is CSV-listable and still not worth using**, which is the more useful finding. The
SKU's whole annual market is **8,694 units, about $299 of GMV**, against 31,493 units already
standing — some 3.6 years of demand queued ahead. Thirty thousand more cards take it to about
seven years.

**There is no lot structure there at all.** One SKU, priced per card, and the BUYER picks the
quantity; observed weekly sales run 1,425 / 1,100 / 975 / 734 / 700 / 558 units. So
`codes/lots.py`'s fixed-lot model is right for eBay and does NOT describe TCGplayer, and that
is recorded rather than papered over: the two venues want different shapes and only one is
built.

**Seller level gates it.** The item cap counts QUANTITY — Level 1 is 100 items, Level 2 is
500, Level 3 is 50,000, Level 4 unlimited — and Export Filtered CSV / Import to Staged is
**Level 4 only**, as is setting shipping to $0. The pipeline this repo emits is therefore a
Level 4 feature, and below that listing is UI work whatever it produces.

**The $1.49 shipping minimum fires only under a $5.00 product total**, verified across twelve
live listings. That is what makes a sub-$5 premium single net more than its own price, and it
is why a $40 bulk order carries no subsidy and the seller absorbs the postage.

---
