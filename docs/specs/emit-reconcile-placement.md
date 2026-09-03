# Where `emit` and `reconcile` belong

**Status 2026-09-02 — the textarea, `PUT /pipeline/runs/<name>/decisions` and `remembered_sub_threshold` are deleted (D86 amended); the sub-threshold answer is a store policy with a default (D9 amended); every line below naming them is history.**

**STATUS — the placement answer stands; three of the six items have since been built.**
Re-checked against the tree 2026-08-30. **Items 1, 2 and 3 of §6 are BUILT**: the preset now
moves `rule`/`basis` and `pricing presets` is a blocking audit row guarding it; `#/pricing`
draws the sub-threshold answer and reads `remembered_sub_threshold` (overtaken 2026-09-02); and `app/src/readiness.ts`
computes what a run owes. **Items 5 and 6 are NOT built** — no `#/runs?run=<name>` link exists
and `.run-phase-identifying` still has no `reconcile` sibling. §2.1 and §2.2 are therefore the
record of two defects that were fixed, not two that are live; both are written in the present
tense below and were true when written. **This header read "RECORDED, NOT BUILT. Nothing in
this file is implemented" until 2026-08-30**, by which point the two findings it calls its
sharpest had both shipped.

It answers one question
the owner asked on 2026-08-29 — *"whether emit and reconcile ought to move from the runs page,
to be its own page, or to be within the pricing page"* — and it changes no decision entry. The
work it proposes is ordered and costed at the foot; the status line above says which of it has
since been built.

**Method.** Four agents, four lenses, run in parallel and told to disagree: the command seam
(what each command reads, writes and refuses on), operator ergonomics (route switches, fold
position, keystrokes), an adversarial pass instructed to defend the status quo and find what
every move breaks, and a workflow pass over the real calendar of a box. Three were additionally
pointed at `docs/specs/ui-redesign-options.md` and `docs/specs/ui-research.md`, which had
already argued a neighbouring question and which none of them would otherwise have found.

**Every measurement below was re-checked against the live store before it was written down.**
The agents' numbers are not taken on trust: the run manifests, `decisions.json` contents, and
the three grep results that carry the two defects were verified directly.

---

## 0. THE ANSWER

**Both stay on `#/runs`. Neither moves.** Three of the four lenses reached this independently
and the fourth's case for moving dissolves under its own precondition — see §4.

**And the question is worth less than what answering it turned up.** Two of the three runs on
disk have never emitted, and neither is stuck for a reason a placement change would touch. The
ordered work in §6 is what saves the time; the placement is a scroll.

---

## 1. What was measured

Three run directories exist in the main checkout. Their manifests:

| run | cards | SKUs | sub-threshold | `sub_threshold` answer | emitted |
|---|---|---|---|---|---|
| `2026-08-22-box1-03` | 53 | 45 | 44 | `"floor"` | yes — and reconciled |
| `2026-08-24-box2-01` | 543 | 108 | **108** | `null` | **never** |
| `2026-08-29-box1-01` | 133 | 50 | **42** | `null` | **never** |

Machine time is not the constraint and the panel's own copy is wrong about it.
`RunPanel.tsx`'s `STEPS` calls identify *"Minutes to hours"*; all three runs completed
identification in **2m20s, 6m40s and 3m51s**. The one complete cycle this project has —
Gate B — was 38 minutes end to end in a single sitting, of which roughly 3 minutes was machine
time, 29 minutes was the review queue, and 6m44s was the external TCGplayer errand between
`emit` and `reconcile`.

**So the calendar is not made of stages. It is made of runs that stop.**

---

## 2. TWO DEFECTS, BOTH VERIFIED, BOTH INDEPENDENT OF PLACEMENT

These are the reason the two unfinished runs are unfinished. Neither is a layout question and
neither is fixed by moving a button.

### 2.1 `emit`'s commonest refusal has no control anywhere but a raw textarea (overtaken 2026-09-02)

