# The UX overhaul after PR 3: PR 4B, with PR 5 folded in

This record survives a handoff. Any session reads it to resume the UX overhaul. It was
rewritten on 2026-09-27 as a status board: finished, in motion, still to come. The owner's
rulings are quoted in backticks, and the full log sits at the foot of this file.

PR 5's work now lives inside PR 4B. Owner: `bring everything that was PR5 into PR4`.

## How to resume

- The orchestrator plans, briefs, verifies and merges. It never builds product code.
- The integration branch is `ux/pr4b`. Each lane branches from it and merges back. PR 4B is
  one PR from it. Its worktree for records is `.claude/worktrees/pr4b-orch`.
- Session grants lapse with their session. A new session asks the owner again for the merge
  grant and the model cap. This session's grants are in the log below.
- Cadence (owner, 2026-09-26): each lane gets one review, and a re-review only after a FAIL. A
  reviewer never re-runs a suite that the builder ran green at the same head. A lane merge gets
  only `cd app && npx tsc --noEmit`. The final head gets linting only (Vale retired 2026-09-27), then the PR, green CI,
  and the merge. CI is the only browser gate before main.
- A test that asserts a superseded rule goes to the owner. Nobody rewrites it silently.

## Finished (merged into `ux/pr4b`)

| Lane | What | Proof |
|---|---|---|
| S | Removed the redundant `_lookup_key` in `pipeline/stockimages.py` | Review PASS |
| D1 | Re-centered the lock glyph, and removed Pricing's 1px nudge | Review PASS |
| E | An Orders sale no longer jumps the screen, and Hide picked folds on its own press | Review PASS |
| M | The demo recorder resumes, and scrubs each route before it caches it | Re-review PASS after a FAIL |
| B2 | DEBT53: every writer of `prices.json` takes the store lock, with four revision checks inside it | Re-review PASS after a FAIL |
| F1 | Cards born by join or emit keep their game, plus a one-off repair script with a logged event | Review PASS |
| F2 | Sales falls back to the stock photo, Pokemon sealed included | Re-review PASS after a FAIL |
| C | `emit --cap` refuses a card with a pending copy, DEBT37 closed, D7 amended and names DEBT24 | Re-review PASS after a FAIL |
| A0 | The decision slug `D304`, amending D220 and D274, and spec §16 | Orchestrator check, key fixed |
| A1 | The walk draws stops densest first (cards to pick), and the box name breaks a tie | Review PASS |
| A2a | `CardPane` and one hero head, moved out of `BoxBrowse.tsx` | Review PASS, 0-pixel diff |
| A2b | `RailFrame`, moved out of `BoxBrowse.tsx` | Review PASS, 0-pixel diff |
| A2c | `CardLocations` gains `head={false}`, and `layoutsOf` moved to a shared home | Review PASS |
| A3 | The Orders pane becomes `CardPane`, with no Details fold | Merged (c8562273) |
| A4 | Every Orders walk row carries its copies as `CardLocations` rows | Merged (1736fc8e) |
| A5 | Orders takes Inventory's three-column skeleton, a phone sheet for the card | Merged (952fbd34) |
| A6 | No `Box <n>` fallback in the walk | Merged (633aff52) |
| B3 | A refused markdown apply writes nothing | Merged (49e12373) after four rounds |
| D2 | Capture's gap with a head-to-body check, Review onto the kit's top gap, ReviewQueue's five controls, Codes' filter row | Merged (752d638b, plus the z-index follow-up) |
| F5 | Cut the excess words on every screen. The palette keeps "Go to" | Merged (ee17847c), plus T7's own fix (5918d8ab) |
| F8 | Inventory search leads with the best-ranked match, and says when it is sold | Merged (bc66af69) |
| F9 | An empty section leaves the Inventory walk's ruler and box header | Merged (66992bce) |
| F9b | Four stale tests follow F5's approved copy and the server's box contract | Merged (6aea8d15) |
| F10 | The box rail counts matches while a printing waits to be picked | Merged (8e2476e8) |
| F11 | Every search field uses the one matcher (D271 amended), F11b folded in | Merged (1eaa5939) |
| F11c | The hand-search lint catches every folded comparison, with a self-test | Merged (ad379c57) |
| G | Every staged image gets the QR scan, fail closed. `claim-selftest` skips ignored files. The tsc premise no longer held | Merged (73037a92) |
| L1 | Cut T7's idle waits | Merged. T7 median 130s to 72s, measured by the reviewer |
| L2 | docs-audit reads the commit, not the tree. Markdown spelling joins a shrinking list | Merged (6b8e3f2d, plus the spelling fix 0481a743) |
| L3 | `claim-stale` out of `make check`, two more gated self-tests, stale lines, and Vale retired | Merged (31355eea) after two FAILs |
| L4 | Breakpoint questions answered. `RunPanel` asks its own sheet (container runs) | Merged (7e33c5ac) |
| L5 | Cut the old demo seed guards, keep the generator | Merged (7481619a) |
| L6 | DEBT47 closed, pull-confirm folded into fulfillment | Merged (29c32166) |
| L7 | Measure the slow CI shard, then one route sweep | Merged (ed07efd9), after one FAIL |
| L8 | docs-audit merges 16 rows into families, 107 to 93 (M3, Q8) | Merged (db207f3c) |
| L10 | Heartbeat and coordinator retired | Merged (4c58fbfb) |
| L12 | docs-audit rows block by tier, 11 rows cut, commit hook 8.63s to 6.12s | Merged (bd88525f) |
| debt48 | B2's debt becomes a slug, and `numbered record growth` refuses a record numbered on a branch | Merged (c5766886) |
| L11 | `match-selftest` joins the path gate | Merged (568f81a2) |
| P5 | Stub D48 and D194 to one line each. Delete debts 5, 6, 18, 28, 35 and 42 | Merged (afc2ca83) |
| R | `make reap` stops only processes tagged with the caller's id | Merged (215dd646) |
| T-claude | `CLAUDE.md` cut from 112 KB to 58 KB. The decision index is a rendered view (D60 amended) | Merged (286d4add) |
| T-hook | `decision-context.py`'s entry says it prints id and title only | Merged (4a2e81bd) |
| debt-claim | Debt slugs are claimed at merge, like decisions. Five debts filed | Merged (9b304772) |
| Box sweep | Every screen names a box through `boxTitle` (D259) | Merged (008a7ccc) |
| memory migration | 71 memory entries judged, each fact given a repo home | Merged (daaccd8d) |
| auto memory off | `autoMemoryEnabled: false`, once the migration landed | Merged (f642a5b5) |
| token-audit report | The token-budget audit report, record only | Merged (b74f9e79) |
| rulings | Two test-audit rulings recorded. Old docs-audit row names in comments follow L8 | 262f3351 |

