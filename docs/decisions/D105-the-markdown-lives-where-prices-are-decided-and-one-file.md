## D105 — The markdown lives where prices are decided, and one file may not have two unguarded writers

**The stale-listing markdown sheet opens from `#/pricing`'s header, not `#/runs`'s.** Moved 2026-09-06 on the owner's objection, in one sentence: *"that's kinda dumb, this should just live in pricing"*.

They are right, and the flaw in D100's placement is nameable rather than a matter of taste. That entry put the sheet beside the store-wide reconcile because the two read the **same file** — TCGplayer's My Pricing export — and argued *"the order of the two buttons is the order of the work"*. That is kinship of **implementation**. `#/runs` is the pipeline over a box that was just photographed: identify, join, emit, and the money gate. A markdown decides a **price** over inventory that is already listed, and this product already has the screen where prices are decided — the one the operator asked for by name when they asked for this feature at all (*"the same pricing sorta setup I get when i'm first listing prices"*, D103).

**The sheet's own second step already went here.** `#/pricing?markdown=<stamp>` is where a written worklist is priced, and it was the sheet's terminal press from the day D103 landed. So the flow crossed screens for no reason the operator could see: press a button on Runs, get sent to Pricing, come back to Runs to read another export.

### It lands rather than navigates, and that is a property of the shell

`App.tsx` renders the view under `key={path}`, where `path` is the hash **minus its query**. `#/pricing` and `#/pricing?markdown=<stamp>` are one key, so the sheet's step-2 press does not remount anything: it closes itself, writes the hash, and `Pricing.tsx`'s own `hashchange` listener picks the stamp up. The operator presses **Price these** and the rows appear under them on the screen they are standing on.

That was true before this move and is what makes the move worth having. On `#/runs` the same press was a screen change.

### `LiveReconcile` stayed, and the split is the point

The obvious reading of the owner's objection is "the two export sheets are on the wrong screen". Only one of them is.

`POST /pipeline/reconcile-live` writes `live` onto the store's own listing records (D87) — how many copies TCGplayer holds. That is a fact about **inventory**, and it is settled where the other inventory facts are: beside the join, the emit and the run log. It writes no price and reads no corpus.

Moving both sheets together would have preserved D100's co-location argument while accepting the objection to it — the two would still be siblings, just siblings somewhere else. Splitting them is what actually answers the objection: each sheet went to the screen that owns the kind of fact it writes.

### Two writers of one file now share a tab, and only one of them had the guard

This is the real cost of the move and the only part of it that is not a button.

`inventory/prices.json` is one file for the whole store (D86). D103 gave `#/pricing` a stale-write guard for exactly the hazard this move creates: the sheet's step 3 runs `reprice apply --write` in a **subprocess**, which writes the corpus behind the screen's back, and the screen's next keystroke would then be refused `corpus_moved` for a write made on its own behalf. While the sheet lived on `#/runs` there was no pricing screen mounted beside it, so the hazard was theoretical. It is not any more — the sheet is mounted **inside** the screen that holds the digest.

So the digest travels: `Markdown` takes `revision` and hands back `onCorpusWritten`, and `Pricing.tsx` adopts the digest the apply produced. Undefined still means *"the host read no revision"*, which the route allows and the terminal user relies on.

**The digest travels BESIDE the document and never inside it**, which is D103's rule and is unchanged here.

### The bare keys enumerate the surfaces they yield to, and there was a new one

`#/pricing` takes two unmodified keys — `R` reloads, held `T` peeks a price history — and both list the open surfaces they stand down for by name. The sheet is a surface that did not exist when they were written.

`R` is the harmful one and it is not cosmetic: typed into the sheet's *"Cut, percent"* field it would call `load()`, re-read the worklist and the corpus, and **discard an in-flight survey out from under the operator** — bytes the screen is holding for an export they just waited on. `app/tests/markdown.spec.ts` carries a case for it that watches the host's own reads.

### A route is still not the answer

D100 wanted `#/markdown` and was refused by arithmetic over a horizontal nav — 1,484.9px of links against a 1,440px desk. D95 deleted that strip, and `App.tsx`'s ROUTES comment carries this tree's own re-measurement of the sidebar: a tenth link costs 38px against 196px of slack. **It would fit, and it is still not a row.**

The lens already has an address — `#/pricing?markdown=<stamp>`, which can be bookmarked, is in the palette and is reachable by chord. A second pricing route would be two screens for one job, which is the complaint this move answers, restated one level up. Adding a row also moves a count three mechanical checks reconcile (`route census`, `route rosters`, and every spec's pinned roster), so it is a deliberate edit and never a side effect.

### What this amends

**D100 §5's placement**, which `docs/specs/stale-listings.md` records. The sheet is a modal and not a route — that half stands. Which screen hosts the modal is what changed, and the reason it changed is that D100's stated reason for the host was kinship of implementation.

**Nothing on the wire moved.** No route, no payload, no shape. `server/pipeline_routes.py` is untouched by this entry.

### What would reopen this

*The operator wanting the reconcile on `#/pricing` too* — which would be them saying the two sheets are one piece of work after all, and is theirs to say. *A third writer of `inventory/prices.json` in one tab*, at which point a digest passed hand to hand between components stops scaling and the corpus wants a subscription rather than a prop.
