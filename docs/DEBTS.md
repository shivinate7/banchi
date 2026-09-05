# Known gaps, deliberately unfixed

Findings recorded rather than repaired. Each says what is wrong, what it costs, and why it is
not fixed. This file exists so a green `make docs-audit` is not read as "the auditor is
complete" — it means the checks that exist, passed.

Not a backlog to burn down on sight. An entry leaves when someone argues it should, the way
`docs/DECISIONS.md` entries are argued.

**Grouped by the work that would close them, not by when they were found** (2026-08-30). The
old chronological order hid the fact that five separate entries were one defect, and put two
one-line UI questions eleven sections apart. Each cluster names what unblocks it.

**Swept 2026-08-30**, from 1,401 lines. The majority was closure narrative for defects nobody
can hit any more; it is in git. Every surviving entry was re-checked against the tree, and
**three were wrong**:

- `check dispatch` said `--self-test` is "on no gate at all: not the pre-commit hook, not
  `make check`". `make check` has run `audit-self-test` since 2026-08-24 — recorded 900 lines
  further down in this same file.
- The `fixtures/` entry called a commit-time byte check "the tractable route, named rather
  than built". `scripts/githooks/pre-commit` has done exactly that since the repo's first
  commit.
- The registry table claimed six fields were read by nothing. Five now have consumers.

**The lesson, which is this file's own failure mode turned on itself:** an entry naming a
residue is a claim about the code, and no row of `make docs-audit` reads a claim made here. A
cluster is worth what a human re-checking it is worth, and that had not happened in
seventeen days.

---

## 1 — The reverse direction: five checks walk docs→code and never back

**One defect, five sites.** Each row proves everything *published* is consistent, and none can
see something real that was never published.

| check | what is invisible | live example |
|---|---|---|
| `tested_by reach` | a module a test exercises, carrying no claim | `store/cache.py` |
| `env vars` | a real variable documented nowhere | `PKMNSCAN_ALLOWED_ORIGINS` |
| `reason codes` | a reason the pipeline emits and nothing publishes | `rarity_claim_mismatch` |
| the game registry | a field whose consumer arrived, roster unstruck | five of six, silently |
| `governed_by` | the map may know less than the code, never more | three illustrative citations |

**THE BLOCKER IS ONE DECISION, AND IT IS THE SAME ONE FIVE TIMES.** Finding "a real
environment variable", "a reason rather than a ladder stage", "a module a test covers" each
needs a heuristic, and D16 puts a heuristic on a *blocking* row out of bounds — a row that
guesses and stops commits is how a gate gets switched off. The honest options are an
**advisory severity** or an **explicit roster the module publishes**, and neither has been
costed. **Fanning agents at these five separately produces five different answers to that one
question.** Settle it in a decision entry first; afterwards they are five independent edits in
five different modules.

**`tested_by`.** 39 claims, every cited test reaches the package it names. `store/cache.py` is
reached by T7 through a session, asserts nothing of its own, carries no claim, and
`docs/map.py` says so at the entry. `store/queues.py` was the second case until 2026-08-22,
when `check_queue_supersede` began asserting `queues.apply_run` and the entry gained the claim
it had earned — **nothing detected that; a human did.** Closing it means ruling that "a test
imports it" equals "a test covers it", which is what the row's own name refuses to say.

**`env vars`.** Walks docs→code only. Found 2026-08-23 by a test author, not by the audit:
`PKMNSCAN_ALLOWED_ORIGINS` — the allowlist standing between an unrelated browser tab and a
hard delete — existed for a day and a half documented nowhere while the row read "all real".
So did `PKMNSCAN_EXPORTS`. **The part worth keeping is the comment that sat above one of
them**, asserting in prose that the variable was documented the same day and that a blocking
check would fail a commit otherwise. Both halves false, the second about the very mechanism it
invoked. That comment is a correction now, kept where the next person looks.

**`reason codes`.** Four reconciliations, all starting from the labels or the doc. Found
2026-08-23 live: `rarity_claim_mismatch` was defined in `pipeline/variant.py`, emitted by the
ladder, carried by neither `REASON_LABELS` nor `docs/DESIGN.md` — and the row read **green**.
Had it fired, the queue would have drawn a bare machine string, the exact outcome the two-size
label rule exists to prevent. The fifth direction needs telling a reason from a ladder stage
by walking the AST for `Resolution(stage=REVIEW, reason=NAME)` — deterministic and
blocking-grade, but coupled to that call shape; or the roster `pipeline/routing.py` already
half has in `UNPRICEABLE_REASONS`. The row reads **14 enumerated, 14 labelled** on 2026-08-30:
twelve when the defect was live, thirteen after the hand repair, fourteen now. Every move was
made correctly by a session that remembered.

**The registry.** Four audit rows sweep `pipeline/games.py` and every one compares it against
the *exports*. Nothing compares it against the *code*, so a field can be perfectly consistent
and entirely inert — **and can stop being inert without anything saying so.** Re-walked
2026-08-30:

