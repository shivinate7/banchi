# Code cards, end to end

**Status: the decode path and the ledger are BUILT. The channel decision is RECORDED and
unexecuted. Read section 8 before treating any number here as settled.**

**Dormant** (CLAUDE.md). `scripts/docs-audit.py`'s `views exposure` advisory stays OFF
(`VIEWS_EXPOSURE_ENABLED = False`), because no session draws pooled captures onto a screen.
Set the constant to `True` when code-card work resumes. `scripts/guard-opsec.sh` stays ARMED
regardless. It refuses a real code-card photo or code string in a commit.

The codes track runs from the operator putting a stack of code cards on the feeder to the
money arriving. It supersedes `code-card-fork/CLAUDE.md`'s architecture section. It amends C2,
C4 and C5 below. Each is named where it is overturned.

Every number is measured against `fixtures/pokemon_wide_export_untouched.csv`, measured on this
machine, or sourced from web research named in the text.

---

## 1. The chain

    operator loads a stack                the cards came out of ONE sealed product
      -> capture screen, game = pokemon_code, product picker, set hint
      -> POST /capture per card           photo + sidecar + record, exactly as singles
    ./banchi scan <capture-dir>         FREE. QR decode. NO model call. NO network.
      -> codes/qr.py                      100% of physically-readable frames, 0 mis-reads
      -> codes/ledger.py                  inventory/codes.jsonl, keyed by the CODE
      -> whatever QR refused              queued for the paid vision read, then a human
    #/codes                               the screen: what is held, what is dead, what sold
      -> export a channel file            a list of code strings, per channel
    disposal                              D24: the card is destroyed, the ledger survives

Two properties of the chain are the design. Both depart from the singles track.

**Identification costs nothing and calls nothing.** The redemption code is the QR's payload.
The field that must be exactly right is recovered arithmetically. The singles track's paid
Batch API call has no role on the primary path.

**The product is a claim, not a reading.** Set and product come from the operator at capture
time. Code cards arrive in sealed-product batches. See section 4.

---

## 2. What a code card is, verified

Verified against first-party sources. Two corrections to C1 and C3.

- **The QR payload is a redeem URL carrying the code in a `2d_code` parameter.** Confirmed by
  reading the official redeemer's JavaScript bundle. It reads `2d_code`, stores it, and feeds
  it into the redemption form. The parameter value is the code.
- **Correction to C1: it is a query string on `redeem.tcg.pokemon.com`.** C1 recorded a
  `#redeem` fragment on `tcg.pokemon.com`. That host now returns 404 for the redeem path. A
  fragment form still exists on a different redirect chain. `codes/qr.py` reads both.
- **The printed code is 13 characters, `XXX-XXXX-XXX-XXX`.** Read off The Pokemon Company's own
  sample card image. Three common community figures are wrong. Bulbapedia says 11 characters.
  One guide gives a 4-4-4-1 mask. A third-party parser validates 4-4-4-3.
- **The QR carries no set or product metadata.** The official client reads no other parameter.
  This negative evidence, not a decoded real card, is why section 4 exists.
- **Codes are globally single-use and do not expire.** Old PTCGO-branded cards still redeem in
  TCG Live with no cutoff. A redeemed card looks the same as an unredeemed one. The ledger is
  the only record of a code's state.
- **Correction to C3: redemption limits are soft.** Past the limit, a code grants a small amount
  of in-game currency instead of the product. It is not refused. Official figures: booster 400
  per expansion, Build & Battle 25, preconstructed deck 4, other products 4 (or 1 if only
  cosmetic). At most 10 codes per redemption batch.
- **Validity can be checked without consuming a code, but no usable API exists.** The official
  flow is two-phase. A `verify` step returns a per-code `validationStatus`. Only codes marked
  valid go to `redeem`. Every call carries a session cookie against an authenticated endpoint.
  Each call also passes a `can_redeem` gate. The redeem step requires a reCAPTCHA token too.
  Automated dead-code screening is therefore unavailable. Section 8 keeps it as the open question.

---

## 3. Decoding, and why there is no OCR

`codes/qr.py` carries the full measurement. In summary, at the rig's frame size of 3840x2160,
the shipped ladder reads **140 of 140 physically-possible frames with zero mis-reads at 87 ms
each**. It refuses the rest. Ablation against eleven transforms shows three cases are
unrecoverable: a QR under about 40 px, a 3.5 px defocus, and glare that clips the symbol to
white.

