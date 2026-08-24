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
  thing that changes. Camera preview while shooting; the card photograph while answering; the
  box walk while browsing; a run's console while it runs.
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
| chrome above content | 46 / 217 / 146px | 0px | 44px | 40px |
| width used, review task | 45.6% | 100% | 100% | 100% |
| scroll for one review card | 4.5 viewports | 0 | 0 | 0 |
| routes | 5 | 1 + Fulfiller | 1 + Fulfiller | 0 + Fulfiller |
| clicks, shoot → CSVs in hand | 3 route changes, 3 folds | 0 route changes, 0 folds | 6 stop clicks, 0 folds | 0 clicks, 4 typed subjects |
| "what do I do next" | terminal only | bead colour | the counts | `?` or a stale breadcrumb |
| decision entries reopened | — | none (DESIGN.md re-argued) | **D31, D33** | D31 softened, DESIGN.md re-argued |
| risk | — | one big tree | demotes the box axis | discoverability |

**They are not equally safe.** A is the largest layout change with the smallest argument to
have — it reopens no decision, because it keeps the box as the unit and only stops paginating
it. B is the largest claim about the product and needs the owner to reopen two entries. C has
the highest ceiling and the sharpest failure mode.

**If one is to be built, A is the one to build first, and B's stage bar is the piece worth
stealing into it.** A rail of boxes with beads and a bar of stages with counts are the same
information at two orientations; A's rail can carry the counts as rows, which is most of B's
benefit without reopening D31. That is a recommendation, not a decision.

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
