## D38 — The photograph is sized by the rows beside it, and the box and the runs get the third column

**The card photograph is sized for confirming a slot, not for judging a card.** Built 2026-08-25. `#/inventory` drew two columns — the box walk, and one 1004px column holding the card detail, the copies, then `BoxOps` and the run panel side by side.

Measured at 1440x900 on box 2 card 1 with six copies, by rebuilding the old arrangement in the live DOM: **body 1878px -> 1396px, photograph 420x587 -> 150x204**. The saving is data-dependent — most of what remains is the copies list, where a `position-bar` takes a line by rule — so read 482px as this card, not every card.

**The photograph had been sized against the wrong screen.** D33 gave it a `minmax(280px, 420px)` track arguing 280px was small because the review queue gives the same job 415x736. The two screens do not have the same job: the review queue is where a card is JUDGED, and this screen's question is *where is this card*. Borrowing a floor from a screen with a different job is the mistake `docs/DESIGN.md` names when it refuses to draw the Fulfiller's minimums on the owner's screens.

### Sized by the rows, then by its column

`.browse-facts` measures 203.5px, and 63:88 at that height is 145.7px wide — a 150px track, down from 420.

**It took its height from the facts for a few hours and is sized by its column again**, and the middle step is what made the right size findable. Pinned to the rows it was 150x204; the owner then asked for it back, which reads as a contradiction and is not. The two conflict only while the facts are as wide as they were: `Captured` printed a full ISO stamp at ~234px and now reads `6:35pm · Aug 23` at ~100px, so the widest value is the card's own NAME and the facts want ~270px instead of ~426px. `CardOps` moves up beside the facts, and the re-shoot control becomes a 24px icon with its words on `aria-label`.

**The frame went with it, deleting a class of defect rather than an instance.** While the photograph took its height from the facts the reservation had to live on a WRAPPER — and a wrapper holds whatever `PhotoPanel` returns, so a card with a missing file got a card-shaped box around a paragraph: measured 424x592 around 424x149, with the re-shoot control at y=985 of a 900px viewport. `aspect-ratio` is back on the `<img>`, where it cannot reach anything that is not an image. **Moving a reservation off the thing it describes and onto a wrapper gives it to everything else that wrapper can hold.** `align-self: stretch`, `.browse-frame` and a `:not(.is-absent)` media rule are all gone.

**`object-fit: cover` stays, against the obvious objection.** The frame is no longer guaranteed 63:88, so `contain` looks honest. D32 measured these frames at 2160x3840 with the card filling 80–88% of the width and 61–72% of the height, so `contain` would letterbox a narrow frame and shrink the card inside an already small photo. `cover` crops the desk off.

### The column, and what it cost on the axis nobody checked

The ~270px the photograph gave up became a third column for `BoxOps` and the run panel, which rewrites D33's last line: the row cost the card's column one panel's height, and the column costs it nothing.

**That was true about width and false about height.** A grid row is as tall as its tallest cell, and the card shared row 1 with the run panel while the copies were row 2 — so the copies began wherever the console ended:

| console state | console | copies at | whitespace | page |
|---|---|---|---|---|
| closed | 799px | y=938 | 378px | 1552 |
| a run picked | 1461px | y=1599 | 1039px | 2214 |

Picking a run is ordinary and the panel polls on a 4s/20s timer, so the second row is a resting state — the answer to *where is this card* positioned by something that is not about the card, at a height with no cap.

`.browse-body` is two columns and three rows: the walk, then the card, the copies and the console stacked in the content column. That voids D33's argument of 2026-08-24 for keeping the copies in the facts column — a 587px photograph would have pushed them off a 900px viewport, and no photograph here is that tall. **The console pays for its own move** — widened from 370px to 1024px it draws 625px closed and 1143px open with no code change, because its head stops wrapping four command names and its notes and free steps unwrap with it. What this entry got right and the rebuild keeps: the box belongs in the walk's column, the runs are not the card's neighbor, and nothing folds.

**What it costs:** `Check cost` was at viewport y=495 and is now below the copies. Identifying is done once per box; the copies answer the per-card question. If that trade is wrong the fix is to swap the last two rows, **never to restore the column**, which is the mechanism.

### Then the box left that column too

The owner, the same day: the operations should all exist on the left. The evidence was a duplication nobody had counted — `BoxOps` drew `Section 1 #1–#85  85 cards` as inert text for every divider, while `.browse-secthead` drew the same five rows a thousand pixels left, foldable, tickable and walkable. **The walk IS the sections list**, which is D31's finding one scale down, so the panel headed `Box 2` was the redundant instance.

