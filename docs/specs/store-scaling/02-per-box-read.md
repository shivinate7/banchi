# Item 2 — the per-box read

**Status of this file: SPECIFIED. Nothing below is built.** It is the playbook for
`docs/specs/store-scaling.md` §3 item 2 ("The per-box read, and the screens move to it. 2–3
days"), written for a session with no other context on this branch. Every file:line below was
read on this worktree on 2026-09-12; re-check line numbers before trusting them if the branch
has moved since.

## Goal and done-when

**Goal.** Stop every non-capture screen from paying `Inventory.to_payload()`'s full-store
walk (78 ms today, 1,485 ms at 20x rows) on every load and after every write. Reopen the
refusal at `server/capture_server.py:10687` ("a per-box read would be a second renderer for
one caller that does not exist yet" — the caller exists now, D53's own §5 argument) and give
`#/inventory` a real per-box data path. Remove `rows.py:177`'s degrade so a scoped `where()`/
`select()` never pays for an earlier full load. `GET /inventory` itself is **kept**, on the
guard's allowlist, unused by any screen this item touches — it is not deleted and no PR in
this plan may delete it.

**Done-when**, all four must hold:

1. `GET /inventory/<box>` exists, returns one box's cards in the exact per-card shape
   `GET /inventory` returns today (same `InventoryCard` fields, same decoration via
   `_Places`), and reads `Inventory.records_in(box)` rather than `to_payload()`. T7's new
   check (below) proves it loads O(cards-in-box) objects, not O(store).
2. `#/inventory` (`BoxBrowse.tsx` + `Inventory.tsx`) never calls `getInventory()` — it calls a
   new `getInventoryBox(box)` for whichever box is on screen, and re-fetches only that box
   after a sale, retire, move or reshoot. `app/tests/inventory.spec.ts`'s stub for
   `GET /inventory` is asserted **unhit** on a sale (new assertion, see Tests).
3. `Home.tsx`, `Fulfillment.tsx` and `Orders.tsx` no longer call `getInventory()`. Each has a
   named replacement source (see §(c) below) — cheap, already-fetched data, or one new lean
   route, never the old full walk.
4. `store/rows.py:177`'s fallback is gone: a `where()`/`select()` issued after this session's
   `Rows` has been fully materialised still resolves through the indexed source, and its cost
   is bounded by what THIS session has read and written, not by the size of the table. T7's
   `check_store_of_record`-style assertion (reusing `Rows.loaded_count`/`Rows.complete`,
   already used at `harness/tests/t7_store_and_seams.py:1084-1089`) proves it.

**CORRECTED 2026-09-12: `make docs-audit`'s `unscoped walk` row drops NOTHING in this item's
PR.** This paragraph originally claimed three entries closed here
(`server/capture_server.py:3056 do_inventory`, `:8349 _boxes_named`,
`store/master.py:1447 to_payload`); all three are verified to stay on the allowlist — see
"Allowlist entries removed" below and `docs/decisions/D-per-box-read.md` for the full
argument. The allowlist count is unchanged at 13 after this item.

## Depends on / conflicts with

- **Item 1 (the `unscoped walk` guard)** must already be on `main` — this item is graded
  against its allowlist and removes rows from it. If item 1 has not landed, do this item
  anyway (the guard's absence does not block the fix) but do not touch the allowlist table
  until item 1's PR is in.
- **Item 3 (`history()` scoped)** touches `store/db.py` and `_sale_origin`/`_retirement_origin`
  in `server/capture_server.py`, not `rows.py` or `do_inventory`. No file overlap; safe to run
  either order, but the plan puts this one first.
- **Item 4 (`_copies_out` as one pass)** touches `cli/resolve.py`, not this item's files. No
  overlap.
- **Item 6 (`do_orders` per SKU)** is the REAL fix for `Orders.tsx`'s `indexStore` /
  `rereadStore` (`Orders.tsx:1359-1373`). This item does the minimum removal described in
  §(c) below and explicitly leaves one sub-feature ("Walk the boxes") on the old call,
  named as item 6's to finish — see "Do not touch" and "Risks".
- **This item touches, in this order:** `server/capture_server.py` (route table + one new
  handler + one new small handler for Home's deck), `store/master.py` (no change needed —
  `records_in` already exists and is already box-scoped and lazy), `store/rows.py` (the
  fallback fix), `app/src/server.ts` (one or two new client functions), `app/src/types.ts`
  (one new type for Home's lean deck route only — the per-box route needs NO new type),
  `app/src/BoxBrowse.tsx` (the biggest edit — box-scoped fetch, search-driven cross-box
  ranking moved off `rows`), `app/src/Home.tsx`, `app/src/Fulfillment.tsx`,
  `app/src/Orders.tsx`. Six source files plus two test files
  (`harness/tests/t7_store_and_seams.py`, `app/tests/inventory.spec.ts`). No new files are
  created by this item's core, so `docs/map.py` needs no new entry — verify this at the end
  by running `make docs-audit`'s `repo map` row; if the session ends up adding a helper
  module it was not asked to add, that row will refuse the commit and say why.

## Read first

- `docs/specs/store-scaling.md` — the whole plan, especially §0, §2's four corrections and
  §4's allowlist. This file is that plan's item 2 written out.
- `CLAUDE.md`, section "Hard rules" — especially "A rule that can be mechanically enforced
  must be mechanically enforced" (item 1's guard reads this item's own diff) and "Fix the
  cause, never the symptom" (why `rows.py:177` gets a real fix and not a call-site patch).
- `CLAUDE.md`, section "The front end" — the `#/inventory` screen's own paragraph, D181's
  freeze rule (`app/src/frozenRank.ts`), D132's rail ordering, D58's numbering. This item
  must not change what any of those rulings say the screen does — only where the data comes
  from.
- D43 (`store/files.py:home()`), D58 (`Place.slot` vs `index`), D88 (SQLite is the store of
  record, one transaction per session, `Rows` per D88's own module) — all three are read
  before touching `store/master.py` or `store/rows.py` by the map's own instruction.
- `server/capture_server.py:1939-2130` — `_Places`'s docstring. Read it before writing
  `do_inventory_box`: it already explains why `_Places(inventory)` costs nothing extra per
  box (`records_in` is lazy, per box, since D88) and what degrades whole-store versus
  per-box (the denominator scan is whole-store on a corrupt neighbor; per-box decoration of
  a single box's own records is not).
- `store/rows.py`, the whole file (303 lines) — read it end to end before changing `where`/
  `select`. The docstring at the top states the two backings and the flush contract; get
  those invariants in your head before editing.
- `harness/tests/t7_store_and_seams.py:1020-1120` (`check_store_of_record`) — the existing
  precedent for asserting `Rows.loaded_count`/`Rows.complete` after a store operation. This
  item's new T7 assertions reuse that exact pattern; do not invent a new instrumentation
  mechanism (no query counters, no `sqlite3.Connection.set_trace_callback` — `Rows` already
  exposes what is needed).

## Steps

Ordered so the tree is green after each step. Steps 1–3 are server-side and can land as one
commit; steps 4–8 are client-side, one screen at a time; step 9 is the `rows.py` fix, done
last because it is the one step with the least test coverage today and you want the box-route
tests (step 3) in place as a second witness that scoped reads still return the right rows
after the fallback is removed.

### Step 1 — `Inventory` gains no new method; confirm `records_in` is enough

Nothing to write here. `store/master.py:1522-1533`:

```python
def records_in(self, box) -> List[Tuple[int, str, Card]]:
    """`(index, key, card)` for every record in `box`, ascending, coerced the way
    `next_index` coerces and refusing the same way. What the box-scoped routes walk
    instead of the whole store (D88)."""
    box = _as_position_int(box, "box")
    self._positions_in(box)  # the refusal, before anything is built
    out = [
        (_as_position_int(card.index, f"index of card {card.key}"), card.key, card)
        for card in self.cards.where(box=box)
    ]
    out.sort(key=lambda row: row[0])
    return out
```

already returns exactly what `do_inventory_box` needs: every `Card` in one box, via
`self.cards.where(box=box)` — an indexed query (`box` is in `CARDS.column_names`, confirmed at
`store/master.py:2485-2495`). Do not add a second method; `records_in` is the one this whole
item is named after in the plan text ("through `records_in`, with `_Places` built for that
box alone").

### Step 2 — the route: `do_inventory_box`

Add beside `do_inventory` in `server/capture_server.py` (after line 3119, where `do_inventory`
ends):

```python
def do_inventory_box(box: int) -> dict:
    """One box's cards, in exactly `do_inventory`'s per-card shape. The per-box twin of
    `GET /inventory` (D188 — see docs/specs/store-scaling.md item 2), through
    `Inventory.records_in`, which is already scoped and already lazy (D88): it queries the
    indexed `box` column and builds a `Card` object only for rows in this box, never for the
    store.

    THE SAME DECORATION, THE SAME DEGRADE RULE, NARROWED TO ONE BOX — WITH A CLAIM HERE THAT
    WAS WRONG AND IS CORRECTED. This paragraph originally claimed a corrupt record in ANOTHER
    box could no longer cost this box its denominator, reasoning that `records_in`'s call to
    `_positions_in(box)` is box-scoped. **Verified against the tree: it is not.**
    `_positions_in`'s own docstring says its refusal fires "ANYWHERE in the store," and its
    second pass (`self.cards.select(("box", "idx"), box=None)` / `idx=None`) is a genuinely
    unscoped query for any record whose box or index will not coerce, store-wide — the same
    rule `next_index`/`allocate_capture` have always had. So a single record ANYWHERE with a
    non-coercible box or index still raises `BadPosition` out of THIS route too, for every
    box, which is a real regression against `do_inventory`'s own per-record
    `continue`-and-keep-going (it never calls `_positions_in` at all). Fixing that is
    `_positions_in`'s own job, named as a follow-up rather than folded into this diff — see
    "Do not touch" below, which is unchanged and correct. What IS box-scoped, and is what this
    route's O(cards-in-box) claim actually rests on, is the row-building query below it,
    `self.cards.where(box=box)` — a healthy store never touches this refusal at all, and that
    is the case T7 exercises; the corruption case is exercised too, asserting the refusal
    rather than the isolation this paragraph originally (and wrongly) claimed. See
    `docs/decisions/D-per-box-read.md` for the full argument.

    `boxes` AND `listings` DO NOT RIDE ALONG, UNLIKE `do_inventory`'s. Nothing under `app/src`
    reads `Inventory.boxes` from a `GET /inventory` response — `GET /boxes` is what every
    screen actually reads for the box registry — so serving it here would cost a walk for a
    field with no client. `listings` DOES ride along, narrowed to the SKUs this box's own
    cards carry: `BoxBrowse.tsx` reads `inventory.listings[sku]?.live_as_of` for exactly one
    card at a time (the one selected), and a screen holding one box's worth of SKUs already
    has every listing it can address.
    """
    inventory = Store().read().inventory
    rows = inventory.records_in(box)
    places = _Places(inventory)
    cards: dict = {}
    skus: set = set()
    for index, key, card in rows:
        record = asdict(card)
        record["number_display"] = join.display_number(
            record.get("number"), record.get("printed_total")
        )
        try:
            place = places.of(record["box"], record["index"])
        except (KeyError, TypeError, ValueError, master.BadSections):
            cards[key] = record
            continue
        if place["located"]:
            record.update(_flat_place(place))
        record["place"] = place
        cards[key] = record
        if card.sku:
            skus.add(str(card.sku).strip())
    listings = {
        sku: asdict(inventory.listings[sku])
        for sku in skus
        if sku in inventory.listings
    }
    return {"version": master.VERSION, "cards": cards, "listings": listings}
```

Notes for whoever writes this:

- `records_in` raises (`BadPosition` etc.) on a record in this box whose `box`/`index` will
  not coerce, same as `_positions_in` does for `next_index` — that exception is NOT caught
  here and propagates as a 500, exactly as `do_inventory` today lets `to_payload()`'s
  `asdict` run over every record without a per-record try/except (the per-record catch in
  `do_inventory`'s loop is only around `places.of(...)`, never around building the record
  itself). Keep that asymmetry — do not add a broader try/except that `do_inventory` does not
  have, or the two routes' error behavior on a truly corrupt Card diverges silently.
- `asdict(card)` is the same call `Inventory.to_payload()` makes per card
  (`store/master.py:1459`) — reuse it so the two routes can never drift on which fields a
  `Card` serialises to.
- `box` here is the ALREADY-VALIDATED int from the route regex (see step 3); `records_in`
  itself calls `_as_position_int(box, "box")`, so a query-string box of `"0"` or a negative
  number is refused by `records_in` with the store's own `BadPosition`, not by a bespoke
  check in this function. Do not add one.
- `master.VERSION` is the module-level constant `to_payload()` also writes
  (`store/master.py:1452`). Import it the same way `capture_server.py` already imports
  `master` (it does; grep `from store import master` or similar near the top of the file —
  do not add a second import statement if one already exists).

### Step 3 — wire the route

`server/capture_server.py:546` already declares:

```python
_INVENTORY_BOX_RE = re.compile(r"^/inventory/(\d+)$")
```

and it is already used once, in `do_PUT` (`:11305`), for `do_put_box_claims`. **Do not touch
that PUT usage.** Add a GET arm in `do_GET`'s `run()` closure. The insertion point is right
after the existing `/inventory` exact-match at `:10636-10637`:

```python
            if path == "/inventory":
                return self._json(HTTPStatus.OK, do_inventory())
```

Insert immediately after it, and BEFORE `_BOXES_ITEM_RE`'s explainer block (the ordering
comment at `:10688-10693` explains why one-segment regexes are checked in a specific order —
read it, then add this in the same spirit, matched by its own anchored regex so there is no
overlap to reason about):

```python
            match = _INVENTORY_BOX_RE.match(path)
            if match:
                return self._json(HTTPStatus.OK, do_inventory_box(int(match.group(1))))
```

This is the same regex object the PUT handler already uses — reusing it (rather than
declaring a second `_INVENTORY_BOX_GET_RE`) is deliberate: one pattern, one place that says
what `/inventory/<n>` means as a path, matched by two different HTTP methods with two
different handlers. `_INVENTORY_ITEM_RE` (`/inventory/<box>/<index>`, two segments) is
distinct and unaffected.

A box number this store has never seen (an empty box, never captured into) is not an error:
`records_in` returns `[]` for it, and the route answers `{"version": ..., "cards": {},
"listings": {}}` — a real, empty payload, not a 404. This matches `GET /inventory`'s own
behavior for a store with no cards at all, and matches `GET /boxes/<n>`'s deliberate NON-
existence (`:10687-10699`) staying exactly as it is: this route answers "what is in box N",
not "does box N exist" — that second question is still `GET /boxes`'s alone.

### Step 4 — T7 proof the route is scoped, before touching any client code

Add to `harness/tests/t7_store_and_seams.py`, near `check_box_routes_and_search` (`:7183`,
same file, same section — put the new function directly after it so the box-route tests stay
together). Model: `check_store_of_record`'s `built <= 2` / `not complete` assertion at
`:1084-1089`.

```python
def check_inventory_box_route(checks: Checks) -> None:
    """D188/item 2: `GET /inventory/<box>` reads one box, never the store.

    THE PROOF IS `Rows.loaded_count`, NOT A TIMING. A wall-clock assertion is what
    docs/specs/store-scaling.md's own `.backup`-copy measurement is for, run by hand against
    the owner's real store; a harness test needs to be true on every machine and every CI
    runner, so it asserts what the route BUILT rather than how long it took. `Rows` already
    tracks this for exactly this reason (D88) — see `check_store_of_record` for the
    precedent.
    """
    checks.note("")
    checks.note("PER-BOX READ — server/capture_server.py:do_inventory_box (item 2)")

    with isolated_home():
        for at in range(1, 21):
            capture_server.do_capture(capture_payload(1, capture_id=f"a{at}", set_hint="sv9"))
        for at in range(1, 6):
            capture_server.do_capture(capture_payload(2, capture_id=f"b{at}", set_hint="sv9"))

        with Store().write() as snapshot:
            box, count = snapshot.inventory.cards.loaded_count, None  # placeholder read

        payload = capture_server.do_inventory_box(1)
        checks.equal(
            sorted(payload["cards"].keys()),
            [f"1/{n}" for n in range(1, 21)],
            "GET /inventory/1 returns exactly box 1's twenty cards",
        )
        checks.ok(
            all(row["box"] == 1 for row in payload["cards"].values()),
            "and every row decorates as box 1 — none of box 2's five leaked in",
        )

        after = Store().read()
        checks.ok(
            not after.inventory.cards.complete and after.inventory.cards.loaded_count <= 20,
            f"and it built {after.inventory.cards.loaded_count} card objects reading box 1 "
            "of a 25-card store, not the store's 25 — a fresh `Store().read()` proves the "
            "PREVIOUS read's session is gone and this is a clean instrument",
        )

        # An empty, never-captured box answers with nothing rather than refusing. Done BEFORE
        # the corruption case below, which leaves the store corrupted for every box.
        empty = capture_server.do_inventory_box(999)
        checks.equal(
            empty["cards"], {}, "box 999, never captured into, answers an empty map"
        )

        # CORRECTED 2026-09-12: the sketch this playbook originally gave here asserted that a
        # corrupt record in ANOTHER box does NOT take box 1's read down with it. Verified
        # against the tree: it DOES — `_positions_in`'s refusal is store-wide, not box-scoped
        # (see this file's corrected docstring for `do_inventory_box` above, and
        # `docs/decisions/D-per-box-read.md`). The real, verified assertion is the opposite:
        with Store().write() as snapshot:
            snapshot.inventory.cards["2/1"].box = "not-a-box"  # type: ignore[assignment]
        caught = checks.raises(
            master.BadPosition,
            lambda: capture_server.do_inventory_box(1),
            "and a record ANYWHERE with a non-coercible box still raises out of THIS route "
            "too, for every box asked about — `do_inventory` never hits this because it "
            "never calls `_positions_in`; narrowing that refusal to the box asked about is a "
            "separate item, not this one",
        )
```

Placeholder note: the `box, count = ...` line above is scaffolding to force a fresh session
read before the assertion below it if a helper for that does not already exist elsewhere in
this file — check whether `isolated_home()`'s block already gives you a clean `Store().read()`
per call (it does: every `Store()` constructs a new session against the same on-disk file, so
`after = Store().read()` a few lines down is already a fresh instrument). Delete the
placeholder line; it was left in this playbook as a reminder to verify that assumption before
relying on it, not as code to ship.

Register `check_inventory_box_route` in this file's `TESTS` list (search for where
`check_box_routes_and_search` is registered — same list, insert the new name next to it) and
confirm with `python3 harness/run.py` (or `make harness`) that it is picked up and green
before moving on.

### Step 5 — client: `getInventoryBox`

`app/src/server.ts:714-717`:

```ts
/** The whole card map. Keyed `"<box>/<index>"`. */
export async function getInventory(): Promise<Inventory> {
  return (await request('/inventory', NO_CACHE)) as Inventory
}
```

Add directly after it:

```ts
/** One box's cards, in the same per-card shape as `getInventory()` — same `InventoryCard`
 *  fields, same decoration. `boxes` is never present (nothing under `app/src` reads
 *  `Inventory.boxes`; `getBoxes()` is the box registry's one reader) and `listings` is
 *  narrowed to this box's own SKUs, which is every listing a screen holding one box can
 *  address (D188, item 2 of docs/specs/store-scaling.md). */
export async function getInventoryBox(box: number): Promise<Inventory> {
  return (await request(`/inventory/${box}`, NO_CACHE)) as Inventory
}
```

**No new type.** `Inventory` (types.ts:522-532) already declares `boxes?` and `listings?` as
optional — this response simply omits `boxes` and narrows `listings`, both already legal
shapes of the existing type. Do not add `InventoryBox` or similar; that would be the "second
renderer" mistake the plan spent a paragraph refusing to repeat (§2's first bullet).

### Step 6 — `BoxBrowse.tsx`: the fetch becomes box-scoped

This is the one genuinely hard step. Read this whole section before editing.

**What changes structurally.** Today `BoxBrowse` fetches the WHOLE store once per mount/reload
(`useEffect` at `:862-887`, keyed on `[reloads, reloadToken, onListings]`) and holds it in
`rows: Row[] | null` (state at `:632`). Switching the visible box (`shelf`, state at `:637`)
is then a pure client-side filter over that one array — no new network call. Under a search,
the cross-box rail ranking (`order` at `:724-764`, `shelvesOf` at `:766-769`,
`matchesByShelf` at `:806-814`) also reads `inQuery` — the SAME store-wide `rows`, filtered
by the search's matched keys.

After this step, `rows` holds ONE box's cards, fetched fresh every time `shelf` changes (a
new `getInventoryBox(shelf)` call), and the search-driven cross-box behavior (D181's rule
that a search can jump the rail to a box you are not standing in) is re-derived from the
search's OWN result (`results: SearchResult`, already held by this component via
`useSearch()` at `:690`) instead of from `rows`. This works because `SearchCopy` already
carries `place.box` and `place.section` (`types.ts:1204`, `1180-1220`) — everything the rail
ranking needs — without requiring the box's full card objects to be loaded.

**Verified: the copies-list ("other boxes hold this card too") needs no change.** It is NOT
sourced from `BoxBrowse`'s `rows` at all — `Inventory.tsx`'s `CopiesFor` component
(`:628-650` area) runs its OWN `useSearch()` keyed on the selected card's SKU/name
(`:651-676`) and hands the resulting `SearchGroup.copies` straight to `CardLocations`. That
call already goes through `/search`, a full-store server-side walk that item 8 (not this one)
scopes. Nothing in this item touches `Inventory.tsx`'s `CopiesFor` — confirm this by reading
`Inventory.tsx:628-770` before you start and again after you finish; if you find yourself
editing it to "fix" the copies list, stop, you have misread the dependency.

**6a. Replace the full-store fetch effect.**

Current (`:862-887`):

```tsx
  useEffect(() => {
    let live = true
    getInventory()
      .then((inventory) => {
        if (!live) return
        const next = rowsOf(inventory.cards)
        setRows(next)
        const held = inventory.listings ?? NO_LISTINGS
        setListings(held)
        onListings?.(held)
        setFailure(null)
        setPhotoAbsent(null)
        setSelected((prev) =>
          prev !== null && next.some((row) => row.key === prev) ? prev : (landingOf(next)?.key ?? null),
        )
      })
      .catch((err: unknown) => {
        if (!live) return
        setRows(null)
        setFailure(describeFailure(err))
      })
    return () => {
      live = false
    }
  }, [reloads, reloadToken, onListings])
```

Replace the trigger array and the call. It must now also re-run when `shelf` changes (a box
switch is a data-fetch, not a filter, from here on), and it must NOT run before the first
shelf is known (the shelf-selection effect below `:934+` decides the initial shelf off
`GET /boxes` and the URL's `?box=` — do not fetch box data before that has resolved, or you
fetch box 0 / `NaN` on first paint):

```tsx
  useEffect(() => {
    if (typeof shelf !== 'number') return
    let live = true
    getInventoryBox(shelf)
      .then((inventory) => {
        if (!live) return
        const next = rowsOf(inventory.cards)
        setRows(next)
        const held = inventory.listings ?? NO_LISTINGS
        setListings(held)
        onListings?.(held)
        setFailure(null)
        setPhotoAbsent(null)
        setSelected((prev) =>
          prev !== null && next.some((row) => row.key === prev) ? prev : (landingOf(next)?.key ?? null),
        )
      })
      .catch((err: unknown) => {
        if (!live) return
        setRows(null)
        setFailure(describeFailure(err))
      })
    return () => {
      live = false
    }
  }, [shelf, reloads, reloadToken, onListings])
```

Import `getInventoryBox` alongside the existing `getInventory` import at `:21` — actually
**remove `getInventory` from the import list entirely** once every call site in this file is
converted (there should be none left after 6a and 6b); leaving an unused import is a lint
failure (`make lint`'s eslint pass) and, more importantly, a sign the conversion is
incomplete.

This makes `rows` hold ONE box's cards, and `shelf` changing (rail click, search-jump, URL's
`?box=`, keyboard `,` navigation) now costs a network round trip — accept this; it is the
per-box read the plan asks for, and D88 measures `records_in` flat at ~4 ms per box at every
store size. Do not build a `Map<number, Row[]>` cache across boxes to avoid the round trip:
a cached OTHER box goes stale the moment `BoxOps.tsx`'s `doMove` (see step 8) moves cards INTO
it, and there is no write response naming which boxes besides the current one were touched.
Fetching fresh on every shelf switch is simpler and cannot go stale by construction.

**6b. Cross-box ranking moves off `rows` and onto `results`.**

`shelfOf`/`hasDeparted` operate on a `Row` (`{key, card}`); the ranking code needs the same
two facts (which box, is it departed) about a `SearchCopy` instead. Add two small helpers
near `shelfOf` (`:111-116`):

```tsx
/* The same two facts `shelfOf`/`hasDeparted` read off a Row, read off a SearchCopy instead —
 * for the cross-box search ranking, which no longer has every box's Rows loaded to ask. */
function copyShelf(copy: SearchCopy): Shelf {
  if (copy.place.located === false) return 'pooled'
  const box = copy.place.box
  return typeof box === 'number' && !Number.isNaN(box) ? box : 'unplaced'
}

function copyDeparted(copy: SearchCopy): boolean {
  return isDeparted(copy.place)
}
```

`isDeparted` is already imported from `./server` at `:17`. Add `copy.place.located` — check
`SearchCopy.place: Place` (`types.ts:1377`) already carries `located?: boolean`
(`types.ts:1196`), so this compiles against the existing type with no change to `types.ts`.

Now change three computations to read `results` (the search hook's own state, already at
`:690`, unchanged) instead of `inQuery`/`rows`:

`order` (`:724-764`) — replace the `liveMatches` block (`:738-751`) which today does:

```tsx
    const liveMatches = new Map<number, number>()
    if (filtered) {
      const perSection = new Map<string, number>()
      for (const row of inQuery) {
        const shelf = shelfOf(row)
        if (typeof shelf !== 'number' || !ranksAsLive(row.key, hasDeparted(row.card), frozen)) continue
        const key = `${shelf}/${row.card.section ?? '?'}`
        const n = (perSection.get(key) ?? 0) + 1
        perSection.set(key, n)
        liveMatches.set(shelf, Math.max(liveMatches.get(shelf) ?? 0, n))
      }
    }
```

with:

```tsx
    const liveMatches = new Map<number, number>()
    if (filtered && results !== null) {
      const perSection = new Map<string, number>()
      for (const group of results.groups) {
        for (const copy of group.copies) {
          const shelf = copyShelf(copy)
          if (typeof shelf !== 'number' || !ranksAsLive(copy.key, copyDeparted(copy), frozen)) continue
          const key = `${shelf}/${copy.place.section ?? '?'}`
          const n = (perSection.get(key) ?? 0) + 1
          perSection.set(key, n)
          liveMatches.set(shelf, Math.max(liveMatches.get(shelf) ?? 0, n))
        }
      }
    }
```

and add `results` to `order`'s `useMemo` dependency array (`:764`), replacing `inQuery` there
(it is no longer read by this block — check whether `inQuery` is still used elsewhere in
`order`'s body; it is not, per the excerpt above, so drop it from the deps and keep
`[boxRecords, recency, filtered, results, frozen]`).

`shelvesOf`'s call at `:766-769`:

```tsx
  const shelves = useMemo(
    () => shelvesOf(inQuery, filtered ? [] : boxRecords.map((record) => record.box), order),
    [inQuery, filtered, boxRecords, order],
  )
```

The `filtered` branch must stop asking `inQuery` (now just this box's matched rows) for which
boxes to list, and instead ask `results` for every box ANY match touches:

```tsx
  const searchBoxes = useMemo(() => {
    if (results === null) return []
    const boxes = new Set<number>()
    for (const group of results.groups) {
      for (const copy of group.copies) {
        const shelf = copyShelf(copy)
        if (typeof shelf === 'number') boxes.add(shelf)
      }
    }
    return [...boxes]
  }, [results])

  const shelves = useMemo(
    () => shelvesOf(inQuery, filtered ? searchBoxes : boxRecords.map((record) => record.box), order),
    [inQuery, filtered, searchBoxes, boxRecords, order],
  )
```

Note `shelvesOf`'s signature (`:134-154`) takes `rows: Row[]` as its first argument to find
`'pooled'`/`'unplaced'` shelves too, alongside the `registry: readonly number[]` extra-boxes
list — `inQuery` (this box's own matched rows) is still a legitimate source for whether THIS
box itself is pooled/unplaced, so it stays as the first argument; only the "which OTHER boxes
have this filtered/registry set" argument changes.

`matchesByShelf` at `:806-814`:

```tsx
  const matchesByShelf = useMemo(() => {
    const out = new Map<Shelf, number>()
    if (!filtered) return out
    for (const row of inQuery) {
      const s = shelfOf(row)
      out.set(s, (out.get(s) ?? 0) + 1)
    }
    return out
  }, [inQuery, filtered])
```

becomes:

```tsx
  const matchesByShelf = useMemo(() => {
    const out = new Map<Shelf, number>()
    if (!filtered || results === null) return out
    for (const group of results.groups) {
      for (const copy of group.copies) {
        const s = copyShelf(copy)
        out.set(s, (out.get(s) ?? 0) + 1)
      }
    }
    return out
  }, [filtered, results])
```

**6c. `onShelf`, `visible`, `sections`, `inQuery` stay exactly as written.** They already
operate on `rows`/`inQuery` scoped to the CURRENT box, which is correct and unchanged — the
only thing that changed is that `rows` itself now arrives pre-scoped from the server instead
of being filtered client-side from a store-wide array. Do not touch `inQuery` (`:711-716`),
`onShelf` (`:771-774`), `visible` (`:793-801`) or `sections` (`:803`).

**6d. Reload triggers.** Every place that calls `setReloads((n) => n + 1)` inside
`BoxBrowse.tsx` (the reshoot success handler at `:842`, the remove-in-place handler around
`:2242` which is followed by its own `setReloads`, and the manual "Reload" button at `:1732`)
needs no change: they bump the SAME `reloads` counter, and the fetch effect (6a) now reads
`getInventoryBox(shelf)` keyed on `[shelf, reloads, reloadToken, onListings]` — bumping
`reloads` re-fetches the CURRENT box, which is exactly "the `reloads` counter … becomes
box-scoped" from the plan text. No edits needed at `:842`, `:1732`, or the remove-in-place
call site beyond what 6a already changed in the effect itself.

**6e. `getBoxes()` effect (`:890-912`) is unchanged.** It already reads `GET /boxes`, which
is on the guard's "stays" list (§4 of the plan: `distinct("box")`, cheap, one column). Do not
touch it.

### Step 7 — `Inventory.tsx`: nothing to change, verify only

`Inventory.tsx`'s `doSell` (`markSold` at `:370`, `setReloads` at `:386`) and `doRetire`
(`retireCard` inside, `setReloads` at `:442`) both already end by bumping THIS file's own
`reloads` counter (`:243`), which flows down as `<BoxBrowse reloadToken={reloads}>` at
`:563` and `:587`. `BoxBrowse`'s fetch effect (6a) already lists `reloadToken` in its
dependency array, so a sale or a retirement already re-triggers `getInventoryBox(shelf)` with
no change needed in `Inventory.tsx`. Read `:340-475` once after finishing step 6 and confirm
no call in this file still imports or calls `getInventory` — it should not, since `Inventory.tsx`
never called it directly (only `BoxBrowse.tsx` did); this is a verification step, not an
edit.

**Undo** (`undoSale`, `undoRetire`, imported at `:22-24`) also ends by bumping `reloads` the
same way — same verification, no edit expected.

### Step 8 — `BoxOps.tsx`: the move, and why it needs no special case

`BoxOps.tsx:446-459`'s `doMove` calls `moveCards(record.box, ..., toBox)` — `record.box` is
the box currently open in the "Manage box" sheet, i.e. the CURRENT shelf. Its `write()`
wrapper (find the `write` helper passed into `BoxOps`'s props — it is the same one every
other `BoxOps` mutation uses, e.g. `applyClaims` at `:434-442`, `saveSectionNames` at
`:479-481`) calls `onChanged` on success, which every caller wires to
`setReloads((n) => n + 1)` on `BoxBrowse` (confirmed at `:1871` and `:2008`). After step 6,
that reload re-fetches `getInventoryBox(shelf)` — i.e., the SOURCE box, which is exactly the
box whose card count just changed. The DESTINATION box (`toBox`) is not re-fetched, and does
not need to be: `BoxBrowse` never holds more than one box's `rows` at a time (6a deliberately
rejected a multi-box cache), so the destination box's data is fetched fresh, automatically,
the next time the operator's shelf becomes `toBox`. No code changes in `BoxOps.tsx`.

Name this explicitly in the PR description: "a move refreshes the box you were looking at;
the box you moved cards INTO is fetched fresh whenever you next open it, because nothing
caches more than one box's data across a shelf switch." This is the argument the reviewer
needs to not ask for a `toBox` refetch that would in fact be dead code.

### Step 9 — Home, Fulfillment, Orders (item (c))

Each screen's ONLY use of `getInventory()` / its fields, and its replacement:

**`Home.tsx:405`** —

```tsx
  const shelf = useLoad<Record<string, InventoryCard>>(async () => (await getInventory()).cards)
  const fromBoxes = deckFromBoxes(boxes.state === 'ready' ? boxes.value : null)
  const fromCards = deckFromCards(shelf.state === 'ready' ? shelf.value : null)
  const deck = fromCards.length > 0 ? fromCards : fromBoxes.cards
```

`deckFromCards` (`:145-168`) needs the newest IDENTIFIED cards ACROSS THE WHOLE STORE, sorted
by `captured_at` descending, top `DECK_DEPTH` (find the constant — grepped near the top of
`Home.tsx`, currently a small number, single digits to low tens). This is a genuine top-K
query over every box and cannot be answered by any per-box route or by `GET /boxes`/
`Inventory.counts()` alone — it is the one place in this item that needs **a new small
route**, per the task's own third option.

`captured_at` is already an indexed column (`store/master.py:2485-2495`'s `CARDS`
`column_names` includes it; `store/db.py:118` confirms it in the SQLite schema). Add:

- `store/rows.py`: extend the `Source` contract (documented at the top of the file,
  `:36-49`) with one more method, and implement it only where a table is actually queried
  this way (cards):

  ```python
  top(column, limit, columns) -> Iterable[(key, tuple)]  # rows ordered by `column`
                                                          # descending, values only
  ```

  and add a `Rows.top(self, column: str, limit: int, columns: Sequence[str])` method
  mirroring `select()`'s shape (`:231-251`) — no object built, `(key, tuple)` pairs, source
  query first when bound and `self.source is not None`, falling back to a Python sort over
  `self._loaded` for the memory-backed case (T7 fixtures, which never carry 50,000 rows, so
  a Python sort there is fine).
- `store/db.py`: on `SqliteSource`, add `top`:

  ```python
  def top(self, column, limit, columns):
      if column not in self._spec.column_names:
          raise ValueError(f"{column!r} is not an indexed column of {self.table}")
      cols = ", ".join(c for c in columns if c in self._spec.column_names or c == "key")
      cursor = self._conn.execute(
          f"SELECT key, {cols} FROM {self.table} WHERE {column} IS NOT NULL "
          f"ORDER BY {column} DESC LIMIT ?",
          (limit,),
      )
      return [(row[0], tuple(row[1:])) for row in cursor.fetchall()]
  ```

  (Adjust to this file's actual connection-holding attribute name and quoting helper — read
  `SqliteSource.select`/`where`/`distinct` at `:1065-1096` first and match their exact
  patterns for parameterisation and column-name validation; the sketch above is the shape,
  not a drop-in.)
- `store/master.py`, `Inventory`: add

  ```python
  def newest_captured(self, limit: int) -> List[Tuple[str, int, int, Optional[str]]]:
      """`(key, box, index, cid)` of the `limit` most recently captured cards, newest
      first, for Home's hero deck (D188). Column values only — no `Card` built — because
      the deck over-fetches and filters (state, name, photo) on the small surviving set,
      never on the full result."""
      rows = self.cards.top("captured_at", limit, ("box", "idx", "cid"))
      return [(key, int(box), int(idx), cid) for key, (box, idx, cid) in rows]
  ```

- `server/capture_server.py`: a small new route, `GET /inventory/recent?limit=N`, dispatched
  from `do_GET`'s `run()` beside the other query-string routes (model: `/search`'s
  `parse_qs` handling at `:10657-10662`). Handler:

  ```python
  def do_inventory_recent(limit: int) -> dict:
      """The newest-captured cards, over-fetched and filtered down to the ones the hero can
      actually show (D188, Home.tsx's deck). Over-fetches 3x limit because a captured-but-
      unidentified or photo-less card is skipped by the screen (see `deckFromCards`'s own
      comment on why identified-not-merely-captured); the handful that survive get a real
      `Card` lookup (`inventory.cards[key]`, a point read, not a table scan) so the response
      carries the fields the screen actually draws (name, state, photo presence).
      """
      inventory = Store().read().inventory
      candidates = inventory.newest_captured(max(limit * 3, limit + 12))
      out = []
      for key, box, index, cid in candidates:
          if len(out) >= limit:
              break
          card = inventory.cards.get(key)
          if card is None or card.state in ("sold", "retired", "moved"):
              continue
          if not card.name or card.photo is None:
              continue
          out.append({"key": key, "box": box, "index": index, "cid": cid, "name": card.name})
      return {"cards": out}
  ```

  Adjust field names to whatever `Card`/`asdict` actually calls the "has a photo" field
  (`do_inventory`'s own code reads `record.get("photo")`-shaped data — confirm the exact
  attribute name on `Card` before writing this, it may be `photo` or a derived boolean).

- `app/src/types.ts`: one new type, since this route's shape is NOT `Inventory`'s:

  ```ts
  export type RecentCard = { key: string; box: number; index: number; cid: string | null; name: string }
  export type RecentCards = { cards: RecentCard[] }
  ```

- `app/src/server.ts`: `getRecentCards(limit: number): Promise<RecentCards>` beside
  `getInventory`, same `request()` pattern.
- `Home.tsx:405`: replace the `shelf`/`fromCards`/`deckFromCards` machinery with a load of
  `getRecentCards(DECK_DEPTH)` and a small mapper that produces the same `DeckCard[]` shape
  `deckFromCards` produced (`{key, box, index, photo: photoUrl(box, index, cid), card:
  null}` — note `card: null` here is fine; check every reader of `DeckCard.card` in
  `Home.tsx` to see whether it only reads `box`/`index`/`photo`/`key`, which is likely since
  the "front card" is used for `useCardCrop({box, index})` at `:419`, not for name/state
  display beside it — if a reader DOES need `card.name`, carry `name` through `DeckCard` as
  an added optional field rather than fetching a second, full `InventoryCard`).

**`Fulfillment.tsx:451`** — two separate uses of the same `getInventory()` call, and they get
two separate answers:

1. **Order resolution** (`waiting`/`walk`, built from `orders` which itself resolves against
   `cards` — read `:236-260` to confirm exactly how `cards` feeds order resolution before
   changing this). The boxes involved are named by the server's own order resolution
   (`GET /orders`'s response already carries which boxes each candidate copy sits in, per
   D66/`do_orders`'s existing shape — check `OrdersPayload`'s type for a `place`/`box` field
   on each resolved line). Fetch `getInventoryBox(box)` for the small, bounded set of boxes
   the CURRENT open orders actually name (dedup, one fetch per box), merge their `cards` maps
   client-side into the same shape `cards` holds today, and feed that into the existing
   `offered`/`sellable` pipeline unchanged.
2. **Store-wide browse** (`byBox`, the "No cards are for sale right now" fallback view at
   `:1275+`, which lists every sellable card across every box for the Fulfiller to browse with
   no order in hand — this is a real, separate capability, not a leftover). This is
   store-wide by design and cannot be scoped to "the boxes an order names" because there may
   be no order at all. **This is the one place in this item where the honest answer is "no
   cheap replacement exists yet."** Two options, name the choice made in the PR:
   - (i) leave this ONE call on `getInventory()`, commented plainly as a known carry-over
     ("this is the Fulfiller's whole-store browse, D5/D6 — item 7 or a future item gives
     this a lean route; until then it pays the full walk"), OR
   - (ii) build the same kind of lean "recent"-style route as Home's, but for "every
     sellable card, lean shape" instead of "N most recent" — a real but larger effort than
     this item budgets (2–3 days total for the whole item), so (i) is the recommended
     choice unless the session has time left over.
   Whichever is chosen, the `unscoped walk` guard (item 1) does not see this: it watches
   `server/*.py` and `store/master.py`, not client fetch call sites, so choosing (i) does
   not fail any commit. It is a documented, argued scope decision (CLAUDE.md's "Fix the
   cause… First ask whether the primitive already exists" — here the honest answer is that
   it doesn't yet, and inventing one under time pressure would be the "band-aid presented as
   the solution" the same rule forbids).

**`Orders.tsx:1361`** — `rereadStore`'s `indexStore(inventory)` (`:623-639`) builds a
`sku -> PickRow[]` map over every on-hand card in the store, for the "Walk the boxes"
cross-order feature (D97). Same shape of problem as Fulfillment's browse view, and the same
answer: item 6 (`do_orders` per SKU) is the real fix, described in the plan as building
`_Places` only "for the boxes those copies sit in, never for a box no line touches." For
THIS item, do the minimum named in the plan text — "Orders reads GET /inventory/<box> for
the boxes an order names" — by changing `rereadStore` to fetch `getInventoryBox(box)` for
the boxes named by the CURRENT `hub.payload`'s resolved order lines (the same set Fulfillment
needs for its order-resolution half; consider factoring the "which boxes do my open orders
touch" computation into one shared helper both screens import, rather than writing it twice).
Leave "Walk the boxes" itself calling `getInventory()` for now, with the same kind of
inline comment Fulfillment's browse view gets, naming item 6 as the closer. Do not silently
narrow "Walk the boxes" to only order-named boxes — that would quietly break a real feature
(the whole point of that walk is to reach boxes NO open order touches) rather than admit the
scope gap honestly.

### Step 10 — `store/rows.py`: a `where()`/`select()` after a full load answers from SQL

**CORRECTED 2026-09-12, AFTER LANDING: the `_touched`-based design this section originally
sketched below is WRONG for this codebase and was replaced.** It tracked keys written through
`Rows.__setitem__` and trusted the source's own index for every other row — but `Rows`'s own
docstring documents that mutating an object's attributes directly, without reassigning
through `__setitem__`, is a SUPPORTED write path, and it is the one `store/master.py:
set_state`, `record_identification` and `store/submissions.py:release`/`attach_run` all
actually use. The `_touched`-only design broke `submission-selftest.py`'s real
`case_resume_releases_only_its_own` for real, in production code this item never touches: a
released claim's in-place `state` mutation stayed invisible to a same-session re-query. The
actual fix re-validates every candidate the source's own indexed query returns against the
LIVE loaded object (never trusting either the source's row or `_touched` alone), and
`store/submissions.py`'s two mutators were corrected to reassign through `__setitem__` to
match this codebase's other mutators. See `docs/decisions/D-per-box-read.md` for the full
argument, the one gap this still leaves (a row mutated in place INTO a match the source
cannot see — verified not to affect `box`/`idx`, which is what this item's own routes read),
and the T7 case that pins it. The sketch below is kept as a record of the FIRST, wrong
attempt — read the decision entry and the actual `store/rows.py` before trusting any of the
code in this section.

This is the load-bearing fix in item 2 (`docs/specs/store-scaling.md` §0: "`store/rows.py:177`
… a handler that materialises first and filters second gets no benefit from the index at
all"). Without it, `do_inventory_box` is scoped on its OWN first call, but any handler that
happens to run `.values()`/`.items()`/`to_payload()` earlier in the SAME session (setting
`_complete = True`) makes every later `.where()`/`.select()` in that session degrade to a
Python scan — exactly the mechanism the plan names, and exactly what item 2's own tests must
rule out, not just the route's happy path.

**What `_complete` currently gates (`store/rows.py`, read end to end before editing).**
`__iter__` (`:173-175`) and `to_dict()` (`:289-292`) call `_load_all()` (`:185-205`), which
sets `self._complete = True` after copying every source row into `self._loaded`. `MutableMapping`
derives `.values()`/`.items()`/`.keys()` from `__iter__` + `__getitem__`, so `to_payload()`'s
`self.cards.items()` (`store/master.py:1459`) is what flips `_complete` for `do_inventory`'s
own session. `__len__` (`:177-181`) branches on `_complete` too, but only to pick between
`len(self._loaded)` and `source.count() - deleted + fresh` — both are O(1)-ish (no row
filtering), so **`__len__` needs no change** and is not part of this fix; note this in the PR
so a reviewer does not go looking for a change that should not exist.

**The actual defect is in `where()` (`:213-229`) and `select()` (`:231-251`).** Both already
gate their SOURCE query on `if not self._complete:` — correct, since once `_complete` is True
every row is already in `_loaded` and re-querying the source would only refetch what is
already there. The bug is the line AFTER that gate, in both methods: the final filter scans
**all of `self._loaded`**, unconditionally:

```python
# where(), :226-229 (current)
        found = {
            key: obj for key, obj in self._loaded.items() if self._matches(obj, equals)
        }
        return [found[key] for key in sorted(found)]
```

```python
# select(), :247-251 (current)
        for key, obj in self._loaded.items():
            if self._matches(obj, equals):
                derived = self.spec.columns(obj)
                out[key] = tuple(derived.get(name) for name in columns)
        return [(key, out[key]) for key in sorted(out)]
```

Once `_load_all()` has run, `self._loaded` holds every row in the table — 50,000 of them at
the size this plan is written for — so this loop costs O(table size) on every subsequent
scoped call, in Python, with none of the benefit `cards_box` or `cards_sku`'s SQLite index
gives. This is `rows.py:177`'s degrade, exactly as the plan names it, and it is NOT fixed by
touching the `if not self._complete:` gate above it — that gate only controls whether the
SOURCE is re-asked, and the source has nothing left to say once every row is loaded. The fix
has to bound the FINAL filter, not the query above it.

**The fix: track which loaded rows this session actually wrote, and filter only those —
never the whole loaded set.** Every OTHER loaded row (fetched from the source, whether before
or after `_complete`) is known to still match the source's own index, because nothing in a
read session changes it and nothing in a write session changes a row without going through
`__setitem__`. So the bound set is exactly "rows this `Rows` instance has itself assigned,"
which `changes()` (`:274-282`) already has to compute (its own diff against `self._baseline`)
— reuse that comparison rather than inventing a second one.

Add one field, set in `__init__` and touched in exactly the two places a row's identity as
"session-written" can change:

```python
# __init__, :107-111 (current)
        self._loaded: Dict[str, Any] = {}
        self._baseline: Dict[str, dict] = {}
        self._deleted: set = set()
        self._complete = source is None
```

becomes:

```python
# __init__ (after)
        self._loaded: Dict[str, Any] = {}
        self._baseline: Dict[str, dict] = {}
        self._deleted: set = set()
        self._complete = source is None
        # Keys this SESSION has written via `__setitem__` — a brand-new record, or one
        # mutated after `_remember` loaded it from the source. Bounded by what this request
        # touched, never by the size of a prior full load: this is the set `where()`/
        # `select()` must re-check by hand after `_complete`, because the source's own index
        # cannot see an uncommitted change (D188, item 2's `rows.py:177` fix).
        self._touched: set = set()
```

```python
# __setitem__, :153-156 (current)
    def __setitem__(self, key, obj) -> None:
        key = str(key)
        self._loaded[key] = obj
        self._deleted.discard(key)
```

becomes:

```python
# __setitem__ (after)
    def __setitem__(self, key, obj) -> None:
        key = str(key)
        self._loaded[key] = obj
        self._deleted.discard(key)
        self._touched.add(key)
```

`_remember` (`:117-129`, the source-load path) does **not** add to `_touched` — it assigns
`self._loaded[key] = obj` directly rather than through `__setitem__`, which is exactly the
distinction that already exists in this file and is exactly right here: a row the source
handed us is not "touched," a row a caller wrote is.

`flushed()` (`:284-287`) clears `_deleted` once a flush has landed; it must also clear
`_touched`, since a written row's baseline now agrees with the source and the source's own
index can be trusted for it again:

```python
# flushed(), :284-287 (current)
    def flushed(self, upserts: Iterable[Tuple[str, Dict[str, Any], dict]]) -> None:
        for key, _, payload in upserts:
            self._baseline[key] = payload
        self._deleted = set()
```

becomes:

```python
# flushed() (after)
    def flushed(self, upserts: Iterable[Tuple[str, Dict[str, Any], dict]]) -> None:
        for key, _, payload in upserts:
            self._baseline[key] = payload
        self._deleted = set()
        self._touched = set()
```

Now `where()` and `select()`. The source query stays exactly as it is (still correctly gated
on `not self._complete`, since after a full load there is nothing new to fetch); what changes
is that the final filter runs over `self._touched` instead of `self._loaded`, UNIONED with
whatever the source query itself found:

```python
# where(), :213-229 (current, in full)
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
```

becomes:

```python
# where() (after)
    def where(self, **equals) -> List[Any]:
        """Every record whose indexed columns equal `equals`, in key order.

        A SCOPED CALL COSTS WHAT THE INDEX COSTS, WHATEVER RAN EARLIER IN THIS SESSION
        (D188). Bound-and-incomplete still does one indexed query plus a pass over what that
        query returned, exactly as before. Bound-and-complete (a prior `.values()`/`.items()`/
        `to_payload()` loaded everything) now ALSO queries the source rather than scanning
        `self._loaded` — the source's index answers correctly for every row this session has
        not itself written, which is every row except `self._touched`. Only `self._touched`
        is re-checked by hand, because a row this session wrote may match or stop matching in
        a way the source's own index — built from the row's LAST COMMITTED state — cannot see
        yet. Memory-backed (`self.source is None`) is unaffected: there is no index to defer
        to, so the old whole-`_loaded` scan is exactly right there and is kept.
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
            if key not in self._loaded:
                self._remember(key, text)
            keys.add(key)
        for key in self._touched:
            if key in self._deleted or key not in self._loaded:
                continue
            if self._matches(self._loaded[key], equals):
                keys.add(key)
            else:
                keys.discard(key)
        return [self._loaded[key] for key in sorted(keys)]
```

```python
# select(), :231-251 (current, in full)
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
```

becomes:

```python
# select() (after)
    def select(self, columns: Sequence[str], **equals) -> List[Tuple[str, Tuple[Any, ...]]]:
        """`(key, column values)` for matching rows, WITHOUT building objects for them.

        Same split as `where()` above, for the same reason (D188): a scoped, column-only read
        must not pay for an earlier full load either. `self._touched` is re-derived from the
        live object (never trusted from the source's stale row), everything else answers from
        the source's index.
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
            if key in self._loaded and key in self._touched:
                continue  # re-derived below, from the live object, not the stale row
            out[key] = tuple(values)
        for key in self._touched:
            if key in self._deleted or key not in self._loaded:
                continue
            obj = self._loaded[key]
            if self._matches(obj, equals):
                derived = self.spec.columns(obj)
                out[key] = tuple(derived.get(name) for name in columns)
            else:
                out.pop(key, None)
        return [(key, out[key]) for key in sorted(out)]
```

`__len__` (`:177-181`) is read again here for completeness and is **unchanged** — it never
filters `_loaded`, so it is not part of the O(table) defect this step fixes.

**Why this is safe inside `Store.write()`'s transaction (`store/session.py`).** `Store.write()`
(per D88) opens one `Inventory` bound to the database, hands it to the caller inside a `with`
block, and on a clean exit computes `changes()` per `Rows` (cards/boxes/listings) and commits
them in one transaction (`store/session.py` — the "one transaction over every table" this
class's own docstring at `store/master.py:1327-1336` describes). Everything a write handler
does to a row goes through `Rows.__setitem__` (confirmed: `allocate_capture`,
`do_put_card`/`do_put_box_claims`, `do_sell`, `do_retire` — every mutator assigns
`self.cards[key] = card`, never mutates `self._loaded` directly) — so `_touched` is a
complete record of "what this write transaction changed," which is exactly the set `where()`/
`select()` must re-check for correctness. A row this transaction has NOT written is safe to
resolve from the source's index even mid-transaction, because SQLite's `SqliteSource`
(`store/db.py:1011`) queries the connection this session holds, which has not committed
anything yet — but it has also not been asked to see anything OTHER than this session's own
writes, and this session's own writes are exactly `_touched`. There is no second writer to
race: `store/files.py`'s flock (D88's own store-of-record write-up) serialises `Store.write()`
sessions, so no other session's commit can appear mid-transaction to make the source's
"unwritten" answers stale. **No narrower read-only variant is needed — the general fix above
is correct for both read and write sessions**, which is why this step does not split into
two.

**T7 proof.** Add to `harness/tests/t7_store_and_seams.py`, beside
`check_inventory_box_route` (step 4):

```python
def check_rows_scoped_after_full_load(checks: Checks) -> None:
    """D188/item 2: `where()`/`select()` cost what the index costs, even after this
    session's own `Rows` has been fully materialised. The mechanism is `rows.py:177`'s own
    citation in docs/specs/store-scaling.md; this pins it so a later change to `Rows` cannot
    reopen it silently.
    """
    checks.note("")
    checks.note("ROWS SCOPED AFTER A FULL LOAD — store/rows.py (item 2)")

    with isolated_home():
        for at in range(1, 11):
            capture_server.do_capture(capture_payload(1, capture_id=f"a{at}", set_hint="sv9"))
        for at in range(1, 6):
            capture_server.do_capture(capture_payload(2, capture_id=f"b{at}", set_hint="sv9"))

        session = Store().read()
        before = sorted(card.key for card in session.inventory.cards.where(box=1))

        # Force the degrade condition: materialise every row in THIS session, the way
        # `to_payload()` does for `do_inventory` and the way any other handler that calls
        # `.values()`/`.items()` on `cards` would.
        session.inventory.to_payload()
        checks.ok(
            session.inventory.cards.complete,
            "the whole-store call set `_complete`, which is the condition this test exists "
            "to exercise",
        )

        after = sorted(card.key for card in session.inventory.cards.where(box=1))
        checks.equal(
            after, before,
            "and a scoped `where(box=1)` on the SAME session still returns exactly box 1's "
            "cards after a full load — correctness survives the degrade condition",
        )

        # THE PART THAT PROVES THE FIX, NOT JUST CORRECTNESS: a session that touched nothing
        # answers a scoped query with an empty `_touched` set, so the fallback's extra pass
        # costs nothing proportional to the store. A session that HAS written something is
        # exercised separately below.
        checks.equal(
            len(session.inventory.cards._touched), 0,
            "and this read-only session touched nothing, so `where()`'s post-source pass "
            "had nothing of the store's own size to scan — the loaded_count above already "
            "proves the source's index (not a loaded_dict scan) answered the query",
        )
        checks.ok(
            session.inventory.cards.loaded_count == 15,
            "loaded_count is 15 (all captured cards) because `to_payload()` forced the full "
            "load ABOVE — this number does not fall after the fix; what changes is that the "
            "SUBSEQUENT `where()` call above did not have to re-filter it by hand, which "
            "`_touched` being empty is what proves",
        )

        # --- a session that WRITES, then queries, must still see its own write -----------
        with Store().write() as snapshot:
            snapshot.inventory.cards.to_dict()  # force _complete inside the transaction too
            card = snapshot.inventory.cards["2/1"]
            card.box = 1  # move it into box 1's own index space, in memory, uncommitted
            snapshot.inventory.cards["2/1"] = card
            moved_in = sorted(c.key for c in snapshot.inventory.cards.where(box=1))
            checks.ok(
                "2/1" in moved_in,
                "and a row this transaction just wrote is found by a scoped query even "
                "though the source's own index still says box 2 — `_touched` is what "
                "catches it, not a re-scan of everything loaded",
            )
            moved_out = sorted(c.key for c in snapshot.inventory.cards.where(box=2))
            checks.ok(
                "2/1" not in moved_out,
                "and it no longer answers for box 2, which is the same `_touched` re-check "
                "the other direction",
            )
```

**Mutation arm.** Restore the old fallback — replace the fixed `where()`/`select()` bodies
above with the ORIGINAL unconditional `for key, obj in self._loaded.items()` scan — and
confirm `check_rows_scoped_after_full_load` goes red on the `len(..._touched) == 0` /
`loaded_count == 15` pairing: with the old code the assertions about `_touched` staying empty
still pass (the field would not exist at all under the reverted code, which is itself the
signal — the test should fail with an `AttributeError` on `_touched`, which counts as red).
For a mutation that keeps `_touched` but reverts only the final filter loop back to scanning
`self._loaded` in full, the correctness assertions (`after == before`) still pass (the bug is
about COST, not correctness) — which is exactly why this step's T7 case is not sufficient on
its own to prove the fix at store scale, and why the `.backup`-copy timing in "Measure" below
is still required in the PR alongside this test. Name this limitation in the PR description
rather than letting the T7 pass stand in for the timing proof.

## Call sites (complete)

Every place `getInventory()` is called today, and what happens to each:

| File:line | Purpose | After this item |
|---|---|---|
| `app/src/BoxBrowse.tsx:864` | whole-store fetch, filtered client-side by shelf | `getInventoryBox(shelf)`, refetched on shelf change and on `reloads`/`reloadToken` |
| `app/src/Home.tsx:405` | hero deck, newest identified cards store-wide | `getRecentCards(DECK_DEPTH)` — new lean route |
| `app/src/Fulfillment.tsx:451` | (a) order resolution, (b) store-wide sellable browse | (a) `getInventoryBox` per order-named box; (b) left on `getInventory()`, named as a debt for a later item |
| `app/src/Orders.tsx:1361` | (a) order-line resolution map, (b) "Walk the boxes" cross-order walk | (a) `getInventoryBox` per order-named box; (b) left on `getInventory()`, named as item 6's to close |

Every place `Inventory.to_payload()` / `do_inventory()` is called server-side:

| File:line | After this item |
|---|---|
| `server/capture_server.py:10637` (`do_GET`, exact `/inventory`) | unchanged — route kept, unused by the app, on the allowlist |
| `server/capture_server.py:3093` (`do_inventory`'s body) | unchanged — the function itself is not touched, only no longer called from anywhere this item edits |

New routes added: `GET /inventory/<box>` (`do_inventory_box`), `GET /inventory/recent`
(`do_inventory_recent`). New client functions: `getInventoryBox`, `getRecentCards`.

## Tests

**T7** (`harness/tests/t7_store_and_seams.py`):

- `check_inventory_box_route` (new, step 4 above) — three assertions: exact card set for one
  box, `loaded_count` bounded by that box's size on a fresh read, a corrupt record in another
  box does not affect this box's answer, an uncaptured box answers empty rather than 404.
- A second new check, `check_rows_scoped_after_full_load` (put it near
  `check_store_of_record`, `:1020`), for the `rows.py` fix (step 10 below, not yet written —
  see that step): load every card via `.values()` inside one session (forcing `_complete =
  True`), then call `.where(box=N)` and assert (a) the result is still correct and (b) — this
  is the part that actually tests the fix rather than just correctness — that a SECOND,
  freshly-opened session's `.where(box=N)` on the same store does not need a full load at all
  (`loaded_count` stays bounded). Model the "does a full load happen" assertion the same way
  as `check_inventory_box_route` does: read `loaded_count`/`complete` before and after, never
  a query counter.
- Mutation check: each of the three assertions above should have a corresponding "delete this
  assertion, does a mutation of `do_inventory_box`/`Rows.where` survive" pass, per this repo's
  mutation-testing convention used throughout T7 (see `check_reap`-style tests' own mutation
  notes, or simply: comment out `records_in`'s box filter and confirm
  `check_inventory_box_route`'s "none of box 2's five leaked in" assertion goes red).

**Playwright** (`app/tests/inventory.spec.ts`):

- The file already stubs `GET /inventory` extensively (grep hits at `:55`, `:264`, `:628`,
  `:641`, `:673`, `:680`, `:735`, `:4019`, `:4039` — read the block around `:4019-4039` first,
  it already discusses "`GET /inventory` is stubbed there and not…" in its own comment,
  meaning some existing tests already have opinions about this route). After step 6, most of
  those stubs need to become stubs for `GET /inventory/<box>` instead — go through each one
  and confirm the test's fixture-building helper (`ONE CARD IN THE SHAPE GET /inventory
  ANSWERS WITH…`, `:55`) is reused for the per-box route's response too, since the per-card
  shape is identical (this item's whole point).
- New assertion, in the sale/retire/reshoot specs: after the write, assert the network log
  shows **no** request to `/inventory` (the bare, store-wide path) and **does** show a
  request to `/inventory/<box>` for the box under test. `sealEveryTest()` (imported at `:4`,
  called at `:1144`) already refuses an unrouted request by default — use that same
  seal-and-assert-the-roster mechanism rather than adding a bespoke network spy: read
  `./shell.ts`'s `sealEveryTest` implementation to find how an existing test asserts "route X
  was hit, route Y was not," and follow that pattern exactly.
- One test per departed screen (`Home.tsx`, `Fulfillment.tsx`, `Orders.tsx`) confirming
  `GET /inventory` (the bare path) is not requested on that screen's normal load, EXCEPT
  Fulfillment's browse view and Orders' "Walk the boxes" — name those two exceptions in the
  test file with a comment pointing at this playbook's step 9, so the exception reads as
  intentional rather than as a test that forgot to assert something.

## Allowlist entries removed

**CORRECTED 2026-09-12, VERIFIED AGAINST THE TREE: this item removes NOTHING from the
allowlist.** This section originally copied `docs/specs/store-scaling.md` §4 as claiming
three rows closed by this item; all three are wrong, and `docs/decisions/D-per-box-read.md`
carries the full argument. `docs/specs/store-scaling.md` §4 and `00-phases.md`'s phase table
are corrected in the same PR that found this.

| Site | Shape | Actually removed by |
|---|---|---|
| `server/capture_server.py:3056` `do_inventory` | `to_payload()` | **stays permanently** — `GET /inventory` is kept, unused, on the owner's word (`00-phases.md`'s own "Where each item's decisions came from" section already said this; §4's table had not been updated to match) |
| `server/capture_server.py:8349` `_boxes_named` | `select(("box",))` | **stays** — its only caller is `do_status` (the health endpoint), which this item does not touch at all; a future item scoping `do_status` removes it |
| `store/master.py:1447` `to_payload` | `.items()` | **stays with `do_inventory`** — `do_inventory` calling it is a real, still-reachable code path (the route is kept), so the function inside it that walks the whole store cannot be "removed" without deleting the route itself, which this item explicitly does not do |

**`_boxes_named`'s callers were traced, per this section's own original instruction to do so
before checking the row off.** `grep -rn "_boxes_named" server/ store/ cli/ app/src/` finds
exactly one call site: `do_status` (`server/capture_server.py:2783`), computing `next_index`
for every box on the health endpoint. Nothing this item touches (`do_inventory_box`,
`BoxBrowse.tsx`, `Home.tsx`, `Fulfillment.tsx`, `Orders.tsx`) calls `do_status` or
`_boxes_named`. The row stays.

The two rows the plan's §4 table already marked "stays" are unaffected by any of this:
`server/capture_server.py:8388 do_boxes` (`distinct("box")`, cheap) and
`store/master.py:2378 counts` (cheap).

## Do not touch

- `server/capture_server.py:10687-10699` — the `GET /boxes/<n>` refusal. The plan's §5
  explicitly reopens this refusal's REASONING (the caller now exists) but the fix is the NEW
  `/inventory/<box>` route, not turning `/boxes/<n>` into a real route. `GET /boxes/<n>`
  stays refused; do not add a second per-box route answering a different question (box
  registry metadata) under a similar path. If a future item wants per-box registry metadata
  scoped, that is a new decision, not a side effect of this one.
- `GET /inventory` itself (`do_inventory`, `:3056-3119`) and its route registration
  (`:10636-10637`). Kept, unused, on the allowlist. No PR in this plan deletes it — deleting
  it is explicitly out of scope per the item's own framing at the top of this file.
- `Inventory.tsx`'s `CopiesFor` component and its `useSearch()`-driven copies list
  (`:628-770` area) — already sourced from `/search`, not from `GET /inventory`. Confirmed in
  step 6's opening paragraph. Do not edit.
- `app/src/frozenRank.ts` and D181's freeze semantics — `ranksAsLive`/`ranksAsShown` are
  called with the same `(key, departed, frozen)` signature whether the caller is iterating
  `Row`s or `SearchCopy`s; this item changes WHICH objects feed those calls, never the
  freeze logic itself.
- `app/src/BoxOps.tsx`'s `doMove` and every other mutation in that file — step 8 establishes
  they need no code change, only a documented reason.
- The "Walk the boxes" full-store walk (`Orders.tsx`) and Fulfillment's whole-store browse
  view — both explicitly deferred, both must keep working exactly as they do today. Narrowing
  either to "only the boxes an order names" would silently break a real capability; that is
  the mistake to avoid, not the fix.
- `store/master.py:records_in`, `_positions_in`, `_Places` — all three already do what this
  item needs. Do not refactor them "while you're in there." If a genuine bug is found in one
  of them during this work, it is a separate PR with its own T7 case, not folded into this
  item's diff.

## Measure

Reproduce `docs/specs/store-scaling.md` §1's own methodology — a `.backup` copy of the real
store, then the same copy with `cards`/`events` duplicated 20x — rather than inventing a new
one. From the primary checkout (never a worktree — the real store lives there, D43):

```bash
# 1. Copy the real store aside (read-only; never point PKMNSCAN_HOME at the live one
#    while measuring — that would race the owner's own capture server, D53).
sqlite3 inventory/store.sqlite ".backup /tmp/store-scaling-measure/base.sqlite"

# 2. Build the 20x copy the same way the plan's own measurement did — check
#    docs/specs/store-scaling.md's own repo history / PR for the exact duplication script if
#    one was committed; if not, write one that inserts each `cards`/`events` row 19 more
#    times under new keys (`box` unchanged so per-box costs scale realistically, `idx`
#    offset to avoid collisions) and re-derives the indexed columns the schema expects.

# 3. Point a throwaway PKMNSCAN_HOME at each copy in turn and time the routes:
PKMNSCAN_HOME=/tmp/store-scaling-measure/base python3 -c "
import time
from server import capture_server
t0 = time.perf_counter()
for _ in range(5):
    capture_server.do_inventory_box(1)
print('median-ish, base:', (time.perf_counter() - t0) / 5)
"
# repeat with PKMNSCAN_HOME pointed at the 20x copy
```

**Expected: `GET /inventory/<box>` is flat across the two copies**, the same claim the plan
makes for `allocate_capture`/`records_in` (measured flat at 3.9 ms, §0) — because both read
the same `records_in(box)` path over an indexed column, and duplicating rows in OTHER boxes
does not grow the box being asked about. Report the actual before/after numbers in the PR,
five runs each, median, exactly as `docs/specs/store-scaling.md`'s own table does — do not
report a single run.

Also re-run the ORIGINAL `GET /inventory` timing from §1's table (78 ms / 1,485 ms, 19.0x) on
the same two copies to confirm it is UNCHANGED by this item (it must be — the route is kept
verbatim) and to have a fresh side-by-side number for the PR description: "`GET /inventory`
still costs 78/1,485 ms and nothing calls it any more except the deliberately-deferred two
call sites named in step 9; `GET /inventory/<box>` costs N/N ms, flat."

For the `rows.py` fix specifically, measure `Rows.where()` cost after a full load, before and
after: build a memory session with 2,535 (or 50,000, from the 20x copy) cards, call
`.values()` once to force `_complete`, then time 1,000 calls to `.where(sku=X)` for a SKU that
exists — before the fix this is O(50,000) per call (a Python scan of everything loaded);
after, it should cost what the indexed SQL query costs, close to the flat `records_in` figure
above.

## Risks

- **The search-driven cross-box rail (step 6b) is the highest-risk rewrite in this item.**
  It changes what data three `useMemo`s read (`order`, `shelves`, `matchesByShelf`) without
  changing what they're supposed to compute. A subtle mismatch between `Row`-shaped and
  `SearchCopy`-shaped section keys (`row.card.section` vs `copy.place.section` — confirm
  these are the same TYPE, both `number | undefined`, before assuming the string keys built
  from them (`` `${shelf}/${section ?? '?'}` ``) collide correctly) would silently rank boxes
  wrong under a search with no test failure, because nothing today asserts the RANKING order
  under search, only that matched rows appear. Write a new Playwright test that searches for
  a card known to exist in two boxes and asserts the rail shows both boxes with the right
  counts, before trusting this refactor.
- **Fulfillment's browse view and Orders' "Walk the boxes" are left on the old full-walk
  call, by design** — but this is exactly the kind of decision the owner's "flag a rotted
  ruling, don't defer to it" instruction (CLAUDE.md) asks to be surfaced rather than buried.
  Say so plainly in the PR: "this item does not close `GET /inventory` on two call sites;
  item 6 does."
- **Step 10's `_touched` set is correct only as long as every mutator writes through
  `Rows.__setitem__`.** The step's "safe inside `Store.write()`" argument depends on this —
  a future handler that reaches into `self._loaded[key]` and mutates the object in place
  without reassigning it through `__setitem__` would change a row's columns without adding it
  to `_touched`, and `where()`/`select()` would then trust the source's stale index for it.
  This is not a new risk this fix introduces — `changes()` (`:274-282`) already depends on the
  same discipline (a mutated-in-place object still gets diffed correctly there because it
  re-dumps every key in `_loaded`, but `_touched` is a stricter dependency, since it is
  consulted BEFORE the final dump). Grep for any `self.cards[key].<attr> = ...` pattern that
  is not followed by `self.cards[key] = self.cards[key]` before relying on this fix, and add
  one if a genuine in-place mutator is found rather than assuming the convention holds.
- **`SqliteSource.top()` is new surface on the `Source` contract.** Every OTHER backing of
  that contract (a mock, a test double, anything besides `SqliteSource`) needs the method
  too or it breaks at attribute-access time rather than at a typed boundary (Python duck
  typing, per `rows.py`'s own docstring: "duck-typed rather than declared"). Grep for every
  class that currently implements `get`/`has`/`count`/`all`/`where`/`select`/`distinct` (the
  contract's full method list, `rows.py:36-49`) before adding `top` — there may be more than
  one.
- **`do_inventory_box`'s narrowed `listings` could silently break a screen that reads a
  listing for a SKU NOT in the current box** — verified in this playbook that `Inventory.tsx`
  only ever reads `listings[group.sku]` for the SELECTED card's own group, and the selected
  card is always in the current box, so this should be safe — but re-verify after step 6 is
  written, since a mid-refactor mistake (e.g., holding onto a STALE `listings` map from a
  previous box while `selected` still points at the old box during the fetch-in-flight
  window) could reintroduce exactly this bug transiently. Test the box-switch loading state
  explicitly.
