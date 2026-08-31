# Code cards, end to end

**Status: the decode path and the ledger are BUILT. The channel decision is RECORDED and
unexecuted. Read section 8 before treating any number here as settled.**

The codes track, from the operator putting a stack of code cards on the feeder to the money
arriving. It supersedes `code-card-fork/CLAUDE.md`'s architecture section and amends
`docs/CODES-DECISIONS.md` C2, C4 and C5, each of which is named where it is overturned.

Everything numeric here was measured on 2026-08-30 — either against
`fixtures/pokemon_wide_export_untouched.csv`, or on this machine, or by web research whose
sources are named. Nothing is carried forward from an earlier draft unmeasured.

---

## 1. The chain

    operator loads a stack                the cards came out of ONE sealed product
      -> capture screen, game = pokemon_code, product picker, set hint
      -> POST /capture per card           photo + sidecar + record, exactly as singles
    ./pkmnscan scan <capture-dir>         FREE. QR decode. NO model call. NO network.
      -> codes/qr.py                      100% of physically-readable frames, 0 mis-reads
      -> codes/ledger.py                  inventory/codes.jsonl, keyed by the CODE
      -> whatever QR refused              queued for the paid vision read, then a human
    #/codes                               the screen: what is held, what is dead, what sold
      -> export a channel file            a list of code strings, per channel
    disposal                              D24: the card is destroyed, the ledger survives

Two properties of that chain are the whole design, and both are departures from how the
singles track works:

**Identification costs nothing and calls nothing.** The redemption code IS the QR's payload,
so the field that must be exactly right is recovered arithmetically. The singles track's
paid Batch API call has no role on the primary path here.

**The product is a claim, not a reading.** Which set and which product a code redeems comes
from the operator at capture time, because code cards arrive in sealed-product batches. See
section 4.

---

## 2. What a code card is, verified

Confirmed 2026-08-30 against first-party sources, correcting C1 in two places.

- **The QR payload is a redeem URL carrying the code in a `2d_code` parameter.** Confirmed
  by reading the official redeemer's own JavaScript bundle: it reads `2d_code`, stores it,
  and feeds it straight into the redemption form. The parameter value IS the code.
- **CORRECTION to C1: it is a real query string, on `redeem.tcg.pokemon.com`.** C1 recorded
  a `#redeem` fragment on `tcg.pokemon.com`; that host now returns 404 for the redeem path.
  A fragment form still exists on a different redirect chain, so `codes/qr.py` reads both.
- **The printed code is 13 characters, `XXX-XXXX-XXX-XXX`.** Read off The Pokemon Company's
  own sample card image. Three widely-repeated community figures are wrong: Bulbapedia says
  11 characters, one guide publishes a 4-4-4-1 mask, and a third-party parser validates
  4-4-4-3.
- **The QR carries no set or product metadata.** Negative evidence — the official client
  reads no other parameter — rather than a decoded real card. This is why section 4 exists.
- **Codes are globally single-use, and do not expire.** Old PTCGO-branded cards still redeem
  in TCG Live with no cutoff. There is no visual difference between a redeemed and an
  unredeemed card, which is why the ledger is the only record of a code's state.
- **CORRECTION to C3: the redemption limits are SOFT.** Past the limit a code grants a small
  amount of in-game currency instead of the product; it is not refused. Official figures:
  booster 400 per expansion, Build & Battle 25, preconstructed deck 4, other products 4 (or
  1 if only cosmetic). At most 10 codes per redemption batch.
- **Validity CAN be checked without consuming a code.** The official flow is two-phase —
  a `verify` step returns a per-code `validationStatus`, and only codes marked valid are
  sent to `redeem`. **But there is no usable API**: every call carries a session cookie
  against an authenticated endpoint, passes a `can_redeem` gate, and the redeem step
  additionally requires a reCAPTCHA token. So automated dead-code screening is not
  available, and section 8 keeps that as the open question it is.

---

## 3. Decoding, and why there is no OCR

