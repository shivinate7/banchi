# Test audit, slice 1: app/tests/*.spec.ts

Input for the Opus reviewer named in the owner's plan, 2026-09-27. This is evidence.
This is a first verdict. Nothing here decides what gets cut.

## Scope and method

44 spec files under app/tests/. Plus the shared helpers they import: fontsReady.ts,
iconTooltip.ts, machineWords.ts, moneyFace.ts, motionSettled.ts, routeExclusions.ts,
routeFixtures.ts, routeSweep.ts, routes.ts, shell.ts, textShape.ts. Plus three pending
lists: machine-words-allow.json, money-face-allow.json, text-shape-allow.json.

**Test count.** Counted with `grep -c "test("` per file. This is a floor, not the real
count, for files that generate tests in a loop. A loop can run over a case table, a
route list, or a width list. Sixteen files do this: brand, capture-undo, filters,
fulfillment, home, kit-data, match, gallery, locating, pull-confirm, scaffold,
pricing-markdown, section-ruler, review, orders, run-panel, pricing. match.spec.ts is
the extreme case. It has 3 `test(` call sites in source. One sits inside a loop over
match.cases.json. That file holds more than 20 rows per match.spec.ts's own check. So
the real count is 22 or more, not 3. This note is per file. It is not hand-counted for
all sixteen. A hand count would need `npx playwright test --list` per file. That is a
Playwright invocation. The hard rules reserve Playwright invocations for `make
design-check`. A number alone does not earn that cost here.

**What it protects.** Read from each file's own header comment. Every file in this
directory carries one. Each header is unusually explicit about the owner complaint or
defect that caused the file to exist. Quoted in spirit here, not verbatim, to stay under
the copyright limit.

