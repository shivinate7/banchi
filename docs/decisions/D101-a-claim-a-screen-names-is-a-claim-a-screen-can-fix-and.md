## D101 — A claim a screen names is a claim a screen can fix, and the derived tuple outran its decoder

**`product` gets two doors: the box-level claim editor on `#/inventory`, and an inline correction on `#/codes` beside the banner that names the problem.** Ruled by the owner 2026-09-05, on being shown that the claim was settable at capture and correctable nowhere.

### The defect was a screen sending the operator somewhere that could not help

`#/codes` draws a banner reading *"N held codes carry no product claim, so neither lane will take them"*, with a button labelled **Fix on Inventory** pointing at `#/inventory`. That editor had no product field. The button had been landing on a dead end since D70 added the claim on 2026-08-30.

This repo's hard rule is *"A route is not a feature. Nothing is built until it is reachable from a screen."* This is that rule failing in the direction it does not cover: the capability was reachable, the screen was built, the button existed — and the destination could not perform the act the source named. **A rule about reachability does not catch a screen that reaches the wrong place.**

### Why nobody saw it: the tuples were derived and the decoder was not

`master.CAPTURE_CLAIM_FIELDS` is the authority. `capture_server.PUT_FIELDS` is derived from it; `BOX_CLAIM_FIELDS` is derived from `PUT_FIELDS`. So when D70 declared `product` on `Card` and named it in `CAPTURE_CLAIM_FIELDS`, **both wire tuples grew on their own and the hand-written decode tables did not.**

`do_put_card`'s table got its branch the day the claim landed. `do_put_box_claims`'s did not, for six days, behind a comment reading *"The same decode table as `do_put_card`, phase for phase."* The consequence is the worst available shape for a bug: `_reject_unknown` accepted the key, the `any(field in payload ...)` guard passed it, `incoming` never received it, the apply loop moved nothing, and **the route answered `200` with `"applied": 0, "unchanged": N`** — which is the same sentence it says to a box that already carries the claim. A silent no-op that reads as agreement.

No check could have found it, because none sent the field: every `do_put_box_claims` call in `harness/tests/t7_store_and_seams.py` sent `set_hint`, `game` or `variant`.

### Both doors, and the argument for each

**The general door is `#/inventory`'s Manage box sheet**, because that is where every other claim is corrected and a box of code cards out of one sealed product is the normal case — one press for the drawer rather than one per card.

**The second door is `#/codes`, because that is where the operator is standing when they are told.** The banner is not a passive label; it names a specific set of held codes and says why neither lane will take them. Sending someone to another screen to act on a sentence they are reading here is the hop the first door already pays for, and paying it twice is what makes a warning something an operator learns to ignore.

**This is a deliberate exception to the one-door habit, and it is narrow.** `#/inventory` keeps the general editor; `#/codes` gets a correction scoped to the lane its banner describes. The rule this does not repeal is D31's — there is still exactly one owner-side view of stored cards, and the codes control edits a claim, never a position or a state.

### What is not built, on purpose

**The operator's `note` does not reach the model.** `misc` never joins (`pipeline/games.py`, `catalogued: False`), so a note can only improve a description nothing prices from. That stays out until there is a reader that pays for it.

**`cli/cmd_identify.py`'s hand-built `master.Card(...)` is still a fourth restatement of the claim vocabulary.** It is harmless on the re-record path, because `record_capture` skips falsy values — but the same function CREATES a card when the key is absent, and on that branch `rarity_claim` and `product` are both lost. Named here rather than fixed, because the fix is a constructor change with its own blast radius.

### How this is kept true

`harness/tests/t7_store_and_seams.py:check_box_claim_product` sends the claim through the box route, asserts the record moved, and asserts the vocabulary still refuses outside `codes/products.py`. Verified failing under the mutation that removes the decode branch: `applied` drops to `0` and the invalid product stops being refused.

**And the restatements are reconciled mechanically rather than by comment.** `make docs-audit`'s `claim decode` row AST-reads both decode tables in `server/capture_server.py` and asserts each set equals the wire names in `PUT_FIELDS`; `claim clients` reads `app/src/server.ts`'s payload assignments and `app/src/BoxOps.tsx`'s `ClaimPatch` members and reconciles those against the same tuple. Both are red against the tree as it stood on 2026-09-05, which is the only non-vacuity proof this repo accepts. The section of `docs/DEBTS.md` that called the client hops permanently unauditable — *"no Python constant reaches a `.tsx`"* — was a runtime argument standing in for an audit gap: `check_route_census` already reads `App.tsx` and reconciles it against a table.

**What would reopen this.** *A second game carrying products*, which would make `_optional_product`'s "not scoped to the game" comment wrong and put the vocabulary back behind the registry. *A third door* — if one appears, the one-door habit is worth restating rather than eroding one exception at a time.