`codes/qr.py` carries the full measurement; the summary is that at the rig's real frame size
of 3840x2160 the shipped ladder reads **140 of 140 physically-possible frames with zero
mis-reads at 87 ms each**, and refuses the rest. Three cases are unrecoverable by ablation
against eleven transforms: a QR under about 40 px, a 3.5 px defocus, and glare that clips the
symbol to white.

**C2's OCR half is not built and should not be.** C2 specified a SKU crop taken off the QR as
a fiducial, then Tesseract with an `A-Z0-9` whitelist. Three findings retire it:

1. The research measured Apple's Vision OCR returning **confidence 1.0 on all 24 renders of
   which 10 were misreads**, with a single candidate every time. An OCR that is confidently
   wrong and offers no alternative cannot be an authority over a bearer instrument.
2. Tesseract's character whitelist **does not work with its default LSTM engine** — the
   maintainers confirm it. The whitelist was the mitigation C2 was relying on.
3. The question OCR was for is answered better by section 4.

**A mis-read is worse than a refusal, and that asymmetry decides the architecture.** A
refusal costs a re-shoot. A mis-read sells a stranger something that does not work, is
discovered days later, and lands in C6's replace-don't-refund with the operator unable to
tell whether the code was bad or the read was.

---

## 4. The product is a capture claim

**Code cards arrive in sealed-product batches.** A booster box yields 36 identical booster
code cards. An Elite Trainer Box yields one ETB code. The operator is not sorting a shuffled
pile; they are feeding a stack that came out of one thing, and they can see the box it came
out of while the camera cannot.

So the product joins `game`, `set_hint`, `metadata_finish` and `rarity_claim` as a **capture
claim** in D21's sense: client state, resent with every capture, written to the record and
the sidecar, correctable afterwards on the card that got it wrong. One picker on a screen
replaces a fiducial crop, an OCR engine, a whitelist, a fuzzy matcher, and a hand-built SKU
table that no published source exists for — the research confirmed there is **no public list
of code-card SKU strings**, official or community, and a GitHub code search for the two
examples in the fork's own notes returns zero hits.

**What is given up, plainly**: a genuinely shuffled pile of unknown provenance cannot be
sorted this way. Three things say the trade is right. A booster code is worth $0.03 and sells
undifferentiated, so sorting those by set earns nothing. The premium products, where the
product decides the price, arrive in ones and twos and are trivially declared. And where
provenance really is unknown the paid vision read remains available at about $0.002 a card —
worth spending on a $1.39 code and never on a $0.03 one.

`codes/products.py` holds the vocabulary, derived from the catalog rather than invented.

---

## 5. What a code is worth

### 5.1 TCGplayer catalog, from the real export

Read off the Near Mint rows of `fixtures/pokemon_wide_export_untouched.csv` — a real Filtered
Export scoped to four sets, 51 distinct code-card products. **A catalog price, not a realised
sale.**

    pc_etb              1.19 - 1.50   median 1.39
    premium_collection  0.09 - 1.50   median 0.26
    etb                 0.09 - 2.00   median 0.16
    collection          0.04 - 0.99   median 0.09
    blister             0.04 - 0.15   median 0.08
    tin                 0.03 - 0.12   median 0.05
    booster             0.03 - 0.05   median 0.03

**A Pokemon Center ETB code lists at roughly 46x a booster code, and boosters are the
overwhelming majority of any real pile.** The pile's value is a long flat floor with a few
tall spikes. The fork's instinct — "separate non-BST codes on sight" — is confirmed by the
first numbers anyone here has looked at, and D9's $0.40 threshold falls between the two
populations, which it predicted three months early.

### 5.2 What the market actually pays, from live sources

    acquisition, physical bulk on eBay        $0.020 - $0.040 per code
    published wholesale bid, booster          $0.01          <- BELOW acquisition
    published wholesale bid, premium SKUs     $0.10 - $1.00
    dedicated-shop retail, current sets       $0.38 - $0.43
    dedicated-shop retail, older sets         $0.08 - $0.20
    eBay digital 100-lot                      $0.056 - $0.130
    eBay 5-lot                                $0.142

