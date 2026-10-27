# D183 — Photos filed by name, not number

**A card's photograph is stored under the card's own name: `photos/<aa>/<cid>.jpg`.** `Box 3 · Section 2 · Card 17` is purely derived again. The owner ruled that the card-naming problem is a systems problem, not an outcome patch, and approved the rescope. D172 gave the card a name. This entry makes the name the filename of its bytes. That retires the work rather than defending against it.

### The systems problem D172 left standing

**`(box, index)` did three jobs: the card's identity, the filename of its photograph, and the address a human reads off a shelf.** D172 fixed the first and left the other two welded together. So every hazard in its own §7 survived. Measured on the owner's live store:

- **164 `moved` events** each paid a tombstone plus five hand-moved derived copies. The copies: the photograph renamed, the sidecar rewritten, and the review, parked and cache entries re-keyed by hand.
- Deleting one junk capture at index *k* in a box of *N* costs **N − k photograph renames and N − k rewritten sidecars**. On box 2 that is 537 of each, because the filename is the index.
- One remove followed by one capture composes a path a live card's photograph still occupies. `files.write_atomic` does no existence check. It **overwrites a photograph that cannot be re-taken**.
- A D26 re-shoot breaks the frozen digest match. The excuse for it had to come from `events`, the one table that cannot be trusted. **6,771 of 11,919 position-carrying events sit at a key that opened more than one occupancy.**
- **D36's `realign` exists to repair drift** between a run's remembered positions and the store's current ones. **701 of 3,728 run records bind by digest to a different position key than the one they name.**

Six symptoms, each with its own guard, is the wrong shape. They are one defect: the bytes were filed under a number that moves.

### The rule, and it is D145 one register down

**A number a person reads is never a key a machine uses.** D145 applies this to boxes: a drawer has a `bid` that is never reused, and the number on its front is a label. This entry applies it to cards, photographs and runs. `pipeline/join.py:Position` already computes the readable address. It stops being half-derived and half-stored in a filename.

### What follows, and the third one is what the change is worth

**A renumber is a no-op.** Photographs of cards behind a deleted one are not named after their indices, so nothing needs renaming. **A move is a field update**, because the path contains no box. **A capture cannot overwrite another capture's photograph, structurally, not by a guard.** `cards_cid` holds the name UNIQUE. The path is a pure function of it, so two cards cannot compose one path. That hazard is absent, not defended against.

**`realign`, `_photo_digests` and `refuse_reallocated` become unnecessary for every run written from here. They are kept anyway, live, behind the replay branch.** A cid cannot reach backwards into an immutable file written before it existed. 3,728 existing run records are read by `#/pricing?run=<n>` and by "Join again". Both re-read an old receipt against today's store. Dropping the code would give up the 701 re-bindings, which is the whole reason it stays. What the kept code gains is that `_photo_digests` stops reading 997 MB of photographs per box to build a digest-to-position map the store now holds as a column.

### The address is materialized on demand

**`identify` takes a directory, and the repo already built the answer.** `_scope_dir` exists because *"widening it to take a list of files would put a second input shape through `sidecar.scan`, which is the one function that decides what a capture is."* So the whole-box case becomes the case that mechanism was built for. It is a view of symlinks named `<idx:04d>.jpg` pointing at the content store. The **sidecar is materialized, not linked**, so it carries the card's current index. That retires the 537 sidecar rewrites. A derived sidecar cannot go stale, so nothing on disk needs correcting. `identify/sidecar.py:load` needs no change. Its resolution is per field, so a view's sidecar is read through the path it has always taken.

**The store lives outside `captures/`.** `_scopes_root`'s docstring gives the reason. `sidecar.scan` walks its root recursively and turns every photo-suffixed file into a paid Batch request. A content store under `captures/cards/` would be swept by any run pointed at the directory above it. **Every card in it would be billed twice.**

**`position_from_path` refuses a digest-shaped stem.** It takes the last run of digits in a stem as the index. A 64-hex digest is full of digits. `6b1cf2fd83713889` ends in `83713889`, so a cid-named photograph with no sidecar would have recovered **index 83713889**. That is a plausible, wrong position: this repo's signature defect in its purest form. It now yields `None`. The card goes to the review queue flagged `no_position`, the named, safe outcome the module's docstring promises.