**Decision currency.** Cross-checked against docs/decisions/'s own text (`grep -i
supersede`). Also checked against CLAUDE.md's decision index. Not checked against `make
map` for every one of the roughly 150 unique D-number citations found. That would be
about 150 separate commands for one slice. Two citations were found actively superseded
in a way that matters. D48 is superseded by D180, 2026-09-13. D194 is superseded by
D284, 2026-09-23. Every file citing either is checked below. The check asks whether the
citation is a live assertion or a historical comment. No other citation showed
supersession language pointed at it.

**Last real defect.** Read from `git log --oneline -- app/tests/<file>`. Filtered for
these words in the subject line: red, caught, regress, defect, fail, fix, bug, observed.
A file with commits but no matching subject is marked unknown. Unknown means that no fix
commit named it. It does not mean the file never caught anything.

**Cost.** docs/specs/verification-cost.md names exactly one per-file figure.
orders.spec.ts: 11.8s for 57 cases, measured 2026-09-17. That file has since grown past
57 test( call sites. Every other file's cost is unmeasured here. The document's own
total is 648 cases over 26 spec files, 117.5s. That total is also stale against today's
44 files. It does not divide cleanly per file.

**Overlap.** Read from cross-references each header already makes to a sibling file.
Also read from the shared route-sweep infrastructure (routeSweep.ts, routesFromNav).

**A note on stubbing.** Most owner-side specs stub every server route on purpose. Each
says so loudly in its header. This is not the "proves nothing" pattern. It is a
deliberate choice. It proves a route is reachable. It proves the route gets the right
body. The choice answers a real, recorded failure: three fully tested routes shipped
with zero client functions (docs/GATES.md step 7). A dozen headers repeat this argument.
This note replaces repeating it 20 times below. One file stubs away the exact thing
under test: demo-coverage.spec.ts. It gets its own section, DEBT47 below.

---

## Summary table

| Spec | Tests | Verdict | Reason |
|---|---:|---|---|
| boxmap.spec.ts | 13 | KEEP | small, live feature, caught 2 real bugs recently |
| brand.spec.ts | 20 | KEEP | only spec proving the generated mark actually draws |
| button-stack.spec.ts | 1 | KEEP | cheap, self-discovering, no roster to rot |
| capture-claims.spec.ts | 44 | KEEP | owner's most-used screen, real fix history |
| capture-section.spec.ts | 18 | KEEP | real fix history, own screen mechanism |
| capture-undo.spec.ts | 34 | KEEP | catches sequencing bugs types cannot |
| card-variants.spec.ts | 4 | KEEP | pinned to the owner's own real SKU collision |
| confirm-identity.spec.ts | 7 | KEEP, SHRINK boot | duplicate boot fixture with correct-answer.spec.ts |
| correct-answer.spec.ts | 2 | KEEP, SHRINK boot | duplicate boot fixture with confirm-identity.spec.ts |
| cursor.spec.ts | 10 | KEEP | rule-based, caught 41 of 65 real defects |
| demo-coverage.spec.ts | 14 | KEEP screens, SHRINK network case | DEBT47: seal case tests a fake rule |
| filters.spec.ts | 39 | KEEP | shared kit control, real review-round catches |
| fulfillment.spec.ts | 61 | KEEP | only instrument for the Fulfiller persona |
| gallery.spec.ts | 37 | KEEP | closes a real "specimen never rendered" defect |
| graveyard.spec.ts | 6 | KEEP | small, pinned to a real owner bug report |
| home.spec.ts | 12 | KEEP | guards a headline figure against over-counting |
| icon-button.spec.ts | 11 | KEEP | five named, previously-shipped defects |
| inventory-sets.spec.ts | 6 | KEEP, watch | rebuilt twice in one day, still churning |
| inventory.spec.ts | 161 | KEEP, SPLIT | size forces 4 files to duplicate its boot |
| kit-data.spec.ts | 34 | KEEP | shared primitives, real fix history |
| live-reconcile.spec.ts | 11 | KEEP | proves a two-step money gate opens a sheet |
| locating.spec.ts | 4 | KEEP | pinned to a real owner bug, wrong section math |
| machine-words.spec.ts | 1 | KEEP | closes a static-analysis gap on purpose |
| match.spec.ts | 3 (22+ real) | KEEP, consider fold | narrow, could live inside kit-data.spec.ts |
| money-face.spec.ts | 3 | KEEP | one rule, D221, CSS alone cannot see it |
| motion-live.spec.ts | 1 | KEEP, gap noted | proves wiring, not the rig; rig needs a human |
| motion.spec.ts | 23 | KEEP, gap noted | proves arithmetic only, same rig caveat |
| nav.spec.ts | 20 | KEEP | only spec on the shell's own keyboard |
| order-walk.spec.ts | 5 | KEEP | closes a real clock-timed-undo defect |
| orders.spec.ts | 116 | KEEP, SPLIT | largest owner screen, real recent fix history |
| page-edge.spec.ts | 1 | KEEP | pinned to a real 330px owner-reported defect |
| phone.spec.ts | 7 | KEEP | only spec that opens phone-width overlays |
| pricing-markdown.spec.ts | 31 | KEEP | own file on purpose, protects pricing.spec.ts |
| pricing.spec.ts | 125 | KEEP, SPLIT | second-largest, real recent fix history |
| product-history.spec.ts | 5 | KEEP | small, names a specific chart-shape trap |
| pull-confirm.spec.ts | 5 | MERGE into fulfillment.spec.ts | that file's own header claims full coverage |
| revenue.spec.ts | 28 | KEEP | fake clock, real fix history |
| review.spec.ts | 51 | KEEP | owner's most-used screen after Capture |
| run-panel.spec.ts | 79 | KEEP, SPLIT | money-spend gate, large test count |
| scaffold.spec.ts | 9 | KEEP | derives its own roster, cannot drift from ROUTES |
| section-ruler.spec.ts | 3 | KEEP | pinned to a real owner bug report |
| shipping.spec.ts | 16 | KEEP | one of 3 lanes, own route, seals the server |
| text-shape.spec.ts | 2 | KEEP | correctly replaced D194 with D284 |
| wide.spec.ts | 2 | KEEP | only spec above 1440px, measured a real defect |

**Cross-cutting flag, not a per-file verdict.** Six files each walk every route on their
own: cursor.spec.ts, nav.spec.ts, phone.spec.ts, wide.spec.ts, page-edge.spec.ts,
scaffold.spec.ts. Each checks one different property. Cursor checks cursor state. Nav
checks keyboard chords. Phone checks overlays. Wide checks layout above 1440px.
Page-edge checks left-edge alignment. Scaffold checks the page frame. The assertions do
not overlap. Each is real and named to a real defect. But the navigation cost is paid
six times over. One walk could serve all six. This is the same redundancy the
text-shape, machine-words and money-face trio already solved with routeSweep.ts. This
is the clearest concrete SHRINK candidate here. It costs nothing in coverage. Fold the
six navigation loops into one shared sweep. Keep all six assertion sets.

---

## Per-spec entries

### boxmap.spec.ts
13 tests, 360 loc.
- **Protects:** the box map's edit-mode flow. A drag queues a move. Nothing writes until
  Confirm. Confirm sends the whole draft as one request with fresh digests. This stops a
  half-applied drag from silently reordering the owner's real boxes.
- **Product or mechanism:** product. Routes are stubbed. The store is never touched.
- **Decisions:** D264, current.
- **Last real defect:** d4442491 fixed the card-blind Confirm gate. e7341174 fixed the
  Map carrying the layout token. Both are real. Both are recent.
- **Cost:** unmeasured.
- **Overlap:** none direct. Shares the general stub pattern with other screen specs.
- **Note:** the file's own header flags that its prior version was pinned to a retired
  ruling. It says so rather than carrying that silently. The current file fixes it.
- **Verdict: KEEP.** Small. Live feature. Two real catches this week.

### brand.spec.ts
20 tests, 918 loc.
- **Protects:** the generated logo mark. It must draw at the right cut, at every size.
  Before this file, nothing in the suite mentioned the mark. It could stop rendering at
  all six call sites and the suite would stay green.
- **Product or mechanism:** product. The header states an observed-red mutation proof.
- **Decisions:** D102 (current), D134, D136, D204 (current, cited for context).
- **Last real defect:** 0e477bba, "the chevron had no rule at all... restored." Real.
- **Cost:** unmeasured. 918 loc for 20 tests is heavy per test.
- **Overlap:** none. Unique subject.
- **Verdict: KEEP.** Only instrument for the brand at all.

### button-stack.spec.ts
1 test, 183 loc.
- **Protects:** same-role buttons stacked in one panel share a width. The owner's own
  complaint, 2026-09-13, about lopsided button rows.
- **Product or mechanism:** product. It finds its own subjects by walking the DOM. It
  groups by sector, variant and size. It does not read a declared class. A stack built
  without the CSS hook is still caught.
- **Decisions:** D195, current.
- **Last real defect:** unknown. Only 2 commits touch this file. Neither names a fix.
  One is the creation commit. One is an id-claim commit.
- **Cost:** unmeasured. One test sweeps every route. Likely cheap.
- **Overlap:** none.
- **Verdict: KEEP.** Cheap. Well-argued. No roster to go stale.

### capture-claims.spec.ts
44 tests, 1744 loc.
- **Protects:** every control on the Capture screen: box, game, set hint, finish,
  rarity. This is the screen the owner spends the most hours in. Its own header says
  nothing exercised these controls before this file existed.
- **Product or mechanism:** product. No capture is ever taken. Routes are stubbed.
- **Decisions:** D10, D101, D118, D142, D145, D20, D205, D211, D218, D22, D23, D27,
  D299, D56, D65. All current.
- **Last real defect:** d63b8652 fixed six owner review items. 8bc82538 fixed R2-search
  and R2-date. Both real and recent.
- **Cost:** unmeasured. Large file.
- **Overlap:** capture-undo.spec.ts and capture-section.spec.ts are explicit siblings.
  Each header explains why the split is real.
- **Verdict: KEEP.**

### capture-section.spec.ts
18 tests, 883 loc.
- **Protects:** the sub-box section picker. The row fills correctly. Bracket keys step
  it. S sends and advances the pick. A stale pick falls back honestly. A divider press
  never moves the shutter beneath it.
- **Product or mechanism:** product. The store and server half is proven by a separate
  harness test. This proves the screen only.
- **Decisions:** D118, D128, D164, D260, D264. Current.
- **Last real defect:** 9b0bf1c2, section count went stale on undo and remove.
  e4915950 fixed all 8 Opus review findings. Both real and recent.
- **Cost:** unmeasured.
- **Overlap:** capture-undo.spec.ts shares the canvas-as-camera trick. It is documented,
  not copied blind.
- **Verdict: KEEP.**

### capture-undo.spec.ts
34 tests, 1595 loc.
- **Protects:** the 10-deep undo stack on Capture. A wrong walk-back here deletes the
  wrong physical card's record from a real box. The header names the exact bug class a
  type system cannot catch: sequential deletes where the next one is only legal because
  the last one succeeded.
- **Product or mechanism:** product. This is the one capture file that does capture.
  Routes are always intercepted.
- **Decisions:** D10, D101, D117, D118, D136, D153, D164, D196, D211, D218, D41, D58,
  D67. Current.
- **Last real defect:** 3220c7b3 fixed a ref-timing bug at the cause. 10ca21d9 fixed a
  pause and play flake, and a real trigger-rearm race. Both real. The second is exactly
  the bug class this file argues only a browser can catch.
- **Cost:** unmeasured. Largest capture-family file.
- **Overlap:** capture-claims.spec.ts and capture-section.spec.ts, explicit sibling split.
- **Verdict: KEEP.**

### card-variants.spec.ts
4 tests, 285 loc.
- **Protects:** two SKUs that differ only by set. They must not collapse into one
  indistinguishable chooser tile. Pinned to the owner's own real collision: Mind Rune,
  SKU 9139852 against 9277742.
- **Product or mechanism:** product. Every assertion reads rendered text. It never reads
  the data object passed in. The header argues this is the whole point.
- **Decisions:** D213, current.
- **Last real defect:** 0ebe59cf fixed a regression from an N5 placeholder rename. Real.
- **Cost:** unmeasured, small.
- **Overlap:** none. Deliberately its own fixture, not inventory.spec.ts's.
- **Verdict: KEEP.**

### confirm-identity.spec.ts
7 tests, 414 loc.
- **Protects:** the "The listing is right" confirm control. This covers a held card
  whose camera-drawn name is wrong. It is the misread-name case
  correct-answer.spec.ts cannot reach.
- **Product or mechanism:** product. Own minimal boot. Everything stubbed. Real store
  never touched.
- **Decisions:** D118, D252, current.
- **Last real defect:** unknown by subject-line match. 0e50f2c3 and 13ab38a7 are close
  to fixes, correcting a sampling technique.
- **Cost:** unmeasured, small to medium.
- **Overlap:** correct-answer.spec.ts is an explicit sibling on the same screen area.
  Each keeps its own small duplicate boot fixture rather than sharing one. The reason:
  importing that file would re-run every test() it registers.
- **Verdict: KEEP, SHRINK the boot fixture.** The test cases are distinct and earn their
  place. The duplicated boot lines are real, avoidable waste. A shared non-spec helper
  would remove it without re-running either file's tests.

### correct-answer.spec.ts
2 tests, 281 loc.
- **Protects:** the "this answer was wrong" listing-correction control on
  #/inventory. The owner asked for exactly this control, quoted verbatim in the header.
- **Product or mechanism:** product. Own minimal boot. Real store never touched.
- **Decisions:** D252, D46, current.
- **Last real defect:** unknown by subject-line match. 0ee3a7d8 is the creation commit,
  not a later fix.
- **Cost:** unmeasured. 281 loc for 2 tests is the highest loc-per-test ratio this
  small. Almost all of it is the boot fixture.
- **Overlap:** confirm-identity.spec.ts, see above. Reuses the same fixture card,
  Thievul 8937370, that inventory.spec.ts uses.
- **Verdict: KEEP, SHRINK the boot fixture.** Same note as confirm-identity.spec.ts.

### cursor.spec.ts
10 tests, 913 loc.
- **Protects:** every control tells the pointer the truth: pointer, text, or
  not-allowed. Measured 41 of 65 real controls wrong before this file existed. Nothing
  else could see it, including make design-check at the time.
- **Product or mechanism:** product. It classifies by element state, tag, type and
  disabled. It never reads a pinned roster of expected answers.
- **Decisions:** D110, D118, D43, D50, D70. Current.
- **Last real defect:** 96efee72, "the first fix snapped." Real. 64153f8f fixed the
  route-harvest mechanism itself.
- **Cost:** unmeasured.
- **Overlap:** shares routesFromNav route harvest with nav.spec.ts and wide.spec.ts.
  See the cross-cutting flag above.
- **Self-flagged gap:** the file's own header admits a control that does not render in
  the empty seeded store is not checked at all.
- **Verdict: KEEP.**

### demo-coverage.spec.ts
14 tests, 418 loc.
- **Protects:** the published demo build, dist-demo/, actually shows real data on every
  screen a reviewer grades it on. This is the only spec that runs against the demo's
  static artifact, not the dev server. It catches broken image paths, a static-host
  base-path bug, or a stale locator against fixed demo data. No other spec sees these.
  Every other spec stubs the dev server.
- **Product or mechanism:** product, of the demo build specifically.
- **Decisions:** D183, D227, D271, D277, D282, D295, D301. Current.
- **Last real defect:** very active. d0271ce7 fixed two real failures, honestly.
  0343dbb4 and 9d68d335 fixed an Orders-walk race at its actual cause. 91980fff fixed 5
  more stale locators, run 4 times green. d59712f3 fixed three real CI failures at
  cause. This is the most recently and repeatedly fixed file in this slice.
- **Cost:** unmeasured. Skipped by name when dist-demo/ does not exist. Costs nothing on
  an ordinary make design-check.
- **Overlap:** none for the screen-coverage half.
- **Verdict: KEEP the screen-coverage cases.** They are real, recent, and the only place
  these defects can be seen. **SHRINK the network-seal case. See DEBT47 below.**

### filters.spec.ts
39 tests, 689 loc.
- **Protects:** the shared filter bar, hide toggle, sortable table header and
  match-highlight. These are used across every screen that filters a list. A defect
  here breaks filtering everywhere at once, not on one screen.
- **Product or mechanism:** product. Drawn on a router-less, store-less test page, like
  kit-data.spec.ts.
- **Decisions:** D118, D132, D270, D288. Current.
- **Last real defect:** 92b5d4ba, 1121724d, 6a4715dc fixed readSort ignoring a written
  direction when the key was absent. bdbc22cf fixed eleven review findings. The header
  says every guard here was observed red on its own defect before the fix.
- **Cost:** unmeasured.
- **Overlap:** match.spec.ts covers the underlying matcher alone. This file covers what
  is built on top. A real, argued split.
- **Verdict: KEEP.**

### fulfillment.spec.ts
61 tests, 3391 loc.
- **Protects:** every row of docs/DESIGN.md's Fulfillment table. This is the only
  instrument for the Fulfiller persona: a retired, non-technical user with no other way
  to be checked. Every ratio is computed from rendered colors. None is copied from the
  doc. A token change not re-argued in the doc breaks something here.
- **Product or mechanism:** product. The flagship "battery," applied to every screen
  state. That includes loading, failure, empty, and missing-photo, not only the two
  easy ones.
- **Decisions:** D10, D115, D118, D13, D136, D193, D21, D212, D218, D259, D28, D288,
  D31, D57, D93. Current.
- **Last real defect:** 474d6a5f fixed the glyph-size blocker. 2d5a6092 fixed real
  column alignment and a null test. de228859 was a round-2 review fix pass. 44edb156
  fixed the review's 9 findings on Cards to pull. Real and frequent.
- **Cost:** unmeasured. Largest owner or Fulfiller spec by loc. Likely one of the most
  expensive single files in make design-check.
- **Overlap:** pull-confirm.spec.ts covers 3 of the same 9 floors, against one
  component. This file's own header says it now covers all nine against the view.
- **Verdict: KEEP.** Irreplaceable. The only Fulfillment instrument.

### gallery.spec.ts
37 tests, 1213 loc.
- **Protects:** the kit sheet, #/gallery, actually renders every row shape the product
  can draw. The header documents a real, closed defect. The DEPARTED and POOLED row
  shells existed in code. They were unreachable on the sheet, because the fixture never
  gave a specimen the right shape. A specimen never rendered is not a specimen. The
  sheet stayed green through it.
- **Product or mechanism:** product. The mutation proof is documented: give the
  DEPARTED fixture a numeric slot, the shell drops, the case reports 0 where it wants 1.
- **Decisions:** D118, D119, D24, D269, D272, D68, D71. Current.
- **Last real defect:** 3101422f fixed a stale gallery.spec.ts case. 27bf0e09 fixed
  three integration-only regressions the whole-suite design-check found. Real.
- **Cost:** unmeasured.
- **Overlap:** none direct.
- **Verdict: KEEP.** A textbook example of a guard that once could not see its subject,
  fixed and documented as such.

### graveyard.spec.ts
6 tests, 329 loc.
- **Protects:** the graveyard screen, after a real owner bug report quoted in the
  header. Measured on a copy of the owner's real store: 1,358 departed rows, 264 tagged
  moved, and not one moved row was ever also sold or retired. The screen now draws
  exactly 3 tabs, not 5.
- **Product or mechanism:** product, client half only. The server-side filter is proven
  by reading the Python function, not by this file.
- **Decisions:** D134 (amended 2026-09-26, this file matches the amendment), D196.
  Current.
- **Last real defect:** bccd51cd, the creation commit, driven by a real bug.
- **Cost:** unmeasured, small.
- **Overlap:** none direct.
- **Verdict: KEEP.**

### home.spec.ts
12 tests, 489 loc.
- **Protects:** Home's "cannot be filled" headline figure. It must not over-count an
  order the feed already closed. A wrong figure sends the owner chasing orders that
  need no chasing.
- **Product or mechanism:** product. It hands the client an inconsistent wire shape on
  purpose, to prove the client does not blindly trust the wire's own filtering.
- **Decisions:** D114, D121, D202, D218, D63. Current.
- **Last real defect:** unknown by subject-line match. The 16 commits here are feature
  build-out, not named fixes.
- **Cost:** unmeasured.
- **Overlap:** none direct.
- **Verdict: KEEP.**

### icon-button.spec.ts
11 tests, 306 loc.
- **Protects:** five named, previously-shipped IconButton defects. The 40px hit area. A
  tooltip clipped inside a sheet. A long-press firing a ghost click. Toast-close
  contrast. Glyph sizing. Each is documented as measured red before the fix.
- **Product or mechanism:** product.
- **Decisions:** D118, D288. Current.
- **Last real defect:** 4545bd4b fixed the icon tooltip clipped on inventory's first
  row. a917bcb1, 474d6a5f, 1121724d are real and recent.
- **Cost:** unmeasured, small.
- **Overlap:** the 40px hit-area assertion also appears in cursor.spec.ts,
  phone.spec.ts and kit-data.spec.ts, from different angles. Flagged for Opus to
  confirm the four do not silently duplicate coverage.
- **Verdict: KEEP.**

### inventory-sets.spec.ts
6 tests, 353 loc.
- **Protects:** the owner's "By set" Inventory view. One set at a time. A picker.
  Quantity from the server's own qty field. A tap lands on the ordinary box walk.
- **Product or mechanism:** product, client half. The server aggregation is verified in
  its own route's header.
- **Decisions:** D172, D264, D285, D293, D301. Current. D293 is the day-of ruling this
  file exists for.
- **Last real defect:** 8145ab4d, N1 review fixes. e9187b78, a fix round. Real.
- **Cost:** unmeasured, small.
- **Overlap:** shares fixture family with inventory.spec.ts and boxmap.spec.ts.
- **Note:** the header says this file was rebuilt twice in one day, 2026-09-27, as the
  feature's own design changed under it.
- **Verdict: KEEP, but flag as still churning.** Re-check once the "By set" feature
  stops moving.

### inventory.spec.ts
161 tests, 8358 loc.
- **Protects:** #/inventory, the owner's one view of stored cards. This screen founded
  this whole testing culture. The header names the founding defect: three fully tested
  routes shipped 2026-08-23 with green harness and green make check, and no control on
  any screen. The owner found them by looking and not finding them.
- **Product or mechanism:** product. It checks reachability of every client call the
  screen owns. The real store is never touched. Writes are asserted from the
  intercepted request body.
- **Decisions:** about 46 unique citations, spanning D10 through D194. All current. The
  one D194 reference is a historical comment about an old caption rule. It is not an
  active word-ceiling assertion. Harmless.
- **Last real defect:** constant and recent. 01dced24 fixed a phone shutter clipped by
  the tab bar and two stale fixtures. 55536c68 and 3363363a fixed a wipe-after-re-pick
  bug and a wrong undo name. 82d91e6b fixed review findings F1 through F7. This file is
  touched by 183 commits. By that count, it is the most defect-catching file here.
- **Cost:** unmeasured directly. By loc and test volume, almost certainly the most
  expensive file in make design-check.
- **Overlap:** card-variants.spec.ts, correct-answer.spec.ts, confirm-identity.spec.ts
  and section-ruler.spec.ts each build their own small duplicate fixture. Each says why:
  importing a spec file re-runs every test() it registers. This file's size forces
  duplication in four other files.
- **Verdict: KEEP, indispensable.** Its size is a real, named cost. Flag for a SPLIT by
  screen area: box operations, search and filter, the copies panel, the Manage box
  sheet. Also extract its private boot helper into a shared module, so the four
  dependent files stop hand-rolling their own copies.

### kit-data.spec.ts
34 tests, 725 loc.
- **Protects:** the kit's data primitives and the one shared search matcher. Pure
  functions are checked directly. Every primitive is checked drawing correctly at 4
  widths and both themes on a dedicated test page.
- **Product or mechanism:** product. Split into a no-browser half and a browser half.
- **Decisions:** D118, D195, D288. Current.
- **Last real defect:** 01dced24, 1121724d, 6a4715dc are real. 46a86a6e fixed one clear
  path per facet and a contrast issue. b0cd1817 fixed focus, D118 widths, the thumb
  floor, contrast and the matcher after review.
- **Cost:** unmeasured.
- **Overlap:** match.spec.ts covers the matcher, see that entry. filters.spec.ts is
  built on the same primitives from the caller's side.
- **Verdict: KEEP.**

### live-reconcile.spec.ts
11 tests, 399 loc.
- **Protects:** the fourth CLI command, reconcile --live, reached from a screen. The
  strongest cases are absences: the settle control does not exist before a preview has
  answered, and the preview itself carries write: false.
- **Product or mechanism:** product. No real request is ever made.
- **Decisions:** D118, D174, D218, D33, D87. Current.
- **Last real defect:** 9272a77c fixed the full-suite reds, joining the runs sheets to
  the kit's overlay stack. Real.
- **Cost:** unmeasured.
- **Overlap:** none direct.
- **Verdict: KEEP.**

### locating.spec.ts
4 tests, 420 loc.
- **Protects:** where a card is, said the same way on every screen. Pinned to a real
  owner bug report about sections passing their container's width. Also pinned to
  D260's section-relative numbering, card 1 at the far back.
- **Product or mechanism:** product. The fixture is the server's own arithmetic written
  out by hand. A departed card's place and its neighbour's place read as the same
  string except for the mark.
- **Decisions:** D116, D259, D260. Current.
- **Last real defect:** 1a647ec4 closed five gaps against the mockup. f79eaa0e fixed the
  place pill's reading order. Real.
- **Cost:** unmeasured, small.
- **Overlap:** own minimal fixture, not inventory.spec.ts's.
- **Verdict: KEEP.**

### machine-words.spec.ts
1 test, 103 loc.
- **Protects:** D196's own gap. A machine-internal word, a decision id, a repo path, a
  pipeline noun, reaching the screen through a channel the static AST check cannot see.
  A relayed server string. The demo's own fixture text. Anything composed at runtime.
- **Product or mechanism:** product. Shares one sweep, routeSweep.ts, with
  text-shape.spec.ts and money-face.spec.ts, every route once at 1440 and 390.
- **Decisions:** D196, D269. Current.
- **Last real defect:** 2cddeb9f fixed a ReferenceError in the phone-drawer route
  harvest. Real, mechanism-level.
- **Cost:** unmeasured. Cheap by construction, one page load per route shared across
  three concerns.
- **Overlap:** deliberately shares infrastructure with text-shape.spec.ts and
  money-face.spec.ts. This is the good pattern the six-file walk group should follow.
- **Verdict: KEEP.**

### match.spec.ts
3 test( call sites, 74 loc. Real count is 22 or more: one test per row of
match.cases.json, plus a whole-file emptiness check, plus a memoization-regression
timing test.
- **Protects:** kit/match.ts's matcher, against a shared, data-driven case table. A
  Python candidate step can read and run the same table. One matcher gets one proof
  across languages. The timing test protects a real memoization regression.
- **Product or mechanism:** product. The matcher is shared production code. No browser.
- **Decisions:** none cited.
- **Last real defect:** 761a7f0f and 82f8011f, Search-server rounds R4 and R5. Real,
  cross-language regression work.
- **Cost:** unmeasured. No browser, likely one of the cheapest files here per test.
- **Overlap:** kit-data.spec.ts already carries the matcher's hand-written cases per its
  own header. The split is argued, not accidental. Two files test one function.
- **Verdict: KEEP.** Both halves are real and cheap. Consider folding this file into
  kit-data.spec.ts as a section. That is a reorganization, not a coverage change.

### money-face.spec.ts
3 tests, 115 loc.
- **Protects:** D221, every dollar figure on screen is drawn in the mono face. CSS
  alone cannot tell a dollar figure from a SKU. Both can be mono, bold, tabular-nums.
  This reads what the span actually holds.
- **Product or mechanism:** product. Shares routeSweep.ts with the other two text checks.
- **Decisions:** D221, current.
- **Last real defect:** 2cddeb9f, shared mechanism fix, see machine-words.spec.ts.
- **Cost:** unmeasured. Cheap by shared-sweep construction.
- **Overlap:** deliberately shares infrastructure with machine-words.spec.ts and
  text-shape.spec.ts.
- **Verdict: KEEP.**

### motion-live.spec.ts
1 test, 447 loc.
- **Protects:** the motion trigger's DOM wiring in a real browser, against the real
  capture screen. The mode toggle arms the machine. The sampler reads real video
  frames. A settle becomes a fire. A fire with no box selected counts as dropped rather
  than silently vanishing.
- **Product or mechanism:** product, but honestly limited. The header states plainly
  that real lighting, real foil and the real feeder rhythm sit outside what a
  browserless test can reach. That is Gate C's job, done by hand at the rig.
- **Decisions:** D19, D218, D81, D84. Current.
- **Last real defect:** eac72bd1 gave a feeder that never rests a second trigger.
  e3c9f3e0 fixed two defects the first post-D81 rig sessions found. c74b0cfd stopped
  the fixture betting on a sleep. Real. That last one fixed the test itself.
- **Cost:** unmeasured.
- **Overlap:** motion.spec.ts is the pure-arithmetic sibling, no case overlap.
- **Verdict: KEEP, with a self-documented gap.** This file and motion.spec.ts together
  cannot substitute for a real rig session. The repo already says so.

### motion.spec.ts
23 tests, 677 loc.
- **Protects:** the motion state machine's arithmetic, against hand-built synthetic
  frame sequences with an exact answer key. Same honest limit as motion-live.spec.ts.
- **Product or mechanism:** product. No page, no server. A pure class.
- **Decisions:** D131, D81, D84. Current. D81 and D84 amend themselves, not each other.
- **Last real defect:** e3c9f3e0, fixed two defects the first post-D81 rig sessions
  found. Real.
- **Cost:** unmeasured. No browser, likely cheap.
- **Overlap:** motion-live.spec.ts, disjoint scope by design.
- **Verdict: KEEP.**

### nav.spec.ts
20 tests, 1005 loc.
- **Protects:** the shell's own keyboard: the comma-then-letter jump, and the
  Cmd-arrow ring step. This is the first test this app ever had of its own chrome.
  Strongest cases: the step never wraps, a bare arrow is not the shell's, a held Cmd
  inside a text field belongs to the caret.
- **Product or mechanism:** product.
- **Decisions:** D105, D109, D134, D174, D192, D20, D275, D276, D291, D298, D43, D51,
  D70, D86, D95. Current.
- **Last real defect:** 706776ff fixed Home's Review tile disagreeing with a run's real
  phase. 64153f8f fixed the cursor sweep's own route discovery. Real.
- **Cost:** unmeasured.
- **Overlap:** shares routesFromNav with cursor.spec.ts and wide.spec.ts. See the
  cross-cutting flag.
- **Self-documented gap:** Playwright fires keys through the debug protocol, never the
  browser's own native shortcuts. This file cannot prove Chrome or Safari declines to
  go Back on the same chord. Stated plainly in the header.
- **Verdict: KEEP.**

### order-walk.spec.ts
5 tests, 414 loc.
- **Protects:** OrdersWalkPane's own undo. Closes a real, shipped defect: RowAction
  used to drop a copy's Undo 20 seconds after the pull, on a hard clock, even mid-walk.
  docs/specs/undo.md rules that out everywhere. Replaced with a rank: newest pull keeps
  Undo.
- **Product or mechanism:** product. Scoped tightly. It does not touch what a pull
  writes or which copy it claims, by design.
- **Decisions:** D118, D136, D164, D252. Current.
- **Last real defect:** ce6d9cc6 fixed the walk's over_fulfilled bug: pickOrderFor
  stopped falling back to for[0]. Real.
- **Cost:** unmeasured, small.
- **Overlap:** orders.spec.ts, explicit non-overlap by design.
- **Verdict: KEEP.**

### orders.spec.ts
116 test( call sites, some inside loops so the real count is higher, 4414 loc.
- **Protects:** #/orders. The grouped-by-buyer walk. A held-copy conflict. The
  aim-checked pull, capture_id from the pressed row, never the first pick on the line.
  All six reasons render, including the structural zeros. The header names the founding
  defect again: step 7b shipped with three missing routes while every static check was
  green.
- **Product or mechanism:** product. No real request is ever made.
- **Decisions:** D113, D114, D118, D123, D132, D171, D181, D193, D203, D209, D212,
  D218, D221, D24, D274, D285, D296, D50, D57, D58, D63, D90, D91, D96. Current. D96
  reads as historical context for D90's numbering. It is not a live assertion here.
- **Last real defect:** a59963b8 pinned scrollY for a real, repeat CI red on a D118
  rect-diff. 3e0ecfed reconciled counts and fixed four more findings. a5b6a357 fixed the
  orders-sort fixture's walk refs. Real and recent.
- **Cost:** the one measured figure in this slice, 11.8s for 57 cases, 2026-09-17. Stale
  against today's larger test count.
- **Overlap:** order-walk.spec.ts, disjoint by design.
- **Verdict: KEEP, indispensable.** Same SPLIT flag as inventory.spec.ts. 4414 loc is
  large enough that a seam is worth a look: buyer grouping, the walk, the reasons panel.
  This is less urgent than inventory's forced duplication. No file copies this one's boot.

### page-edge.spec.ts
1 test, 109 loc.
- **Protects:** one left edge for every screen, D197. Pinned to a real owner
  screenshot: #/pricing's content started about 330px further right than
  #/review or #/inventory at the same width. Cause: margin auto centered a
  narrower page cap inside the shell column.
- **Product or mechanism:** product. The assertion is relative: every route's left edge
  equals Home's, within 1px. Never a hard-coded pixel.
- **Decisions:** D197, current.
- **Last real defect:** unknown by subject-line match. Only 2 commits touch this file.
- **Cost:** unmeasured, cheap. One sweep.
- **Overlap:** shares route-harvest style with wide.spec.ts.
- **Verdict: KEEP.** No catch since creation. The defect it guards was real and
  specific.

### phone.spec.ts
7 tests, 710 loc.
- **Protects:** the owner-side shell at phone width. Nothing else reaches here.
  cursor.spec.ts explicitly cannot, it scopes to .bn-side, hidden below 768px. The
  header states the real finding: a route-only sweep finds 3 short controls. A sweep
  that opens menus, sheets, the palette, the hold panel and the toast stack finds 25.
- **Product or mechanism:** product. It measures the hit area at the four cardinal
  points of the required 40px box. It does not measure the declared box size. This
  needs no forgiveness list.
- **Decisions:** D117, D134, D204, D266, D288, D291. Current.
- **Last real defect:** bccd51cd, shared graveyard fix. 8a5f09a8 taught a redirect route
  as a real route shape to both this file and the scaffold sweep. Real.
- **Cost:** unmeasured.
- **Overlap:** hit-area assertion style overlaps icon-button.spec.ts, see that entry.
- **Verdict: KEEP.**

### pricing-markdown.spec.ts
31 tests, 978 loc.
- **Protects:** #/pricing's Live tab, over live TCGplayer listings. Kept in its own
  file so pricing.spec.ts never had to change to add this feature. pricing.spec.ts is
  the gate the underlying source seam was built against. That is what proves the second
  source cost the first one nothing.
- **Product or mechanism:** product. No real request is ever made. The write is
  recorded, never performed.
- **Decisions:** D101, D103, D107, D118, D197, D218, D221, D267, D273, D277, D28, D54,
  D62, D99. Current.
- **Last real defect:** 7f5606c7, "the charts were wired to runs, so a live listing
  could be marked down but never looked at." Real.
- **Cost:** unmeasured.
- **Overlap:** pricing.spec.ts, deliberately kept separate.
- **Verdict: KEEP.**

### pricing.spec.ts
125 test( call sites, some inside loops so the real count is higher, 4345 loc.
- **Protects:** #/pricing. Same founding argument as inventory.spec.ts and
  orders.spec.ts. Strongest cases are absences: a suggested row writes no key, a Tab
  across one writes nothing, a snap onto a blank column writes nothing. A suggestion
  silently written to overrides would make changing the preset silently change nothing.
- **Product or mechanism:** product. No real request is ever made. The write to
  prices.json is recorded, never performed.
- **Decisions:** D103, D115, D118, D156, D168, D181, D196, D20, D218, D269, D273,
  D277, D278, D28, D301. Also D48, D49, D54, D56, D59, D62, D79, D86, D98, D99. Current.
  The D48 reference names D48's cart as a real fixture case's shape. It does not assert
  D48's retired mechanism.
- **Last real defect:** 7c145028 fixed a flag column, name and number consistency, held
  lock parity. 65e04b85 fixed a number-chip suppression to a token match. a595a8cd
  fixed Clear firing on a failed read. 2ba430b2 fixed the send matrix. Nine message
  tests were shown red first against it. Real, dense, recent.
- **Cost:** unmeasured. Second-largest file here by loc.
- **Overlap:** pricing-markdown.spec.ts, deliberately disjoint.
- **Verdict: KEEP, indispensable.** Same SPLIT flag as inventory.spec.ts and
  orders.spec.ts. A seam by concern is plausible: the send matrix, suggestions and
  overrides, the run picker, holds.

### product-history.spec.ts
5 tests, 282 loc.
- **Protects:** #/product. The market series and the owner's own sale fills must draw
  as two visibly different SVG shapes, never one line. A sale older than the archive's
  history must be listed but never plotted. Leaving the deep link by any nav press must
  land on the target hash, never bounce to an empty #/product.
- **Product or mechanism:** product. An off-nav deep link. The route itself is a thing
  a compiler cannot check here.
- **Decisions:** D227, D278, D62. Current.
- **Last real defect:** 21277c12, "one view two frames, the trap fixed, printings
  identifiable." Real, names the exact trap this file exists to catch.
- **Cost:** unmeasured, small.
- **Overlap:** none direct.
- **Verdict: KEEP.**

### pull-confirm.spec.ts
5 tests, 147 loc.
- **Protects:** the first rows of the Fulfillment constraints table, against the one
  component step 6 built.
- **Product or mechanism:** product.
- **Decisions:** none cited directly. Governed by docs/DESIGN.md's table, same as
  fulfillment.spec.ts.
- **Last real defect:** unknown by subject-line match. Only 3 commits touch this file.
- **Cost:** unmeasured, small.
- **Overlap:** direct, and named in fulfillment.spec.ts's own header. That file states
  this spec covers 3 of these rows against one component. It states fulfillment.spec.ts
  covers all nine against the view.
- **Verdict: MERGE into fulfillment.spec.ts.** The larger file already claims full
  coverage of what this file checks. Confirm during the merge whether the 3 rows still
  need a component-level check. If not, this file is fully subsumed.

### revenue.spec.ts
28 tests, 681 loc.
- **Protects:** #/revenue as a tool: sort, filter, cross-filter, drill-down, deep-link.
  This is built over the same payload D214 already shapes. It does not re-test D214's
  counting rules. That argument lives in docs/specs/revenue.md.
- **Product or mechanism:** product. A fake, fixed clock everywhere, so a "this month"
  bucket does not go flaky across a month boundary.
- **Decisions:** D201, D214, D217, D225, D281, D298, D62. Current.
- **Last real defect:** fd9e9745 fixed Sales items 1 through 4, 6 through 8, and a
  second preview round. 826d3139 fixed Revenue.tsx defects design-check found, and
  rebuilt this file. Real.
- **Cost:** unmeasured.
- **Overlap:** none direct. D214's counting logic is explicitly out of scope.
- **Verdict: KEEP.**

### review.spec.ts
51 tests, 1726 loc.
- **Protects:** #/review, the owner's most-used screen after Capture. Its own header
  says grep found no mention of this route in app/tests/ before 2026-08-24. Protects a
  real reversal: the split that moved the photo beside the choices, against a rule
  docs/DESIGN.md had stated by name.
- **Product or mechanism:** product. The real store is never touched.
- **Decisions:** D118, D13, D136, D14, D16, D174, D194, D218, D221, D23, D24, D28, D29,
  D291, D32, D35, D37, D46, D76, D77. Current. The D194 citation is a historical
  comment about matching a caption's word count. It is not a live word-ceiling check.
  D284 replaced that mechanism. The wording is slightly dated, a minor nit, not a
  functional problem.
- **Last real defect:** 69b7f375, "Identify now spends exactly the cards the strip
  priced." e8e92ffb, "six cases failed on a fixture that omitted two required keys, and
  three on a banner nobody stubbed away." Real. The second names a test-fixture defect,
  not a product one.
- **Cost:** unmeasured. Large file.
- **Overlap:** none direct.
- **Verdict: KEEP.**

### run-panel.spec.ts
79 test( call sites, some inside loops, 3090 loc.
- **Protects:** the pipeline, identify, join, emit, reconcile, reachable from a screen.
  The header's account: this CLI chain ran real 53-card and 544-card production runs
  since step 4. It was reachable only from a terminal, until this file existed.
  Strongest assertion: before the free preflight answers, the control that spends money
  does not exist. Not disabled, absent.
- **Product or mechanism:** product. No real request is ever made. The spend route is
  intercepted with a body assertion.
- **Decisions:** D118, D13, D136, D145, D165, D166, D174, D180, D196, D20, D207, D210,
  D218, D275, D291. Also D32, D33, D36, D43, D48, D49, D54, D56, D57, D64, D65. Current.
  The D48 reference is explicit and correct. The file's own comment says the cart is
  gone and the capability is not, D180 overtaking D48. This file documents the
  supersession. It tests the replacement, not the retired mechanism.
- **Last real defect:** 50e8c197 gave the copy ratchet checked-in fixtures for its five
  emptiest routes. 77e6fa22 fixed the hours fixture to a whole number of hours. 9000
  seconds rounds to 3, not 2.5. Real fixture-correctness fixes.
- **Cost:** unmeasured. Large. Third-largest file after inventory, pricing, orders.
- **Overlap:** none direct. The money-spend gate is unique to this screen.
- **Verdict: KEEP.** Same SPLIT consideration as the other three large files, lower
  priority.

### scaffold.spec.ts
9 test( call sites, wrapping a loop over ROUTES so the real count is per-route times
9, 415 loc.
- **Protects:** every screen inherits the page scaffold, D275. One Page component. One
  h1 from the route's title. The page width token. The top gap token. No sideways
  scroll. One fixed document title, not the old alternating one. The command palette
  listing. The keyboard sheet entry.
- **Product or mechanism:** product. Reads routes from the same reader the static
  kit-adoption check uses. Cross-checks routesFromNav too.
- **Decisions:** D121, D275, D276, D291. Current.
- **Last real defect:** 8a5f09a8 taught a redirect route as a real route shape to both
  this file and the scaffold sweep. Real.
- **Cost:** unmeasured.
- **Overlap:** shares the walk-every-route shape with cursor, nav, phone, wide,
  page-edge. See the cross-cutting flag.
- **Verdict: KEEP.** Well-built. It derives its own roster. It cannot silently drift
  from ROUTES.

### section-ruler.spec.ts
3 tests, 277 loc.
- **Protects:** the section ruler never overflows its container. Pinned to a real,
  specific owner bug report: box WB1 R2 had 12 sections but only 11 showed.
- **Product or mechanism:** product. Own minimal fixture, a box of any section count on
  request, not inventory.spec.ts's fixed 7-record box.
- **Decisions:** D155, amended by the ruling this file matches. Current.
- **Last real defect:** be18182a, "no wrapped identity line begins with a separator."
  Real.
- **Cost:** unmeasured, small.
- **Overlap:** shares the locating-family subject with locating.spec.ts, but a
  different fixture and a different property: overflow, not section-relative numbering.
- **Verdict: KEEP.**

### shipping.spec.ts
16 tests, 634 loc.
- **Protects:** the shipping export's 3-lane routing, D61. Proves the shell's own
  network read never leaks into this screen's assertions. Enforced by the same spec
  seal audit row that governs every file's sealEveryTest() call ordering.
- **Product or mechanism:** product.
- **Decisions:** D117, D16, D194, D196, D218, D292, D33, D61, D63. Current. A raw
  decision-number search also matches a shipping tracking number this file uses as a
  fixture. That is not a citation. Named here so a future audit does not repeat the
  mistake. The D194 citation, like inventory.spec.ts's, reads as historical, not a live
  check.
- **Last real defect:** 50e8c197, shared ratchet-fixture commit. 6fcf2478 measured the
  order screen and shipping lane transport before writing them. Real.
- **Cost:** unmeasured.
- **Overlap:** none direct. One of three lanes, own route.
- **Verdict: KEEP.**

### text-shape.spec.ts
2 tests, 144 loc.
- **Protects:** D284's replacement for D194's retired pinned word ceiling. A repeated
  sentence across 3 or more cards. A number-plus-noun fact stated twice. A sentence
  over 25 words. A caption repeating most of its own heading.
- **Product or mechanism:** product. Shares routeSweep.ts with the other two text
  checks. A shrinking pending list, never a ceiling, keyed to the finding's own text.
- **Decisions:** D18, D194 (correctly noted as superseded, in the file's own header),
  D284. Current.
- **Last real defect:** 2cddeb9f, shared mechanism fix.
- **Cost:** unmeasured. Cheap by shared-sweep construction.
- **Overlap:** deliberately shares infrastructure with machine-words.spec.ts and
  money-face.spec.ts.
- **Verdict: KEEP.** This is the file that actually moved to D284. Other files, like
  inventory.spec.ts, review.spec.ts and shipping.spec.ts, still say D194 in old comments.

### wide.spec.ts
2 tests, 198 loc.
- **Protects:** the owner's screens above the desk: 1440, 1920, 2560. Nothing in the
  suite had ever rendered above 1440 before this file. Measured a real defect: at 1920
  with the sidebar open, #/pricing's card-identity cell was 924px wide while the
  price field it decides was 68px. At 2560 the widest prose line had no cap, 950px.
- **Product or mechanism:** product. Asserts the rule, never a pinned roster. Takes its
  routes from the same harvest cursor.spec.ts uses.
- **Decisions:** D123, D27, D275. Current.
- **Last real defect:** 45a25fdf, "Capture's phone floor, wide.spec's Fulfillment
  measure, and DEBT38-41." Real, names its own measured defects.
- **Cost:** unmeasured, small.
- **Overlap:** route-harvest shape shared with cursor.spec.ts and page-edge.spec.ts.
  See the cross-cutting flag.
- **Verdict: KEEP.**

---

## DEBT47: demo-coverage.spec.ts's network-seal case

**The owner's question, 2026-09-27.** The sealed browser only runs in testing. The real
demo has an unsealed browser. It does not refuse other websites. If that is true, is any
test for that portion just wrong to keep?

**What the test does.** Read at app/tests/demo-coverage.spec.ts, lines 68 to 72.
sealEveryTest() refuses every network request outside the app's own origin. Since PR
#476, the real, published demo intentionally loads stock images from
tcgplayer-cdn.tcgplayer.com. That is a real outside host, on purpose, in production. PR
#477 added a page.route() override, to make the suite pass against that real behavior.
It intercepts requests to that one host. It answers with a local, one-pixel stub image.
It is registered after the seal, so it wins.

**Answer to the owner's question: yes.** That portion tests a rule the real page does
not follow. The seal's premise says this page only ever talks to its own origin. That
premise is false for the shipped page. It has been false since PR #476. The stub does
not test that the image loads from the real host. It substitutes a fake image. It never
exercises the real request. So this test proves nothing about whether the real demo can
reach that host. That is the one path a real visitor's browser will actually take. This
is not merely redundant. It is silently empty on the one thing it appears to check.

**What it still protects, and no other file shares this.** The demo screens correctly
render real data from the dist-demo/ artifact, on over a dozen screens. Photographs.
Undo. The order walk. The graveyard. Product history. Value bands. Facet counts. Typed
search. None of that depends on the network-seal mechanism. None of it is covered
anywhere else. See the entry above. Cutting the whole file over the seal's defect would
throw away the part that works.

**The owner's own ruling, already recorded.** DEBT47 already says the guard's premise
changed. It says the stub hides real behavior. It says the
right test allows that one image host by name. It still refuses every other outside
host. The owner's words there: is not that a case of revising the test, since the test
is the wrong test to keep now.

**First verdict.** KEEP demo-coverage.spec.ts's screen-coverage cases, 13 of 14 tests.
SHRINK the one network case. Replace the blanket seal and stub with a named allow-list:
one host, tcgplayer-cdn.tcgplayer.com. Let the request reach that host. Or assert
against its real response shape. Remove the stub. The owner already ruled this a debt.
The fix belongs in the same pass over the tests. This audit does not reopen the question.

---

## Cross-file flags for the Opus reviewer

**Tests pinned to a superseded ruling.** Only two decisions in this slice were found
superseded: D48 to D180, D194 to D284. Every file citing either does so correctly. Some
name the supersession outright: run-panel.spec.ts, text-shape.spec.ts. Some carry a
harmless historical comment with no live assertion: inventory.spec.ts, review.spec.ts,
shipping.spec.ts, pricing.spec.ts. No file asserts retired D48 or D194 behavior as if it
were still current.

**Guards that cannot see their subject.** gallery.spec.ts documents a real, closed case
of this: the DEPARTED and POOLED fixture shapes that never rendered. cursor.spec.ts and
nav.spec.ts each self-document an open, known gap. A control absent from the empty
seeded store is not checked. A native browser shortcut cannot be proven declined. These
are not hidden. They are named in the files' own headers. They are real coverage holes,
worth carrying into the plan.

**Tests that stub so much they prove nothing.** One confirmed case:
demo-coverage.spec.ts's network-seal assertion, DEBT47, above. No other file in this
slice stubs away the exact property its own header claims to prove. The
reachability-battery files stub the server: inventory.spec.ts, orders.spec.ts,
pricing.spec.ts, run-panel.spec.ts and others. But they assert against the request body
the screen sent. That is a real and different claim from "the button exists." Not
vacuous.

**Size concentration.** Four files carry more than half the directory's total test
count and loc. inventory.spec.ts: 161 tests, 8358 loc. pricing.spec.ts: 125 or more, 4345
loc. orders.spec.ts: 116 or more, 4414 loc. run-panel.spec.ts: 79 or more, 3090 loc. All
four are KEEP on merit. Each protects a real, load-bearing screen with active, recent,
named defect catches. inventory.spec.ts's size is the stated reason four smaller files
had to hand-roll a duplicate boot fixture rather than reuse it. That is a concrete,
named cost of the file's size, not a guess.

**Redundant navigation, not redundant assertions.** cursor.spec.ts, nav.spec.ts,
phone.spec.ts, wide.spec.ts, page-edge.spec.ts and scaffold.spec.ts each walk every
route independently. The three text checks already solved the same problem with one
shared sweep. Folding the first six into a similar shared runner is the clearest
concrete SHRINK candidate here. It costs zero coverage.
