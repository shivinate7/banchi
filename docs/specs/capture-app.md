# Capture app — execution spec (build-order step 7)

Written 2026-08-13 by interview, the way `docs/specs/capture-server.md` was. Every choice
below was made by the owner against a stated alternative; where a recommendation was
overruled, the overruled option and its cost are named, because a decision nobody can see
the losing side of is one the next session will quietly reverse.

---

## STATUS — BUILT, AND NOT VALIDATED

**Read this before anything below it.** This spec covers the whole of build-order step 7 and
both halves are built: 7a on 2026-08-13, and 7b — the review queue, the Fulfillment view, the
inventory SKU views and mark-sold — the same day, ahead of Gate B, at the owner's instruction.

**The schedule question is closed and the validation question is not, and this section is
only about the second.** 7b was originally scheduled after the gate so it would be built
against a real run; it was built before instead, and the owner has since confirmed that
ordering is settled rather than an outstanding deviation. Sections 0 and 9 have been
rewritten to describe what this spec covers rather than to forbid what now exists — a
prohibition left standing over built code is read by the next session as a defect report,
which is the opposite of useful.

**What does not change is that nothing here has met a card.** These screens are built *to*
`docs/DESIGN.md` and validated against nothing, because the thing that would validate them
has not happened. That is not an apology for the ordering — it is the same statement
`docs/GATES.md` makes about every other number in this repo, and it is what Gate B is for.

### What "not validated" means, concretely

The data these screens display has never been produced by a real run. Not produced and
awaiting review — never produced. On the day 7b was built, `make status` reported
`inventory/ absent — nothing captured yet` and `runs/ absent — no identify run yet`. No card
has been photographed, no `identify` call has been paid for, and no `review.json` or
`parked.json` has ever existed with a row in it. Every item below is a consequence of that
one fact.

- **The review queue's row hierarchy is tuned against a price distribution nobody has
  measured.** `docs/DESIGN.md` requires the row's name size and its price size to both step
  down as the price does, and a parked row to be dimmed rather than merely lower. That is a
  mapping from dollars to type sizes, and its input is the spread of `market` values in a
  real queue file. The ordering underneath it is real — `store/queues.py:sort_key` is built,
  runs today, and sorts priced-first-descending then box-walk. What it will be handed is a
  guess. Whatever breakpoints the built screen draws, the first real run can invalidate all
  of them without one line of the code being wrong.

- **The twelve reason codes have never all fired, and two of them cannot reach a queue at
  all today — one by construction and one for want of a producer.** Six
  come from `pipeline/variant.py` (`no_catalog_row`, `metadata_not_stocked`,
  `metadata_detection_disagreement`, `detected_finish_not_stocked`, `ambiguous_no_signal`,
  `duplicate_condition`) and six from `pipeline/routing.py` (`low_confidence`, `no_position`,
  `identification_failed`, `set_ambiguous`, `card_not_detected`, `no_market_data`).
  `docs/DESIGN.md` requires each on screen as a human label with the machine string small
  beneath it, so twelve human labels now exist — and each one is a translation of a string
  that has never been seen attached to a photograph of a card. A label written for a code
  that fires weekly and a label written for a code that fires once a year are different
  pieces of copy, and there is currently no way to tell which is which.

  **Eleven of the twelve can reach the review queue at all**, which is a fact about the
  pipeline rather than about the run that has not happened: `no_market_data` is routing's
  fourth destination beside listed, main and parked, and `pipeline/join.py` writes a queue
  entry only for `routing.MAIN` and `routing.PARKED`. A card with a blank or $0.00 market
  cell is priced by hand in `decisions.json` (D9) and never appears on that screen.
  Separately, `card_not_detected` is a constant nothing in `pipeline/`, `cli/` or `identify/`
  ever assigns — it is reachable in principle and has no producer in the repo today. Neither
  is a defect in the screen and neither costs more than a line in a lookup table; both are
  recorded because §10.2 item 2 asks for the codes that fired ZERO times, and a zero for
  these two would mean nothing about the owner's stock.

- **The queue's volume and shape are unknown, including whether it is ever long.** Section 0
  says a twenty-card run is expected to produce close to zero review items at T1's committed
  holdout accuracy. That is still true, and it is the load-bearing half of the argument for
  waiting: the screen `docs/DESIGN.md` calls the hardest in the product, and the one the
  owner is said to spend hours in, was designed against a length nobody has observed. "A
  queue where every row looks equally important has thrown away a sort it already has" is an
  argument about a long list. Whether this is ever a long list is a Gate B number.