**The decoder is pinned, and the pin is load-bearing.** `codes/qr.py` uses `zxing-cpp==2.3.0`.
Plain `pip install zxing-cpp` fails on this repo's Python 3.9. Install from `requirements.txt`.
Never install freehand.

**C2's OCR half is not built, and should not be.** C2 specified a SKU crop taken off the QR as a
fiducial. Then Tesseract, with an `A-Z0-9` whitelist. Three findings retire it:

1. Measured: Apple's Vision OCR returned **confidence 1.0 on all 24 renders, 10 of them
   misreads**. It offered a single candidate every time. An OCR that is confidently wrong, with
   no alternative, cannot be an authority over a bearer instrument.
2. Tesseract's character whitelist does not work with its default LSTM engine. Its maintainers
   confirm this. The whitelist was the mitigation C2 relied on.
3. Section 4 answers the question OCR was for.

**A mis-read is worse than a refusal, and that asymmetry decides the architecture.** A refusal
costs a re-shoot. A mis-read sells a stranger something that does not work. It is found days
later and lands in C6's replace-not-refund. The operator then cannot tell whether the code or
the read was bad.

---

## 4. The product is a capture claim

**Code cards arrive in sealed-product batches.** A booster box yields 36 identical booster code
cards. An Elite Trainer Box yields one ETB code. The operator feeds a stack from one source. They
can see the box it came from. The camera cannot.

So the product joins `game`, `set_hint`, `metadata_finish` and `rarity_claim` as a **capture
claim** in D21's sense. It is client state, resent with every capture. It is written to the
record and the sidecar, and it is correctable afterwards on the card that got it wrong. One
picker replaces a fiducial crop, an OCR engine, a whitelist, a fuzzy matcher and a hand-built SKU
table. No public list of code-card SKU strings exists, official or community. A GitHub code
search for the two examples in the fork's own notes returns zero hits.

**What is given up:** a shuffled pile of unknown provenance cannot be sorted this way. The trade
is still right. A booster code is worth $0.03 and sells undifferentiated, so sorting those by set
earns nothing. Premium products arrive in ones and twos, and their product sets the price. They
are declared trivially. Where provenance is unknown, the paid vision read costs about $0.002 a
card. Spend it on a $1.39 code, never on a $0.03 one.

`codes/products.py` holds the vocabulary. It is derived from the catalog, not invented.

---

## 5. What a code is worth

### 5.1 TCGplayer catalog, from the real export

Read off the Near Mint rows of `fixtures/pokemon_wide_export_untouched.csv`. That is a real
Filtered Export scoped to four sets, with 51 distinct code-card products. **A catalog price, not a
realised sale.**

    pc_etb              1.19 - 1.50   median 1.39
    premium_collection  0.09 - 1.50   median 0.26
    etb                 0.09 - 2.00   median 0.16
    collection          0.04 - 0.99   median 0.09
    blister             0.04 - 0.15   median 0.08
    tin                 0.03 - 0.12   median 0.05
    booster             0.03 - 0.05   median 0.03

**A Pokemon Center ETB code lists at roughly 46x a booster code.** Boosters are the overwhelming
majority of any real pile. The pile's value is a long flat floor with a few tall spikes. The
fork's rule, "separate non-BST codes on sight", is confirmed by these numbers. D9's $0.40
threshold falls between the two populations.

### 5.2 What the market actually pays, from live sources

    acquisition, physical bulk on eBay        $0.020 - $0.040 per code
    published wholesale bid, booster          $0.01          <- BELOW acquisition
    published wholesale bid, premium SKUs     $0.10 - $1.00
    dedicated-shop retail, current sets       $0.38 - $0.43
    dedicated-shop retail, older sets         $0.08 - $0.20
    eBay digital 100-lot                      $0.056 - $0.130
    eBay 5-lot                                $0.142

**Recency beats chase status.** Retail spread from newest to oldest is 4.9x. Prismatic
Evolutions, the most hyped physical set of the era, sits near the bottom at $0.09. Buyers pay
for a set still in print and standard-legal in TCG Live. **This is a decay curve. Inventory
must move, not be held.**

**Product type beats set.** A Build & Battle code is about 5x a booster from the same set. The
gap widens to 15x for older sets. Deck codes run 10x to 200x a booster.

---

## 6. Channels, and what destroying the card costs

Six channel families were researched independently. **Every one returned MARGINAL.** This is the
headline. It is not softened here.

