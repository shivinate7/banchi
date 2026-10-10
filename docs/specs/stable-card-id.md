# The first photograph is the card's name (`cards.cid`)

**Status: BUILT.** The `cid` column, the seeding, the relocation, the audit and the photograph
routes are in the tree. D172 (a card's name is its first photograph) holds the ruling. D183
(photos filed by name, not number) holds the re-scope. Section 0 governs. Sections 1 to 6
describe the id, the migration and the proofs. Section 0.9 lists what is built and what is not.

**The rule.** A number a person reads is never a key that a machine uses. `Box 3 - Section 2 -
Card 17` is an instruction to a hand at a drawer. It is derived from the store at draw time.
The card's name is a frozen sha256. The photograph is stored under that name.

## 0. The photograph is stored under the card's name

### 0.1 The systems problem: one string did three jobs

`(box, index)` was the card's IDENTITY (the store's primary key), the FILENAME of its
photograph, and the ADDRESS that a human reads off a shelf. Each of these hazards came from
that one conflation.

| the hazard | why |
|---|---|
| a D83 move needed a tombstone and hand-moved derived copies | moving a card changed its identity |
| one junk capture deleted mid-box renamed every photograph behind it and rewrote every sidecar | the filename WAS the index |
| remove-then-capture could overwrite a photograph that cannot be re-taken | `next_index` and a filename could compose the same path twice |
| a D26 re-shoot broke the frozen digest | the photograph was identified by where it sat |
| D36's `realign` exists to repair drift between a run's remembered positions and the store | a run bound a photograph to a position |

A `cid` column alone would name the card and leave the photograph filed under the address. The
address would stay load-bearing for the bytes, and every hazard would survive. So the
photograph moves under the name.

### 0.2 The rule, in its general form

D145 applied this rule to boxes: a drawer has a `bid` that is never reused, and the number on
its front is a label. The rule now covers cards, photographs and runs. `pipeline/join.Position`
computes the label. It stays purely derived.

### 0.3 The layout: the photograph is named by the card

```
BEFORE   <home>/captures/cards/box3/0017.jpg        the address is the filename
         <home>/captures/cards/box3/0017.json       the sidecar beside it

AFTER    <home>/photos/6b/6b1cf2fd83713889....jpg   the card's own name is the filename
         <home>/photos/6b/6b1cf2fd83713889....json  the sidecar beside it
```

`store/photos.py` is the one module that composes that path. Three properties follow.

1. **A renumber is a no-op.** `do_remove_card` renames no photograph, because no filename is an
   index. The sidecars keep the index that the capture claimed.
2. **A move is a field update.** The path holds no box, so a card that crosses drawers moves no
   bytes.
3. **A capture cannot overwrite another capture's photograph.** `cid` is UNIQUE on `cards`, and
   the path is a pure function of it. Two cards cannot compose one path. The overwrite is
   absent, not defended against. No birth address exists, and no index is allocated for a
   filename.

**The shard is two hex characters wide.** This is the one number that is a guess. 256 buckets
hold a few thousand photographs at about ten per directory. Nothing lists that directory, and
every read is a direct open by name.

**The store is outside `captures/`.** `identify.sidecar.scan` walks its root recursively and
turns every photo-suffixed file into a capture, and so into a paid Batch request. A store
under `captures/cards/` would submit and bill every card twice. So `photos/` is a sibling of
`captures/`, `runs/` and `inventory/`. It is gitignored bare, with no trailing slash, because a
worktree can put a symlink at that name. `make ignore-check` reads the pattern (D47).

**`identify/sidecar.position_from_path` refuses a cid-shaped stem.** That function takes the
last run of digits in a stem as the index. A 64-hex digest ends in digits, so a cid-named
photograph with no sidecar would have read a plausible, wrong index. A cid-shaped stem now
gives `index = None`. The card goes to the review queue flagged `no_position`.

### 0.4 The address is a rendering

