# The first photograph is the card's name (`cards.cid`)

**STATUS: SPECIFIED, NOT BUILT.** Nothing in this file is implemented. No store carries a
`cid` column, no migration exists, and neither the `cid-audit` nor the `cid-selftest` target
nor the `cards` subcommand this file describes is in the tree. What IS real is the evidence:
every figure below was read from the owner's live store or from a `.backup()` copy of it, and
every mechanism was proved on a copy — the migration, the reverse, the `-9` kill and the two
probes all ran. This is the argument and its receipts, landed so the next session finds them
instead of re-deriving them (`CLAUDE.md`'s working agreement: design work is repo work).

**THE MEASUREMENTS ARE EVIDENCE AND ARE NEVER REWRITTEN.** `docs/GATES.md`'s discipline
applies to this file: if you re-verify a number and it disagrees, write the new reading BESIDE
the old one with its date, the way `docs/specs/order-pipeline.md` §1 carries three snapshots.
§7 item 7 already names two figures here that will not reproduce.

**THE SURROUNDING PLAN IS NOT A REPO DOCUMENT, AND THAT IS THE GAP THIS FILE ONLY HALF
CLOSES.** §5 schedules this work against PRs lettered A to H, from a session plan that lives
in no file here; three of those letters have landed as pull requests #301, #302 and #304, and
the rest are a transcript. So §5 is readable as an ORDERING ARGUMENT — which schema step goes
first, and why two 2→3 steps in one function is the one merge conflict that loses data — and
is not readable as a roster anybody can look up. Do not treat a letter in it as an identifier.

**NAMES OF THINGS THAT DO NOT EXIST ARE WRITTEN BARE, ON PURPOSE.** A target spelled
`make <name>` or a subcommand spelled `pkmnscan <name>` in any markdown file is reconciled
against the Makefile and `cli/__main__.py` by `make docs-audit`'s make targets and pkmnscan
commands rows — both MECHANICAL, and both deliberately named here without backticks, because a
backticked span is exactly what they read. Spelling an unbuilt one fails the commit. The
two targets are therefore written `cid-audit` and `cid-selftest`, and the subcommand
`cards name` / `cards audit`, with no prefix, until the implementation adds them and the
prefixes can go back on. `scripts/cid-audit.py` is named as a path and carries a line in
`scripts/docs-audit-allow.txt` for the same reason; that line is stale the day the file
arrives, which is the allowlist's whole design.

_Executable specification. Written 2026-09-12 against **main `df6ec79`** (`Merge pull request #309`), worktree clean at the same sha. Every figure below was read from the owner's live store opened `mode=ro&immutable=1` or from a `.backup()` copy under the session scratchpad. **The live store ends this session at `md5 b3373ed823a7b397054e9980f2ddcaa9`, 7,438,336 B, mtime `Sep 12 11:28`, schema 2, no `cid` column** — unchanged from before the survey. Every writable probe ran on a copy. Re-read before trusting any number here: three of the store survey's figures did not reproduce against this tree and two of mine will not reproduce against the next one._

This is the ninth PR and the one the plan's own section 7 excluded by name: *"taking the box out of `store/master.py:243 position_key`."* **It does not take it out.** It gives the card a name that is not its box, which is the mechanism that makes taking it out possible; the removal itself is a later PR and §4 says which parts and why they wait. The plan's own arithmetic was *"about 90%"*; this is the seam, measured, migrated and proved, and it is honest about which of the remaining 10% it buys today.

---

## 1 · THE ID, IN ONE SENTENCE

**`cards.cid` is the sha256 of the photograph the store held when the id was issued — read off the disk, frozen from that moment, never recomputed — so it is a birth certificate rather than a live content address, and it is the only candidate identity in this store that can be re-checked against the 4.45 GB that cannot be re-taken.**

**The decisive measurement, re-taken today.** For all 2,535 cards, `sha256(captures/cards/box<B>/<idx:04d>.jpg)` equals the `photo_sha256` already stored for that card in `identifications`. **2,535 of 2,535. 0 disagreements. 0 files missing. 0 photographs claimed by no card. 2,535 distinct digests among 4,445,351,065 bytes. 0 duplicates.** The whole corpus hashes in **2.68 s**. `identifications` is 2,535 rows against 2,535 cards with **0 orphans in either direction**.

So the id is not invented, allocated or guessed. It is read.

### The rejected options, and the deciding reason for each

**`capture_id` — REJECTED because it is a photograph's identity, not a card's.** It is present and distinct on 2,535 of 2,535 cards, `fulfilment` already references copies by it, and `Ledger.holder_of` indexes on it — which is why it looks right. But `do_reshoot` overwrites it (`capture_server.py:7534`, `card.capture_id = capture_id`) under a docstring that says in as many words *"The card's identity, state, claims and `captured_at` all describe the card and the capture session, not the picture, so none of them moves"* — eleven lines before it moves one. `move_card` **clears** it on the tombstone, and its own docstring gives the reason: *"the photograph, not the vacated slot, is what the id anchors."* The column is not UNIQUE. **Measured: 3 of 82 `fulfilment` copy references already dangle**, all three traced to `buried` events at `1/34`, `1/58`, `1/85`, and `holder_of` simply answers `None`.

**A never-reused integer from a `meta` high-water mark — D145's `bid` one register down — REJECTED on a measured failure mode neither prior design found.** Two probes, both on copies:

1. **A build that does not declare `Card.cid` strips it on any ordinary write, silently.** I planted 2,535 ids and stamped a copy `schema = 3`, then ran one `set_state("3/17", …)` under today's build: `hasattr(card, "cid")` is `False` (`Inventory.parse` filters on `Card.__annotations__`), `SqliteSource.upsert` names only this build's `column_names`, and the row came back with **the column NULL and the payload key gone**. 2535 → 2534. No error. `CREATE UNIQUE INDEX` does not object — SQLite NULLs are never duplicates, verified with three stripped rows. **There are 27 worktrees on this machine right now**, every one a pre-guard build.
2. **Under a digest, the next migration re-run heals it. Under an integer, it orphans.** Measured: stripped `3/17`, re-ran the seeding, and the cid came back **byte-identical** (`6b1cf2fd83713889…`). The re-run issued exactly 3 new ids for the 3 stripped rows and 0 for the other 2,532. An allocator would have handed `3/17` a fresh number and left every reference to its old one pointing at nothing — and would have reported success both times.

That is the deciding reason. An integer cannot be checked against anything on disk, so a mis-binding is undetectable forever; and the one live hazard this design cannot prevent is the one a digest silently repairs.

**A replay-derived occupancy integer — REJECTED because the algorithm is under-specified in a way no gate can see.** Three independent implementations of the same described replay produced mis-bind rates of **22.3%, 31.3% and 32.8%** against the naive key join (mine: **3,911 of 11,919 position-carrying events, 32.8%**, including 35 `sold` and 133 `buried` lines, plus 440 bound to nothing). My replay produced 3,627 occupancies with the roll-call rule tested first and 4,452 with `captured` tested first. **Every row receives a non-NULL value under all three.** §4 keeps this out of the PR entirely.

**A server-minted UUID4 — REJECTED for the integer's reason plus one more:** it is not derivable, so there is no second source to reconcile it against, ever.

**The position key with the box removed (a store-wide `next_card_index`) — REJECTED because it invites being read as an address**, and this repo has already paid for a field holding a plausible, wrong rendering (291 of 565 queue rows carry one).

### Frozen, not tracked — and the four shapes

**`cid` is issued once and never recomputed.** That single word is what makes it survive a D26 re-shoot, a D89 reclaim, a D83 move, a mid-box renumber and a box deletion. It is not a copy of the current photograph's digest — that field already exists (`Card.photo_sha256`, D89) and keeps its narrow job. Values are one of four shapes, **all named, none NULL**, with today's measured population:

| shape | means | on this store |
|---|---|---|
| `<64 hex>` | named by the photograph the store held at issue | **2,535** |
| `<64 hex>-<n>` | the nth card whose bytes are identical to an earlier card's | **0** |
| `moved:<64 hex…>` | the tombstone a moved card left behind (`move_card`) | **0** (`state='moved'` rows: 0) |
| `nophoto:<box>/<index>@<captured_at>` | a card with no photograph and no digest anywhere | **0** |

`master.is_photo_cid(cid)` is the one predicate that tells shape 1/2 from 3/4, and the audit uses it. **A NULL is never one of the four**, because a NULL here cannot distinguish *"no photograph was found"* from *"this migration did not look"* — this repo's signature defect stated verbatim.

**Naming note, read it before you type:** `cid` sits two fields from `capture_id` and is not an abbreviation of it. Use the `bid` : box :: `cid` : card symmetry, and open the field comment by saying what it is not. `cid` currently appears **0 times** anywhere under `cli server store pipeline identify app/src harness scripts codes geometry` — the name is free. `card_id` is not: `harness/eval/fixtures.py` and `t1_id_eval.py` use it for a T1 fixture's own id.

---

## 2 · WHAT STAYS

**THE BOX IS A REAL ADDRESS AND ALMOST EVERYTHING IT DOES IS CORRECT. Nothing below moves.**

**`Box 3 · Section 2 · Card 17` — untouched.** It is an instruction to a hand at a drawer. `pipeline/join.py:Position` stays the only label formula, `join.departed_label` stays the answer for a card in no slot, and `Place.slot` / `Place.index` stay split. The Fulfiller reads that label at a 32px floor asserted in a real browser by `make design-check`, and `app/tests/fulfillment.spec.ts` floors it unweakened. **A `cid` never appears on his screen.**

**D58's argument HOLDS and is not the subject.** Measured today: **zero index gaps in all five boxes** — box 1 `1..322`, box 2 `1..543`, box 3 `1..887`, box 4 `1..678`, box 5 `1..105`, each max equal to its count. The rendering layer is drawing an identity mapping, which is exactly why it is not under strain.

**`store/master.py:243 position_key` stays, and `cards.key` stays `"<box>/<index>"`.** All four primary keys it is (cards, identifications, queues, and `events.position`) stay. The cid arrives **beside** the key on `cards` alone.

**`store/master.py:1390 next_index` stays, unchanged, and is still needed.** `1 + max(idx WHERE box = N)` over every state, D10's high-water mark. Its argument in D10 is *permanent gaps from departures*; note that D26's re-shoot is **not** a second ground — `do_reshoot`'s own docstring says *"allocator never involved"* — and with zero gaps in all five boxes today, high-water, count+1 and first-free return the same integer. That is a population of zero, not a vindication, and it is why `next_index` is left alone here rather than defended.

**The whole shutter-to-sidecar path stays.** `_require_box`, `allocate_capture`'s sealed-box check and its `capture_id` replay guard, `BoxClosed`, `PositionOccupied`, `next_index` inside the lock, `sidecar_payload(box, index, …)`, `open_section`'s `S`, `banchi.session.box`. One statement is added to it.

**Every photograph and every sidecar stays exactly where it is.** `captures/cards/box<N>/<idx:04d>.jpg` — 2,535 files, 4,445,351,065 bytes — and `captures/cards/box<N>/<idx:04d>.json`. **This PR performs zero filesystem renames, zero unlinks, and zero writes outside the database.** `photo_path` stays derived, `INDEX_PAD = 4` stays load-bearing (`sidecar.scan` sorts by path string), and `Card.photo` stays a stored path string: measured **0 of 2,535 stored paths disagree with the derived tail** (1,993 absolute, 542 relative, one naming an iCloud root deleted 2026-08-29), so the store survey's 536-drifted-paths argument for deleting it **does not reproduce on this tree and must not be acted on**.

**`do_remove_card`'s renumber stays, all 1,608 filesystem operations of it.** So does `do_move_card`'s tombstone-plus-five-hand-moved-copies. §4 says why, and §7 names the contradiction that has to be resolved before either is touched.

**The wire stays.** All ten anchored regexes at `capture_server.py:530-566` keep `(\d+)/(\d+)`, including `_PHOTO_RE`. `CLAUDE.md`'s rule holds: *"A session that finishes the rename by touching `server/` or `store/` has moved the store of record for a word."* One route is **added**, none is changed and none is removed.

**D88's transaction stays and is what makes this cheap.** One `BEGIN IMMEDIATE … COMMIT` over every table inside the flock. It is why the whole migration is 3.0 s and why a `kill -9` leaves nothing behind.

**D7's fungibility stays.** `listings` is keyed by SKU and carries no position (567 rows); `import.csv` has 16 columns and none is a position. **No migration here can reach outside this machine.**

**D145's `bid` stays and is the template, not a competitor.** `_add_box_ids` is copied line for line: additive, no-op on a re-run because it reads the existing value first, stamp last inside the transaction, receipt carrying a plain-English `reverse` sentence. `meta.box_ids_issued = 5`, all five boxes wear a bid.

**D89's `photo_sha256` / `photo_reclaimed_at` stay, narrowed.** The pair still travels together and a screen that finds them set still draws *"reclaimed"* rather than *"missing"*. **D89's one weakened clause, narrowed not repealed:** it says the digest is `None` while the file exists *"because while the file exists the file is the fact and a copy of its digest here would be a second thing to keep true through D26's re-shoot."* That argument holds **for a field that tracks the current photograph**, which is why `cid` must not do that job. Measured: **0 of 2,535 live cards carry either field** — all 34 `photo_reclaimed` records were buried with boxes 1 and 6 on 2026-09-11 — so that clause currently describes a population of zero, and the field's surviving job is the digest of the photograph that was reclaimed, which differs from `cid` only for a card re-shot first.

**D36's repair layer stays, live, for the runs that exist.** `realign`, `_photo_digests`, `refuse_reallocated`, `box_disowns_run`. A cid cannot reach backwards into an immutable file written before it existed: 13 run directories, 3,728 records, all 3,728 carrying `photo_sha256`, and **701 of them bind by digest to a different position key than the one they name** (537 of 544 on `2026-08-24-box2-01`, 99 crossing box 1 → box 3, 65 crossing box 6 → box 3), plus 88 whose photograph is gone. That layer is production evidence that a content id beats a positional one, and this PR neither deletes nor demotes it.

**`capture_id` stays, at the job it is good at** — the photograph's id and `allocate_capture`'s replay guard, the only thing between a lost response and two records for one physical card. What it stops being is an identity other tables should reference.

---

## 3 · THE MIGRATION, STEP BY STEP

**The whole operation touches no file outside the database. That is its strongest property and it is what lets it be priced at 3.0 s.** `do_remove_card`'s "files first, records after" and `_move_one`'s "records first, files after" both carry an explicitly accepted crash window; this is the first operation in this repo that has none.

### 3.1 · Two guards land first, in this order

**Commit 1 — the forward-version guard, alone, changing no behavior on any store that exists.** `store/db.py:_ensure_schema` has none, and I proved it: I stamped a copy `schema = 3`, opened it with today's build, **and the read SUCCEEDED (2,535 cards) while the stamp was silently rewritten DOWN to 2.** The mechanism is `_ensure_schema:192` (`stored != SCHEMA_VERSION` → `_upgrade`) then `_upgrade:246` (`if stored < 2` false, then `INSERT OR REPLACE … 'schema'`).

```python
if stored is not None and stored > SCHEMA_VERSION:
    raise StoreError(
        f"{db.path(directory)} is stamped schema {stored} and this build knows {SCHEMA_VERSION}. "
        "A newer build wrote it; an older one opening it rewrites the stamp DOWN and then "
        "strips every field it does not declare, one row per write, silently. "
        "Update the checkout — `git pull` in the main tree, then `make hooks`."
    )
```
Every store on this machine is stamped 2, so this refuses nothing today. **State in the PR body: do not merge commit 3 until commit 1 is on main and the main checkout's supervisor has re-execed onto it** (D53 re-execs on a change to one of its four files; `make status`'s own rows are how to confirm). The guard protects builds that HAVE it, which is the half it cannot cover and must say so.