- **The Fulfillment view's floors are asserted; its copy is not.** The constraints table in
  `docs/DESIGN.md` is numbers precisely so a browser can check them, and a browser can. What
  no test reaches is D5's actual requirement — "if a flow needs explaining twice, redesign
  the flow" — whose only instrument is a retired, non-technical person using it to fill a
  real order. No order has been pulled. The banned-word list catches the vocabulary it
  names and nothing else.

- **Nothing here has met a card.** The same sentence `docs/GATES.md` carries against step 4
  and step 7a now carries against 7b, and it is the one to repeat: verified against
  fixtures, synthetic images and hand-built props only.

### Built was not wired for several hours, and only one check could tell

Separate from everything above, and a different kind of gap: the three screens shipped
existing, typechecking and linting clean, with **nothing reaching them.** `app/src/App.tsx`'s
ROUTES table named three views, `app/src/server.ts` exported no client function for the three
routes 7b had added to the capture server, and the review queue's two calls arrived as a prop
nothing supplied. Both files were another group's during the session that built 7b and were
correctly left alone.

**`make design-check` was the only thing that said so, and it failed: 16 of 30 assertions**,
every one reporting the unregistered route rather than a design defect. That is
`app/tests/fulfillment.spec.ts` working exactly as written — it asserts the view is on
screen before measuring anything, because the alternative is nine confident measurements of
whatever Vite serves for a hash it does not recognise.

**`make harness`, `make lint`, `make typecheck` and `make docs-audit` were all green
throughout.** That combination is the finding, and it survives the fix: nothing on the path
that decides whether a commit proceeds can tell whether a screen can be opened, and
`make design-check` — the one check that can — is deliberately not on it, because it starts a
browser and a dev server. Compare `docs/DEBTS.md`'s repo-map entry, where a whole directory
went unaudited under a rule that looked like it covered it.

**Wired 2026-08-13.** Six routes in the ROUTES table, one client function per new route in
`server.ts`, the queue wire types moved into `types.ts`, and the shell drawing no nav over
the Fulfillment view — which is what that view's row in the constraints table requires, and
which replaced the `display: none` bridge `Fulfillment.css` was carrying. `make design-check`
now runs 30 of 30. What that does **not** change is anything in the section above: the
screens open, and the data they open onto has still never been produced by a run.

### What this section is not

It is not a precedent. The next thing scheduled behind a gate is still behind it, and the
reason this is written as a status block rather than folded into section 0's prose is that a
schedule broken once with a signature is recoverable, while a schedule quietly rewritten to
match what was done is not.

**What would settle every item above is Gate B, and section 10.2 says exactly which numbers
to take while it runs.** That subsection exists because of this one: having built 7b early,
the gate can now produce the measurements 7b was guessing at, and taking them is what turns
a rule broken into a rule broken for something.

---

## 0. Scope — step 7, built in two passes

This spec covers all of build-order step 7. It was written as a 7a spec and grew to cover
both passes when 7b was built the same day; the two are still named separately below because
they were built and reviewed separately, and because Gate B exercises only the first.

**7a — the Gate B path.** The app shell, the capture screen, undo, the pull preview, and one
new server route. This is the chain the gate walks: capture, server save, batch script, join,
CSV, import, and a pull modal showing the right location.

**7b — the rest.** The review queue, the Fulfillment view, the inventory SKU views and
mark-sold, plus three more server routes.

**Why the split existed, recorded because the reasoning outlives the schedule.** 7b was
scheduled after the gate so that it would be built against a real run rather than against
guesses about what one produces — the review queue especially, since it is the screen
`docs/DESIGN.md` specifies in most detail and its *inputs* are guesses until a run exists. At
T1's committed holdout accuracy a twenty-card run should produce close to zero review items,
so 7b is not needed to pass the gate. It was built early anyway and that call is settled. The
consequence did not go away with the schedule: §10.2 is where the gate replaces those guesses
with numbers.

### 0.1 — The rule this session runs under

`docs/specs/capture-server.md` section 0.3 documents how writing docs in this repo can
block your own commit. It has not changed and it applies here. The trap most relevant to
this spec: **a path whose first segment is an existing top-level directory, and which does
not exist, BLOCKS the commit.** `app/` is now a real top-level directory, so naming a
component file before it exists is a blocked commit. This spec therefore names components
by their component name and points at directories that exist, not at files that do not.

## 1. Order of operations

**All eight are done. Item 7 was missed in the build commit it was scheduled for and done in
the review that followed** — see below.