A readable address exists on demand, as a rendering. The store never keeps it where a write
must keep it true. `identify` reads a selection (D180), and the run route scans the sidecars
and photographs directly. `sidecar.load` resolves the index per field, so a sidecar that
names the current index is read as the sidecar's own claim. No precedence changed.

### 0.5 The relocation: resumable, and verified per card

The relocation moves each legacy photograph to its name exactly once. It is not part of
`_upgrade`. It is its own step (`./banchi cards photos [--write]`), and it previews by
default. It opens the store read-only and takes no write lock. Per card, in ascending order:

```
1. destination exists and hashes to `cid`  -> already done
2. legacy file hashes to something else    -> refuse this card by name, move nothing
3. os.link(legacy, destination)            a hard link, no bytes copied
4. hash the destination, require `cid`     -> else unlink it, refuse
5. unlink the legacy file
6. the sidecar, the same steps, best effort
```

**A hard link, not a rename.** A rename verifies after the only other copy is gone. A hard link
gives two names for one inode. The digest is read again from the new name before the old one is
dropped. Killed anywhere, the bytes exist under at least one name, and a re-run finishes the
move. No state exists in which a photograph has no name.

**A refused card is left alone and named in the report.** A legacy file that does not hash to
its card's `cid` is the one case where something is wrong. A re-shoot that no one re-read is
the likely cause. Moving it would file it under a name it does not have.

**The read path prefers the name. It falls back to the legacy address until the store is
stamped.** `meta.photos_relocated` is written only when a pass finds every card's photograph
at its name. Once it is set, the legacy address is never read. So the fallback cannot hide an
unfinished move. `make status` reports the residue by count. Whether the owner's store is
stamped: unmeasured here.

### 0.6 The three hazards, decided

**Hazard 1: the migration's store lock lands on the live capture server.** The decision is
three parts. Hash outside the lock. Re-stat inside it. Keep the relocation out of the upgrade.

- The corpus is hashed before `files.exclusive`, and `(size, mtime_ns)` is recorded per file.
- Inside the lock every file is re-stat'ed. A file whose stat moved is re-hashed. The receipt
  counts these as `rehashed`, a positive counter.
- The transaction writes rows only.

A capture lost mid-feeder leaves a physical card in the drawer with no record, and that
renumbers every card behind it. It is the worst outcome in this pipeline, because it is silent
and physical. A re-shoot can change a file during the window. A changed `mtime_ns` catches it,
and a re-hash answers it.

**Hazard 2: a write-time refusal in `_card_columns` takes down every writer, including the
shutter.** The decision: `_card_columns` does not refuse. The refusal is in `record_capture`'s
`existing is None` branch, where a card is born. It raises `UnnamedCard`. The birth site is
reached by `allocate_capture` and by `cli/cmd_identify.py` and `cli/cmd_emit.py`. The shutter
cannot reach it, because `do_capture` hashes a blob already in RAM.

A refusal in the row chokepoint is a 500 on `POST /capture` mid-sitting, with the card already
in the drawer. `_ensure_schema` rejects the same shape one layer up. A NOT NULL column is not
an option, because SQLite rebuilds the table to add one. A UNIQUE index cannot substitute,
because SQLite accepts any number of NULLs under one.

**Hazard 3: a build that does not declare the column strips it silently on any write.** Old
worktrees are pre-guard builds. The decision: keep the self-heal, and make it loud.

- A NULL cid on a stamped store is repaired on the next open by the same ladder as the
  seeding. Under a digest the re-issue is byte-identical.
- The repair shows in three places: `cards_reissued` in the receipt, a `card_ids_reissued`
  history event that names every key, and a line in `make status`.
- The probe is cheap because the index is partial: `cards_cid_missing` covers `WHERE cid IS
  NULL`. It is empty on a healthy store, so the check runs on every open.

Prevention is at the open. The forward-version guard (3.1) refuses a store stamped newer than
the build knows. A worktree that has not pulled stays a stripping build until it does. The
self-heal makes that survivable.