| channel | digital delivery? | verdict |
|---|---|---|
| Dedicated buylist (paste a list) | yes, by design | the only lane that fits, at wholesale prices |
| Own storefront | yes | best margin, all the customer acquisition |
| eBay, digital delivery | yes, in practice | real volume, **zero dispute protection** |
| TCGplayer | **no — policy** | **foreclosed**, see below |
| Etsy / Gameflip / Kinguin | yes | permitted, effectively no buyers |
| Whatnot / Mercari / FB / Amazon | **no — policy** | foreclosed |

### 6.1 Destroying the card forecloses three things, conditionally

**Owner ruling (amended).** The owner ruled that PREMIUM code cards are held physically. They
sit in a box at tracked locations, and they are shipped. Only the BULK tier is destroyed. The
points below hold **of a destroyed card and of nothing else.**

The consequences of the split:

- **TCGplayer is open for the retained premium tier.** The existing `join -> emit -> Import to
  Staged` path reaches it. The fixture export holds 263 code-card rows, with five conditions
  each. The 16-column schema is byte-identical to singles.
- **TCGplayer's bulk lane is open and CSV-listable, but economically dead.** All three hold.

  **It is an ordinary catalog product.** `productId 253512`, category 56 "Bulk Lots", group 2303
  "Pokemon Bulk Card Lots", rarity "Code Card", `sellerListable: true`. It has exactly ONE SKU,
  `productConditionId 5274046`, condition "Unopened". The export's `TCGplayer Id` column carries
  that id, so a CSV row for it is an ordinary row.

  **Photos are policy, not a mechanism.** TCGplayer's Bulk Lots FAQ says "Do Bulk Lots need to be
  added as Listings with Photos? **Yes.**" Of 56 live listings, **26 are `listingType: standard`
  with zero images, zero title and zero description.** They hold 28,936 of the 31,493 standing
  units, which is 92%. A CSV row produces exactly a standard listing. So "cannot be listed by
  CSV" was wrong. What is true: 92% of this SKU's inventory breaks a stated rule with no visible
  consequence. That is a risk to weigh. It is not a mechanism to route around.

  **A standard listing has no title and no description.** The CSV path therefore commits you to
  physical shipment. The listing offers no way to say otherwise. There is no "1,000-card lot"
  structure. One SKU is priced per card, and **the buyer chooses the quantity**. Real weekly sales
  run 1,425 / 1,100 / 975 / 734 / 700 / 558 units. This is a commodity listing, not a lot.

  **It cannot absorb the pile.** The SKU's entire annual market across all 56 sellers is **8,694
  units, about $299 of gross merchandise value a year**. **31,493 units already stand, roughly
  3.6 years of demand.** Adding 30,000 takes it to about seven years. The lane works, and it is
  not worth using at this scale.
- **eBay's dispute defense is restored for anything shipped, and only for Item Not Received.** It
  does nothing for Item Not As Described, the dispute code cards actually attract.
- **The hybrid, shipping the cards AND messaging the codes, is the worst case.** The buyer redeems
  from the message, files INAD, and returns worthless redeemed cards. Zero of six high-feedback
  specialists examined do this.

### 6.1a The binding constraint is ABSORPTION, not price or postage

The owner's pile is **~30,000 codes**. Measured against that:

- TCGplayer's bulk SKU absorbs **8,694 units a year across every seller combined, about $299 of
  GMV**. It carries **31,493 standing units across 56 listings**, re-counted first-hand. The pile
  alone is roughly **3.5 years of total market demand**. It queues behind **3.6 years** of
  existing supply.
- The best eBay 1,000-lot comparable sold **twice, lifetime**.
- The entire PREMIUM tier absorbs **924 units and $231 gross a year, marketplace-wide**. At a 3%
  premium fraction, the pile holds ~900 premium codes. That is about a year of the whole market's
  appetite. They decay at a measured **-25% a year**.

**Nothing in the pipeline moves that number.** The lot builder's most valuable property is the
guarantee that a code is never committed twice across two concurrently listed venues. Expect a
multi-year tail at clearing prices, not a liquidation.

### 6.1b Lot size and mixing, settled by measurement

- **1,000 cards is the postage optimum.** $9.70 Ground Advantage is **$0.0097 a code**. At 50
  cards it is **$0.100-$0.168 a code**, because the eBay Standard Envelope cliff hits on weight
  and thickness. No good lot size exists between 16 and ~250.
