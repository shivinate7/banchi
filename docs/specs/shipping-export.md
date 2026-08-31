# The TCGplayer Export Shipping format, and what it can and cannot answer

Provenance and findings for `fixtures/orders-shipping.csv`. Taken **2026-08-30** from the
seller portal: Orders tab → select all → **Export Shipping**.

This note lives here rather than as a `#` comment inside the CSV for two reasons: every other
fixture in `fixtures/` starts directly at its header row, so a comment would mean the fixture
is no longer byte-shaped like the thing it exists to represent; and `.claude/settings.json`
denies writes under `fixtures/**`, which is a rule worth respecting for a file that is not
the deliverable. Moving it inline is a one-line change if the owner prefers.

## Real, not hand-authored

The owner declined a hand-authored fixture explicitly. A hand-authored one tests the
*assumed* format rather than the real one — the failure the multi-game prompt seam nearly
shipped, where a differently-named identifier field would have parsed cleanly and joined
nothing.

## Shape

17 columns, **one row per order**, 331 rows. Byte format, reproduced exactly in the fixture:

- no BOM
- **LF** line endings — this differs from the *import* CSVs, which are CRLF (T2)
- header row **unquoted**, every data field **quoted**
- trailing newline at EOF

```
Order #,FirstName,LastName,Address1,Address2,City,State,PostalCode,Country,Order Date,
Product Weight,Shipping Method,Item Count,Value Of Products,Shipping Fee Paid,Tracking #,Carrier
```

**There are no line items.** No SKUs, no product names — only `Item Count`. Confirmed against
a real export, not suspected. This is why the shipping lane and the order resolver are
separate problems: the resolver needs per-line SKUs and this file cannot supply them.

## What the fixture changed

| Column | Treatment |
|---|---|
| `FirstName`, `LastName`, `Address1`, `Address2`, `City` | **stripped**, stable placeholders |
| `PostalCode` | **stabilized** — synthetic, preserving the 5-char / 10-char (ZIP+4) split |
| `Order #` | **stabilized** — synthetic, preserving `A2FFC195-<6 hex>-<5 hex>`, all distinct |
| `State`, `Country` | kept verbatim |
| `Order Date`, `Product Weight`, `Shipping Method`, `Item Count`, `Value Of Products`, `Shipping Fee Paid`, `Tracking #`, `Carrier` | kept verbatim, byte-identical to the export |

`Order #` was **stabilized rather than kept**, which is a deviation from the brief's "KEEP"
list and is recorded here as the brief asked. It resolves to a named buyer inside the seller
portal — `/orders/<order#>` is a live URL — so 331 real order ids in a committed file are a
lookup table into buyer identities for anyone with account access, and they survive into
forks and backups. Nothing is lost: the format is preserved, and for the Pirate Ship emit
path the order id is a passthrough field.

`Address2`'s empty/non-empty split is preserved (26 of 331 non-empty), because that is a real
shape a reader has to handle.

Verified before commit: **zero overlap** between any real value and its own column in the
fixture, no surviving city+zip pairing, no `@` anywhere in the file.

## Two columns are structurally empty

`Tracking #` and `Carrier` are **empty on all 331 rows** — present and blank, not omitted.
Kept as-is because that is the real shape. Do not write a reader that assumes they carry
data. The owner's earlier single-row export was likewise blank in both, so this is not an
artifact of one selection.

## `Product Weight` is a catalog constant, not a measured package weight

The weight-per-item ratio takes **five exact values** across the 234 weight-bearing orders:

```
  0.0700  x187    = 7/100      singles
  1.2850  x1      = 257/200    mixed
  1.3372  x1      = 115/86     mixed
  2.2570  x1      = 2257/1000  mixed
  2.5000  x44     = 5/2        sealed
```

Every non-singles order is an exact combination of a 0.07 unit and a 2.50 unit — 45.14 oz /
20 items is 18 × 2.50 + 2 × 0.07, exactly. So TCGplayer assigns a **per-product catalog
weight** and sums it. The ratio is therefore a proxy for *"does this order contain a
non-single"*, which is what makes it a usable discriminator and also why it is not evidence
about a real package.

**97 of 331 orders (29%) report `Product Weight` of 0.00**, including orders up to $1750.
That is *absent data, not a light order*. Any consumer must abstain on these rather than read
them as cards.

## The weight sweep

Sample: 331 orders, 234 weight-bearing. Log-spaced bins:

