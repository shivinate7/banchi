# Three ways to re-do the platform's UI — navigation and process, from first principles

**STATUS: RECORDED, NOT BUILT. Nothing in this file is implemented.** It is three competing
architectures for the owner-side navigation and the process surface, written to be chosen
between. One of them, part of one, or none of them may be built. No decision entry is
changed by this file existing; every proposal names the entries it would have to reopen, and
reopening one is the owner's call per `docs/DECISIONS.md`'s header.

**The three are deliberately not variations.** They differ in what the top-level unit of
navigation IS — a place, a stage, or a subject — and that choice decides everything below it.
Picking between them is picking a first principle, not a layout.

---

## 0. What was measured, on the live app, before anything was proposed

Every number below was taken in a browser at 1440x900 against the real store on
2026-08-24 — 682 cards, 47 review entries, three boxes. `scripts/views.txt` says in its own
header that no run in this repo had ever produced a populated render; that was true when it
was written and these are the first measurements taken against one.

**The three owner screens do not agree on how wide a screen is.**

| screen | `main` max-width | unused width at 1440 | chrome above first content | scroll height for one task |
|---|---|---|---|---|
| `#/` capture | 1400px | 20px (1.4%) | 46px — nav only, no page title | 0 (fits the viewport exactly) |
| `#/inventory` | 1240px | 200px (13.9%) | 217px to the section list; **482px to the selected card's photograph** | 1278px (1.4 viewports) |
| `#/review` | 688px | **752px (52.2%)** | 146px | **4018px (4.5 viewports)** |

`docs/DESIGN.md` sets page chrome at 16px padding, a 20px title sharing its line with the
controls, and **"the first row of real content sits within 150px of the top of the
viewport"**. Capture clears it with 46px and carries no page title at all. Review clears it
at 146px. Inventory's own first content — the search field and the box header panel — clears
it at 115px, so the letter of the rule is met.

**What the rule cannot see is the thing the operator actually came for.** On a fresh
`#/inventory` at 1440x900, measured top to bottom in the right-hand column: the box header
panel at y=115 (190px tall), its *Layout and controls* fold at y=254, `RunPanel`'s *Runs*
fold at y=321 (76px collapsed), and only then **the selected card's detail panel at y=413,
with its photograph at y=482 — 54% of the way down the viewport — running 435px tall and so
ending at y=917, past the fold.** Two collapsed folds and a box header, none of which was asked for,
sit between the top of the screen and the card that was clicked. That is the "bolted on"
feeling as a coordinate, and nothing mechanical enforces it, exactly as that section says.

**The review queue is the sharpest single finding, and it is a layout fact rather than an
opinion.** At 1440x900 the screen draws:

- the photograph at 244x432, at x=16
- the position label at y=590, the sentence at y=658, the actions at y=797, the facts at y=849
- **the worklist — the `Waiting` section, all 47 entries at a 60px pitch, 2868px tall — starting at y=1134**, which is 234px below the fold
- **752px of empty page to the right of all of it**

So the operator cannot see the card and the queue it came from at the same time, while
enough horizontal space to hold the entire worklist sits unused beside the card. This is one
screen, and it is the screen `docs/DESIGN.md` specifies harder than any other.

**The Fulfillment view renders every card in the store.** `main.fulfillment` measured a
scroll height of **124,348px** — 138 viewports — because the default list is all 682 records
at a 20px floor. This is a scaling defect rather than a navigation one, and it is named here
because it is the thing a redesign must not inherit. It is filed as its own item in §5.

**The process has no surface anywhere in the app.** `python3 scripts/status.py` answers
"where am I, what is next, what is the state of the store" in a terminal. The app answers it
nowhere. `POST /pipeline/*` — the seven routes D33 added, the ones that spend money and
produce the import files — is reached through a `<details>` fold measured at 76px collapsed,
sitting between a box header and the card detail on a screen named Inventory.

**The loop crosses routes three times for one box.** Shoot (`#/`) → open the Runs fold
(`#/inventory`) → answer (`#/review`) → back to the Runs fold for the CSVs (`#/inventory`) →
TCGplayer in another tab → back to the Runs fold to reconcile (`#/inventory`). The screen the
owner returns to three times per box is named after a different question.

**Why it feels bolted on, from `git log` rather than from taste.** `app/src/` was built in
four bursts: 2026-08-12 (tokens, gallery, `PullConfirm`), 2026-08-13 (the shell and all five
screens, in one day), 2026-08-22 (motion), 2026-08-23 (`BoxBrowse`, `BoxOps`, `RunPanel`,
`CardLocations`, `PositionBar`, `SearchField`, `useSearch`, `keys` — six components and the
whole pipeline seam, in one day). **The shell was designed for three screens and never
revisited when the last burst added six components and twenty server routes.** D31 merged two
routes away and D33 added the pipeline panel, and both landed inside a nav strip whose shape
was decided on day two.