| order | item | size | waits for | state |
|---|---|---|---|---|
| 0 | ~~doc-amendments~~ | — | — | **done 2026-08-13**, before this spec was committed |
| 1 | ~~undo-route~~ | ~60 lines in one built module | — | **done 2026-08-13**, `server/capture_server.py` |
| 2 | ~~server-client~~ | ~120 lines, new | — | **done 2026-08-13**, `app/src/server.ts` |
| 3 | ~~capture-screen~~ | ~350 lines, the bulk of it | 1, 2 | **done 2026-08-13**, `app/src/CaptureScreen.tsx` |
| 4 | ~~trigger-seam~~ | ~60 lines, folded into 3 | 3 | **done 2026-08-13**, `app/src/trigger.ts` — its own module, not folded |
| 5 | ~~pull-preview~~ | ~120 lines | 2 | **done 2026-08-13**, `app/src/PullPreview.tsx` |
| 6 | ~~eslint~~ | config + 2 rules | 3 | **done 2026-08-13**, `app/eslint.config.js`; `make lint` stopped being a stub |
| 7 | ~~map-flip~~ | ~20 lines | all, same commit | **missed in that commit**; done in the review that followed, and it took more than 20 lines |

Item 0 first for the reason `docs/specs/capture-server.md` puts its false-claim sweep
first: a doc that contradicts what you are about to build will be read as authority by the
session after this one.

**Item 7 is the one to read twice.** "All, same commit" was the whole of its schedule and it
was not met: the build shipped and `docs/map.py` described none of the thirteen files it
added, so the index D17 calls believed-therefore-dangerous was wrong about the directory that
had just changed most. Nothing caught it, and nothing could — the repo-map orphan rule
filtered on `.py` and did not descend, which `docs/DEBTS.md` had predicted in writing on
2026-08-12. Both halves are fixed now: the map carries every file, and the orphan rule
reaches this directory through a per-entry `source_suffixes` declaration it makes in the map
itself. The lesson for the next spec that ends in a map-flip is that a step scheduled as
"same commit" as everything else is a step with no schedule of its own — and that the map
flip is the one item where nothing but the schedule was ever going to catch it.

## 2. doc-amendments — APPLIED 2026-08-13

Five edits, all of them corrections this interview produced. **They were applied before this
spec was committed, rather than left as the execution session's first task**, so that a
session opening these documents cold finds them agreeing with each other and with this file.
The subsections below are kept as the record of what changed and why — read them as history,
not as work outstanding.

### 2.1 — Step 7 no longer includes a CSV import

`docs/GATES.md` step 7 ends with "CSV import with error reporting". That was a v1 feature,
and v2 moved the whole of it into the four commands: `emit` writes `pushed`, `reconcile`
moves `pushed` to `staged` off the Export From Staged, and `join` moves `staged` to `live`
off the Filtered Export. Every state transition is already owned, and the app reads state
rather than setting it.

Strike the phrase and record why in the same line, so the next session does not reinstate
it from the old list. **This is the one amendment that removes scope rather than adding
it**, and it is worth being explicit that the removal is not a deferral — there is nothing
left for the feature to do.

Note what survives the removal: v1 bug 5 in `docs/DECISIONS.md` is about an import that
silently skipped cards and reported nothing in either direction. Its guard is T3, which is
green and stays green. Removing the app-side import does not weaken it.

### 2.2 — The feeder exists

`docs/GATES.md` Gate C reads as though feeder integration begins with building a feeder.
The machine runs today: cards are fed onto a tray, landing in the same spot each time.
That does not move auto-capture earlier — see section 6 — but it changes what Gate C is,
from "build and integrate" to "tune the trigger against a rhythm that already exists".

### 2.3 — The rig's camera path is recorded for the first time

Nothing in the repo names the capture hardware. Three references to a camera exist —
`CLAUDE.md`'s rule against `facingMode`, v1 bug 3 in `docs/DECISIONS.md`, and the step-5
scope exclusion — and none says what the camera is.

It is a Sony RX100 VII or A7C, over HDMI into an Elgato Cam Link 4K. **The consequence is
the whole reason this belongs in a decision rather than in this spec's prose**: the Cam
Link presents the camera to the browser as a plain UVC webcam. It is not distinguishable
by kind from a laptop's built-in camera — only by its device label and id. That is exactly
why `facingMode: "environment"` was v1 bug 3, and why the device picker is a requirement
rather than a nicety.

Record it in D13, which already owns the stack.

### 2.4 — Undo is a stated exception to the no-dialog rule

`docs/DESIGN.md` says no confirm dialog on a reversible action, and that undo is what
covers a mistake. D10 now says undo hard-deletes the record, the sidecar and the photo.
Those two sentences describe undo as both the remedy and the irreversible act.