`BoxIdentity` splits out of `BoxOps` for it — name, fill, state and the segment track, under the strip that names the box. The operations sit at the bottom of the walk. They sat there beside `RegisterBox` until 2026-08-26, when the owner deleted that control outright; nothing is lost, because `CaptureScreen.tsx:createOfferedBox` calls the same `POST /boxes` from the Box field. The sections list, its `Layout and controls` heading and the `sections 1 86 171 253 394` clause are **deleted rather than moved** — three renderings of one fact on one screen. The third column keeps the runs alone at 370px and the card takes the difference.

**A real defect came with that move.** `.browse-map` is sticky and capped at the viewport, so anything past the cap renders below the fold and the page scroll cannot bring it back. Harmless while the column held a search, a strip and a list; not harmless once the box's editors moved in, where opening the claims editor on a 720px window put the Apply button permanently off-screen. The column scrolls itself now, and `.browse-list` keeps a 6rem floor so an editor cannot squeeze the walk to nothing. `app/tests/inventory.spec.ts` asserts the escape hatch rather than the button's position.

### Density, to earn the narrower track

- **`BoxOps` drew one row per section with no bound**, at 25.5px, so the panel's height was a function of how finely a box happened to be divided. Box 2 declares five sections and draws **127px**, so the cap saves nothing today — what earns it is the other end, D31 recording **this same box at 22 sections**, ~560px, and D10 making dividers freely editable from any screen. Capped at six rows and scrolled, with the section total on the heading so a capped list cannot read as a short one. Row tracks narrow from 8rem/10rem to 5rem/7rem, moving the wrap cliff from ~399px to ~280px.
- **The run panel drew four 20px display headings**, the same size as its own title, so an open run said the steps and the panel were the same rank. 14px body now, matching `BoxOps`. Buttons drop to 32px, which is `.boxops-plain`'s height — the two panels disagreed about how tall a control is by 17%.

The column is then **`minmax(340px, 400px)`**, allocated after the cuts.

**Three columns are a >= 1240px layout.** 1240 rather than 1440 because the owner works at 1440x900 and a breakpoint at the working size is one you cross by un-maximizing a window; it also puts Playwright's 1280x720 inside the new layout, so `make design-check` exercises the three columns rather than only the fallback. **The number survived the columns (2026-08-26):** there is no three-column body any more and no body breakpoint at all, which deleted the `@media (max-width: 1239px)` block. 1240 now governs the CARD BAND's third track, and the reason transfers unchanged.

### Four things the card panel gained, from one finding seen in four places

- **`Rarity` and `Note`, which `CardOps` could overwrite without showing.** `ClaimEditor` writes five claims and the list drew three — and it opens with those fields empty and reads armed-and-empty as a CLEAR, so `Correct claims` was a blind overwrite of two values appearing nowhere on screen. `rarity_claim` is set on 543 of 543 records, so this was live. Rarity renders verbatim (D22), through the same renderer as the finish claim so a second `' · '` join cannot drift.
- **`Run` and `Confidence`.** `run` is on all 543 records and is the join between this panel and the run panel, which lists directories and cannot say which cards each touched. `Confidence` is the only place a RESOLVED card's hedge is readable, since `#/review` draws it only for a queued card. Shown FLAT, never as a chip or a color: T1's and D35's recorded misses are all confident and wrong, so `high` is not reassurance.
- **Whether the card has an open question, from `GET /queues`.** A queued card rendered `State: identified` and nothing else — and `state` there is MISLEADING, describing how far capture and identify got while the question was raised by the JOIN. The candidate count is load-bearing: zero candidates is the difference between *go and answer it* and *it cannot be answered as it stands*, which points at the re-shoot icon already on this panel. The label map moved to `app/src/reasons.ts` and is IMPORTED by both screens rather than copied — nothing keeps it in step with `pipeline/variant.py`, and the defense is making that drift visible. `scripts/docs-audit.py`'s reason-codes check follows it there.
- **The copies list spans the card's column AND the runs'.** Measured: in the middle column it was 976px of a 1450px page on the default card and 1713px of 2187px on an eleven-copy one, with 778px of viewport empty beside it. Wide, the row goes 144px to 82px and eleven copies go 1598px to 902px — **43% with nothing removed**. Keyed to a **container query** rather than a breakpoint, because `CardLocations.css` promises to be honest with no breakpoint to keep in step. It also collapses `detail`'s two render sites into one.

  **Amended 2026-08-26: the copies span the CONTENT COLUMN, the same width by another name** — 1024px at 1440 and 864px at 1280, the exact widths they had spanning columns 2 and 3, so every measurement above stands. Re-measured on the way past: a row is 83px at >= 940px of container, 115 at 864, 127 at 860 and 159 at 630. **The 860 threshold is therefore mis-set**, buying a 127px row rather than the one-line 83px one, and is left alone deliberately: raising it to 940 without guaranteeing the container is that wide would drop 1280 from 115px to 159px. The sharpest known defect in this area.