- **15 cards is the eSE optimum** at $0.78, or $0.052 a code. 20 is the absolute ceiling on
  thickness.
- **Mixing costs nothing at scale.** The mixed-versus-named discount is ~80% at 5-count, 62% at
  single-code retail, ~11% at 24-30, and **~0% by 50+**. Bulk lots need no set sorting. Mixing
  destroys value only on small lots and singles, where the premium codes are.

### 6.1c The original list, which still holds for a DESTROYED card

1. **TCGplayer is foreclosed outright.** Its help article permits code cards *"attached to a
   physical card"*. It states that *"the sale of promo codes not attached to a physical card is
   prohibited."* No physical card, no TCGplayer. This holds regardless of the 1,254
   code-card SKUs in its catalog.
2. **eBay dispute defense is foreclosed.** eBay's Money Back Guarantee explicitly excludes
   *"Digital content, Intangible goods"*. Seller protection requires evidence of physical
   delivery. Every digital-delivery dispute is a guaranteed loss plus a dispute fee.
3. **Six consumer marketplaces are foreclosed** by their own digital-goods bans.

**This overturns C5.** C5 specified shipping the physical cards to buy the protection above. Its
mechanism is unavailable under D24. The protection cannot be replaced on eBay. Channel choice
replaces it: a buylist or an own storefront, with no marketplace dispute machinery to lose to. C6's
replace-not-refund costs pennies. It is the only defense left.

### 6.2 The economics, unsoftened

The best-performing code listing found anywhere on eBay has 7,201 lifetime orders. It sold 41 in
one day. It nets roughly **$4,728 a year**. That is the ceiling of a well-run operation on the
single best listing in the category. It lives at 1x-5x lot sizes. There, **the $0.30 per-order fee
is 42% of a $0.71 order, and eBay's total take is 55.5%**. Bulk lots, the only automatable size,
barely move. The 100x, 50x and 1000x lots measured 16, 30 and 9 lifetime sales.

**Demand and automatability point in opposite directions.** This is the central finding. Volume
lives where delivery is manual. Automation lives where nothing sells.

The buy side is closing. The largest dedicated shop has **shut its buylist** and cut payout to
store credit. A second shop buys only two premium product types and **no booster codes at all**.
Its own stock counts show 500 to 1,350 units standing per set. This is a supply glut, not a
demand shortage.

### 6.3 The recommendation

**Tier the pile and run two lanes.** `codes/products.py:is_premium` exists for this.

- **Premium codes** (pc_etb, etb, premium_collection, the $0.99 to $2.00 population) are worth
  listing individually on an own storefront, or as named single-product lots. These are the
  spikes. They justify per-card attention.
- **Booster and bulk codes** go out in one undifferentiated wholesale submission. They are worth
  $0.01 to $0.13. No amount of sorting changes that.

**Do not build delivery automation yet.** C7's eBay Trading API call is still live, but it is
**deprecated**. A REST Message API replaces it. Building against either is premature while the
channel decision is unexecuted. Section 8 names the experiment that would settle it.

---

## 7. Storage

`codes/ledger.py` carries the argument. In brief:

- **The key is the code**, not the position. C3 asked for this. C8's first build used the
  position. Under D24 the card is destroyed. The position is therefore a filing reference, and
  the code is the identity. That makes dedupe and reservation possible.
- **Codes are fungible pool inventory, not located items** (D24). There is no box, no section and
  no position. The code string is the primary key. Do not reuse the singles schema.
- **`inventory/codes.jsonl`, gitignored.** A ledger of unredeemed codes is a file of bearer
  instruments. The runtime writes into a gitignored file. That is the sanctioned path. The commit
  guards protect the repository, not the store.
- **States belong to the code, not the card**: `held`, `reserved`, `delivered`, `dead`. Under D24
  a card can be destroyed while its code is still `held` and saleable. Conflating the two would
  make disposal look like losing the asset.
- **Reservation is all-or-nothing, and it refuses anything not `held`.** Double-selling is
  unrecoverable, so the refusal is loud, not a no-op.
- **The ledger is one file, parsed in full on every request.** It breaks past about 100,000 code
  entries. That is a different axis from the singles card count. Measure it when a real code card
  runs through it, not before.
- **A duplicate is recorded, never resolved.** A code read at two positions is either one card
  photographed twice, or two cards bearing one code. A human decides with both photographs. A rule
  would be wrong half the time.

---

## 8. What is NOT settled

Named rather than buried. None of it blocks the build.

