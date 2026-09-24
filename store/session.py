"""Opening the store: a lock-free read, or a locked read-modify-write that is one transaction.

    snapshot = Store().read()                  # no lock; one consistent view of every table
    with Store().write() as s:                 # lock held, transaction open, rows loaded on demand
        s.inventory.set_state(key, store.IDENTIFIED)
        s.inventory.listing(sku).bump(store.PUSHED)

Two writes because there are two subjects. `set_state` moves ONE CARD between `store.STATES`
— `captured`, `identified`, `sold` — and `bump` moves a QUANTITY on one SKU's listing
through `store.LISTING_STAGES`. The second line used to read
`s.inventory.set_state(key, store.PUSHED)`, which now raises `UnknownState`: `pushed`,
`staged` and `live` are counts against a SKU rather than states a card wears (D7 amended),
because every unsold copy of a SKU is equally sellable and an address there would be a
fiction the pull then has to honour.

THE RE-READ INSIDE `write()` IS STILL THE POINT, and it is cheaper than it was. A lock around
a snapshot taken before the lock was acquired loses updates exactly as quietly as no lock at
all: you would be writing back state that predates whatever the other writer just committed.
So the snapshot handed to the block is built INSIDE the lock, on a transaction opened inside
the lock — and since D88 it is built lazily: a capture reads the box it is capturing into and
the one `capture_id` it is replaying, and never the other 99,000 cards. `store/rows.py` is
what makes `s.inventory.cards` a dict to every caller and a set of queries to the database.

EVERYTHING A SESSION TOUCHED IS COMMITTED ON A CLEAN EXIT AS ONE TRANSACTION, AND NOTHING IS
WRITTEN ON AN EXCEPTION. That sentence used to have a paragraph after it — five files, each
atomic alone, "the set of them is not one transaction", the ledger written last so a torn
write lost the order feed rather than the inventory, "a decision nobody has argued". D88
argued it. There is one file, `BEGIN IMMEDIATE` is issued before the block runs and `COMMIT`
after `flush` has written every table's diff, so a kill anywhere in between leaves the store
as it was in every table at once, and the history rows describing the change commit with the
change rather than after it. The ordering the old header spent its length on is gone because
the thing it ordered is gone.

WHAT IS NOT IN THE TRANSACTION, and it is the same list it always was: photographs and
sidecars under `captures/`, and `codes.jsonl`. Callers write those inside the block on the
strength of the flock, and a crash between a file write and the commit still leaves a file
the store does not describe — `do_delete_box`'s docstring carries the money rule for that
case and it is unchanged. The lock is why the flock survives D88 at all.
"""

from __future__ import annotations

import contextlib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from store import db, files
from store.cache import Cache
from store.master import Inventory
from store.orders import Ledger
from store.pricearchive import PriceArchive
from store.postings import Postings
from store.queues import MAIN, PARKED, Queue
from store.readings import Readings
from store.rows import Rows
from store.sendclaims import SendClaims
from store.submissions import Submissions