**What the redesign has to compose from.** 33 server routes (`server/capture_server.py`'s
header is the register), five faces of state per card, two personas, and a keyboard
vocabulary that is currently per-screen and collides across screens: `r` is rarity on
capture and reload on review, `c` is capture and clear-filter, `u` is undo on both. The
`,`-leader chord in `app/src/App.tsx` is the only global key.

---

## 1. Proposal A — **The Rig**: one instrument, three fixed docks, no routes

**First principle: a tool you spend hours in should never change address.** Navigation is
replaced by focus. The owner's app is one screen for its whole life, and what changes is
which subject the three docks are pointed at.

### Shape

A frame that never reflows, at any subject, ever:

```
+--------+-------------------------------------+-----------+
| RAIL   |               STAGE                 |   DOCK    |
| 280px  |               fluid                 |   340px   |
| fixed  |          full viewport height       |   fixed   |
+--------+-------------------------------------+-----------+
```

- **RAIL (280px, fixed)** — the only navigator in the product. A vertical list of boxes, each
  one row carrying its number, name, fill bar and a **stage bead** (see §1.2). Beneath the
  boxes, the run list and the queue depth as two more rows of the same kind. Nothing else.
- **STAGE (fluid, full height)** — the largest thing on screen at all times, and the only
  thing that changes. The live/last-capture pair — coequal, per `CaptureScreen.css`'s own
  rule — while shooting; the card photograph while answering; the box walk while browsing;
  a run's console while it runs.
- **DOCK (340px, fixed)** — the capture screen's collapsed key-row pattern, generalised. That
  pattern is the best thing in the current app and it is used on exactly one screen: a 32px
  row carrying `key · LABEL · right-aligned value`, which opens in place. In the Rig it
  carries claims while shooting, candidate rows while answering, facts while browsing, and
  steps while running.

**Zero page titles and zero nav strip.** The rail says which box you are on and the dock says
what is true of it, so a 20px title repeating one of them is chrome with no reader. Chrome
above content is **0px** — the stage starts at y=0.

### 1.2 The bead is the process surface

Every box row in the rail carries one bead, and the bead is that box's stage: `open` ·
`shot` · `identified` · `answering` · `priced` · `emitted` · `staged` · `live`. It is
computed from what the store and `runs/` already say — nothing new is stored.

**Clicking a box points all three docks at whatever that box needs next.** An `open` box puts
the camera on the stage and the claims in the dock. A `shot` box puts the preflight on the
stage and the money gate in the dock. An `answering` box puts the queue on the stage and the
candidates in the dock. The bead answers "what do I do next" in a glance, which is the
question `scripts/status.py` answers in a terminal today and the app answers nowhere.

### 1.3 What this does to the measured waste

Answering a card: photograph on the stage at full viewport height (~854px against today's
432px), candidates in the dock under the fingers, the worklist as the rail's queue rows.
**Nothing scrolls and nothing reflows between cards** — which is half of D28 solved by
layout rather than by reserving a height. Width used: 280 + fluid + 340 = 100% of 1440,
against today's 45.6%.

### 1.4 Costs, honestly

- **It is one component tree**, and a big one. Every Playwright selector except
  `app/tests/fulfillment.spec.ts`'s would be rewritten.
- **The Fulfiller cannot use it**, and must not: D5 and `docs/DESIGN.md`'s constraints table
  make his view a different posture at different floors. He keeps `#/fulfillment` as its own
  route, unmerged, exactly as D31 already requires.
- **Fixed docks mean fixed costs.** 620px of the 1440 is committed before any content. That
  is correct at 1440 and wrong at 1100, so the rail and dock need collapse behaviour, and a
  collapsing dock is the one place this proposal grows a fold.
- **Reopens nothing, strictly.** It is a shell change: D31's spine survives inside the stage,
  D33's panel becomes a dock state rather than a fold. But it makes `docs/DESIGN.md`'s page
  chrome numbers unreachable as written, since there are no pages — that section would have
  to be re-argued as frame chrome.

### 1.5 THE OBJECTION, AND THE FIVE MECHANISMS THAT ANSWER IT

**The owner's response to the above, 2026-08-24**: *"I like the Rig, but I think having one
page for the entire app is gonna grow frustrating fast and end up feeling cumbersome not
efficient."*

