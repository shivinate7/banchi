## D291 — Runs fold into Review

**The owner ruled to fold Runs into Review (RULINGS.md, Q6).** When cards wait, Review shows an "Identify N cards, ~$X" strip. Past runs sit behind a link. `#/runs` stays a route for links. Home's six-stage strip becomes five. The owner heard the counterpoint, the money press on a daily screen, and chose the fold.

The Runs sheet on Review holds the run list. The twelve `review/ICON-MAP.md` rows keyed to `Runs*.tsx` go with the fold. `#/runs` is an off-nav redirect. Home's spine has five stages.

### Raw ids off the screen (D196)

`RunPanel.tsx`'s `run-row-name` and `runs-detail-name` drew the run's own directory name, such as "demo-box3", as primary text. That is a repository path, which D196 forbids. The box label already tells two runs apart, from `scopeOf(row)`. The raw id now rides a title tooltip only. `claim()`'s `raw` argument uses the same pattern elsewhere on this screen for a pipeline spelling. Two dead CSS rules were deleted. Two `run-panel.spec.ts` row selectors found a row by its raw-id text. They now use the title attribute.

### The strip

- **Its shape.** It is a well, not a warning. Cards that wait to be read are the normal state of a store between runs. It says "Identify N cards, ~$X" and holds two presses.
- **"~$X".** It is this store's past cost per card: every recorded `usage.cost_usd` divided by every `counts.cards_in` of the same runs, times N (`Runs.tsx:perCardRate`). Both figures are the server's. No token count is multiplied here. It is not a quote, and nothing is gated on it. The preflight is still the figure the spend press is confirmed against.
- **Why no preflight on the strip.** The preflight decodes every waiting photograph. That takes about a minute over 544 cards. The strip would run it on every visit to a daily screen. So the strip uses the store's past cost instead.
- **No figure without history.** A store with no recorded spend draws no figure, rather than a guess. The run list is read only while cards wait.
- **Past runs.** The full list sits behind one link: the `history` IconButton on Review's header. It opens the Runs sheet on its run list. A count with the list one press further was rejected. The list is the only way to a run's own steps (join, rescue, fetch). A count adds a press and reaches nothing new.
- **One layer above another.** The composer and the rescue and live-check sheets moved onto the kit's own Dialog and Sheet (D275). That exposed a kit defect. A layer drawn inside another layer, mounted in the same commit, joined the overlay stack first. React runs a child's layout effects before its parent's. The outer Sheet then painted over the composer. It took the clicks, Escape and focus. `kit/overlay.tsx` now hands each layer's panel down to the layers inside it. A parent that joins late goes under them. Four `run-panel.spec.ts` cases traced to this, or to the rescue sheet staying in the DOM while hidden. They run again.

### The two presses

The owner ruled that the strip has two presses. The owner wanted to choose between waiting for the free pre-check and going straight to the bill. "Identify now" spends at once. "Check first" opens the composer.