### 0.7 What becomes unnecessary, and what is kept

`realign`, `_photo_digests` and `refuse_reallocated` (D36) are unnecessary for every run
written after this change. A run record's `photo_sha256` is the photograph's filename, so
nothing binds bytes to a position.

They are kept. A `cid` cannot reach backwards into an immutable run file that was written
before it existed. `#/pricing?run=<n>` and "Join again" re-read an OLD receipt against
today's store. For those records, the repair layer is the only thing that makes the answer
right. It can go when no run directory that predates the change is still readable.

`GET /photo/<box>/<index>` stays for the same reason. Old `runs/<n>/pricing.json` files hold
position records with no cid. Deleting the slot route would leave those photographs
unreachable.

### 0.8 Doubts from section 7, and where they stand

| item | the doubt | now |
|---|---|---|
| 1 | a re-shoot breaks the frozen digest, so the audit needs an excused set | closed. A re-shoot writes new bytes at the card's own name. The `reshot` history line records the new `photo_sha256`. The audit excuses a card only by a recorded digest that equals the file |
| 2 | `do_remove_card`'s docstring and a survey disagree about a killed renumber | closed. The rename loop is gone, and the docstring says so |
| 3 | freezing a filename, keeping `next_index` and forbidding a cid-named file cannot all hold | closed structurally. The name is a UNIQUE sha256 and no filename is an index |
| 4 | whether the owner wants a 64-character id on the wire | open. The full 64 characters is built. `cid[:12]` is what prose and screens use. Nothing types either. Only the owner can rule |
| 5 | the seeding stalls the live capture server | closed by hazard 1. The lock holds for row writes and a re-stat |
| 6 | "100%" | not the claim. The box leaves the photograph's path and the run's re-binding. It stays in `cards.key`, the cache's key, the queues' key, `events.position` and the route regexes |

The re-scope has two costs. First, it moves gigabytes of photographs that cannot be re-taken,
where the first design moved none. So the relocation previews by default, is verified per card
and is resumable. Second, `photos/` is a new top-level directory, and a worktree can put a
symlink at that name. `make ignore-check` covers it.

### 0.9 Built, recorded, neither

**BUILT.**

- `cards.cid` (schema 4) and the seeding with its receipt.
- The forward-version guard, the four-roster reconciliation and the partial-index self-heal.
- `store/photos.py`, and the relocation with its preview.
- The `GET /photo/by-card/<cid>` route, and the client that uses it.
- `./banchi cards name`, `audit` and `photos`.
- `make cid-selftest` and `make cid-audit`.

**Two rules in `store/db.py` keep the cid unique.**

- `SqliteSource.upsert` is `ON CONFLICT (<primary key>) DO UPDATE`, never `INSERT OR REPLACE`.
  `INSERT OR REPLACE` resolves a conflict in ANY constraint by deleting the conflicting row, so
  a second card with a held name would delete the first card. The claim "two cards cannot
  compose one photograph path" rests on two cards never holding one name.
- `flush_rows` clears every touched key before it writes any. A mid-box renumber re-keys rows,
  so two rows briefly hold one name, and SQLite checks a UNIQUE index at once.

**A guard is trusted once it goes red on its defect.** Two guards can mask each other. The
relocation's source check and its destination re-hash end in the same outcome, so the re-hash is
provoked by making `os.link` land different bytes.

**The client.** `photoUrl` in `app/src/server.ts` is the one place that builds a by-card URL.
It sends `?v=<capture id>`, which moves exactly when the bytes do. `PHOTO_CID` there is the
client half of the server's `is_photo_cid`. An `InventoryCard` can carry the raw name,
including `moved:<hex>` on a tombstone and `nophoto:<key>@<stamp>` on a record that `emit`
made. Two of the four shapes name no file, and `photos.path` refuses to compose one. The
client must not ask for them.

**RECORDED.** This file and the decision entries.

**NEITHER.** These are unchanged and not follow-ups of this work.

