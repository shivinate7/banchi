## D183 — A number a person reads is never a key a machine uses, so the photograph is stored under the card's name and the address is derived

**A card's photograph is stored under the card's own name — `photos/<aa>/<cid>.jpg` — and `Box 3 · Section 2 · Card 17` goes back to being purely derived.** The owner's instruction, 2026-09-12, on reading D172's spec: *"I think this is a systems problem rather than worrying about the outcome we need to solve — can you think bigger?"* and then, on this answer, **"Yes rescope it, approved."** D172 gave the card a name; this says the name is what the bytes are filed under, which is the half that retires the work rather than defending against it.

### The systems problem D172 left standing

**`(box, index)` was doing three jobs at once: the card's IDENTITY, the FILENAME of its photograph, and the ADDRESS a human reads off a shelf.** D172 fixed the first and left the other two welded together, so every hazard its own §7 names survived it. Measured, all of it, on the owner's live store:

- **164 `moved` events** have each paid a tombstone plus five hand-moved derived copies — the photograph renamed, the sidecar rewritten, and the review, parked and cache entries re-keyed by hand.
- Deleting one junk capture at index *k* in a box of *N* costs **N − k photograph renames and N − k rewritten sidecars** — 537 of each on box 2 — because the filename IS the index.
- One remove followed by one capture composes a path a live card's photograph still occupies, and `files.write_atomic` does no existence check, so it **overwrites a photograph that cannot be re-taken**.
- A D26 re-shoot breaks the frozen digest match, and the excuse for it had to come from `events` — the one table that cannot be trusted, because **6,771 of 11,919 position-carrying events sit at a key that opened more than one occupancy**.
- **D36's `realign` exists entirely** to repair drift between a run's remembered positions and the store's current ones: **701 of 3,728 run records bind by digest to a different position key than the one they name.**

**Six symptoms, each with its own guard, is the wrong shape.** They are one defect: the bytes were filed under a number that moves.

### The rule, and it is D145 one register down

**A number a person reads is never a key a machine uses.** D145 is this applied to boxes — a drawer has a `bid` that is never reused and the number on its front is a label. This is the same thing applied to cards, photographs and runs. `pipeline/join.py:Position` already computes the readable address; it stops being half-derived and half-stored-in-a-filename.

### What follows, and the third one is what the change is worth

**A renumber is a no-op.** The photographs of the cards behind a deleted one are not named after their indices, so there is nothing to rename. **A move is a field update**, because the path contains no box. **And a capture cannot overwrite another capture's photograph — structurally, not by a guard**: `cards_cid` holds the name UNIQUE and the path is a pure function of it, so two cards cannot compose one path. That hazard is not defended against; it is absent.

**`realign`, `_photo_digests` and `refuse_reallocated` become unnecessary for every run written from here, and they are KEPT ANYWAY, live, behind the replay branch.** A cid cannot reach backwards into an immutable file written before it existed, and 3,728 existing run records are read by `#/pricing?run=<n>` and by "Join again" — both of which re-read an OLD receipt against TODAY's store. What is given up if they go is those 701 re-bindings, and that is the whole reason they stay. What they gain is that `_photo_digests` stops reading 997 MB of photographs per box to build a digest-to-position map the store now holds as a column.

### The address is materialized on demand

**The one contract a flat store breaks is that `identify` takes a DIRECTORY, and this repo already argued, built and shipped the answer.** `_scope_dir` exists because *"widening it to take a list of files would put a second input shape through `sidecar.scan`, which is the one function that decides what a capture is."* So the whole-box case becomes the case that mechanism was built for: a view of symlinks named `<idx:04d>.jpg` pointing at the content store, with the **sidecar materialized rather than linked** so it carries the card's CURRENT index. That is what retires the 537 sidecar rewrites — a derived sidecar cannot go stale, so nothing on disk has to be corrected. `identify/sidecar.py:load` needs no change, and that is not luck: its resolution is per-field, so a view's sidecar is read through the path it has always taken.

**The store lives OUTSIDE `captures/`, and `_scopes_root`'s own docstring is the reason**: `sidecar.scan` walks its root recursively and turns every photo-suffixed file into a paid Batch request, so a content store under `captures/cards/` would be swept by any run pointed at the directory above it and **every card in it would be billed twice**.

