# D145 — Box bid is a hidden identity

A box gains a `bid`. It is an integer allocated once at the drawer's creation, never reused, and never displayed. The box NUMBER does not change in any respect. That includes `next_box_number`, which still hands out the lowest free number. Records that outlive a box (a run, a buried card) bind to the id. Every screen still says `Box 1`.

### The report, and the ruling

The owner reported that a deleted box 1, followed by a new box 1, made old runs read as a "Box 1" run from long ago. The owner ruled that box numbers used as indexes must be immutable. A deleted box's index must not be reused. A box needs an index that no screen shows, a true index rather than the box number used as one.

The ruling names two jobs and one value that does both. The fix separates the jobs. It does not change how either one works.

### This repo had already met this collision twice and fixed neither half

**D36 (amended) refuses to JOIN a run over a reallocated box.** It names the owner's own data as the case. Box 1 held 53 Pokemon cards earlier. It then held 133 Riftbound cards. **D56 withholds the box's NAME from such a run** under the same rule. The rule is `store/master.py:box_disowns_run`. Both the screen and the command call it, so they cannot decide one case two ways.

**The store could already detect the collision. No entry let a screen say so.** D56's withholding is why the complaint reads as it does. The old run drew `Box 1` rather than `Box 1 · RB Epics`. That is correct, and on a screen it looks the same as an unnamed box. The operator sees a run over `Box 1` and a drawer called `Box 1`. The page has no third thing. Withholding a name is not a sentence. It is the absence of one.

**Both rules reason from the shape of the evidence.** `box_disowns_run` needs two conditions. The registry entry must be younger than the run. The box's cards must all come from elsewhere. Each condition rules out the other's false positive, and the rule abstains when it cannot tell. That is the right rule to build from timestamps and card sets, and it is an inference. With an id, the same question is a lookup.

### What is separated, and what is not

**`Box.bid` is the true index.** `Inventory.next_box_id` allocates it as `max(issued, every live bid) + 1`. It runs against a high-water mark stored in the `meta` table. That table has existed since D88. A deletion does not lower the mark. This is **D10's rule for the card index inside a box**, applied to a box for the first time. CLAUDE.md says `next_box_number` is "deliberately NOT D10's high-water mark". That stays true for the NUMBER. The entry needed one more sentence: the number is not a high-water mark, and the id is.

**`Box.box` does not change, and keeping it reusable is required.** The owner did not ask for monotonic numbers. A physical drawer relabelled 1 really is box 1. D20's argument for the lowest free integer still holds. The number names an object on a shelf. The operator no longer types it, so there is no gap for it to close wrongly. Monotonic numbers would have fixed the complaint. They would also have changed what the operator reads off the drawer, and every existing run would still be mislabelled.

**This is D58 one level up, and it uses D58's vocabulary.** `Place.index` is the stored key. `Place.slot` is the number a person counts to. `Box.bid` is the key. `Box.box` is the number a person reads. Both pairs exist because a label a human maintains and a key a machine joins on are different jobs.

**Nothing in `app/` renders the id.** The owner said so twice. The id is on the wire because the SERVER needs it to tell two drawers apart. A screen draws the answer the id produces.

### What the runs tab says, and why that wording

**`Box 1 (deleted) · Pokemon shakedown`**, or `Box 1 (deleted)`. It is `Box 1 (deleted)` when the drawer was never named. It is also `Box 1 (deleted)` when the run is old enough that the server can tell THAT its drawer departed, but not WHICH.

**The number stays.** It is the run directory's own name, and the photographs are in that directory. Every refusal in `server/pipeline_routes.py` names it. D56's argument for carrying both halves still holds. Removing the number would cost the operator the thread back to all three.

**`(deleted)`, not `(former)`, which the first draft used.** Both are short, and neither is jargon. "Former" leaves the reader to wonder what became of the box. "Deleted" names the act the operator performed and remembers performing. `docs/DESIGN.md`'s register rule asks for sentences a person reads. The sentence here is the box 1 I deleted.

**The departed drawer's NAME is recovered, and D56 still holds.** D56 forbids writing a name into a run directory. A live name can be edited, and a copy goes stale when the drawer is renamed. A deleted drawer's last name cannot be edited, because nothing is left to edit. So it is a fact, not a stale copy. The name is read at join time from the `box_deleted` history line. It is not stored on the run. The id makes that join possible. Recording the id on a run is not a copy of an editable thing. An identity is fixed at creation.

### The two arms

**Where the run carries an id, the answer is a comparison, with no third outcome.** Every run started after this change takes this arm.

**Where it does not, the older rule decides, unchanged.** That is every run on the owner's machine, including the run that produced the report. So it is the arm that must keep working. It is not a shim to remove later. It can say THAT the drawer departed, but not WHICH. A legacy run therefore gets `(deleted)` with no name. That is already all the complaint asked for.

**The arms are not combined. The id wins outright where it exists.** The older rule abstains toward the box being the run's own. It must abstain, because it cannot tell. Letting an abstention soften a fact would make a rule that grows less certain as it learns more.

### The migration

**Schema 1 to 2 runs under the store lock. It is additive and writes a receipt to `inventory/migrations/box-ids.json`.** Every box gains an id in ascending box NUMBER. That is the only stable order available. A legacy box's `created_at` is optional, because `Inventory.parse`'s v1 backfill creates entries with none. Ordering by it would make the result depend on SQLite's row order. Which box gets id 3 does not matter. What matters is that one store always produces one answer.

**Lossless, and the harness says so.** No column is dropped, no payload key is overwritten, and no row is removed. The receipt states the reverse in four statements. T7's legacy-import case asserts "everything the file said, plus exactly these two facts", and names both facts. The test was not loosened to ignore unknown keys, because that would stop it testing losslessness.

**A store loaded from the legacy JSON files is numbered on the way in.** The staging database is created fresh at the current version. It never passes through the upgrade step.

### What this does not do

**It does not renumber anything, and it closes no gap.** A deleted drawer's id is spent forever. `docs/map.py`'s culled step 12 follows the same rule for a build-order id. D10 follows it for a card index. A reused identifier revives every reference to the thing that used to wear it. Nothing can detect that, because a stale id still resolves.

**It does not make the id an address.** No route takes one, no screen shows one, and the capture screen still finds a box by name (D20). Adding `/boxes/by-id/<n>` would make the id a second way to address a live box. The owner's ruling says it must not be that.

**It does not reach the position label.** `pipeline/join.py:Position` is untouched. `app/tests/fulfillment.spec.ts` floors it. The Fulfiller walks a shelf, where the number on the drawer is the only thing that helps him.

### What would reopen it

**Two drawers wearing one number at the same time.** The design assumes that the number is unique among LIVE boxes and ambiguous only across time. If boxes became per-shelf or per-location, the id would be the right address for a route. Two `Box 1`s on two shelves is one such case. The ruling that the id stays invisible would then need to be asked again.

**A run over more than one box.** `_run_box_id` reads one id from a scope block that names one box, because D180 keeps a run to one box. A cart-shaped run would need a list. `refuse_reallocated` already loops over boxes in a way that anticipates it.

A run binds to the box's bid. A reused number is refused by comparing ids, never timestamps.
