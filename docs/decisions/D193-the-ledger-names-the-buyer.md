# D193 — The ledger names the buyer

**The ledger keeps two names: the buyer's and the name on the parcel. It keeps no street.** The owner ruled the second one ("Save it on the order"): a TCGplayer order can have buyer Anna Hutson and ship-to Logan Hager, and a pack that reads only the buyer puts the wrong name on the parcel. The rest of this entry argues the buyer's name; its argument holds for the ship-to name, which is no more a credential or a delivery instruction.

**The owner walks drawers per PERSON, not per order number, and the ledger has never named one.** D63 built the ledger with two rulings that read as a single PII stance — *"No buyer, no address, no email. The ledger holds a SKU, a quantity and what the feed called the card"* — and D69's paste projection enforces the same shape at the browser. **That was never an owner ruling.** It was a session's design, made under D63/D69's own scope, at a moment nobody had asked what the screen should be for. The owner's outcome is a hand working through drawers for one buyer at a time. A list of order numbers with no name on it cannot be walked that way. D63's working agreement says to think in outcomes, not processes. That is what asks whether the exclusion still served anybody once the screen existed.

### The owner's rulings

1. **Store the buyer's display name, and the ship-to name.** The ship-to name is first and last as
   TCGplayer gives it (`OrderRecord.ship_to`), written by every path that has it: the Export Shipping read
   (`Shipment.ship_to`, matched to the ledger by order number), a feed or paste that carries `ship_to`
   (`ORDER_INGEST_ORDER_FIELDS`, `orderPaste.ts`'s `ORDER_KEEP`), and a names pass. The ledger keeps the name
   and NEVER the street, city or postcode beside it, on this ruling. D326 (the TCGTracking pipe) lifts the
   address exclusion for what TCGTracking returns, and that lane keeps the address only in its label rows; this
   entry's ledger keeps none. Email, payment and the transaction breakdown stay excluded by the same
   allowlist mechanism D63 and D69 built. Nothing about how PII is kept OUT changes. Two fields move from the
   excluded side of the line to the kept side.
2. **A one-time backfill**, `LastTwoYears` (the store is younger than that), every status,
   skip-known, looped by the screen until `remaining == 0`. After that the ordinary press is
   an APPEND: all statuses, skip-known, one pass.
3. **Clicking a buyer opens one merged walk over all their open orders.** The screen must
   make it obvious when a person has more than one. It shows an `N orders` pill on the row, and it
   enumerates the orders in the detail header.

### Why this reopens D63 and D69 rather than widening them quietly

**"No buyer, no address, no email" was one sentence doing two jobs, and only one of them was ever argued.** D63's own text argues for the second and third. `inventory/` is
gitignored, which keeps a bearer instrument or a mailing address out of a commit. That reason says nothing about a NAME, which is not a credential and not a delivery instruction. The
first clause rode along on that argument without one of its own. It stood for three weeks
because nothing on the commit path reads whether an exclusion still matches what the owner
asked for. That is the same gap D63's amended working agreement now names directly. It says to flag a stale or overly bearing decision and ask for the right fix. This is that
flag, and the owner's word is what it waited for.

**What is unchanged, and it is the part that was doing real work.** Three allowlists are the
mechanism, not the exclusion: `server/order_transport.py`'s `project_summary` / `project_order`,
`server/capture_server.py`'s `ORDER_INGEST_ORDER_FIELDS`, and `app/src/orderPaste.ts`'s
`ORDER_KEEP`. Each still refuses everything it refused yesterday, `shippingAddress` by name. `buyerName`'s sibling
fields (`shippingAddress`, `email`, payment, the transaction breakdown) are named and dropped
at the same three seams, by the same code. T7's key-set assertions still pin the shape
whole rather than by exception. Adding one field to an allowlist that already existed is the
opposite of loosening a boundary that had none. A boundary with no allowlist at all would be
the license this entry declines to take.

### What is added, and its register

**`buyer` and `ship_to` are feed-owned content, not facts this pipeline derives.** They live in
`OrderRecord._content` beside `status` and the lines. `ship_to` is a field of the stored order and has no
column, so an order stored before it reads back with none and the next Export Shipping read fills it. So a changed buyer stamps `changed_at`
exactly as a changed status does. D63's ruling that the ledger holds only what a sync can
justify is unchanged. This is one more thing a sync can justify. `Ledger.ingest` now carries
three fields across an upsert instead of one: `first_seen`, D63's own named exception, and a
buyer and a ship-to the new record did not mention. A paste built from `orderPaste.ts`'s narrower shape
must not erase a name a fetch already wrote. D63's "exactly one field is carried over" is
false the moment a second one is. It is rewritten in place below, rather than left to
contradict a paragraph three sections down.

**A new route, chosen for what it does NOT cost.** `POST /orders/names` writes names for
orders the ledger already knows, from search SUMMARIES alone. It makes zero detail calls, because
`fetch_open_orders` already parses a `buyerName` off every summary before it drops the known
ones. `/orders/fetch` keeps its documented `writes_nothing` contract. Its answer carries the
names a names-only pass would still need to write, filtered against what the ledger already
holds. So the steady-state press (everything already named) writes zero of them. Widening
`/orders/fetch` to write as a side effect was rejected. So was overloading `/orders/ingest`'s
`lines_required` shape to carry a name with no lines. Both put a write behind a route whose
contract says it has none.

**`{all_statuses: true}` is the explicit "every one" D91's refusal already asks for.** D91
built `statuses_required` on the ground that guessing a status vocabulary risks dropping an
order silently. Naming every status by hand is not a guess. It is the caller saying "all of
them" in as many words. The transport still refuses a call naming neither `statuses` nor
`all_statuses`, and a call naming both.

### The costs, named rather than discovered

**A two-year backfill spends the request budget D91 measured, repeatedly.** D91's own figures
are: a search page per 25 orders, a detail call per undetailed order, and no sleep in the
transport. They apply here at `LastTwoYears` scale rather than `LastThreeMonths`. So the screen
loops in batches and paces between them. A single unpaced call over two years of orders is the
same mistake D91 was written to retire.

**Homonyms share a walk.** The buyer key folds case and collapses whitespace. It uses the same
normalization `store/orders.py:order_key` already applies to the order key, for the same
reason. A display name is not a stable identity. Two people who happen to share a spelling
would otherwise be silently split by a stray capital. Folding them together means two
different people can open one merged walk. The mitigation is that every underlying order and
pull stays keyed and correct on its own record. The walk's detail header enumerates every
order number under the name, rather than presenting one undifferentiated pile. A homonym is
visible as "two orders" the moment the operator looks.

**The Ship stage draws the ship-to name.** D69's two-route split is untouched: `#/shipping` still answers
from a TCGplayer shipping export, and its rows carry the export's `FirstName` and `LastName` joined as
`ship_to`, never the street. The export has no buyer field, so a row shows its ship-to name, and also the
buyer when the ledger holds that order and the buyer is someone else. When the two are the same person, one
name shows. Reading the file writes the ship-to name onto each order the ledger holds (a number two
sources spell is skipped), and the screen says how many it saved. The file stays in memory for half an
hour as before. The name has no undo press: a newer read replaces it.

**The Orders screen draws it where packing reads.** An order's header shows "Ship to" its name when it differs
from the buyer; a buyer with one order shows it in the panel head. The buyer list still groups by the buyer's
name, since grouping by person is the buyer's job. Search matches the ship-to name too.

**The live feed fills it from the order detail.** `order_transport.project_order` keeps
`shippingAddress.recipientName` as `ship_to` (measured on a live detail, key names only) and drops the rest of
that object. The search summary is not read for it, so a known order that is skipped as already detailed gets
its ship-to from the Export Shipping read. The Fulfiller's packing screen leads with the ship-to name and shows
the buyer after it when they differ. The public demo clears `ship_to` (D295's mirror).

### What would reopen this

**The feed ceasing to carry `buyerName`** on a summary or a detail would leave every group
keyed by `order:<key>`, the existing no-name fallback. That is a transport fact rather than a
ruling to revisit. **A third person-field being wanted** is a new entry and not a widening of this one. Examples are an email address to send a message, or a shipping city to sanity-check a lane. This entry's whole argument is that a NAME is not a credential and not a delivery
instruction. That argument does not extend to either of those.
