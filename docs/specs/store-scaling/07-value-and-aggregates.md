# Item 7 — the value route paginated, and the aggregates in SQL

Source: `docs/specs/store-scaling.md` §3 item 7 and its §4 allowlist rows for
`do_pipeline_value`, `_release_plan`, `box_views`, `_box_names`, `_on_hand_by_run`. This file
is the implementation playbook; it does not itself change code. It also carries the owner's
2026-09-12 ruling that item 7's row list PAGINATES rather than merely switching to a cheaper
walk — that ruling post-dates the spec file's own item-7 paragraph, which only asks for "a
`select` of the columns it ranks on" and says nothing about pagination. Both are done here.

## Goal and done-when

**(A) `do_pipeline_value`** (`server/pipeline_routes.py:3117`, the `.values()` walk at
`:3202`, behind `GET /pipeline/value` at `server/capture_server.py:10744-10755`, consumed by
`#/pricing?band=top|bottom` — `app/src/ValueBands.tsx`) ranks every on-hand card by market.
Today it builds a full `Card` dataclass for every row in the store (`inventory.cards.values()`
triggers `Rows._load_all()`, which JSON-parses and constructs a `Card` for every stored
payload — `store/rows.py:177-196`), sorts the whole list, and ships every row to the browser
in one response, which then does all percentile/cut-off slicing and "show more" paging
client-side over the full array (`app/src/ValueBands.tsx:150-177`, `608-618`,
`660-687`). At 2,535 cards that is 78–185 ms and a response the owner measured around 739 KB
(`app/src/server.ts:2459` — "2,245 rows, ~739KB, 0.11s server-side"); at 50,000 cards
(≈20x) the equivalent walk elsewhere in this store measures 18–21x
(`docs/specs/store-scaling.md` §1's table), which puts this route in the multi-second, multi-MB
range for a screen the owner opens to glance at a handful of cards.

The owner's ruling: **paginate**, "as long as it's well planned." The plan, confirmed against
the actual code below:

1. The **aggregates** — `boxes`, `unrankable`, `totals`, `sources`, `threshold` — are computed
   server-side over **every** on-hand row, via a column-only `select()` (never a built `Card`
   object), so D159's "nothing on hand is omitted" figures stay whole no matter which page of
   the row list is open. This is unavoidably O(cards) — an aggregate over the whole store has
   to touch the whole store — but the fix removes the per-row cost of building a `Card`
   (JSON-parsing every field, most of them unused here), which is where the 19–21x scaling
   actually comes from (`docs/specs/store-scaling.md` §0: "materialises the whole `cards`
   table... and then does per-card work over it").
2. The **row list** (`copies`) is paged by rank, with a cursor stable across pages even if the
   store changes between two page fetches: `?band=top&after=<cursor>&limit=N`.
3. Percentile bands (top/bottom 1%/5%/10%) and the cut-off band do **not** need the row list
   to compute their counts — every count they need is already arithmetic over the aggregate
   figures (`totals.valued`, and the per-box `under_cutoff`/`at_or_over` this route already
   computes, `:3245-3253`). Only the **rows to display** need paging. This is the load-bearing
   finding of this playbook (§"Read first" below) and it is what keeps the client's percentile
   math correct without shipping the whole store.

**(B) `box_views`** (`cli/resolve.py:372`, the `inventory.cards.values()` walk at `:397`,
called from `server/pipeline_routes.py:2020`, `:2732`, `:3178`) builds full `Card` objects for
every card in the store to answer "what section/card number does this box render right now"
(D58). Two of its three callers only ever ask about a bounded set of boxes (the boxes a run's
own positions name); the third (`do_pipeline_value`) genuinely needs every box in the store.
The fix is **both** halves the plan names: a per-box path through `Inventory.records_in`
(`store/master.py:1522`) for the two bounded callers, and a column-only `select()` fallback
for the store-wide caller — never a raw SQL rewrite, and never Card objects in either path.

**(C) `_release_plan`** (`server/capture_server.py:4526`, the `.items()` walk at `:4551`)
aggregates one box's SKUs against every OTHER box those SKUs also sit in (D34's release
preflight). Also in scope by the plan's own §4 allowlist: `_box_names`
(`server/pipeline_routes.py:797`, `select(("box","run"))` with no filter, `:838`) and
`_on_hand_by_run` (`server/pipeline_routes.py:2429`, `select(("run","state"))` with no
filter, `:2444`). All three become **two rounds of the existing indexed `equals` filter** on
`Rows.select` — `box=` and `sku=` for `_release_plan`, `box=` for `_box_names`, `run=` for
`_on_hand_by_run` — never a new SQL primitive. `grep -n "GROUP BY" store/*.py` returns nothing
today; this playbook does **not** add the repo's first one, because the existing
`select(columns, **equals)` machinery already does the job in two indexed passes (see
"Steps" §C below) — the "no bandaids" rule (`CLAUDE.md`, `docs/decisions/` — check whether
the primitive already exists before building around its absence) applies directly here: the
primitive (`Rows.select` with an `equals` filter) already exists, and the task description's
own suggestion of a raw grouped query is the "check whether the primitive already exists"
step this playbook is doing on the implementer's behalf.

**Done-when:**
1. `GET /pipeline/value` with no query string still returns exactly today's shape — full
   `copies`, `boxes`, `unrankable`, `totals`, `threshold`, `sources` — so `harness/tests/
   t7_store_and_seams.py:check_value_table` (`:26343`, calling `pipeline_routes.
   do_pipeline_value()` with zero arguments) passes unmodified.
2. `GET /pipeline/value?band=top|bottom|gaps&box=<n>&after=<cursor>&limit=N` returns
   `{rows, next, total, ...aggregates}` per the wire shape in "Steps" below, and the
   aggregates block is byte-identical to (1)'s aggregate fields for the same store state.
3. `app/src/ValueBands.tsx` fetches pages instead of slicing one full array; the percentile
   and cut-off chip counts are computed from the aggregates alone (no row-list fetch needed
   to show them); "Show N more" and the gaps disclosure both become real network fetches
   with the same button text and the same `"N of M shown"` line.
4. `box_views` gains an optional `boxes=` parameter; its two bounded callers pass it; its
   one store-wide caller does not, and its no-argument behavior for every existing direct
   caller (`cli/resolve.py:785`, `:1923`, and every T7 site listed in "Tests") is unchanged.
5. `_release_plan`, `_box_names`, `_on_hand_by_run` no longer walk `.items()` / a filter-less
   `select()` over the whole `cards` table; each is bounded by a real filter.
6. All five rows leave `docs/specs/store-scaling.md` §4's allowlist (see "Allowlist entries
   removed").
7. `make harness` (all nine suites) is green, and `.backup`-copy measurements are taken and
   reported per "Measure" below.

## Depends on / conflicts with

- **Item 1 (the `unscoped walk` guard, `docs/specs/store-scaling/01-guard.md`)** should land
  first per the plan's own ordering. If it has not, this item's new code must not trip it —
  every `select()` call this playbook adds carries a real `equals` filter (`box=`, `sku=`, or
  `run=`), which is exactly what the guard is meant to allow through. If the guard's allowlist
  or pattern already exists when this item lands, run `make docs-audit` after these changes
  and confirm the five allowlist rows below actually disappear rather than silently staying
  `ok` for the wrong reason (a scoped call that still matches the guard's pattern is a guard
  bug, not a reason to keep the allowlist entry — `docs/specs/store-scaling/06-orders.md`'s
  "Allowlist entries removed" section makes the identical point).
- **Item 4 (`_copies_out`, `04-copies-out.md`, else
  `store-scaling.md` §3 item 4)** also edits `cli/resolve.py` — it touches
  `cli/resolve.py:487` and the two per-SKU helpers beside it, this item touches
  `cli/resolve.py:372-425` (`box_views`). Different functions in the same file; a merge
  conflict is likely if both land as concurrent branches (adjacent line ranges), not a
  logical conflict. `do_pipeline_value` (`:3117`) calls `_readings()` (`:2975`), which itself
  calls `run_resolve._copies_out` indirectly through `_committed_keys`/`_copies_out` in
  `do_pipeline_worklist`'s neighborhood (`:3178-3183` calls `run_resolve.box_views`, not
  `_copies_out`, directly) — confirm at implementation time with
  `grep -n "_copies_out\|_committed_keys" server/pipeline_routes.py` that item 4's rewrite of
  `_copies_out` has not changed its call signature before this item's code lands on top of
  it.
