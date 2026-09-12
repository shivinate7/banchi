## D145 — A box has an index nobody sees, because the number on the drawer is a label and a label may be reused

**Settled 2026-09-11, on the owner's report and their ruling in the same message.** A box gains a `bid`: an integer allocated once at the drawer's creation, never reused, never displayed. The box NUMBER is unchanged in every respect, including that `next_box_number` goes on handing out the lowest free one. Records that outlive a box — a run, a buried card — bind to the id; every screen still says `Box 1`.

### The report, and the ruling

**The owner, verbatim:** *"im seeing that i deleted an old box 1, started writing into a new box (now new box 1) and if i go on say my runs tab it shows that i'd run a 'Box 1' run a long time ago etc. it's confusing."*

**And, in the same message:** *"box #s as indexes should be immutable so if i delete a box # that deleted box's index # is not deleted, like box # and index # should not be the same thing, a box needs an index # not visible anywhere in the app thats a true index rather than cheaply using boxes as an index."*

The second half is the design, and it is stated more precisely than a specification would have been: two jobs, one value doing both, and the fix is to separate them rather than to change how either behaves.

### This repo had already met this collision twice and fixed neither half of it

**D36 (amended) refuses to JOIN a run over a reallocated box**, and names the owner's own data as the case: box 1 held 53 Pokemon cards on 2026-08-22 and box 1 has held 133 Riftbound cards since 2026-08-29. **D56 withholds the box's NAME from such a run** on the same rule, `store/master.py:box_disowns_run`, shared between them so the screen and the command cannot decide one case two ways.

**So the store could already detect the collision, and what neither entry did was let a screen SAY anything about it.** D56's withholding is the reason the complaint reads the way it does: the old run drew `Box 1` rather than `Box 1 · RB Epics`, which is correct and is indistinguishable, on a screen, from an unnamed box. The operator sees a run over `Box 1` and a drawer called `Box 1` and there is no third thing on the page. Withholding a name is not a sentence; it is the absence of one.

**And both rules reason from the shape of the evidence, because that was all there was.** `box_disowns_run` requires two conditions — the registry entry is younger than the run, and the box's cards all came from elsewhere — each ruling out the other's false positive, and it abstains when it cannot tell. That is the correct rule to build out of timestamps and card sets, and it is an inference. With an id the same question is a lookup.

### What is separated, and what is emphatically not

**`Box.bid` is the true index.** Allocated by `Inventory.next_box_id` as `max(issued, every live bid) + 1`, against a high-water mark persisted in the `meta` table that has existed since D88 and that a deletion does not lower. This is **D10's rule for the card index inside a box**, applied to a box for the first time — and CLAUDE.md's sentence that `next_box_number` is *"deliberately NOT D10's high-water mark"* is still exactly right about the NUMBER. It needed one more sentence, not a correction: the number is not a high-water mark and the id is.

**`Box.box` is unchanged, and keeping it reusable is a requirement rather than an omission.** The owner did not ask for monotonic numbers and a physical drawer relabelled 1 really is box 1. D20's argument for the lowest free integer is untouched: the number names an object on a shelf, the operator no longer types it, and there is no gap for it to close wrongly. Making numbers monotonic would have "fixed" the complaint by changing what the operator reads off the drawer, and would have left every existing run mislabelled anyway.

**This is D58 one register up, and the vocabulary is deliberately D58's.** `Place.index` is the stored key and `Place.slot` is the number a person counts to; `Box.bid` is the key and `Box.box` is the number a person reads. Both pairs exist because a label a human maintains and a key a machine joins on are different jobs. The repo already had the word for this.

**Nothing in `app/` renders the id.** The owner said so twice. It is on the wire because the SERVER needs it to tell two drawers apart; what a screen draws is the ANSWER that produces.

### What the runs tab says now, and why that wording

**`Box 1 (deleted) · Pokemon shakedown`**, or `Box 1 (deleted)` where the drawer was never named or where the run is old enough that the server can tell THAT its drawer departed without being able to say WHICH.

