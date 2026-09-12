# The first photograph is the card's name (`cards.cid`)

**STATUS: RE-SCOPED 2026-09-12 ON THE OWNER'S APPROVAL, AND §0 IS THE CHANGE.** This file was
landed the same day as SPECIFIED, NOT BUILT, describing a `cid` column that arrives beside
`(box, index)` and then defends against that key's hazards. The owner read it and said
*"I think this is a systems problem rather than worrying about the outcome we need to solve —
can you think bigger?"*, and then, on the answer in §0, **"Yes rescope it, approved."** §0 is
therefore the governing section: **the photograph moves out of the address and is stored under
the card's name**, which is what turns most of §7's doubts into questions that cannot be asked.
Everything §0 supersedes is annotated in place and nothing is deleted — §1's identity, §2's
list of what stays, and §3's seeding are all still the design, and §3's measurements are still
the evidence.

**WHAT WAS SPECIFIED, NOT BUILT, IS NOW BUILT, AND §0.9 IS THE ROSTER.** The `cid` column, the
migration, the relocation, the audit, the two targets and the `cards` subcommand are in the
tree. What remains NEITHER is named there too, in the same words as before: the batch
`custom_id`, the `identifications` re-key, the order-ledger repair, and the position key
itself.

What was already real when this file landed is unchanged: every figure below was read from the
owner's live store or from a `.backup()` copy of it, and every mechanism was proved on a copy —
the migration, the reverse, the `-9` kill and the two probes all ran. This is the argument and
its receipts, landed so the next session finds them instead of re-deriving them (`CLAUDE.md`'s
working agreement: design work is repo work).

**THE DECIDING MEASUREMENT WAS RE-TAKEN ON 2026-09-12, AFTER THE RE-SCOPE, AND IT REPRODUCES.**
Beside §1's reading, not instead of it (`docs/specs/order-pipeline.md` §1's discipline): 2,535
cards, **2,535 of 2,535** digests equal the file on disk, 0 mismatches, 0 missing, 2,535
distinct digests over **4,445,351,065 bytes**, 0 duplicate groups, in **3.00 s** against §1's
2.68 s — the same corpus, a colder cache. `Card.photo` measures **1,993 absolute, 542 relative,
0 tail-drift**, exactly as §2 reports, and `photo_reclaimed_at` is set on **0** of 2,535. Two
figures did move and neither is load-bearing: **294** sold rather than 289, and **12,007**
events rather than 12,002 — a live store between two readings.

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

**THE NAMES HAVE THEIR PREFIXES BACK, BECAUSE THE THINGS EXIST.** This file carried a
note explaining that a target spelled `make <name>` or a subcommand spelled
`pkmnscan <name>` is reconciled against the Makefile and `cli/__main__.py` by
`make docs-audit`'s make targets and pkmnscan commands rows — both MECHANICAL — so
spelling an unbuilt one fails the commit, and the two targets and the subcommand were
therefore written bare until the implementation landed. It has. They are `make cid-selftest`,
`make cid-audit`, and `./pkmnscan cards name` / `audit` / `photos`.

**AND THE AUDIT DID NOT LAND WHERE THIS FILE PUT IT.** §6.3 and §6.5 planned a script under
`scripts/`, and it is a CLI SUBCOMMAND instead — `./pkmnscan cards audit`, with
`make cid-audit` as the one-word way to reach it. That is a real change of shape and it has a
reason: the audit needs the same read-only store opening, the same photograph resolution and
the same four value shapes the preview needs, and a script beside a subcommand that shared all
three would be a second reader of the layout. The allowlist line this file's own note pointed
at is deleted rather than left to go stale.

_Executable specification. Written 2026-09-12 against **main `df6ec79`** (`Merge pull request #309`), worktree clean at the same sha. Every figure below was read from the owner's live store opened `mode=ro&immutable=1` or from a `.backup()` copy under the session scratchpad. **The live store ends this session at `md5 b3373ed823a7b397054e9980f2ddcaa9`, 7,438,336 B, mtime `Sep 12 11:28`, schema 2, no `cid` column** — unchanged from before the survey. Every writable probe ran on a copy. Re-read before trusting any number here: three of the store survey's figures did not reproduce against this tree and two of mine will not reproduce against the next one._

This is the ninth PR and the one the plan's own section 7 excluded by name: *"taking the box out of `store/master.py:243 position_key`."* **It does not take it out.** It gives the card a name that is not its box, which is the mechanism that makes taking it out possible; the removal itself is a later PR and §4 says which parts and why they wait. The plan's own arithmetic was *"about 90%"*; this is the seam, measured, migrated and proved, and it is honest about which of the remaining 10% it buys today.

---

## 0 · THE RE-SCOPE — the photograph is stored under the card's name

### 0.1 · The systems problem: one string is doing three jobs

**`(box, index)` is simultaneously the card's IDENTITY — the store's primary key — the FILENAME
of its photograph, and the ADDRESS a human reads off a shelf.** Every hazard §7 names is
downstream of that one conflation, and the original scope answered each of them separately:

