### T7 — Inventory store, capture server, and the command seams

The first test to reach `store/`, `server/` and `cli/`. Isolation is `BANCHI_HOME` pointed
at a temporary directory, so nothing here touches the real inventory.

<!-- ste-disable-next-line STE001: the test's own criterion string, published word for word -->
- **Pass**: positions never collide and a replay burns none; the sidecar round-trips through the reader identify uses; every refusal answers in its own code; command seams read the columns they name, and commands refuse rather than prompt
- **Two cases are regressions, not new coverage.** Both were live bugs that passed every
  gate in the repo on the day they shipped. One was the `PUT` that never reached the sidecar.
  It passed its own route test while doing it. The other was the `c.box == box` filter that
  dropped a string-typed record and returned an index that collided later. Both are recorded in
  `docs/debts/`, and both were re-introduced deliberately to confirm this test catches
  them before it was committed.
- **The markdown blocks are two, and the second is about a seam the first cannot reach.**
  See D103 (staleness filters, never gates). `check_markdown` owns the byte contract — every file carries `Add to Quantity` 0, the
  upload is built from the manifest's bytes, a spreadsheet's mangling round-trips identically, a
  raise refuses the whole file. `check_markdown_lens` owns the WIDENING. It asserts that
  `survey.json` holds every live row while the worklist stays narrow. It asserts that a row the
  offer never held is priceable because its bytes are on disk. It asserts that `dropped` still
  counts the offer and not the record. It asserts that a `sold_out` row is refused by name
  however good its price. It asserts that a stale corpus digest refuses before a byte is built.
  The two are kept apart because the first must
  keep running over byte-identical inputs — that is what makes the money path provably
  untouched by the second.
- **The markdown blocks are three since 2026-09-09**, and the third is a regression rather
  than a seam. `check_markdown_floor` runs the whole `reprice list` -> hand-back -> `apply`
  loop over a store whose cut-off is `$0.29`. It then TIGHTENS the cut-off to `$0.50` to prove
  the refusal still bites. A fix that only widened would have deleted the guard rather than
  corrected it. It exists because `plan` and `read_back` both defaulted to
  `pipeline/pricing.py:FLOOR` and no caller ever passed anything else: 293 of 354 hand-priced
  rows on the owner's real store were refused `below_floor` against a figure the store had not
  used for a week. The refusal came after every one of those answers had already been written into
  `prices.json`. Five mutation arms, each caught by its own named assertion.
- **`check_supervisor_recovery` is the first case here that reaches `scripts/`**, which is a
  fourth tree for a test whose own docstring names three. It is there because the supervisor
  is the one process in this project that runs unattended for days — `make launch-agent`
  starts it at login — so its failure mode is nobody watching. Both halves it asserts were
  found on the owner's rig rather than reasoned about. First, `FAST_FAILURE_SECONDS` was declared
  and read by nothing, so a limit meant for a crash loop was being spent by exits nineteen
  minutes apart. Second, the crash-recovery respawn logged nothing about whether it worked. It
  asserts the RULE rather than the scenario, because the scenario takes nineteen minutes.
- **What it checks that T1–T6 cannot.** They check rules and this checks wiring. A wrong
  rule gives a wrong answer you can see. A wrong position gives a card that is exactly where
  the inventory says it is not. A person finds it weeks later by opening the wrong slot.
- **Two blocks measure a defect against the path it replaces rather than against a fixture
  (2026-09-02).** `check_merged_emit_cap` asserts the CSV and the `pushed` count a merged emit
  writes, not the plan behind them. The first build of that command computed the right figure
  and wrote the wrong one. Only a head-to-head against three separate emits caught it.
  `check_live_reconcile` asserts that the store-wide reconcile writes `live` and leaves
  `pushed` alone, and that a **second pass corrects nothing**: idempotence is the property that
  separates it from the first build, which rewrote the cumulative record it had just read.