Records and studies, also merged:

- Lane A's design: mockups and plan in `orders-a/`.
- The test audit: four Sonnet slices and the Opus plan in `docs/reviews/test-audit-2026-09-27/`.
- F5's verbiage list: `verbiage-blind/verbiage.csv`.
- Lane H's blind review: `cyberpunk-blind.md`.

Earlier PRs, done: PR 3B, the demo mirror (#467 to #477), and PR 4A (#466).

## In motion (state at 709ef385)

Every PR 4B lane is merged. Next: open PR 4B, wait for green CI, and merge with `make merge`.

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
  - The diagnosis: `server/match.py` ranks Hand Hammer first. The walk in `BoxBrowse.tsx` picks its box and landing by the largest pile of live copies across all matches, and never reads that rank. The owner confirmed that in-stock Hand Hammers did not surface until another box was picked.
  - The owner's ruling: `Rank before pile size (Recommended),Say when the best match is sold (Recommended)`. Lane F8 builds both on `ux/pr4b-F8`.
  - A second example (owner, same day): a search for "shadow" shows a Zed card before the card named Shadow. Sent to lane F8 to confirm the same cause.
- F9: an empty section must not show in the Inventory walk. The owner often opens the next section at the end of a capture, and it stays empty. The strip then counts it ("Section 10 of 11"), which breaks the back-to-front count while locating a card. Owner: `be careful about this change`. Default scope: the walk hides it (strip, "of N", ruler). Capture, Manage box and the move targets still show it, so it can be filled, renamed or deleted. It runs as one lane after F8, since both edit `BoxBrowse.tsx`. D264 (a section is an object that moves whole) and D260 (a card counts within its section) govern.

Before PR 4B merges:

- Main is red. The docs audit's `id claims` row fails on main's unclaimed slug
  `D302`, because PR #476 merged without its claim. The owner: `Fold it into PR 4B`.
  So PR 4B's merge claims it. Check at merge time that `make merge` claims a slug main already holds.
- The final head: linting only (Vale retired 2026-09-27), then the PR, green CI, and `make merge`.

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
- The final head gets linting only (Vale retired 2026-09-27), not a full `make check`: `Agreed and proceed`.

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

- B2, DEBT53: `yes build now`.
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
- The decision index (2026-09-27): `Derived view + pointer (Recommended)`. The ruling lives in
  the test audit's TIERS.md. One lane builds it after L2, beside L4.
- Token budget (2026-09-27): `Prune memory.md now, and then send an audit lane`. The audit lane
  measures every source loaded into each session and proposes a cut or a move per section. It
  writes a report under `docs/reviews/`. Nothing changes until the owner rules.
  The owner ruled on its four questions the same day. The rulings are in that report's last
  section. Two lanes build them: the edit hook, and one CLAUDE.md lane that also takes the
  decision index.
- Auto memory (2026-09-27, process only): `Migrate first, then off`. A lane gives each memory fact
  with no repo home a real home: a debt, a spec or a decision entry. It also proposes
  global-rule sentences for the owner. After it merges, `autoMemoryEnabled: false` goes into the project's
  `.claude/settings.json`. The session scratchpad is the per-session note file.
- Debt numbers (2026-09-28): `i think there's a straightforward way where they just get assigned numbers upon merge with CI`. A lane teaches the merge-time claim to number debts, as it numbers decisions. The memory lane's five drafted debts then land as slugs.
- The global-rule lines (2026-09-28, process only): the owner takes G1, G2 and G3 to a claude-settings session, with the two parent guard defects. The brief is in this session's scratchpad.
- F10 (2026-09-28), the owner's report: `if i type let's say punch first, or body rune (fully) then it shows no searches found, but if i type body run or punch firs then it does show up`.
- F5 and D276 (2026-09-27): `Keep "Go to" (Recommended)`. The palette keeps its D276 name.
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
- H, on the first mockups (current, A, B, C, desktop only): `all of the H concepts tend to just pick one color and stick to it, when the power of cyberpunk is its fusion of several loud color schema contrasting and clashing`. So no single-accent concept is the answer.
- H, same round: `neon noir was the closest of the dynamism though if i had to pick one`, then `none were good tho`. Neon Noir is the starting point, not the answer.
- H round 2 (owner, same day): `Mockup round 2: fusion (Recommended)`. Three multi-color concepts on Neon Noir's ground, Pricing and Home, desktop only.
- H round 2 verdict: `pretty underwhelming, neon noir and synthwave are again too mild`. The next step, on the owner's word: a new BLIND agent sees only the LIGHT mode and designs several novel many-color palettes. Colors only, no layout change. Owner: `super spicy, loud, color schema ... not just one color, MANYYY COLORS ... cyberpunk anime esque dark mode as though you're a league of legends pro`.
- H, the blind colorist's four palettes (Championship, Drift King, Overclock, Lantern District): `This version of H is absolute fire`. The same agent makes four more. Then H leaves PR 4B and becomes its OWN DEFERRED PR. Its palettes, sheet and method notes are committed as that PR's record.
- The docs-audit tiers (owner, same day): approved, with changes. Every ruling is in `docs/reviews/test-audit-2026-09-27/TIERS.md`, section "The owner's rulings". Line anchors convert and collapse into one row. Rows 20, 48 and 92 are cut. Q8 is yes. Row 17 and the CLAUDE.md decision index are still open.
- H leaves PR 4B (owner, same day): `abysall bloom might be gold -- love it. commit all the work done for  H and leave it all as something to come back to in its own PR`. The record is on branch `ux/h-record`, in its design-refs folder, h-palettes.
- Lane R, reap ownership (owner, same day): `Make reap stop only what the caller started ... tag each process reap starts with its owner's id, and let --confirm stop only processes carrying the caller's tag`. Narrowed: `do Blanket for the orchestrator and limited to its own tagged processes for an agent`.
- The Box number sweep (owner, same day): `In PR 4B, after A3 and F5 (Recommended)`. One Sonnet lane adds a shared browser `boxTitle`. It fixes the screens that show a box number: the Orders copy map, the run scope, the rescue, Capture and Home's status line. A check refuses a new typed `Box ${`. D259 (a box is shown only by its name) governs.
- Walk density: `Cards to pick at the stop (what's built)`.
- Test-audit Q1, the tiers: `Three tiers, agent proposes, you approve (Recommended)`. Q2: `Yes (Recommended)`.
- Start now: `L1, L3, L6, L7`. The owner asked for the other three options explained first.
- Vale: `Retire it, keep American spelling in docs-audit (Recommended)`. Lane L3 removes Vale.
  The spelling row learns markdown in lane L2. So the final head no longer runs Vale.
- Old demo seed: `Cut the old seed guards`. Lane L5. The heartbeat and coordinator: `Retire both (Recommended)`. Lane L10.
- Q8: `you haven't shown me the changes made to docs audit`. No docs-audit change is made yet. The owner sees the tier list and the merge families before any lane changes it.
- Search, one method (owner, 2026-09-28, on F11's review): `search should just be one sorta object/method that's called upon and used in uniform across the app`. So Sales matches SKU and set name too. The palette, the shortcut sheet and Capture's box filter move onto `matchQuery` as well. Codes: `Keep substring on codes (Recommended)`, as a field of the one matcher, not beside it. Lane F11b carries it. Its home is a D271 amendment.