**The four rows closed the band's air and slightly overshot.** The facts are now 415px against a 349px photograph, so the ~90px under the facts is ~66px under the photograph. Which side is taller was never the property worth guarding; the assertion checks the two stay within a band of each other.

**What would reopen this: a photograph nobody can read.** If the owner opens the review queue to look at a card they were already looking at here, this screen has acquired the other screen's job, and that is worth naming before it is resized.

### The twelfth row is a price, and it is the first fact here that is not on the record

The owner, 2026-08-29, asked for `TCG Market Price` on the card summary with a note of how stale it is.

**The store holds no price, and that is D8 rather than a gap.** Every figure comes from the Filtered Export and `store/master.py` has no field shaped like money — so *what is this card worth* was answerable on `#/pricing` and on no screen the operator is standing at when they ask. The eleven rows above are `asdict(card)`; this one is a join.

**The edge is D46's, reused: card -> `run` -> that run's `pricing.json`.** `cli/cmd_join.py` writes that file on every join with each matched SKU's export row verbatim AND every position holding a copy, so a position resolves to a SKU and a Market cell with no new route, no new field on the wire and no schema change. `GET /pipeline/runs/<name>/pricing` is free and read-only.

**Keyed by position, never by `card.sku`** — the one decision here that could be silently wrong. That field is written by `emit`, so a sub-threshold card, a card withheld under D49 and every card in a run joined but never emitted all carry `null`. A SKU-keyed lookup would draw nothing for all of them and look correct on the rest. The position is on both sides and written by neither. `app/tests/inventory.spec.ts` prices a fixture card carrying `sku: null`.

**One read per run, cached by run name.** A real table is ~80KB for 50 SKUs and a box normally names one run, so walking a box costs one read — the argument `queued` beside it already makes. Keyed by RUN and not by box, because D33 scopes a run to a SELECTION inside a box, so two cards on one shelf can carry two tables read at two different moments.

**The age is never optional and `read` is never `as of`.** `join` is free and routinely pointed at a refreshed export, so a bare `$5.47` claims a currency the file cannot support. `GET .../pricing` answers `written_at`, the mtime of `pricing.json`, because the export is a CSV downloaded at an earlier moment nothing here can see. The freshest honest sentence is when the pipeline last looked: `$0.34 · read 3d`.

**It read `$0.34 · read 3 days ago` until 2026-08-30 and wrapped onto two lines on every priced card.** Measured at 1440: `.browse-facts` is 578px at `column-width: 260px`, taking two columns of 277px and leaving a **181px value track** at 9.1px per character — a budget of **19 characters**. `$0.34 · read 9 hours ago` is 218.4px. Six of the row's twelve outcomes were over the line, so this was the ordinary state of the row.

**It was never a copy problem.** The figure is variable-width, so no wording holds: `$30.81 · read 9h ago`, with the age already at its shortest, measures **182px — one pixel over**. Widening cannot rescue it either, since two columns of 277px is what 578 gives; shrinking the label track to its ink (80px, `CONFIDENCE`) and the gap to `--s2` buys 8px against the 47 needed. The row asks for ~230px in a 181px track.

**`ago` goes and `read` stays, which is a trade rather than an abbreviation.** `read` is what establishes that the age is the JOIN's; without it `$0.34 · 12d` reads as twelve days on the market. `ago` is redundant beside a past tense and is the wider of the two, 45.5px against 36.4px. Measured headroom for the figure: `· read 12d` leaves **8 characters** (`$1234.56` fits), `· 12d ago` leaves 9 but spends the verb, and `· read 12 days ago` leaves none.

**And the words were unbounded where the compact form is not.** `N days ago` grows with N, so a year-old join renders `read 400 days ago` — wider the longer it went unattended, which is the opposite of what a staleness reading should do. `Nd` is four characters until 2036.