| field | 2026-08-23 | 2026-08-30 |
|---|---|---|
| `located`, `card_aspect`, `crop_bands` | closed | closed |
| `finish_by_rarity` | nothing | **`app/src/CaptureScreen.tsx` unions it over the claimed rarities. D23's chip narrowing is built** |
| `product_line` | nothing | **`pipeline/join.py`, `cli/resolve.py`, `pipeline/pricehistory.py`. D25's "real reader" is built** |
| `product_line_rarities` | nothing | **`pipeline/join.py` narrows a claimant's rows by it** |
| `rarities` | emptiness guard only | **validated at `identify/sidecar.py`, checked at `server/capture_server.py`, rendered as the stack claim** |
| `prompt` (per-card) | nothing | **still nothing — see cluster 3** |

D22 says "a field no consumer reads is a field nothing keeps honest". The correction is that
nothing kept the roster of unread fields honest either.

**`governed_by`.** Enforced one way: the map may not know less than the code's own citations,
and may say anything beyond them. Three files are listed under decisions they do not implement
— `scripts/docs-audit.py` names `D2` in a comment about citations, `scripts/decision-context.py`
names `D2` and `D3` as worked examples. Each is labelled as such in the map; the expensive side
would be the rule guessing which citations count.

---

## 2 — The map's reach

**Unblocked and small. Cluster 1's `governed_by` row belongs here too; it is filed there
because it shares that cluster's decision.**

### The orphan rule cannot see an extensionless file, and those are the three enforcement seams

`scripts/docs-audit.py:scan_plan` rejects any `source_suffixes` member not starting with a
dot, so no declaration can reach a filename without an extension. Recorded 2026-08-13 as a
thought experiment — *"creating a second extensionless hook beside it — a `pre-push`, say —
left the row reading `ok repo map` at exit 0."*

**D42 then committed that exact file.** `scripts/githooks/pre-push` and
`scripts/githooks/reference-transaction` arrived 2026-08-29 and the rule was silent for both;
they are in `docs/map.py` by hand and nothing would have failed had the author forgotten. The
same commit added `scripts/githooks-selftest.sh` one directory up, which carries a declared
suffix and duly **failed the commit** until it was described. **One commit, both outcomes: the
rule's coverage is decided by whether a filename happens to have a dot in it.**

**What it now protects is what moves the priority.** The unscanned directory held one file
when this was written. It holds three — `pre-commit`, `pre-push`, `reference-transaction` — so
the files the rule cannot see are the commit path, the push path and the ref path. Every
enforcement seam, none scanned. Their *disappearance* is caught, because each is listed; a
fourth sibling's arrival is not.

**The fix exists a few hundred lines away.** `code_haystack()` reaches that same file by
handing `_walk` the whole filename as a suffix. Not done because it changes what
`source_suffixes` means; `docs/map.py` records the hole at the `scripts/` entry.

### An entry proves a file is described, never that the description is true

165 hand-written lines. A `does` describing the wrong file passes exactly as well, and there
is no equivalent fix — an import is in a parse or it is not, a sentence about what a file does
is neither. Two specifics: **a stale cross-reference in prose is invisible to every row** (the
two orphan-rule entries each described the other's coverage, written in one run by different
hands, and nothing would ever have told either); and **`.json` is deliberately outside `app/`'s
suffixes**, since including it would conscript `app/package-lock.json` — so `app/package.json`,
holding the npm scripts `make lint`, `make typecheck` and `make design-check` all run through,
has no entry.

---

## 3 — The claim chain

**Three entries. The first two overlap in files; none is parallel with another.**

### A capture-time claim crosses ten hops and nothing binds them together

Recorded 2026-08-22 from the multi-game work (D21-D25). Each operator claim is one value
carried by hand through independent restatements; the chain is the finding:

1. `app/src/CaptureScreen.tsx` — the control and its client state
2. `app/src/types.ts` — the shape the wire speaks
3. `app/src/server.ts` — the body `POST /capture` sends
4. `server/capture_server.py` — the route pulling the field off it
5. `server/capture_server.py:sidecar_payload` — the JSON beside the photo
6. `server/capture_server.py:PUT_FIELDS` — what the correction route may change
7. `store/master.py:Card` — the dataclass field
8. `store/master.py:Inventory.parse` — the reload filter
9. `store/master.py:allocate_capture` — the keyword pass-through
10. `identify/sidecar.py` then `pipeline/join.py` — the consumer that reads the claim

**Hops 4-10 were bound on 2026-08-23** by `CAPTURE_CLAIM_FIELDS`, which drives
`record_capture`'s upsert, `allocate_capture`'s pass-through, `sidecar_payload` (via
`CLAIM_WIRE_NAMES`) and `PUT_FIELDS` (derived, no longer a literal), with an import-time
assertion that every name is declared on `Card`. T7's `check_capture_claim_chain` iterates the
tuple, so a new claim is covered the day it is added.