**Commit 2 — the column-roster arm, which earns its place before any cid exists.** Four hand-written rosters must learn the name: `Card.__annotations__`, `_card_columns` (`master.py:1238`), `Inventory.CARDS.column_names` (`master.py:2351`) and `db.TABLES["cards"]` (`db.py:97`). `_INTEGER` is **not** one of them — `cid` is TEXT and TEXT is `_ddl`'s default. Nothing reconciles those four today; `grep` finds one prose comment and no check. Miss `_card_columns` alone and every write stores the cid in the payload and leaves the COLUMN NULL — `cards_cid` never fires, a cid lookup returns nothing for every card, and `TableSpec`'s own promise (*"the column and the payload cannot disagree"*) goes quietly false while the seeding's `record.get("cid")` idempotence check reports clean forever. Miss `db.TABLES["cards"]` and a **fresh** store gets no column at all, because `_ensure_schema`'s fresh path stamps `SCHEMA_VERSION` directly and `_upgrade`'s `ALTER` never runs — so every worktree, the demo seed and all nine harness tests would exercise a schema the owner's store does not have.

New T7 arm, passing today (verified):

```python
a = set(db.TABLES["cards"]); b = set(master.Inventory.CARDS.column_names)
d = set(master._card_columns(master.Card(box=1, index=1)))
checks.equal(a, b, "db.TABLES['cards'] and CARDS.column_names name the same columns")
checks.equal(b, d, "CARDS.column_names and _card_columns' keys agree")
checks.equal(sorted(d - set(master.Card.__annotations__)), ["idx"],
             "every card column is a declared field, and `idx` is the one named alias for `index`")
```