- **A per-card send quantity is covered as of 2026-09-11, with D7 (duplicates aggregate by SKU) amended, and it is asserted on the
  file and the store.** `check_emit_send_quantity` runs `emit --quantity SKU=N` over a run
  holding five copies and reads the CSV's `Add to Quantity` and the listing's `pushed` back. The
  row carries the figure typed. Every copy still carries the SKU. A second press asking past the
  shelf gets the remainder and names it (*asked 9, only 3 can go*). `0` sends none of the card
  without a hold. The ceiling and the quantity compose to the tighter. A merged send spends the
  figure once over the union. Every unusable pair is a sentence before the store is read, on the
  flag and on the route's parser. Mutation-tested: twelve assertions red with the bound
  removed from `add_to_quantity`.
- **The stranded-run repair is covered as of 2026-09-12, and the case is `check_reused_box_refusal`
  read the other way round.** That block asserts the refusal of D36 (the store decides a card's slot).
  `check_rescue_stranded_run` asserts the way OUT of it. This covers a run whose cards were moved
  into another drawer before its own was deleted and its number reused. It rebuilds the owner's
  own case in miniature: two records
  describing box 1, whose photographs are at new indices in box 3, with box 1's number reused for
  somebody else's cards. It asserts that the preview presses nothing. It asserts the re-keying.
  It asserts that the SOURCE run is untouched and that the derived run passes `refuse_reallocated`
  on its `scope.bid`. It asserts that a second press writes nothing. It asserts each of the five
  refusals. **Its strongest assertion swaps box 3's `bid` and moves nothing else.** The number is
  the same, the cards are at the same keys, and the registry stamp is the same. So the refusal
  fires on the ID alone. The timestamp-and-card-set rule structurally cannot reach that case.
  `check_run_binds_to_bid` covers the other end. It asserts that a run started in a TERMINAL now
  records that id at all, off the sidecars rather than the capture directory's name. It also
  asserts that two boxes get no scope rather than a guessed one. Nineteen mutation arms across
  both, every one caught.
- **Concurrency is small-N on purpose.** Two and four simultaneous captures over real
  sockets, matching D5's two devices. The twenty-way case that found the listen backlog
  proved something about a socket option and is not worth paying for at every turn end.
- **The identity stamp is covered as of 2026-08-30, and the case exists because the obvious
  fix was destructive.** `cli/cmd_emit.py` wrote the SKU inside a loop over `live_positions`,
  bounded by D7's live cap of 4, so the fifth copy of anything kept `sku: null` — invisible to
  `GET /search`, `copies_on_hand` and `positions_for_sku`. Measured on the owner's store:
  Rengar, Trophy Hunter (9189797, $30.81) holds seven copies and four carried the SKU.
  `check_emit_identity_stamp` asserts every matched copy carries it, that `pushed` still stops
  at the cap, and that the import file still asks for exactly the cap on one row.

  **Its fourth assertion is the one that matters most and is about the FIX rather than the
  defect.** Iterating `match.positions` would have stamped every copy and moved every sold one
  back to `identified`. That happens because `cli/resolve.py` commits a copy for being TERMINAL
  as well as for being counted, and `set_state` has no terminal guard. Eight of the box-3 run's
  33 matched positions are sold today. So the case sells a copy and re-emits, and requires it
  still sold. Three mutations were observed failing before it was kept. They were the original
  `live_positions` loop, the naive `match.positions` loop, and a shared increment. Each was red
  on a different assertion. That is what says the four are measuring four things rather than one.
- **Undo is covered as of 2026-08-13**, the day its route landed with step 7a. The cases assert
  that it answers with the position it removed. They assert that the record, sidecar and photo
  all go. They assert that a second call walks back one more card. They assert that it refuses
  anything but the newest and anything already written into an import file. All of this is D10
  (inventory positions, sections, stack). All of it was written the same day the route was,
  which is what this bullet promised when it said the cases were writable then.
  **Narrowed 2026-08-23 by D10's ruling 2**: undo now stops at `captured`, and the case
  that asserted "undo at `identified` is ALLOWED" asserts the refusal instead — and
  exercises the three remedies it names (re-shoot, retire, the mid-box remove). The two
  destructive operations the same rulings added are covered the same day they landed:
  the mid-box delete with its contiguous shift (`renumber_blocked` and the aim check,
  photos following their records byte-for-byte, the `renumbered` mapping and the
  per-position roll-call lines that keep the state reversals reading the right card) and
  the whole-box delete behind `box_not_empty_of_commitments`.
- **The pricing route's `written_at` is covered as of 2026-08-30, and the case had to be
  rewritten before it was worth anything.** `GET /pipeline/runs/<name>/pricing` now reports the
  mtime of `pricing.json`. This lets `#/inventory`'s card panel say `$0.34 · read 3 days ago`
  rather than a bare figure. `join` is free, re-runnable and routinely pointed at a refreshed
  export. Two cards on one shelf can therefore carry prices read a week apart.

  **The first assertion compared the field against the file's live mtime and was VACUOUS.**
  `seam_run` joins immediately before the request, so a route stamping `time.time()` answers the
  same integer — that version was written, mutated to a clock, and **observed passing**. It
  backdates the file by a week now, so what is checked is that the number describes THIS TABLE
  rather than THIS REQUEST. The failure it forbids is invisible from the screen. A price whose
  age resets to `read today` every time the panel is opened is a stale figure wearing a fresh
  stamp. That is worse than no stamp at all. Same lesson this file already records at the
  multi-game prompt seam — a check that cannot fail is not coverage.
- **The price-history reader is covered as of 2026-08-30, in its own isolated home, and
  OFFLINE.** `pipeline/pricehistory.py` walks a SKU to a productId against tcgcsv.com's
  mirror and reads the public `infinite-api` price-history endpoint. Every assertion runs
  against two committed fixtures and a fetcher the test supplies, so the harness opens no
  socket. That is not a style preference. This suite runs behind the Stop hook at the end
  of every turn. A case that reached a third party would put a stranger's uptime on the
  path that decides whether work is done. It would also hammer a free public mirror once per turn.

  **What is real here and what is constructed, because the two prove different things.** The
  fixtures are verbatim upstream captures and carry the SHAPE. Every number arrives as a
  string. A literal zero is written into a bucket that sold nothing. **The buckets arrive
  NEWEST FIRST.** The arithmetic is asserted against small literal buckets whose answer is
  computable in the assertion's own label. This is because a real series' VWAP is a number
  nobody can check by hand, and a fixture cannot tell a correct weighted mean from a
  plausible one.

  **The case that would otherwise fail silently is the bucket order.** It is why the real
  capture is committed rather than described. `momentum` subtracts one end of the list from
  the other. So a parser trusting the wire order reports every rising card as falling. There
  is no exception, no missing field, and nothing on screen to see. The fixture is asserted
  newest-first ON DISK and the parse ascending. So an upstream change goes red and says so,
  rather than the parser quietly starting to pass for a new reason.

  **The `/prices` half is covered by its ABSENCES.** The same mirror serves current prices per
  product per PRINTING. The cases assert what the payload does NOT carry: no
  `TCGplayer Id` and no `Total Quantity`. They assert these absences because that is what
  makes it a supplement to an export
  rather than a replacement for one. A real two-printing product in the fixture (Arena Kingpin,
  Foil $0.11 against Normal $0.08) is what makes the composite key load-bearing rather than
  tidy.

  **Thirteen mutations were observed failing before the block was kept**, each on a named
  assertion. The first four were the sort dropped, `"0"` read as a price, `find()` picking
  the first of an ambiguous pair, and the name rung deleted. The next three were the VWAP
  unweighted, the cache never reaching disk, and a corrupt cache entry raising instead of
  missing. The next four were an unresolvable row dropped without being named, `momentum`
  comparing a window against itself, an unknown range fetched anyway, and the printing dropped
  from the price key. The last two were a null direct low read as $0.00 and the group's
  prices re-fetched rather than cached.

  **What it does NOT cover, named so a green harness is not misread.** It does not cover
  whether the endpoint is still public, whether tcgcsv still mirrors these groups, or whether
  the figures are right.
  All three are facts about someone else's server on the day you ask, and no committed fixture
  holds them. The module is also a LIBRARY — nothing calls it and no screen draws it — so this
  is coverage of a reader, not of a feature.

- **The queue's starvation tier is covered as of 2026-08-24, in its own isolated home.**
  `store/queues.py:sort_key` gained a tier that promotes an entry past `STARVATION_DAYS`
  ahead of price, because price alone never releases an unpriced card: `no_catalog_row` has
  no market, so it sorted last permanently, and box 2 left 47 entries queued, counted and
  unreachable. The case asserts oldest-first inside the tier, expensive-first untouched
  inside the threshold, and the boundary one day short. It also asserts that a missing
  `first_seen` can never starve. **It was observed failing against the old key before it was
  kept.**

  **Two findings from writing it, both of which are this file's own lessons repeating.**
  `Queue.upsert` overwrites `first_seen` with today on insert and preserves only an existing
  stamp. So an entry cannot be aged by passing the field in. That is correct for the store
  and means the test writes the stamp afterwards. And the first draft put six entries into
  `check_queues`' shared store and took four of that block's own assertions red. This is the
  same shared-fixture failure the mass-select bullet below already records. It was found again
  the same way, and fixed the same way.

- **D34's listing release and its free preflight are covered as of 2026-08-24, in their own
  isolated home.** `GET /boxes/<box>/listings` answers what a release would give up;
  `POST /boxes/<box>/listings/release` gives it up, on the operator's word that TCGplayer is
  holding none of those copies. The block asserts every refusal (`confirm_required` including
  the stringified-flag case, `field_not_settable`, `box_not_found` on both routes, and
  `nothing_to_release` on a replay), that neither the preflight nor any refusal moves a count,
  and the two boundaries that keep the operation honest: **a sold card still holds its box open
  after every listing in it is clear**, and **a SKU shared with another box keeps that box's
  copies untouched**.

  **The budget is what most of the block is about.** Each SKU gives up at most the unsold copies
  the calling box holds. This is the owner's ruling in D34 (release against the box's copies).
  The fixture is built to exercise the hard case rather than the easy one. Box 4 holds 2 of a
  SKU's 5 staged copies, and box 6 holds the other 3. So the release gives up 2, and **box 6's
  three survive**. The first build, zeroing outright, could not promise that. A remainder
  therefore stays, the box is STILL refused
  afterwards, and both the plan and the receipt say so before and after. That remainder is
  intended, not a defect.

  **The gap it closes was found by a box that could not be deleted, and the mechanism is the
  finding.** `staged` is drawn down in exactly one place: `cli/cmd_join.py`, by the *rise* in
  live quantity a fresh Filtered Export reports. So an import that never lands leaves a count
  nothing can take back down. Box 1's 53 Gate B cards sat behind 45 records claiming 53 staged
  copies TCGplayer had long since cleared. `staged_stale` has named that case since D7
  (duplicates aggregate by SKU) was amended and nothing could act on it: a diagnostic with
  no remedy.

  **Its own home, and that is this file's own lesson a third time.** The block writes listings,
  which `check_boxes_and_listings` counts and `check_cli_seams` reads back through `emit` — the
  same shared-fixture failure the two bullets above already record, avoided rather than
  rediscovered.