That is the correct objection and it is not a matter of taste. A page hands you five things
for free that a single surface has to earn back deliberately, and a Rig that skips any one of
them earns exactly that reputation. Recorded as a numbered ledger because each cause has one
mechanism, and dropping a mechanism silently is how this proposal would fail.

**Cause 1 — nothing has a name any more.** No bookmark, no link, no browser-back; every move
is an unnamed mode change and the app forgets where you were. This is the biggest single
reason one-surface apps feel worse than pages.

> **Mechanism: the stage is ADDRESSED, not moded.** `#/2/17`, `#/box/2`, `#/answer`,
> `#/run/2026-08-24-box2`. Back, forward, reload, bookmarks and two tabs side by side keep
> working, because they are the browser's and were never ours to break. `app/src/App.tsx`'s
> hash router already does this — the Rig changes what a route *paints*, not whether routes
> exist. **This is the mechanism that makes the whole proposal survivable, and it is the one
> that would be dropped first** for looking like a formality.

**Cause 2 — everything secondary becomes a modal.** With no room for another screen, the
fifteenth operation arrives as an overlay, then two. A stack of things covering the thing you
were looking at is precisely how efficient turns into cumbersome.

> **Mechanism: drawers, never overlays.** Box ops, claim corrections, the retire reasons and
> `decisions.json` each open in the dock and PUSH the rows beneath them down. The stage is
> never occluded, so the photograph being judged stays visible while you operate on the card.
> `docs/DESIGN.md`'s destructive-action gate stays the one exception.

**Cause 3 — fixed zones are wrong for most tasks.** A 280px box rail is right for choosing a
box and waste while answering a queue. §1.4 already concedes 620px of committed chrome, which
is the same complaint §0 makes about today's app.

> **Mechanism: three states per zone — full, mini, gone**, on `[` and `]`, remembered per
> subject. The stage then runs 820px browsing, 1044px answering, 1100px shooting and 1328px
> judging one photograph, against today's 244px review photo. Below 1200px the rail auto-minis;
> **below ~1000px the dock stops being a zone and becomes a drawer over the stage**, which is
> this design's one honest concession and is named rather than designed away. D13 puts the rig
> on a desktop browser, so that is a laptop-lid case.

**Cause 4 — you can only look at one thing.** The real questions here are comparisons: is this
Thievul the one already in box 1?