**The number stays.** It is the run directory's own name, the directory the photographs are in, and what every refusal in `server/pipeline_routes.py` names — D56's argument for carrying both halves, unchanged. Removing it would cost the operator the thread back to all three.

**`(deleted)` rather than `(former)`, which the first draft used.** Both are short and neither is jargon, so the more specific one wins: "former" says this is not the current box 1 and leaves the reader to wonder what became of it, while "deleted" names the act the operator performed and remembers performing. `docs/DESIGN.md`'s register rule is sentences a person reads; the sentence here is *the box 1 I deleted*.

**The departed drawer's NAME is recovered, and that does not reopen D56.** D56 forbids writing a name into a run directory because a live name is editable and a copy goes stale the first time the drawer is renamed. A deleted drawer's last name cannot be edited — there is nothing left to edit — so it is a fact rather than a stale copy, and it is read at join time off the `box_deleted` history line rather than stored on the run. The id is what makes that join possible, and recording the ID on a run is likewise not a copy of an editable thing: an identity is fixed at creation.

### The two arms, and which one the owner's machine actually takes

**Where the run carries an id, the answer is a comparison and there is no third outcome.** Every run started after this lands takes this arm.

**Where it does not, the older rule decides, unchanged.** That is EVERY RUN ON THE OWNER'S MACHINE, including the one that produced the report, so it is the arm that had to keep working rather than a shim to be deleted later. It can say THAT the drawer departed and not WHICH, which is why a legacy run gets `(deleted)` with no name — and that is already the whole of what the complaint asked for.

**The arms are not combined, and the id wins outright where it exists.** The older rule abstains towards the box being the run's own, because it must; letting an abstention soften a fact would be a rule that gets less certain as it learns more.

### The migration

**Schema 1 to 2, under the store lock, additive, with a receipt in `inventory/migrations/box-ids.json`.** Every box gains an id in ascending box NUMBER — the only stable order available, since a legacy box's `created_at` is optional (`Inventory.parse`'s v1 backfill creates entries with none) and ordering on it would make the result depend on SQLite's row order. Which box gets id 3 does not matter; that one store always produces one answer does.

**Lossless, and the harness states it that way.** No column is dropped, no payload key is overwritten, no row is removed, so the reverse is stated in the receipt and is four statements. T7's legacy-import case now asserts "everything the file said, plus exactly these two facts" and names both — rather than being loosened to ignore unknown keys, which is what would have made that test stop being about losslessness.

**A store arriving from the legacy JSON files is numbered on the way in**, because the staging database is created fresh at the current version and so never passes through the upgrade step.

### What this does not do

**It does not renumber anything, and it closes no gap.** A deleted drawer's id is spent forever. `docs/map.py`'s culled step 12 is the same rule about a build-order id and D10 is the same rule about a card index: a reused identifier resurrects every reference to the thing that used to wear it, and nothing can detect that, because a stale id still resolves.

**It does not make the id an address.** No route takes one, no screen shows one, and the capture screen still finds a box by name (D20). Adding `/boxes/by-id/<n>` would make the id a second way to address a live box, which is the thing the owner's ruling says it must not be.

**It does not reach the position label.** `pipeline/join.py:Position` is untouched, `app/tests/fulfillment.spec.ts` floors it, and the Fulfiller walks a shelf where the number on the drawer is the only thing that helps him.

### What would reopen it

**A second drawer wearing one number at the same time.** Everything here assumes the number is unique among LIVE boxes and only ambiguous across time. If boxes ever became per-shelf or per-location — two `Box 1`s on two shelves — the id would be the right address for a route, and the ruling that it stays invisible would need re-asking.

**A run over more than one box.** `_run_box_id` reads one id out of a scope block that names one box, because D48 keeps a run to one box. A cart-shaped run would need a list, and `refuse_reallocated` already loops over boxes in a way that anticipates it.