- **Item 5 (`docs/specs/store-scaling/05-readings-writer.md`)** changes `_readings()`
  (`server/pipeline_routes.py:2975`), which `do_pipeline_value` calls at `:3178`
  (`found, sources = _readings()`). This item does not change `_readings()` or its return
  shape (`Tuple[Dict[str, _Reading], List[dict]]`); if item 5 has landed, `_readings()`'s
  *behavior* changes (it reads a `readings` table instead of re-parsing CSVs) but its
  *signature* does not, so this item's code is unaffected either way — confirm the signature
  is unchanged with `grep -n "^def _readings" server/pipeline_routes.py` before writing code.
- **Item 2 (the per-box read, `server/capture_server.py:10687`)** reopens `GET
  /inventory/<box>` and touches `store/rows.py:177`'s "materialise-then-filter" fallback.
  This item's `box_views` change does not depend on that fallback being fixed — the per-box
  branch here calls `Inventory.records_in`, which is `self.cards.where(box=box)`
  (`store/master.py:1528`), an indexed query regardless of whether `rows.py:177`'s
  degrade-to-Python-filtering bug is fixed. If item 2 lands first, nothing here needs
  re-testing; if it lands after, nothing here needs to wait for it.
- **No conflict with item 6** (`do_orders`, `docs/specs/store-scaling/06-orders.md`) — that
  item's `_Places.for_keys` and this item's `box_views(boxes=...)` are two independent
  answers to the same shape of problem (a per-box, bounded read replacing a full-store one)
  in two different modules (`server/capture_server.py`'s `_Places` vs.
  `cli/resolve.py`'s `box_views`) with two different callers. They do not call each other.

## Read first

Run these before writing any code — they are the load-bearing facts this playbook's design
rests on, not decoration:

```bash
# Confirm do_pipeline_value's only external consumer, and that it is safe to redesign the
# wire freely (no second caller depends on today's unpaginated shape).
grep -rn "getValueTable\|pipeline.value" app/src/*.ts app/src/*.tsx server/*.py

# Confirm every field ValueCopy/do_pipeline_value reads off a card is an INDEXED column —
# this is what makes the "column select instead of built Card objects" fix possible at all.
grep -n "column_names=" store/master.py
sed -n '2480,2497p' store/master.py

# Confirm the percentile/cut-off math the client does today, and that its inputs
# (`pool.length`, i.e. count of priced rows) are exactly `totals.valued` or a box's `valued`
# — never anything from individual ROWS.
sed -n '150,177p' app/src/ValueBands.tsx
sed -n '386,401p' app/src/ValueBands.tsx

# Confirm no existing GROUP BY precedent — this is why _release_plan is redesigned as two
# indexed select() passes rather than a new SQL primitive.
grep -n "GROUP BY" store/*.py

# Confirm records_in's cost shape (bounded by one box's cards, plus a store-wide but
# index-range-scan-cheap NULL check) before relying on it in box_views's bounded branch.
sed -n '1492,1531p' store/master.py

# Confirm every current caller of box_views, so none is missed.
grep -n "box_views(" cli/resolve.py server/pipeline_routes.py harness/tests/*.py
```

**The finding that makes pagination NOT break the percentile bands**: `app/src/
ValueBands.tsx:176` computes a percentile band's row count as
`Math.round((rows.length * SHARES[cut]) / 100)` where `rows` is `pool` — the full list of
priced rows for the current `end`/`box` scope (`:150-155`, `:369`). `pool.length` is exactly
the count of priced cards in scope, which the aggregates block already reports: store-wide as
`totals.valued` (`server/pipeline_routes.py:3348`, `"valued": valued`) and per-box as
`ValueBox.valued` (`:3319`, `"valued": seat["valued"]`). The cut-off band's count is likewise
already computed store-wide as the sum of every box's `at_or_over`/`under_cutoff`
(`:3247-3253`) — this playbook adds two convenience totals (`totals.under_cutoff`,
`totals.at_or_over`) rather than making the client sum `boxes[]` itself, since a box-scoped
request already gets its per-box figures for free from `ValueBox`. **No band's chip count
ever needs a row.** Only the rows a human is about to look at do.

## Steps

### A1. Extract the per-card classification into a shared, column-only pass —
`server/pipeline_routes.py:3117-3350`

Replace the `for card in inventory.cards.values():` loop at `:3202` with a `select()` over
exactly the columns the loop reads. Cross-check against `ValueCopy`'s fields
(`app/src/types.ts:3355-3386`) and the loop body (`:3202-3269`): every field the loop reads
off `card` — `card.box`, `card.index`, `card.sku`, `card.state`, `card.name`, `card.set_hint`,
`card.condition`, `card.game` — is an indexed column on the `cards` table
(`store/master.py:2485-2488`: `"box", "idx", "state", "sku", "condition", "capture_id",
"name", "number", "game", "set_hint", "run", "captured_at", "state_at", "cid"`). So the whole
loop can run over `inventory.cards.select(("box", "idx", "sku", "state", "name",
"set_hint", "condition", "game"))` and build **no** `Card` object at all:

```python
def _value_rows(inventory, found, book, threshold, cut, views, answers, listings):
    """One column-only pass over every on-hand card. Returns (copies, aggregates) exactly
    as `do_pipeline_value`'s body builds them today, unsorted — sorting is the caller's job,
    once, over whichever of the two callers needs it."""
    copies: List[dict] = []
    tally: Dict[int, dict] = {}
    unrankable = {_NEVER_IDENTIFIED: 0, _READ_NOTHING: 0, _NO_READING: 0}
    by_box: Dict[str, int] = {}
    total = Decimal("0")
    valued = 0

    for _key, (box_raw, idx_raw, sku_raw, state, name, set_hint, condition, game) in (
        inventory.cards.select(
            ("box", "idx", "sku", "state", "name", "set_hint", "condition", "game")
        )
    ):
        if state in master.TERMINAL_STATES:
            continue
        try:
            box, index = int(box_raw), int(idx_raw)
        except (TypeError, ValueError):
            continue
        sku = str(sku_raw or "")
        # ... exactly `do_pipeline_value`'s existing body from here, `reading = found.get(sku)`
        # through the `seat[...]` tally and the `copies.append({...})` — unchanged, only its
        # source is now the tuple's `name`, `set_hint`, `condition`, `game` in place of
        # `card.name`, `card.set_hint`, `card.condition`, `card.game`. Do not change any
        # rule inside this body — only the source of each field.
        ...
    return copies, {
        "tally": tally, "unrankable": unrankable, "by_box": by_box,
        "total": total, "valued": valued,
    }
```

`do_pipeline_value()` (no args, called by T7 and any other direct caller) becomes:

```python
def do_pipeline_value() -> dict:
    # ... unchanged setup: Store().read(), _readings(), box_views(inventory), corpus, cut ...
    copies, agg = _value_rows(inventory, found, book, threshold, cut, views, answers, listings)
    copies.sort(key=_value_sort_key)  # extract today's lambda at `:3296-3303` verbatim
    names = _box_names()
    boxes = _boxes_payload(agg["tally"], names)  # extract `:3315-3335` verbatim
    return {
        "at": master.now(), "basis": "market", "threshold": threshold,
        "sources": sources, "copies": copies, "boxes": boxes,
        "unrankable": {
            "total": sum(agg["unrankable"].values()), **agg["unrankable"],
            "by_box": agg["by_box"],
        },
        "totals": {
            "cards": len(copies), "valued": agg["valued"],
            "value": tcgcsv.format_price(agg["total"]),
            # NEW, additive fields — see "Read first": the sum of every box's own
            # under_cutoff/at_or_over, so a store-wide chip count needs no row list either.
            "under_cutoff": sum(seat["under"] for seat in agg["tally"].values()),
            "at_or_over": sum(seat["over"] for seat in agg["tally"].values()),
        },
    }
```

Extract `_value_sort_key` from the existing `copies.sort(key=lambda row: (...))` at
`:3296-3303` as a named module-level function — it is needed twice (full sort here, and the
paginated sibling below).

### A2. The paginated sibling — `server/pipeline_routes.py`, new function beside
`do_pipeline_value`

```python
_VALUE_PAGE_DEFAULT = 200  # matches app/src/ValueBands.tsx's PAGE constant, `:66`


def _value_cursor_encode(row: Optional[dict]) -> Optional[str]:
    """An opaque token naming a row's position in the SAME sort order `_value_sort_key`
    produces — never a bare integer offset, because an offset desyncs the moment a sale or
    a new capture changes which row sits at that offset between two page fetches. Base64 of
    a small JSON object; the client never inspects it, only echoes it back as `after`."""
    if row is None:
        return None
    payload = {"market": row["market"], "box": row["box"], "index": row["index"]}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def _value_cursor_decode(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8"))
    except (ValueError, TypeError):
        # AN UNREADABLE CURSOR IS THE FIRST PAGE, NEVER A REFUSAL — a bookmarked or
        # copy-pasted URL with a stale/mangled `after` should not 400; it should restart
        # the band from the top, which is the harmless direction to fail toward.
        return None


def do_pipeline_value_page(
    *, band: str, box: Optional[int], after: Optional[str], limit: int
) -> dict:
    """`GET /pipeline/value?band=top|bottom|gaps&box=&after=&limit=` — one page of the same
    ranked list `do_pipeline_value()` returns whole, plus the same aggregates.

    `band` PARTITIONS THE SORTED LIST AND NEVER RE-SORTS IT — `top` is the priced rows in
    `_value_sort_key` order, `bottom` is the SAME rows in the reverse of that order (an
    actual reverse comparator, not `list.reverse()` on a pre-sorted Python list, so a tie
    group's internal order is deterministic in both directions rather than an artifact of
    which end the caller reversed from), and `gaps` is the unpriced rows in `(box, index)`
    order — natural store order, since there is no market to rank them by. `box` narrows
    every band to one drawer's rows without changing which band's rule chose them.
    """
    if band not in ("top", "bottom", "gaps"):
        raise BadRequest(HTTPStatus.BAD_REQUEST, "band_unknown", f"No such band: {band!r}")
    inventory = Store().read().inventory
    found, sources = _readings()
    views = run_resolve.box_views(inventory)  # store-wide caller — see Steps B3
    try:
        book = corpus.Corpus.read()
    except (decisions.MalformedDecisions, ValueError, OSError):
        book = corpus.Corpus()
    answers = book.to_payload().get("skus") or {}
    threshold = _policy_threshold(book)
    cut = _market_of(threshold) or pricing_mod.FLOOR

    copies, agg = _value_rows(
        inventory, found, book, threshold, cut, views, answers, inventory.listings
    )
    if box is not None:
        copies = [row for row in copies if row["box"] == box]

    if band == "gaps":
        scoped = sorted(
            (row for row in copies if row["market"] is None),
            key=lambda row: (row["box"], row["index"]),
        )
        cursor_key = lambda row: (row["box"], row["index"])
    else:
        priced = [row for row in copies if row["market"] is not None]
        priced.sort(key=_value_sort_key)
        scoped = priced if band == "top" else list(reversed(priced))
        cursor_key = _value_sort_key if band == "top" else _value_sort_key_reversed

    after_row = _value_cursor_decode(after)
    start = 0
    if after_row is not None:
        # SKIP EVERYTHING UP TO AND INCLUDING THE CURSOR'S KEY, comparing by VALUE rather
        # than by a remembered index — a card that left the store between two page fetches
        # shifts every later index, and comparing keys is what keeps the second page
        # starting in the right place regardless.
        marker = (after_row.get("market"), after_row.get("box"), after_row.get("index"))
        for i, row in enumerate(scoped):
            if (row["market"], row["box"], row["index"]) == marker:
                start = i + 1
                break
        else:
            start = len(scoped)  # the row the cursor named is gone; nothing "after" it remains
    page = scoped[start : start + limit]
    next_cursor = _value_cursor_encode(page[-1]) if start + limit < len(scoped) else None

    names = _box_names()
    boxes = _boxes_payload(agg["tally"], names)  # SAME helper as `do_pipeline_value`
    return {
        "at": master.now(), "basis": "market", "threshold": threshold,
        "sources": sources,
        "rows": page, "next": next_cursor, "total": len(scoped),
        "boxes": boxes,
        "unrankable": {
            "total": sum(agg["unrankable"].values()), **agg["unrankable"],
            "by_box": agg["by_box"],
        },
        "totals": {
            "cards": sum(seat["cards"] for seat in agg["tally"].values()),
            "valued": agg["valued"], "value": tcgcsv.format_price(agg["total"]),
            "under_cutoff": sum(seat["under"] for seat in agg["tally"].values()),
            "at_or_over": sum(seat["over"] for seat in agg["tally"].values()),
        },
    }
```

`_value_sort_key_reversed` is `_value_sort_key`'s tuple negated the same way `_value_sort_key`
itself negates market (`-(_market_of(...) or Decimal("0"))`) but with box/index descending
instead of ascending, so `bottom`'s tie-break is a real independent ascending-by-cheapness
order and not a `list.reverse()` of `top`'s array (which would silently reverse tie order
too — a deliberate, documented behavior refinement over today's `app/src/
ValueBands.tsx:154` `[...priced].reverse()`; call this out in the PR description as an
intentional small change, not an oversight, since a mutation test might catch the old
reversed-tie-order as "removed" behavior). Write `_value_sort_key_reversed` explicitly rather
than deriving it by negating `_value_sort_key`'s output, so a reader sees the actual
comparator.

**Route dispatch** — `server/capture_server.py:10744-10755`. The docstring comment there
currently reads *"No band, no filter and no percentile in the query string"* — this is now
false and must be corrected in the same edit, not left as a stale claim (`CLAUDE.md`'s own
rule about a claim a check can no longer support):

```python
if path == "/pipeline/value":
    query = parse_qs(parsed.query, keep_blank_values=True)
    band = (query.get("band") or [None])[0]
    if band is None:
        return self._json(HTTPStatus.OK, pipeline_routes.do_pipeline_value())
    box_raw = (query.get("box") or [None])[0]
    box = int(box_raw) if box_raw not in (None, "") else None
    after = (query.get("after") or [None])[0]
    limit_raw = (query.get("limit") or [None])[0]
    limit = int(limit_raw) if limit_raw not in (None, "") else pipeline_routes._VALUE_PAGE_DEFAULT
    return self._json(
        HTTPStatus.OK,
        pipeline_routes.do_pipeline_value_page(band=band, box=box, after=after, limit=limit),
    )
```

Follow the `GET /pipeline/pricing` handler's own query-parsing style two branches up
(`server/capture_server.py`, `asked = parse_qs(parsed.query, keep_blank_values=True).get
("run") or []`) rather than inventing a new convention.

### A3. The client — `app/src/server.ts`, `app/src/ValueBands.tsx`

**`app/src/server.ts:2461-2466`** (`getValueTable`) is no longer called once the client
paginates — remove its one call site rather than keeping a function with no caller. Add two
new functions instead, following `getExportScope`'s `URLSearchParams` pattern
(`app/src/server.ts:2603-2616`):

```typescript
export type ValueAggregates = Pick<
  ValueTable, 'at' | 'basis' | 'threshold' | 'sources' | 'boxes' | 'unrankable'
> & { totals: ValueTable['totals'] & { under_cutoff: number; at_or_over: number } }

export type ValuePage = ValueAggregates & { rows: ValueCopy[]; next: string | null; total: number }

export async function getValuePage(options: {
  band: 'top' | 'bottom' | 'gaps'
  box?: number | null
  after?: string | null
  limit?: number
}): Promise<ValuePage> {
  const query = new URLSearchParams()
  query.set('band', options.band)
  if (options.box !== undefined && options.box !== null) query.set('box', String(options.box))
  if (options.after) query.set('after', options.after)
  if (options.limit !== undefined) query.set('limit', String(options.limit))
  return (await request(`/pipeline/value?${query.toString()}`, NO_CACHE)) as ValuePage
}
```

Add `ValueAggregates`/`ValuePage` to `app/src/types.ts` beside `ValueTable`
(`:3421-3445`), and add the two new `totals` fields (`under_cutoff`, `at_or_over`) to
`ValueTable` itself too, since `do_pipeline_value()`'s no-args response now carries them as
well (§A1) — keep the two response shapes' `totals` field lists in sync so a future reader
does not have to remember which route has which fields.

**`app/src/ValueBands.tsx`** — the rewrite is real work, not a one-line swap, because the
component currently treats `table.copies` as a single in-memory array it filters/sorts/slices
four different ways (`ordered`, `slice`, `stacks`, `pulls`, all `:121-192`). Restructure
around **two fetches**:

1. On mount and whenever `end`/`cut`/`price`/`box` change, fetch aggregates alone — a
   dedicated `getValueAggregates()` call with no `rows`, not a `limit: 0` page ("fetch a page
   and throw the rows away" is the kind of shortcut this repo's rules call a bandaid). Compute
   `counts.p1/p5/p10/cutoff` from it by pure arithmetic (`Math.round(valued * SHARE / 100)`;
   `under_cutoff`/`at_or_over` read directly) — **no row fetch needed for chip counts**, per
   "Read first".
2. Once a `cut` is chosen, compute the WANTED row count (`p1/p5/p10`: arithmetic on `valued`;
   `cutoff`: `under_cutoff`/`at_or_over` directly; `price`: unknown ahead of time) and fetch
   via `getValuePage({ band: end, box, limit: wanted ?? PAGE })`. For `price`, keep the
   existing "Show N more" pattern (`:611-618`) backed by real `getValuePage({ ..., after:
   cursor, limit: PAGE })` calls, stopping once a page's last row fails the typed-price
   predicate (unchanged from `slice`'s logic at `:157-170`, applied per page) or `next` is
   `null`.
3. The `gaps` disclosure (`:622-690`) becomes `band: 'gaps'` fetches with the same "Show N
   more" mechanics, driven by `unrankable.total` instead of a locally-held full array.
4. `stacks()` (`:182-192`, "copy N of M") groups the WHOLE `pool` by SKU — with `pool` no
   longer fully in memory, add a `stack_index`/`stack_of` pair to `ValueCopy`, computed in
   `_value_rows` from a SKU→count map built during the same one-pass loop, and drop the
   client-side `stacks()`. (The alternative — "copy N of M" correct only within the fetched
   page — silently breaks the claim at any store size and is rejected.)
5. `pulls()` (`:107-142`, the "N separate spots across M drawers" sentence) genuinely needs
   the WHOLE scoped band to count contiguous index runs — not derivable from `valued`/
   `under_cutoff` alone. Compute it server-side as a `reach` object (grouped by `(box,
   index)` per band, arithmetic beside the tally the aggregate pass already builds) rather
   than relabeling the sentence to describe only what has loaded so far.

## Call sites (complete)

- `server/capture_server.py:10748` — the `GET /pipeline/value` route dispatch. Edited per §A2.
- `harness/tests/t7_store_and_seams.py:26460`, `:26576` — direct calls to
  `pipeline_routes.do_pipeline_value()`. Unedited (T7-parity requirement).
- `app/src/ValueBands.tsx:349` — `getValueTable()` call inside `read()`. Replaced per §A3.
- `cli/resolve.py:785`, `:1923` — `box_views(inventory)` calls INSIDE `cli/resolve.py`
  itself (not `pipeline_routes.py`). Read each before touching anything: if either resolves a
  bounded set of boxes (a single run's positions, a single reconcile's SKUs), it is a THIRD
  candidate for the `boxes=` parameter and should take it for the same reason `pipeline_
  routes.py:2020`/`:2732` do; if either is genuinely store-wide (e.g. a full-store report
  command run from the CLI, where "slow" is acceptable because it is not on a polled screen),
  leave it on the no-args path. This playbook does not pre-judge which, because it did not
  read the surrounding function bodies at `:785` and `:1923` in full — do that first.
- `server/pipeline_routes.py:2020` — `_relabel_positions`'s `views = ... run_resolve.
  box_views(inventory)`. Before this call, collect `{at.get("box") for entry in
  table.get("skus") or () for at in entry.get("positions") or () if isinstance(at, dict)}`
  and pass it as `boxes=`.
- `server/pipeline_routes.py:2732` — `do_pipeline_worklist`'s `views = run_resolve.
  box_views(snapshot.inventory) if snapshot is not None and ledger else {}`. Collect
  `{p.get("box") for row in merged.values() for p in row.get("positions") or ()}` from
  `merged` (already fully built by this line) and pass as `boxes=`.
- `server/pipeline_routes.py:3178` (inside `do_pipeline_value`) and the equivalent line inside
  the new `do_pipeline_value_page` (§A2) — `views = run_resolve.box_views(inventory)`. **No**
  `boxes=` argument — this caller genuinely needs every box.
- `server/capture_server.py:4636` (`do_box_listings`) and `:4714`
  (`do_release_box_listings`) — both call `_release_plan(inventory, box)`. Signature
  unchanged; only `_release_plan`'s body changes (§C below).
- `server/pipeline_routes.py:1908` (inside `do_pipeline_runs`, `names = _box_names()`) and
  `:2564` (inside `do_pipeline_worklist`, before the run loop, `names = _box_names()` —
  confirm exact line at implementation time; it is the call immediately preceding `for entry
  in sorted(root.iterdir())` around `:2564-2584`) — both unaffected by signature; `_box_names`'
  body changes (§C below) to scope its walk to the box registry's own (small) key set instead
  of scanning every card.
- `server/pipeline_routes.py:2579` — `on_hand = None if snapshot is None else
  _on_hand_by_run(snapshot.inventory)`. Signature changes: `_on_hand_by_run(inventory, runs)`
  — the caller must collect the joined run names it is about to loop over BEFORE this line
  (the loop starting at `:2584`, `for entry in sorted(root.iterdir())`, already filters
  `manifest.get("joined")`; hoist that filter into a first pass that just collects names,
  then pass the resulting list here, then reuse the parsed manifests in the main loop rather
  than re-reading them — check whether `_manifest(entry)` is cheap enough to call twice per
  run before deciding whether to cache it).

## Tests

### `harness/tests/t7_store_and_seams.py`

- **`check_value_table`** (`:26343`) — the load-bearing pin for `do_pipeline_value()`'s
  no-args shape. Every existing assertion (`:26460-26576`) must pass unmodified: the unit is
  the copy not the SKU, terminal cards excluded, the newest reading wins per SKU, the three
  `why` causes, the exact `unrankable` dict (`:26495-26504`), sort order and tie-break, the
  drawer-is-not-a-rollup arithmetic, the label composed fresh, and the empty-store case
  (`:26635-26639` — both new `totals` fields must read `0` there; check whether the
  `checks.equal` at `:26576-26580` compares the whole `totals` dict or a subset before
  assuming the new fields are covered for free — assert them explicitly if not).
- **New**: `check_value_page` (add near `check_value_table`, called from `run()` beside it at
  `:26639`). Build the same fixture `check_value_table` uses (or share its store-building
  helper if one is factored out) and assert:
  - `do_pipeline_value_page(band="top", box=None, after=None, limit=2)["rows"]` equals the
    first two rows of `do_pipeline_value()["copies"]` (filtered to priced-only, since `top`
    never includes unpriced rows) — the two code paths must never disagree.
  - Paging through with the returned `next` cursor, `limit=2` each time, reconstructs the
    exact same priced-row sequence `do_pipeline_value()` returns whole.
  - `band="bottom"` reconstructs the priced rows in ascending-market order with box/index
    ascending WITHIN a tie (the deliberate `_value_sort_key_reversed` behavior — assert this
    explicitly, since it differs from a literal `list.reverse()`).
  - `band="gaps"` reconstructs every unpriced row in `(box, index)` order and its `total`
    equals `unrankable["total"]`.
  - **A D159 arm, required by this playbook's own instructions**: build a store with at least
    one card of each of the three `why` causes (`never_identified`, `read_nothing`,
    `no_reading`) AND at least one priced card, request `band="top"` with `limit=1` (i.e.
    open the very first page), and assert the returned `unrankable` block still counts all
    three causes at their full store-wide figures — the aggregates must never shrink to "what
    this page could see." Repeat the same assertion with `band="bottom"` and `band="gaps"`
    open at page 1: the `boxes[]`, `unrankable`, and `totals` blocks must be identical across
    all three band requests against the same store state, since they describe the whole
    store and not the band.
  - A cursor naming a row that has since left the store (simulate: fetch page 1, mark that
    row's SKU sold via `Store().write()`, fetch page 2 with the stale cursor) still returns
    the correct remaining rows rather than skipping or duplicating one — the "SKIP EVERYTHING
    UP TO AND INCLUDING THE CURSOR'S KEY, comparing by VALUE" design in §A2 exists
    specifically for this case; write the test to actually exercise it rather than trusting
    the design note.
  - A malformed `after` token returns page 1 rather than 400ing (§A2's `_value_cursor_decode`
    contract).
- **`check_pricing_labels`** (`:15968`, exercises `_relabel_positions` via `resolve.
  box_views(inventory)` calls at `:15955`, `:15965`) — unmodified calls (no `boxes=` argument)
  must still pass, since this test calls `box_views` directly rather than through
  `pipeline_routes.py:2020`'s new `boxes=`-passing call site. Confirm this test does NOT
  itself need updating — it exercises the function's default no-`boxes` behavior, which this
  playbook does not change.
- **New**: a `box_views(inventory, boxes={...})` case beside `check_pricing_labels` or
  `check_consolidated_numbering` (`:8543`) asserting: (a) the bounded call agrees with the
  unbounded call on the SAME boxes, on a store with several boxes, when `boxes` names only a
  subset; (b) a box NOT in `boxes` is absent from the bounded result even though the
  unbounded call would include it; (c) a box in `boxes` that has been deleted (D10 ruling 3)
  degrades to that ONE box being absent, never to every other requested box degrading too —
  a genuine deviation from the store-wide branch's all-or-nothing degrade (§B below), and it
  needs its own assertion.
- **`check_listing_release`** (`:3422`) exercises `_release_plan` through `do_box_listings`/
  `do_release_box_listings`. Every existing assertion (the SHARED/OWNED/SOLDCOPY layout,
  `:3448-3456`, and whatever `checks.equal` calls follow through the rest of that function —
  read the whole function, not just its header, before changing `_release_plan`) must pass
  unmodified against the rewritten two-pass implementation.
- **New**: a `_release_plan` case with a SKU spread across three-plus boxes, asserting
  `elsewhere` reports every one of them (the rewritten per-SKU `select(sku=...)` pass must
  not stop early or miss a box just because it wasn't the box a shallower fix would have
  checked).
- **`check_box_names`** (`:7547`) exercises `_box_names()` via
  `server/pipeline_routes.py:11161`'s call (line number from the earlier grep — re-confirm
  at implementation time since this file's line numbers shift). Every existing assertion
  must pass unmodified against the box-registry-scoped rewrite.
- The `_on_hand_by_run` case around `:11964` (function name from the grep at the top of this
  file's research — re-confirm at implementation time) must pass unmodified against the
  signature change (`runs` parameter); update the call at `:11964` to pass the run-name list
  the surrounding test builds, matching the new signature.

### `app/tests/value-bands.spec.ts`

**Every one of the eighteen tests in this file stubs a single monolithic `GET /pipeline/value`
response** via the `open()` helper's `page.route(/\/pipeline\/value$/, ...)` (`:97-101`). The
`$` anchor in that regex matches the END of the URL string, so it will **stop matching** the
instant the client starts appending a query string (`?band=top&limit=200`) — every test in
this file breaks on that regex alone, before any assertion even runs. This is the single
biggest concrete change this item makes to the test suite; do not treat it as a detail.

Fix, applied once in `open()` (`:96-119`) rather than per-test:

```typescript
async function open(page: Page, answer: ValueTable, end: 'top' | 'bottom' = 'top'): Promise<string[]> {
  const asked: string[] = []
  await page.route(/\/pipeline\/value(\?|$)/, async (route) => {
    asked.push(route.request().url())
    const url = new URL(route.request().url())
    const band = url.searchParams.get('band')
    // BUILD THE PAGE/AGGREGATES SHAPE OUT OF THE SAME `answer: ValueTable` FIXTURE EVERY
    // EXISTING TEST ALREADY PASSES, so no test has to be rewritten to construct two
    // different fixture shapes — one helper here does the reshaping once.
    const body = band === null ? answer : valuePageFrom(answer, band, url.searchParams)
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  // ... the GET /pipeline/pricing and GET /pricing routes below are unchanged ...
}
```

Write `valuePageFrom(table: ValueTable, band: string, params: URLSearchParams): ValuePage`
as a small test-only helper (in this spec file, not shipped code): filter `table.copies` to
the requested `band` (`market !== null` for top/bottom, `market === null` for gaps), apply
the same sort/reverse the real server does, slice by `limit`/`after` using the SAME cursor
scheme as `_value_cursor_encode`/`_value_cursor_decode` in §A2 (a literal, obvious TypeScript
port — do not try to share code between the Python and the fixture), and return
`{ ...aggregates from table, rows: page, next, total }`. No existing `table({...})` fixture
builder (`:65-77`) needs to change — the reshaping happens entirely inside the route stub.

**Tests needing more than the shared fix**, read individually:

- `'the unrankable list pages, and says how much of it is on screen'` (`:376-395`) builds one
  261-row `copies` array and asserts client-side slicing shows 200 then 260. Once gaps paging
  is server-side (§A3 point 3), the *assertion* is unchanged but now exercises two real
  fetches through the stub — verify `valuePageFrom`'s `after`-cursor continuation against this
  fixture; it is the one existing test that most directly proves the new plumbing.
- `'one SKU in three slots draws three rows, and each says which copy it is'` (`:135`)
  asserts "copy N of M" text, which after §A3 point 4 comes from server-side
  `stack_index`/`stack_of` rather than the client's `stacks()`. Update this test's
  `copy({...})` rows to carry those fields explicitly.
- Any test asserting `"They sit in N separate spots across M drawers"` (`pulls()`'s output,
  `app/src/ValueBands.tsx:541`) needs its fixture to carry the new server-side `reach` field
  (§A3 point 5).
- Read the remaining tests (`:193-374`) individually — several assert chip counts
  (`counts.p1` etc.) that after this rewrite come from the aggregates block rather than from
  `slice(pool, ...).length`; confirm each fixture supplies the right aggregate figures
  (`valued`, `under_cutoff`, `at_or_over`).

### Mutation arms

Per `docs/specs/store-scaling/01-guard.md`/`06-orders.md`'s convention — this repo
mutation-tests every load-bearing fix:

- Remove the `band not in (...)` guard in `do_pipeline_value_page` — an arm proving the T7
  400-on-unknown-band case actually catches an unrecognized value falling through silently.
- Swap `_value_sort_key_reversed` for a literal reverse of the top-sorted list — an arm
  proving the T7 tie-break assertion distinguishes the two.
- Replace the cursor's compare-by-value lookup with a raw list-index cursor — an arm proving
  the stale-cursor T7 case actually catches the regression. This is the single most important
  arm in this item: it is the exact class of bug the whole cursor design exists to prevent.

## Allowlist entries removed

From `docs/specs/store-scaling.md` §4:

| Site | Confirmed removed? |
|---|---|
| `server/pipeline_routes.py:3202` `do_pipeline_value` (`.values()`) | **Yes** — §A1 replaces it with `inventory.cards.select(...)`. |
| `cli/resolve.py:372` `box_views` (`.values()`) | **Yes** — §B (below) replaces the store-wide fallback with `select()` and gives the two bounded callers a `records_in`-per-box path that never builds more than one box's `Card` objects at a time. |
| `server/capture_server.py:4549` `_release_plan` (`.items()`) | **Yes** — §C replaces it with two rounds of indexed `select(box=...)`/`select(sku=...)`. |
| `server/pipeline_routes.py:838` `_box_names` (`select(("box","run"))`, filter-less) | **Yes** — §C scopes the walk to the box registry's own keys (`inventory.boxes.items()`, a small table) plus one indexed `select(("run",), box=b)` per registry box, never a filter-less pass over `cards`. |
| `server/pipeline_routes.py:2444` `_on_hand_by_run` (`select(("run","state"))`, filter-less) | **Yes** — §C scopes the walk to the joined-run-name list the caller already has, one indexed `select(("state",), run=name)` per run. |

All five leave the allowlist in this item's PR. If research at implementation time (§"Read
first", and the open questions in "Call sites" about `cli/resolve.py:785`/`:1923`) finds
either of these two callers is ALSO store-wide in a way that makes the bounded fix
inapplicable, say so explicitly in the PR and leave that ONE site on the allowlist with a
named reason — do not silently keep an entry the spec says should go, and do not remove an
entry that turns out to still need to stay, without a sentence explaining which.

## Steps (§B and §C detail, referenced above)

### B. `box_views` — `cli/resolve.py:372-425`

```python
def box_views(
    inventory: master.Inventory, boxes: Optional[Iterable[int]] = None
) -> Dict[int, join.BoxView]:
    """... existing docstring, plus a paragraph on `boxes`:

    `boxes=None` (the default, and every existing caller's behavior) WALKS EVERY CARD IN THE
    STORE, exactly as before — needed by `do_pipeline_value`, which ranks across every box
    there is. `boxes={...}` BOUNDS THE WALK to exactly those box numbers, through
    `Inventory.records_in` (indexed on `box`) — needed by a caller whose positions already
    name a bounded set of boxes (a run's own `pricing.json` positions, a cross-run
    worklist's merged positions), where walking the whole store to answer a question about
    five boxes is the exact defect item 7 exists to remove.

    THE TWO BRANCHES DEGRADE DIFFERENTLY, AND BOTH ARE DELIBERATE. The unbounded branch
    degrades the WHOLE result to `{}` the instant any record's position will not coerce —
    unchanged from today, because a caller asking about the whole store has no way to know
    in advance which boxes are "the good ones", so a partial answer would be indistinguishable
    from a complete one that happened to have fewer boxes. The bounded branch degrades ONE
    box at a time — a `boxes={3, 7, 12}` caller whose box 7 has a corrupt record still gets
    correct views for 3 and 12, because the caller already knows exactly which boxes it is
    asking about and a corrupt box 7 does not render its knowledge of box 3 any less true.
    """
    if boxes is not None:
        grouped: Dict[int, List[Tuple[int, bool]]] = {}
        for number in boxes:
            try:
                n = int(number)
            except (TypeError, ValueError):
                continue
            try:
                records = inventory.records_in(n)
            except master.BadPosition:
                continue  # this one box degrades; the others in `boxes` do not
            rows: List[Tuple[int, bool]] = []
            for index, _key, card in records:
                game = str(getattr(card, "game", None) or games.DEFAULT_GAME)
                try:
                    if not games.get(game)["located"]:
                        continue
                except games.UnknownGame:
                    pass
                rows.append((index, card.state not in master.TERMINAL_STATES))
            grouped[n] = rows
    else:
        grouped = {}
        for _key, (box_raw, idx_raw, game_raw, state) in inventory.cards.select(
            ("box", "idx", "game", "state")
        ):
            try:
                at = (int(box_raw), int(idx_raw))
            except (TypeError, ValueError):
                return {}  # the store-wide degrade, unchanged from today
            game = str(game_raw or games.DEFAULT_GAME)
            try:
                if not games.get(game)["located"]:
                    continue
            except games.UnknownGame:
                pass
            grouped.setdefault(at[0], []).append(
                (at[1], state not in master.TERMINAL_STATES)
            )

    views: Dict[int, join.BoxView] = {}
    for number, rows in grouped.items():
        try:
            sections = inventory.sections_for(number)
        except master.BadSections:
            sections = ()
        views[number] = join.BoxView(
            sections=sections,
            occupied=tuple(i for i, on_hand in sorted(rows) if on_hand),
            departed=tuple(i for i, on_hand in sorted(rows) if not on_hand),
        )
    return views
```

The `# broken: set` local in today's function (`:394`, checked at `:415` but never populated
anywhere in the body — read the current source again before assuming this; it may be dead
code already, in which case drop it rather than preserving it into the rewrite) — verify
with `grep -n "broken" cli/resolve.py` whether it is genuinely unused before deleting it, and
if it turns out to do something this playbook's re-reading missed, keep it and adjust the
sketch above.

Add `from typing import Iterable` (or extend the existing `typing` import line) at the top of
`cli/resolve.py` if `Iterable` is not already imported — check `sed -n '30,34p'
cli/resolve.py` first.

### C. `_release_plan`, `_box_names`, `_on_hand_by_run`

**`_release_plan`** — `server/capture_server.py:4526-4590`. Replace the single
`for card_key, card in inventory.cards.items():` walk with two rounds:

```python
def _release_plan(inventory: master.Inventory, box: int) -> Tuple[List[dict], dict]:
    box = int(box)
    copies_here: Dict[str, int] = {}
    for _key, (sku_raw, state) in inventory.cards.select(("sku", "state"), box=box):
        if not sku_raw or state in master.TERMINAL_STATES:
            continue
        sku = str(sku_raw)
        copies_here[sku] = copies_here.get(sku, 0) + 1

    elsewhere: Dict[str, Dict[int, int]] = {}
    for sku in copies_here:
        for _key, (at_box_raw, state) in inventory.cards.select(("box", "state"), sku=sku):
            if state in master.TERMINAL_STATES:
                continue
            at_box = _position_int(at_box_raw, f"box of a copy of {sku}")
            if at_box == box:
                continue  # this box's copies are already in `copies_here`
            elsewhere.setdefault(sku, {})
            elsewhere[sku][at_box] = elsewhere[sku].get(at_box, 0) + 1

    # ... the rest of the function — the `rows` loop building `entry`/`before`/`gave`/
    # `after`/`still_held`/`also_in_boxes` — is UNCHANGED from `:4560` onward, since it
    # already only reads `copies_here` and `elsewhere`, both preserved exactly in shape.
```

This is bounded by `O(cards in box) + O(distinct SKUs in box × copies of each SKU
store-wide)` instead of `O(all cards in the store)`. `sku` is an indexed column
(`store/master.py:2487`), so `select(("box", "state"), sku=sku)` is a real indexed query, not
a scoped-looking full scan.

**`_box_names`** — `server/pipeline_routes.py:797-843`. Replace the filter-less
`inventory.cards.select(("box", "run"))` with a per-registry-box indexed query:

```python
def _box_names() -> Dict[int, "BoxFacts"]:
    try:
        inventory = Store().read().inventory
        present: Dict[int, set] = {}
        for key, entry in inventory.boxes.items():  # the SMALL registry table, already read below
            try:
                box = int(key)
            except (TypeError, ValueError):
                continue
            runs_here = {
                run for _k, (run,) in inventory.cards.select(("run",), box=box)
                if isinstance(run, str) and run.strip()
            }
            if runs_here:
                present[box] = runs_here
    except Exception:  # noqa: BLE001 — unchanged: a name is never worth an unanswered poll
        return {}
    names: Dict[int, BoxFacts] = {}
    for key, entry in inventory.boxes.items():
        # ... unchanged from `:822` onward, reading `present.get(box, ())` exactly as today.
```

This walks `inventory.boxes` (a handful of rows — the box registry, not the card table)
once, and issues one indexed `select(("run",), box=b)` per registry box — bounded by
`O(boxes) × O(cards per box)`, never `O(all cards)`.

**`_on_hand_by_run`** — `server/pipeline_routes.py:2429-2455`. Change the signature to take
the run names to count, rather than discovering them from a full-table scan:

```python
def _on_hand_by_run(inventory: master.Inventory, runs: Iterable[str]) -> Dict[str, int]:
    """... existing docstring, amended: `runs` is the caller's own list of run names to
    count — every caller already knows this list before calling (it is the joined-run
    directory listing `do_pipeline_worklist` builds anyway), so asking the whole `cards`
    table which runs exist and then counting each is strictly more work than counting the
    runs the caller was already going to look at.
    """
    counts: Dict[str, int] = {}
    for name in runs:
        n = 0
        for _key, (state,) in inventory.cards.select(("state",), run=name):
            if state in (master.SOLD, master.RETIRED, master.MOVED):
                continue
            n += 1
        counts[name] = n
    return counts
```

Caller at `server/pipeline_routes.py:2579` must collect the joined run-name list before this
line — hoist a first, cheap pass over `sorted(root.iterdir())` (reading only `manifest.get
("joined")`, which the existing loop at `:2584` already does per-run) into a list
comprehension executed before `on_hand = ...`, then have the main loop reuse that same list
rather than re-deriving it. Read `_manifest(entry)`'s cost (`server/pipeline_routes.py`,
grep `^def _manifest`) before deciding whether calling it twice per run (once to collect
names, once in the main loop) is acceptable or whether the collected names should carry
their parsed manifests along to avoid a second file read.

**Note on the comment this replaces** (`server/pipeline_routes.py:2578`, "ONE PASS, BEFORE
THE RUN LOOP, because the loop asks this question once per run and the answer is one read of
two columns for the whole store") — this is a settled argument that has rotted exactly the
way `CLAUDE.md`'s "a settled decision is an argument, not an authority" section describes:
correct when the store was 2,535 cards and the run count was small, wrong once the store
crosses tens of thousands of cards while the run count stays small — the crossover is
whatever `docs/specs/store-scaling.md` §1's own 20x measurement shows for this specific
function (measure it, per "Measure" below, rather than asserting the crossover point without
a number). Replace the comment rather than leaving it beside code it no longer describes.

## Do not touch

- **`pipeline/join.py:BoxView`, `Position`, `place_text`.** This item supplies a cheaper set
  of inputs to the SAME `BoxView`/`Position` construction every caller already used — it does
  not touch the label formula itself, D58's rule, or `join.is_located`.
- **`_readings()`** (`server/pipeline_routes.py:2975`) and its return shape. Item 5
  (`docs/specs/store-scaling/05-readings-writer.md`) owns changes to how it gets its data;
  this item only calls it, twice now (once in `do_pipeline_value`, once in
  `do_pipeline_value_page`) with the identical call signature it uses today.
- **`corpus.Corpus`, `pipeline/corpus.py`, `pipeline/pricing.py:FLOOR`.** Unchanged — this
  item reads the corpus exactly as `do_pipeline_value` does today, in both the no-args and
  paginated paths.
- **`Rows.select`, `Rows.where`, `store/db.py:SqliteSource`.** No new primitive is added to
  either — every fix in this item uses the `equals` filter mechanism that already exists.
  Do not add a `group_by` parameter to `Rows.select` or a `GROUP BY` query to `SqliteSource`
  — §"Goal and done-when" (C) explains why the existing two-pass indexed approach is
  preferred, and adding an unused new primitive alongside it would be exactly the kind of
  surface area `CLAUDE.md`'s "Scope is argued, not gated" rule asks a session to justify and
  this playbook does not find a justification for.
- **`do_box_listings`/`do_release_box_listings`'s HTTP-facing behavior** — refusals, status
  codes, the `{**summary, "listings": rows}` response shape. Only `_release_plan`'s internal
  walk changes; its return value (`Tuple[List[dict], dict]`, same two shapes) does not.
- **`app/src/PositionLabel.tsx`, `app/src/pricingSource.ts:bandInHash`.** Neither is touched;
  the hash-routing and label-rendering machinery around `ValueBands` stays as-is.
- **`pricing.spec.ts`** — the file header comment in `value-bands.spec.ts` (`:8-11`) is
  explicit that this suite is deliberately separate from the worklist suite so that a case
  added to prove the two lenses don't interfere lives in exactly one file. Do not add a
  value-bands case to `pricing.spec.ts` or vice versa.

## Measure

Follow `docs/specs/store-scaling.md` §1's own recipe — a `.backup` copy of the real store,
and the same copy with `cards`/`events` rows duplicated 20x — matching
`docs/specs/store-scaling/06-orders.md`'s "Measure" section's own instruction to reuse
whatever 20x copy the item-1-through-5 measurement sessions already built rather than
re-deriving the duplication independently (grep for one before building a new one; a second,
subtly different 20x copy makes this item's numbers incomparable to the other six).

```bash
# From this worktree, never the owner's live checkout (D43, D158) — always a copy.
cp /path/to/real/inventory/store.sqlite /tmp/store-scaling-07/store.sqlite
PKMNSCAN_HOME=/tmp/store-scaling-07 python3 -c "
import time
from server import pipeline_routes
for label, fn in (
    ('do_pipeline_value (full)', lambda: pipeline_routes.do_pipeline_value()),
    ('do_pipeline_value_page (band=top, limit=200)',
     lambda: pipeline_routes.do_pipeline_value_page(band='top', box=None, after=None, limit=200)),
):
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    times.sort()
    print(label, 'median', times[2])
"
```

Run against the plain `.backup` copy and against the 20x copy, five runs each, median,
matching `docs/specs/store-scaling.md` §1's own table shape. Expected shape of the result
(state the actual numbers in the PR rather than assuming these hold):

- **The AGGREGATES cost** (time `_value_rows` alone, or `do_pipeline_value_page`'s total
  minus the slice/serialize of `page`) should still scale roughly linearly with row count —
  this item removes the O(cards) **Card-construction** cost, not the O(cards) aggregate pass
  itself. Expect something closer to a per-row column-read cost than the 19–21x multiplier
  §1 measured for `.values()`-based walks, but expect real growth with store size — report
  the actual ratio, do not round it to "flat."
- **The PAGE FETCH cost** (`limit=200`) is **not** flat under this design, because the
  aggregate pass still runs in full on every page request. State this plainly in the PR
  rather than claiming flatness the design does not deliver; if the cost is unacceptable at
  50,000 cards, the follow-up is caching the aggregates briefly — new surface area with no
  existing precedent in this codebase (grep for one), out of scope here and named as a debt
  in `docs/DEBTS.md` rather than built on a guess.
- **`_release_plan`, `_box_names`, `_on_hand_by_run`** — measure each with a small script
  calling the function directly (`server/capture_server.py:_release_plan` needs a `box`
  number that exists in the copied store; `_box_names`/`_on_hand_by_run` take no arguments
  beyond the run-name list, which for `_on_hand_by_run` should be built from
  `sorted((runs_dir).iterdir())` filtered the same way the real caller does). Expect these
  three to show the clearest wins in this item, since they move from genuinely O(all cards)
  to O(bounded set) rather than merely O(cards) with lighter per-row cost.

Report all measurements in the PR body as a dated addendum to `docs/specs/
store-scaling.md` §1's table, per that file's own rule that measured numbers are evidence
and are never rewritten to match a later tree — do not edit §1's existing table in place.

## Risks

- **The aggregate pass is still O(cards), and this item does not claim otherwise.** The
  biggest risk to this playbook is a PR description that oversells "paginated" as "fast" —
  every page fetch still walks the whole store once to build `boxes`/`unrankable`/`totals`.
  What is fixed is the per-row cost (no `Card` construction) and the response SIZE (a page
  instead of the whole store). If the aggregate pass alone is still too slow at 50,000 cards,
  that is a real finding for the PR to report, not a reason to silently drop the D159
  "nothing dropped" requirement by computing aggregates over a sample or over the current
  page only — the "Read first" and T7 D159 arm above exist specifically to catch that
  temptation.
- **`stack_index`/`stack_of` and `reach` are new fields this playbook adds beyond what
  `docs/specs/store-scaling.md`'s own item-7 paragraph names.** They exist because §A3
  found that `ValueBands.tsx`'s existing client-side `stacks()`/`pulls()` genuinely cannot
  survive pagination without either a new server field or a real behavior change (a "copy N
  of M" or "N spots across M drawers" claim that quietly becomes wrong once the client no
  longer holds the whole band). Flag both explicitly in the PR as scope this playbook added
  on top of the spec file's literal text, with the reasoning above, so a reviewer can
  disagree with the tradeoff rather than discovering it silently.
- **The bottom-band tie-break change** (`_value_sort_key_reversed`, a real ascending
  comparator, vs. today's `[...priced].reverse()` of the top-sorted array) is a genuine,
  small behavior change. It is very unlikely to be user-visible (it only affects the ORDER
  of rows that share an exact market price within the bottom band), but it is a real
  difference from today's code and must be called out rather than discovered by a flaky
  Playwright assertion on row order.
- **`app/src/ValueBands.tsx`'s rewrite is the largest single piece of this item** and the
  one most likely to be underestimated — it changes a component that currently does all its
  work over one in-memory array into one that manages multiple in-flight fetches, cursors,
  and "Show more" states across three bands and a box scope. Budget real time for it; do not
  treat it as "swap one fetch call for another."
- **Ordering against items 4 and 5** (see "Depends on / conflicts with") — this item's own
  research did not re-verify `_copies_out`'s or `_readings()`'s exact current signatures at
  the moment of writing; the implementing session must re-run the two `grep` commands named
  there before trusting this playbook's line numbers, since a concurrent branch may have
  already moved them.
- **`_position_int`'s exact refusal behavior** (`server/capture_server.py:3586`) is reused
  verbatim in the `_release_plan` rewrite's `elsewhere` loop; this playbook did not read
  `_position_int`'s full body, only confirmed it exists at that line. Read it before relying
  on its exception type/message shape in a new call site.