**What is still unbound.** The three app-side hops, permanently: no Python constant reaches a
`.tsx`, and `make typecheck` sees a field *added* to `app/src/types.ts`, never one omitted.
And **a fourth restatement** — `cli/cmd_identify.py` builds a `master.Card(...)` literally
rather than through `allocate_capture`, so it carries the claim names by hand. Correct today,
unbound tomorrow; the site says so in a comment. **That one IS closable** and is the only
tractable half.

**Cost, and it is paid at the wrong moment.** Every symptom appears at the far end — a claim
missing from a sidecar, a finish reverting after a correction — and debugging starts at the
screen. Gate B's six defects included one of this family: review answers written by a route
nothing on the join path consumed, which took a real run to find.

### The operator's `note` never reaches the model

`identify/prompt.py:user_text` takes `set_hint`, `with_crops`, `strategy` and `rarity_claim`.
It takes no note. The note is carried faithfully everywhere else — `identify/sidecar.py`
reads it, `cli/cmd_identify.py` records it, `CAPTURE_CLAIM_FIELDS` keeps it — and the one
consumer that could act on it never sees it. **It is the whole point of the field for `misc`**,
the game naming a card the model most needs help with, where the note stands in for a set hint
that does not exist.

**Why not threaded through `set_hint`.** That rides on templates the file owns
(`user_with_hint`, `hint_clause`), and smuggling a note down that path tells the model the note
is a stack label. Doing it properly means `Profile` growing a note clause and `user_text` a
parameter — a prompt-contract change with its own fingerprint questions, since
`prompt_fingerprint` hashes both user turns and T1's recorded scores are evidence about the
bytes that exist today.

### `app/src/readiness.ts` is a second `blocking`, and nothing reconciles the two

`app/src/readiness.ts:owed` is a second implementation of `pipeline/decisions.py:blocking` so
`#/pricing`'s ready line settles on the keystroke that satisfies it, with no round trip — D54's
choice, and the right one for a line whose whole value is that it is instant. **Its header
claimed an `emit readiness` row in `scripts/docs-audit.py` and a Makefile target,
`readiness-agreement`, until 2026-09-02, and neither has ever existed.** `OWED_REASONS` was shaped as a flat
literal for a parser nobody wrote.

**What it costs.** The two can disagree and nothing says so: when `blocking` gains a refusal,
the line keeps saying *Pricing is answered* while `emit` refuses, and the operator learns it
from the emit's stdout. The one live defense is the roster on `GET /pipeline/pricing`, which
asks the Python that actually refuses — so a chip and the line can disagree, and the chip is
the one that is right.

**Why not fixed.** The honest check reconciles a vocabulary — `OWED_REASONS` against the
reasons `blocking` can return — and `blocking` builds its reasons as sentences rather than off
a tuple, so the row needs a roster the Python does not publish. That is cluster 1's decision
again, asked of one more module. Until it is settled the header says nothing audits it, which
is the claim this file exists to keep true.

---

## 4 — Criteria and evidence: nine ways a row goes quiet

Recorded 2026-08-11. **One file (`scripts/docs-audit.py`) and one spec
(`docs/specs/criteria-binding.md`), so this parallelizes as a focused pass and not across
agents.** Re-checked 2026-08-30: `EVIDENCE_SOURCES` is still three bare literals nothing
resolves.

- **`criteria evidence` can go silent.** If the score file's `test` value stops matching the
  filename-derived key, the row compares nothing and still reports `gate field published`.
  Trigger is narrow — hand-editing `NAME` in `harness/tests/t1_id_eval.py` — but there is no
  ADVISORY downgrade for the "could not look" state. First thing to build in
  `docs/specs/criteria-binding.md`, because the threshold fix walks straight into it.
- **It never opens the value it names.** `holdout_accuracy: null` — a run that measured
  nothing — still reports `gate field published`.
- **`Pass:` matching is narrow and one-sided.** `startswith("Pass:")` misses `**Pass**:`, the
  spelling `docs/GATES.md` itself uses; absence is deliberately not a finding, so a bolded
  stale claim is exempt. Both comparison legs are containment, so `docs/GATES.md` may publish
  a *longer* threshold than the test enforces and stay green.
- **The number leg is substring containment.** `"0.9"` is contained in `"0.95"`, so a loosened
  threshold satisfies the check against an unchanged doc.
- **`EVIDENCE_SOURCES` is three unvalidated path literals.** Nothing resolves them, so renaming
  any of the three silently retires the `evidence freshness` row.
- **The evidence glob assumes one convention.** `t1*.json` — a score file named otherwise is
  invisible rather than a finding, while the summary claims coverage across all registered
  tests.
- **`harness/results/` filenames encode the hint mode but not the split**, so a tune-only run
  overwrites the committed holdout score.
- **A partial `make audit-history` replay exits 0** and silently deflates every per-check total,
  with no denominator on any row.
- **An empty requested split raises `ZeroDivisionError`** in `harness/tests/t1_id_eval.py`
  instead of reporting a clean failure.