- **The mass-select on `PUT /inventory/<box>` is covered, in its own isolated home.** The
  owner's `indices` selection narrows the box-wide claim sweep, and it is checked on the
  route rather than as a client loop for the reason the case states: N card calls are N
  chances to half-apply, which is the partial sweep that route's all-or-nothing exists to
  prevent. Both refusals were observed failing under mutation before the cases were kept.
  In one, an empty array was quietly read as the whole box. In the other, a selection naming a
  card the box does not hold was ignored instead of refusing the call.

  **The separate home is itself a finding worth keeping.** These cases first ran inside the
  block above, which counts history lines over a box it builds card by card. So the sweep
  moved numbers that block asserts. The section failed on its own fixture rather than on
  the code. A test that writes to a shared fixture is a test that will eventually be blamed
  for someone else's assertion.
- **The refill is covered as of 2026-08-30 (D59), end to end and in both directions.** The
  cap is a per-SKU quantity rather than a count of one run's positions, and the two halves
  of that live at a seam T3 cannot reach: `cli/resolve.py:_copies_out` reads a real store
  and a real export, and `emit` writes a real file. So the cases run the whole cycle —
  `join` -> `emit` -> import -> `reconcile` -> a fresh export -> `join` again — rather than
  asserting an expression.

  **The positive case is the refill sentence of D7 (duplicates aggregate by SKU) itself,
  restored.** Six copies, four pushed, the
  import lands, two of them sell, and a fresh Filtered Export reports two live. The SKU tops
  back up to the cap, and **the import file carries the DELTA, not the total**. It carries two
  rows, never four. That is the rule of D54 (re-emit adds, never subtracts), reached from the
  other end. `Add to Quantity = min(cap - live, backstock)` is what that computes, and it is
  the arithmetic `docs/specs/batch-script.md` §8's counter-argument was written to
  protect.

  **The negative case is the one that matters more, and it is the fix nobody should reach
  for.** Eight copies, four pushed, and an export reporting **two** live because the other
  two are still sitting in Staged. The answer is **add nothing**. The obvious repair for a
  stuck `pushed` is to clear the claim once the export reports anything live. It passes the
  positive case. It re-offers two copies TCGplayer is already holding, which is exactly the
  double-stage the first post-import re-emit produced on 2026-08-22. What bounds the claim
  instead is physical: `store/master.py:Inventory.copies_not_sold`, which cannot be argued
  above the copies this Mac actually owns and has not sold.

  **Observed failing first, and the mutation that counts is the PLAUSIBLE repair rather
  than an absent one.** A case that only goes red when the whole feature is deleted does
  nothing to stop somebody clearing `pushed` the moment an export reports a live copy. That
  is the one thing this negative case exists to refuse.