- The batch `custom_id` (`identify/sidecar.Capture` calls `f"{box}/{index}"` a stable id).
- The `identifications` re-key. If any build reads a cid-keyed cache without understanding
  cid, paid answers read as absent and the next store-wide press bills again.
  `photo_sha256` must stay on every entry as the staleness gate.
- The `fulfilment` repair for dangling capture references.
- `position_key` itself.

## 1. The id, in one sentence

**`cards.cid` is the sha256 of the photograph the store held when the id was issued, read off
the disk and frozen from that moment. It is a birth certificate, never a live content address.
It is the only candidate identity that can be re-checked against photographs that cannot be
re-taken.**

The id is not invented or allocated. It is read. On the store measured, every stored digest
equalled its file, with no missing file and no duplicate. That measurement is the proof that
each move has an oracle. Re-run `./banchi cards audit` to measure it again.

### The rejected options

- **`capture_id`.** It names a photograph, not a card. `do_reshoot` overwrites it. `move_card`
  clears it on the tombstone. The column has no UNIQUE constraint. A `fulfilment` reference to it
  can dangle after a burial. It stays as the photograph's id and `allocate_capture`'s
  replay guard.
- **A never-reused integer from a `meta` high-water mark.** Two probes on copies killed it.
  A build that does not declare `Card.cid` strips it on any ordinary write with no error, and
  a UNIQUE index does not object to NULLs. Under a digest, the next seeding re-issues the same
  id, byte for byte. Under an integer it would hand the card a fresh number and orphan every
  reference to the old one. An integer cannot be checked against anything on disk.
- **A replay-derived occupancy integer.** The replay algorithm is under-specified. Three
  implementations of one described replay gave three different mis-bind rates against the
  naive key join.
- **A server-minted UUID4.** It fails for the integer's reason. It is also not derivable, so
  no second source can ever reconcile it.
- **The position key with the box removed.** It invites being read as an address. A stored
  label already went wrong on many queue rows.

### Frozen, not tracked, and the four shapes

`cid` is issued once and never recomputed. So it survives a D26 re-shoot, a D89 reclaim, a D83
move, a renumber and a box deletion. It is not a copy of the current photograph's digest.
`Card.photo_sha256` (D89) already holds that and keeps its narrow job. A `cid` is one of four
named shapes, and never NULL.

| shape | means |
|---|---|
| `<64 hex>` | named by the photograph the store held at issue |
| `<64 hex>-<n>` | the nth card whose bytes are identical to an earlier card's |
| `moved:<64 hex>` | the tombstone that a moved card left behind (`move_card`, `MOVED_CID_PREFIX`) |
| `nophoto:<box>/<index>@<captured_at>` | a card with no photograph and no digest anywhere |

`store/photos.is_photo_cid` is the one predicate that tells shapes 1 and 2 from 3 and 4. A NULL
is never one of the four. A NULL cannot tell "no photograph was found" from "this migration did
not look", which is this repo's signature defect. Shapes 2, 3 and 4 exist for populations that
were empty when measured. Whether they have fired on the owner's store: unmeasured.

**Naming.** `cid` sits two fields from `capture_id` and does not abbreviate it. The
symmetry is `bid` : box :: `cid` : card. `card_id` is taken by the T1 fixtures.

## 2. What stays

- **The label.** `Box 3 - Section 2 - Card 17` is unchanged. `pipeline/join.Position` stays the
  only label formula, and `join.departed_label` stays the answer for a card in no slot. The
  Fulfiller reads it at a 32px floor (`make design-check`). A `cid` never appears on his screen.
- **`store/master.position_key` and `cards.key` (`"<box>/<index>"`).** The position key stays
  the primary key of `cards`, `identifications`, `queues` and `events.position`. The cid sits
  beside the key on `cards` alone.
- **`Inventory.next_index`.** It is D10's high-water mark: `1 + max(index)` over every state.
  D10 argues permanent gaps from departures. D26's re-shoot is not a second ground, because the
  allocator is never involved.