@dataclass
class Snapshot:
    """Everything in the store at one moment. Each field loads only what it is asked for."""

    directory: Path
    inventory: Inventory
    cache: Cache
    review: Queue
    parked: Queue
    ledger: Ledger
    # THE CARDS A LIVE RUN HAS ALREADY CLAIMED (D174). It is in the snapshot
    # rather than beside it for the one reason that makes the claim worth anything: the check
    # against it and the write of it have to be the SAME transaction as the cache consult that
    # decides what is being bought, and D88 is what makes that one transaction.
    submissions: Submissions
    # THE SKUS A PRESS TO TCGPLAYER IS SENDING (`D-one-press-sends-and-makes-live`), in the
    # snapshot for `submissions`' reason: `cli/cmd_emit.py` checks and writes it in the SAME
    # transaction that counts the copies as sent, so two presses cannot both decide first.
    send_claims: SendClaims
    # THE MARKET READING `pkmnscan readings adopt --write` LAST CACHED, PER SKU
    # (D189). Bound like every other table so a `Store.write()` from `readings
    # adopt` commits it atomically with everything else D88 already protects; every other
    # writer in this package leaves it untouched.
    readings: Readings
    # THE PRICE-HISTORY ARCHIVE (D219): every bucket `pkmnscan archive
    # sweep --write` has ever read, kept past the source's own 357-day ceiling. In the
    # snapshot for the same reason `readings` is: a `Store.write()` from `archive sweep`
    # commits it atomically with everything else D88 already protects.
    archive: PriceArchive
    # EVERY `TCG Marketplace Price` THIS STORE HAS EVER POSTED (D243).
    # An accumulator like `Inventory.events`, not a `Rows` table — see `store/postings.py`
    # for why this ledger must never go through `Rows`'s delete-then-upsert flush. Flushed by
    # `Store.write()` with `db.append_postings`, in the same transaction as everything else
    # a press touches.
    postings: Postings

    def queue(self, name: str) -> Queue:
        return self.review if name == MAIN else self.parked

    @property
    def queue_summary(self) -> str:
        """What every run report leads with (v2 §5.5)."""
        return " | ".join([self.review.summary, self.parked.summary])

    @property
    def tables(self) -> List[Rows]:
        """Every mapping a flush writes, in a fixed order."""
        return [
            self.inventory.cards,
            self.inventory.boxes,
            self.inventory.listings,
            self.cache.entries,
            self.review.entries,
            self.parked.entries,
            self.ledger.orders,
            self.ledger.fulfilment,
            self.submissions.entries,
            self.send_claims.entries,
            self.readings.entries,
            self.readings.sources,
            self.archive.entries,
            self.archive.sources,
        ]


