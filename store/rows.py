"""A keyed table of records that behaves as a dict and loads only what is asked for (D88).

`Inventory.cards`, `Cache.entries`, `Queue.entries` and the ledger's two maps were plain
dicts, parsed whole out of a JSON file on every read. That was the cost D88 measured: every
capture re-read and re-serialised every card in the store, and at ~48,000 cards the write
cycle crossed the feeder's own cadence. This class is what lets those fields stay dicts to
every caller — `.get`, `[]`, `in`, `del`, `.items()`, `.pop` — while a session bound to the
database touches only the rows it names.

TWO BACKINGS, ONE CONTRACT.

  memory   `Rows(spec, objects=...)`. A dict with a query vocabulary. What `Inventory()`
           and `Inventory.parse` build, what T7 drives directly, what the legacy JSON
           import produces. Always complete.
  bound    `Rows(spec, source=...)`. Rows arrive from a `Source` one at a time — a point
           lookup, a `where` over an indexed column, a `select` of columns with no object
           built at all — and are cached here so a caller that got an object back and
           mutated it is writing to the same object the flush will read. Iterating the
           whole mapping loads the whole table, which is what iterating a whole table
           should cost, and nothing less than that does.

WHAT A FLUSH WRITES IS A DIFF, NOT THE TABLE. `changes()` re-dumps every LOADED object and
compares it to the shape it had when it was read, so a session that read one card and
changed nothing writes nothing, and a session that read one card and changed it writes one
row. The baseline is `dump(parse(payload))` rather than the stored text, so a record
carrying a field its dataclass no longer declares is not rewritten on every session for
the crime of being old — `Inventory.parse`'s annotation filter drops such a field on
reload and the baseline agrees with what was reloaded.

NO SQL HERE, NO I/O, NO IMPORT FROM THE REST OF THE PACKAGE. `store/master.py` keeps its
isolation from disk — its own comment beside `BadPosition` explains why it will not import
`store/files.py` — and this module is the one thing it is allowed to import, because it is
a container. The database side is `store/db.py`, which implements `Source` over sqlite3
and is the only module that knows a table's name.

THE `Source` CONTRACT, duck-typed rather than declared, stated here once:

    get(key) -> Optional[str]               the stored payload text, or None
    has(key) -> bool
    count() -> int
    all() -> Iterable[(key, text)]          every row, ordered by key
    where(equals) -> Iterable[(key, text)]  rows whose indexed columns equal `equals`
    select(columns, equals) -> Iterable[(key, tuple)]
                                            column values only, same filter, no text
    distinct(column) -> Iterable[value]

`equals` maps an INDEXED COLUMN NAME to a value, and `None` means the column is NULL —
which is how `Inventory.next_index` finds a record whose box will not coerce without
scanning the store for it (see `TableSpec.columns`).
"""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