- **The shutter-to-sidecar path.** `_require_box`, `allocate_capture`'s `capture_id` replay
  guard, `PositionOccupied`, `next_index` inside the lock, `sidecar_payload(box, index, ...)`,
  `open_section`'s `S`. D299 (boxes have no lid or capacity) removed the seal check.
- **The wire.** The ten anchored route regexes keep `(\d+)/(\d+)`. One route is added, and
  none is removed.
- **D88's transaction.** One `BEGIN IMMEDIATE` over every table, inside the flock. It is why the
  seeding is one step and a kill leaves nothing behind.
- **D7's fungibility.** `listings` is keyed by SKU and carries no position.
- **D145's `bid` is the template.** `_add_box_ids` set the shape. It is additive. A re-run is a
  no-op, because it reads the existing value first. The stamp is last inside the transaction.
  The receipt carries a plain-English `reverse` sentence.
- **D89's `photo_sha256` and `photo_reclaimed_at`.** They stay, narrowed. The pair travels
  together. A screen that finds them set draws "reclaimed", not "missing". D89 says the digest
  is `None` while the file exists. That holds for a field that tracks the current photograph,
  which is why `cid` must not do that job.
- **D36's repair layer** (0.7).
- **`capture_id`.** It stays as the photograph's id and the replay guard (section 1).

## 3. The migration

Schema version 4 adds `cards.cid`. Version 3 is D174's `submissions` table. Each step in
`_upgrade` owns one version (section 5).

The seeding touches no file outside the database. That property lets it run inside `_upgrade`.

### 3.1 Two guards land first

**The forward-version guard.** `_ensure_schema` in `store/db.py` refuses a store stamped newer
than the build knows, with a message that says to update the checkout. Without it, an older
build opens a newer store and rewrites the stamp DOWN. It then strips every field that it does
not declare, one row per write, silently. The guard protects only builds that have it. It cannot cover the
older ones, and this section says so.

**The column-roster arm.** Four hand-written rosters must all name `cid`: `Card.__annotations__`,
`_card_columns`, `Inventory.CARDS.column_names` and `db.TABLES["cards"]`. `cid` is TEXT, which is
`_ddl`'s default. If `_card_columns` misses it, every write stores the cid in the payload and
leaves the column NULL. If `db.TABLES["cards"]` misses it, a fresh store gets no column. The T7
arm compares the rosters. `scripts/cid-selftest.py` also runs a query that catches a column
that disagrees with its payload. The query is `SELECT count(*) FROM cards WHERE cid IS NOT json_extract(payload,'$.cid')`.
It must be 0 after the migration AND after an ordinary write.

### 3.2 The seeding

`_add_card_ids` in `store/db.py` issues the ids inside `_upgrade`, and it can never refuse. A
migration that someone must remember to run does not happen. A refusal from `_ensure_schema`
over one unnameable card would take every route down. Shape 4 exists instead of a refusal.

```
under files.exclusive, stamp re-read inside the lock:
  A. ALTER TABLE cards ADD COLUMN cid TEXT, if absent
  B. read identifications.photo_sha256 for every key
  C. hash every photograph at its derived address, BEFORE the transaction
  D. BEGIN IMMEDIATE
  E. for each card in ascending (box, index):
       1. a cid is already present     -> keep it, issue nothing
       2. the photograph hashed in C   -> that digest          (source: disk)
       3. the record's photo_sha256    -> it                    (source: record)
       4. the identifications entry    -> it                    (source: identification)
       5. otherwise                    -> nophoto:<key>@<captured_at>
       then, while the cid is taken: n += 1, cid = <digest>-<n>, log duplicate_photograph
  F. UPDATE cards SET cid, payload
  G. CREATE UNIQUE INDEX cards_cid
  H. meta: card_ids_seeded, card_id_sources
  I. meta: schema = 4                     the LAST statement in the transaction
  J. COMMIT
  K. write the receipt (best effort)
```

