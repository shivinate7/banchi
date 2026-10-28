# D36 — The store decides a card's slot

**A re-join of box 2 wrote all 47 queue entries one position off.** Every entry carried the right read with its neighbor's slot, photograph and label. On screen, `Wally's Compassion` sat over a photograph of an Inteleon. The queue was restored from a backup taken minutes earlier. It was caught before it was answered. Built immediately after D35, because applying D35 exposed it.

**Nothing about D35 caused it. Any re-join of that run would have done the same.**

**Each half is correct. The seam between them was not.** `cli/runs.py` makes a run an immutable input on purpose. It lets a Batch outlive the server that started it (D33), and it keeps the run an auditable record of what was submitted and billed. D10 ruling 1 lets a junk capture be deleted from the middle of a box. Every higher card then slides down one slot. The store remaps everything: records, photographs, sidecars and **both queue files**. A `renumbered` event maps each old index to its new one. What was wrong: the run's POSITIONS were then read as truth.

Box 2: card `2/7` was deleted and 537 cards shifted down one. The run directory was correctly unable to be rewritten, so it still described the box as it had been.

**The owner's reading is the basis of this design.** It is a better diagnosis than the three options offered. The owner's point: the store should have corrected all the other cards too. Those cards were never disconnected.

**So the run no longer owns the slot number.** It owns what the model read from a PHOTOGRAPH. The store owns which slot that photograph is in. `photo_sha256` joins the two. It is on every run record whose photograph could be read. It is the only binding that survives a renumber. A slot number is exactly what moves. A record whose photograph raised an `ImageError` carries `None`, the digest-less case below. `cli/resolve.py:realign` runs before anything reads a position from the payload. The run directory on disk is never touched.

**Measured before it was chosen.** Box 2's 543 photographs are 997 MB. They hash in **0.56s**, to 543 distinct digests with no collisions. Reading the photographs is affordable per join. Trusting the store's identification cache is worse. That cache is another derived copy. A future defect could leave it stale in the same way.

**Five outcomes, reasoned per box.** The per-box part matters. The first draft reasoned over the whole run and declared **all 53 of box 1's cards departed**. Box 1's photographs had been deleted from disk while its records lived on. That inverts the check. Absent photographs are no evidence of absent cards.

- **moved**: the digest is on disk at a different slot. Re-bound, and named in the report.
- **departed**: the digest is on no photograph in a box whose *other* photographs are present. The card has left, by deletion mid-box or retirement. It is skipped, and **named**. `CLAUDE.md` forbids dropping a card silently. It does not forbid dropping one.
- **ambiguous**: the digest is on two photographs. That is a question, not a slot. Guessing an identity is forbidden. Refuses the whole run.
- **collided**: two RECORDS carry one digest, so they re-bind to one slot. This is `ambiguous`'s missing twin. `ambiguous` checks the DISK for a digest that appears twice. Nothing checked the PAYLOAD. Two records on one key overwrote each other in the rebuilt payload. The measured case was two cards in and one out, with `departed` empty and nothing printed. The function written to prevent a silent drop was causing one. Refuses the whole run and names the contested slot.
- **unverified**: the box offers nothing to check against. It has no photographs on disk, no record with a digest, or no digest matching any photograph there. Its records pass through exactly as recorded. The report says the slots were **not** checked, so an unchecked box cannot read as a verified one. This case is worded "nothing to check against", not "no photographs". A box whose photographs were all REPLACED (D26's re-shoot writes new bytes at the same slot) matches none of the run's digests. Calling its cards departed would repeat the inversion above.

**A box whose number was deleted and reused after the run is refused outright.** `unverified` keeps its meaning. Box 1 was deleted with 53 Pokemon cards. Its number was later reused for 133 Riftbound cards, because `next_box_number` allocates the lowest free integer (D20 amended). The run `2026-08-22-box1-03` still describes the old drawer. `realign` never opened the store. None of the run's digests were among the new box's photographs, so it answered `unverified` and passed the keys through. Everything after it then read the CURRENT box's records at those keys: the `held.game` fallback, `answered`, `committed`, `box_views`. A refusal fired at last, with the message "this run holds 53 riftbound card(s) and no export covers that game" over a Pokemon run. By then it had sent the operator to edit live records that were never this run's.

The rule is one D56's `server/pipeline_routes.py:_box_name_for` has used since it was built. It withholds a box's NAME when the registry entry was made AFTER the run started and the box's cards came from somewhere else. The rule now lives in `store/master.py:box_disowns_run`. `Inventory.box_disowns_run` reads it off the store. `cli/resolve.py:refuse_reallocated` refuses on it before `_games_needed` or `load` reads a record. The photographs are deliberately not an input. `do_delete_box` deletes the cards with the entry, so a box `realign` can verify cannot satisfy the rule. The honest `unverified` case (photographs missing, box unchanged) fails the time test or the membership test, and passes through as above.

**A record with no digest is a fifth refusal, and it is not an outcome of a box.** `cli/cmd_identify.py` writes `photo_sha256` as `None` for any card whose photograph raised an `ImageError`. So a run written today can carry digest-less records. This is live, not a guard against old payloads. Such a record is harmless while nothing in its box has moved. It cannot be placed once something has, so it refuses only in the second case.

**A healthy run returns the identical payload object.** That keeps its join byte-for-byte unchanged. Gate B's box-1 run verifies this, and the diff is clean.

**What would reopen this: a second binding that outlives a renumber.** `capture_id` is on the card record but not on the run record. If it were carried into the run payload, it would be a cheaper key than hashing a gigabyte. Hashing could then become the fallback rather than the primary. That is a change to what `identify` writes, not to this entry.

---