**Recency beats chase status.** Retail spread newest-to-oldest is 4.9x, and Prismatic
Evolutions — the most hyped physical set of the era — sits near the bottom at $0.09. What
buyers pay for is a set still in print and standard-legal in TCG Live. **This is a decay
curve, and it means inventory must move rather than be held.**

**Product type beats set.** A Build & Battle code is about 5x a booster from the same set,
widening to 15x for older sets. Deck codes run 10x to 200x a booster.

---

## 6. Channels, and what destroying the card costs

Six channel families were researched independently. **Every one returned MARGINAL.** That is
the honest headline and it is not softened here.

| channel | digital delivery? | verdict |
|---|---|---|
| Dedicated buylist (paste a list) | yes, by design | the only lane that fits, at wholesale prices |
| Own storefront | yes | best margin, all the customer acquisition |
| eBay, digital delivery | yes, in practice | real volume, **zero dispute protection** |
| TCGplayer | **no — policy** | **foreclosed**, see below |
| Etsy / Gameflip / Kinguin | yes | permitted, effectively no buyers |
| Whatnot / Mercari / FB / Amazon | **no — policy** | foreclosed |

### 6.1 Destroying the card forecloses three things — CONDITIONALLY, and the condition changed

**AMENDED 2026-08-30 by the owner's ruling. Read this before the list below.** The owner
holds the PREMIUM code cards physically, in a box, at tracked locations, and will ship them.
Only the BULK tier is destroyed. Everything below is therefore true **of a destroyed card and
of nothing else** — the original draft stated it unconditionally and that was wrong.

The consequences of the split, settled:

- **TCGplayer is OPEN for the retained premium tier**, and the existing `join -> emit ->
  Import to Staged` path already reaches it: 263 code-card rows in the fixture export, five
  conditions each, a 16-column schema byte-identical to singles.
- **TCGplayer's BULK lane is also open** — catalog product 253512, "Pokemon Code Card Bulk
  Lot", **8,694 units/year, active 32 of 52 weeks, at $0.03-$0.04/card**, with real observed
  orders of 1,100 / 1,425 / 700 / 300 cards. **But it cannot be listed by CSV**: bulk lots are
  "Listings with Photos" through the seller portal, which is both a manual third-party UI step
  (CLAUDE.md forbids one inside the autonomous pipeline) and a request for photographs of code
  cards (the opsec rule forbids those). Unresolved; the owner rules.
- **eBay's dispute defence is restored for anything shipped**, and only for Item Not Received.
  It does nothing for Item Not As Described, which is the dispute code cards actually attract.
- **The hybrid — ship the cards AND message the codes — is the worst case, not the best.** The
  buyer redeems from the message, files INAD, and returns worthless redeemed cards. Zero of six
  high-feedback specialists examined do it.

### 6.1a The binding constraint is ABSORPTION, not price or postage

The owner's pile is **~30,000 codes**. Measured against that:

- TCGplayer's bulk SKU absorbs **8,694 units/year across every seller combined**, and already
  carries **~19,300 standing units across 56 listings** at a $0.01-$0.02 floor. The pile alone
  is roughly **3.5 years of total market demand**, queued behind two years of existing supply.
- The best eBay 1,000-lot comparable sold **twice, lifetime**.
- The entire PREMIUM tier absorbs **924 units and $231 gross per year, marketplace-wide**. At a
  3% premium fraction the pile holds ~900 premium codes — about a year of the whole market's
  appetite — decaying at a measured **-25%/year**.

**Nothing in the pipeline can move that number.** It is why the lot builder's most valuable
property is not the listing text but the guarantee that a code is never committed twice across
two concurrently-listed venues, and why the honest expectation is a multi-year tail at
clearing prices rather than a liquidation.