The owner chose one tap and no dialog. Record the reasoning rather than the ruling alone,
because it is the reasoning that stops the next session from "fixing" it: the deleted
photo is of a card that is still physically in your hand, so the remedy for a wrong undo
is to photograph it again. The loss is bounded in a way that a wrong pull or a wrong sale
is not, and `docs/DESIGN.md`'s "genuinely destructive actions may still gate" is about
those.

Rejected, and worth naming: confirming only on a second consecutive undo. It protects
against a held key walking backwards through good cards, at the cost of one more state to
explain. If a held key ever does that in practice, this is the fix to reach for first.

### 2.5 — `docs/DESIGN.md`'s "none of this is built" header

That header now covers a section describing a queue screen only. When the capture screen
lands it stops being true of the file as a whole, and the header should say which sections
it still governs.

## 3. undo-route

The only new server route in this spec. Everything else the app needs already exists:
`POST /capture`, `GET /status`, `GET /photo/<box>/<position>`, `GET /inventory`, and
`PUT /inventory/<box>/<position>`.

**`DELETE /inventory/<box>/<index>`.** Removes the card record, its sidecar and its photo,
in that order of importance and inside one `Store.write()` — the same shape `do_capture`
uses, so a failure part-way commits nothing.

The rules it enforces, all from D10:

- **It deletes; it does not tombstone.** There is no third state between captured and
  absent, and nothing in the response should suggest one.
- **Only the newest card in that box.** `next_index` is a high-water mark, so deleting from
  the middle leaves a gap that can never be reused and is indistinguishable, later, from
  the permanent gap a sale leaves. Refuse anything else, and say which position *is*
  undoable in the refusal — a refusal that does not say what would have worked costs a
  round trip.
- **Refused once the card's row has been written into an import file.** In store terms:
  allowed at `captured` and `identified`, refused at `pushed`, `staged`, `live` and `sold`.
  Up to `pushed` nothing outside this Mac knows the card exists, so removing it costs only
  the identification fee. After it, a file on disk would disagree with the inventory.
- **Repeated undo walks backwards, one card per call.** This falls out of the rule above
  rather than needing anything: each call deletes what is now the newest.

Two details that are easy to get wrong:

**Delete the sidecar, not just the photo.** `identify.sidecar.scan` finds photos by suffix
and reads sidecars beside them, so an orphaned sidecar is harmless — but an orphaned
*photo* is a paid Batch request for a card that no longer exists. That is the money rule
in T7, from the other direction.

**The refusal codes are new strings and the app shows them.** Follow the existing uniform
error body: what happened, and what to do next. Reserve 500 for bugs.

T7 gains its cases the day this lands. `harness/tests/t7_store_and_seams.py` already
asserts the allocator behaviour undo depends on — that deleting the newest record releases
its index — and says in its own docstring that the route's own cases arrive with the route.

## 4. server-client

One module under `app/src/` owning every call to the capture server. Not spread across
components: the failure behaviour in section 5 has to be one decision applied once.

Base URL is the server on port 8000, configurable through a Vite env variable so the
Fulfiller's device can point at the Mac by address later. CORS is already handled server
side — any origin, no credentials, preflight answered — and the decision that there is no
auth and no TLS on a LAN tool is recorded in `docs/specs/capture-server.md`. Do not add a
login screen.

Every response the app surfaces uses the server's own message. `docs/DESIGN.md`'s copy
rules reach these strings: they say what happened and what to do next, and the app must not
paraphrase them into something friendlier and less actionable.

## 5. capture-screen

The screen the owner spends hours in. Everything here was chosen against a named
alternative.

### 5.1 — Layout

**Live camera on the left, the photo just taken on the right**, the second large enough to
see a blur or a finger on the card. Rejected: live-only, which is faster to work through a
stack but defers discovery of a bad photo to the review queue or to a failed
identification; and last-photo-only, which never shows the live view while the next card is
being positioned.

Catching a bad photo *now* is the entire reason undo exists. Three weeks later it is a card
that cannot be identified sitting at a position nobody can correct without handling the box.

The position label of the card just taken sits with its photo, in the utility face, built
from the same renderer `pipeline/join.py` uses. The server already returns it, so the app
never composes a second one.

### 5.2 — Box selection

**Pick from a list of boxes already in use.** The list comes from `GET /status`, which
already reports the next index per known box; no new route.

**Starting a new box is a typed number with no confirmation step.** The owner was offered a
confirmation and declined it, and the cost is worth stating plainly rather than
rediscovering: a typo like 33 for 3 is a valid box number, a real photo and a real listing,
and nothing downstream can tell. The server flags the first capture into a box as
`new_box` for precisely this purpose. **That flag is deliberately not surfaced as a
dialog** — but it should still be visible on screen, because showing "this is a new box" as
information is not a confirmation step and costs nothing.