| the hazard | what it costs today | why |
|---|---|---|
| a D83 move | a tombstone plus five hand-moved derived copies, **164 times** | moving a card changes its identity |
| one junk capture deleted mid-box | **537 photograph renames and 537 rewritten sidecars** | the filename IS the index |
| remove-then-capture (§7 item 3) | **overwrites a photograph that cannot be re-taken** | `next_index` and a filename can compose the same path twice |
| a D26 re-shoot (§7 item 1) | the frozen digest stops matching, so the audit needs an excused set | the photograph is identified by where it sits |
| the excuse mechanism for it | rests on `events`, **the one table §4 spends a paragraph refusing to trust** | 6,771 of 11,919 position-carrying events sit at a key that opened more than one occupancy |
| D36's `realign` | **exists entirely** to repair drift between a run's remembered positions and the store's | 701 of 3,728 run records bind by digest to a different key than the one they name |

**Answering six symptoms separately is what the original scope did, and it is the wrong shape.**
`cards.cid` alone gives the card a name and then leaves the photograph filed under the address,
so the address is still load-bearing for the bytes — and every one of the six survives.

### 0.2 · The rule, in its general form

**A number a person reads is never a key a machine uses.**

D145 is that insight applied to boxes: a drawer has a `bid` that is never reused, and the number
printed on its front is a label. This is the same insight applied to **cards, photographs and
runs**. `Box 3 · Section 2 · Card 17` is an instruction to a hand at a drawer and it stays
exactly as it is — `pipeline/join.py:Position` already computes it, and it goes back to being
**purely derived** rather than half-derived and half-stored-in-a-filename.

### 0.3 · The layout: the photograph is named by the card

```
BEFORE   <home>/captures/cards/box3/0017.jpg        the address is the filename
         <home>/captures/cards/box3/0017.json       the sidecar beside it

AFTER    <home>/photos/6b/6b1cf2fd83713889….jpg     the card's own name is the filename
         <home>/photos/6b/6b1cf2fd83713889….json    the sidecar beside it
```

`store/photos.py` is the one module that composes that path and the only one permitted to.
Three properties follow, and the third is the one worth the PR:

1. **A renumber is a no-op.** `do_remove_card`'s rename loop has nothing to rename: the
   photographs of the cards behind the deleted one are not named after their indices.
2. **A move is a field update.** The path contains no box, so a card crossing drawers moves no
   bytes.
3. **A capture cannot overwrite another capture's photograph, structurally rather than by a
   guard.** Two cards cannot compose one path, because `cid` is UNIQUE on `cards` and the path
   is a pure function of it. §7 item 3's overwrite is not defended against — it is **absent**,
   and the three questions it says a future PR must answer in writing are answered here: the
   birth address is not stored because there is no birth address, `photo_path` becomes
   `photos.path(cid)`, and no index is allocated for a filename because no filename is an index.

**IT IS A SHARD, TWO HEX WIDE, AND THAT IS THE ONE NUMBER HERE THAT IS A GUESS.** 256 buckets
holds 2,535 photographs at ~10 per directory and 100,000 at ~390 — both comfortable on APFS.
Nothing measures the alternative because nothing in this pipeline lists that directory: every
read is a direct open by name.

**IT IS OUTSIDE `captures/`, AND `_scopes_root`'s DOCSTRING IS WHY.** That function already
argues this exact point for scope directories: *"`identify.sidecar.scan` walks its root
recursively and turns every photo-suffixed file into a capture and therefore a paid Batch
request."* A content-addressed store placed under `captures/cards/` would be swept by any run
pointed at the directory above it, and **every card in it would be submitted twice, and billed
twice.** So it is a sibling of `captures/`, `.scopes/`, `runs/` and `inventory/`, gitignored on
`inventory/`'s reason rather than a weaker one — it holds the real photographs.

**AND `position_from_path` IS TAUGHT TO REFUSE A NAME LIKE THAT, WHICH IS A REAL GUARD AND NOT
A TIDY-UP.** That function takes the LAST run of digits in a stem as the index, and a 64-hex
digest is full of digits: `6b1cf2fd83713889` ends in `83713889`, so a cid-named photograph whose
sidecar was missing would have recovered **index 83713889** — a plausible, wrong position, which
is this repo's signature defect in its purest form. A cid-shaped stem now yields `index = None`,
which routes the card to the review queue flagged `no_position`: the named, safe outcome the
module's own docstring promises. One mutation arm deletes that refusal.

### 0.4 · The address is materialized on demand, so `./pkmnscan identify <capture-dir>` is untouched

**The one thing a flat store breaks is that `identify` takes a DIRECTORY** — and the repo has
already argued, built and shipped the answer to exactly that. `server/pipeline_routes.py`'s
`_scope_dir` builds *"a directory of symlinks to the chosen cards, so `identify` can be pointed
at a subset"*, because *"widening it to take a list of files would put a second input shape
through `sidecar.scan`, which is the one function that decides what a capture is."*