**It is a second rendering of `sinceText`, not a second vocabulary.** That function forbids two spellings of *two days* sixteen pixels apart, and this panel draws both ages within one screen. The thresholds, rounding and `today` floor stay in one function and only the spelling is a parameter; a private helper beside `marketText` would have been the same rule written twice. **The queue age keeps its words**, drawn in `.browse-queued`, which is full-width and has never been short of room.

- **Rejected: an absolute date.** `$0.34 · Aug 29` leaves 10 characters and reuses `capturedText`'s form, the structurally cheapest option. It answers *when* where the question is *how stale*, and reads as the `as of` this entry refuses.
- **Rejected: splitting the age onto a `READ` row.** The only option that shrinks nothing, at 9px of list height. The owner chose the one line.

**The guard measures the row and pins the viewport.** `app/tests/inventory.spec.ts` already asserted what this row says in five places, and every one was green through the defect — a sentence written past the track does not fail an assertion about its text, it takes a second line. The new case counts the lines the value draws. **The suite's default 1280 cannot see it**: there the list is 506px, one column, a 410px track where every string fits. The whole defect lives at a width nothing in that file had rendered, so 1440x900 is the case. Mutation-tested: the old wording takes it red at 2 lines, the compact form green at 1.

**The mtime rather than a `joined_at` inside the table.** A field written into the file would be better data and absent from every run already on disk — precisely the runs a screen is opened over. The mtime needs no re-join and cannot drift from the bytes it describes; what it does not survive is the directory being copied, and nothing here copies one. T7 backdates the file and requires the route to report the backdate, because asserting against the live mtime is VACUOUS — the test joins immediately before the request, so a route stamping `time.time()` answers the same integer. That version was written, mutated to a clock, and **observed passing**.

**Five outcomes, five sentences, and the row is never conditional** — the rule `Rarity` and `Note` already follow, because a row that disappears leaves *this card has no price* and *this screen does not show prices* indistinguishable. No run on the card is `not joined yet`; a run with no table is `join this run`, the one refusal worth telling apart since its remedy is a join; a position the table does not hold is `no row in this run`, which is `no_catalog_row` and the review queue's business; and a **blank Market cell is `no_market_data`**, verbatim, because it is `pipeline/routing.py`'s own `NO_MARKET_DATA` and D9 is emphatic that a missing price is unknown rather than low. Rendering it as `$0.00` is what hands a chase card away at the floor.

**Three of those were cut to the same 181px, and the refusal lost half of itself.** `no row matched by this run` was 236.6px and `no pricing table — join this run` 291.2px — the second wider than any price this row can draw, so it wrapped in the one state an operator cannot reproduce. Only one half fits, and **the remedy is the half that survives**: `MARKET: join this run` already says a table is missing, and the sentence it is told apart from — `could not be read` — names no remedy, so the pair still reads as two failures. `no age` replaces `age unknown` on the same grounds, joining `none` and `not recorded`.

**The underscore is a ruling.** Spelled `no market data` it is neither the machine string nor a human label — the second vocabulary D22 refuses and D16 exists to catch — and it greps to nothing against `decisions.json`'s own `no_market_data` block, which is where such a card is priced by hand. So the row splits: plain English where THIS SCREEN has nothing, and the pipeline's own word where the PIPELINE said something.

**A reload re-reads it, and leaving that out was a live bug.** The cache is cleared on the reload counter and the READ was keyed on the run NAME alone, which does not change when a box is re-read — so the cleared entry was never re-fetched and the row sat on `reading…` permanently. A clear and its re-read are one gesture. It matters more than ordinary staleness: Reload is pressed after something downstream changed, and a join is what rewrites a price.

**Beneath `Run` and above `Note`**, the placement `Confidence` gets for the same reason: the price is not a property of the card but what one join found in one export, so provenance reads down. Both rows would be inexplicable apart.

**What this does not do: it does not put pricing on this screen.** No preset, no override, no snap, nothing writable — `#/pricing` is where a price is DECIDED (D49) and this is where one is READ. If this row grows controls it has acquired that screen's job.

**What would reopen this: a box whose cards span many runs.** The one-read-per-run cache is sized for a box identified in one go; a box assembled from a dozen ticked selections would fetch a dozen tables while the arrow keys walk it. The measurement is how many distinct `run` values one box's records carry — two today, across the whole store.

---