def payload_text(payload: dict) -> str:
    """The one serialisation the store writes and compares. Compact, key-sorted."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class TableSpec:
    """How one kind of record becomes a row, and back.

    `parse(key, payload)` builds the object, or returns None to skip a row that will not
    construct — `Cache.parse` and `Queue.parse` both skip such a record rather than raising,
    and that rule is theirs to keep. `dump(obj)` is the JSON-able dict that is stored whole
    as the row's payload. `columns(obj)` is the handful of INDEXED columns beside it: what
    `where` and `select` can filter on without building an object, and what a person queries
    with the `sqlite3` CLI. Every column value is derived from the object at write time, so
    the column and the payload cannot disagree.
    """

    def __init__(
        self,
        name: str,
        *,
        parse: Callable[[str, dict], Any],
        dump: Callable[[Any], dict],
        columns: Callable[[Any], Dict[str, Any]],
        column_names: Sequence[str],
    ):
        self.name = name
        self.parse = parse
        self.dump = dump
        self.columns = columns
        self.column_names = tuple(column_names)


class Rows(MutableMapping):
    """A mapping of key -> record, memory-backed or bound to a `Source`."""

    def __init__(
        self,
        spec: TableSpec,
        *,
        source: Any = None,
        objects: Optional[Dict[str, Any]] = None,
        track: bool = True,
    ):
        self.spec = spec
        self.source = source
        # Keys are strings on disk and strings in every caller. Coerced here so a lookup by
        # the int a caller happens to hold finds the row the str wrote.
        self._loaded: Dict[str, Any] = {}
        self._baseline: Dict[str, dict] = {}
        self._deleted: set = set()
        self._complete = source is None
        self._track = track
        for key, obj in (objects or {}).items():
            self._loaded[str(key)] = obj

    # ------------------------------------------------------------------- the mapping

    def _remember(self, key: str, text: str) -> Optional[Any]:
        """Parse one row into the cache. None for a row `parse` refuses."""
        try:
            payload = json.loads(text)
        except ValueError:
            return None
        obj = self.spec.parse(key, payload)
        if obj is None:
            return None
        self._loaded[key] = obj
        if self._track:
            self._baseline[key] = self.spec.dump(obj)
        return obj

    def __getitem__(self, key) -> Any:
        key = str(key)
        if key in self._loaded:
            return self._loaded[key]
        if self._complete or key in self._deleted:
            raise KeyError(key)
        text = self.source.get(key)
        if text is None:
            raise KeyError(key)
        obj = self._remember(key, text)
        if obj is None:
            raise KeyError(key)
        return obj

    def __contains__(self, key) -> bool:
        key = str(key)
        if key in self._loaded:
            return True
        if self._complete or key in self._deleted:
            return False
        return bool(self.source.has(key))

    def __setitem__(self, key, obj) -> None:
        key = str(key)
        self._loaded[key] = obj
        self._deleted.discard(key)

    def __delitem__(self, key) -> None:
        key = str(key)
        if key in self._loaded:
            del self._loaded[key]
            # A row the source holds is a delete to write; a row born and dropped inside
            # this session was never there.
            if self._complete or key in self._baseline or (
                self.source is not None and self.source.has(key)
            ):
                self._deleted.add(key)
            return
        if self._complete or key in self._deleted or not self.source.has(key):
            raise KeyError(key)
        self._deleted.add(key)

    def __iter__(self) -> Iterator[str]:
        self._load_all()
        return iter(list(self._loaded))

    def __len__(self) -> int:
        if self._complete:
            return len(self._loaded)
        fresh = sum(1 for key in self._loaded if key not in self._baseline)
        return int(self.source.count()) - len(self._deleted) + fresh

    # ------------------------------------------------------------------ the queries

    def _load_all(self) -> None:
        if self._complete:
            return
        ordered: Dict[str, Any] = {}
        for key, text in self.source.all():
            key = str(key)
            if key in self._deleted:
                continue
            if key in self._loaded:
                ordered[key] = self._loaded[key]
                continue
            obj = self._remember(key, text)
            if obj is not None:
                ordered[key] = obj
        # Rows born in this session and not yet written sit after the stored ones, which
        # is exactly where a dict would have put them.
        for key, obj in self._loaded.items():
            if key not in ordered:
                ordered[key] = obj
        self._loaded = ordered
        self._complete = True

    def _matches(self, obj: Any, equals: Dict[str, Any]) -> bool:
        if not equals:
            return True
        columns = self.spec.columns(obj)
        return all(columns.get(name) == value for name, value in equals.items())

    def where(self, **equals) -> List[Any]:
        """Every record whose indexed columns equal `equals`, in key order.

        Bound and incomplete, this is one indexed query plus a pass over what is already
        loaded — a loaded object may have been changed since it was read, so its column
        values are recomputed from the object rather than trusted from the row.
        """
        if not self._complete:
            for key, text in self.source.where(equals):
                key = str(key)
                if key in self._deleted or key in self._loaded:
                    continue
                self._remember(key, text)
        found = {
            key: obj for key, obj in self._loaded.items() if self._matches(obj, equals)
        }
        return [found[key] for key in sorted(found)]

    def select(self, columns: Sequence[str], **equals) -> List[Tuple[str, Tuple[Any, ...]]]:
        """`(key, column values)` for matching rows, WITHOUT building objects for them.

        The allocator's high-water scan is the caller this exists for: it wants `box` and
        `idx` of every record in one box and nothing else, and building a thousand `Card`s
        to read two ints off each is the O(cards-in-box) cost a capture should not pay.
        Loaded objects are consulted through `columns()` so an unwritten change is seen.
        """
        columns = tuple(columns)
        out: Dict[str, Tuple[Any, ...]] = {}
        if not self._complete:
            for key, values in self.source.select(columns, equals):
                key = str(key)
                if key in self._deleted or key in self._loaded:
                    continue
                out[key] = tuple(values)
        for key, obj in self._loaded.items():
            if self._matches(obj, equals):
                derived = self.spec.columns(obj)
                out[key] = tuple(derived.get(name) for name in columns)
        return [(key, out[key]) for key in sorted(out)]

    def distinct(self, column: str) -> set:
        """Every value one indexed column takes, across stored and loaded rows."""
        values: set = set()
        if not self._complete:
            for value in self.source.distinct(column):
                values.add(value)
        for obj in self._loaded.values():
            values.add(self.spec.columns(obj).get(column))
        return values

    # ------------------------------------------------------------------- the flush

    @property
    def loaded_count(self) -> int:
        """How many objects this session built. What T7 holds a capture session to."""
        return len(self._loaded)

    @property
    def complete(self) -> bool:
        return self._complete

    def changes(self) -> Tuple[List[str], List[Tuple[str, Dict[str, Any], dict]]]:
        """`(deleted keys, [(key, columns, payload)])` — what a flush has to write."""
        upserts = []
        for key, obj in self._loaded.items():
            current = self.spec.dump(obj)
            if key in self._baseline and self._baseline[key] == current:
                continue
            upserts.append((key, self.spec.columns(obj), current))
        return sorted(self._deleted), upserts

    def flushed(self, upserts: Iterable[Tuple[str, Dict[str, Any], dict]]) -> None:
        for key, _, payload in upserts:
            self._baseline[key] = payload
        self._deleted = set()

    def to_dict(self) -> Dict[str, Any]:
        """Every record, key-ordered, as a plain dict. Loads the whole table."""
        self._load_all()
        return dict(self._loaded)


def int_or_none(value) -> Optional[int]:
    """The coercion the indexed `box`/`idx` columns use: an int, or NULL for a value that
    will not coerce — which is what lets `where(box=None)` find the record `next_index`
    must refuse on, without reading every row to look for it."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