So the whole-box case becomes the case that mechanism was built for. A **view** is built on
demand under `.scopes/`:

- the **photograph** is a symlink named `<idx:04d>.jpg`, pointing at `photos/<aa>/<cid>.jpg`;
- the **sidecar** is MATERIALIZED rather than linked, carrying the card's claims and its
  **current** index.

That second half is the part that pays. Today `do_remove_card` rewrites 537 sidecars to keep
their `index` true after a renumber. A view's sidecar is derived from the store at the moment of
the press, so it is **always** current and **nothing on disk has to be corrected**. The
canonical sidecar in `photos/` keeps the index the capture claimed, which is a historical fact
about a capture and never goes stale because nothing reads it as an address.

`identify/sidecar.py:load` needs no change for this and that is not luck: its resolution is
per-field — `resolved_index = sidecar_index if sidecar_index is not None else file_index` — so a
view's sidecar naming the current index is read as the sidecar's own claim, through the path it
has always taken. **No precedence is changed and `FROM_SIDECAR` still means what it meant.**

**THE VIEW IS THE `Position` FORMULA MADE INTO DIRECTORY ENTRIES, WHICH IS THE WHOLE RULE IN ONE
OBJECT**: the readable address exists, on demand, as a rendering — and is thrown away, like
every rendering, rather than stored where a write has to keep it true.

**MEASURED AGAINST A FULLY RELOCATED COPY OF THE OWNER'S STORE, because if this is wrong the
whole pipeline is wrong after the move and nothing else in the suite would say so.** Box 3, 887
cards: the view builds in **0.75 s** as 1,774 entries — a symlinked photograph and a
materialized sidecar each — and `identify.sidecar.scan` reads **887 captures in 0.16 s, all 887
from `FROM_SIDECAR`, 0 problems**, in ascending index order, with every photograph resolving
through its link. A ticked selection of 8 returns exactly the 8 indices asked for. The claims
travel: the first capture reads back `box=3 index=1 game=riftbound`. **Nothing in `identify/`
changed for any of it.**

### 0.5 · The relocation: resumable, and verified per card rather than trusted

**4.45 GB of photographs that cannot be re-taken move exactly once, and every single file is
checked against a digest that was already proven.** §1's measurement is what makes this
possible: 2,535 of 2,535 stored digests equal the file on disk, so each move has an oracle.

The relocation is **not** part of `_upgrade` and that is deliberate — see 0.6 hazard 1. It is
its own step, previewing by default, and per card it is:

```
for each card, independently, in ascending (box, index):
  1. destination already exists and hashes to `cid`   -> DONE, count `already`
  2. hash the legacy file at box<B>/<idx:04d>.jpg
       != cid            -> REFUSE THIS CARD BY NAME, move nothing, count `refused`
  3. os.link(legacy, destination)                      hard link: no bytes copied
  4. HASH THE DESTINATION AND REQUIRE IT EQUALS `cid`  -> else unlink dst, refuse, count
  5. unlink the legacy file                            count `moved`
  6. the sidecar, the same four steps, best effort      count `sidecars`
```

**A HARD LINK RATHER THAN A RENAME, AND THE REASON IS THE ONLY REASON THAT MATTERS HERE.** A
rename is atomic and cheaper to argue about, and it is also the one form where **the verification
happens after the only other copy is gone.** Steps 3 to 5 mean that from the moment the
destination exists until the moment the source is removed there are **two names for one inode**,
and the digest is re-read from the new name before the old one is dropped. Killed anywhere in
that window, the bytes exist under at least one name, and the next run resolves it: step 1 sees
a correct destination and step 5 removes the leftover source. **There is no state this can stop
in that a re-run does not finish**, and none in which a photograph exists under no name.

**It never opens the store for writing at all.** The relocation reads `cards` for `(cid, box,
index)` and touches the filesystem; there is nothing to commit, which is why it can be
interrupted freely and re-run as often as you like.

**A CARD IT REFUSES IS LEFT EXACTLY ALONE AND NAMED IN THE REPORT.** A legacy file whose bytes
do not hash to the card's `cid` is the one case where something is genuinely wrong — a re-shoot
whose identification was never re-read, most plausibly — and moving it would file it under a
name it does not have. It stays where it is, the read path still finds it, and the report says
which card and both digests.

**THE READ PATH PREFERS THE NEW ADDRESS AND FALLS BACK TO THE OLD ONE UNTIL THE STORE IS
STAMPED.** `meta.photos_relocated` is written only when a pass finds every card's photograph at
its name; until then `photos.find(card)` tries `photos/<aa>/<cid>.jpg` and then the legacy
address. **Once stamped, the legacy address is never consulted again**, so the fallback cannot
become the thing that hides an unfinished move — and `make status` reports the residue by count
for as long as one exists. That is the gate, and it is why this is a migration window rather
than a permanent second lookup.