`pipeline/decisions.py:332` refuses `emit` while `sub_threshold is None` and any sub-threshold
SKU exists. **That check never consults `overrides`** — so pricing all 108 of box 2's SKUs by
hand on `#/pricing` still leaves `emit` refusing. The run-wide answer is settable only by typing
into the `decisions.json` textarea behind the Emit step's "Pricing answers" button on `#/runs` (overtaken 2026-09-02).

D9 makes this disposition a deliberate per-run choice, and it is right to. What is wrong is that
the screen built to answer pricing cannot express it, and the screen that can expresses it as
JSON.

**The server already serves the answer and nothing draws it.**
`server/pipeline_routes.py:1192` computes `_remembered_sub_threshold` (overtaken 2026-09-02), `:1279` puts it on the
pricing payload, and `app/src/types.ts:1304` declares it. No component reads it. The control was
designed for that screen and never built there — `CLAUDE.md`'s route-is-not-a-feature rule, one
field rather than one route.

> **Half of this is fixed, checked 2026-08-30.** `app/src/Pricing.tsx` now draws the
> sub-threshold control and reads `remembered_sub_threshold` (overtaken 2026-09-02), so the textarea is no longer the
> only way to answer — §6 item 2. **The refusal itself is unchanged**: `Decisions.blocking`
> still tests `sub_threshold is None` against the sub-threshold SKUs and still never consults
> `overrides`, so pricing every SKU by hand leaves `emit` refusing exactly as described.

### 2.2 The preset control writes a key nothing reads

`app/src/Pricing.tsx:387` carries the comment *"A PRESET WRITES `rule`/`basis` AND NO
OVERRIDE"*, and the line beneath it writes `preset: key`. **`preset` appears nowhere in
`pipeline/decisions.py`, `cli/` or `server/`** — `Decisions.parse` reads `rule`, `basis`,
`sub_threshold`, `overrides` and `no_market_data`, and drops unknown keys. `cli/cmd_join.py`
writes preset *prices* into `pricing.json` and never reads a chosen preset back.

The consequence is a silent mispricing, and it is D49's own stated failure arriving by the other
road. That entry makes an untouched row write no key on purpose — *"a screen that wrote its
hundred suggestions would produce a run where changing the preset silently changed nothing"* —
which is correct only if the preset moves `rule`/`basis` instead. It does not. So an operator who
picks `Market −5%` and commits nothing gets a run that emits at `match`/`market`, with the −5%
figures still on screen.

**It is on disk.** `2026-08-29-box1-01` reads `preset: market_undercut_5`, `rule: match`,
`basis: market`, two overrides across fifty SKUs.

**This is the sharpest finding in this file and it has nothing to do with the question asked.**

> **FIXED, and it grew a guard.** The press writes `rule`/`basis` and `pricing presets` is now
> a blocking row of `make docs-audit`, reconciling `app/src/Pricing.tsx`'s table against
> `cli/cmd_join.py:PRESETS` key for key and rule for rule. That row's docstring carries this
> finding as the reason it exists, including the measurement on the owner's riftbound run.

---

## 3. Why `emit` reads as misplaced, and why moving it does not fix that

Emit's button sits below a page header, a box picker, an identify step, the run list, an open-run
console, a figures grid and a fully-expanded join step. Estimated at 1440x900 on the realistic
re-entry state — arriving at `#/runs` with no box picked — the control lands around **y≈1,110**,
roughly 210px below the fold. On the same visit as a send, with the crop preview drawn, it is
around y≈1,750.

**The stack decomposes into chrome for steps the operator is not performing.** About 262px of it
is a `max-height: 260px` console (`RunPanel.css:583`) tailing a step that has already finished,
and about 130px is the join step's bypass toggle, two fine notes and three buttons for a join
already run. `.runs` sets no `max-width`, so the four steps stack at full width and emit's two
buttons occupy roughly 90px of a ~1,376px line: **the vertical budget is expensive and the
horizontal budget is 93% idle.**