> **Mechanism: the stage splits** on `\`, into two independently addressed panes — so the
> split is itself in the hash and a comparison is a link you can keep.

**Cause 5 — background work makes you go and look.** A run takes minutes to hours and outlives
the request that started it (D33). If checking it means navigating away, you lose your place;
that trip, three times a box, is most of §0's measured friction.

> **Mechanism: a ticker, not a destination.** A live run paints one line across the bottom of
> the stage from any subject — phase, count, elapsed, spend — expandable into the stage on a
> key. `cli/runs.py` already makes a run an immutable input read from disk, so this holds no
> state between requests.

**Four of the five are answered by design. What remains real, and is the grounds to reject
this:** three zones is a bet that every task decomposes into subject / content / controls, and
a task that does not — a wide table, a long console — has to borrow the whole stage; the
collapse keys are discoverable only from the dock caption, which is one more thing to know than
a page needs; and the build is one large component tree that rewrites every Playwright selector
outside `app/tests/fulfillment.spec.ts`, even though the screens' logic is re-hosted rather
than re-implemented.

**Visuals exist for all six modes** — answering, shooting, browsing, a drawer, a split, and the
ticker — drawn to the real 1440x900 aspect with the zone budget as arithmetic. They are an
artifact rather than a file in this repo, which is the one thing about this entry that is not
self-contained; `docs/DESIGN.md`'s screenshot loop is the standing rule that a design needs a
rendered reference, and this is that reference.

**THE FIRST DRAWING OF SHOOTING WAS WRONG, AND THE OWNER CAUGHT IT ON SIGHT.** *"I don't see
how any of these work given the current capture setup of needing two images (one of live
camera feed, one of capture) while you've just done a one large square box."* Checked against
`CaptureScreen.tsx` and `CaptureScreen.css`: the real stage is `grid-template-columns: 1fr
1fr`, two panels captioned "Live" and "Last capture," same 16:9 aspect, same size —
`CaptureScreen.css`'s own comment states the rule directly: *"Both frames share one aspect and
one size so the photo can be compared against the live view without either being the small
one."* The first drawing gave Live the whole stage and Last Capture a 16%-height strip with two
placeholder rows, which is the exact thing that comment forbids.

It was not only a proportion error. "Last capture" is not a thumbnail — it renders the bytes
the *server* stored, deliberately not a local preview, "which is the one failure this screen
exists to make loud," and it carries the position label, the game/set-hint/finish claims, flags
(`new box`, `already recorded`), and a per-card note field with its own `<form>` so Enter saves
the note rather than firing the shutter. None of that survived the 16% strip. The corrected
wireframe draws both panels at true equal size and puts the note and metadata back on the
Last Capture panel rather than in the claims dock — matching the real screen's own reasoning,
which is that a note is per-card state tied to the photo it is about, not a session setting set
once and left alone.

**Grepped for the same failure shape elsewhere first**: no other screen in `app/src/` pairs two
coequal panels (`grep -n "grid-template-columns: 1fr 1fr" app/src/*.css` returns exactly this
one rule), so this was Shooting's defect alone, not a pattern to hunt down mode by mode.

---

## 2. Proposal B — **The Line**: the pipeline is the navigation

**First principle: the product is a conveyor, so the UI should be the conveyor.** Cards are
the units and stages are the addresses. Navigation by stage rather than by screen, because a
stage is what the owner actually decides to do next.

### Shape

The nav strip is deleted and replaced by a **44px stage bar** — the same height the current
nav measures — carrying seven stops, each with a live count:

```
SHOOT 85 · IDENTIFY 0 · ANSWER 47 · PRICE 3 · EMIT 2 · IMPORT 1 · SELL 597
```

**The count is the navigation and the to-do list at the same time.** Clicking a stop opens
that stage's workbench below: full-bleed, full height, no page header, no fold. The bar never
moves; the workbench swaps.

### 2.1 The seven workbenches

| stop | what it is | where it lives today |
|---|---|---|
| SHOOT | the capture screen, unchanged in spirit | `#/` |
| IDENTIFY | the preflight numbers as the whole screen, then the two-step confirm | a fold on `#/inventory` |
| ANSWER | the review queue, **two columns**: card left, worklist right | `#/review`, one column, worklist below the fold |
| PRICE | `decisions.json` as a real surface — sub-threshold bands, `no_market_data` rows | a textarea in the same fold |
| EMIT | the import CSVs as files, per game | the same fold |
| IMPORT | the staged-export upload and `reconcile` | the same fold |
| SELL | the box walk, the search, and the Fulfiller's mirror | `#/inventory` |

Four of the seven stages of this product currently live inside one `<details>` element. The
Line's whole claim is that they are stages, not a panel.

### 2.2 What it fixes that nothing else does

**The app becomes self-documenting.** A session opens, reads the bar, and knows the state of
the business: 85 cards shot and unidentified, 47 waiting on a human, 3 needing a price. That
is `scripts/status.py` rendered where the work happens, and it is the single largest thing
missing from the product today.

**The line is directional, so finishing is visible.** Clearing a stage drops its count to
zero and dims the stop; the next stop lights. "Am I done with this box" stops being a
question you answer by remembering.

**Box scope becomes a filter on the bar**, not a place: `box 2 ▾` beside the stops, and every
count re-reads for that box. This is the inverse of D31's spine and it is the honest cost —
see §2.3.

### 2.3 Costs, honestly

- **It demotes the box axis, and D31 is explicit that the box walk is the spine.** The owner
  ruled that finding a card is *"basically find a card in a box-based system if anything"*.
  The Line makes the box a filter and the stage the place, which is the opposite cut.
  **Building this means reopening D31 with the owner**, and this file does not pretend
  otherwise.
- **It contradicts D33's placement argument** — that a run is *"something done to the box
  being walked"* and therefore belongs on `#/inventory` rather than on a route of its own. The
  Line's answer is that four stages hiding in one fold is the evidence against that
  placement, but that is an argument to have, not a fact to assume.
- **Seven stops is six more nav items than the product needs on a quiet day.** A count of zero
  on five stops is five dead controls, and a bar that is mostly dim is a bar that stops being
  read.
- **`PRICE` is a stage nobody has built.** D9's sub-threshold disposition and
  `no_market_data` are answered by editing text today. The Line gives them a workbench, which
  is new surface area and needs the argument `CLAUDE.md`'s scope rule asks for.

---

## 3. Proposal C — **The Slab**: no navigation at all, only a subject line

**First principle: navigation is overhead; addressing is not.** Delete the nav, the routes,
the titles and the folds. One full-bleed surface, and one line at the top that is
simultaneously the address bar, the search field and the verb entry.

### Shape

```
+----------------------------------------------------------+
| > box 2 › card 17                              40px      |
+----------------------------------------------------------+
|                                                          |
|                    THE SLAB                              |
|              100% of what is left                        |
|                                                          |
+----------------------------------------------------------+
```

**40px of chrome, on every screen, forever.** 95.6% of a 900px viewport is content, against
today's 84% on capture, 76% on inventory and 84%-of-45%-of-the-width on review.

### 3.1 The subject line

You type what you want to look at, and the slab becomes it:

| typed | the slab becomes |
|---|---|
| `2/17` | that card — photograph at full height, facts beside it |
| `box 2` | that box's walk |
| `thievul` | every copy of it and where each one sits (D7's map) |
| `answer` | the queue, one card at a time |
| `47` | the 47th queue entry |
| `identify box 2` | the preflight, as the whole screen, with the confirm on the line |
| `run 2026-08-24-box2` | that run's console, steps and artefacts |
| `?` | every verb and every key — the safety net |

The line keeps a breadcrumb of the last few subjects (`box 2 › card 17`), so back is one
keystroke and history is visible rather than remembered.

### 3.2 Why this suits this product specifically

`docs/DESIGN.md` already says the owner-side answer out loud: **"an hour in the queue is a
keyboard and not a mouse"**, and *"every choice shows its key"*. `app/src/App.tsx` says the
owner *"knows every route in this app by name"*. The Slab is those two sentences taken
literally — and it dissolves the key-collision problem in §0 for free, because with one
surface consuming keys there is no second screen for `r` or `c` or `u` to mean something else
on.

**The money gate survives intact and gets better.** D33 requires two steps and no typing.
Typing `identify box 2` renders the preflight — the count and the estimate — as the whole
slab, and the confirm appears on the subject line as a thing to press. The number is
impossible not to have seen, which is D33's own stated cheapest honest gate, and the confirm
still does not exist before the preflight has answered.

### 3.3 Costs, honestly

- **Discoverability is the whole risk.** A verb you do not know is a verb you cannot reach.
  `?` is the mitigation and it is not a complete one; the honest version of this proposal
  ships `?` as a persistent affordance rather than a hidden key.
- **It is the furthest from what exists**, and the most likely to be half-built. A Slab with
  three verbs and a fallback nav strip is worse than either end.
- **It cannot be the Fulfiller's** under any reading of `docs/DESIGN.md`'s constraints table —
  a command line is the opposite of self-evident. He keeps his route, again unmerged.
- **`docs/DESIGN.md`'s page-chrome section becomes inapplicable**, not violated: there are no
  pages to put a 20px title on. Like Proposal A, that section would need re-arguing.

---

## 4. How they compare on the three things asked for

Measured today against the projection for each proposal, at 1440x900.

| | today | A · The Rig | B · The Line | C · The Slab |
|---|---|---|---|---|
| top-level unit | screen | box (place) | stage (process) | subject (address) |
| chrome above content | 46 / 482 / 146px | 0px | 44px | 40px |
| width used, review task | 45.6% | 100% (stage 1044px) | 100% | 100% |
| scroll for one review card | 4.5 viewports | 0 | 0 | 0 |
| routes | 5 | addressed subjects + Fulfiller (§1.5 cause 1) | 1 + Fulfiller | 0 + Fulfiller |
| clicks, shoot → CSVs in hand | 3 route changes, 3 folds | 0 route changes, 0 folds | 6 stop clicks, 0 folds | 0 clicks, 4 typed subjects |
| "what do I do next" | terminal only | bead colour | the counts | `?` or a stale breadcrumb |
| decision entries reopened | — | none (DESIGN.md re-argued) | **D31, D33** | D31 softened, DESIGN.md re-argued |
| risk | — | one big tree; three zones is a bet | demotes the box axis | discoverability |

**They are not equally safe.** A is the largest layout change with the smallest argument to
have — it reopens no decision, because it keeps the box as the unit and only stops paginating
it. B is the largest claim about the product and needs the owner to reopen two entries. C has
the highest ceiling and the sharpest failure mode.

**If one is to be built, A is the one to build first, and B's stage bar is the piece worth
stealing into it.** A rail of boxes with beads and a bar of stages with counts are the same
information at two orientations; A's rail can carry the counts as rows, which is most of B's
benefit without reopening D31. That is a recommendation, not a decision.

---

## 4.5 THE EVIDENCE PASS — B AND C ARE REFUTED, A SURVIVES AS A SKELETON

**Run 2026-08-24 at the owner's instruction**, after this file's §4 recommended A on
reasoning alone. Twelve agents, eight domains of prior art, live web research, then an
adversarial pass that tried to refute each proposal. Full record and every source in
`docs/specs/ui-research.md`. The three verdicts:

- **B, The Line — REFUTED, and not on taste.** Jenkins Blue Ocean was the purest stage-first
  UX ever shipped and is deprecated as of July 2026; Dagster beat Airflow by moving *further*
  toward objects; GitHub Actions ships zero counts in navigation. It is not brave and untested,
  it is the position the field occupied and vacated. It also fails on its own facts: the seven
  stops omit `join` — `RunPanel.tsx:68` holds exactly identify / join / emit / reconcile — which
  is the step that PRODUCES both the ANSWER queue and the PRICE questions, and the counts carry
  three different denominators (cards, run directories, SKU copies) so the one claim B rests on
  cannot hold. D7's fungibility puts one card at several stops at once.
- **C, The Slab — REFUTED on an absence.** The corpus was searched for a tool with more than one
  object type navigating by typed line alone and found none; Superhuman, the most
  keyboard-extreme product surveyed, says so in its own palette guide. And C's arithmetic is
  fatal on its own terms: deleting a 45px nav to install a 40px command line recovers **5px of
  900**, while the measured waste is 752px of width and 4,018px of scroll. **Its component half
  is the best-supported single addition in the corpus** — a subject field hosted in the rail.
- **A, The Rig — SURVIVES, but "as written" does not.** The skeleton is the best-evidenced
  structure in the corpus. The owner's objection is confirmed by the field that invented fixed
  layouts: where the protocol library is thin, "the viewer defaults to a layout that satisfies
  no one." The remedy is not fewer zones but **named postures** — SHOOT / ANSWER / BROWSE / RUN
  — the way OHIF ships hanging protocols with a guaranteed default and Blender ships Workspaces.

**"One frame for the entire app" is withdrawn.** It is false by construction:
`#/fulfillment` cannot live in this frame under any configuration — a rail of box rows fails the
20px text floor and the 44x44/12px tap floor at once, a key-labelled dock fails "his screens are
touch and show none", and a rail that navigates at all is a route *out* of the view, which
`docs/DESIGN.md`'s constraints table forbids outright. The frame is **four owner routes**. This
product will carry two navigational paradigms and that is correct.

**The single most useful finding reframes §0's headline number.** The review screen's 752px of
empty width is not idle waste sitting beside a badly-sized photo — it is the *cause* of the
photo's size. `ReviewQueue.css:93` caps the image at `--photo-cap: 48vh` = 432px, because
everything stacks in one 688px column and the sentence plus first candidate must stay visible.
The card therefore draws 309x432 = **10.3% of the viewport** for the one thing that screen
exists to show. Splitting photo and candidates side by side takes it to 551x769 = **32.7%**,
which is **3.17x the area**, and retires the cap rather than tuning it.

**What the research vindicates, so it is not re-litigated**: no overlays (Figma shipped floating
panels in UI3 beta and reversed them — they "cramped the canvas" and measurably slowed power
users); `[` and `]` as bare zone toggles (Linear ships exactly this pairing); hash addressing
inside a one-page shell (Linear ships full history too); one bare key per candidate with no
modifier and no confirm (Prodigy sustains ~2.9s/item on bare digits; Label Studio requires
Ctrl+Enter and is nobody's throughput reference); one card at a time, photo first (RSNA measured
stack mode 3.2-5.7x faster than tile, P=.0002); expensive-first sorting (active worklist
reordering cut turnaround 43.7% where decoration-only cut 7.6%); and D29's group answer, which
MorphoCluster shows raises macro precision to 0.949 from 0.738 — so D29's safety hedge points at
the wrong risk.

**The strongest argument against the whole direction, kept because it is strong**: the frame
fixes none of the four measured defects, and two of its three zones already exist —
`CaptureScreen.css:151` and `BoxBrowse.css:137` are already rail|stage layouts, and the 240px
header and the y=482 photo happened *inside* them. Every item in the ranked list is achievable
without a frame. The correct response is sequencing rather than argument: build the ANSWER
posture first, on the route where the measured harm is largest, and let it earn the rest.

---

## 5. Two defects found while measuring, which are not proposals

Both are real today, in the tree, independent of anything above.

1. **`#/fulfillment` renders all 682 records — a 124,348px scroll.** The Fulfiller's default
   view is every card in the store at his 20px floor. At 682 cards it is 138 viewports; the
   store is designed for tens of thousands. This is a scaling bug in the one view whose whole
   design is a floor, and `app/tests/fulfillment.spec.ts` cannot see it because every
   constraint it asserts is still met on each row.
2. **`#/inventory` opens the photograph of the card you clicked at y=482 of a 900px
   viewport**, so it ends at y=917 and is cut off — the image is 435px tall, its shape now
   reserved by `0d1bd60`, which fixed the shake without moving the origin. The cause is stacking order rather
   than spacing: `BoxOps`' box header (190px) and its *Layout and controls* fold, then
   `RunPanel`'s *Runs* fold (76px collapsed), all sit above the card detail in the same
   column. Both folds are correctly collapsed by default and both are still paying 266px of
   vertical rent above the screen's subject. Re-ordering the column so the detail sits
   directly under the box header would cost nothing and is independent of every proposal
   above.

---

## 6. Proposal D — **The Repair**: no frame, four screens fixed where they stand

**RECORDED 2026-08-24, and it is the direct consequence of §4.5's strongest counterargument.**
That argument was: the frame fixes none of the four measured defects, two of its three zones
already exist, and every item in the ranked list is achievable without it. Taken seriously,
that is not a caveat on the Rig — it is a fourth proposal, and it is the cheapest one on the
table.

**The thesis, verified in the tree.** `CaptureScreen.css:151` is already
`grid-template-columns: var(--side-w) minmax(0, 1fr)`. `BoxBrowse.css:137` is already
`minmax(300px, 380px) minmax(0, 1fr)`. Both are rail-and-stage layouts today, and **the 240px
header and the y=482 photograph happened inside them**. A frame cannot fix a stacking order.
Every measured defect is a decision about what sits above what, inside a column that exists.

**Four edits, no new routes, no shell change:**

1. **`#/review` — split the column, move the worklist out, retire `--photo-cap`.** The card
   goes from 10.3% of the viewport to a projected 32.7% (3.17x the area) and the 4,018px of
   scroll goes to zero. What sits beside the card becomes the **last ten decisions** — what is
   behind you, not ahead of you — which is Prodigy's shape and Zendesk's stated reason. The
   price-band sort is not lost: `store/queues.py:sort_key` already orders expensive-first
   server-side, so the operator gets the benefit without paying 3,318px to look at it.
2. **`#/review` — a 1:1 sheen inset**, ~400x300 native pixels, prefetched with the next card.
   The one change that raises accuracy rather than speed: FADGI and Metamorfoze both require
   this judgment at 100%, and detection was wrong on 230 of 544 with 19 of 40 frames
   disagreeing with themselves across downscales.
3. **`#/inventory` — put the card detail above the two folds.** The folds move onto the head
   line. The clicked card's photograph opens at y=115 instead of y=482 and stops being cut
   off. **This is a reorder of one column and nothing else.**
4. **`#/fulfillment` — search-first, no default full list.** The 124,348px scroll is a scaling
   defect, not a navigation one, and all nine floors stay green.

**What the Rig was right about survives as CONVENTION rather than architecture**, and costs
nothing here because the routes already exist: each route declares its layout and never
reflows (radiology's hanging protocol, applied per screen — the fix is that the width is
*declared*, not that every screen shares one); deep operations push rather than cover; the URL
addresses the subject.

**What is dropped**: the global frame, the box rail as primary navigator (past ~15 boxes it
scrolls, its items move, and the stable-coordinate claim that is the frame's whole case is
gone), and zone collapse on `[` / `]` — there is nothing to collapse once each screen is sized
for its own task.

**THE CAPTURE PANE-RATIO ITEM IS WITHDRAWN, and the owner is why.** This section first
proposed collapsing Live to a strip during a run so Last Capture could grow, on the research's
finding that no surveyed capture UI draws the two coequal. The owner, on seeing the drawing:
*"Your #3 is wrong because 16:9 is landscape and we use portrait."*

Correct, and it removes the proposal rather than merely re-drawing it. The rig's camera is
side-mounted (D13), so `.capture-frame-portrait` applies: `aspect-ratio: 9/16`, and
`.capture-stage-portrait` sizes the pair by HEIGHT then centres it. At 1440x900 the derivation
resolves to **`--portrait-by-height` 748px against `--portrait-by-width` 827px — height binds**,
giving two 421x748 frames with 96px of centring slack in a 970px stage. **A frame already as
tall as the stage allows cannot grow when width is freed beside it**, so collapsing Live buys
nothing. The "recover ~485px" figure was landscape arithmetic applied to a portrait rig.

**What survives is not a layout change at all**: at 623ms nobody verifies a write by looking at
an image, and the panel's stated job — making a failed write visible — is a counter's job being
done badly by a photograph. The repo already computes the right instrument ("85 records at
indices 1..85, zero gaps, 85 distinct `capture_id`s"); it has never been on a screen. That is
the whole of the capture item now, and it is XS.

**Recorded at length because it is the second miss on this one screen.** The first drawing gave
Live the whole stage and Last Capture a 16%-height strip; the second drew both panes landscape.
Both times the source said otherwise in plain sight — `.capture-frame-portrait` has been in the
file since 2026-08-23, and `docs/specs/ui-research.md`'s own correction list opens by noting
that "the 16:9 waste is real only at rotation 0". The evidence was in hand and went unused
twice. **The capture screen's geometry is read before it is drawn, not after.**

**The sequencing rule, which is the whole point of this proposal:** do the review split first,
because it carries the largest measured harm. **If it does not deliver, nothing after it is
worth building — and no frame was rewritten to find out.**

---

## 7. THE REPAIR, AS BUILT — 2026-08-24

Proposal D shipped. Every item measured, on the owner's instruction to complete the plan.

| # | Change | Measured result | State |
|---|---|---|---|
| 1 | `#/review` splits: photograph beside the choices | photo 8.1% -> **23.6%** of viewport (2.91x area); page scroll 2,356px -> **0**; third candidate row was cut off, now every row is on screen | BUILT |
| 2 | 1:1 sheen loupe, `background-size: auto` | native pixels at 240x180, inside the frame, no second request | BUILT |
| 3 | `#/inventory` card detail above the folds | detail y=413 -> **y=115**; photo y=482 (cut off at 917) -> **y=184** | BUILT |
| 4 | `#/fulfillment` caps the default list | **124,348px -> 4,693px** against the real 682 cards; all 42 of his assertions still pass | BUILT |
| 5 | review undo: depth 10, no clock | verified live — three answers still reversible at 35s, where the old window dropped them at 20 | BUILT |
| 6 | capture run counter | arithmetic correct on 7 cases incl. a gap and a replayed `capture_id`; render typechecked, NOT browser-verified | BUILT, partly verified |
| 7 | grey patch on the tray | **physical, not code — see below** | NOT DONE, owner's to do |
| + | `app/tests/review.spec.ts` | 9 assertions, all passing; 113 across every suite | BUILT |

**Two deviations from the plan, both deliberate and both argued where they landed.** The
worklist was NOT replaced by a last-ten-decisions list — beside the card it costs no vertical
budget, it is the only rendering of "the ordering is visible", and the replacement would empty
on every reload including the `R` the server prescribes in six refusal messages; it got a
`max-height` and its own overflow instead, which fixes the scroll completely. And `--photo-cap`
was NOT retired — its two readers are D28's reservation and their being one expression is what
makes it exact — so the value was rebased and both readers left alone.

**Three defects were found by doing the work rather than by looking for them**: the served
frame is 9:16 and every area figure in this file and in `ui-research.md` was computed from a
bare card's 63:88; `store/queues.py:sort_key` stopped being purely expensive-first when the
starvation tier landed, so `docs/DESIGN.md`'s "that ordering is visible" was already false; and
`app/src/App.css`'s nav strip did not wrap, so **every owner screen inherited a sideways scroll
to 557px on a 375px viewport** from the shell.

### 7.1 Item 7 — the grey patch, which is the highest leverage-per-dollar item here

**It is not a UI change and no session can complete it, because it is a piece of card.** Stated
here so it stops being carried as an unfinished software task.

**What to do**: print a neutral grey patch — an 18% grey card, or the grey row of any colour
target — and fix it to the tray inside the camera's field, within about 5cm of where the card
lands, in the same plane. Metamorfoze 3.2 requires a workflow target in every preservation
master for exactly this reason, "to compare the stability of the image performance over a
series of images or scans"; RBGE mounts a fixed chart and scale bar on the backboard. It
survives D32's crop, because that crop is in memory at identify time and the stored frame is
untouched.

**What it buys, and why it is worth more than anything above.** Two runs have now concluded
"systematic sheen under the rig's lighting" — 30% at Gate B, **42% on box 2 with the owner
supplying ground truth** — from entirely INDIRECT evidence. A patch of known reflectance in
every frame turns that into a per-card number computed locally and free, and it makes D3's own
stated re-enable condition — *"a rig that measures better"* — a thing that can be TESTED rather
than asserted. `join --bypass` currently exists because nobody can measure the lamp.

**What it does not need**: a decision entry, a route, or a line of code. Once the patch is in
frame, the measurement is a few lines against `geometry/`, and that is worth writing only after
the patch exists — code that reads a target no photograph contains is the shape this repo calls
built-but-unreachable.