### 0.6 · The three hazards, decided rather than inherited

**HAZARD 1 — the migration's store lock landing on the owner's live capture server mid-sitting.
DECIDED: hash outside the flock, re-stat inside it, and take the relocation out of the upgrade
entirely.** §3 priced the seeding at 3.0 s with the flock held for all of it, and §7 item 5
offered hashing-outside as a contingency while conceding it is correctness-neutral. At the
feeder's measured 623 ms cadence a 3.0 s lock is ~5 captures arriving against `REQUEST_SLOTS =
4`, and **a capture lost mid-feeder leaves a physical card in the drawer with no record, which
renumbers every card behind it** — the worst outcome in this pipeline, because it is silent and
it is physical. So:

- the corpus is hashed **before** `files.exclusive` is taken, recording `(size, mtime_ns)` per
  file;
- inside the lock every file is **re-stat'ed**, and any whose stat moved is **re-hashed** — the
  count is reported as `rehashed`, a positive counter, never an absence;
- the transaction is row writes only.

**The flock therefore holds for the row writes and the re-stat, not for the hashing.** The
window this opens is the one `do_reshoot` can write in, and re-stat closes it: the file cannot
change without its `mtime_ns` changing, and re-hashing is the answer rather than a refusal.
**The relocation is a separate step for the same reason** — it is filesystem work, it takes no
store write lock at all, and welding 2,535 link-verify-unlink triples into `_upgrade` would put
minutes of filesystem work where a read used to be.

**HAZARD 2 — a write-time refusal in `_card_columns` takes down every writer, including the
shutter. DECIDED: `_card_columns` DOES NOT REFUSE.** §3.3 put `MissingCardId` there because it
is the one chokepoint every card row passes through, and that is exactly why it is the wrong
place: **§3.2 rejects this shape one layer up** — *"`_ensure_schema` raising over one unnameable
card would take every route and every command down, which is unacceptable"* — **and then accepts
it one layer down without re-arguing it.** A refusal in `_card_columns` mid-feeder is a 500 on
`POST /capture`. The operator is watching a stand, not a network panel; the card is already in
the drawer; and the record is the thing that does not exist. That is the same physical loss
hazard 1 is about, arriving through a guard meant to prevent a lesser one.

What replaces it, and neither half is a refusal a capture can hit:

- **the refusal moves to where a card is BORN** — `record_capture`'s `existing is None` branch,
  which is the birth site all four writers reach (`allocate_capture` plus
  `cli/cmd_identify.py`, and `cli/cmd_emit.py` twice, the three §3.3 names). A cid missing
  *there* is a programming error in a caller, not a data condition, and it is raised before the
  shutter's row is built rather than at flush;
- **and the shutter cannot reach it**, because `do_capture` computes the digest from a blob
  already in RAM, so there is no path by which a capture arrives without a name.
- **a card row whose cid is NULL is HEALED, loudly, not refused** — see hazard 3.

**HAZARD 3 — a build that does not declare the column strips it silently on any ordinary write,
and ~30 worktrees on this machine are pre-guard builds. DECIDED: keep the self-heal, prove it,
and make it impossible to be quiet.** §6.1 item 2 made a stripped cid a **named refusal**
(`card_ids_stripped`) *"never a silent re-issue, even though under a digest the re-issue would be
correct."* That trades a self-healing store for a store that stops. Under a digest the re-issue
is not merely correct, it is **byte-identical** — §1's probe 2 measured it — which is the whole
argument against an allocator, and refusing to use the property in the one situation it was
bought for is giving it away.

So a NULL cid on a stamped store is repaired on the next open, by the same ladder, and the
repair is **loud in three places**: `cards_reissued` in the receipt, a `card_ids_reissued`
history event naming every key, and a line in `make status`. Never silent, and never a stop.

**The probe is cheap because the index is partial.** `CREATE INDEX cards_cid_missing ON
cards(key) WHERE cid IS NULL` makes "is anything unnamed?" an index probe that is empty on a
healthy store, so the check can run on every open without the scan `_ensure_schema`'s docstring
warns about.

**AND THE PREVENTION IS AT THE OPEN, NOT AT THE WRITE.** The forward-version guard (§3.1 commit
1) refuses to open a store stamped newer than the build knows. That is once per process, loud,
and before any card exists — the opposite end of the spectrum from a per-capture refusal. Within
one PR the guard and the bump merge together, so **every worktree that has not pulled is still a
stripping build until it does**, and the self-heal is what makes that survivable rather than a
data-loss event. It is stated here rather than scheduled away.

### 0.7 · What becomes unnecessary — and the one thing that is given up

**`realign`, `_photo_digests` and `refuse_reallocated` become unnecessary for every run written
after this, rather than demoted.** Their whole job is re-binding a run's remembered
`(box, index)` to the slot its `photo_sha256` sits at now (D36). Under this layout a run record's
`photo_sha256` **is the photograph's filename**: there is no binding to repair, because nothing
bound the bytes to a position in the first place.

**They are kept, live, and here is the thing that is given up if they are not.** §2 measured it
and the measurement is the argument: **13 run directories, 3,728 records, 701 of them binding by
digest to a different position key than the one they name**, plus 88 whose photograph is gone. A
cid cannot reach backwards into an immutable file written before it existed. `#/pricing?run=<n>`
and "Join again" both re-read an OLD receipt against TODAY's store, and for those 3,728 records
the repair layer is the only thing that makes the answer right.