- **The export fetch of D65 (export request names its own scope) is covered as of 2026-08-30,
  aimed at a local socket and never at
  TCGplayer.** `POST /pipeline/runs/<name>/export` downloads the Filtered Export with the
  session cookie from `.env` instead of the operator downloading and uploading it.
  `check_export_fetch` has its own `isolated_home` AND its own environment. It is the first
  section here that reads `.env`. So one that leaked `TCGPLAYER_STORE_COOKIE` or
  `BANCHI_TCG_EXPORT_URL` would point every later fetch in the process somewhere
  unexpected.

  **What it proves**: that a session redirected to a login page never becomes a parsed CSV.
  It also proves that a login page served as a **200** refuses the same way. It proves that a
  WAF 403 has its own code. It proves that every refusal deletes what it wrote. It proves that
  the cookie reaches the socket and reaches **no file the run holds**. It proves that a fetched
  file is the one `join` then actually joins against, recorded in the manifest. That is the
  seam a route that fetched a file nobody used would pass without.

  **Three cases called `_coverage` directly, and the figures they carried are the evidence in
  D65 (export request names its own scope) that a content-inspection guard is hard to get
  right.** All three REFUSED, and what differed
  was whether the refusal claimed a FINISH was lost — invisible from outside the route. They
  pinned two defects that shipped in the guard's first build. They were found by measuring
  against the owner's real exports rather than the three-row fixture. One was counting play
  conditions as finishes (measured, all 153 of box 3's numbers read as thinned and not one
  had lost a finish). The other was a key carrying `Product Name` (measured, 550 multi-finish
  riftbound numbers keyed `(set, number)` against 522 with the name, so 28 real cases were
  invisible to the check written to find them). Both mutations were observed failing, each on
  one case.
  **The guard those measurements justified is retired** (D65). D65 names
  the scope, so the positive check `export_scope_incomplete` is the whole guard. Also, the
  delta's first-fetch refusal cost every run an acknowledgment and a second download. The
  three cases went with it. What the section proves instead is that a re-fetch of identical
  bytes lands on the file the run already holds. It also proves that the receipt carries the
  last joined export's rows and SKUs beside the new file's, per game, and that the comparison
  refuses nothing.

  **What it CANNOT prove, said here so a green run is not misread**: whether TCGplayer's WAF
  accepts this client when the request carries a real session. Measured unauthenticated, the
  stdlib default User-Agent reaches the endpoint unblocked — which is not evidence about an
  authenticated one. That is one live fetch by the owner and D65 records it as owed.
