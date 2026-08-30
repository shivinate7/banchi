# PKMNCODES — code card track

Shares the rig, capture server, and capture app shell with singles. Shares nothing
downstream: data model, identification, sales channel, and fulfillment are its own (D14).
Root operating rules apply.

**The gating system is retired.** This file used to say the delivery worker "was gated on
singles Gate B". Gate B passed 2026-08-22, the gating system was retired 2026-08-23, and
nothing here is blocked behind anything. The worker is unbuilt because the channel decision
is unexecuted, which is a different reason and is argued in `docs/specs/code-cards.md` §6.

**`docs/specs/code-cards.md` is the spec and supersedes this file's architecture.** Read it
before building. This file is the short operating summary; the spec carries the measurements,
the channel research, and the open questions.

## Things you will get wrong without being told

- **The QR IS the code, and the primary path makes NO model call and NO network call.**
  `codes/qr.py` decodes locally. Measured at the rig's real 3840x2160 frame size: **140 of
  140 physically-possible frames, ZERO mis-reads, 87 ms each.** The decoder is
  `zxing-cpp==2.3.0` and **the pin is load-bearing** — plain `pip install zxing-cpp` FAILS on
  this repo's Python 3.9.
- **THERE IS NO OCR, AND C2's OCR HALF IS RETIRED.** C2 specified a SKU crop off the QR as a
  fiducial, then Tesseract with an `A-Z0-9` whitelist. Do not build it. Vision OCR was
  measured returning confidence 1.0 on 24 renders of which 10 were misreads; Tesseract's
  whitelist does not work with its default LSTM engine; and no public list of code-card SKU
  strings exists to fuzzy-match against. The question it was for is answered by the next
  rule.
- **The product is a CAPTURE CLAIM, not a reading.** Code cards arrive in sealed-product
  batches — a booster box yields 36 identical booster codes — so the operator declares the
  product and set at capture, in D21's exact sense. `codes/products.py` holds the vocabulary,
  derived from the real catalog rather than invented.
- **A MIS-READ IS FAR WORSE THAN A REFUSAL.** A refusal costs a re-shoot. A mis-read sells a
  stranger something that does not work, is found days later, and lands in C6 with nobody
  able to tell whether the code was bad or the read was. Every failure path here returns
  nothing rather than a guess.
- **The ledger's key is the CODE, not the position** (C3, and C8's first build had it as the
  position). Under D24 the card is destroyed, so the position is a filing reference and the
  code is the identity. This is what makes dedupe and reservation possible.
- **Codes are fungible pool inventory, not located items** (D24). No box, no section, no
  position. The code string is the primary key. Do not reuse the singles schema.
- **Atomic dequeue is required.** A code is marked reserved the instant it is assigned to an
  order. Never reissue. Double-selling a code is unrecoverable, so `codes/ledger.py:reserve`
  REFUSES anything that is not `held` rather than quietly doing nothing.
- **Codes are globally single-use and never expire, and a redeemed card looks identical to an
  unredeemed one.** The ledger is the only record of a code's state. There is no usable API
  to check one — the official verify step is genuinely non-consuming but sits behind session
  auth, a `can_redeem` gate and a reCAPTCHA.
- **The redemption limits are SOFT** (corrects C3). Past the limit a code grants a little
  in-game currency instead of the product; it is not refused.
- **DESTROYING THE CARD FORECLOSES TCGPLAYER AND EBAY'S DISPUTE DEFENCE.** TCGplayer permits
  code cards only when *attached to a physical card*. eBay's Money Back Guarantee excludes
  intangible goods and its seller protection requires physical delivery evidence. This
  overturns C5, which existed to buy exactly that protection. See `docs/specs/code-cards.md`
  §6.1 — it is a real cost of D24, stated so nobody rediscovers it.
- **Every researched channel came back MARGINAL.** Booster codes are worth $0.01-$0.13 and
  the published wholesale bid for one is BELOW what bulk costs to acquire. The money is in
  the premium tail: a Pokemon Center ETB code lists at ~46x a booster. Tier the pile.

## Hard rules

- Never guess a code. No decode → the paid vision read, then a human. Never a default.
- Failure must be loud. A QR that does not decode is a stop.
- Separate non-`BST` codes on sight — they are the scarce, high-value ones, and the catalog
  numbers now confirm it rather than merely asserting it.
- No real code-card photo or code string in any tracked file. Enforced by pre-commit hook.
  The runtime writing codes into gitignored `inventory/` is the sanctioned path; the guards
  protect the repository, not the store.

Rationale, sales strategy, and open questions: @../docs/CODES-DECISIONS.md
Spec, measurements and channel research: @../docs/specs/code-cards.md
