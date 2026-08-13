# Capture app — execution spec (build-order step 7a)

Written 2026-08-13 by interview, the way `docs/specs/capture-server.md` was. Every choice
below was made by the owner against a stated alternative; where a recommendation was
overruled, the overruled option and its cost are named, because a decision nobody can see
the losing side of is one the next session will quietly reverse.

## 0. Scope — this is 7a, not step 7

Build-order step 7 lists ten things. **This spec covers only the ones Gate B exercises**,
because Gate B is the first time any of this touches a real card, and everything built
before it is unvalidated against reality.

In scope: the app shell, the capture screen, undo, the pull preview, and one new server
route. Out of scope and deliberately so: the review queue, the Fulfillment view, the
inventory SKU views, and mark-sold. Those are 7b, built after Gate B against real data
rather than against guesses about what a real run produces.

The review queue in particular is the hardest screen in the product and the one
`docs/DESIGN.md` specifies in most detail — and its *inputs* are guesses until a run
exists. At T1's committed holdout accuracy a twenty-card run is expected to produce close
to zero review items, so it is not needed to pass the gate.

### 0.1 — The rule this session runs under

`docs/specs/capture-server.md` section 0.3 documents how writing docs in this repo can
block your own commit. It has not changed and it applies here. The trap most relevant to
this spec: **a path whose first segment is an existing top-level directory, and which does
not exist, BLOCKS the commit.** `app/` is now a real top-level directory, so naming a
component file before it exists is a blocked commit. This spec therefore names components
by their component name and points at directories that exist, not at files that do not.

## 1. Order of operations

| order | item | size | waits for |
|---|---|---|---|
| 0 | ~~doc-amendments~~ | **done 2026-08-13, before this spec was committed** | — |
| 1 | undo-route | ~60 lines in one built module | — |
| 2 | server-client | ~120 lines, new | — |
| 3 | capture-screen | ~350 lines, the bulk of it | 1, 2 |
| 4 | trigger-seam | ~60 lines, folded into 3 | 3 |
| 5 | pull-preview | ~120 lines | 2 |
| 6 | eslint | config + 2 rules | 3 |
| 7 | map-flip | ~20 lines | all, same commit |

Item 0 first for the reason `docs/specs/capture-server.md` puts its false-claim sweep
first: a doc that contradicts what you are about to build will be read as authority by the
session after this one.

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

`make lint` is still a deliberate `exit 1`. Wire it here, because the device picker is the
first code the v1-bug rules can actually catch:

- no `facingMode` in any camera constraint (v1 bug 3)
- no `split(",")` CSV parsing (v1 bug 2)

Both are listed in `docs/DECISIONS.md`'s v1 bug table with "lint rule" named as the guard,
and neither has had one since the table was written.

## 9. What this session must not build

No review queue. No Fulfillment view — and therefore none of the rest of `docs/DESIGN.md`'s
constraints table beyond the three rows already asserted. No inventory browsing by SKU. No
mark-sold, no order pull, no undo of a sale. No auto-capture, no motion state machine, no
video frame extraction — Gate C, and section 6 is the seam that keeps that cheap. No
identification, pricing, joining or CSV work of any kind in the app: the four commands own
all of it. No second store in the browser. No auth, no login, no TLS. No renumbering,
compaction or gap-filling, ever.

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

## 11. What this plan does not do

It does not close the `tested_by` gap in `docs/map.py`, add the token-drift check for
`app/src/tokens.css`, or extend the repo-map orphan rule to reach `app/`. All three are in
`docs/DEBTS.md` with their reasons. The second of them gets materially worse during this
work — step 7a is where the number of files reading those tokens stops being one — and it
is the cheapest of the three. Doing it early in this session is defensible; doing it as a
rider on the capture screen is not.

It does not settle what the Fulfiller's device points at, beyond making the server's base
URL configurable so that the question stays answerable later.