**So they stay behind the replay branch, and the argument is that they are load-bearing for
history and dead for the future.** `cli/resolve.py:realign` gains a sentence saying so and
naming the condition under which it can go: when no run directory predating this change is still
readable. That is not a date anybody can name, so it is not scheduled.

**`GET /photo/<box>/<index>` also stays, on §4's measured reason** — `runs/<n>/pricing.json`
holds 3,629 position records across 12 immutable files, 0 of which carry a cid, and deleting the
slot route would leave those photographs unreachable from the screen that draws them.

### 0.8 · §7's seven doubts: what the re-scope makes moot, and what it makes worse

| § | the doubt | after the re-scope |
|---|---|---|
| **1** | the re-shoot breaks the frozen digest, so the audit needs an excused set drawn from a `reshot` event with **no digest at all**, and today's one case passes **by luck** | **MOOT, and by construction rather than by a better excuse.** The path is `photos/<aa>/<cid>.jpg` and `cid` is frozen, so a re-shoot writes the new bytes **at the card's own name**: the file the card points at is always the current photograph, and the audit asks a question that cannot go stale — *does the card's name resolve to a file, and does the `reshot` chain account for its digest?* The excused set survives, but it stops being the thing the design rests on, and §7 item 1's own preferred alternative — *"keeping the current photograph's digest on the record always"* — is what `reshot`'s new `photo_sha256` field is. |
| **2** | `do_remove_card`'s docstring and the photos survey **disagree** about whether a killed-and-retried renumber destroys 2 photographs, and nobody ran it | **MOOT, and the contradiction is retired rather than resolved.** The renumber has no rename loop to kill: the photographs are not named after the indices being shifted. Neither party to the disagreement is right or wrong any more, because the loop they disagreed about is gone. The measurement §7 asked for is no longer worth taking. |
| **3** | three commitments a filename-freezing PR cannot all keep, and the composition **overwrites a photograph that cannot be re-taken** | **MOOT, structurally.** The name is a sha256 that `cards_cid` holds UNIQUE, so two cards cannot compose one path. `next_index` is untouched and no longer reaches a filename. Its three questions are answered in 0.3. |
| **4** | whether the owner wants a 64-character id on the wire | **UNCHANGED, and it is still a question only the owner can answer.** The re-scope makes it slightly louder rather than quieter: the digest is now a **path on disk** as well as a route segment, so it is visible in a Finder window too. The full 64 is what is built, `cid[:12]` is what prose and screens use, and nothing types either. |
| **5** | the 3.0-second stall lands on the live capture server, unattended, measured on a warm cache | **BETTER, and it is now the design rather than a contingency.** Hashing is outside the flock and the lock holds for row writes and a re-stat. What the re-scope ADDS is the relocation's own filesystem work — which is why it is a separate, previewing, resumable step that takes no store write lock, instead of minutes of link-verify-unlink inside a read. |
| **6** | *"100%"* is not what this delivers | **BETTER, and still not 100%.** Four of the six rows in 0.1 are retired. The box is out of the photograph's path and out of the run's re-binding; it is still in `cards.key`, the cache's key, the queues' key, `events.position` and the ten route regexes. The honest figure is that the box stops being a unit of **work** and stays half of a **readable address** — which is what the owner asked for. |
| **7** | every number carries its read, and two will not reproduce | **UNCHANGED, and re-taken.** The re-read is in the header: the deciding measurement reproduces to the byte; 294 sold and 12,007 events are the two that moved. |

**AND TWO THINGS THE RE-SCOPE MAKES WORSE, SAID HERE RATHER THAN DISCOVERED:**

**A · 4.45 GB now moves, where the original scope moved nothing.** §3's single strongest
property was *"this PR performs zero filesystem renames, zero unlinks, and zero writes outside
the database"*, and that is gone. What replaces it is weaker in kind and stronger in degree: the
move is per-card resumable, every file is verified against a digest proved before the move
began, and no window exists in which a photograph has no name. **But it is 2,535 link-and-unlink
pairs against the owner's irreplaceable corpus, and the original had none.** It previews by
default for that reason.

**B · a new top-level directory is a new thing a worktree can create, and D47 is what that costs
when it is got wrong.** `photos` is gitignored bare, with no trailing slash, per `.gitignore`'s
own opening rule — a pattern ending in `/` matches directories only, and a worktree can put a
symlink at that name. `make ignore-check` is what reads it.