1. **No real code card has been through this pipeline.** Every decode number is synthetic. The
   first real stack is the measurement that matters. It may find a layout, a glare pattern or a
   print run that nothing here anticipates.
2. **The dead-code rate is unknown.** Bulk lots are sold "unused" and cannot be verified. There is
   no automated way to screen them, and no source publishes a rate. Price bulk assuming a loss.
   Measure it on the first batch.
3. **No channel has been executed.** Every price above is an ask or a catalog figure, except where
   a sold count is cited. The cheapest experiment that would settle the plan has two parts. Submit
   one wholesale batch of a few hundred booster codes to a buylist that accepts a pasted list. List
   one premium code on a storefront. A week's work replaces six MARGINAL verdicts with two
   realised prices.
4. **Buylist counterparty risk is real and unquantified.** The one app that accepts a pasted list
   of codes rates 2.3 to 3.1 stars, with recurring non-payment complaints. Submit a small batch
   first.
5. **The redemption limits are TPCi's published figures.** This repo has not re-verified them
   against a current source.
6. **The SKU suffix vocabulary is undetermined.** Only `BST` was ever observed. This costs nothing
   while section 4 stands. It would matter if OCR were revisited.
7. **Whether the code string itself encodes the product is unverified, either way.** If it does,
   section 4's picker is unnecessary. It is worth ten minutes against the first real batch.
8. **`#/codes` names a card by its stored index, and D196 stays open on it.** A review found
   `Codes.tsx` printing `slot {index}` on screen, in the dup-positions list and the Position
   column. That is the ledger's own row number. D196 bans a user-visible string that names a
   pipeline-internal noun. D24 already hides this number from a card's identity, for the reason
   D58 hides a singles card's stored index. No fix landed. Codes carry no section-relative number
   the way a located singles card does (D260). Nothing today can stand in its place. The owner
   ruled: leave it as a known gap until the dormant feature wakes.

---

## 9. Lots

`codes/lots.py` builds them. A human builds them on `#/codes`. Two rules carry the design. Both
were found by reading generated output, not by reasoning.

**A PHYSICAL LOT IS SCOPED TO A BOX.** The obvious shape is "reserve any 1,000 sellable bulk
codes". That commits codes A through J. Meanwhile the operator, standing at a shelf, grabs a
different thousand cards. The buyer receives cardboard whose codes were never committed to them,
and the ledger is confidently wrong about both. No packing discipline fixes this. The cards are
indistinguishable by eye. A count-scoped lot is legal only for a DIGITAL sale, where nothing is
pulled.

**A PHYSICAL LOT TAKES THE WHOLE BOX, OR IT IS REFUSED.** A lot that takes 1,000 of a box's 1,003
cards produces a correct ledger. It also produces a packing slip reading "Box 12, 1000 card(s)".
The operator holds that slip and that box, and ships 1,003. Two of those three strays list at
roughly 46x a booster. "Pull all of them except these three" is not an instruction anyone executes
reliably against a thousand identical pieces of cardboard. So it is not offered. `plan` refuses and
names the strays by index.

**That check asks what is PHYSICALLY IN THE BOX, not what is sellable from it.** A first version
missed two classes of card. The first is a code with no product claim. Every lot filter drops it on
purpose. The second is a code **already reserved to another lot**, which would ship to two buyers.
Only `delivered` shows that the cardboard has left. The second class was caught on real data. Two
cards in a demo box were already committed to an earlier order, and they would have gone out twice.

**Three artifacts, because three different people read them.** `listing.txt` is for the seller,
once. `manifest.txt` is for the BUYER: one code per line and nothing else, because it is pasted
whole. `packing.txt` is for the operator at the shelf. The manifest is **never returned inline by
the route**. A thousand live codes in a JSON response land in every devtools network tab and in any
screenshot that catches it. The screen links to the file instead.

`lots/` is gitignored for `inventory/`'s reason, and for no weaker one.

---

## 10. Seller level gates the whole TCGplayer plan

Measured from TCGplayer's own help articles. **The item cap counts QUANTITY, not distinct
products.** That is what makes it bite here:

    Level 1     100 items        30,000 units is impossible
    Level 2     500 items        still impossible
    Level 3     50,000 items     one listing of 30,000 fits
    Level 4     unlimited        and the ONLY level with Export Filtered CSV / Import to
                                 Staged, and the only one that may set shipping to $0

