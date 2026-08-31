# Settled decisions — code card track

## C1 — Card anatomy, verified on physical cards (Aug 2026)

The face side carries everything needed. Single-sided capture, no flipping.

- **QR code** decodes to `https://tcg.pokemon.com/en-us/tcgl/#redeem?2d_code=<CODE>`. The
  payload is the code only — no set metadata, no product metadata.
- **Printed code**, format `XXX-XXXX-XXX-XXX`.
- **Product SKU** printed directly above the code: `EN` + set code + product suffix.
  Observed: `ENME1BST` (Mega Evolution booster), `ENSV8P5BST` (Prismatic Evolutions
  booster). This is the identification key.
- **Plain-English name line** at the bottom ("Scarlet & Violet—Prismatic Evolutions").
  Secondary cross-check only — em-dashes and spaces make it a worse OCR target.
- **Reverse art is useless.** Five randomized designs, set-independent, across the whole
  modern range.

## C2 — Identification architecture

**SUPERSEDED IN PART, 2026-08-30. Steps 1 and 2 stand; steps 3, 4 and 5 are retired.** The QR
decode is built and is the primary path. The OCR half — SKU crop, Tesseract, fuzzy match
against a hand-built SKU table — is NOT built and should not be: see C9. The cost argument
below still holds and is now stronger, because the primary path costs nothing at all.

1. Decode QR locally. Deterministic, and doubles as an "in frame and readable" check.
2. Use the QR as a fiducial: four corners give scale, rotation, and perspective for free.
   Crop the SKU relative to the QR bounding box.
3. OCR the crop, `A-Z0-9` whitelist, Tesseract.
4. Fuzzy-match against the SKU table → set + product type.
5. Low confidence → cross-check the English name line.
6. No match → review queue.

**The SKU table is built empirically**: scan a few dozen cards across eras, dump
unrecognized strings, map by hand once. A couple hundred entries covers everything. Haiku
is the fallback for unknown SKUs only — same shape as the singles variant ladder.

Cost on the primary path is effectively zero, versus ~$0.002/card if Haiku ran on every
card. That is 1–2% of a code's retail value — tolerable, but unnecessary.

## C3 — Data model

**AMENDED 2026-08-30 (C9): the redemption limits below are SOFT, not hard caps.** Past a
limit a code grants a small amount of in-game currency instead of the product; it is not
refused. The figures are otherwise confirmed against the official FAQ.

Fungible pool inventory. Code string is the natural primary key, giving free dedupe and
structural protection against double-selling. Atomic dequeue on order assignment.

Per-code audit trail: source, `scanned_at`, capture photo, SKU, `order_id`, buyer,
`delivered_at`.

Product type matters as much as set. Redemption limits: booster 400, Build & Battle 25,
precon deck 4, other products 4 (or 1 if only cosmetic). `BST` will dominate the pile;
non-`BST` codes are the scarce, high-value ones and must be separated out.

## C4 — Sales: eBay bulk lots, sorted by set

25x / 50x / 100x. Single-code and 5-for-$1 lots are negative margin once eBay's ~13% plus
per-order fee applies. Mystery mixed lots sell at a real discount — which is the entire
justification for the SKU OCR work.

## C5 — Ship the physical cards AND message the codes instantly

**OVERTURNED 2026-08-30 by C11.** Its mechanism is unavailable: D24 disposes of the physical
cards, so there is nothing to ship. The problem it identified is real and its solution is
gone — read C11 for what replaces it. The analysis below is kept because the risk it names
is exactly the risk the track now carries unmitigated.

Pure digital delivery has no seller protection. eBay requires carrier tracking with
delivery confirmation for an item-not-received defense, so a buyer can redeem 100 codes,
file INR, and win automatically. At 100-count lots, $1.50–4 postage against a $15–25 sale
converts an unprotected digital sale into a protected physical one — and sidesteps the
electronically-delivered-goods approval question entirely.

Listing copy states plainly: physical cards shipped, codes messaged instantly, no returns.

## C6 — Dispute policy: replace, don't refund

Costs pennies, protects feedback.

## C7 — Automation, gated on singles Gate B

`ORDER.CREATED` webhook → dequeue N codes → Trading API
`AddMemberMessageAAQToPartner` (75 calls per 60s, 90-day order window; no REST equivalent
exists) → mark shipped → decrement listing quantity.

Until Gate B passes: manual listing, semi-manual code delivery. Cash flow can start there.

---

## Open questions

- **CODES-A — vintage SKU geometry.** Pre-TCG-Live (green PTCGO-era) cards may not carry
  the SKU in the same format or position. Verify before assuming the fiducial offset holds
  across the whole pile.
- **CODES-B — SKU table coverage.** Build the mapping table; confirm coverage against
  actual inventory.