```
  [ 0.00,  0.05)     0     <-- empty
  [ 0.05,  0.10)   187    #############################################################
  [ 0.10,  0.30)     0     <-- empty
  [ 0.30,  1.00)     0     <-- empty
  [ 1.00,  2.00)     2    #
  [ 2.00,  3.00)    45    ######################
```

Empty band **(0.0700, 1.2850)** — an **18.4x** separation with nothing whatsoever inside it.

**Cut: 0.30 oz/item**, the geometric midpoint of the empty band (√(0.07 × 1.285) = 0.2999).
Derived from where the distribution is actually empty rather than picked, per D19's rule that
the motion trigger was tuned from a real trace and not from a plausible number. At that cut,
47 of 234 weight-bearing orders flag and the rule abstains on the 97 with no weight data.

**The signal is "heavier than cards alone — check contents". It must never say "contains a
playmat".** Even at 18x separation that is an inference, and this repo prefers refusal over
inference.

Two limits, named rather than left to be discovered:

- **It abstains on 29% of orders.** A zero-weight order is unjudgeable, and one of them is a
  $1750 order.
- **A zero-weight non-card drags the ratio *down*, not up.** Because the weight is a summed
  catalog constant, an order of one card plus one weightless non-card reads 0.035 oz/item —
  *below* the singles constant, so it would read as safer than a pure-singles order. No such
  row occurs in this sample (the minimum is exactly 0.07, confirmed with exact rational
  arithmetic rather than floats, which reported a phantom sub-0.07 row on the first pass), but
  the mechanism is real and is a false-negative path.

This is a **cross-check and a pre-line-data stopgap**, not a dependency. The definitive answer
comes from line items via the Bridge, and this cut should be retired rather than tuned when
that lands.

## STATUS

**RECORDED, READ, AND NOW REACHABLE.** Amended twice on 2026-08-30 — first by D61, which made
this format something the code reads, then by D69, which gave it a screen.

It read: *"RECORDED, not BUILT. Nothing reads this file and nothing reads the fixture."*
**Both halves are now false.** `pipeline/shipping.py` reads this format and routes an order by
the cut derived above, `pipeline/pirateship.py` writes the Pirate Ship import, and
`harness/tests/t7_store_and_seams.py:check_shipping_lane` asserts the lane counts against this
fixture's 331 real orders. Reachability followed within the day: `#/shipping` is in `ROUTES`,
`POST /shipping/batches` is served by `server/shipping_routes.py`, `app/src/server.ts` carries
the client functions, and `app/tests/shipping.spec.ts` asserts the screen.

**The intermediate wording — "no route, no client function, and no screen reaches either
module" — was true for part of one day and false by the end of it**, because D61 and D69
landed on the same date and each was written against a tree the other had moved. That
sentence was `CLAUDE.md`'s route-is-not-a-feature test applied correctly and answered by a
tree that had already moved past it.
`docs/specs/order-pipeline.md`'s step table is the register for what is reachable; this file
is the register for the format, and it should not have been carrying a reachability claim at
all.

**Two of this document's own limits are answered by the build rather than by re-measurement,
and one is not:**

- **"It abstains on 29% of orders, and one of them is a $1750 order."** The router asks the
  VALUE question before the weight proxy, and 58 of the 97 weightless orders are at or over
  $50 — answered with certainty by a rule that needs no weight. Abstention is **39 of 331
  (11.8%)**, and order `A2FFC195-0000F4-006AC` at $1750.00 is routed to a tracked parcel
  without the proxy being consulted. The 29% figure is still correct **about the weight rule
  in isolation**, which is what this document measures.
- **The sub-0.07 false-negative path.** Named here as a real mechanism with no row in the
  sample. It is now a third answer rather than a silent `cards_only`: a ratio below the
  singles constant abstains as `sub_single_weight`, on the grounds this document gives — no
  combination of catalog weights can produce one, so the proxy does not apply.
- **The cut itself is untouched and unre-fitted.** 0.30, the geometric midpoint of the empty
  band, exactly as derived above. D61 re-derives nothing here and cites this document for
  every number it uses.

**The retirement condition is unchanged and is now written into the code that depends on it:**
this is a pre-line-data stopgap, and the cut is to be **deleted rather than tuned** the day a
feed supplies line items. `pipeline/orders.py` already answers the same question properly
from declared line kinds.
