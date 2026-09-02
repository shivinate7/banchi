"""The master store — inventory, the identification cache, the standing queues, the order
ledger and the history, in one SQLite file (D88).

Runs are immutable inputs; this is the thing they feed. Deleting a run directory must never
cost money or state, which is only true if the answers already paid for and the decisions
already made live somewhere else. That somewhere is here.

    inventory/
      store.sqlite          MASTER. Cards at positions, boxes, per-SKU listing counts, the
                            paid answers, both standing queues, the order ledger and every
                            history event — one table each, one transaction per write.
      store.sqlite-wal      SQLite's own write-ahead log and shared-memory index, beside
      store.sqlite-shm      the file. They ARE the database while a server is up.
      legacy-json/          the six files this store was migrated FROM on first open —
                            inventory.json, identifications.json, review.json, parked.json,
                            orders.json, history.jsonl — moved aside whole and read by
                            nothing (D86's rule for a legacy file). MIGRATED.json beside
                            them says what was imported and how to reverse it.
      prices.json           the pricing corpus (D86). Still a file: it is the operator's
                            answers rather than the store's state, and `pipeline/corpus.py`
                            owns it.
      codes.jsonl           the code ledger (C8). Still a file, upserted under this lock.
      .lock                 Exclusive lock file — the WRITER's lock, held around every
                            transaction and around the file writes a session makes beside it.

TWO KINDS OF STATE, AND THEY ARE ABOUT DIFFERENT SUBJECTS. A `Card` wears one of `STATES`
— `captured`, `identified`, `sold` — which describes one physical object at one position.
A `Listing` holds a count at each of `LISTING_STAGES` — `pushed`, `staged`, `live` — which
describes a SKU's progress through TCGplayer.

The three stages used to be card states too, so listing progress was an address: four of
seven copies were sellable and three were not, for no physical reason. The owner's ruling
is that copies of one SKU are fungible, so they moved onto the SKU as quantities and WHICH
copies back them is deliberately unrecorded. `check_state` refuses them, which is what
turns the old `set_state(key, PUSHED)` into a raised `UnknownState` rather than a silent
per-position flag. `Inventory.parse` migrates a v1 file: a card wearing a stage becomes
`identified` and hands that stage to its SKU as a count.

SQLITE, AS OF D88 — AND THE PARAGRAPH THIS REPLACES SAID THE OPPOSITE FOR THREE WEEKS. It
read "NOT SQLITE. D13 settles inventory as server-side JSON ... a later session that
'upgrades' inventory to SQLite is re-litigating D13, not improving it." D88 re-litigated it
in the open, with the argument D13 never made: the five JSON files were each replaced
atomically and the SET of them was not one transaction, and every capture re-read and
rewrote every card in the store. D13's sentence — one truth, server-side, on the Mac, read
and written through the capture server — is unchanged; what changed is the file format
behind it. D15's SQLite for the read-only catalog is still a different thing: that one is
an index built from a snapshot, this one is the store of record.

TWO WRITERS, ONE OWNER. Step 5's capture server writes here too. It uses the same lock and
the same transaction; it is a second writer, not a second owner.

READS NEED NO LOCK; WRITES DO. WAL mode is what buys the first half: a reader sees the store
as of the last commit and never a torn one, and holds nothing a writer waits on. What a
transaction does NOT prevent is a lost update: two writers each reading, each modifying,
each writing back means the second silently erases the first. So `write()` takes the
exclusive lock AND opens its transaction inside it, and every row a session touches is
read inside that transaction. Re-reading is the half that actually matters; a lock around
a stale snapshot loses the update just as quietly.

THE HISTORY IS A TABLE NOW AND STILL APPEND-ONLY, and it is the audit trail. D10 makes it
worth keeping: positions are never renumbered and sold cards leave permanent gaps IN THE
INDEX — D58 closes the gap in the LABEL and touches nothing here — so the history IS
inventory truth over time, in a way the current-state tables cannot be. Since D88 the rows
describing a change commit in the same transaction as the change, where `history.jsonl`
was appended after the files and could under-report a change the store had made.
"""

from store.files import (  # noqa: F401
    HOME_ENV,
    LockTimeout,
    StoreError,
    home,
    inventory_dir,
    runs_dir,
)
from store.cache import Cache, CacheEntry  # noqa: F401
from store.master import (  # noqa: F401
    BOX_CLOSED,
    BOX_OPEN,
    CAPTURED,
    IDENTIFIED,
    LISTING_STAGES,
    LIVE,
    PHOTO_RECLAIMED,
    PUSHED,
    SOLD,
    STAGED,
    STATES,
    Box,
    Card,
    CardNotSold,
    Inventory,
    Listing,
)
from store.queues import Queue, QueueEntry  # noqa: F401
from store.session import Snapshot, Store  # noqa: F401