- Confirm eBay account standing, and whether digital-goods approval is needed even under
  the ship-physical model.
- Codes cannot be validated without redeeming them. Codes from own sealed product are safe;
  anything acquired in bulk should be priced assuming a dead percentage.
- Resale of codes is a gray zone. Nothing in TPCi's terms formally authorizes
  redistribution, though the market is large and openly tolerated. Read the terms.

## Why codes goes first

Small track: QR decode, SKU OCR, codes table, eBay lot listings, delivery worker. It rides
the shared foundation and serves as the feeder's shakedown cruise — low stakes to fail on,
since a misread QR fails to decode rather than mispricing a $40 card.

## C8 — The code ledger: every code's text beside its photograph, for the dispute that will come

Ratified by the owner 2026-08-23, in his own words: code cards *"live in the arbitrary box of
code cards, ideally sorted by set"*, and *"we likely will need both the code card image +
image to text csv of them saved (in case a customer says a certain code didn't work, we check
that code retroactively, tap its image, and likely it was an image to text error)."*

**The dispute flow is the spec.** A buyer says a code did not work. The owner looks the code
up, opens the photograph it was read from, and re-reads it by eye — because the likeliest
failure is the image-to-text step, and C6 already rules the remedy (replace, don't refund).
Everything below exists to make that lookup two taps.

**The mechanism rides what the singles track already built.** `pokemon_code` gets a real
prompt profile whose job is transcription: the printed code, exactly as printed. The
extracted code lands on the card record the way every identification does, which makes it
searchable through the existing search with zero new UI — type the code, get the card, tap
the photo. The ledger file is the fork's export: code text keyed to box/index and photo path.

**A LEDGER OF UNREDEEMED CODES IS A FILE OF BEARER INSTRUMENTS**, and that sentence decides
its storage: it lives under the store beside `inventory.json`, gitignored like everything
there, and never in a commit — the commit-time opsec rules and the re-enabled PreToolUse
guard both fire on a code literal precisely because a file like this must never cross them.
The runtime writing codes into a gitignored file is the sanctioned path; an agent pasting one
into a tracked file is what the guards exist to stop.

**BUILT 2026-08-23, the same day it was ratified.** The profile is `pokemon_code_v1`:
`{code, name, confidence}`, uncertainty per character (`?` outside the printed alphabet, so
the owner's re-read knows exactly which character was doubtful), the 3-4-3-3 layout described
in words because a literal example would trip the commit guard on the prompt's own source.
The code lands in the record's `number` — free because this game joins by name — which makes
the existing search the dispute lookup with zero new UI: type the code, get the card, tap the
photo (demonstrated over real HTTP against a scratch store). The ledger is two files with two
jobs: `inventory/codes.jsonl`, a standing index upserted by position so one-line-per-card
stays literally true across re-identifications, and `runs/<run>/codes.jsonl`, the run's
deletable export — both verified gitignored (`git check-ignore -v`) before a byte was
written. Transcription accuracy is unmeasured and cannot be measured without paid runs; the
dispute flow is the corrective loop by design, which is what this entry says it is for.

**Sorted by set is a capture convention, not a schema**: the set hint field already carries
it, and the code-card box is its own box by the same owner ruling (recorded in D24 — a
pooled card in a located box knowingly consumes a slot number, so the convention is what
keeps the located boxes' denominators honest).


---

## C9 — The QR is the whole identification, and the OCR half is retired

Ratified by measurement, 2026-08-30. `docs/specs/code-cards.md` carries the full argument;
this entry records the decision and what it overturns.

**The redemption code IS the QR's payload.** Confirmed first-party by reading the official
redeemer's own JavaScript bundle: it reads a `2d_code` parameter and feeds the value straight
into the redemption form. So the one field that must be exactly right — the thing being sold
— is recovered by arithmetic over pixels, with no model call, no network call and no cost.

**Measured, at the rig's real frame size of 3840x2160: 140 of 140 physically-possible frames,
ZERO mis-reads, 87 ms each.** Three cases are unrecoverable and were established by ablation
against eleven transforms rather than assumed: a QR under about 40 px, a 3.5 px defocus, and
glare that clips the symbol to white. All three return nothing.

**C2's OCR half is retired rather than deferred**, on three findings:

1. Vision OCR was measured returning **confidence 1.0 on all 24 renders, of which 10 were
   misreads**, offering a single candidate every time. An OCR that is confidently wrong and
   offers no alternative cannot be an authority over a bearer instrument.
2. **Tesseract's character whitelist does not work with its default LSTM engine**, confirmed
   by its maintainers. The whitelist was the mitigation C2 depended on.
3. There is **no published list of code-card SKU strings**, official or community, to fuzzy
   match against — a GitHub code search for the two examples in the fork's own notes returns
   zero hits. C2's "build the table empirically" would be building the only copy in
   existence, kept honest by nobody.

**The decoder is `zxing-cpp==2.3.0` and the pin is load-bearing.** This repo's venv is Python
3.9.6; the 3.x line dropped cp39 wheels, so an unpinned install resolves 3.1.1, finds no
wheel, falls back to source and dies in CMake. An unpinned requirement here is a broken clone.

**OpenCV was declined a SECOND time, and the first refusal stands.** A first pass at this took
opencv's two QR detectors on a benchmark whose frames were at most 1600 px wide — which is not
this rig. Re-measured at 3840x2160, opencv scored 72.7% at 211 ms including **0 of 8 on a card
filling a quarter of the frame and 0 of 8 with glare**, against zxing-cpp's 100% at 67 ms. The
46 MB stays unspent.

---

## C10 — The product is a capture claim, not a reading

**Code cards arrive in sealed-product batches.** A booster box yields 36 identical booster
code cards; an Elite Trainer Box yields one ETB code. The operator is not sorting a shuffled
pile — they are feeding a stack that came out of one thing, and they can see the box while
the camera cannot.

So which set and which product a code redeems is a **capture claim** in D21's exact sense:
client state, resent with every capture, written to the record and the sidecar, correctable
afterwards on the card that got it wrong. It joins `game`, `set_hint`, `metadata_finish` and
`rarity_claim`, and it is what makes C9's retirement of the OCR possible — the OCR existed to
answer this question, and one picker answers it more reliably.

**What is given up**: a genuinely shuffled pile of unknown provenance cannot be sorted this
way. The trade is right anyway. A booster code is worth $0.03 and sells undifferentiated, so
sorting those by set earns nothing. The premium products, where the product decides the price,
arrive in ones and twos and are trivially declared. And where provenance really is unknown the
paid vision read remains available at ~$0.002 a card — worth spending on a $1.39 code and
never on a $0.03 one.

**The vocabulary is derived from the catalog, never invented** (`codes/products.py`), which is
the rule D22 already imposes on rarities and which has no reason to be weaker one track over.

---

## C11 — Disposal forecloses two channels, and the tier decides the rest

D24 rules that the physical card is destroyed once the code is extracted, and the owner
reaffirmed it on 2026-08-30. **It has a price, recorded here so nobody rediscovers it.**

**TCGplayer is foreclosed outright.** Its own help article permits code cards *"attached to a
physical card"* and states that *"the sale of promo codes not attached to a physical card is
prohibited"*. No physical card, no TCGplayer — regardless of the 1,254 code-card SKUs in its
catalog, and regardless of this repo's entire join-and-emit pipeline pointing at it.

**eBay's dispute defense is foreclosed.** The Money Back Guarantee explicitly excludes
*"Digital content, Intangible goods"*, and seller protection requires evidence of physical
delivery. Every digital-delivery dispute is a guaranteed loss plus a dispute fee. **This is
precisely what C5 was written to solve, and C5's mechanism is gone.** What replaces it is
channel choice — a buylist or an own storefront, where there is no marketplace dispute
machinery to lose to — and C6's replace-don't-refund, which costs pennies.

**Every researched channel came back MARGINAL**, and that is stated rather than softened. Six
channel families, researched independently. The best-performing code listing found anywhere on
eBay nets about $4,728 a year, at 1x-5x lot sizes where the $0.30 per-order fee is 42% of the
order and eBay's total take is 55.5%. Bulk lots, the only automatable size, barely move. **Demand
and automatability point in opposite directions.** The buy side is closing too: the largest
dedicated shop has shut its buylist, a second buys no booster codes at all, and their own stock
counts show 500 to 1,350 units standing per set — a supply glut.

**THE OPERATING RULE IS THE TIER.** A Pokemon Center ETB code lists at roughly **46x** a booster
code, and boosters are the overwhelming majority of any pile. So:

- **premium codes** (`pc_etb`, `etb`, `premium_collection`) are listed individually or as named
  single-product lots. They justify per-card attention.
- **booster and bulk codes** go out in one undifferentiated wholesale submission. No amount of
  sorting changes what they are worth.

`codes/products.py:is_premium` is that rule in code. D9's $0.40 threshold falls between the two
populations, which it predicted three months early.

**Delivery automation is NOT built and should not be yet.** C7's eBay Trading API call is still
live but is now **deprecated**, replaced by a REST Message API. Building against either is
premature while no channel has been executed even once. The cheapest experiment that would
settle the whole plan is one wholesale submission of a few hundred booster codes and one premium
code listed on a storefront — a week's work that replaces six MARGINAL verdicts with two
realised prices.