### 3.2 · Commit 3 — the seeding. Schema 2 → 3, `_add_box_ids`' shape exactly

`SCHEMA_VERSION = 3`. `db.TABLES["cards"]` gains `"cid"`. `_INDEXES` does **not** — the index is UNIQUE and gets its own `CREATE UNIQUE INDEX` statement. `_ensure_schema`'s fresh path therefore creates the column from `TABLES` and the UNIQUE index alongside the other eight; the upgrade path runs `_add_card_ids`.

**`_add_card_ids` issues the ids automatically, inside `_upgrade`, and it can never refuse.** That is a deliberate choice against the alternative of an operator-pressed migration, on two grounds: a migration somebody has to remember to run is a migration that does not happen and the PR buys nothing until it does; and `_ensure_schema` raising over one unnameable card would take every route and every command down, which is unacceptable and is why shape 4 (`nophoto:`) exists instead of a refusal.

```
under files.exclusive(directory), stamp re-read inside the lock:

  A. cols = PRAGMA table_info(cards); if "cid" not in cols: ALTER TABLE cards ADD COLUMN cid TEXT
  B. read identifications.photo_sha256 for every key                     (one SELECT, 2,535 rows)
  C. HASH EVERY PHOTOGRAPH AT ITS DERIVED ADDRESS, before BEGIN, so the
     transaction itself is row writes only                               (2,535 files, 2.68 s)
  D. BEGIN IMMEDIATE
  E. for each card, IN ASCENDING (box, index), the only stable order available:
       1. record.get("cid") present  -> KEEP IT, count it into `taken`, issue nothing
       2. the photograph hashed in C -> cid = that digest        source: disk
       3. record["photo_sha256"]     -> cid = it                 source: record   (D89 reclaim)
       4. identifications[key]       -> cid = it                 source: identification
       5. otherwise                  -> cid = f"nophoto:{key}@{card.captured_at or ''}"
       then: while cid in taken: n += 1; cid = f"{digest}-{n}"   and log duplicate_photograph
  F. UPDATE cards SET cid = ?, payload = ? WHERE key = ?
  G. CREATE UNIQUE INDEX IF NOT EXISTS cards_cid ON cards(cid)
  H. meta: card_ids_seeded = <count>, card_id_sources = {disk: N, record: N, identification: N,
                                                         nophoto: N, kept: N}
  I. meta: schema = 3                                            LAST STATEMENT IN THE TRANSACTION
  J. COMMIT
  K. _write_migration_receipt(directory, "card-ids.json", receipt)   outside, best effort
```

**THE LADDER ORDER IS THE LOAD-BEARING DECISION AND IT IS DELIBERATELY THE OPPOSITE OF THE OBVIOUS ONE.** `identifications.photo_sha256` answers every card today in 19 ms with no I/O, and taking it would make the whole migration free — and would bind all 2,535 permanent names **through the position-keyed lookup this design exists to replace, without ever reading the bytes it is naming.** It is also provably stale in a real window: `do_reshoot` writes new bytes with `files.write_atomic` and touches neither `cards` nor `identifications`, D26 forbids archiving the old photograph, so **from a re-shoot until the next paid press, `identifications[key].photo_sha256` is the digest of bytes that exist nowhere on disk and in no backup.** The store's one `reshot` event (`2/96`, 2026-08-23T18:48:56) agrees with disk today only because an `identified` event landed after it. Rung 4 stays in the ladder for a card whose photograph has vanished without a reclaim, and **it is recorded as a distinct, weaker source and reported by name**, never folded into success.

