## D295 — The public demo is the scrubbed real store

**Owner ruling: the published demo (`shivinate7.github.io/banchi`) is a full mirror of the real store, with people scrubbed. Its purpose is that peers browse the app as if in the owner's store, on a public link.** Before this entry, the demo showed an invented store. `scripts/demo-seed.py` writes real catalogue rows out of `fixtures/`. Which card sits in which box, what has sold, and who bought it were all made up (`docs/specs/demo.md` §2). The rulings:

- The full mirror is fine.
- Photos are capped at 512MB.
- An address never appears. Every address becomes 123 Demo Way.
- A buyer shows as first name plus last initial: "Jordan Miller" becomes "Jordan M.". A one-word name keeps that word. The initial is a Unicode letter.
- The mirror refreshes weekly, and on the owner's word (`make demo-mirror`).
- When the recorded wire digest differs from the tree's, the workflow holds the last good demo and publishes nothing.
- The mechanism is option 1, below.
- A CI check on every name and address costs more than it protects. So there is NO CI scrub check. The build itself rewrites every name and address. It ends with one plain assert.

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
- `build()` copies that snapshot into a working `BANCHI_HOME`. Then, inside one
  `Store().write()`:
  - **Buyers.** `short_name()` cuts every order's `buyer` to the first word plus the last
    word's initial: "Jordan Miller" is "Jordan M.", "Mary Jane Watson" is "Mary W.", and
    "Priya" stays "Priya". Two real buyers who share a short name show as one buyer in
    `#/orders`, which groups by name. The recorder groups by the same field, so its recorded
    walk sets still match the screen.
  - **Addresses.** The store holds no address, email or phone at all. The one file that
    ever carries one is TCGplayer's Shipping Export, and it is not part of the store
    (D61). So `write_shipping_export()` builds a NEW one from the ledger's own Ready to
    Ship orders. Order number, date, item count and value are real. Every name is the
    buyer's short name. Every street is "123 Demo Way". City, state and zip are
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
  `buyerName` field in the recorded bundle must be one word, or a first word plus one
  Unicode letter and a period. The shipping export's first and last name must read the same
  way together. A full surname is refused. Every address-shaped field, in the bundle or the
  shipping export, must be blank or exactly "123 Demo Way". It never prints a bad value: a
  failure here may be a real person's name.
- `commit_output()` copies the built bundle and photographs into the tracked
  `demo-assets/mirror/`. It refuses if the photographs are over the 512 MB cap.
- `--install` is CI's only mode. It copies the committed `demo-assets/mirror/` into
  `app/demo/bundle.json` and `app/public/demo/photos/`. It reads no store and touches no
  network.

**One walk-plan subject list change, forced by scale.** The invented demo seeds seven
orders and records every ticked subset (`WALK_PLAN_ORDERS = 7`, §5). The owner's real
ledger holds 834 orders. Recording every subset of that is not a
target to raise. It is a different shape of problem. `sweep_coverage` now reads only the
OPEN orders the recorded `/orders` GET returned. Every caller of `walkPlan` sends open
keys alone: `Fulfillment.tsx` filters `order.open`, and `Orders.tsx` walks
`walkableKeysAll` (D97, D220). A set holding a closed order is a question no screen ever
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
depend on it. The mirror has no determinism check, because rebuilding it twice
means reading the real store twice. Whether the real ledger's open-order count ever
exceeds `WALK_PLAN_ORDERS` on a future rebuild is unmeasured. If it does, the recorder
refuses loudly rather than guessing.

**Amended (L5).** Ruling (test-audit plan, Q5): cut the old seed guards. `demo-seed`/`demo-record`/`demo` stay, a generator anyone can run on demand.
C4 named three guards over that seed's own bundle. `demo-determinism-selftest` ran in
`make check`. `demo-determinism` ran on every demo publish, `.github/workflows/demo.yml`.
`demo-freshness` gated neither. All three retire together. `demo-determinism.py` and
`demo-freshness.py` are gone from the tree. None of the three ever tested the mirror this
entry publishes. `--install` still writes `app/demo/bundle.json`, rebuilt from the committed
chunks, because `app/tests/demo-coverage.spec.ts` reads one file.

**Amended (the hold).** The committed mirror is a recording, and a recording goes stale when a
wire shape moves. Chunk 0 carries the wire digest it was recorded against. The workflow's
`hold` job runs `scripts/demo-hold.py` and compares that digest with the tree's
(`demo-record.py`'s `wire_digest()`). On a difference, or when the chunk records none,
`build` and `deploy` are skipped, the last good demo stays up, and a notice names both
digests. A hold is a skip and not a failure, so the alarm job stays quiet. The next refresh
ends it.

**Amended (standing grant, weekly refresh).** Ruling: the demo's data refreshes WEEKLY and
AUTOMATICALLY, with auto-merge. The owner can still refresh on demand with `make demo-mirror`. A mirror-only PR auto-merges on green CI through the merge tool, with
no word asked each time. The grant covers only a PR with head `demo/mirror-refresh`, opened by
`scripts/demo-mirror-daily.py` after the scrub assert and the fence, whose whole diff is under
`demo-assets/mirror/`. `make demo-mirror-agent` installs the weekly job on the owner's Mac (Sunday, 04:30). The safety
is a fence in `scripts/demo-mirror-daily.py`: it refuses to merge a PR whose diff touches any path
outside `demo-assets/mirror/`. `assert_scrubbed` still gates publishing, and a failure or any error
publishes nothing. The grant is recorded in D42's grant terms too.