That is a page-chrome-budget failure, and `docs/specs/ui-research.md` already drew the
distinction that decides it — `#/inventory`'s 240px header was fixed by deleting a title, a lede
and a mode switch, not by re-zoning. **Relocating emit carries ~200px of fresh page chrome to a
new address and leaves every one of those dead pixels standing.**

---

## 4. The three options, and why two lose

### `#/runs` keeps both — ADOPTED

`RunPanel.tsx:108` states why `STEPS` is authored rather than derived: *"a screen that only drew
the current step would leave the operator unable to see that emit exists until join had
finished."* That promise has already been broken once and repaired at cost — the three free steps
once rendered inside the open-run guard, so with no runs on disk *"they existed nowhere on the
screen."* Splitting emit and reconcile onto another route recreates that defect at route scale,
where no guard removal fixes it.

Emit's inputs and its outputs are both here: the run is picked here, and the import CSVs are
rendered from `detail.files` outside the step. `docs/GATES.md` names those files as the gap Gate B
did not close, so a move that separates the press from its receipt gives back the thing the panel
was built to deliver.

### An own route — REFUSED

It is a partial adoption of `docs/specs/ui-redesign-options.md`'s proposal B, whose stops table
lists EMIT and IMPORT as separate destinations, and which `docs/specs/ui-research.md` refuted on
external evidence: Jenkins Blue Ocean deprecated, Dagster beating Airflow by moving further
toward objects, Shopify demoting stage tabs, and no tool with multiple object types navigating by
stage alone.

Two of B's faults do **not** transfer — a move leaving identify and join in place does not repeat
B's omission of `join`, and it does not demote the box axis. The fault that does transfer is the
one that decides it: **each stop needs its own object picker, and the object here is the run.**
An emit route would be the third run picker in the product, against `#/runs`' list and
`#/pricing`'s picker, and D39 spent its whole length preserving exactly one place a selection can
be made.

Then the arithmetic. `docs/DESIGN.md`'s own page chrome is roughly 133px to host two buttons and
a file input totalling about 32px of content — a page that is 96% chrome by the standard it is
being measured against. Plus an eighth route, a nav item, a `group` ruling, and a chord key that
does not exist: `e` is free for Emit, and **Reconcile has no free letter** — `r` is Runs, `c` is
Capture, `i` is Inventory.

And the route count is provably unmaintained. D31 records it false in five places for the whole
of D39's life. **It is false right now in the file that owns the table**: `app/src/App.tsx:14`
opens *"The app shell: six routes"* while line 25 of the same comment says *"SEVEN again now"* and
the table carries seven. Nothing in `scripts/docs-audit.py` reconciles it.

### Into `#/pricing` — REFUSED, and its own argument is why

This is the one lens that argued for a move, and its case is the round trip in §2.1: the operator
prices on `#/pricing`, cannot set `sub_threshold` there, crosses to `#/runs` to type JSON, and
presses emit. Co-locating emit with pricing removes one crossing per run.

**But the precondition it names is the fix that removes its own reason.** That recommendation is
explicitly gated on `#/pricing` first gaining the `sub_threshold` control — and once that control
exists, `emit` has no operator input left on that screen to co-locate with. It becomes a free,
re-runnable, one-press step whose output is a set of files rendered on `#/runs`.

Three further costs make it worse than the link it would replace:

- **A write race that does not exist today.** `Pricing.tsx` autosaves `inventory/prices.json` on every
  commit with in-flight coalescing; `emit` reads that file server-side. An emit button adjacent
  to the autosave loop can fire against the pre-write document. The two writers are currently on
  different routes.
- **A stale run list.** `RunPanel` polls `getRuns()` at 4s/20s because a run started in a
  terminal *begins* live; `Pricing.tsx` calls it once, with no poll.
- **`Pricing.tsx:29`'s "NOTHING HERE SPENDS"** survives only as a technicality — emit is free —
  and D33 refused exactly that kind of narrowing when `capture_server.py`'s old promise went the
  same way.