**Rung E.1 is what makes a re-run after a crash a no-op**, which is `_add_box_ids`' own rule and the survey's sharpest warning. Under a digest a re-issue would be harmless — I measured the self-heal — but the read-first line goes in anyway, because the `-n` suffix is order-dependent and a re-run must not renumber one.

**Ascending `(box, index)` is the order for `_add_box_ids`' stated reason**: `created_at` is more meaningful and is optional on these rows, so ordering on it would make the result depend on SQLite's row order.

**MEASURED, on a `.backup()` copy of the owner's live store:**

```
MIGRATION 3.018 s, ONE transaction
  hashed 2,535 files / 4,445,351,065 bytes
  sources {kept: 0, disk: 2535, record: 0, identification: 0, nophoto: 0}
  refused 0   duplicates 0   suffixed 0
  cid NULL: 0     distinct cid: 2,535
  column == payload disagreements: 0
  file 7,438,336 B -> 7,938,048 B  (+6.7%)
  cid -> (box, idx) lookup: 4.0 us, EXPLAIN says SEARCH cards USING INDEX cards_cid (cid=?)
```

**Every card was named from disk.** Rungs 3, 4 and 5 exist for populations that are empty today and will not always be: a reclaimed card (34 such records existed on 2026-09-11 and were buried), and a `captured` card between the shutter and the next press (0 today; 543 on 2026-08-23, 322 on 2026-09-11 — and a photograph exists for those, so they take rung 2).

**The cost at the rig, stated with its number: one 3.0-second stall on the first read after the pull.** `_upgrade` already takes `files.exclusive` from inside `Store.read()` — its docstring names *"the first read after a `git pull`"* as the ordinary case — and `LOCK_TIMEOUT_SECONDS` is 30, so the hash sits comfortably inside it. Step C is outside `BEGIN IMMEDIATE` so the **transaction** is 50 ms of row writes; the flock is held for the full 3.0 s. It happens exactly once.

### 3.3 · The write-time refusal, and why it is in exactly one place

**`_card_columns` raises `MissingCardId(key)` when `card.cid is None`.** One function, and it is the single chokepoint every card row passes through on its way to SQLite — so it covers **every** writer, including ones nobody has enumerated. That matters, because `allocate_capture` is not where cards are born: `record_capture`'s `existing is None` branch is, and there are **three real call sites that reach it without the allocator** — `cli/cmd_identify.py:1056`, `cli/cmd_emit.py:683` and `cli/cmd_emit.py:1064`. `store/master.py:40-42` calls this *"a seam to watch rather than a guarantee"*, and `cmd_emit`'s own comment names the case: *"A position the store has never seen — a run joined from a recovered identifications file, say."* A refusal placed only in `allocate_capture` would leave all three minting nameless rows.

`NOT NULL` is refused as the mechanism: adding it to an existing SQLite column means rebuilding the table, which is precisely the operation this design will not perform on 2,535 rows of the store of record. The UNIQUE index cannot substitute — **verified: SQLite accepts unlimited NULLs under a UNIQUE index** (three stripped rows, no refusal).

**In-memory `Inventory()` never calls `_card_columns`**, so a test that builds cards and never flushes stays green — which is correct: an object that was never stored has harmed nothing. Four harness sites do flush and must supply a cid: `t7:18361`, `t7:18404`, `t7:18441` and `t3_join_coverage.py:220`. The four in-memory sites (`t7:6648`, `6660`, `6691`, `17137`) need nothing.

### 3.4 · Who issues a cid, and the exact edit at each site

| where | the cid | note |
|---|---|---|
| `capture_server.py:do_capture` | `hashlib.sha256(blob).hexdigest()` | `blob` is already decoded in RAM at `:2390` before the `Store.write()` block. Pass it into `allocate_capture` as a keyword beside `capture_id` — **not** a member of `CAPTURE_CLAIM_FIELDS`, because a claim survives a re-record and this must not. Zero extra I/O. |
| `capture_server.py:do_reshoot` | **nothing** — `cid` is untouched | and one line is ADDED: the `reshot` history event gains `photo_sha256=hashlib.sha256(blob).hexdigest()`. Today's `reshot` line carries two capture ids and **no digest at all**, so nothing in this store records the boundary between two photographs of one card. This is what §6's audit excuses a re-shot card by, and it must be a recorded digest and never the bare fact of a re-shoot. |
| `master.py:move_card` | tombstone gets `card.cid = f"moved:{card.cid}"` | One line, beside the four existing clears, and the docstring's list of what the tombstone clears gains a fifth entry with the reason: `replace(card, …)` already hands the transplant the original cid, so leaving it on the tombstone would fire `cards_cid`. `move_cards` loops this and is covered. |
| `cli/cmd_identify.py:1056` | `item.photo_sha256` | Already set for every item at `:631` (`images.sha256_of(item.capture.photo)`) before the cache consult — PR A put it there. Free. |
| `cli/cmd_emit.py:683` and `:1064` | `images.sha256_of(path)` where the path resolves, else `nophoto:<key>@` | Both hold `resolved.photos.get(key)`. Hash it; where there is no file, write shape 4 and name the position in the report. |
| `scripts/demo-seed.py:392` | `sha256(demo-assets/photos/<row.photo>)` | The seed writes `inventory.cards[card.key] = card` directly, bypassing `record_capture` — `_card_columns` catches it at flush, which is why the backstop is the right place. **Deterministic by construction**, no allocator and nothing seeded: measured **132 pool files, 132 distinct digests, 0 duplicates**, so an unchanged tree rebuilds byte-identically and CI's republish-on-merge does not churn. Its one synthetic `moved` card (`:417`) needs the `moved:` prefix. |

### 3.5 · Previewable

`cards name` **previews and writes nothing**, on the `prices adopt` / `make reap` posture. **It opens the store `sqlite3` read-only and must never call `db.connect`** — that function is the single entry to the store and always calls `_ensure_schema` (`db.py:433`), so a preview routed through it would perform the migration it claims to be previewing. That is a hard property with a harness arm in §6.

It prints, from a read-only connection: the count per source, so a non-zero `identification` or `nophoto` says exactly how many cards will be named by something weaker than their own bytes; every card that would land shape 4, by key; every duplicate photograph it would suffix, naming both keys and both capture ids; the digest it would assign to the first and last card, so a human can check two by hand with `sha256sum`; and the receipt in full including its `reverse` sentence.

`cards name --write` takes the lock and runs the same step now rather than waiting for the next read. `cards audit` is §6's proof. `--reverse --write` is 3.6 below.

**`cli/__main__.py` gains `cards` and `harness/tests/t7_store_and_seams.py:11794`'s exact-match roster goes from nine to ten** — that list is an exact match on purpose (*"a command cannot appear in the dispatch without somebody editing this list"*) and it has already caught a merge where both sides counted eight. Update the count in its comment too.

### 3.6 · Reversible — measured, byte-identical

```
DROP INDEX cards_cid
for each card: payload.pop("cid"); UPDATE cards SET cid = NULL, payload = ?
DELETE FROM meta WHERE key IN ('card_ids_seeded','card_id_sources')
meta: schema = 2
```