**The ladder puts the bytes first, on purpose.** `identifications.photo_sha256` answers every
card with no I/O. Taking it first would bind every permanent name through the position-keyed
lookup that this design replaces, without reading the bytes it names. It is also stale in a real
window. `do_reshoot` writes new bytes and touches neither `cards` nor `identifications`. From a
re-shoot until the next paid press, that digest belongs to bytes that exist nowhere. Rungs 3 and
4 serve populations that may be empty. One is a reclaimed card. The other is a card with no
file between the shutter and the next press.

**Rung 1 makes a re-run a no-op.** The `-n` suffix depends on order, so a re-run must not
renumber one. Ascending `(box, index)` is the only stable order, because `created_at` is
optional. `verified_against_disk` counts the rungs that read bytes (rungs 2 and 3). It is named
so that a zero cannot read as "nothing needed hashing".

**The cost at the rig is one stall on the first read after the pull.** The seeding hashes every
photograph before the transaction, so the transaction writes rows only. The lock is held for
the whole seeding. `LOCK_TIMEOUT_SECONDS` is 30. The stall on the live server with a cold
cache: unmeasured.

### 3.3 The write-time refusal, in exactly one place

The refusal is `UnnamedCard`, in `record_capture`'s `existing is None` branch (0.6, hazard 2).
An in-memory `Inventory()` that never flushes never calls `_card_columns`. That is correct,
because an object that was never stored harmed nothing. A NULL that reaches disk anyway is
healed at the next open.

### 3.4 Who issues a cid

| where | the cid |
|---|---|
| `server/capture_server.do_capture` | `hashlib.sha256(blob).hexdigest()`, passed to `allocate_capture` beside `capture_id`. It is not a member of `CAPTURE_CLAIM_FIELDS`, because a claim survives a re-record and this must not |
| `server/capture_server.do_reshoot` | nothing. `cid` is untouched. The `reshot` history event carries the new `photo_sha256` |
| `Inventory.move_card` in `store/master.py` | the tombstone gets `moved:<cid>`, so `cards_cid` does not fire when the transplant keeps the original |
| `cli/cmd_identify.run` | `item.photo_sha256` |
| `cli/cmd_emit.run`, `run_merged` | the hash of the resolved photograph, else `nophoto:<key>@` and the report names the position |
| `scripts/demo-seed.build_store` | `sha256(demo-assets/photos/<row.photo>)`. It is deterministic, so an unchanged tree rebuilds byte for byte |

### 3.5 Previewable

`./banchi cards name` previews and writes nothing. It opens the store `sqlite3` read-only and
never calls `db.connect`. That function always runs `_ensure_schema`, so a preview through it
would migrate the store it is meant to preview. `scripts/cid-selftest.py` asserts this by behavior and
by source inspection. The preview prints the count per source. It lists every card that would land in shape 4 and
every duplicate that would get a suffix. It prints the receipt with its `reverse` sentence.
`cards name --write` runs the same step now.

### 3.6 Reversible

The receipt carries a `reverse` sentence that says how to undo the seeding. No command runs it.
`scripts/cid-selftest.py` proves the procedure. It drops `cards_cid` and `cards_cid_missing`,
clears `cid` in the column and the payload, deletes the two `meta` keys and stamps the schema
back. It reproduces `store/rows.py:payload_text` exactly, so every table comes back byte for
byte. The residue is an empty nullable column that no reader sees.

The reverse is for a store that an OLDER checkout will open. On a build that still declares
`Card.cid`, the next read sees the old stamp and names every card again. That is safe because a
digest gives the same ids again. A reverse and re-apply under an allocator would renumber the
store.

### 3.7 What proves no record-to-photograph link was lost