---

## 5 — The departed card on screen

**Unblocked, two files, parallel with everything.** Both are D68's residue.

### The copies list says the state twice on every departed row

Each departed row draws the word twice at 11px about 40px apart: `.card-locations-state` in
`app/src/CardLocations.tsx`, which is `copy.state` verbatim, and `app/src/Inventory.tsx:Action`'s
fallback, which prints the same word for the door the copy left by. **They can never disagree,
because the second is derived from the first** — `sold`/`sold`, `retired`/`retired` — which is
what makes it a duplication rather than two facts that coincide. Confirmed unchanged
2026-08-30.

**Why it is a question and not a wire.** The state span is the pipeline's own word on the
screen where grepping what you saw is worth a machine string. The action slot is D57's — it
becomes `Undo` for twenty seconds after a sale, and the word is the fallback. And `Action`'s
**other** call site, the lone-copy branch, has no state span beside it, so nulling the fallback
loses the fact on the 92% of the store with no group. The honest fix is per-call-site and it is
a D57 ruling. **The Fulfiller's skin already does the other thing** (`sold ? null :`), so the
two skins disagree today.

### The component gallery has no departed case

`app/src/Gallery.tsx` draws four position bars and a pull-confirm in three states, and every
place fixture is a live card — the one `sold` copy still carries a live card's place. The
departed rendering (plain label, demoted store key, absent bar) is a real state of two
components and appears in no catalogue. **Cost is low and specific**: the gallery is where a
treatment is checked against the tokens rather than through a screen's layout, and the departed
row is the one that was found drawn wrong by looking at it. Nothing checks the gallery is
complete.

---

## 6 — Measured against one rig, or not at all

**Blocked on the owner, not on code.**

### The border search is measured against one rig, on one day

`geometry/detect.py`'s tone path scored **0 of 53** against the Gate B photographs on
2026-08-22; a border search was added that finds 53/53, covered by T6's `_rig_scene`.

**The synthetic case reproduces a mechanism, not a photograph.** `_rig_scene` is built from the
measured numbers — border-ring sides 33 / 65 / 82 / 66, artwork spanning 88 to 231 — and does
make the tone path refuse for the reason the rig makes it refuse. It is still a drawing. There
is no rig photo in this repo and cannot be: `captures/` is gitignored twice, once under an
opsec heading. **The harness can prove the mechanism and can never prove the lighting.**

**The 53 are one sample of one rig state** — one camera position, one lamp, one afternoon, one
set. A second lighting setup, a sleeved card, a foil under raking light or a black-bordered card
on a dark mat are all untested. 53 is a great deal more than zero; it is not a detection rate.

**What would close it**: a second physical run under deliberately different lighting, scored
through `detect_card` and committed the way T1's score is. That needs a ruling on **where rig
photographs may live**, given the opsec rule keeping `captures/` out of git. Not blocking
anything — Gate B produced 53/53 at high confidence with zero retries, so `detect_card` was
never reached in anger.

### What T7 leaves uncovered in `server/`

- **Twenty-way contention.** T7 runs two and four simultaneous captures, matching D5's two
  devices. The twenty-way case is what found `request_queue_size` at its default of 5 — 8
  served, 12 reset by the OS — and re-running it every turn buys nothing the smaller case does
  not. If that constant is ever lowered, nothing will notice.
- **The bare-interpreter start.** The server runs on system `python3` with no venv, which is
  what makes `python3` rather than `$(PYTHON)` correct in the Makefile. T7 imports the module
  under whichever interpreter runs the harness, so it cannot see this.

Both cost more at every turn end than they can return.

---

## 7 — The preview crops the card, and the one check that looks at a photo cannot see it

**Blocked on a ruling, not on code.** Found 2026-08-31 by the owner, on the screen, looking at
cards photographed the night before.

### `object-fit: cover` is centred on the frame, and the card is not

Five stylesheets draw a stored photograph into a `63 / 88` box under `object-fit: cover`:
`app/src/BoxBrowse.css` (the `#/inventory` preview), `app/src/Inventory.css` (sell-confirm),
`app/src/CardLocations.css`, `app/src/Fulfillment.css` and `app/src/Pricing.css`. The frames are
2160x3840 — aspect 0.5625 — and the box is 0.7159, so `cover` scales to the width and keeps
**10.71% to 89.29% of the frame height, 411px discarded at each end**. Default `object-position`
is `50% 50%`, so the window is nailed to the centre of the FRAME whatever the card is doing.

**The slack was always about three points wide and D32 measured it without anyone reading it that
way.** That entry records cards filling 61–72% of the frame height; against a 78.57% window a
perfectly centred card has 3.3 to 8.8 points of frame height per side before an edge goes.

**Measured, 48 box-3 frames sampled evenly, `detect_card` at 48/48 with zero refusals:**