**MEASURED on the migrated copy, then diffed against the pre-migration baseline table by table:**

```
REVERSE 0.033 s
  cards           2535 identical=True      identifications 2535 identical=True
  queues           565 identical=True      boxes              5 identical=True
  listings         567 identical=True      orders           122 identical=True
  fulfilment        17 identical=True      meta               3 identical=True
  events         12002 identical=True
ALL NINE TABLES IDENTICAL: True
residue: an empty nullable `cid` column
```

Byte-exact rather than semantically equal, because the reversal reproduces `store/rows.py:payload_text` — `json.dumps(payload, sort_keys=True, separators=(",", ":"))`. The residue is invisible to every reader: `Inventory.parse` drops an undeclared field on reload and an all-NULL column changes no query. That is `_add_box_ids`' stated bargain — *"additive only — no column was dropped, no payload key was overwritten, no row was removed."*

**Be honest about what the reverse is for.** On a build that still declares `Card.cid`, the next `Store.read()` sees `schema = 2 < 3` and names every card again. The reverse is for a store you are about to open with an OLDER checkout, and the receipt must say so in those words. **The reason that is safe rather than a wart is the digest**: re-applying produces the identical ids, which I measured. A reverse-and-reapply under an allocator would renumber the store.

### 3.7 · What proves no record-to-photograph link was lost

**The link is the record's own name.** After the seeding, `cards.cid` IS the sha256 of the photograph at that card's address, for every card issued from rung 2 — and the receipt's `card_id_sources` says how many that was. The proof is re-runnable by anybody, forever, on any copy, with no external state:

> For every card, `sha256(captures/cards/box<B>/<idx:04d>.jpg)` equals `cid` with any `-<n>` suffix stripped, unless the card carries a `photo_reclaimed_at` or a `reshot` history line **whose recorded digest equals the file**.

**MEASURED against the migrated copy, over all 4,445,351,065 bytes: 2,535 match, 0 mismatch, 0 excused, 0 unexplained missing files, in 2.68 s.** Not one card needed an excuse, including the single re-shot card (`2/95`, re-shot 2026-08-23, slid to index 95 by the 2026-08-25 renumber, now `retired: given_away`) — **and that is luck, not design**, because its identification was re-read after the re-shoot. §7 item 1 is that seam.

**What the audit does and does not prove, stated plainly.** Run immediately after the seeding it is close to tautological — the migration read those bytes and the audit reads them again. Its value is **temporal**: it proves the link still holds later, after renumbers, moves, deletions and reclaims. What proves it was right in the first place is a different thing: the source census, plus the fact that only rungs 2 and 3 are accepted without a named report.

**`cid-audit` is not in `make check`.** It reads the owner's 4.4 GB, and `make check` answers from the tree alone — `make lan-check`'s reason exactly. It is its own target, and `do_status` reports when it has never been run against this store.

### 3.8 · Killed with `-9` halfway: the store comes back unchanged. Proven, not asserted

I forked a process that opens a copy with the store's real pragmas (`journal_mode = WAL`, `synchronous = FULL`, `isolation_level = None`), ran `BEGIN IMMEDIATE`, performed the `ALTER TABLE`, hashed and wrote 1,200 of 2,535 rows, then `os.kill(os.getpid(), 9)` with the transaction open:

```
child exit status 9 (SIGKILL)
  kill.sqlite        7,438,336 B
  kill.sqlite-wal            0 B      <- empty
  kill.sqlite-shm       32,768 B
reopened:
  cards 2535      schema stamp 2      cid column present: FALSE
  payloads carrying cid: 0
  cards table byte-identical to baseline: TRUE
```

**Nothing survived, including the DDL** — SQLite treats `ALTER TABLE` as transactional, so the column itself is gone. **The recovery procedure is: nothing.** There is no repair step, no `--resume`, no half-state to reason about. The next read runs it again.

