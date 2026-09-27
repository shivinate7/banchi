# The UX overhaul plan after PR 3: PR 4A, PR 4B and PR 5

This record survives a handoff. Any session reads it to resume the UX overhaul. It was
written on 2026-09-27, after PR 3 (#465) merged as `5b7f5d295`. The owner's rulings it
carries are quoted in backticks.

## How to resume

- The orchestrator plans, briefs, verifies and merges. It never builds product code.
- **Model cap (owner, 2026-09-26):** `going forward no subagent is allowed to be above sonnet in this session`.
- **Merge grant:** it is session-bound. A new session asks the owner for it again.
- **Cadence (owner, 2026-09-26):**
  - Each lane gets one review. A re-review happens only after a FAIL.
  - A reviewer never re-runs a suite that the builder ran green at the same head.
  - A lane merge into the integration branch gets only `cd app && npx tsc --noEmit`.
  - ONE `make check` runs on the final head. Then open the PR, wait for green CI, and merge.
  - CI is the only browser gate before main.
- **A stale test:** a test that asserts a superseded rule is flagged to the owner. Nobody
  rewrites it silently. Owner: `let me know if the rule in ci itself is bad/stale`.
- **Order:** PR 4A, then PR 4B, then the post-PR 4 checks, then PR 5. PR 4A and PR 4B merge
  independently.

## PR 3B: the demo data follow-up (in flight)

- The full-store mirror build runs detached in worktree
  `.claude/worktrees/agent-a184b2e3f6b4fe201`. It survives a session restart.
- The first detached run hung. The cause was an unread server output pipe that filled, so
  every server thread blocked on a write. Commit `36d2f796` on `ux/demo-mirror-data-build`
  fixes it. The recorder now drains the pipe, and a failed request stops the build loudly.
  A new recorder self-test on that branch proves both. This fix needs its one review before it
  merges.
- The build is done when `demo-mirror-build.exit` exists at that worktree's root. The log is
  `demo-mirror-build.log` beside it.
- Then:
  1. Check the scrub. Every buyer matches `^Jane Doe \d+$`, and every address is `123 Demo Way`.
  2. Check that the photos total 512 MB or less.
  3. Commit `demo-assets/mirror/` and the fix, then push to `origin ux/demo-mirror-data`.
  4. A short leak check, a small PR, green CI, and merge.

## PR 4A (in flight)

Owner, 2026-09-27: `approved on your next portion, can merge them all into an integration branch ... merge when green`.

| Lane | Branch | What | State on 2026-09-27 |
|---|---|---|---|
| J | `ux/pr4a-capture` | Capture: two key caps, one next-card number, short section note, Rarity clip, one-line camera prompt, Game in Stack | Review FAIL: the next-card number stays high after an undo in a section. Builder fixing |
| K | `ux/pr4a-pricing` | Pricing: flag on its own line, number chip, the stranded-cards line as a link, Held lock, column tint | PASS |
| F | `ux/pr4a-stock` | Stock images: fold the spaces around the slash in a lookup number | PASS |
| N1 | `ux/pr4a-sets` | Inventory Sets: a grid of card images, a set picker, a clean header. A tile opens the card's Inventory view | Building |
| N2 | `ux/pr4a-map` | Inventory Map: box rows left to right, an edit mode with one Confirm that saves all or nothing, no subtitles on Inventory | Building. Needs a strict review, because it writes store data |
| E | `ux/pr4-search` | Search: close the open gaps that D271 (one forgiving search matcher) discloses | Done. Every listed gap was already closed. D271 round 12 records it. Typo search is deferred as DEBT46 |
| records | `ux/pr4a-records` | DEBT45, DEBT46, and this file | Committed |
| B (from 4B) | `ux/pr4b-pricing-undo` | The restore race crash, the skip reason in the toast, the matrix check | PASS. Moved into PR 4A by the owner |
| F2 (from 4B) | `ux/pr4b-join-spacing` | The shared join key drops all whitespace | Building. Moved into PR 4A by the owner. After it merges, remove Lane F's `_lookup_key` wrapper |

Owner rulings for N1 and N2 (2026-09-26):

- `i dont need location unless i click on the card itself then maybe it opens the regular inventory view of the card`
- `map should be that i enter an edit mode, in this edit mode i can drag and drop freely, and then i have to hit confirm once once im happy with the layout`
- `using horizontal rather than vertical it seems more intuitive`
- `i hate subtext and ur overuse of verbiage`, then `let's eliminate evne the subtitles`
- The card-range move ("Some cards"), 2026-09-27: the owner chose `Bring it back into edit mode (Recommended)`. A card range drafts like a section, and the one Confirm saves both, all or nothing.

Owner, 2026-09-27: `the few  changes i pullled forward from PR4B btw  that were made rn btw are gonna join PR4A`.

Then: merge every lane into `ux/pr4a-integration` off main, with tsc per merge. Run one
`make check`, open the PR, wait for green CI, and merge.

## PR 4B lanes

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
5. The sold-row jump is its own lane, E, below. Lane A must not undo that fix.
6. On a phone, the buyer shows before the photo.

Do a design pass first, and show the owner a mockup.

### B. Pricing and undo follow-ups

- `pipeline_routes.do_pricing_restore`: `kept[ids.index(...)]` raises `ValueError` when a
  concurrent request drops the clear.
- The restore skip toast says "answered again since". The text is wrong when a newer clear
  holds the SKU.
- The two low notes from the pricing review: the ranks 5-6 failed-read note, and the matrix
  `failed=None` check.
- Lane B (branch `ux/pr4b-pricing-undo`, `d89839a9`) PASSED review on 2026-09-27 for the three items above.
- Found by its reviewer, older than the lane: `do_pricing_restore` reads the corpus, then the clears, with no lock across
  both. Two concurrent restores can lose an unrelated price edit. Fix it under the store lock, or record a DEBT.

### C. Send path (money, so an adversarial review)

- The `--cap` plus `--live-guard` defect.
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

### E. The Orders jump, unpinned (replaces the search item, which is done)

Owner, 2026-09-27: `save it in the markdown as an item for PR4B, ironically rpelcaing the current E you have in there since we solved that now`.

- The defect: in an Orders walk, Mark sold hides the row at once under `hideSold`. The page
  shrinks, and the view jumps about 48px. `OrdersWalkPane.tsx` does this, on main since
  `fc58ca3f`. D118 (a press never moves the rest of the screen) forbids it.
- PR 3 made CI green with a bandaid. A `scrollTo` pin in `app/tests/orders.spec.ts` UN-6 hides
  the jump from the test. The test no longer guards the real behavior.
- The fix: a sold walk row stays in place until the next load, as D263 (a sold row folds on
  the next load) already rules for Inventory. Remove the pin. Prove UN-6 red on the old
  behavior, then green. Add a DEBT for the jump first, and close it in the same lane.

### F2. The spacing gap in the real join (in flight)

- Measured on a store copy, 2026-09-27: 2 of 3,510 cards carry a space in their number. The
  real risk is the 155 Riftbound Token SKUs whose printed number has an interior space.
- The owner chose `Fold in the shared key (Recommended)`. `join.number_index_key` drops all
  whitespace, for every caller. Branch `ux/pr4b-join-spacing`.
- After PR 4A merges, remove Lane F's `_lookup_key` wrapper in `pipeline/stockimages.py`,
  because it becomes redundant.

### G. Records and tooling

- `claim-selftest` reads gitignored demo build output. So a lane that built the demo goes red.
  Fix it, or record a DEBT.
- The cadence above becomes a repo rule, with its enforcement or an argument for why it has
  none. D173 (a rule that can be enforced mechanically is enforced) governs.
- Sync the orchestrator's scratch rulings into `RULINGS.md` in this folder.
- Add the `STATE.md` deferred items.

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