| | |
|---|---|
| card top | 2.0% .. 71.9% (window opens at 10.71%) |
| card bottom | 73.2% .. 98.0% (window closes at 89.29%) |
| clipped at the bottom | 34 of 48 |
| clipped at the top | 16 of 48 |
| worst bottom loss | 333px of cardboard |

Bottom loss is what gets noticed because the collector number and the set line print there. The
survey passed `card_rect`'s corrected box at the default 0.716; three frames were checked
against the photographs by eye and the rest were not, so the per-frame rows are indicative and
the counts are the claim.

### Why `make design-check` is green over it

`docs/DESIGN.md`'s floor is `>= 320px` on the short edge of the pull-modal photo, asserted at
`app/tests/fulfillment.spec.ts`. Its `paintedPhoto` helper resolves `object-fit` properly —
`cover`, `contain`, `scale-down`, `none` and `fill` each get their own scale — so it measures how
large the photograph is **drawn**. It has no way to ask whether the CARD is inside what was
drawn, and under `cover` it never can: the frame fills the box by construction, so the painted
short edge IS the box and the row passes at exactly the moment the card is being cut. **A floor
on size is not a floor on content**, and this is the second time that distinction has cost
something here — the same helper's own comment draws it, about a broken image that still has a
layout box.

Closing it needs the thing the assertion does not have: where the card is. `detect_card` answers
that, and putting a detector behind a Playwright row buys a check that is slower than the suite
it joins and can refuse. Not costed.

### Neither fix is a stylesheet edit, which is why this is recorded

**`object-fit: contain` fails the floor it would have to clear.** `.fulfillment-photo` is
`min(360px, 100%)` at `63 / 88`, so 360 x 503; `contain` scales by
`min(360/2160, 503/3840)` = 0.131 and paints **283px** on the short edge, under the 320 floor.
Computed from the helper's own formula rather than observed in a run. The box would have to reach
407px to hold the floor and it is capped at 360, so `contain` is unavailable on the Fulfiller's
screen without reopening that row of the constraints table — which D31 says is not his to
reopen. On the owner's screens nothing checks it, and the cost there is size: the frame draws at
78.6% of the box width and the card lands at 63–69% of it, against 80–88% today.

**The server crop is mostly wiring and four open questions.** `identify/images.py:crop_rect` is
already extracted so a second caller can draw the rectangle the pipeline cuts, and
`POST /pipeline/crop-preview` already detects and serves for `#/runs`; a third caller of the same
function is D32's own rule rather than an exception to it. What is not answered:

- **Latency forces a cache.** D32 measured ~115ms per card for the crop preview. `GET /photo` is
  hit on every arrow-key step of the browse walk and auto-repeat is faster than that; the runs
  panel bought its way out with a 140ms debounce and a photo route cannot debounce.
- **The rect has no home.** A capture sidecar is `{box, game, index, rarity_claim}` today. Adding
  the rectangle makes this a capture-write change plus a backfill over every photograph already
  on disk.
- **D32 enumerated the consumers that keep the whole frame** — the review queue photograph a
  human judges foil against, the pull preview matched to a physical slot, the re-shoot comparison
  — and the browse preview is on that list. Per-request cropping honours *in memory, never on
  disk*, and still needs an amendment saying why identifying a card differs from judging one.
  `app/src/ReviewQueue.css` deliberately sets no `object-fit` and should keep the frame either
  way.
- **A refusal renders as today.** `detect_card` returning `None` means the whole frame, which is
  the clipping. So the crop narrows the case `contain` answers and does not remove it.

**Not blocked on the games registry.** `card_aspect` is 0.716 for `pokemon`, `pokemon_code`,
`riftbound` and `one_piece`; only `misc` is `None`, which `detect_card` refuses by contract. Box
3 is Riftbound, so the box this was found on is not the blocked case.

**Why it stays open**: the two fixes trade legibility against coverage in opposite directions and
one of them moves a published floor. That is a decision entry, not an edit, and the owner has not
made it.

---

## 8 — Recorded and correctly unfixed

**No work proposed. Here so a green run is not read as a promise none of these exists.**

### The supervisor's four gaps (D53)

It said "Three" over four bullets from the day it was written until 2026-08-30 — the swap gap
was appended without the lead-in being re-read, which is cluster 2's defect at the scale of one
word.

- **A request accepted but not yet inside `_dispatch` is uncounted by the drain.** Window is
  microseconds; closing it means reimplementing `handle_one_request` in the file that most wants
  to stay boring.
- **The parse pre-check catches syntax errors only.** `scripts/serve.py` refuses to restart into
  a file that does not `compile()`. An `ImportError` or module-scope `NameError` still kills the
  new child and **there is no rollback** — the last-good process is already gone. Containment is
  the fast-failure cap: after five quick deaths it stops respawning, keeps watching, and says so.
  Fixing it properly means the socket-passing design D53 names and rejects for v1.
