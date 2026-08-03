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