### 0.9 · BUILT, RECORDED, NEITHER

**BUILT** — reachable, exercised and asserted: `cards.cid` at **schema 4** (D174's
`submissions` took 3 while this was open, which is the merge conflict §5 predicted by name),
the seeding with its receipt, the forward-version guard, the four-roster reconciliation, the
partial-index self-heal, `store/photos.py`, the relocation with its preview, the view-directory
builder, the `GET /photo/by-card/<cid>` route and the client that addresses photographs through
it, `./pkmnscan cards name` / `audit` / `photos`, and `make cid-selftest` / `make cid-audit`.

**AND TWO DEFECTS THAT WERE FOUND RATHER THAN DESIGNED FOR, both in `store/db.py` and
neither in this file's plan.** `SqliteSource.upsert` was `INSERT OR REPLACE`, which resolves a
conflict in ANY constraint by DELETING the conflicting row — so a second card carrying a name
another card already held did not refuse, it silently deleted that other card's row and the
store came back one card short. It is `ON CONFLICT (<primary key>) DO UPDATE` now, which
resolves a collision on the row's own identity and lets every other constraint raise. That
mattered because `cards_cid` is load-bearing in an ARGUMENT rather than merely tidy: the claim
that two cards cannot compose one photograph's path rests entirely on two cards never holding
one name. **And fixing it exposed the second**: `flush_rows` wrote its row writes one statement at
a time, and a mid-box renumber re-keys rows — card 4 to index 3, card 5 to index 4 — so
part-way through that loop two rows transiently carry one name. The end state is fine and the
intermediate one is not, and a UNIQUE index in SQLite is IMMEDIATE with no deferred form. Every
touched key is cleared before any is written.

**EVERY GUARD HERE IS MUTATION-TESTED: 16 arms, 16 caught, 0 survived.** Three survived the
first pass and each was information rather than something to explain away. `column_names`
survived because **nothing in this repo reads `TableSpec.column_names` at all** — `grep -rn
"\.column_names"` returns nothing, `SqliteSource` takes its columns from `db.TABLES[table]`,
and that field is a declaration with no consumer on every `TableSpec` in the store. It has a
reader now. The relocation's two guards survived because they **mask each other**: the source
check refuses before linking and the destination re-hash catches after, and both end in the
same observable outcome, so no single-arm mutation could see either. The link tally
distinguishes the first; the second is provoked by making `os.link` land different bytes, which
is not a contrivance but the exact fault it is for.

**RECORDED** — this file, §0 in particular, and the decision entry. The shard width, the
`(size, mtime_ns)` re-stat and the refusal's new home are decisions with arguments here and
nowhere else.