Box, set hint and finish are client state resent on every capture. The server holds no
notion of a current box, which is what lets two devices work without a session.

### 5.3 — Set hint and finish

Both are always visible and changeable in one action. The owner sorts by set and by finish,
staying within a set for a while before a finish changes, so neither is a rarity.

The **finish** toggle is `normal | holo | reverse_holo`, matching the enum the server
validates against, and it is a claim rather than a hint — D3 rung 1 treats it as trusted,
which is why a mis-toggled stack reviews rather than being silently corrected.

The **set hint** is free text and was nearly cut from this spec. It was restored during the
interview once its real cost was named: without it, a collector number that matches rows in
two different sets has nothing to break the tie and reviews as `set_ambiguous` — a required
case in T3. Free text rather than a picker because there is no catalog in the repo until
build-order step 9; a picker has no list to offer yet.

### 5.4 — Undo

One tap, no dialog, repeating. Each press removes the newest card in the current box.

The control is always visible rather than appearing after a capture — a control that
appears and disappears is one you have to look for at the moment you are least inclined to.

It must show *what it will delete* before you press it: the position, and ideally the
thumbnail, of the card that would go. That is not a confirmation step; it is the difference
between an undo you can aim and one you fire hopefully.

### 5.5 — Failure behaviour

**A failed capture stops the run and says so, loudly.** Rejected: quiet retry, and
queue-and-continue.

The reasoning is the feeder. With a machine feeding cards, a quietly-failing capture means a
stack of physical cards passes the lens with no record and no photo, and nothing afterwards
can say which ones. The whole value of a position is that every card that went past has one.

Queue-and-continue was rejected for a second, structural reason: holding photos in the
browser that are not yet on the Mac creates a second place inventory lives, and D13 has
exactly one.

The retry guard is still worth using. Every capture sends a `capture_id`; when a response is
lost between commit and client, resending the same id returns the original card with
`created` false and burns no index. That is a *retry of one request*, not a queue.

## 6. trigger-seam

**Gate B runs on a key press and an on-screen button. The trigger is built as one
replaceable piece.**

The owner confirmed the original reasoning: auto-capture was scoped as an incremental
addition after step 7 because of its own complexity, with the agreement being something
simple first. That agreement is what `docs/GATES.md` records at Gate B — "Manual capture
button, no auto-detect" — and at Gate C, where v1's motion state machine (motion,
stabilize, capture, cooldown) is named as the favored method with ffmpeg frame extraction
as the fallback.

So the seam, not the feature: whatever fires a capture is one module with one job, and the
capture screen does not know which implementation is behind it. At Gate C the motion state
machine drops into the same slot. Auto-capture is then an addition rather than a rewrite,
and Gate B stays a clean test of the pipeline instead of a test of the pipeline and an
untuned trigger at once — where a bad result cannot say which one failed.

The key is shown on screen. `docs/DESIGN.md` requires it owner-side: an hour at this screen
is a keyboard and not a mouse, and the visible hint is what the no-dialog decision looks
like in markup.

### 6.1 — The camera

The device picker enumerates video inputs and selects by `deviceId`. **Never `facingMode`** —
v1 bug 3, and the reason is now recorded in D13: the Cam Link presents the camera as a plain
UVC webcam, indistinguishable by kind from a laptop's built-in one.

The chosen device is remembered and re-selected silently on later sessions, with a visible
control to change it. This one is my call rather than the owner's — the question was
overtaken by the hardware answer — and it follows from the hardware being fixed: the rig
camera does not move, so choosing it daily is friction with no upside. **If the remembered
device is absent, the app says so and asks rather than falling back to another camera.**
Silently grabbing a different input is how a box gets photographed through the wrong lens.

### 6.2 — Why the camera is not driven directly, which was asked and is worth recording

Tethered capture — talking to the Sony over USB and firing its shutter from code — was
raised as possibly the smarter option. It is not, and the reason is in this repo rather
than in an opinion about cameras.

`identify/images.py` downscales every photo to 1568px on the longest edge, because anything
larger is billed and then discarded. That is true, and on its own it is **not** a sufficient
argument — the first draft of this section made it and was wrong. Recorded here with its
correction, because the corrected version is the one that changes how the rig is set up:

**Resolution does matter, through the crop rather than through the whole card.**
`geometry/crop.py` cuts the collector number and upscales it to at least 600px, on the
stated grounds that a 40px number is a coin flip and enlarging it is the point. It can only
enlarge pixels that were really captured. And T1's recorded misses are exactly numerator
misreads — `051/197` for `031/197`, `271/167` for `211/167` — name right, digits wrong.