### 6.1b Lot size and mixing, settled by measurement

- **1,000 cards is the postage optimum**: $9.70 Ground Advantage = **$0.0097/code**, against
  **$0.100-$0.168/code at 50**, which falls off the eBay Standard Envelope cliff on both weight
  and thickness. There is no good lot size between 16 and ~250.
- **15 cards is the eSE optimum** at $0.78 = $0.052/code, and 20 is the absolute ceiling on
  thickness.
- **Mixing costs nothing at scale**: the mixed-versus-named discount is ~80% at 5-count, 62% at
  single-code retail, ~11% at 24-30, and **~0% by 50+**. So bulk lots need no set sorting, and
  mixing only destroys value on small lots and singles — where the premium codes are.

### 6.1c What the original list said, which still holds for a DESTROYED card

1. **TCGplayer is foreclosed outright.** Its own help article permits code cards *"attached
   to a physical card"* and states that *"the sale of promo codes not attached to a physical
   card is prohibited."* No physical card, no TCGplayer — regardless of the 1,254 code-card
   SKUs in its catalog.
2. **eBay dispute defense is foreclosed.** eBay's Money Back Guarantee explicitly excludes
   *"Digital content, Intangible goods"*, and seller protection requires evidence of physical
   delivery. Every digital-delivery dispute is a guaranteed loss plus a dispute fee.
3. **Six consumer marketplaces are foreclosed** by their own digital-goods bans.

**This directly overturns C5**, which specified shipping the physical cards precisely to buy
the protection above. C5 is superseded: its mechanism is unavailable under D24, and the
protection it bought cannot be replaced on eBay. What replaces it is channel choice — a
buylist or an own storefront, where there is no marketplace dispute machinery to lose to —
and C6's replace-don't-refund, which costs pennies and is the only defense left.

### 6.2 The economics, unsoftened

The best-performing code listing found anywhere on eBay — 7,201 lifetime orders, 41 sold in
one day — nets roughly **$4,728 a year**. That is the ceiling of a well-run operation on the
single best listing in the category, and it lives at 1x-5x lot sizes where **the $0.30
per-order fee is 42% of a $0.71 order and eBay's total take is 55.5%**. Bulk lots, the only
automatable size, barely move: 16, 30 and 9 lifetime sales on the 100x, 50x and 1000x lots
measured.

**Demand and automatability point in opposite directions**, and that is the central finding.
Volume lives where delivery is manual; automation lives where nothing sells.

The buy side is also closing. The largest dedicated shop has **shut its buylist** and demoted
payout to store credit; a second now buys only two premium product types and **no booster
codes at all**. The reason is visible in their own stock counts — 500 to 1,350 units standing
per set. This is a supply glut, not a demand shortage.

### 6.3 The recommendation

**Tier the pile and run two lanes**, which is what `codes/products.py:is_premium` exists for:

- **Premium codes** (pc_etb, etb, premium_collection — the $0.99 to $2.00 population) are
  worth listing individually on an own storefront or as named single-product lots. These are
  the spikes and they justify per-card attention.
- **Booster and bulk codes** go out in one undifferentiated wholesale submission. They are
  worth $0.01 to $0.13 and no amount of sorting changes that.

**Do not build delivery automation yet.** C7's eBay Trading API call is still live but is now
**deprecated**, replaced by a REST Message API. Building against either is premature while
the channel decision is unexecuted, and section 8 names the experiment that would settle it.

---

## 7. Storage

`codes/ledger.py` carries the argument. In brief:

- **The key is the code**, not the position. C3 asked for this and C8's first build used the
  position; under D24 the card is destroyed, so the position is a filing reference and the
  code is the identity. This is what makes dedupe and reservation possible at all.
- **`inventory/codes.jsonl`, gitignored.** A ledger of unredeemed codes is a file of bearer
  instruments. The runtime writing into a gitignored file is the sanctioned path; the commit
  guards protect the repository, not the store.
