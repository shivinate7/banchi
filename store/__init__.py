"""The master store — inventory, the identification cache, and the standing queues.

Runs are immutable inputs; this is the thing they feed. Deleting a run directory must never
cost money or state, which is only true if the answers already paid for and the decisions
already made live somewhere else. That somewhere is here.

    inventory/
      inventory.json        MASTER. Cards at positions, boxes, per-SKU listing counts.
      history.jsonl         Append-only event log. Never rewritten.
      identifications.json  The cache. Answers already paid for.
      review.json           Standing main review queue. Survives runs.
      parked.json           Standing low-value queue. Survives runs.
      .lock                 Exclusive lock file.

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

NOT SQLITE. D13 settles inventory as server-side JSON. D15's SQLite is the read-only
*catalog* index at build step 9 and is a different thing entirely — a later session that
"upgrades" inventory to SQLite is re-litigating D13, not improving it.

TWO WRITERS, ONE OWNER. Step 5's capture server writes here too. It uses the same lock and
the same atomic replace; it is a second writer, not a second owner.

READS NEED NO LOCK; WRITES DO. Every file is replaced atomically, so a reader sees the whole
old file or the whole new one and never a torn one — that is what `os.replace` buys, and it
is why `read()` is lock-free. What atomicity does NOT prevent is a lost update: two writers
each reading, each modifying, each writing back means the second silently erases the first.
So `write()` takes the exclusive lock AND re-reads from disk inside it. Re-reading is the
half that actually matters; a lock around a stale snapshot loses the update just as quietly.

`history.jsonl` is append-only and is the audit trail. D10 makes it worth keeping: positions
are never renumbered and sold cards leave permanent gaps, so the history IS inventory truth
over time, in a way the current-state file cannot be.
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
    PUSHED,
    SOLD,
    STAGED,
    STATES,
    Box,
    Card,
    Inventory,
    Listing,
)
from store.queues import Queue, QueueEntry  # noqa: F401
from store.session import Snapshot, Store  # noqa: F401