### The move of 4.45 GB is verified per card

**D172's measurement is what makes this safe.** 2,535 of 2,535 stored digests equal the file on disk. That was re-confirmed over 4,445,351,065 bytes, with 0 mismatches and 0 duplicates. Every file therefore has an oracle before it moves.

Per card, independently: hash the legacy file. **Refuse that card by name** if it does not match its `cid`. Then `os.link` to the destination, and **re-hash the destination**. Only then unlink the source. **A hard link, not a rename, is the whole argument.** A rename is atomic and cheaper to reason about. It is also the one form where verification happens after the only other copy is gone. Between the link and the unlink there are two names for one inode. The digest is re-read from the new name before the old one is dropped. Killed anywhere, the bytes exist under at least one name, and a re-run finishes the job. **No state can stop it that a re-run does not complete. No state exists in which a photograph has no name.**

**It opens the store for writing at no point.** That is what makes it safe to stop at any moment. The read path prefers the new address and falls back to the legacy one until `meta.photos_relocated` is stamped. **Once stamped, the legacy address is never consulted.** So the fallback cannot become the thing that hides an unfinished move.

### Three hazards, decided

**The migration lock does not hold while the corpus is hashed.** D172 priced the seeding at 3.0 s, with the flock held throughout. Its §7 offered hashing outside the lock as a contingency. At the feeder's measured 623 ms cadence, a 3.0 s lock means captures arrive against `REQUEST_SLOTS = 4`. **A capture lost mid-feeder leaves a physical card in the drawer with no record, which renumbers every card behind it.** That loss is silent and physical. So the corpus is hashed before `files.exclusive`. Each file is **re-stat'ed inside** the lock. Any whose `(size, mtime_ns)` moved is re-hashed, and the count is reported as a positive `rehashed` counter. The relocation is a separate step for the same reason.

**`_card_columns` does not refuse.** D172's §3.3 put the refusal at the one chokepoint every card row passes through. That is the wrong place. D172's own §3.2 rejects that shape one layer up: *"`_ensure_schema` raising over one unnameable card would take every route and every command down, which is unacceptable."* It then accepts the shape one layer down without re-arguing. A refusal there is a 500 on `POST /capture` mid-sitting. That is the same physical loss, arriving through a guard meant to prevent a lesser one. The refusal moves to where a card is born: `record_capture`'s `existing is None` branch, the birth site all four writers reach. A missing name there is a programming error, not a data condition. The shutter cannot reach it, because `do_capture` has the bytes in RAM.

**A stripped cid is healed, loudly, not refused.** D172 made it a named refusal. Its text reads *"even though under a digest the re-issue would be correct."* Under a digest the re-issue is **byte-identical**, as its own probe measured. That property is the whole argument against an allocator. Refusing to use it in the one situation it was bought for gives it away. So a NULL cid on a stamped store is re-issued by the same ladder. It is loud in three places: `cards_reissued` in the receipt, a history event naming every key, and a line in `make status`. The probe is an index probe, not a scan. The index is partial (`WHERE cid IS NULL`), so it is empty on a healthy store and can run on every open. **Prevention stays at the open.** The forward-version guard runs once per process and is loud. It does not run once per capture.

### What it does not buy

**The box stops being a unit of work. It stays half of a readable address,** as was asked. It leaves the photograph's path and the run's re-binding. It remains in `cards.key`, the identification cache's key, the queues' key, `events.position` and the ten route regexes. Taking it out of those is not this change. Four follow-ons are unchanged, and none follows from this one. They are the batch `custom_id`, the `identifications` re-key with its ~$3.63 hazard, the order-ledger repair, and the position key itself.

**Two things are worse, and this entry says so.** D172's strongest property was that it *"performs zero filesystem renames, zero unlinks, and zero writes outside the database."* That is gone. **2,535 link-and-unlink pairs now run against an irreplaceable corpus.** That is why the step previews by default. Also, `photos` is a new top-level directory. A worktree can now create it. It is gitignored bare, with no trailing slash, per `.gitignore`'s opening rule and D47's receipt.

---