- **The reload notice has no automated case, and three attempts to write one are why.**
  `ServerReloaded` renders nothing until the boot header CHANGES between two responses. A stub
  over `app/tests/fulfillment.spec.ts`'s helpers did not win the route, `route.fetch()` fails
  outright, and a body-stubbing version left too few requests to produce a second header. **Two
  attempts PASSED against a build with the notice rendered unconditionally** — vacuous — and
  were deleted, because a case that cannot fail is a green row asserting nothing. What IS
  verified: the header observed reaching the browser cross-origin over the real server (eight
  responses carrying `X-Pkmnscan-Boot`), and the notice photographed appearing on `#/inventory`
  after a real restart and NOT on `#/fulfillment`. What guards it structurally is `hasChrome`,
  the nav's own condition, which `fulfillment.spec.ts:noWayOut` already covers.
- **The swap gap.** Between the old child exiting and the new one binding a request gets
  `ECONNREFUSED`, and `app/src/server.ts` deliberately has no retry, so it surfaces as
  `unreachable`. Tens of milliseconds. Named in D53 with the fix considered and declined.

### A Playwright line number is not a line in the file

Playwright strips the TypeScript and reports against the generated file, so a spec loses the
lines its type-only constructs occupied and gains the lines its long ones are re-broken into.
**Wrong for nearly every test in the suite** — 254 of 256 at `3ca904e`, 257 of 259 later —
checked by walking `--reporter=json`'s location for all of them. Measured with a probe: a test
on source line 24 with nothing above it reported 23; the same test on line 27 under a 22-line
`type` block reported 3. Clearing `$TMPDIR/playwright-transform-cache-501` changes nothing.
**Cost: a citation nobody can follow** — a session opening the file at it lands on unrelated
code, silently, because the line is real and the file is right. Grep the TITLE instead; the
reporter prints that too and it is exact. Nothing to fix at 1.55.1; the remedy is to stop
writing the number down.

**The same shape in the docs, and `doc hygiene` sees only its provable half.** Docs carry 52
resolvable `path:line` citations. D74's row catches one failure — a number past the end of its
file — and there are none today. **The common case is invisible**: a citation whose file is
long enough but whose line has moved, which is exactly what `ReviewQueue.css:47` became when
the comment it named slid to line 57. Nothing distinguishes that from a correct citation
without knowing what the line should say. **The remedy is the same one this entry already
gives** — cite the identifier, not the number — and the 2026-08-30 prose sweep applied it
where it rewrote a citation rather than adding a check that cannot exist.

### What is not closed about the `make design-check` flakes

Three flakes were reproduced and fixed 2026-08-30 — a `toBeVisible()` timeout answered by
`expect: { timeout: 15_000 }` in `app/playwright.config.ts`, a two-layout subtraction in
`app/tests/inventory.spec.ts` answered by reading both tops in one `page.evaluate`, and a
snapshot race in `app/tests/shipping.spec.ts` answered by `toHaveText`. None weakened an
assertion.

**A starved rig is not a slow one, and no wait answers it.** At 40 workers against 12 CPU hogs
— 4x oversubscription on a 15-core machine — a context can fail to render at all: with the
allowance at 120s, 10 of 80 still failed and one took 122 seconds. At that load the suite also
loses `app/tests/fulfillment.spec.ts` on `main.fulfillment`, `app/tests/capture-claims.spec.ts`
on the Finish row, and `app/tests/capture-undo.spec.ts` on a capture that never landed — it
expects `Card 10` and the newest is `Card 9`, a **dropped press** rather than a slow one and the
only one a longer wait could never answer. **None of it is reachable from `make design-check`,
which runs 7 workers here.**

**One sighting is unexplained**: at 15 workers, before either fix, `app/tests/cursor.spec.ts`
failed once in nine runs. Its message was not captured.

**Three non-retrying reads remain**, all in `app/tests/inventory.spec.ts`, of the eight
originally counted. None has been observed failing, and `expect(await …innerText())` is a
narrower hazard than the list form that broke. **Two comparisons in the geometry case still
pair an early read with a late one** and are left alone — 8px of declared slack against a
measured 0, and a 41px column gap. A case is not improved by rewriting assertions that have not
failed.

**Two numbers were published against runs nobody read.** A commit message said "design-check
257" when the run was 255 passed and 1 failed and the true count was 256; and the entry above
said five non-retrying reads when there were three. The suite is **264 cases** as this is
written, which is the same lesson a third time: a count recorded here is stale the week after.

### `make check` is not automatic

`--self-test` had been RED for some time — a `tested_by reach` case pinned to T3, T3 began
importing `store`, and the case asserting a false claim stopped catching one — while
`make docs-audit` stayed green and so did every commit, because **nothing ran it**. Closed
2026-08-24: the case moved to T5 and states its requirement in the comment, and `make check`
runs `audit-self-test`.

**Deliberately NOT in the git hook** — D18, not taste: `--self-test` is the one mode of that
script that writes, and nothing that writes may run on the path deciding whether a commit
proceeds.

