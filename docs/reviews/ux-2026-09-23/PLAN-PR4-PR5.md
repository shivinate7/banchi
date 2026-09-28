# The UX overhaul after PR 3: PR 4B, with PR 5 folded in

This record survives a handoff. Any session reads it to resume the UX overhaul. It was
rewritten on 2026-09-27 as a status board: finished, in motion, still to come. The owner's
rulings are quoted in backticks, and the full log sits at the foot of this file.

PR 5's work now lives inside PR 4B. Owner: `bring everything that was PR5 into PR4`.

## How to resume

- The orchestrator plans, briefs, verifies and merges. It never builds product code.
- The integration branch is `ux/pr4b`. Each lane branches from it and merges back. PR 4B is
  one PR from it. Its worktree for records is `.claude/worktrees/pr4b-plan`.
- Session grants lapse with their session. A new session asks the owner again for the merge
  grant and the model cap. This session's grants are in the log below.
- Cadence (owner, 2026-09-26): each lane gets one review, and a re-review only after a FAIL. A
  reviewer never re-runs a suite that the builder ran green at the same head. A lane merge gets
  only `cd app && npx tsc --noEmit`. The final head gets `make vale` only, then the PR, green CI,
  and the merge. CI is the only browser gate before main.
- A test that asserts a superseded rule goes to the owner. Nobody rewrites it silently.

## Finished (merged into `ux/pr4b`)

| Lane | What | Proof |
|---|---|---|
| S | Removed the redundant `_lookup_key` in `pipeline/stockimages.py` | Review PASS |
| D1 | Re-centered the lock glyph, and removed Pricing's 1px nudge | Review PASS |
| E | An Orders sale no longer jumps the screen, and Hide picked folds on its own press | Review PASS |
| M | The demo recorder resumes, and scrubs each route before it caches it | Re-review PASS after a FAIL |
| B2 | DEBT48: every writer of `prices.json` takes the store lock, with four revision checks inside it | Re-review PASS after a FAIL |
| F1 | Cards born by join or emit keep their game, plus a one-off repair script with a logged event | Review PASS |
| F2 | Sales falls back to the stock photo, Pokemon sealed included | Re-review PASS after a FAIL |
| C | `emit --cap` refuses a card with a pending copy, DEBT37 closed, D7 amended and names DEBT24 | Re-review PASS after a FAIL |
| A0 | The decision slug `D-orders-walk-rejoins-inventory`, amending D220 and D274, and spec §16 | Orchestrator check, key fixed |
| A1 | The walk draws stops densest first (cards to pick), and the box name breaks a tie | Review PASS |
| A2a | `CardPane` and one hero head, moved out of `BoxBrowse.tsx` | Review PASS, 0-pixel diff |
| A2b | `RailFrame`, moved out of `BoxBrowse.tsx` | Review PASS, 0-pixel diff |
| A2c | `CardLocations` gains `head={false}`, and `layoutsOf` moved to a shared home | Review PASS |
| L11 | `match-selftest` joins the path gate | Review PASS |

Records and studies, also merged:

- Lane A's design: mockups and plan in `orders-a/`.
- The test audit: four Sonnet slices and the Opus plan in `docs/reviews/test-audit-2026-09-27/`.
- F5's verbiage list: `verbiage-blind/verbiage.csv`.
- Lane H's blind review: `cyberpunk-blind.md`.

