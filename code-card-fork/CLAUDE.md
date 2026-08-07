# PKMNCODES — code card track

Shares the rig, capture server, and capture app shell (mode toggle) with singles. Shares
nothing downstream: data model, identification, sales channel, and fulfillment are its own.
Root operating rules apply, including the sequencing ruling — the codes MVP rides the
shared foundation with a **manual** eBay sales end; the automated delivery worker is gated
on singles Gate B.

## Things you will get wrong without being told

- **No vision model on the primary path.** QR decode (`zxing-cpp` / `pyzbar`) → SKU crop →
  Tesseract with an `A-Z0-9` whitelist → fuzzy match against the SKU table. Haiku is the
  fallback for unknown SKUs only.
- **The QR is a fiducial marker.** The decoder returns four corner coords, so compute the
  SKU crop *relative to the QR bounding box*, never at fixed image coordinates. Layout has
  already drifted between 2023 and 2025 print runs.
- **The identification key is the product SKU** printed above the code: `EN` + set code +
  product suffix (`ENME1BST`, `ENSV8P5BST`). `SV8P5` maps to pokemontcg.io `sv8pt5`.
- **Reverse art is useless for ID.** From Mega Evolution through Chaos Rising all code
  cards use one of five randomized designs, set-independent. Perceptual hashing is dead on
  arrival — do not propose it.
- **Codes are fungible pool inventory, not located items.** No box, no section, no
  position. Do not reuse the singles schema. The code string is the primary key.
- **Atomic dequeue is required.** A code is marked reserved the instant it is assigned to
  an order ID. Never reissue. Double-selling a code is unrecoverable.
- **Delivery is eBay Messages only** — never email, never text. Off-platform contact
  violates policy and destroys the evidence trail.

## Hard rules

- Never guess a SKU. No match → review queue with the stored photo.
- Failure must be loud. A QR that does not decode is a stop, not a default.
- Separate non-`BST` codes on sight — they are the scarce, high-value ones.
- No real code-card photo or code string in any tracked file. Enforced by pre-commit hook.

Rationale, sales strategy, and open questions: @../docs/CODES-DECISIONS.md