- **One list, and every half reads it.** The strip's N, its ~$X, the "Identify now" spend and the receipt all come from one list. That list is `POST /pipeline/waiting` (`pipeline_routes.do_pipeline_waiting`). It answers the cards a spend over a selection would buy. Each has a photograph, and no live claim holds it (D174). It is free, decodes nothing and spawns nothing. It makes the same two reads the spend route makes before it spawns, so the strip never offers a card the press would refuse. On the demo store, whose captured cards have no photograph, the strip draws nothing. After a spend, the run's claim takes those cards off the list. `/status`'s `captured` count is only the cheap gate on whether to ask at all.
- **The selection is the composer's opening one, for both presses.** When `#/inventory` hands over ticked cards (`banchi.run-scope`), that set is the selection. The composer opens on its `ticked` start. The strip names, prices and spends the same set. Otherwise the selection is every card photographed and not identified. One function derives it (`RunsComposer.tsx:openingSelection`, over `selectionOf`).
- **"Check first"** opens the composer on that selection. Its flow is unchanged: the free pre-check, then the confirm, then the spend. It runs over D180's selection grammar. A composer opened this way and closed with no run started also closes the sheet. The operator returns to Review.
- **"Identify now"** starts the paid run at once. There is no pre-check and no confirm screen. It spends exactly the strip's list. The list is sent as a `keys` selection (D180, `RunsComposer.tsx:sendOfKeys`) with the composer's default reading. It never sends a state. A card captured in another tab after the strip read its list is not in the list, so it cannot grow the spend. An empty list is refused before the wire. The wire drops an empty `keys` term, because a send with no term would buy the whole store. The receipt is a toast with the server's own count (`started[0].cards`). Then the run opens in the Runs sheet, where its progress reads itself. A refusal is also a toast, so it moves nothing on the screen (D118).
- **The spend route is unchanged.** It asks only for `confirm: true` (D33). It holds no pre-check token. D174's claim is still written by the command, inside the transaction that decides which cards it buys. A second tab can never buy the same cards twice. `make submission-selftest` proves that half. The screen adds an in-flight guard, so a double press sends one spend. `review.spec.ts` proves each rule here. Each case fails on its own mutation. The mutations are: a state sent in place of the keys, the handoff ignored, N read off `/status`, and the guard deleted.
- **What a keys send does not re-check.** A `keys` send carries no state term. So a card identified between the strip's read and the press is read again. That is usually a free cache hit. If a capture undo frees an index, and a new card takes it, the press buys the new card. The count stays the same. The owner accepted that trade when choosing the immediate press. "Check first" still quotes the exact cards before any spend.
- **The demo draws no strip.** The published demo holds no recording of `POST /pipeline/waiting`. It refuses the read as `demo_not_recorded` (`demoServer.ts`, `docs/specs/demo.md`: an unrecorded read is refused, never answered with an empty list). The strip treats that refusal as nothing waiting, and draws nothing. Identify is frozen in the demo anyway.
- **The estimate says it is one.** "~" marks every figure, including "under a cent". A title says "An estimate from this store's past runs, not a quote". A screen reader hears "(estimate)".
- **Which press is worded, and which is primary.** Both keep their words, because both are about money (the iconography rule, step 2). "Identify now" takes the one solid fill, because it is the press that spends. It must read as the loud one. "Check first" is ghost. The header holds no worded primary, so the header rule still holds. That rule is the owner's tightening: at most one worded primary, and the rest are IconButtons or a More menu.

### Where emit and reconcile live

Both stay together in the Runs sheet. Neither moves to `#/pricing`, and neither becomes its own page. Placement is a scroll. The ordered work saves the time. A run stalls for a missing answer, such as the sub-threshold disposition or an unanswered review queue. It never stalls for where a button sits. Identification takes minutes. The review queue takes most of a sitting. So the calendar is made of runs that stop, not of stages.

- **Emit is free.** A pricing screen may hold its button. A stale run list or a race with the pricing autosave are the costs of doing so. Emit has no argument for moving.
- **Reconcile does not belong on pricing under any reading.** Its input is a file. The file exists only after the operator has left the app, imported to TCGplayer and downloaded as Export From Staged. Reconcile reads no pricing answer. Its only tie to emit is one manifest key. What it needs is to be findable on re-entry. So a run's phase says what the run owes, in its own unit ("price 12", "answer 4"). It does not name three different states as `emit`.
- **Built:** the preset moves `rule` and `basis`. `#/pricing` draws the sub-threshold answer. `app/src/readiness.ts` computes what a run owes.
- **Abandoned by the owner, three items:**
  - Collapsing a finished step's body.
  - A `#/runs?run=<name>` link back from pricing.
  - The same ink weight for the `reconcile` phase as for `identifying`.
- **What would reopen it:** any one of these.
  - Emit still complained about after the sheet.
  - A median box needing two or more refused emit presses.
  - The emit-to-reconcile gap measured in days on a real listing box. One measurement exists: 6m44s, 13 SKUs.