**NEITHER** — unchanged from §4 and §7 item 6, and none of it is a follow-up to this: the batch
`custom_id` (`identify/sidecar.py:164`'s false claim), the `identifications` re-key and its
~$3.63 hazard, the `fulfilment` repair for 3 dangling references, and `position_key` itself.
`events` gains nothing, for §4's measured reason.

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

**`make cid-audit` is not in `make check`.** It reads the owner's 4.4 GB, and `make check` answers from the tree alone — `make lan-check`'s reason exactly. It is its own target, and `do_status` reports when it has never been run against this store.

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

**NEVER open the owner's live `inventory/store.sqlite` for writing.** Every figure above came from a `.backup()` through a `mode=ro&immutable=1` connection (0.014 s, 7,438,336 B) into the scratchpad, with `captures/` read through absolute paths and never written. `make cid-selftest` builds its own throwaway store under `PKMNSCAN_HOME`; the real store is migrated by the owner's own `git pull`, on the supervisor's first read, once.

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

### 6.2 · `make cid-selftest` — counts work, on a throwaway store under `PKMNSCAN_HOME`

- **the seeding hashes exactly `card_count` files** on a store with complete identifications — not "at least", not "zero is fine";
- **a re-run hashes 0 files and issues 0 ids**, and every cid is byte-identical to the first run's (the self-heal, measured at `3/17`);
- **the re-run after a strip issues exactly as many ids as were stripped**, and each equals what it was;
- **the migration performs 0 renames, 0 unlinks and 0 writes outside the database** — count the filesystem calls, do not assert about the outcome;
- **the duplicate arm fires deliberately**: write the same bytes twice through `do_capture` with two capture ids, assert `X` and `X-2`, the `duplicate_photograph` event naming both keys and both capture ids, and the receipt row. **This arm has never run in production — 0 duplicate digests among 2,535 real photographs and 0 among 132 demo pool files — so a green suite over zero firings proves nothing**, which is why it must be provoked rather than asserted about;
- **the re-shoot arm fires deliberately**: capture, re-shoot, audit, and assert the excuse came from the `reshot` line's **recorded digest matching the file** and not from the bare fact of a re-shoot. A `reshot` line with no digest is a NAMED UNPROVABLE that exits non-zero — never an excuse;
- **the preview never migrates**: run `cards name` against a store stamped 2 with no cid column and assert the column is still absent and the stamp still 2 afterwards. Assert by source inspection too that the preview path does not reach `db.connect`;
- **the reverse restores all nine tables byte-identically**, reproducing `payload_text`'s exact serialization (measured: 0.033 s, nine of nine);
- **the `-9` case**: fork, `BEGIN IMMEDIATE`, write half, `kill -9`, reopen, assert 2,535 cards, stamp 2, **no cid column**, and the `cards` table byte-identical to the baseline. Prove it by violating it, `make suite-lock-selftest`'s standard.

### 6.3 · `./pkmnscan cards audit` — and it has a NOT-KNOWN verdict

Read-only, re-runnable by anybody on any copy, **2.68 s over 4,445,351,065 bytes measured**. Three verdicts, never two: `pass` (every card's cid equals its photograph's digest, or is excused by a recorded digest), `fail` (a named mismatch, listed), and **`not known`** — which it prints when the `cid` column is absent, when any cid is NULL, or when it was pointed at no photographs. A "for every card, `sha256(file) == cid`" check over zero rows prints `checked 0, mismatch 0` and reads as a pass; that is the shape this repo has now hit nine times in twenty-four hours and it does not get a tenth.

`do_status` reports when `make cid-audit` has never been run against this store, and reports a `nophoto:` population above zero by name.

### 6.4 · Harness placement, and the mechanical rosters that must move with it

- **T7** takes the new arms — the store's own seams live there: the forward-version guard, the roster reconciliation, the strip refusal, the column/payload query, the move tombstone's `moved:` prefix, the CLI roster going nine → ten.
- **T3** needs `cid=` at `t3_join_coverage.py:220` (it flushes).
- `make cid-selftest` joins **`make check`**, and that turned out to be FIVE places rather than the three this line predicted: the `check:` recipe in the `Makefile` (29 targets now), `ci-check:` beside it — which NOTHING reconciles and which therefore drifts silently — the `.PHONY` line, `scripts/checks.py`'s `CHECKS` tuple (a full entry with `runs`, `asserts`, `needs`, `writes`, `commit_path`, `why_off_commit_path`, `gates`, `governed_by`, in recipe order), and every published list — `CLAUDE.md`'s and `make help`'s, the latter twice because the target needs its own help line as well as a place in the `make check` claim. That row exists because `make help` under-reported by five targets for months with nothing comparing the two, and **it refuses to go quiet**: a claim reworded past its pattern is reported as an unwatched sentence.
- `make cid-audit` does **not** join `make check` — §3.7.
- **Mutation arms, one per guard, and report a survivor rather than explaining it away** (PR #305's survivor revealed two dead exclusions carrying a comment that claimed otherwise): delete the forward-version comparison; delete one name from each of the three column rosters; delete `_card_columns`' refusal; delete rung E.1's `record.get("cid")`; delete the suffix loop; delete the `moved:` prefix; make the preview call `db.connect`; make `_add_card_ids` stamp without the source-count check. Re-run each against the whole nine-test harness, not just the new check, and **report equivalent mutants as equivalent instead of counting them as caught.**

### 6.5 · A decision entry, in the same session

`docs/decisions/D172-the-first-photograph-is-the-name.md`. **Never guess a D number** — write the heading as `## D-` followed by a lowercase hyphenated slug and let `make merge` claim it (D140); `make claim-stale` catches a claimed number that goes stale. One-line bold runs, `_add_box_ids`' receipt shape. It must carry: the 2,535/2,535 proof and the 2.68 s figure; the 701-of-3,728 run-record measurement as the production receipt that a content id beats a positional one; the two probes (the silent downgrade, the one-write strip) with their outputs; **the self-heal measurement, because it is the whole argument against an allocator**; the frozen-not-tracked distinction in one sentence; D89's narrowing with its population-of-zero measurement; the four shapes with their zero populations and the honest admission that three of them have never fired; and the reverse sentence. `python3 scripts/index-decisions.py --write` also appends to `docs/decisions/ORDER.json` — expected, and the manifest line is resolved by hand, main's numbers first and the slug last.

`docs/map.py` needs an entry for every new file under a mapped directory or the commit fails; the two that landed are `cli/cmd_cards.py` and `scripts/cid-selftest.py`, not the standalone audit script this line predicted.

---

## 7 · WHAT I AM LEAST SURE OF

**1 · The re-shoot is the seam in my own thesis and today it passes by luck.** `cid` is frozen, so after a D26 re-shoot it no longer matches the file — which means `cid-audit`, the thing this design is sold on, needs an excused set, and the excuse has to come from the `reshot` history line. **Measured: the one `reshot` event on this store (`2/96`, 2026-08-23T18:48:56) carries `capture_id` and `replaced_capture_id` and NO DIGEST AT ALL.** It passes the audit only because its identification was re-read afterwards. Commit 3 adds the digest to that line — bytes already in RAM, one field — but the excused set is **0 of 2,535** and its correctness from then on rests on a field with zero production history. **Settle it:** capture into a throwaway store, re-shoot, run `cards audit`, and assert the excuse was drawn from the recorded digest and not from a coincidence — then mutate the digest and see the audit go red. The alternative I did not fully evaluate is keeping the *current* photograph's digest on the record always, beside the frozen cid, which would make the audit exact with no excused set at all; D89's objection to that is weaker than it reads, because both writers (`do_capture`, `do_reshoot`) hold the bytes in RAM. **It is the first thing I would look at again and I am not confident enough to reopen D89 inside this PR.**

**2 · `do_remove_card`'s own docstring contradicts the photos survey, and I did not resolve it.** The survey reports that a kill-then-retry of the renumber destroys 2 photographs, reproduced on an APFS clone of real box 2. The function's docstring argues the opposite in detail — *"a rename RESUMES rather than repeating … the RECORD is what breaks the tie"* — and names the record as what distinguishes a card that never had a photograph from one whose photograph has already moved. **One of the two is wrong. I did not run it.** This PR does not touch the function, so nothing here depends on the answer, but **no later PR may delete that loop until it is reproduced on a copy**, because if the docstring is right the loop is the safe version and the deletion would be a regression sold as a fix. **Settle it:** clone real box 2 with `cp -Rc`, run `do_remove_card` against the copied store under `PKMNSCAN_HOME`, kill at mover 275, retry, and hash every surviving file against the pre-kill digests. `grep photo_missing harness/` returns **0**, so that arm and its refusal have never been tested either way.

**3 · The three commitments a filename-freezing PR cannot all keep, and I am naming them rather than scheduling them.** Freezing the photograph's filename at its birth address, leaving `next_index` unchanged, and forbidding a cid-named file are mutually inconsistent: `do_remove_card` **compacts** (its first rename consumes the target), `allocate_capture` assigns off the high-water mark, and `files.write_atomic` does no existence check — so one remove followed by one capture composes a path a live card's frozen address still names and **overwrites a photograph that cannot be re-taken**. Any future PR in that direction must answer three questions first, in writing: where is the birth address stored, what does `photo_path` become, and how is a never-reused index allocated. **Unmeasured on this tree** — I did not reproduce the overwrite, I read the three functions.

**4 · Whether the owner wants a 64-character id on the wire.** `GET /photo/by-card/<64 hex>` is 64 characters in every access-log line and network panel. Nobody types it, `#/inventory` still addresses cards by box and index, and the short form (`cid[:12]`, mono per D124) is what would appear in prose and on screen — the ETag already truncates to 32 hex at `capture_server.py:2834`, so there is precedent for shortening on the wire and an ambiguity waiting to happen if a short form ever becomes a lookup key. **I chose the full 64 without asking and it is a taste question I have no authority over. Settle it by asking.**

**5 · The 3.0-second stall lands on the owner's live capture server, unattended, and I did not measure it there.** The seeding runs inside `_upgrade` on the first `Store.read()` after the pull, under `files.exclusive`, and on this store that is 2.68 s of hashing plus 50 ms of row writes. `LOCK_TIMEOUT_SECONDS` is 30 so nothing times out, and `REQUEST_SLOTS = 4` means at most four requests queue behind it. **But `make launch-agent` keeps that process alive at login over the real store, and I measured the 3.0 s on a copy with a warm page cache, not on the rig mid-sitting with a feeder emitting a card every 623 ms.** A cold cache over 4.45 GB could be much worse. **Settle it:** `cards name` on a copy with the page cache dropped, and — if it is bad — hash outside the flock and re-verify the digests inside it, which is a correctness-neutral reordering because the file cannot move while the lock is held.

**6 · "100%" is not what this delivers, and the plan should stop saying it.** This takes the box out of the card's NAME. It does not take it out of the card's KEY, the cache's key, the queues' key, `events.position`, the photo path, the sidecar, or the ten route regexes. Two of the four things the plan's excluded sentence named are still paid in full after this merges: the move is still a tombstone plus five hand-moved copies, and the renumber is still 1,608 filesystem operations. What changes is that every one of those becomes a mechanical follow-through over a name that cannot move, instead of a re-key nobody can safely attempt. **Call it the seam, priced and proved, and name the four follow-on PRs** — the batch `custom_id`, the `identifications` re-key, the `fulfilment` repair, and the key itself.

**7 · Every number here carries the read that produced it, and two of mine will not reproduce.** Main at **`df6ec79`**, store **`md5 b3373ed823a7b397054e9980f2ddcaa9`**, 2026-09-12. Three of the store survey's figures measure clean on this tree — the 536 drifted `photo` paths are **0**, the 2,534-of-2,535 derived-address agreement is **2,535**, the 45 drifted parked-queue paths are **0** — against a tree roughly 49 PRs further on. **Do not build a guard against a defect that is no longer there, and do not read my 2,535/2,535 as permanent.** Run `cards name` as a read-only preview before trusting a single figure in §3.