# The UX overhaul plan after PR 3: PR 4A, PR 4B and PR 5

This record survives a handoff. Any session reads it to resume the UX overhaul. It was
written on 2026-09-27, after PR 3 (#465) merged as `5b7f5d295`. The owner's rulings it
carries are quoted in backticks.

## How to resume

- The orchestrator plans, briefs, verifies and merges. It never builds product code.
- **Session grants lapse with their session.** The 2026-09-26 model cap (`no subagent ... above
  sonnet in this session`), the merge grant, and the 2026-09-27 autonomous-run grants all
  ended with that session. The run finished: PR 3B merged (#467 to #477). A new session asks
  the owner again for the merge grant and the model cap.
- **This session's grants (owner, 2026-09-27, second session, process-only):**
  - Model cap: `Only sonnet unless if I tell you to use opus for a specific agent work (I will say so for that lane) so no Opus for Lane C.`
  - Opus for lane A (owner, same day): `Send an opus agent for A mockups and full plan`.
  - Order (owner, same day): E, B2 and S start now. A's design pass starts now. D, C and
    DEBT35 wait for an interview. G and T wait for an interview and a cross-check. The
    cross-check covers debts, deferred items, wants, CI tests, audits and rules. H waits.
  - Merge grant: the owner named this session an Orchestrator. It merges PR 4B into main with
    `make merge` once CI is green.
- **Integration branch (2026-09-27, second session):** `ux/pr4b`. Each lane branches from it
  and merges back into it. PR 4B is one PR from it.
- **Cadence (owner, 2026-09-26):**
  - Each lane gets one review. A re-review happens only after a FAIL.
  - A reviewer never re-runs a suite that the builder ran green at the same head.
  - A lane merge into the integration branch gets only `cd app && npx tsc --noEmit`.
  - On the final head, run `make vale` only, the one part of `make check` that CI skips. Then
    open the PR, wait for green CI, and merge. Owner, 2026-09-27: `Agreed and proceed`. This
    replaced one full `make check` at the end, because CI's `check` job runs `make ci-check`.
  - CI is the only browser gate before main.
- **A stale test:** a test that asserts a superseded rule is flagged to the owner. Nobody
  rewrites it silently. Owner: `let me know if the rule in ci itself is bad/stale`.
- **Order:** PR 4A, then PR 4B, then the post-PR 4 checks, then PR 5. PR 4A and PR 4B merge
  independently.

## PR 3B: the demo data follow-up (DONE, 2026-09-27)

The full mirror is live at `shivinate7.github.io/banchi/`, publish run 36329643153 on main
`b61f995e2`. PRs #467 to #474 carried it. 808 buyers are scrubbed to `Jane Doe N`, 3,510
photos total 94.7 MB, and a leak check against a store copy found 0 real names.

Stock images: #476 and #477 (2026-09-27) fill Riftbound and One Piece images in the demo.
They come from the live server's own tcgcsv cache, offline, for 795 of 796 SKUs. The bundle is split into
files under 50 MB for GitHub's limit. The test stubs the image host for now (DEBT47).

Left for PR 4B (lane M):
- The demo records a walk plan for each order and for the screens' own "walk all" sets. Any
  other ticked combination shows the demo's honest refusal, by design.

## PR 4A (DONE, 2026-09-27)

Merged as #466. It carried lanes J, K, F, N1, N2, E (search), B and F2, and the records. Every
lane passed one review. N2 passed a strict review in three rounds.

## PR 4B lanes (rewritten 2026-09-27)

Lanes B and F2 moved into PR 4A. This is what PR 4B still holds. The lanes are independent,
except where a line says otherwise.

| Lane | What | Starts |
|---|---|---|
| E | The Orders jump, unpinned | Now |
| B2 | The restore lost-update race | Now |
| C | The send path (money) | Now |
| D | Leftover screens and the lock glyph | Now |
| M | Demo mirror resumability | Now |
| G | Records and tooling | Now |
| T | The test pass: DEBT45 and DEBT47 | Now |
| S | Remove Lane F's redundant `_lookup_key` wrapper | Now |
| A | Orders becomes Inventory's screen | After a mockup the owner approves |
| H | Cyberpunk dark mode | Last, as the epilogue |

### E. The Orders jump, unpinned

Owner, 2026-09-27: `save it in the markdown as an item for PR4B, ironically rpelcaing the current E you have in there since we solved that now`.

- The defect: in an Orders walk, Mark sold hides the row at once under `hideSold`. The page
  shrinks, and the view jumps about 48px. `OrdersWalkPane.tsx` does this, on main since
  `fc58ca3f`. D118 (a press never moves the rest of the screen) forbids it.
- PR 3 made CI green with a bandaid. A `scrollTo` pin in `app/tests/orders.spec.ts` UN-6 hides
  the jump from the test. The test no longer guards the real behavior.
- The fix: a sold walk row stays in place until the next load, as D263 (a sold row folds on
  the next load) already rules for Inventory. Remove the pin. Prove UN-6 red on the old
  behavior, then green. Add a DEBT for the jump first, and close it in the same lane.

### B2. The restore lost-update race — STOPPED, see DEBT48

- Found by lane B's reviewer, older than lane B. `do_pricing_restore` reads the corpus, then
  the clears, with no lock across both. Two concurrent restores can lose an unrelated price
  edit.
- The builder checked first, as asked. `PUT /pricing` and the clear path do not take the store
  lock either. Nothing that writes `inventory/prices.json` does. Five call sites write it. All
  are unlocked. Each is guarded only by an optional revision digest, and a slow client can skip
  past that. A lock around `do_pricing_restore` alone would not close the named race. The other
  side of every pairing the lane named stays unlocked. It can still land its write in the same
  gap. DEBT48 has the full finding and the fix: `files.exclusive` around all five call sites,
  one Sonnet lane's worth of touch points, across three files. It asks the owner whether to
  build that now or defer it.

### C. The send path (money, so an adversarial review)

- The `--cap` plus `--live-guard` defect. The owner's ruling (2026-09-25) is in `RULINGS.md`:
  the cap counts the larger of the guard's live count and the store's own count.
- The DEBT35 exit split for `emit`.

### D. Leftover screens

- The Home h1 greeting, the Capture top gap, the Fulfillment `<Page>` variant, the Runs R2
  entries, and the six icon entries (see `STATE.md` in this folder).
- The lock glyph sits low in its drawing (`kit/Icon.tsx`, `lock`). Lane K nudged one Pricing
  button 1px as a bandaid. Fix the glyph, and remove the nudge.

### M. Demo mirror resumability

Owner: `is there anyway u can have it chunking so that way it's not starting from zero each time`.

- The recorder writes each route as it lands. A re-run over the same snapshot skips the routes
  already recorded.
- The build log already moved out of `demo-mirror/` in PR 3B.

### G. Records and tooling

- `claim-selftest` reads gitignored demo build output. So a lane that built the demo goes red.
  Fix it, or record a DEBT.
- The cadence above becomes a repo rule, with its enforcement or an argument for why it has
  none. D173 (a rule that can be enforced mechanically is enforced) governs.
- Sync the orchestrator's scratch rulings into `RULINGS.md` in this folder.
- Add the `STATE.md` deferred items.
- The typecheck runs out of memory at Node's default heap on this Mac since the full mirror
  landed. Measure it, then raise the limit in the Makefile or exclude the demo data from `tsc`.

### T. The test pass

- DEBT45: one page that says what each test protects, in plain words.
- DEBT47: the demo coverage spec allows the TCGplayer image host by name, and the stub goes.
- Any other test whose premise a ruling changed, found in the same pass.

### S. Small cleanups

- Lane F's `_lookup_key` wrapper in `pipeline/stockimages.py` is redundant since F2 folded
  whitespace in the shared join key. Remove it.

### A. Orders: the walk becomes Inventory's screen (the biggest lane)

D220 (Orders is Inventory's screen, and the walk is a mode of it) governs. The built screen
drifted from it. The owner's final direction:

1. Inventory's left rail becomes the Orders buyer list, with checkboxes and "Walk all N buyers".
2. The walk list keeps its style: grouped by section in the solver's order, with "Pick N of M".
   Sort by box NAME, then section. Today `walkplan.Stop.walk_order` sorts by the hidden box
   number, so "WB1 R3" can come before "WB1 R1". D259 (a box is shown only by its name)
   governs.
3. Every pick row carries Inventory's location detail. That detail is the box, section and
   card, the section strip, the back-to-front ruler, and the neighbor names. Mark sold works
   on the row. Reuse Inventory's own components. Never fork them.
4. A click on a row fills the right pane with the photo and the card facts. Below them goes
   EVERY on-hand copy, in Inventory's copies list, with the walk's chosen copy first. D212
   (every copy is fungible) governs.
5. Lane E fixes the sold-row jump. Lane A must not undo that fix.
6. On a phone, the buyer shows before the photo.

Do a design pass first, and show the owner a mockup.

### H. Epilogue: cyberpunk dark mode

- Owner: `it'll be the epilogue of PR4`. First an interview and mockups, then one lane.
- The earlier palette work is shelved on `ux/dark-palette`.

## After PR 4 lands in full

Owner: `The sonnet review will come after PR4 lands in its entirety`.

1. A Sonnet integration review of PR 3 and PR 4 together. Its focus is the hand-merged
   `Inventory.tsx` move and undo.
2. The screen pass at 1440, 820 and 390, in both themes, with a verdict per screen.
3. The full `make design-check`.
4. DEBT45 (no page lists what each test protects) is ready to close once the tests stop moving.

## PR 5: the decision and debt cleanup

Owner, 2026-09-27: `just add the decision and debt cleanup as a PR5 item to come after we do a sonnet review which came after pr4`.

It starts only after the Sonnet review above. The owner asked whether a Haiku agent could delete
solved entries in place. The orchestrator advised against it. Deciding "solved" is a judgment,
and many entries are amended rather than retired. Also, other records cite each entry by its
number. The plan:

1. A read-only Sonnet agent lists the candidates, one line each: the entry, why it looks solved,
   and what replaced it.
2. The owner rules on the list.
3. A builder condenses each approved decision to a short stub that points at its successor. The
   id and every citation keep working. An approved debt is deleted, and its number is retired.
   The debt preamble says "an entry leaves when someone argues it should", and the owner's
   ruling is that argument.
4. `make docs-audit` proves that every citation still resolves.

## Outside the repo

The owner runs the `claude-settings` prompt that the orchestrator gave in chat on 2026-09-26.
It covers the stale dev-server enforcement and two parent-guard bugs: an apostrophe inside a
comment, and the stash clause on an empty stack.