- **The order ledger is covered as of 2026-08-30, in its own isolated home.** See D63
  (sync writes only the feed's map).
  `store/orders.py` persists what `pipeline/orders.py` deliberately does not, and the
  cases work hardest on the two rules that make it safe to re-run. **Idempotence is
  asserted as BYTE EQUALITY of `orders.json`, `inventory.json` and `history.jsonl` across
  two syncs, never as a count.** This is the lesson of D54 (re-emit adds, never subtracts)
  said out loud. There, a guard reading
  `len(rows) == 0` was satisfied identically by the emitter correctly omitting a row and
  by it overwriting two good rows with a bare header. A row count here goes green on a
  ledger that threw its fulfillment away and re-ingested the same order over the top.

  **The renumber case drives the real route rather than simulating a shift.** Five cards,
  two copies pulled at 3/2 and 3/3, then `POST /inventory/3/1/remove`: both pulled copies
  slide down one and **position 3/3 ends up holding a card that was never pulled**. A
  ledger keyed by position ships that card; one keyed by `capture_id` does not. Asserted
  as both halves, because the first alone is satisfied by a ledger that stores nothing.

  **Six mutations were observed failing first, each through the assertion that owns it.**
  They were `fulfilment` moved inside the replaced record (7 red), `changed_at` restamped
  unconditionally (2), and the pull's dedup dropped (1). They were also `holder_of` not
  consulted (1), the nested `__annotations__` filter removed (1), and capture ids stored as
  position keys (7). **Three of them first failed by ABORTING the block rather than naming
  anything**, and two assertions were changed for it. This is because a mutation that raises
  out of the middle leaves
  the case that covers it unrun and everything after it unreported. It is loud, so it is
  not the silent pass this file fears most — but it is coverage of the traceback rather
  than of the defect.

  **What it does NOT cover, so a green harness is not misread**: nothing calls this module.
  No route serves it, no screen draws it, and no command reads it. So these cases assert a
  data structure and not a feature. `pipeline/pricehistory.py` carries the same standing,
  and so does the order resolver beside it.

- **7b's three routes are covered as of 2026-08-13**, the day they landed: `GET /queues`,
  `POST /review/<box>/<index>/answer` and `POST /inventory/<box>/<index>/sold` — the
  standing-queue read, D4's one-tap answer, and D10's mark-sold with its reversal. This
  bullet said those routes did not exist. **Of everything 7b shipped, the routes are the one
  part that did not get built ahead of its evidence**, and that is worth noticing when
  reading the rest of it.
- **Known blind spot, and it is 7b's — half of it closed on 2026-08-22.** Every queue entry
  these cases assert against is still hand-built by the test, so a green T7 still says only
  that the routes behave the way `docs/DESIGN.md` describes. What is no longer true is the
  sentence that used to follow: a real run HAS produced entries, 16 of them, and their shape
  matches what the test builds — `position`, `reason`, `read`, `candidates`, `market`,
  `first_seen`, `cleared_by_human`. All 16 were `metadata_detection_disagreement`, all
  parked, and the owner answered every one through the answer route.

  **A third reason code met a real card on 2026-08-29, and it is the one that produced D35 (unreadable numbers fall back to the name).**
  Box 1's riftbound run queued four zero-candidate `no_catalog_row` entries — cards the
  answer route refuses outright, so they could not be answered at all, only skipped. Three
  turned out to be a set code glued to a correct identifier (`UNL • 140/219`). They are now
  recovered by code with no human involved. The fourth had its champion name dropped by the
  model, and it is what the catalog lookup exists for. T7's `check_review_catalog` covers that
  route and D35's answer path, against the committed riftbound export rather than an invented
  fixture. It is the first block in this file whose catalog is a real 10,078-row file.

  So the remaining gap is narrower and worth stating exactly: the fixtures are still
  invented, and Gate B's run of one lot produced exactly one reason code. **Box 2 produced a
  second, and this bullet denied it until 2026-08-25.** `no_catalog_row` has stood in the live
  queue as 47 real entries with zero candidates. This is the case D35 (unreadable numbers
  fall back to name) was written for. It is also the case that `wasted_position` in D37 (stand-down
  closes a question, writes nothing) was measured against. Both decisions landed in this repo
  on the strength of it. The count was stale too: the roster is fourteen, not twelve. So **two of fourteen have
  met a real card**, and nothing has exercised `set_ambiguous`, `low_confidence` or the other
  eleven against a real queue. Same standing as T6's synthetic composites: self-consistency
  over a wider range than the evidence covers.

- **The order screen's three routes are covered as of 2026-08-30, in four isolated
  homes.** See D69 (orders and shipping are separate routes). `check_order_screen` covers
  `GET /orders`, `POST /orders/ingest` and
  `POST /orders/pull`. `check_order_resolver` already covers the resolver over an `Inventory`.
  `check_order_ledger` already covers the ledger over a file. **Neither of them can fail on the
  route**, which is where the two are joined. There the orders are composed into engine objects
  and resolved in ONE pass. A place is rendered per pick. The ledger write and the sale happen
  inside a single `Store.write()`.

  **The case it exists for is the double book, asserted on the ROUTE's payload.** Two orders
  for one SKU with one copy on hand are pasted newest-first. The older order carries the pick
  and the newer answers `short` with no picks and `on_hand` 1. The copy has not left. It is
  spoken for. A handler that looped `resolve_all` per order passes every assertion in
  `check_order_resolver`, because that section calls `resolve_all` itself, and still hands two
  buyers the same physical card.

  **Four more properties, each one a thing a plausible build gets wrong.** The reason
  vocabulary is asserted as `sorted(counts) == sorted(orders.LINE_REASONS)`. So a seventh
  reason added to `pipeline/orders.py` and not carried through the route fails here rather than
  as a blank row on a screen. Every pick's `place.label` is compared against
  `cli/resolve.py:box_views(...).at(...).label` — the reporter's walk, the other implementation
  of the counting space of D58 (a card's number counts cards). The PII backstop refuses a paste carrying `buyer` **by name**, at
  the order level and at the line level, and writes nothing. And a pull's receipt is asserted
  as a DIFFERENCE. `places[0].label` is `Box 3 · Section 1 · Card 1`, while a `_Places` built
  after the same call answers `Box 3 · departed`. This is because a sale moves the box's
  occupancy (D58), and a receipt composed afterwards would name where the box has closed up to.

  **And the screen is asserted to draw NO postage lane.** The order answer's key set and the
  line answer's key set are both pinned whole. So `OrderResolution.ships_in_an_envelope`
  cannot arrive on this wire quietly. D69 (orders and shipping are separate routes) makes that
  a prohibition rather than an omission: the lanes are the answer of D61 (shipping routes three
  lanes, one unsure), computed from an export this screen has never read.

  **Idempotence is byte equality and never a row count**, which is `check_order_ledger`'s own
  lesson one layer up: the second identical paste leaves `orders.json`, `inventory.json` AND
  `history.jsonl` byte-for-byte as they were. Twelve refusals are covered by code:
  `field_not_settable` in both directions, `line_kind_invalid`, `already_sold`,
  `capture_id_mismatch`, `copy_not_identifiable`, `sku_mismatch`, `sku_not_on_order`,
  `order_not_ingested`, `over_fulfilled`, `copy_already_pulled`, `pull_not_recorded` and
  `pull_spans_lines`. Each is asserted to have moved neither a count nor a card's state.
  A fourth copy against a line of three is refused rather than clamped: you cannot ship the
  fourth. **One equality ties the extraction**: `_sell`'s body is exactly the nine keys
  `do_mark_sold` answers, so the pull and the sale button hand the app one shape.
- **The shipping routes and the order transport are covered as of 2026-08-30, in one
  isolated home, and the transport half opens no socket at all.** See D69 (orders and
  shipping are separate routes).
  `check_shipping_routes` runs the same committed 331-order Export Shipping file through
  `POST /shipping/batches`. The result is 166 envelope / 126 parcel / 39 unjudged. It has all
  six reasons as one absolute dict including the two zeros. It has 112 rows carrying
  `certain`, and every one of them is `value_at_threshold`. It also has a 14,786-byte import
  file of 126 data lines.

  **Every assertion about `server/shipping_routes.py` is an ABSENCE, and each is pinned as an
  absolute.** The union of every row's key set is exactly eight keys, so a name or a postcode
  added later is argued for in the test rather than slipped in. The fixture's own first buyer
  name and street appear nowhere in the serialized answer. Not one of the 39 unjudged order
  ids reaches the import file. This is because being swept into the parcel lane to be safe is a
  postage charge the operator did not choose. Every `Package Weight` cell is empty **including
  on a `non_card_signal` order**, which is the row routed BY its weight and therefore the one
  where carrying it across looks most reasonable. No spelling of an insurance column
  appears in the bytes. **Nothing is persisted**: the store's whole file list is identical
  before and after reading the export, rendering the import and downloading it.

  **The way back is asserted to actually forget and the holding is asserted to be bounded.**
  Forget drops the batch, the file then refuses `no_such_batch`, and a second Forget refuses
  too — without that assertion the button is a lie. Reading `BATCH_LIMIT + 1` exports evicts
  the oldest, which is how much buyer PII this process can hold at once stated as a fact
  rather than as a comment.

  **The transport half is what is decidable without a live session, and a green run still says
  nothing about the live one.** `server/order_transport.py`'s `search` HAS since run
  authenticated (2026-08-30, three real orders, run by the operator because an agent may not
  read `.env`). `detail` and `fetch_open_orders` have not. What is asserted is that
  `project_order`'s four keys are an allowlist. `buyerName`, `shippingAddress` and
  `paymentType` are asserted to be dropped where they are parsed, on the line as well as at
  the top. `skuId` is asserted to survive coerced to a string. The search body is asserted to
  go out as a plain JSON document with `Content-Type: application/json` and **not** the
  form-encoded `model=` shape of D65 (export request names its own scope). A reader will
  first try to "fix" the body into that shape. A missing seller key, an expired session and a
  rejected key are asserted to be three codes and not one. This is because 403 on that host is
  usually the request rather than the session. A problem+json body is asserted to yield its
  `traceId` and drop `title` and `detail`. These are the fields most likely to quote a
  credential back into a log. It is asserted that no refusal message carries the session.
  The one request built is handed to a stubbed opener that raises instead of connecting, so
  the suite behind the Stop hook still reaches nobody's server.
- **`PASS_CRITERIA` did not change for either block**, and the direction is the one this file
  fixes: the test is the source and the gate publishes it. Both fit the criterion already
  published above — every refusal answers in its own code — so the `- **Pass**:` line is
  untouched rather than reworded to accommodate them.

---