**Reconcile does not belong there under any reading.** Its input is a file that does not exist
until the operator has left the app, imported to TCGplayer and downloaded Export From Staged; it
reads no pricing answer at all, and its only tie to emit is one manifest key.

---

## 5. What reconcile actually needs, which is not a new address

Reconcile is a different act by input and by question — but the only complete cycle on record put
it **6m44s after emit, in the same sitting**. n=1 is not enough to build a split on.

What it needs is to be *findable on re-entry*. `_phase` draws `reconcile` at 11px in `--muted`,
the quietest register on the panel, while `.run-phase-identifying` gets ink at 600. And
`BoxRuns.tsx:88` filters on `row.live`, so box 2 — parked five days short of emitting — renders
**"Box 2 · nothing running"** on `#/inventory`.

**`_phase` cannot say what a run owes.** Its seven values derive from four manifest booleans, so
`emit` names three different human states at once: joined with cards still in the review queue;
joined and owing a sub-threshold answer emit will refuse over; and genuinely one press from done.
Both stuck runs read `emit`.

---

## 6. The ordered work — items 1, 2 and 3 built since

Costs are relative sizes, not hours. **The heading read "none of it built" until 2026-08-30**;
the `state` column is the re-check against the tree that replaced it.

| # | change | why | size | state |
|---|---|---|---|---|
| 1 | **`preset` moves `rule`/`basis`, or the control stops claiming to** (§2.2) | a silent mispricing, live on disk | S | BUILT |
| 2 | **Draw `sub_threshold` on `#/pricing`** — the payload is already served and typed (§2.1) | unblocks both stuck runs; removes the only argument for moving emit | S | BUILT |
| 3 | **`phase` says what the run owes**, in the run's own unit — `price` with a count where the disposition is unanswered, `answer N` where the queue is non-empty | both stuck runs read `emit` today | M | BUILT |
| 4 | **A finished step's body collapses; its head and note never do** (§3) | puts emit near y≈660, above the fold, with no relocation | M | not verified |
| 5 | **`#/pricing` links back as `#/runs?run=<name>`, and `#/runs` reads it** | the link is one-directional today: `RunPanel.tsx:1603` links out with the run name, `Pricing.tsx` links back bare, and `openRun` is local state with no persistence — so every return costs a re-pick | S | NOT BUILT |
| 6 | **`phase === 'reconcile'` gets the ink-600 treatment** `.run-phase-identifying` has | it is the fact the operator needs on re-entry, drawn in the quietest register | XS | NOT BUILT |

**Item 4 is the only one that touches the thing the question was about**, and it is fourth
because the three above it are worth more.

**Item 4 must not collapse the heads and notes.** `RunPanel.tsx:108`'s promise is about a first
visitor being able to see that the pipeline has four parts; it was never made about a finished
step's console, and the controls are already conditional on `detail !== null`.

---

## 7. What would falsify this

- **The owner says box 2 and box 1 are abandoned experiments rather than parked work.** Then
  nothing is waiting, the multi-day figures measure nothing, and items 3 and 6 are worth
  little. §2's two defects stand regardless. **This is the cheapest question to ask and it
  should be asked first.**
- **Emit measured above the fold after item 4 and still complained about.** Then it is a
  placement problem after all, this analysis was wrong, and `#/pricing`'s header row is the next
  address to try — as an outline control, never a fill, on a screen that currently draws zero.
- **Emit refusals turn out to be the common case rather than the tail.** Measure how many emit
  presses per box return `ok: false`. If the median box needs two or more, the refusal loop
  dominates the session and emit belongs where its remedy is.
- **D49's premise holds** — *"almost everything coming next is all above 0.40"*. Then
  `blocking`'s first reason stops firing, and item 2 matters much less than it does today.
- **The emit→reconcile gap turns out to be days on a real listing box.** Today: n=1, 6m44s,
  13 SKUs, the smallest box. If it lands in days, reconcile is genuinely a different sitting and
  a split is worth arguing then — with evidence.