So the number of real pixels landing on the number corner is a live accuracy variable, and
the 1568px cap says nothing about it. Roughly, on a 63×88mm card:

| capture | card long edge | number corner |
|---|---|---|
| framed to the 1568px target | 1568px | ~100px |
| 4K, card filling the frame | ~3400px | ~230px |
| full-resolution still | ~5500px | ~370px |

**Tethering is still the wrong trade, but for a narrower reason than "resolution is
discarded":** it buys about 1.6× the linear detail of a tightly-framed 4K frame, and most of
that gap closes for free by framing the card to fill the field. Against that, tethering
costs:

- **Latency the feeder will not forgive.** A PTP shutter-and-download over USB is commonly
  one to three seconds per frame. Grabbing a frame from a video stream is one frame. Across
  a full box that is the difference between a run and an afternoon.
- **A native dependency and a new failure surface.** Sony's own Camera Remote SDK is C++
  and aimed at the Alpha bodies — A7C support is likely, RX100 VII is worth verifying
  before believing. `gphoto2` is the open alternative and needs the camera in PC Remote
  mode. Either way it is a platform-specific binary the capture server would have to shell
  out to, and it inverts the flow: the app would ask the Mac to take a photo instead of
  sending bytes it already has.
- **Refocus per shot.** A video stream holds focus; a still capture re-acquires it, which
  on a fixed tray is latency spent re-solving a problem that does not change.

Sony's Imaging Edge Desktop is ruled out before any of that, by `CLAUDE.md`: no manual
third-party UI step inside the autonomous pipeline, and external tools without an API
contract can be benchmarks, never components.

**What the Cam Link path does require, and what gets it wrong if unstated:**

- **Frame the card to fill the field.** The single largest lever on identification accuracy
  available at capture time, per the table above, and it costs nothing but rig setup.
- **Glare on the number corner is unrecoverable at any resolution.** Gate B's raking-light
  shot is currently aimed at foil detection; check the number corner in the same pass.
- **Request the resolution explicitly.** A browser video track defaults far below what the
  Cam Link can deliver — a 640x480 default would put the frame *under* the 1568px target and
  make every photo worse than the rig can produce. Ask for the native mode.
- **Encode at high quality.** The frame is re-encoded by the pipeline later, so capturing at
  a low JPEG quality compounds two lossy passes on the one image identification depends on.
- **Clean HDMI output must be on at the camera.** Otherwise the capture card faithfully
  records the camera's own overlays across the card.
- **Disable auto power off.** A body that sleeps mid-box drops the HDMI signal, and the
  failure behaviour in section 5.5 then stops the run — correctly, but avoidably.

The last two are rig settings rather than code, recorded here because they are invisible
until a box has been shot wrong.

## 7. pull-preview

**Look only. No actions.** Photo, and the position rendered from `join.Position.label`.

This is the last link in the Gate B chain: a card photographed at the start shows up at the
end with the right photo at the right box, section and card. `GET /photo/<box>/<position>`
serves it — D6's route, and the reason it exists.

Mark-sold was offered and declined for this pass. It needs a new route and pulls 7b work
into the gate.

## 8. eslint

`make lint` was a deliberate `exit 1` when this was written, and stopped being one here —
wired 2026-08-13 at `app/eslint.config.js`, because the device picker is the first code the
v1-bug rules can actually catch:

- no `facingMode` in any camera constraint (v1 bug 3)
- no `split(",")` CSV parsing (v1 bug 2)

Both are listed in `docs/DECISIONS.md`'s v1 bug table with "lint rule" named as the guard,
and neither has had one since the table was written.

## 9. What step 7 still may not build

This list once opened by forbidding the review queue, the Fulfillment view, the inventory SKU
views and mark-sold. All four are built and that ban is gone — a prohibition left standing
over shipped code reads to the next session as a defect report. Recorded rather than deleted
silently, because the four names would otherwise be reinstated from an older copy of this
list, which is exactly how `docs/GATES.md` lost and regained a CSV-import line.

**Everything else here still binds, and none of it was touched:**

No auto-capture, no motion state machine, no video frame extraction — that is Gate C, and
section 6 is the seam that keeps it cheap. No identification, pricing, joining or CSV work of
any kind in the app: the four commands own all of it, and the app reads state rather than
setting it. No second store in the browser. No auth, no login, no TLS. No renumbering,
compaction or gap-filling, ever.