- **States are the code's, not the card's**: `held`, `reserved`, `delivered`, `dead`. A card
  can be destroyed under D24 while its code is still `held` and perfectly saleable, and
  conflating the two would make disposal look like losing the asset.
- **Reservation is all-or-nothing and refuses anything not `held`.** Double-selling is
  unrecoverable, so the refusal is loud rather than a no-op.
- **A duplicate is recorded, never resolved.** One code read at two positions means either
  one card photographed twice or two cards bearing one code. A human decides with both
  photographs; a rule would be wrong half the time.

---

## 8. What is NOT settled

Named rather than buried, and none of it blocks the build.

1. **No real code card has ever been through this pipeline.** Every decode number is
   synthetic. The first real stack is the measurement that matters, and it may find a layout,
   a glare pattern or a print run nothing here anticipates.
2. **The dead-code rate is unknown.** Bulk lots are sold "unused" and unverifiable, there is
   no automated way to screen them, and no source publishes a rate. Price bulk assuming a
   loss and measure it on the first batch.
3. **No channel has been executed.** Every price above is an ask or a catalog figure except
   where a sold count is cited. The cheapest experiment that would settle the whole plan is
   **one wholesale submission of a few hundred booster codes to a buylist that accepts a
   pasted list, and one premium code listed on a storefront** — a week's work that replaces
   six MARGINAL verdicts with two realised prices.
4. **Buylist counterparty risk is real and unquantified.** The one app that accepts a pasted
   list of codes rates 2.3 to 3.1 stars with recurring non-payment complaints. Submit a small
   batch first.
5. **The redemption limits are TPCi's published figures and have not been re-verified
   against a current source by this repo.**
6. **The SKU suffix vocabulary is undetermined.** Only `BST` was ever observed. This costs
   nothing while section 4 stands, and would matter if OCR were ever revisited.
7. **Whether the code string itself encodes the product** is unverified in either direction.
   If it did, section 4's picker becomes unnecessary — worth ten minutes against the first
   real batch.

---

## 9. Lots

`codes/lots.py` builds them; `#/codes` is where a human does. Two rules carry the design and
both were found by reading generated output rather than by reasoning.

**A PHYSICAL LOT IS SCOPED TO A BOX.** The obvious shape — "reserve any 1,000 sellable bulk
codes" — commits codes A through J while the operator, standing at a shelf, grabs a different
thousand cards. The buyer then receives cardboard whose codes were never committed to them,
and the ledger is confidently wrong about both. No packing discipline fixes it, because the
cards are indistinguishable by eye. A count-scoped lot is legal only for a DIGITAL sale, where
nothing is pulled.

**A PHYSICAL LOT TAKES THE WHOLE BOX OR IT IS REFUSED.** A lot that took 1,000 of a box's
1,003 cards produces a correct ledger and a packing slip reading "Box 12, 1000 card(s)" — and
the operator, holding that slip and that box, ships 1,003. Two of those three strays list at
roughly 46x a booster. "Pull all of them except these three" is not an instruction anybody
executes reliably against a thousand identical pieces of cardboard, so it is not offered:
`plan` refuses and names the strays by index.

**That check asks what is PHYSICALLY IN THE BOX, not what is sellable from it**, and the
difference is two classes of card that a first version missed entirely — a code with no product
claim, which every lot filter drops on purpose, and a code **already reserved to another lot**,
which would then be shipped to two buyers. Only `delivered` means the cardboard has left. The
second class was caught on real data: two cards in a demo box were already committed to an
earlier order and would have gone out twice.

**Three artefacts, because three different people read them.** `listing.txt` for the seller,
once. `manifest.txt` for the BUYER — one code per line and nothing else, because it is pasted
whole. `packing.txt` for the operator at the shelf. The manifest is **never returned inline by
the route**: a thousand live codes in a JSON response also land in every devtools network tab
and screenshot that catches it, so the screen links to the file.

`lots/` is gitignored for `inventory/`'s reason and not a weaker one.