**So the CSV path this repo already emits is a Level 4 feature.** Below that, listing is UI work,
whatever the pipeline can produce. The owner's seller level is not recorded here. It decides which
of these paragraphs applies.

**The $1.49 shipping minimum fires only under a $5.00 product total.** Verified against twelve live
listings. A $0.02 item with a $0.00 seller rate still charges the buyer $1.49. A $9.00 item with a
$0.00 seller rate charges $0.00. This cuts both ways. It is what makes a sub-$5 PREMIUM single net
more than its own price. It is also why a $40 bulk order carries no shipping subsidy, and the seller
pays the postage.

Tracking is advised over $20. It is **mandatory over $49.99**. Signature is advised over $250.
Enforcement runs by dispute forfeiture, not a hard block.

---

The settled decisions of the codes track, C1 to C11, follow. Sections 1 to 10 amend C2, C4 and C5.
Each amendment is named where it is overturned. A `C<n>` citation resolves to the `## C<n>` heading
below.

## C1 — Card anatomy, verified on physical cards

The face side carries everything needed. Single-sided capture, no flipping.

- **QR code** decodes to `https://tcg.pokemon.com/en-us/tcgl/#redeem?2d_code=<CODE>`. The payload is
  the code only, with no set or product metadata.
- **Printed code**, format `XXX-XXXX-XXX-XXX`.
- **Product SKU** printed directly above the code: `EN` + set code + product suffix. Observed:
  `ENME1BST` (Mega Evolution booster), `ENSV8P5BST` (Prismatic Evolutions booster). This is the
  identification key.
- **Plain-English name line** at the bottom ("Scarlet & Violet—Prismatic Evolutions"). It is a
  secondary cross-check only. Em-dashes and spaces make it a worse OCR target.
- **Reverse art is useless.** Five randomized designs, set-independent, across the whole modern
  range.

## C2 — Identification architecture

**SUPERSEDED IN PART. Steps 1 and 2 stand. Steps 3, 4 and 5 are retired.** The QR decode is built
and is the primary path. The OCR half (SKU crop, Tesseract, fuzzy match against a hand-built SKU
table) is NOT built, and should not be. See C9. The cost argument below still holds. It is stronger
now, because the primary path costs nothing.

1. Decode QR locally. Deterministic, and it doubles as an "in frame and readable" check.
2. Use the QR as a fiducial. Its four corners give scale, rotation and perspective for free. Crop the
   SKU relative to the QR bounding box.
3. OCR the crop, `A-Z0-9` whitelist, Tesseract.
4. Fuzzy-match against the SKU table to get set and product type.
5. Low confidence: cross-check the English name line.
6. No match: review queue.

**The SKU table is built empirically.** Scan a few dozen cards across eras. Dump the unrecognized
strings. Map them by hand, once. A couple hundred entries cover everything. Haiku is the fallback for
unknown SKUs only. It has the same shape as the singles variant ladder.

On the primary path the cost is effectively zero. Haiku on every card would cost ~$0.002 a card. That
is 1–2% of a code's retail value. It is tolerable, but unnecessary.

## C3 — Data model

**AMENDED (C9): the redemption limits below are SOFT, not hard caps.** Past a limit, a code grants a
small amount of in-game currency instead of the product. It is not refused. The figures are otherwise
confirmed against the official FAQ.

Fungible pool inventory. The code string is the natural primary key. That gives free dedupe and
structural protection against double-selling. Atomic dequeue on order assignment.

Per-code audit trail: source, `scanned_at`, capture photo, SKU, `order_id`, buyer, `delivered_at`.

Product type matters as much as set. Redemption limits: booster 400, Build & Battle 25, precon deck 4,
other products 4 (or 1 if only cosmetic). `BST` will dominate the pile. Non-`BST` codes are the scarce,
high-value ones, and they must be separated out.

## C4 — Sales: eBay bulk lots, sorted by set

25x / 50x / 100x. Single-code and 5-for-$1 lots are negative margin once eBay's ~13% plus per-order fee
applies. Mystery mixed lots sell at a real discount. That discount is the entire justification for the
SKU OCR work.

## C5 — Ship the physical cards AND message the codes instantly

**OVERTURNED by C11.** Its mechanism is unavailable. D24 disposes of the physical cards, so there is
nothing to ship. The problem it identified is real, and its solution is gone. C11 says what replaces
it. The analysis below stays, because the risk it names is the risk the track now carries unmitigated.