`scripts/docs-audit.py` was forbidden here for the reason step 5 forbade it, and that ban is
also lifted: the repo-map orphan rule could not see `app/`, which is what let the map go
stale about the directory that had just changed most. The edits are recorded in
`docs/DEBTS.md` and in D16's own terms — the file still never writes, still parses rather
than imports, and still has no `--fix` flag.

And no edits to `scripts/docs-audit.py`, for the same reason step 5 forbade them.

## 10. Gate B run sheet

Recorded here because the run is what this spec is for, and because the owner chose a shape
for it that is worth writing down before the day.

**Hand-placed first, then a feeder run.** Prove the chain by hand on a few cards — where
nothing mechanical can be blamed for a bad photo — then run the remainder through the
machine, which is how the cards will really arrive and which puts the rig's actual lighting
and framing into the photos.

The rest of Gate B is unchanged in `docs/GATES.md`: twenty cards end to end, plus roughly
ten photos of known-variant cards for finish detection, including one raking-light shot. If
the diffused rig suppresses the foil signal, that is a rig finding and the fix is a second
capture angle, not a prompt change.

### 10.0 — Rig settings, checked before the first card

Measured from the shakedown of 2026-08-20, not reasoned about: eight frames were captured
through the real camera and Cam Link into the real server, and every one of them carries all
four faults below. They cost nothing to fix and are invisible afterwards, which is exactly
why they belong on a checklist rather than in someone's memory.

The shakedown is also the evidence that the front of the chain works. Eight contiguous
positions, every sidecar readable, and `./pkmnscan identify --dry-run` over them reporting
`photographs 8 / payload 1.5 MB in 1 batch chunk / estimated cost $0.01` — so the scan, the
1568px downscale and the batch assembly all ran against real 4K JPEGs. What has never run is
everything after the API call.

- **Clean HDMI output ON at the camera.** The shakedown frames carry the camera's own
  overlays burned in: focus brackets, the focus-distance scale, and an info bar reading
  `1/30 F2.8 ±0.0 ISO AUTO`. The Cam Link records what the camera draws, and D13 is why —
  it is a plain UVC device with no idea it is looking at a menu.

- **Kill the pillarbox.** Those frames are 3840x2160 with live pixels only from x=478 to
  x=3359. **Twenty-five per cent of the width is black bar**, so a nominal 4K capture is
  really 2882 wide before the card is even framed inside it. Check the camera's HDMI output
  resolution and aspect against what the Cam Link is receiving.

- **Manual exposure, and stop down.** `1/30` at `F2.8` on auto ISO is the wrong end of every
  trade for this job: slow enough to blur on any knock, thin enough in depth of field that a
  card sitting proud of the tray loses a corner, and an ISO that drifts shot to shot so no
  two photographs share a baseline. A static card under a fixed lamp wants a faster shutter,
  a stopped-down aperture and a fixed ISO.

- **Manual focus, locked at tray distance.** The tray does not move (D13, and Gate C's whole
  premise), so autofocus has nothing to contribute and one hunt costs a frame.

**And auto power off disabled**, which is the one that bites silently rather than visibly: a
sleeping body drops the HDMI signal while the Cam Link stays enumerated. The capture screen
now halts the run when the track dies, so this is a stoppage rather than a box of frozen
frames — but it is still a stoppage nobody needs.

**Frame the card to fill what is left.** D13 records why this matters more than the sensor:
`identify/images.py` downscales the whole card to 1568px, but `geometry/crop.py` upscales the
collector number to at least 600px and can only enlarge pixels that were really captured —
and T1's recorded misses are numerator misreads. Tight framing is the largest accuracy lever
available at capture time and it costs nothing.

### 10.1 — Open, and the owner's call: run more than twenty

**Not decided. Recorded here so the question is asked on the day rather than discovered
afterwards.** The twenty-card figure was written when the feeder was hypothetical and every
card meant a hand placement. The machine now runs, so the marginal cost of pushing two
hundred cards through after the gate criteria are met is a few minutes and a few dollars of
Haiku.

What the extra cards buy is the only thing this project currently has no way to obtain:

- **A real identification accuracy number.** T1 is measured against flat catalog renders
  with no foil, no glare and no rig lighting. It has never seen a photograph. Twenty cards
  is an anecdote; two hundred is a rate.
- **A real `set_ambiguous` count**, which is what decides whether the set hint earns its
  control — a question that flipped twice during this interview because neither side had a
  number.
- **Real review-queue volume and shape**, which is what 7b's hardest screen should be
  designed against.

**The gate criteria should not move.** Pass or fail stays at twenty cards end to end; this
is measurement taken alongside it, not a harder bar. Keeping those separate is the point —
a gate that grows whenever someone wants more data stops being a gate.

