## D193 — The ledger holds the buyer's name, because a hand walks drawers per person

**The owner walks drawers per PERSON, not per order number, and the ledger has never named one.** D63 built the ledger with two rulings that read as a single PII stance — *"No buyer, no address, no email. The ledger holds a SKU, a quantity and what the feed called the card"* — and D69's paste projection enforces the same shape at the browser. **That was never an owner ruling; it was a session's design, made under D63/D69's own scope, at a moment nobody had asked what the screen should be for.** The owner's outcome, stated 2026-09-13, is a hand working through drawers for one buyer at a time; a list of order numbers with no name on it cannot be walked that way, and D63's own working agreement — *"think in outcomes, not
processes"* — is what asks whether the exclusion still served anybody once the screen existed.

### The owner's rulings, 2026-09-13

1. **Store the buyer's display name only.** Address, email, payment, the transaction
   breakdown and tracking stay excluded, by the same allowlist mechanism D63 and D69 already
   built — nothing about how PII is kept OUT changes; one field moves from the excluded side
   of the line to the kept side.
2. **A one-time backfill**, `LastTwoYears` (the store is younger than that), every status,
   skip-known, looped by the screen until `remaining == 0`. After that the ordinary press is
   an APPEND: all statuses, skip-known, one pass.
3. **Clicking a buyer opens one merged walk over all their open orders**, and the screen must
   make it obvious when a person has more than one — an `N orders` pill on the row, the
   orders enumerated in the detail header.

### Why this reopens D63 and D69 rather than widening them quietly

**"No buyer, no address, no email" was one sentence doing two jobs, and only one of them was ever argued.** D63's own text gives the argument for the second and third: `inventory/` is
gitignored, which keeps a bearer instrument or a mailing address out of a commit — a reason
that says nothing about a NAME, which is not a credential and not a delivery instruction. The
first clause rode along on that argument without one of its own, and it stood for three weeks
because nothing on the commit path reads whether an exclusion still matches what the owner
asked for — the same gap D63's amended working agreement now names directly: *"if a decision
made seems stale or overly bearing, flag it and ask to solve it the right way."* This is that
flag, and the owner's word is what it waited for.

**What is unchanged, and it is the part that was doing real work.** Three allowlists are the
mechanism, not the exclusion: `server/order_transport.py`'s `project_summary` / `project_order`,
`server/capture_server.py`'s `ORDER_INGEST_ORDER_FIELDS`, and `app/src/orderPaste.ts`'s
`ORDER_KEEP`. Each still refuses everything it refused yesterday — `buyerName`'s sibling
fields (`shippingAddress`, `email`, payment, the transaction breakdown) are named and dropped
at the same three seams, by the same code, and T7's key-set assertions still pin the shape
whole rather than by exception. Adding one field to an allowlist that already existed is the
opposite of loosening a boundary that had none; a boundary with no allowlist at all would be
the license this entry declines to take.

### What is added, and its register

**`buyer` is feed-owned content, not a fact this pipeline derives.** It lives in
`OrderRecord._content` beside `status` and the lines, so a changed buyer stamps `changed_at`
exactly as a changed status does — D63's ruling that the ledger holds only what a sync can
justify is unchanged, this is one more thing a sync can justify. `Ledger.ingest` now carries
two fields across an upsert instead of one: `first_seen`, D63's own named exception, and a
buyer the new record did not mention — a paste built from `orderPaste.ts`'s narrower shape
must not erase a name a fetch already wrote. D63's "exactly one field is carried over" is
false the moment a second one is, and is rewritten in place below rather than left to
contradict a paragraph three sections down.

**A new route, chosen for what it does NOT cost.** `POST /orders/names` writes names for
orders the ledger already knows, from search SUMMARIES alone — zero detail calls, because
`fetch_open_orders` already parses a `buyerName` off every summary before it drops the known
ones. `/orders/fetch` keeps its documented `writes_nothing` contract; its answer carries the
names a names-only pass would still need to write, filtered against what the ledger already
holds, so the steady-state press — everything already named — writes zero of them. Widening
`/orders/fetch` to write as a side effect, or overloading `/orders/ingest`'s `lines_required`
shape to carry a name with no lines, were both rejected for putting a write behind a route
whose contract says it has none.

**`{all_statuses: true}` is the explicit "every one" D91's refusal already asks for.** D91
built `statuses_required` on the ground that guessing a status vocabulary risks dropping an
order silently; naming every status by hand is not a guess, it is the caller saying "all of
them" in as many words, and the transport still refuses a call naming neither `statuses` nor
`all_statuses` and a call naming both.

### The costs, named rather than discovered

**A two-year backfill spends the request budget D91 measured, repeatedly.** D91's own figures
— a search page per 25 orders, a detail call per undetailed order, no sleep in the transport —
apply here at `LastTwoYears` scale rather than `LastThreeMonths`, so the screen loops in
batches and paces between them; a single unpaced call over two years of orders is the same
mistake D91 was written to retire.

**Homonyms share a walk.** The buyer key folds case and collapses whitespace — the same
normalization `store/orders.py:order_key` already applies to the order key, for the same
reason: a display name is not a stable identity, and two people who happen to share a spelling
would otherwise be silently split by a stray capital. Folding them together means two
different people can open one merged walk; the mitigation is that every underlying order and
pull stays keyed and correct on its own record, and the walk's detail header enumerates every
order number under the name rather than presenting one undifferentiated pile — a homonym is
visible as "two orders" the moment the operator looks.

**The Ship stage still draws no name.** D69's two-route split is untouched: `#/shipping`
answers from a TCGplayer shipping export that has never carried a buyer field and never will
by this change, so nothing here gives that screen a name to draw.

### What would reopen this

**The feed ceasing to carry `buyerName`** on a summary or a detail would leave every group
keyed by `order:<key>` — the existing no-name fallback — and is a transport fact rather than a
ruling to revisit. **A second person-field being wanted** — an email address to send a
message, a shipping city to sanity-check a lane — is a new entry and not a widening of this
one: this entry's whole argument is that a NAME is not a credential and not a delivery
instruction, and that argument does not extend to either of those.
