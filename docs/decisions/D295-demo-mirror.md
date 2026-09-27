## D295 — The public demo is the owner's real store, scrubbed

**What changed.** Before this entry, the published demo (`shivinate7.github.io/banchi`)
showed an INVENTED store. `scripts/demo-seed.py` writes real catalogue rows out of
`fixtures/`. But which card sits in which box, what has sold, and who bought it were all
made up (`docs/specs/demo.md` §2). As of this entry, the owner has ruled that the demo
should be a FULL MIRROR of the real store instead, with people scrubbed. The owner's own
words:

- "full mirror is fine"
- photos capped "to just 512mb"
- "mirror all … just have all names be Jane Doe and all addresses be 123 Demo Way if that
  is easy?"
- Buyers numbered "Jane Doe N", one stable N per distinct buyer, because `#/orders` groups
  by name: "ah yes agreed"
- On the mechanism: "ah yeah 1 is fine if that is what the builder ocmes back with too" —
  see below
- On the scrub check: "I meant a ci on every name and address is too excessive it should be
  more straightforward." So there is NO CI scrub check. The build itself overwrites every
  name and address. It ends with one plain assert.

**The mechanism (the owner's "option 1").** A `make` target builds the scrubbed mirror
LOCALLY, from a COPY of the owner's store, on the owner's own Mac. Only the scrubbed
output — the recorded bundle and the QR-cleared photographs — is committed, under
`demo-assets/mirror/`. CI never reads a store. It installs that committed output
(`make demo-mirror-install`) and builds, exactly as `make demo-static` always has.

`scripts/demo-mirror.py` is the whole mechanism:

- `snapshot()` reads the owner's live `inventory/store.sqlite` through a read-only
  `sqlite3` backup, never a plain file copy of a live WAL database. It writes into
  gitignored `demo-mirror/`. The owner's real data never leaves this directory. It is
  never committed — `.gitignore` marks it beside `demo`, `app/demo` and `dist-demo`.
- `build()` copies that snapshot into a working `PKMNSCAN_HOME`. Then, inside one
  `Store().write()`:
  - **Buyers.** `jane_does()` numbers every distinct buyer "Jane Doe N". Oldest first
    order wins the lowest N. The numbering stays stable across rebuilds. Every order's
    `buyer` field is overwritten.
  - **Addresses.** The store holds no address, email or phone at all. The one file that
    ever carries one is TCGplayer's Shipping Export, and it is not part of the store
    (D61). So `write_shipping_export()` builds a NEW one from the ledger's own Ready to
    Ship orders. Order number, date, item count and value are real. Every name is the
    buyer's Jane Doe number. Every street is "123 Demo Way". City, state and zip are
    blank.
  - **Photographs.** The rule picks cards on hand first, then the rest, each by (box,
    index), until the next photograph would cross the 512 MB cap. Every one is
    QR-checked at full resolution before it is cropped, because a live code card is a
    bearer instrument (D70). A QR refusal is dropped silently rather than published,
    exactly as `demo-photos.py` and `demo-extra-real.py` already do.
- `record()` runs the ordinary `demo-record.py`, in a new `--offline` mode. The server's
  own socket `connect` is patched before its first import to refuse anything not
  loopback. A mirror holds every SKU the owner ever stocked. `#/product`'s history route
  reads TCGplayer live for any SKU its archive lacks. Swept over thousands of SKUs, that
  would be thousands of live requests to a host the owner allows from a browser only
  (D216). Offline makes that impossible rather than merely undesired. A read that needed
  the network answers an error and is never recorded — the same "best effort" rule the
  invented demo already follows for price histories.
- `assert_scrubbed()` is THE ONE CHECK, per the owner's ruling above. Every `buyer` or
  `buyerName` field in the recorded bundle must match `^Jane Doe \d+$`. Every
  address-shaped field, in the bundle or the shipping export, must be blank or exactly
  "123 Demo Way". It never prints a bad value: a failure here may be a real person's
  name.
- `commit_output()` copies the built bundle and photographs into the tracked
  `demo-assets/mirror/`. It refuses if the photographs are over the 512 MB cap.
- `--install` is CI's only mode. It copies the committed `demo-assets/mirror/` into
  `app/demo/bundle.json` and `app/public/demo/photos/`. It reads no store and touches no
  network.

**One walk-plan subject list change, forced by scale.** The invented demo seeds seven
orders and records every ticked subset (`WALK_PLAN_ORDERS = 7`, §5). The owner's real
ledger holds 834 orders, measured 2026-09-26. Recording every subset of that is not a
target to raise. It is a different shape of problem. `sweep_coverage` now reads only the
OPEN orders the recorded `/orders` GET returned. Every caller of `walkPlan` sends open
keys alone: `Fulfillment.tsx` filters `order.open`, and `Orders.tsx` walks
`walkableKeysAll` (D96, D220). A set holding a closed order is a question no screen ever
asks. The recorder still refuses outright past `WALK_PLAN_ORDERS` open orders. A mirror
whose open-order count exceeds that needs a different recording strategy, not a raised
constant. That is left as an open question below.

**Kept, unchanged.** The opsec/QR guard stays ARMED. `scripts/guard-opsec.sh` and
`scripts/githooks/pre-commit`'s re-decode both now cover the new
`demo-assets/mirror/photos/` path, on the curator's own precedent (D70). The 512 MB
photo cap is the owner's own number. `demo-seed`/`demo-record`/`demo` — the invented
flow — are left in place, for anyone who wants a store with no real photographs to
iterate against. `demo-static` no longer builds from them. It now depends on
`demo-mirror-install`.

**Left open, not blocking.** A parallel lane, `ux/stock-images`, is meant to put stock
image URLs on route responses, so a recorded bundle carries them. This entry does not
depend on it. `make demo-determinism` still tests the OLD invented seed's determinism,
not the mirror's. The mirror has no matching check yet, because rebuilding it twice
means reading the real store twice. Whether the real ledger's open-order count ever
exceeds `WALK_PLAN_ORDERS` on a future rebuild is unmeasured. If it does, the recorder
refuses loudly rather than guessing.