**Residual:** the Stop hook runs `make harness`, not `make check`, so a red self-test surfaces
only when somebody asks — the same standing `githooks-selftest`, `port-agreement`,
`ignore-check`, `vale` and `lint` all have. And **`--self-test` does not drive a real git
index**: the index-mode primitives have cases, but no case exercises the staged blob. It bites
hardest on `check dispatch`, whose whole subject under `--staged` is the blob. Driven by hand
at integration, and by hand is where it stays.

**`check dispatch` also cannot see its own unwiring.** Delete its call from `audit()` and every
other row prints green, the run exits 0, and the row is absent. A detector cannot detect its own
absence, so there is a root to the recursion: unwire anything else and the commit fails, unwire
*this* and only `--self-test` catches it. Related: **called is not run, and run is not looked** —
a dispatched check returning before its `report.add` prints no row, which `check_raw_color` does
when `app/src/` is absent. And **`scripts/status.py` is not in `INVOKERS`**, so `audit invocation`
does not see its call; it would find nothing if it did, since that row reads flags off a literal
command line and `status.py` builds argv as a list.

### The `fixtures/` guard is one tool wide at write time

`.claude/settings.json` denies `Write(./fixtures/**)` and `Edit(./fixtures/**)`. **Bash is
not**, so a `python3 -c`, a heredoc, `cp` or `sed -i` goes past it silently. Measured by
walking through it: the session that built `fixtures/orders-shipping.csv` wrote it with a
script and only discovered the rule afterwards, when a `Write` into the same directory was
denied. **The guard did not participate in the decision at all.**

**The commit-time half is armed and always was.** `scripts/githooks/pre-commit` refuses any
staged modification under `fixtures/` via `--diff-filter=MDR` — which is the add-vs-modify
distinction the deny rule blurs and this entry once proposed as unbuilt. **So the cost this
entry priced cannot happen**: a modification that never reaches a commit never reaches a later
week. The residue is a confusing half-hour, not lost ground truth — a Bash write lands in the
tree immediately, so `make harness` can go red before anything tries to commit.

