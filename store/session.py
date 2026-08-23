"""Opening the store: a lock-free read, or a locked read-modify-write.

    snapshot = Store().read()                  # no lock; sees a whole file, never a torn one
    with Store().write() as s:                 # lock held, state re-read inside it
        s.inventory.set_state(key, store.IDENTIFIED)
        s.inventory.listing(sku).bump(store.PUSHED)

Two writes because there are two subjects. `set_state` moves ONE CARD between `store.STATES`
— `captured`, `identified`, `sold` — and `bump` moves a QUANTITY on one SKU's listing
through `store.LISTING_STAGES`. The second line used to read
`s.inventory.set_state(key, store.PUSHED)`, which now raises `UnknownState`: `pushed`,
`staged` and `live` are counts against a SKU rather than states a card wears (D7 amended),
because every unsold copy of a SKU is equally sellable and an address there would be a
fiction the pull then has to honour.

The re-read inside `write()` is not belt-and-braces, it is the point. A lock around a
snapshot taken before the lock was acquired loses updates exactly as quietly as no lock at
all: you would be writing back state that predates whatever the other writer just committed.

Everything a session touched is written on a clean exit, and nothing is written on an
exception — so a crash halfway through a state transition leaves the store as it was.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from store import files
from store.cache import Cache
from store.master import Inventory
from store.queues import MAIN, PARKED, Queue

INVENTORY_FILE = "inventory.json"
HISTORY_FILE = "history.jsonl"
CACHE_FILE = "identifications.json"


@dataclass
class Snapshot:
    """Everything in the store at one moment."""

    directory: Path
    inventory: Inventory
    cache: Cache
    review: Queue
    parked: Queue

    def queue(self, name: str) -> Queue:
        return self.review if name == MAIN else self.parked

    @property
    def queue_summary(self) -> str:
        """What every run report leads with (v2 §5.5)."""
        return " | ".join([self.review.summary, self.parked.summary])


class Store:
    def __init__(self, directory: Optional[Path] = None):
        self.directory = Path(directory) if directory else files.inventory_dir()

    # ------------------------------------------------------------------------ paths

    @property
    def inventory_path(self) -> Path:
        return self.directory / INVENTORY_FILE

    @property
    def history_path(self) -> Path:
        return self.directory / HISTORY_FILE

    @property
    def cache_path(self) -> Path:
        return self.directory / CACHE_FILE

    def queue_path(self, name: str) -> Path:
        from store.queues import FILENAMES

        return self.directory / FILENAMES[name]

    # ------------------------------------------------------------------------ reading

    def read(self) -> Snapshot:
        """A lock-free snapshot. Safe because every write is an atomic replace."""
        return Snapshot(
            directory=self.directory,
            inventory=Inventory.parse(files.read_json(self.inventory_path)),
            cache=Cache.parse(files.read_json(self.cache_path)),
            review=Queue.parse(MAIN, files.read_json(self.queue_path(MAIN))),
            parked=Queue.parse(PARKED, files.read_json(self.queue_path(PARKED))),
        )

    # ------------------------------------------------------------------------ writing

    @contextmanager
    def write(self, timeout: float = files.LOCK_TIMEOUT_SECONDS):
        """Exclusive, re-read inside the lock, written whole on a clean exit."""
        with files.exclusive(self.directory, timeout=timeout):
            snapshot = self.read()
            yield snapshot
            files.write_json(self.inventory_path, snapshot.inventory.to_payload())
            files.write_json(self.cache_path, snapshot.cache.to_payload())
            files.write_json(self.queue_path(MAIN), snapshot.review.to_payload())
            files.write_json(self.queue_path(PARKED), snapshot.parked.to_payload())
            # Appended last: the log describes what the files above now say, and a crash
            # between the two should under-report history rather than claim a state the
            # master file never reached.
            for event in snapshot.inventory.events:
                files.append_jsonl(self.history_path, event)
            snapshot.inventory.events = []

    def history(self):
        return files.read_jsonl(self.history_path)