class Store:
    def __init__(self, directory: Optional[Path] = None):
        self.directory = Path(directory) if directory else files.inventory_dir()

    # ------------------------------------------------------------------------ paths

    @property
    def db_path(self) -> Path:
        return db.path(self.directory)

    # ------------------------------------------------------------------------ reading

    def _snapshot(self, conn, *, track: bool) -> Snapshot:
        def bound(spec, table, fixed=None):
            return Rows(spec, source=db.source(conn, table, fixed), track=track)

        return Snapshot(
            directory=self.directory,
            inventory=Inventory(
                cards=bound(Inventory.CARDS, "cards"),
                boxes=bound(Inventory.BOXES, "boxes"),
                listings=bound(Inventory.LISTINGS, "listings"),
                # READ INSIDE THE SAME TRANSACTION AS THE TABLES (D145), so the
                # mark a session allocates against is the mark as of the moment its rows were
                # read. Read outside it, a box could be created between the two and this
                # session would hand its id out a second time.
                box_ids_issued=db.box_ids_issued(conn),
                # READ IN THE SAME TRANSACTION, for `box_ids_issued`' reason one line up,
                # and NEVER WRITTEN BACK: `pkmnscan cards photos` is the only writer, so a
                # session that carried a stale None could not un-stamp the store.
                photos_relocated=db.photos_relocated(conn),
            ),
            cache=Cache(entries=bound(Cache.ENTRIES, "identifications")),
            review=Queue(name=MAIN, entries=bound(Queue.ENTRIES, "queues", {"queue": MAIN})),
            parked=Queue(name=PARKED, entries=bound(Queue.ENTRIES, "queues", {"queue": PARKED})),
            ledger=Ledger(
                orders=bound(Ledger.ORDERS, "orders"),
                fulfilment=bound(Ledger.FULFILMENT, "fulfilment"),
            ),
            submissions=Submissions(entries=bound(Submissions.ENTRIES, "submissions")),
            send_claims=SendClaims(entries=bound(SendClaims.ENTRIES, "send_claims")),
            readings=Readings(
                entries=bound(Readings.ENTRIES, "readings"),
                sources=bound(Readings.SOURCES, "readings_sources"),
            ),
            archive=PriceArchive(
                entries=bound(PriceArchive.ENTRIES, "price_history"),
                sources=bound(PriceArchive.SOURCES, "price_history_sources"),
            ),
            # NOT `bound()` — nothing to load, only to append to, exactly like
            # `snapshot.inventory.events` beside it. A read-only `Store.read()` snapshot gets
            # one too, empty and unused: nothing here ever calls `.record()` on it, since
            # nothing writes through a lock-free snapshot.
            postings=Postings(),
        )

    def read(self) -> Snapshot:
        """A lock-free snapshot. One read transaction, so every lazy load sees one moment.

        WAL is what makes this safe without the flock: a reader sees the database as of the
        last commit before its transaction began and never a half-written one, and it holds
        no lock a writer waits on. The transaction ends when the snapshot's connection is
        collected, which for a request-scoped snapshot is the end of the request.
        """
        conn = db.connect(self.directory)
        conn.execute("BEGIN")
        return self._snapshot(conn, track=False)

    # ------------------------------------------------------------------------ writing

    @contextmanager
    def write(self, timeout: float = files.LOCK_TIMEOUT_SECONDS):
        """Exclusive, read inside the lock, committed whole on a clean exit or not at all."""
        with files.exclusive(self.directory, timeout=timeout):
            conn = db.connect(self.directory, locked=True)
            try:
                conn.execute("BEGIN IMMEDIATE")
                snapshot = self._snapshot(conn, track=True)
                yield snapshot
                for rows in snapshot.tables:
                    db.flush_rows(rows)
                db.append_events(conn, snapshot.inventory.events)
                # SAME TRANSACTION, SAME REASON: a posted price and the inventory/listing
                # writes that went with it land together or not at all (D243).
                db.append_postings(conn, snapshot.postings.entries)
                # BEFORE THE COMMIT, so a box row and the mark that says its id is spent land
                # together or not at all. `set_box_ids_issued` never lowers the stored figure.
                db.set_box_ids_issued(conn, snapshot.inventory.box_ids_issued)
                conn.execute("COMMIT")
                snapshot.inventory.events = []
                snapshot.postings.entries = []
            except BaseException:
                # Best effort on a connection that may already be dead; the raise is the point.
                with contextlib.suppress(Exception):
                    conn.execute("ROLLBACK")
                raise
            finally:
                conn.close()

    def history(self):
        """Every event ever appended, oldest first. Refuses the log over one unreadable row."""
        conn = db.connect(self.directory)
        try:
            return db.history(conn)
        finally:
            conn.close()

    def history_at(self, key: str):
        """The events that could bear on one position, oldest first. `history()`'s scoped
        sibling (D191): the reversal readers each want one card's own
        lines plus its box's `renumbered` markers, not a full-table load filtered in
        Python. See `db.events_at`'s docstring for why the scope is the box and not the
        bare position.
        """
        conn = db.connect(self.directory)
        try:
            return db.events_at(conn, key)
        finally:
            conn.close()

    def named_events(self, event: str):
        """Every event of one kind, newest first. `buried()`'s general form.

        IT EXISTS BECAUSE A SECOND READER ARRIVED (D145): `box_deleted` is the
        only record of what a departed drawer was called, and `server/pipeline_routes.py`
        joins it onto a run that outlived its box. Copying `buried()` for it would have been
        two methods differing by a string literal.
        """
        conn = db.connect(self.directory)
        try:
            return db.events_named(conn, event)
        finally:
            conn.close()

    def buried(self):
        """Every `buried` event, newest first (D134). `history()`'s narrower sibling, for
        `#/graveyard`'s read: a whole box's departed records, without loading every other
        event this store has ever written to filter them in Python."""
        conn = db.connect(self.directory)
        try:
            return db.events_named(conn, "buried")
        finally:
            conn.close()
