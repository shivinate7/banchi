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
    top(column, limit, columns) -> Iterable[(key, tuple)]
                                            the `limit` rows with the highest `column`,
                                            descending, NULLs excluded — column values only

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
        # Keys this SESSION has written via `__setitem__` — a brand-new record, or one
        # mutated after `_remember` loaded it from the source. Bounded by what this request
        # touched, never by the size of a prior full load: this is the set `where()`/
        # `select()` must re-check by hand after `_complete`, because the source's own index
        # cannot see an uncommitted change (D-per-box-read, item 2's `rows.py:177` fix).
        self._touched: set = set()
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
        self._touched.add(key)

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

        A SCOPED CALL COSTS WHAT THE INDEX COSTS, WHATEVER RAN EARLIER IN THIS SESSION
        (D-per-box-read) — bound-and-complete (a prior `.values()`/`.items()`/`to_payload()`
        loaded everything) now ALSO queries the source instead of scanning `self._loaded`,
        which is what degraded to an O(table) Python scan after any full load. Bound-and-
        incomplete is unchanged in substance (still one indexed query plus a pass over what
        it returned). Memory-backed (`self.source is None`) is unaffected: there is no index
        to defer to, so the old whole-`_loaded` scan is exactly right there and is kept.

        THIS DOES NOT TRUST `_touched` (a set of keys written via `__setitem__`) TO STAND IN
        FOR "MUTATED SINCE LOADED" — an earlier draft of this method did, and it was wrong.
        `Rows`'s own docstring states the actual convention: a caller that reads an object
        back and mutates its ATTRIBUTES directly — never reassigning through `__setitem__` —
        is a supported, and pervasively used, way to write (`store/master.py:set_state`,
        `record_identification`, `store/submissions.py:release`/`attach_run`, and others all
        do this). `_touched` alone would silently keep answering a stale verdict for such a
        row for the rest of the session — found for real in `submission-selftest`'s resume
        case, where `release()`'s in-place `claim.state = STATE_RELEASED` was invisible to a
        same-session `where(state=LIVE)` moments later. So every key the source returns AS A
        CANDIDATE is re-validated against the LIVE object when one is already loaded, which
        is what actually fixes that case, cheaply — bounded by what the source query itself
        returns, not by the table.

        WHAT THIS STILL DOES NOT CATCH, NAMED RATHER THAN SILENTLY ASSUMED AWAY: a row whose
        indexed column was mutated IN PLACE (not via `__setitem__`) so that it newly MATCHES
        `equals`, while its own on-disk value still would not have — the source query never
        offers it as a candidate, so it is missed. `_touched` (checked below) closes this for
        every row reassigned through `__setitem__`, which is every WRITE this repo's own
        allocator/mutator functions perform on a BRAND NEW row (`allocate_capture`) and is
        the only source of a genuinely new key with no on-disk row at all. It does not close
        it for a row that already existed, was loaded, and had an indexed column mutated in
        place into a NEW match — no case in this codebase's own call graph does that within
        one session today (verified: no handler queries a column immediately after mutating
        that same column on an existing record without reassigning), and it is recorded here
        so a future one does not silently reopen it.
        """
        if self.source is None:
            found = {
                key: obj for key, obj in self._loaded.items() if self._matches(obj, equals)
            }
            return [found[key] for key in sorted(found)]
        keys: set = set()
        for key, text in self.source.where(equals):
            key = str(key)
            if key in self._deleted:
                continue
            if key in self._loaded:
                if self._matches(self._loaded[key], equals):
                    keys.add(key)
                continue
            self._remember(key, text)
            keys.add(key)
        for key in self._touched:
            if key in self._deleted or key not in self._loaded or key in keys:
                continue
            if self._matches(self._loaded[key], equals):
                keys.add(key)
        return [self._loaded[key] for key in sorted(keys)]

    def select(self, columns: Sequence[str], **equals) -> List[Tuple[str, Tuple[Any, ...]]]:
        """`(key, column values)` for matching rows, WITHOUT building objects for them.

        Same split as `where()` above, for the same reason (D-per-box-read) and the same
        care: a loaded row the source offers as a candidate is re-validated against the LIVE
        object rather than trusted from the source's own (possibly stale) row, because this
        codebase's mutators routinely change an object's attributes in place without
        reassigning through `__setitem__`. See `where()`'s docstring for the one case this
        still cannot catch and why it does not matter to any call site today.
        """
        columns = tuple(columns)
        if self.source is None:
            out: Dict[str, Tuple[Any, ...]] = {}
            for key, obj in self._loaded.items():
                if self._matches(obj, equals):
                    derived = self.spec.columns(obj)
                    out[key] = tuple(derived.get(name) for name in columns)
            return [(key, out[key]) for key in sorted(out)]
        out = {}
        for key, values in self.source.select(columns, equals):
            key = str(key)
            if key in self._deleted:
                continue
            if key in self._loaded:
                obj = self._loaded[key]
                if self._matches(obj, equals):
                    derived = self.spec.columns(obj)
                    out[key] = tuple(derived.get(name) for name in columns)
                continue
            out[key] = tuple(values)
        for key in self._touched:
            if key in self._deleted or key not in self._loaded or key in out:
                continue
            obj = self._loaded[key]
            if self._matches(obj, equals):
                derived = self.spec.columns(obj)
                out[key] = tuple(derived.get(name) for name in columns)
            else:
                out.pop(key, None)
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

    def top(
        self, column: str, limit: int, columns: Sequence[str]
    ) -> List[Tuple[str, Tuple[Any, ...]]]:
        """`(key, column values)` for the `limit` rows with the highest `column`, descending
        — Home's hero deck, off the newest-captured cards (D-per-box-read/item 2). Bound, this is the
        source's own indexed `ORDER BY ... DESC LIMIT`, no object built. Memory-backed
        (`self.source is None`, T7's fixtures, which never carry enough rows to make a Python
        sort a cost) sorts what is loaded instead."""
        columns = tuple(columns)
        if self.source is not None:
            return [
                (str(key), tuple(values))
                for key, values in self.source.top(column, limit, columns)
            ]
        ranked = []
        for key, obj in self._loaded.items():
            derived = self.spec.columns(obj)
            value = derived.get(column)
            if value is None:
                continue
            ranked.append((value, key, tuple(derived.get(name) for name in columns)))
        ranked.sort(key=lambda row: row[0], reverse=True)
        return [(key, values) for _value, key, values in ranked[:limit]]

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
        self._touched = set()

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
