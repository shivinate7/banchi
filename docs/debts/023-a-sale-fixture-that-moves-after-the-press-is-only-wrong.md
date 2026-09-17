## 23 — A sale fixture that moves after the press is only wrong sometimes, so no check can flag it

**Measured 2026-09-11, sweeping the eight sites left by `inventory.spec.ts:5074`'s fix.** A case
in `app/tests/inventory.spec.ts` that mutates its store on the line AFTER a press is racing the
browser: `click()` resolves when the click is DISPATCHED, and `Inventory.tsx:doSell` awaits the
sale and then bumps `reloads`. When that `GET /inventory` is served first, the stub answers with
the card still on hand and nothing re-reads again, so the assertion retries a STABLE wrong answer
until it times out. 5074 lost that race on CI four runs in five while passing on a Mac every time.

**The shape alone does not say whether a case is wrong**, which is the whole of this entry. Three
of the seven probed cases were red on demand — they read `data-gone`, a neighbour's landmark, or
the row after an UNDO, all recomputed by the server. The other four were green with a 300ms wait
wedged into the same gap, because `doSell` adds the copy to `sold` BEFORE it bumps `reloads`, on
the success path and on `already_sold`: the receipt, the row's `Undo`, the state pill and the wire
log are answered by that optimistic overlay whatever the re-read says. Those four cases' subject
IS the overlay.

**So a check that flagged every mutation after a click would flag the four that are correct**, and
one that tried to tell them apart would have to know which selectors a case's assertions resolve
to through the product's own state — which is the test's meaning, not its shape. That is why there
is no row for this in `make docs-audit` and no lint rule in `app/eslint.config.js`. The substitute
is that the rule is written where a new sale case gets written: `sellableStore()`'s comment carries
both halves and the measurement, and `movesOnSale` carries the mechanism.

**THE OBVIOUS REPAIR IS WORSE THAN THE DEBT, which is why it is recorded rather than done.**
Freezing the fixture so the racy form cannot be written — routing every move through
`movesOnSale` — would quietly degrade those same four cases. Order the mutation into the sale
handler and the re-read comes back SOLD, so the server agrees with the overlay, and a case whose
whole subject is the overlay answering WHILE the server still disagrees has been weakened into
proving nothing. It would fail no test while removing what four tests are for.

**The way out is to make the intent DECLARED rather than inferred**, which is this repo's move
everywhere else it has faced an un-inferable rule — `chrome()`'s named strips, `App.tsx`'s
`OFF_NAV`, COLUMN-BLIND in `docs/DESIGN.md`. The four are not cases that happen not to race; they
are cases that REQUIRE the re-read to disagree with the overlay. Give them a way to say so — a
named helper beside `sellableStore()`, or an option on `open()` — and the rule becomes decidable
without reading assertions: a post-click fixture mutation is a defect in any case that did not opt
in, and the declared contract in one that did. A new sale case then either routes through
`movesOnSale` or declares the stale-store contract, and a bare `cards[...] =` after a click has no
home.

**THE DECLARATION HAS TO NAME A PROPERTY, NOT BE A FLAG.** `skipMutationCheck` is a spelling
somebody copies onto a fifth case that does not mean it, and the opt-out list then stops being a
list and becomes a habit. *This case requires the re-read to disagree with the overlay* is a claim
a reader can check against `doSell` — and a case that cannot say that sentence truthfully is a
case that should have been converted. Each of the four states what it is FOR, or the mechanism has
bought nothing.

Not built here: it is new surface area across seven cases plus a checker, and it wants its
own argument rather than being smuggled into a CI repair.

**What finds it meanwhile is a probe, not a guard.** Inserting `await page.waitForTimeout(300)`
between a click and its mutation turns the latent dependency into a deterministic red, and
inserting one after EVERY click in a converted case proves the dependency is gone rather than
re-hidden. Neither is ever committed. A session touching these cases should run both.

**The number may move, and nothing allocates it.** The merge-time id claim being built for
decisions, the code-card C entries and the build order does not reach this file's sections, and it
had not landed on main when this was written. 23 is what was next on 2026-09-11 — renumber it
rather than another branch's, the way this file's header already rules for sections 1 to 14.