For every card, `sha256(<photograph>)` equals `cid` with any `-<n>` suffix stripped. This holds
unless the card carries a `photo_reclaimed_at`, or a `reshot` history line whose recorded digest equals
the file. `./banchi cards audit` (or `make cid-audit`) proves this on any copy with no
external state. Run right after the seeding it is close to a tautology. Its value is temporal:
it proves the link still holds after renumbers, moves, deletions and reclaims. The source
census in the receipt shows how many cards were named by something weaker than their own
bytes.

`make cid-audit` is not in `make check`. It reads the operator's photographs, and `make check`
answers from the tree alone. `make status` reports when it has never run against this store.

### 3.8 Killed with `-9` halfway

The store comes back unchanged. Every write is a row UPDATE or a CREATE INDEX inside one
`BEGIN IMMEDIATE ... COMMIT`, and the stamp is the last statement (`_upgrade`'s rule). SQLite
treats `ALTER TABLE` as transactional, so the column is gone too. There is no repair step and no
`--resume`. The next read runs it again. Killed after the commit and before the receipt: the
store is fully migrated and the receipt is missing. That is harmless, because `cards audit`
rebuilds what the receipt would say. Killed while another process holds the store: the loser
re-reads the stamp inside the lock and returns early. The OS releases a dead holder's flock.

**Never open the owner's live `inventory/store.sqlite` for writing to test this.** Use a
`.backup()` copy through a `mode=ro&immutable=1` connection. `make cid-selftest` builds its own
throwaway store under `BANCHI_HOME`.

## 4. What is deleted, and what merely moves

### Deleted

The `?card=<stamp>` query parameter on photograph URLs. It only made a slot URL name the right
picture. The by-card address, with `?v=`, does that work now. Everything else
that this design makes deletable waits for a later change, because deleting it here would
change the wire.

### One route added, none removed

`GET /photo/by-card/<cid>` (`do_photo_by_card`) needs no store read: the path is derived from
the name. Its ETag is the cid plus a hash of `?v=<capture id>`, which moves exactly when the
bytes do. A D26 re-shoot writes new bytes under the same cid, so the address alone cannot be
`immutable`. With `?v=` the response is `immutable`. Without it, the route reads and hashes the
file on each request and answers `no-cache`. `GET /photo/<box>/<index>` and `_PHOTO_RE` stay
(0.7). The old route now goes through the store, because a position is a lookup and not an
address.

The route matters at the rig. A URL that names a slot can serve the wrong card from the
browser's cache after a renumber. A wrong photograph can send the wrong card to a buyer. A URL
that names the photograph changes when the bytes change.

### What moves rather than dissolving

- **The position key stays** on the route regexes, as the primary key of `identifications` and
  `queues`, in `events.position` and as `cards.key`. Several places still hand-compose it as an
  f-string. Consolidating them is a prerequisite for any change that re-keys.
- **`identifications` gains nothing.** Re-keying the cache to `cid` is the highest-value change
  this seam unlocks, and it can spend money (see NEITHER in 0.9).
- **`queues` gains nothing.** Its `upsert` keys on the position. A cid beside it that does not
  move the upsert key would inherit the bug that D162 and D167 fixed. Each row also stores a
  `label`, a copy of the identity that can be wrong.
- **`events` gains nothing.** `events.position` stays ambiguous across every position key that
  has opened more than one occupancy. Replays disagree on where to bind those lines, so no
  correct algorithm is fixed yet.
- **`fulfilment` gains nothing.** Its repair is a payload rewrite, not a column.
- **`identify/sidecar.Capture` keeps its false claim.** Its key becomes the Batch API
  `custom_id`. A junk capture deleted mid-box would return paid answers keyed one card off.
  That has not fired.

## 5. Ordering rules

- **Two schema steps at one version in `_upgrade` are the one merge conflict that loses data.**
  The change that protects money takes the lower version. Claim a version at merge.
- **The forward-version guard lands alone**, as a one-commit change that alters no behavior on
  any store that exists.
- A signature change such as `photoUrl(box, index)` to `photoUrl(cid)` wants a quiet tree.
- An exact-match roster (the T7 command list) needs a recount from `entry.COMMANDS` at a
  conflict, never a side.

## 6. How it is proven

A count of rows that carry a cid cannot prove the migration ran right. Every row gets a value,
and a wrong seeding prints the same row. So each assertion counts positive work, and each
counter that could read "nothing was needed" is named so it cannot.

### 6.1 The states that a half-applied migration can leave

A migration half applied inside the transaction cannot exist (3.8). Three states can exist.

1. **Seeded but never verified against the bytes.** The receipt reports `verified_against_disk`.
2. **Seeded, then stripped by an older build.** The store heals it on the next open, loudly
   (0.6, hazard 3).
3. **The column and the payload disagree.** The query in 3.1 must return 0, after the migration
   and after an ordinary write.

### 6.2 `make cid-selftest`

It builds a throwaway store under `BANCHI_HOME` and proves each point below.

- The seeding names every card from its own bytes, and a re-run names nothing and changes no
  name.
- A stripped name heals byte for byte.
- The four column rosters agree.
- The naming writes nothing outside the database.
- Two cards with one photograph get a suffix. This arm never fired on real data, so it is
  provoked, not assumed.
- The moved tombstone names no photograph.
- A card with no photograph anywhere is named `nophoto:`, not NULL.
- A new card with no name is refused at its birth.
- The preview never migrates, by behavior and by source inspection.
- The reverse restores every table byte for byte.
- The forward-version guard refuses a newer store.
- A renumber moves no file.

### 6.3 `./banchi cards audit`

It is read-only. It has three verdicts, never two: `pass`, `fail` (a named mismatch, listed),
and `not known`. It prints `not known` when the `cid` column is absent, when any cid is NULL, or
when it finds no photographs. A check over zero rows would print "checked 0, mismatch 0" and
read as a pass. `not known` exits non-zero.

### 6.4 Harness placement

T7 holds the store's own seams: the forward-version guard, the roster reconciliation, the
column and payload query, the `moved:` prefix and the CLI roster. T3 needs `cid=` at
`harness/tests/t3_join_coverage._capture_at`, because it flushes. `make cid-selftest` is in
`make check`, and `make cid-audit` is not (3.7). A new self-test must appear in every list that
reconciles with `make check`: the `check:` and `ci-check:` recipes, `.PHONY`, `scripts/checks.py`
and the published lists. Report a mutation survivor. Do not explain it away.

### 6.5 The decision entries

D172 records the ruling and the four rejected options. D183 records the re-scope. A new
decision is written under a slug, and `make merge` claims its number (D140).

## 7. What is least sure

1. **The re-shoot is the seam in the thesis.** `cid` is frozen, so after a re-shoot it no
   longer matches the file. The audit needs an excused set. The `reshot` history line now
   carries the new `photo_sha256`. A `reshot` line without a digest is a named unprovable and
   exits non-zero. It is never an excuse. The correctness of the excused set rests on a field
   whose real-world firings are unmeasured.
2. **`do_remove_card` renames no file.** Photographs live under `cid`. It unlinks only the
   target's photo and sidecar.
3. **The three commitments that a filename-freezing change cannot all keep.** They are freezing
   the birth filename, leaving `next_index` unchanged and forbidding a cid-named file. This
   change avoids the trap because no filename is an index. A future change that freezes a
   filename at the birth address must first answer three questions. Where is that address
   stored? What does `photo_path` become? How is an index allocated for a filename?
4. **Whether the owner wants a 64-character id on the wire.** Only the owner can rule (0.8).
5. **The stall on the live capture server.** Unmeasured on the rig, with a cold cache and
   a feeder that emits a card every few hundred milliseconds. Measure it with `cards name` on
   a copy of the store.
6. **"100%" is not what this delivers.** It takes the box out of the card's NAME. It does not take it out of
   the KEY, the cache's key, the queues' key, `events.position`, the sidecar or the route
   regexes.
   Each of those becomes a mechanical follow-through over a name that cannot move.