Earlier PRs, done: PR 3B, the demo mirror (#467 to #477), and PR 4A (#466).

## In motion (state at the 2026-09-27 compaction)

Each lane builds on its own branch `ux/pr4b-<lane>` and merges into `ux/pr4b` after one review
PASS, with `cd app && npx tsc --noEmit` at the merge.

| Lane | Branch | What | State |
|---|---|---|---|
| B3 | `ux/pr4b-B3` | A refused markdown apply writes nothing | Round 3: the outer file rename sat outside the error guard, and a failure there kept the price with no file. Fixing, then a re-review. |
| F5 | `ux/pr4b-F5` | Cut the excess words. Numbers and names stay. Review's mismatch line becomes "Mismatch: photo reading / matched listing". | Building. Then a review. |
| D2 | `ux/pr4b-D2` | Capture's gap with a head-to-body check, Review onto the kit's top gap, ReviewQueue's five controls, Codes' filter row | Building. Then a review. |
| P5 | `ux/pr4b-P5` | Stub D48 and D194 to one line each. Delete DEBT5, 6, 18, 28, 35, 42. Split DEBT27, or delete it if D279 removed its call. | Review PASS. DEBT27 keeps its open half (the Fulfiller's screen still loads the whole store). DEBT6 is kept in part, because a docs-audit row reads five figures from it. Rebasing onto `ux/pr4b` after a plan-file conflict, then merge. |
| A3 | `ux/pr4b-A3` | The Orders pane becomes `CardPane`, with no Details fold | Building. Then a review. |
| A6 | `ux/pr4b-A6` | No `Box <n>` fallback in the walk | Built. Review running. |
| L1 | `ux/pr4b-L1` | Cut T7's idle waits | Building. Then a review. |
| L3 | `ux/pr4b-L3` | `claim-stale` out of `make check`, two more gated self-tests, stale lines, and Vale retired | Built. Review running. |
| L5 | `ux/pr4b-L5` | Cut the old demo seed guards, keep the generator | Built (kept `demo-freshness`, a judgement call). Review running. |
| L6 | `ux/pr4b-L6` | DEBT47 closed, pull-confirm folded into fulfillment | Building. Then a review. |
| L7 | `ux/pr4b-L7` | Measure the slow CI shard, then one route sweep | MERGED (ed07efd9), after one FAIL: the folded floors now report every failure in one run. Shard 2 is slow from `icon-button.spec.ts` re-rendering the gallery per test. |
| L10 | `ux/pr4b-L10` | Heartbeat and coordinator retired | Review FAIL: docs-audit red (map entries and dead target names left). Fixing, then a re-review. |
| Q1 tiers | merged | A proposed tier for each docs-audit row: `docs/reviews/test-audit-2026-09-27/TIERS.md`. 65 Tier 1, 22 Tier 2, 13 Tier 3, 9 CUT, 7 unsure. | Waiting for the owner, together with Q8's merge families (PLAN.md item M3). No docs-audit lane starts before that. |

## Still to come

Lane A, in order, each after the lanes it needs:

- A4: walk rows carry their copies as `CardLocations` rows. It starts after A3 merges (both edit `OrdersWalkPane.tsx`).
- A5: layout R, with the buyer list in `RailFrame` and the phone order. It needs A3 and A4.

The test audit's lanes (plan: `docs/reviews/test-audit-2026-09-27/PLAN.md`):

- L1 cuts T7's idle waits (99.9s to 69.8s, all 4,568 checks green). L3 moves `vale` and
  `claim-stale` out of `make check`. L6 holds DEBT47's close and folds pull-confirm into
  fulfillment. L7 runs six route walkers as one sweep. These need no ruling and wait for the
  owner's word to start.
- L2 makes the per-commit docs audit read only changed files. It waits on Q1.
- L4, L5, L8, L9, L10 and L12 wait on their questions or on other lanes. L9 is DEBT45's form:
  `make explain` reads each test's own header every run.

Lane G, folded in with the audit:

- `claim-selftest` skips what git ignores, so a demo build never reddens it (owner's ruling).
- Measure the typecheck's out-of-memory failure, then fix its cause.
- Sync this session's rulings into `RULINGS.md`, and fix two stale lines there and in `STATE.md`.

Logged, waiting for the owner's word:

- F3: Pricing filters, from the blind review. They are a name search, a price sort, a set and
  game filter, and price bands. The same screen says "10 held" and "Held 15".
- F6: one spacing rule for every relation, and a check that fails an off-scale value.
- F7: `archive` and `wallet` sit low like the lock did.
- F8: in Inventory, a search for "hand hammer" ranks Jayce cards above the common card Hand Hammer. A Sonnet lane diagnoses the cause and the change that made it, then proposes a fix. D271 (one forgiving matcher everywhere) governs.

Before PR 4B merges:

- Main is red. The docs audit's `id claims` row fails on main's unclaimed slug
  `D-demo-stock-images`, because PR #476 merged without its claim. The owner: `Fold it into PR 4B`.
  So PR 4B's merge claims it. Check at merge time that `make merge` claims a slug main already holds.
- The final head: the PR, green CI, and `make merge`. Vale is retired, so no local step runs.

After PR 4B merges:

- The owner runs the F1 repair on the live store, preview first: `./scripts/repair-born-game.py`,
  then `--write`.
- A Sonnet integration review of PR 3 and PR 4 together. Then the screen pass at 1440, 820 and
  390 in both themes. Then the full `make design-check`.
- Lane H, the epilogue: an interview on the cyberpunk dark mode, then one lane.

Outside the repo: the owner runs the `claude-settings` prompt from 2026-09-26. It covers the
stale dev-server enforcement and two parent-guard bugs.

## Open questions for the owner

- Q1's tier list: an agent is proposing a tier per docs-audit row, for the owner to approve.
- Q5, Q6 and Q8 from the test-audit plan.
- Q7 is closed (2026-09-27). The owner turned on the required checks `check` and `revert-guard` on main, with strict off. Read back from the GitHub API.
- Merge the small PR that fixes main's red?
- The cadence rule's home waits for the test-audit rulings. The two NOT MECHANIZED rules
  outside CLAUDE.md's Hard rules block are deferred.

## Feedback inbox

Owner: `I will also provide feedback as I'm running through the app, and it either needs to logged into the markdown as lanes to start, or it needs to be sent to a lane currently on it, and/or sent as its own lane once identified by me`.

Each item gets an id and one line. Its route: sent to a running lane, logged for the owner's
word, or its own lane at once.

- F1, done: two "Unleashed" sets on Inventory's Sets view. 99 cards in box 5 had no game.
- F2, done: Sales drew "No photo" where Sets and Pricing drew stock images.
- F3, logged: the blind Pricing filter review.
- F4, in D2: Capture's gap below the subheading.
- F5, in motion: cut the excess words on every screen.
- F6, logged: one spacing rule.
- F7, logged: `archive` and `wallet` glyphs.

## Rulings log (2026-09-27, second session)

Grants, process-only:

- Model cap: `Only sonnet unless if I tell you to use opus for a specific agent work (I will say so for that lane) so no Opus for Lane C.`
- Opus for lane A: `Send an opus agent for A mockups and full plan`.
- Opus for the blind look: `send an opus agent to blindly just see wht the app looks like now, none of the decisions/work that went into it`.
- Opus for the test-audit review: `an opus agent reviews the corpus made and plans with me the resolution`.
- Merge grant: the owner named this session an Orchestrator. It merges PR 4B with `make merge`
  once CI is green.
- The final head gets `make vale` only, not a full `make check`: `Agreed and proceed`.

Lane E and A:

- E: `save it in the markdown as an item for PR4B, ironically rpelcaing the current E you have in there since we solved that now`.
- Hide picked: `The press folds picked rows`.
- A, Q1: `Three columns, layout R (Recommended)`. Q2: the buyer list scrolls in a sticky rail.
- A, Q3: `Full detail on every row (Recommended)`. Q4: `The walk, with the card in a sheet (Recommended)`.
- A, Q5: `i thought we sort formulaically be density of the cards available in a section?` Then `Density first, name breaks ties (Recommended)`.
- A, Q6: `we don't need details on this screen`. Q7: the PNGs stay outside the repo, because the
  pre-commit opsec hook refuses images.
- A1's density, the owner's follow-up: `on A1, if what you're saying is inventory has a different sorting order than the order walk's sorting order, then yes that's what i've been saying?` Still open.

Lane B2 and C:

- B2, DEBT48: `yes build now`.
- C, DEBT37: `Send a sonnet agent to see what's left on Debt 37 and how we can fix it`. Then the
  owner asked why it overshoots at all. The owner proposed, in paraphrase, that a cap works
  only once the store has read TCGplayer's live count. Then the owner chose the precise rule:
  `emit --cap` refuses for a card unless the store's live reading is newer than every copy sent
  since. The two wording gaps go in the same lane.

Lane D and the feedback items:

- D: `Keep Home, move Review`. Lane D2 builds Capture's gap, ReviewQueue's five controls and
  Codes' filter row. The owner first said `i need to see a visual` and `ill need to see details/plans before confirming`.
- F1: code fix and repair, own lane. F2: `Yes, including Pokemon sealed`.
- F3: `ask it what filters would be nice to have / optimal for an end user`.
- F5: `Approved on cutting everything from F5`, `rest are good to cull`, and for Review's line
  `middle option approved for the cut mismatch+data`.

G, T and PR 5:

- The demo build: `why do we or do we not want the demo walked? isn't the demo supposed to be more or less a sanitized symlink of main that should be pointless to review`.
- DEBT47: `The sealed browser is only in testing right and we can't change that? while, the real demo has unsealed browser that won't refuse other websites? If that's the case, any test for that portion is just dumb?`
- The test audit: `Sonnet slices build the summaries of what the tests are, an opus agent reviews the corpus made and plans with me the resolution, and then sonnet builders take that plan and execute upon it.`
- Test-audit Q3: `Yes, path-gate it (Recommended)`. Q4: `Re-measure, then remove if still 0 (Recommended)`.
- Test-audit Q1: `it needs a little less of a blunt tool approach than what you're proposing`.
- Test-audit Q2: `doesn't our parent claude say that once a rule is mechanized we remove its prose or soemthing`.
- The cadence rule's home: `Wait for the test-audit plan`. The two NOT MECHANIZED rules: `defer what to do on this for now`.
- PR 5 stubs: `Stub makes sense, but "ONE PARAGRAPH"????`. So each stub is its heading plus one line.
- PR 5 debts: `delete the six, split debt 27, and tell me what is left on debt 27?`
- PR 5 into PR 4: `bring everything that was PR5 into PR4, so you can do that debt27 check now`.
- H: `it'll be the epilogue of PR4`.
- Walk density: `Cards to pick at the stop (what's built)`.
- Test-audit Q1, the tiers: `Three tiers, agent proposes, you approve (Recommended)`. Q2: `Yes (Recommended)`.
- Start now: `L1, L3, L6, L7`. The owner asked for the other three options explained first.
- Vale: `Retire it, keep American spelling in docs-audit (Recommended)`. Lane L3 removes Vale.
  The spelling row learns markdown in lane L2. So the final head no longer runs `make vale`.
- Old demo seed: `Cut the old seed guards`. Lane L5. The heartbeat and coordinator: `Retire both (Recommended)`. Lane L10.
- Q8: `you haven't shown me the changes made to docs audit`. No docs-audit change is made yet. The owner sees the tier list and the merge families before any lane changes it.