Pure digital delivery has no seller protection. eBay requires carrier tracking with delivery
confirmation for an item-not-received defense. So a buyer can redeem 100 codes, file INR, and win
automatically. At 100-count lots, $1.50–4 postage against a $15–25 sale converts an unprotected digital
sale into a protected physical one. It also sidesteps the electronically-delivered-goods approval
question entirely.

Listing copy states plainly: physical cards shipped, codes messaged instantly, no returns.

## C6 — Dispute policy: replace, not refund

It costs pennies and protects feedback.

## C7 — Automation, gated on singles Gate B

`ORDER.CREATED` webhook → dequeue N codes → Trading API `AddMemberMessageAAQToPartner` (75 calls per
60s, 90-day order window; no REST equivalent exists) → mark shipped → decrement listing quantity.

Until Gate B passes: manual listing and semi-manual code delivery. Cash flow can start there.

---

## Open questions

- **CODES-A — vintage SKU geometry.** Pre-TCG-Live (green PTCGO-era) cards may not carry the SKU in the
  same format or position. Verify before assuming the fiducial offset holds across the whole pile.
- **CODES-B — SKU table coverage.** Build the mapping table. Confirm coverage against actual inventory.
- Confirm eBay account standing. Confirm whether digital-goods approval is needed, even under the
  ship-physical model.
- Codes cannot be validated without redeeming them. Codes from our own sealed product are safe. Price
  anything acquired in bulk assuming a dead percentage.
- Resale of codes is a gray zone. Nothing in TPCi's terms formally authorizes redistribution. The market
  is large and openly tolerated. Read the terms.

## Why codes goes first

Small track: QR decode, SKU OCR, codes table, eBay lot listings, delivery worker. It rides the shared
foundation and serves as the feeder's shakedown cruise. Failure costs little, since a misread QR fails to
decode rather than mispricing a $40 card.

## C8 — The code ledger: every code's text beside its photograph, for the dispute that will come

Ratified by the owner. Code cards sit in an arbitrary box, ideally sorted by set. The owner ruled that
both the code card image and an image-to-text CSV are saved. If a customer says a code did not work, the
code is checked against its image. The likely cause is an image-to-text error.

**The dispute flow is the spec.** A buyer says a code did not work. The owner checks the code, opens the
photograph it was read from, and re-reads it by eye. The likeliest failure is the image-to-text step. C6
already rules the remedy: replace, not refund. Everything below exists to make that lookup two taps.

**The mechanism rides what the singles track already built.** `pokemon_code` gets a real prompt profile.
Its job is transcription: the printed code, exactly as printed. The extracted code lands on the card
record, the way every identification does. The existing search then finds it with zero new UI. Type the
code, get the card, tap the photo. The ledger file is the fork's export: code text keyed to box/index and
photo path.

**A LEDGER OF UNREDEEMED CODES IS A FILE OF BEARER INSTRUMENTS.** That sentence decides its storage. It
lives under the store beside `inventory.json`. It is gitignored like everything there, and it never enters
a commit. The commit-time opsec rules and the re-enabled PreToolUse guard both fire on a code literal. A file
like this must never cross them. The runtime writing codes into a gitignored file is the sanctioned path. An
agent pasting one into a tracked file is what the guards exist to stop.

**BUILT.** The profile is `pokemon_code_v1`: `{code, name, confidence}`. It carries uncertainty per character.
A `?` marks a character outside the printed alphabet, so the owner's re-read knows which character was doubtful.
The 3-4-3-3 layout is described in words, because a literal example would trip the commit guard on the prompt's
own source. The code lands in the record's `number`. That is free, because this game joins by name. The existing
search then serves as the dispute lookup, with zero new UI. It was demonstrated over real HTTP against a scratch
store. The ledger is two files with two jobs. `inventory/codes.jsonl` is a standing index, upserted by position,
so one line per card stays literally true across re-identifications. `runs/<run>/codes.jsonl` is the run's
deletable export. Both were verified gitignored (`git check-ignore -v`) before a byte was written.
Transcription accuracy is unmeasured. It cannot be measured without paid runs. The dispute flow is the
corrective loop by design.

**Sorted by set is a capture convention, not a schema.** The set hint field already carries it. The
code-card box is its own box, by the same owner ruling (recorded in D24). A pooled card in a located box
knowingly consumes a slot number. The convention is what keeps the located boxes' denominators honest.

---

## C9 — The QR is the whole identification, and the OCR half is retired

Ratified by measurement. Section 3 carries the argument. This entry records the decision and what it
overturns.