**And `position_from_path` is taught to refuse a digest-shaped stem.** It takes the last run of digits in a stem as the index, and a 64-hex digest is full of digits — `6b1cf2fd83713889` ends in `83713889`, so a cid-named photograph with no sidecar would have recovered **index 83713889**: a plausible, wrong position, this repo's signature defect in its purest form. It yields `None` now, which routes the card to the review queue flagged `no_position` — the named, safe outcome that module's docstring promises.

### The move of 4.45 GB is verified per card, never trusted

**D172's measurement is what makes this possible and it is the only reason this is safe**: 2,535 of 2,535 stored digests equal the file on disk, re-confirmed 2026-09-12 over 4,445,351,065 bytes with 0 mismatches and 0 duplicates. Every file therefore has an oracle before it moves.

Per card, independently: hash the legacy file and **refuse that card by name** if it does not match its `cid`; `os.link` to the destination; **re-hash the destination**; only then unlink the source. **A hard link rather than a rename, and that is the whole argument** — a rename is atomic and cheaper to reason about, and it is also the one form where the verification happens after the only other copy is gone. Between the link and the unlink there are two names for one inode, and the digest is re-read from the new name before the old one is dropped. Killed anywhere, the bytes exist under at least one name and a re-run finishes it. **There is no state this can stop in that a re-run does not complete, and none in which a photograph exists under no name.**

**It opens the store for writing at no point**, which is what makes it safe to stop at any moment. The read path prefers the new address and falls back to the legacy one until `meta.photos_relocated` is stamped; **once stamped the legacy address is never consulted**, so the fallback cannot become the thing that hides an unfinished move.

### Three hazards, decided rather than inherited

**The migration's lock does not hold while the corpus is hashed.** D172 priced the seeding at 3.0 s with the flock held throughout, and its §7 offered hashing-outside as a contingency. At the feeder's measured 623 ms cadence a 3.0 s lock is captures arriving against `REQUEST_SLOTS = 4`, and **a capture lost mid-feeder leaves a physical card in the drawer with no record, which renumbers every card behind it** — silent, and physical. So the corpus is hashed before `files.exclusive`, every file is **re-stat'ed inside** the lock and any whose `(size, mtime_ns)` moved is re-hashed, and the count is reported as a positive `rehashed` counter. The relocation is a separate step for the same reason.

**`_card_columns` DOES NOT REFUSE.** D172's §3.3 put the refusal at the one chokepoint every card row passes through, which is exactly why it is the wrong place: **its own §3.2 rejects that shape one layer up** — *"`_ensure_schema` raising over one unnameable card would take every route and every command down, which is unacceptable"* — **and then accepts it one layer down without re-arguing.** A refusal there is a 500 on `POST /capture` mid-sitting, which is the same physical loss arriving through a guard meant to prevent a lesser one. The refusal moves to where a card is BORN — `record_capture`'s `existing is None` branch, the birth site all four writers reach — where a missing name is a programming error and not a data condition, and the shutter cannot reach it at all because `do_capture` has the bytes in RAM.

**A stripped cid is HEALED, loudly, not refused.** D172 made it a named refusal *"even though under a digest the re-issue would be correct."* Under a digest the re-issue is **byte-identical** — its own probe measured it — and that property is the entire argument against an allocator; refusing to use it in the one situation it was bought for is giving it away. So a NULL cid on a stamped store is re-issued by the same ladder, and it is loud in three places: `cards_reissued` in the receipt, a history event naming every key, and a line in `make status`. The probe is an index probe rather than a scan, because the index is partial — `WHERE cid IS NULL` — so it is empty on a healthy store and can run on every open. **The prevention stays at the OPEN**, in the forward-version guard, which is once per process and loud, rather than once per capture.

### What it does not buy

**The box stops being a unit of WORK and stays half of a readable ADDRESS, which is what was asked for.** It is out of the photograph's path and out of the run's re-binding. It is still in `cards.key`, the identification cache's key, the queues' key, `events.position` and the ten route regexes, and taking it out of those is not this. Four follow-ons are unchanged and none is a follow-up to this one: the batch `custom_id`, the `identifications` re-key with its ~$3.63 hazard, the order-ledger repair, and the position key itself.

**And two things are worse, said here rather than discovered.** D172's single strongest property was that it *"performs zero filesystem renames, zero unlinks, and zero writes outside the database"*, and that is gone: **2,535 link-and-unlink pairs now run against an irreplaceable corpus**, which is why the step previews by default. And `photos` is a new top-level directory, which is a new thing a worktree can create — gitignored bare, no trailing slash, per `.gitignore`'s own opening rule and D47's receipt.

---