**One item above inverted on 2026-08-13.** "Real review-queue volume and shape, which is
what 7b's hardest screen should be designed against" was written while 7b was unbuilt. 7b is
built, so the same numbers are no longer an input to a design — they are a check on a design
already made. That is a worse position to be in and it is the position we are in; 10.2 is
what makes the check happen rather than leaving it to be noticed.

### 10.2 — What Gate B should measure, now that 7b exists

**This subsection is the payoff for building 7b early, and writing it down is what turns a
rule broken into a rule broken for something.** Every number below was a guess when the
screens were built. The gate run is the first opportunity to replace one with a measurement,
and an opportunity that is not written down before the day is one that gets spent on getting
the cards through.

**None of this moves the pass criteria.** 10.1's rule holds without exception: pass or fail
is twenty cards end to end, and everything here is measurement taken alongside it. A number
that comes back ugly is a finding to work, never a failed gate.

Take these, in this order — the first three are the ones 7b was built without:

1. **Queue depth, both queues, as a rate.** How many of the run's cards land in `review.json`
   and how many in `parked.json`, over how many cards. Section 0 predicted close to zero on
   twenty; the prediction is itself worth scoring, because everything the queue screen does
   about hierarchy and expensive-first ordering is an answer to a list long enough to need
   one. A run that reviews two cards in two hundred says the hierarchy is decoration; a run
   that reviews forty says it is the product.

2. **Which of the twelve reason codes fired, with counts — and explicitly, which fired
   zero times.** The zero list is the more useful half and the one that will be skipped if
   it is not asked for by name here. A human label written for a code that never fires is
   copy nobody will ever read, sitting in a screen that pays for it in review surface; a
   code firing far more than expected is a label that needs rewriting for the case it
   actually describes. Both are invisible unless the zeros are recorded alongside the hits.

3. **The price distribution across the run, and separately across the queue.** Minimum,
   maximum and median of `TCG Market Price` for every card the run touched, and the same
   three for queued cards only. D9 already has the join preserve the sub-threshold spread in
   bands rather than lumping it, so the sub-$0.40 half comes for free; what is missing is the
   top of the range, which is what decides whether the queue's largest price type is
   carrying a $3 card or a $300 one. This is the direct input to the row hierarchy that was
   guessed at, and it is the one measurement here that can be taken from the run's own
   output without watching anything.

4. **The `set_ambiguous` count**, which 10.1 already wants for a different reason — it
   decides whether the set-hint control earns its place — and which is also a reason code in
   item 2. Counted once, read twice.

5. **`no_market_data` specifically, separated from the rest.** D9 makes it a distinct
   disposition on the grounds that a missing price is an unknown price and not a low one, and
   the failure it guards against is handing away a chase card at the floor. Nobody knows how
   often a real export leaves that cell blank. If the answer is "often", it is the queue's
   most common reason code and was built as one of twelve.

6. **Whether the Fulfiller can complete a pull without being told how**, if he is available
   on the day. One order, no coaching, and the thing to record is where he stopped rather
   than whether he finished. This is the only item here that cannot be extracted from a file
   afterwards, so it is the only one that has to be planned into the day itself.

Items 1 through 5 are all derivable from the run's own output, which means they survive
being forgotten in the moment — the run directory and the queue files still hold them a week
later. Item 6 does not.

## 11. What this plan does not do

It does not close the `tested_by` gap in `docs/map.py`, add the token-drift check for
`app/src/tokens.css`, or extend the repo-map orphan rule to reach `app/`. All three are in
`docs/DEBTS.md` with their reasons. The second of them gets materially worse during this
work — step 7a is where the number of files reading those tokens stops being one — and it
is the cheapest of the three. Doing it early in this session is defensible; doing it as a
rider on the capture screen is not.

**What actually happened, 2026-08-13. Two of the three were done anyway, and this paragraph
is the record of which.** The third was extended to reach `app/` in the review that followed
this build, because the gap stopped being hypothetical: item 7 above was missed and nothing
noticed. **The second shipped in 7b** — the `design tokens` row of `scripts/docs-audit.py`
now parses the fenced block under `## Tokens` in `docs/DESIGN.md` against the `:root`
properties in `app/src/tokens.css` and blocks on any disagreement in either direction, so the
sentence this paragraph used to carry — that the two are "checked by nobody" — is exactly the
false claim section 2 puts first in the order of operations. It was true when written and
stopped being true in the same session. The first is unchanged. `docs/DEBTS.md` carries all
three, marks the second closed with what it does and does not cover, and records which of
their stated moments went by.

It does not settle what the Fulfiller's device points at, beyond making the server's base
URL configurable so that the question stays answerable later.