**The redemption code IS the QR's payload.** Confirmed first-party by reading the official redeemer's
JavaScript bundle. It reads a `2d_code` parameter and feeds the value straight into the redemption form.
The one field that must be exactly right is the thing being sold. It is recovered by arithmetic over
pixels. There is no model call, no network call and no cost.

**Measured at 3840x2160, the rig's frame size: 140 of 140 physically-possible frames, ZERO mis-reads, 87 ms
each.** Three cases are unrecoverable. Ablation against eleven transforms established them: a QR under
about 40 px, a 3.5 px defocus, and glare that clips the symbol to white. All three return nothing.

**C2's OCR half is retired, not deferred,** on three findings:

1. Vision OCR returned **confidence 1.0 on all 24 renders, 10 of them misreads**. It offered a single
   candidate every time. An OCR that is confidently wrong, with no alternative, cannot be an authority over
   a bearer instrument.
2. **Tesseract's character whitelist does not work with its default LSTM engine.** Its maintainers confirm
   this. The whitelist was the mitigation C2 depended on.
3. There is **no published list of code-card SKU strings**, official or community, to fuzzy-match against.
   A GitHub code search for the two examples in the fork's own notes returns zero hits. C2's "build the
   table empirically" would build the only copy in existence. Nobody would keep it honest.

**The decoder is `zxing-cpp==2.3.0`, and the pin is load-bearing.** This repo's venv is Python 3.9.6. The 3.x
line dropped cp39 wheels. An unpinned install resolves 3.1.1, finds no wheel, falls back to source, and dies
in CMake. An unpinned requirement here is a broken clone.

**OpenCV was declined twice. The first refusal stands.** A first pass tested opencv's two QR detectors on a
benchmark whose frames were at most 1600 px wide. That is not this rig. Re-measured at 3840x2160, opencv scored
72.7% at 211 ms. It scored **0 of 8 on a card filling a quarter of the frame, and 0 of 8 with glare**.
zxing-cpp scored 100% at 67 ms. The 46 MB stays unspent.

---

## C10 — The product is a capture claim, not a reading

Section 4 carries the facts. This entry records the decision.

Which set and product a code redeems is a **capture claim** in D21's exact sense. It is client state, resent
with every capture. It is written to the record and the sidecar, and it is correctable afterwards on the card
that got it wrong. It joins `game`, `set_hint`, `metadata_finish` and `rarity_claim`. This is what makes C9's
retirement of the OCR possible. The OCR existed to answer this question. One picker answers it more reliably.

What is given up: a shuffled pile of unknown provenance cannot be sorted this way. The trade is still right.
Section 4 has the numbers.

**The vocabulary is derived from the catalog, never invented** (`codes/products.py`). D22 already imposes this
rule on rarities. It has no reason to be weaker on this track.

---

## C11 — Disposal forecloses two channels, and the tier decides the rest

D24 rules that the physical card is destroyed once the code is extracted. The owner reaffirmed it. **It has a
price, recorded here so nobody rediscovers it.** Section 6.1c has the detail.

**TCGplayer is foreclosed outright.** Its help article permits code cards *"attached to a physical card"*. It
prohibits promo codes *"not attached to a physical card"*. Without a physical card, TCGplayer is closed. This holds
regardless of the 1,254 code-card SKUs in its catalog. It holds regardless of this repo's join-and-emit
pipeline pointing at it.

**eBay's dispute defense is foreclosed.** Every digital-delivery dispute is a guaranteed loss plus a dispute
fee. **This is what C5 was written to solve, and C5's mechanism is gone.** Channel choice replaces it: a buylist
or an own storefront, with no marketplace dispute machinery to lose to. C6's replace-not-refund also replaces it.

**Every researched channel came back MARGINAL.** Six channel families were researched independently. The buy
side is closing too. The largest dedicated shop has shut its buylist, and a second shop buys no booster codes.
Their stock counts show a supply glut. Section 6 has the figures.

**THE OPERATING RULE IS THE TIER.** Premium codes (`pc_etb`, `etb`, `premium_collection`) are listed individually
or as named single-product lots. Booster and bulk codes go out in one undifferentiated wholesale submission.
`codes/products.py:is_premium` is that rule in code. D9's $0.40 threshold falls between the two populations.
Section 6.3 has the lanes.

**Delivery automation is NOT built, and should not be yet.** Section 6.3 gives the reason. Section 8, item 3,
names the experiment that would settle the plan.