**Why the write-time half stays open.** A deny list cannot see what a script writes at run
time, and a pattern broad enough — denying `python3`, or shell redirection — takes
`make harness`, `make check` and `scripts/docs-audit.py` down with it. Same trade D16 refuses
for `--no-verify`. **Not the same gap as the PII one**: this repo has no secret scanning either
(the hook's only content rule is the code-card regex), so a fixture carrying buyer names commits
clean. That is about what is *inside* a file; this is about *which tool* wrote it.

### Nothing in the product reads `history.jsonl`

The three writes that changed no state — a correction, a capture undo, a review answer — all
leave a line as of 2026-08-13, asserted by `check_history` in
`harness/tests/t7_store_and_seams.py`. No route serves the file, no screen shows it, and the
only reader outside the harness is `_state_before_sale`, which looks for states and skips all
three by construction. The audit value is a person with a text editor, which is what an audit
trail is for — but **a line that stops being written is invisible to everything except T7.**
Two by choice: a `PUT` changing no value logs nothing, so a silent sidecar repair leaves no
trace; and the vocabulary lives in two places (`master.STATES` and `SERVER_EVENTS`), so a
reader has to know both.

### D60's guards see tokens, never arguments

`scripts/prose-guard.py` is the only thing comparing two versions of a doc, and it compares
HARD TOKENS — backticked identifiers, paths, decision ids, measurements, dates. **A rewrite
keeping every backtick and losing the reason an entry exists passes silently.** That is the
residual risk of the whole D60 exercise and nothing mechanical can close it: judging whether a
paragraph still carries its argument is D16's layer 3, a model reading prose, deliberately never
a gate. `--facts` is on no gate either — it needs a BEFORE, which exists only while a rewrite is
in flight. The two rows that DO gate, `decision structure` and `entry budget`, check the tree as
it stands and cannot see what a change removed.

### Two documents outran the code

- `docs/specs/audit-retirement.md` restates a check roster and a count the shipped registry no
  longer matches, and `CLAUDE.md` tells sessions to read specs as settled. It needs a status
  line naming which premises failed under execution — **not** a corrected number, which would
  only reset the clock: the restatement is the defect.
- `.claude/commands/docs-audit.md` says exit 2 means the coupling question, but the command it
  prints in step 1 runs without `--staged`, and coupling only runs under `--staged`.

### The second fenced block in `docs/DESIGN.md` is not read

`design tokens` reconciles the `## Tokens` fence against `app/src/tokens.css` both ways, and
`raw color` now blocks a hex anywhere in `app/src/*.css` — which closed the sharper half, the
`#ffffff` in `app/src/PullConfirm.css` that survived a design review and two integration passes.
What is left is a document disagreeing with itself: step 6's three button states restate five of
these hexes in a second fence nothing reads. Left out because D18's instinct is that deleting a
restatement may be the right answer, and that argument belongs in `docs/DESIGN.md`. The sheets
in `docs/design-refs/` stay unchecked for a settled reason — they are drawings of the spec and
are allowed to lose to it.

### `design tokens` locks names for every token and values for only the hexes

Named 2026-09-03, when the row was rewritten for the `--bn-` system. It compares a VALUE only
where `docs/DESIGN.md`'s block states a hex literal — 31 of 100 declared tokens. The other 69 are
checked for existence in both directions and their values are locked nowhere: an alpha of another
token (`ink 8%`), an alias (`--bn-money` = ink in both themes), a duration, an easing curve, a
shadow, a control height.

**That is a real gap and not a shrug, and the shape of it matters.** The dangerous drift this row
exists to catch is a value nobody chose rendering perfectly, and a wrong `cubic-bezier` or a
wrong shadow is exactly that. What stops it being closed by writing more hexes into the document
is that most of these are not hexes: `--bn-line` is *ink at 8%* by design, and spelling its two
rendered values out would create the second source of truth the tint was invented to avoid — the
light and dark values would then have to be kept in step by hand, which is the defect, not the
fix.

**What would close it**: a reader that resolves `color-mix()` and `rgba()` against the token they
reference and compares the resolved value, which is a small CSS color engine and was judged not
worth building for 69 tokens. Until then the row's summary line says how many hexes it compared,
so a green row cannot be read as full coverage.

## 9 — The sigil check matches text, so a renamed local walks past it

`make sigil-check` (D92) refuses a bare `#` composed from an expression naming `index`, which is
what keeps D58's count and the store key from being spelled the same way on one screen. It reads
SOURCE TEXT. `const n = side.index` on one line and `#{n}` on the next is a violation it cannot
see, and so is any indirection through a helper, a destructure or a prop rename.

**The fix that could not be evaded was considered and rejected on blast radius.** A nominal type
over the two numbers — branding `slot` and `index` so the compiler refuses the swap — is the real
answer, and `slot` and `index` are plain numbers across the whole wire contract and forty call
sites. That is a refactor much larger than the bug, and D92 took the cheap check that runs on
every commit over the expensive one nobody would finish.

**What made the ceiling tolerable was where the mistake usually happens.** All four sites the
check found on its first run compose the `#` and the field on ONE line, at the point of render,
because that is what drawing a number looks like. The paragraph here used to end *"the evasion is
available and has never been taken"*, and it was wrong on the day it was written.

**THE TRIGGER HAS FIRED — one violation shipped through the gap, and was found by reading rather
than by running anything (2026-09-04, D92 amended).** `CaptureScreen.tsx` drew
`#{slotNumber(target)}` on every undo thumbnail, and `slotNumber` returned `String(target.index)`
whenever the target carried no rendered label — which is the target `undoStack` composes from the
server's high-water mark after any reload mid-run. The `#` and the field were three functions
apart, so the check read `slotNumber(target)`, found no `index` in it, and passed. It was green
over that line from the day it was written until the sweep D92 deferred was carried out.

**What that changes and what it does not.** It does not change what the check is worth on the
lines it can see: it read 61 files and the sweep found nothing it had missed except this one. It
does mean the nominal type this entry calls *the real answer* now has a shipped defect behind it
rather than a hypothetical, and D92's rejection of it on blast radius was made without one. That
is the owner's call and nobody else's; recording it is what this file is for.

**The cheap partial was taken first, on the owner's ruling (2026-09-04).** Asked whether the
nominal type should be argued now or the guard shipped first, the owner chose the guard. So the
check reads a second pattern: the word form, `Card {…index}`, which is the same claim as `#{…index}`
in the register a screen reader speaks. **It was measured before it was written rather than adopted
on the argument that it sounded cheap** — over every `.ts`/`.tsx` in `app/src` it returns four
violations and nothing else, all four in `RunsComposer.tsx`, and the eight legitimate `Card {…}`
renders standing in the tree fall outside it on the `index` requirement alone. Those eight are
self-test cases now, so the false-positive rate that made it adoptable is asserted rather than
remembered. **The four it found had shipped**: two of them `aria-label`s, on a panel whose figure
names a photograph the run is about to pay to have read.

**What the second pattern does NOT do is close this section.** It is the same text match one word
wider. `const n = side.index` then `Card {n}` walks past both patterns exactly as it walked past
one, and the ceiling this section was opened about is where it was. What changed is that the
sweep D92 deferred is no longer the only thing standing between this class and a screen — for the
two spellings the product actually uses. **Until the nominal type is ruled on, a green run means
"no figure is drawn over a field literally named index on that line, in either of two spellings",
which is more than it meant and still less than it sounds like, and the sweep that catches the rest
is a person reading `app/src` and asking of each figure what number it is.**

**Two the sweep can see and neither pattern can, left deliberately.** `Pricing.tsx:2641` draws
`` `no label · ${photoAt.box}/${photoAt.index}` `` and `Orders.tsx:1205` draws
`` `box ${target.box}, index ${target.index}` ``. Both spell the key in prose with no figure at
all, so no sigil rule reaches them and none should — naming the index *as* the index is the one
thing that is never the confusion. They are here because they are the shape a future reader will
check this file about.
