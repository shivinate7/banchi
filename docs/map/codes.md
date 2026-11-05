# Code cards

The code-card track: deterministic QR decoding, the code ledger, the product tier.

## Code files

- `codes/__init__.py` — Makes `codes` a package.
- `codes/ledger.py` — The code ledger, keyed by the CODE rather than by the position — C8's first build used the position, and under D24 the card is destroyed, so the code is what outlives it.
  - Decisions: `D24`, `D26`, `D70`
  - Tested by: `harness/tests/t8_codes.py`
- `codes/lots.py` — Build a sellable lot out of the ledger and write the three artifacts a sale needs — the listing, the buyer's manifest and the operator's packing slip.
  - Decisions: `D196`, `D14`, `D24`, `D70`
  - Tested by: `harness/tests/t8_codes.py`
- `codes/products.py` — Which sealed product a code redeems, and what that is worth.
  - Decisions: `D22`, `D9`, `D70`
  - Tested by: `harness/tests/t8_codes.py`
- `codes/qr.py` — Read the QR off a code card.
  - Decisions: `D14`, `D70`
  - Tested by: `harness/tests/t8_codes.py`
- `codes/scan.py` — Read a capture directory into ledger entries, and apply them.
  - Decisions: `D14`, `D70`
  - Tested by: `harness/tests/t8_codes.py`