Why that is a property of the design and not of my harness: every write is a row `UPDATE` or a `CREATE INDEX` inside one `BEGIN IMMEDIATE … COMMIT`, the stamp is the last statement in it (`_upgrade`'s own rule — *"THE STAMP IS THE LAST STATEMENT IN THE TRANSACTION, never a separate commit"*), `synchronous = FULL` means the commit reaches disk before the call returns, and **the operation touches no file outside the database at all**, so there is no second half whose ordering against the commit has to be argued.

The other three ways a run can stop: **killed after COMMIT, before the receipt** — fully migrated, receipt absent, harmless by construction (`_write_migration_receipt` is already `contextlib.suppress(OSError)`, *"a read-only or full disk must not make an already-committed upgrade look like a failure"*); `cards audit` reconstructs everything it would have said. **Killed and re-run** — rung E.1 makes it a no-op. **Killed while another process holds the store** — `_upgrade` re-reads the stamp inside `files.exclusive`, the loser returns early, and a dead holder's flock is released by the OS on process death, which is `make suite-lock-selftest`'s own argument for `flock` over a pidfile.

**NEVER open the owner's live `inventory/store.sqlite` for writing.** Every figure above came from a `.backup()` through a `mode=ro&immutable=1` connection (0.014 s, 7,438,336 B) into the scratchpad, with `captures/` read through absolute paths and never written. `cid-selftest` builds its own throwaway store under `PKMNSCAN_HOME`; the real store is migrated by the owner's own `git pull`, on the supervisor's first read, once.

---

## 4 · WHAT IS DELETED, AND WHAT MERELY MOVES

### Deleted in this PR — and it is almost nothing, which is the honest report

**`app/src/BoxBrowse.tsx:1975` — `?card=${encodeURIComponent(stamp)}`, and `photoSrc`'s stamp parameter.** One screen out of ten already appends a photograph's id to a slot URL to make it name the right picture. Under `GET /photo/by-card/<cid>` (commit 4) the address does that work, so the query parameter becomes unnecessary rather than under-applied at 18 other sites.

**That is the whole deletion list.** Everything else this design makes deletable is deleted by a later PR, because deleting it here would either change the wire or move 4.45 GB. Section 3 of the plan was honest about `realign` being demoted rather than deleted and it was right to be; this is the same posture.

### Commit 4 — one route ADDED, none removed, and why the old one stays

`GET /photo/by-card/<cid>` resolves `cid → row → photo_path(box, idx)` — the **current** box and index, which is correct precisely because this PR does not freeze filenames. Measured: **4.0 µs per lookup, index-backed.** `Cache-Control: immutable` and an ETag that is the cid's own first 32 hex, replacing the `no-cache` + digest-ETag + `?card=` triple. `app/src/server.ts:photoUrl` takes a cid; 19 call sites across 10 screens move in one edit.

**`GET /photo/<box>/<index>` and `_PHOTO_RE` STAY, and the reason is measured, not deference.** `runs/<n>/pricing.json` holds **3,629 position records across 12 immutable files, 0 of which carry a cid**, and `#/pricing?run=<n>` is the screen that draws them. Deleting the slot route would leave those 3,629 photographs unreachable. `do_photo`'s docstring gains a sentence naming the new route as the one to prefer and this file as the reason the old one survives.

**What that buys at the rig.** D52 measured it: deleting box 2's card 180 shifted 363 cards in 288 ms and the screen went on drawing the deleted card's photograph, `transferSize: 0`, served from Chrome's in-document memory cache which consults neither the ETag nor `no-cache`. The operator's reading was that the delete had not happened, and the next press deletes the card that slid in. **17 of 19 `photoUrl` sites are still in that residual today**, and the sharpest is the Fulfiller's 320px hero: a photograph one index off sends the wrong card to a buyer, and the only cross-check on that screen is a position label rendered from the same `(box, index)`.

### What MOVES rather than dissolving

**The position key does not go anywhere.** It stays on all ten route regexes, stays the primary key of `identifications` (2,535 rows) and `queues` (565 rows), stays `events.position` (11,919 of 12,002 rows), and stays `cards.key`. **`position_key` is still called 36 times and hand-composed as an f-string in seven more places** — `cli/resolve.py:290,1107,1486`, `capture_server.py:7693`, `pipeline/merge.py:116`, `identify/sidecar.py:164` — plus ~20 sites in `app/src`. Consolidating those seven is a real prerequisite for any later PR that re-keys, and it is **not** in this one: nothing here reads the key differently, so consolidating it now would be an unrelated diff in a PR whose whole value is that it is additive.

**`identifications` gains nothing in this PR, deliberately, and the reason is money.** Re-keying the cache to `cid` is the highest-value single change this seam unlocks — it closes the batch hazard and the renumber's hand re-key at once — and it is the one that can spend cash. **If any build ever reads a cid-keyed cache without understanding cid, 2,535 paid answers read as absent and the next store-wide press bills ~$3.63** (2,535 × $0.00143–0.00145). `photo_sha256` must stay on every entry as the staleness gate whenever it does move: re-keying without it would make every entry look reusable forever and bill a re-shot card its old answer with no photograph left to disprove it, which the cache's own header calls *"the single worst failure available to a cache in this pipeline."* Note the latent half: `Cache.reusable` returns a `cleared_by_human` entry **without** checking the digest, by design — measured **0 of 2,535 carry that flag**, so the bypass is one review answer away from being live.

**`queues` gains nothing.** Its `upsert` keys on `entry.position` and refuses to re-queue a cleared position; a cid arriving beside that without moving the upsert key would inherit the bug D162/D167 just spent a PR fixing. All 565 rows still carry a stored `label`, **291 of which disagree with today's rendering** — a sixth copy of the identity, wrong on 51.5% of rows, re-rendered by every route so never served. Not this PR's to fix.

**`events` gains nothing, and this is the largest deliberate omission.** `events.position` stays exactly as it is, so the history stays ambiguous across the **1,088 position keys that have opened more than one occupancy** (`1/1` fifteen times; **6,771 of 11,919 position-carrying events sit at such a key; 970 of 2,535 live cards do**). `_state_before_sale`, the graveyard and every history read keep today's behavior. The measured reason is §1's: three implementations of the same described replay, three mis-bind rates (22.3% / 31.3% / 32.8%), 35 `sold` and 133 `buried` lines among them, and **a non-NULL value on every row under all three**. The correct algorithm exists on paper — segment by occupancy, resolve `moved`/`buried` through their own `moved_to` (which recovers the 130 box-6 events whose cards are alive in box 3 at indices 823–887; **164 of 198 `buried` payloads carry `moved_to` and all 164 resolve**, and 34 more carry both a `capture_id` and a digest), and give every remaining line a NAMED departed value. It is a later PR, it needs its own measurements, and **it may never be worth its risk.**

**`fulfilment` gains nothing.** The three dangling refs stay dangling in this PR. They are repairable — all three resolve to a `buried` event carrying `photo_sha256`, which is the card's cid — but `fulfilment` is 17 rows keyed by ORDER, each holding many capture ids across many SKUs, so the repair is a payload rewrite and not a column, and `Ledger.holder_of` walks the ledger's own map and never opens `cards`. Say this in the PR body rather than promising an outcome a column cannot deliver.

**`identify/sidecar.py:164 key` keeps its false claim for now.** Its docstring calls `f"{box}/{index}"` a *"Stable id for the batch and the cache"*, and it becomes the Batch API `custom_id`. Submit 678 requests, delete one junk capture mid-box, and 537 paid answers come back keyed one card off — each plausible, each billed. **It has not fired and nothing prevents it.** The fix is cheap and self-contained (`images.prepare` already calls `sha256_of` at `:378`, 0.7 ms against 113 ms to crop, a 161× ratio) and it is deliberately a separate PR so that this one's diff stays inside `store/` plus two functions.

**`realign` is not demoted.** §2 says why: 701 of 3,728 run records still need re-binding and no cid can reach backwards into a file written before it existed.

**`do_remove_card`'s renumber and `do_move_card`'s tombstone stay whole.** These are the two things the plan's excluded sentence named, and they are the two this PR does **not** collect — 1,608 filesystem operations to delete one junk capture, and 164 `moved` events' worth of copy-and-tombstone. §7 item 2 is the contradiction that has to be resolved first, and §7 item 3 is the three commitments that cannot all hold.

---

## 5 · THE ORDER OF WORK

**`server/pipeline_routes.py` is the file that collides and this PR does not touch it — not one line.** That is the scheduling fact that matters: nothing here contends with C, D, E, G or H over the file that has collided before. What it does touch is `store/db.py`'s `_upgrade`, which is the one function where a merge conflict is a data-loss hazard.

| PR | before or after | why |
|---|---|---|
| **C** — the `submissions` claim table | **AFTER**, except commit 1 which goes **BEFORE** | C adds a table and therefore a schema step. **Two concurrent 2→3 steps in `_upgrade` is a conflict in the one function where taking either side silently loses a migration.** Whichever merges first is 2→3 and the second is 3→4; C goes first because it is the only thing in this whole plan that protects a dollar and must not wait. **Commit 1 (the forward-version guard) is carved out and lands ahead of C as a one-commit PR** — it is two lines plus a T7 arm, touches nothing anyone else touches, changes no behavior on any existing store, and it is what makes C's own schema bump safe too. |
| **D** — the selection | **PARALLEL, rebasing onto D if both are in flight** | D touches `pipeline_routes.py` and `cli/__main__.py`; I touch `cli/__main__.py` only, adding a `cards` sub-parser. The overlap is one block and the t7 command roster — D changes `identify`'s arguments and adds no command, so the roster count moves only for me (nine → ten). Rebase onto D rather than the reverse because D's diff in that file is much larger. **Handoff trap 6 applies to the roster**: a conflict in an exact-match list can go green while dropping an entry, so resolve it by recounting from `entry.COMMANDS`, never by taking a side. |
| **E** — composer stage 1, `CarriedScope` → keys | **BEFORE E** | Commit 4 changes `photoUrl(box, index)` → `photoUrl(cid)`, a signature 19 call sites use across 10 screens. A signature change wants a quiet tree, and E is easier to write against the new signature than to rewrite after it. E's own files (`RunsComposer.tsx`, `runScope.ts`, `runHandoff.ts`) are not among my 10. **And E should carry cids in `CarriedScope`, not position keys** — the plan already schedules it to become `{keys: string[]}`, and a cid is a strictly smaller change than a position key because nothing has to re-resolve it. |
| **G** — `join` optional, store-backed loader, `submitted` in the manifest | **PARALLEL, zero overlap** | G touches `cli/resolve.py` and `cli/cmd_join.py`; I touch neither. G benefits directly: a store-backed loader can read the cid alongside `(box, index)`, and every manifest written after it can record the cid — a copy of a name, which cannot drift, unlike a copy of a position. **Say this in G's own PR body**; it is the one place the two plans compound. |
| **H** — the `readings` table | **BEFORE H** | H adds a table and therefore a schema step, on C's argument exactly. H is last and cuttable, so it takes the higher version. |
| **A, B, F** | already merged (#301, #304, #302) | Carry the addendum's corrections: **PR A's fifth `prepared is None` consumer** (`cmd_identify.py:837` → `resolve.py:1108`'s `blind`) is why `item.photo_sha256` is now set for every item at `:631`, which is what makes my `cmd_identify` edit free. |

**One operational precondition, not a code change, and it belongs in the PR body:** do not merge commit 3 until commit 1 is on main **and** the main checkout's supervisor has re-execed onto it. Until then every one of the **27 worktrees on this machine** is a build that will rewrite a schema-3 stamp down to 2 and strip a cid per write, silently, exactly as probe 2 measured.

---

## 6 · HOW IT IS PROVEN

**An outcome assertion cannot see a work-saving (PR A's arm 9) and a file count cannot prove a dedupe (PR B's). The same trap applies here in its sharpest form: a count of rows carrying a cid cannot prove the migration ran correctly, because every row gets a value and a correct seeding and a seeding nothing checked print the identical row.** So every assertion below counts **positive work**, and every counter that could read as "nothing was needed" is named so it cannot.

### 6.1 · The assertions that can see a half-applied migration

A migration half-applied *inside* the transaction cannot exist — §3.8 proved it with `-9`. The half-applied states that CAN exist are three, and each gets its own positive counter:

1. **Seeded but never verified against the bytes.** The receipt reports `verified_against_disk: N` (rungs 2 and 3 only), and **`_add_card_ids` refuses to stamp unless `N + kept + nophoto + identification == card_count` AND `identification == 0` unless `--accept-unproven` was passed.** `disk: 0` must never read as "no photograph needed hashing"; the field is named `verified_against_disk` for exactly that reason.
2. **Seeded, then STRIPPED by an older build, then re-opened.** `select count(*) from cards where cid is null` with `meta.card_ids_seeded` present is a named refusal, `card_ids_stripped`, naming the keys and the instruction — never a silent re-issue, even though under a digest the re-issue would be correct. Probe 2 is the harness case, verbatim: plant ids, stamp 3, run one `set_state` with `Card.cid` monkey-deleted, assert the refusal fires and names `3/17`.
3. **Column and payload disagreeing.** `select count(*) from cards where cid is not json_extract(payload,'$.cid')` must be 0 — **after the migration AND after a subsequent ordinary write.** That single query is what catches commit 2's roster reconciliation having been missed anyway, and it is the assertion `2,535 ids in 3.0 s` cannot make.

### 6.2 · `cid-selftest` — counts work, on a throwaway store under `PKMNSCAN_HOME`

- **the seeding hashes exactly `card_count` files** on a store with complete identifications — not "at least", not "zero is fine";
- **a re-run hashes 0 files and issues 0 ids**, and every cid is byte-identical to the first run's (the self-heal, measured at `3/17`);
- **the re-run after a strip issues exactly as many ids as were stripped**, and each equals what it was;
- **the migration performs 0 renames, 0 unlinks and 0 writes outside the database** — count the filesystem calls, do not assert about the outcome;
- **the duplicate arm fires deliberately**: write the same bytes twice through `do_capture` with two capture ids, assert `X` and `X-2`, the `duplicate_photograph` event naming both keys and both capture ids, and the receipt row. **This arm has never run in production — 0 duplicate digests among 2,535 real photographs and 0 among 132 demo pool files — so a green suite over zero firings proves nothing**, which is why it must be provoked rather than asserted about;
- **the re-shoot arm fires deliberately**: capture, re-shoot, audit, and assert the excuse came from the `reshot` line's **recorded digest matching the file** and not from the bare fact of a re-shoot. A `reshot` line with no digest is a NAMED UNPROVABLE that exits non-zero — never an excuse;
- **the preview never migrates**: run `cards name` against a store stamped 2 with no cid column and assert the column is still absent and the stamp still 2 afterwards. Assert by source inspection too that the preview path does not reach `db.connect`;
- **the reverse restores all nine tables byte-identically**, reproducing `payload_text`'s exact serialization (measured: 0.033 s, nine of nine);
- **the `-9` case**: fork, `BEGIN IMMEDIATE`, write half, `kill -9`, reopen, assert 2,535 cards, stamp 2, **no cid column**, and the `cards` table byte-identical to the baseline. Prove it by violating it, `make suite-lock-selftest`'s standard.

### 6.3 · `cid-audit` — and it has a NOT-KNOWN verdict

Read-only, re-runnable by anybody on any copy, **2.68 s over 4,445,351,065 bytes measured**. Three verdicts, never two: `pass` (every card's cid equals its photograph's digest, or is excused by a recorded digest), `fail` (a named mismatch, listed), and **`not known`** — which it prints when the `cid` column is absent, when any cid is NULL, or when it was pointed at no photographs. A "for every card, `sha256(file) == cid`" check over zero rows prints `checked 0, mismatch 0` and reads as a pass; that is the shape this repo has now hit nine times in twenty-four hours and it does not get a tenth.

`do_status` reports when `cid-audit` has never been run against this store, and reports a `nophoto:` population above zero by name.

### 6.4 · Harness placement, and the mechanical rosters that must move with it

- **T7** takes the new arms — the store's own seams live there: the forward-version guard, the roster reconciliation, the strip refusal, the column/payload query, the move tombstone's `moved:` prefix, the CLI roster going nine → ten.
- **T3** needs `cid=` at `t3_join_coverage.py:220` (it flushes).
- `cid-selftest` joins **`make check`**, which means editing three things together or `make docs-audit`'s **`check census`** row fails the commit: the `check:` recipe in the `Makefile` (23 targets today), `scripts/checks.py`'s `CHECKS` tuple (a full entry with `runs`, `asserts`, `needs`, `writes`, `commit_path`, `why_off_commit_path`, `gates`, `governed_by`), and every published list — `CLAUDE.md`'s and `make help`'s. That row exists because `make help` under-reported by five targets for months with nothing comparing the two, and **it refuses to go quiet**: a claim reworded past its pattern is reported as an unwatched sentence.
- `cid-audit` does **not** join `make check` — §3.7.
- **Mutation arms, one per guard, and report a survivor rather than explaining it away** (PR #305's survivor revealed two dead exclusions carrying a comment that claimed otherwise): delete the forward-version comparison; delete one name from each of the three column rosters; delete `_card_columns`' refusal; delete rung E.1's `record.get("cid")`; delete the suffix loop; delete the `moved:` prefix; make the preview call `db.connect`; make `_add_card_ids` stamp without the source-count check. Re-run each against the whole nine-test harness, not just the new check, and **report equivalent mutants as equivalent instead of counting them as caught.**

### 6.5 · A decision entry, in the same session

`docs/decisions/D172-the-first-photograph-is-the-name.md`. **Never guess a D number** — write the heading as `## D-` followed by a lowercase hyphenated slug and let `make merge` claim it (D140); `make claim-stale` catches a claimed number that goes stale. One-line bold runs, `_add_box_ids`' receipt shape. It must carry: the 2,535/2,535 proof and the 2.68 s figure; the 701-of-3,728 run-record measurement as the production receipt that a content id beats a positional one; the two probes (the silent downgrade, the one-write strip) with their outputs; **the self-heal measurement, because it is the whole argument against an allocator**; the frozen-not-tracked distinction in one sentence; D89's narrowing with its population-of-zero measurement; the four shapes with their zero populations and the honest admission that three of them have never fired; and the reverse sentence. `python3 scripts/index-decisions.py --write` also appends to `docs/decisions/ORDER.json` — expected, and the manifest line is resolved by hand, main's numbers first and the slug last.

`docs/map.py` needs an entry for `scripts/cid-audit.py`; adding a file under the mapped directories without one fails the commit.

---

## 7 · WHAT I AM LEAST SURE OF

**1 · The re-shoot is the seam in my own thesis and today it passes by luck.** `cid` is frozen, so after a D26 re-shoot it no longer matches the file — which means `cid-audit`, the thing this design is sold on, needs an excused set, and the excuse has to come from the `reshot` history line. **Measured: the one `reshot` event on this store (`2/96`, 2026-08-23T18:48:56) carries `capture_id` and `replaced_capture_id` and NO DIGEST AT ALL.** It passes the audit only because its identification was re-read afterwards. Commit 3 adds the digest to that line — bytes already in RAM, one field — but the excused set is **0 of 2,535** and its correctness from then on rests on a field with zero production history. **Settle it:** capture into a throwaway store, re-shoot, run `cards audit`, and assert the excuse was drawn from the recorded digest and not from a coincidence — then mutate the digest and see the audit go red. The alternative I did not fully evaluate is keeping the *current* photograph's digest on the record always, beside the frozen cid, which would make the audit exact with no excused set at all; D89's objection to that is weaker than it reads, because both writers (`do_capture`, `do_reshoot`) hold the bytes in RAM. **It is the first thing I would look at again and I am not confident enough to reopen D89 inside this PR.**

**2 · `do_remove_card`'s own docstring contradicts the photos survey, and I did not resolve it.** The survey reports that a kill-then-retry of the renumber destroys 2 photographs, reproduced on an APFS clone of real box 2. The function's docstring argues the opposite in detail — *"a rename RESUMES rather than repeating … the RECORD is what breaks the tie"* — and names the record as what distinguishes a card that never had a photograph from one whose photograph has already moved. **One of the two is wrong. I did not run it.** This PR does not touch the function, so nothing here depends on the answer, but **no later PR may delete that loop until it is reproduced on a copy**, because if the docstring is right the loop is the safe version and the deletion would be a regression sold as a fix. **Settle it:** clone real box 2 with `cp -Rc`, run `do_remove_card` against the copied store under `PKMNSCAN_HOME`, kill at mover 275, retry, and hash every surviving file against the pre-kill digests. `grep photo_missing harness/` returns **0**, so that arm and its refusal have never been tested either way.

**3 · The three commitments a filename-freezing PR cannot all keep, and I am naming them rather than scheduling them.** Freezing the photograph's filename at its birth address, leaving `next_index` unchanged, and forbidding a cid-named file are mutually inconsistent: `do_remove_card` **compacts** (its first rename consumes the target), `allocate_capture` assigns off the high-water mark, and `files.write_atomic` does no existence check — so one remove followed by one capture composes a path a live card's frozen address still names and **overwrites a photograph that cannot be re-taken**. Any future PR in that direction must answer three questions first, in writing: where is the birth address stored, what does `photo_path` become, and how is a never-reused index allocated. **Unmeasured on this tree** — I did not reproduce the overwrite, I read the three functions.

**4 · Whether the owner wants a 64-character id on the wire.** `GET /photo/by-card/<64 hex>` is 64 characters in every access-log line and network panel. Nobody types it, `#/inventory` still addresses cards by box and index, and the short form (`cid[:12]`, mono per D124) is what would appear in prose and on screen — the ETag already truncates to 32 hex at `capture_server.py:2834`, so there is precedent for shortening on the wire and an ambiguity waiting to happen if a short form ever becomes a lookup key. **I chose the full 64 without asking and it is a taste question I have no authority over. Settle it by asking.**

**5 · The 3.0-second stall lands on the owner's live capture server, unattended, and I did not measure it there.** The seeding runs inside `_upgrade` on the first `Store.read()` after the pull, under `files.exclusive`, and on this store that is 2.68 s of hashing plus 50 ms of row writes. `LOCK_TIMEOUT_SECONDS` is 30 so nothing times out, and `REQUEST_SLOTS = 4` means at most four requests queue behind it. **But `make launch-agent` keeps that process alive at login over the real store, and I measured the 3.0 s on a copy with a warm page cache, not on the rig mid-sitting with a feeder emitting a card every 623 ms.** A cold cache over 4.45 GB could be much worse. **Settle it:** `cards name` on a copy with the page cache dropped, and — if it is bad — hash outside the flock and re-verify the digests inside it, which is a correctness-neutral reordering because the file cannot move while the lock is held.

**6 · "100%" is not what this delivers, and the plan should stop saying it.** This takes the box out of the card's NAME. It does not take it out of the card's KEY, the cache's key, the queues' key, `events.position`, the photo path, the sidecar, or the ten route regexes. Two of the four things the plan's excluded sentence named are still paid in full after this merges: the move is still a tombstone plus five hand-moved copies, and the renumber is still 1,608 filesystem operations. What changes is that every one of those becomes a mechanical follow-through over a name that cannot move, instead of a re-key nobody can safely attempt. **Call it the seam, priced and proved, and name the four follow-on PRs** — the batch `custom_id`, the `identifications` re-key, the `fulfilment` repair, and the key itself.

**7 · Every number here carries the read that produced it, and two of mine will not reproduce.** Main at **`df6ec79`**, store **`md5 b3373ed823a7b397054e9980f2ddcaa9`**, 2026-09-12. Three of the store survey's figures measure clean on this tree — the 536 drifted `photo` paths are **0**, the 2,534-of-2,535 derived-address agreement is **2,535**, the 45 drifted parked-queue paths are **0** — against a tree roughly 49 PRs further on. **Do not build a guard against a defect that is no longer there, and do not read my 2,535/2,535 as permanent.** Run `cards name` as a read-only preview before trusting a single figure in §3.