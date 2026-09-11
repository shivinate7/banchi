import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'
import { sealEveryTest } from './shell'
import type { Page } from '@playwright/test'

/* The motion trigger's DOM half, in a real browser against the real capture screen —
 * the half motion.spec.ts deliberately cannot reach. That file proves the machine's
 * arithmetic against an exact answer key; this one proves the wiring around it: the
 * mode toggle arms the machine, the sampler actually reads frames off the <video>,
 * a settle becomes a fire, and a fire with no box selected is COUNTED as dropped
 * rather than silently eaten — spec §5.5's requirement, and the one behaviour that
 * distinguishes a machine trigger from a key.
 *
 * The camera is a canvas feeding `captureStream()` into the screen's own <video>
 * element. No fake-device flags, no rig: the sampler cannot tell a canvas stream from
 * a Cam Link, which is the point — everything from "pixels arrive" onward is the real
 * code path. What this still is NOT is evidence about the rig: real lighting, real
 * foil, the real feeder rhythm are Gate C's to measure, and the thresholds this scene
 * crosses are crossed by construction.
 *
 * NO BOX IS EVER SELECTED in this file, deliberately. With a box the fire would POST
 * /capture; against a dev server that write would land in a real store. The dropped
 * counter is not a compromise — it is the assertion: the seam fired, the screen
 * declined for a stated reason, and the number is on screen.
 */

/* THE SCENE IS PIECEWISE CONSTANT AND CHANGES ONLY ON COMMAND. Three values, and the gap
 * between two cards is the level the scene is INJECTED at, which is the level the machine is
 * ARMED over — so a settled gap frame is the arm-time baseline judged against itself, `dBase`
 * at zero, under the presence floor, and the only verdict it can reach is
 * `suppressed:no-card`. That is what makes the gap a WAYPOINT this file can WAIT for, and
 * that is the whole fix. `GAP_LUMA` below carries the rest of that argument.
 *
 * THAT IS THE MACHINE AS IT IS. AS IT WAS, the gap earned the same verdict by being DARK —
 * under motion.ts's `cardLumaFloor`, a brightness constant D81 deleted on 2026-08-31 in
 * favour of the distance from the arm-time baseline (`presenceK`/`presenceMin`, `diag.dBase`).
 * The waypoint survived the change and so did every assertion below; what moved is which
 * property of the gap earns it, from "dark enough" to "no distance from the baseline".
 *
 * WHAT THE RACE WAS. `swapTo` alternated the whole frame 40/220 ten times, each dwell held
 * by `waitForTimeout(30)` over a CDP round trip. A timeout is a FLOOR, not a period, and
 * the round trip is unbounded — so under design-check's parallel workers one dwell spans
 * three DELIVERED frames instead of one. `stillFrames` was 2 CONSECUTIVE then, so three
 * identical delivered frames ARE a settle: `d` reads 0, the episode is judged MID-SWAP, the
 * frame passes the card-present gate, it is novel, and the machine FIRES. `fires 2` then
 * passed for the wrong reason, `lastFired` held the swap frame, the real settle was genuinely
 * novel and fired a THIRD time, and `same 1` became unreachable — which is why step 4 burned
 * its timeout. Reproduced two ways: deterministically by lengthening one dwell to 120ms, and
 * under 24 background spinners at 1 of 3 full-suite rounds, signature `fires 3 ... empty 1`.
 *
 * THE GATE IT PASSED THEN WAS `cardLumaFloor`, AND THE RACE NEVER DEPENDED ON IT. The machine
 * of that day called the mid-swap frame a card because 220 cleared a brightness constant of
 * 90; today's calls it a card because a full-jump frame sits 180 luma levels from whichever
 * end of the alternation the baseline was taken at, and 180 clears the presence floor from
 * either end. Both gates say "card". The race is a property of the DRIVER's timing rather
 * than of the presence rule, which is why replacing the rule retired neither it nor the
 * invariant below.
 *
 * WHY THIS SHAPE CANNOT HAVE IT. Delivered frames are a SUBSET of drawn frames — a canvas
 * `captureStream` pushes on draw and never re-emits one — and each stage is a flat fill, so
 * two consecutive delivered frames are either EQUAL (interior of a stage) or differ by the
 * FULL jump (a boundary). The complete delta table is 0.00 / 90.00 / 150.00 against `tHi`
 * 8.0, and it is the same table at every draw:delivery ratio, regular or not.
 *
 * THE TRAP, NAMED SO A SIMPLIFICATION DOES NOT WALK INTO IT. "Alternate the scene in-page on
 * every rAF draw instead of over CDP" removes the round trips and ALIASES: with the draw loop
 * at ~60Hz and delivery at 30fps, consecutive delivered frames are two draws apart, so a
 * two-value alternation delivers the SAME value every time. `d` reads 0.00 permanently and
 * the machine fires on a swap it never saw as motion — measured against the real machine as
 * `fire@220` at every EVEN ratio. There is no pattern here to alias because there is no
 * pattern.
 *
 * D84 RAISED THE PRICE OF THAT RACE WITHOUT REMOVING IT. A settle is now `stillFrames` of
 * the last `stillWindow` with the window full, so a stage would have to span FIVE delivered
 * frames rather than three to be judged mid-swap. Wider is not immune, and the invariant
 * below is still what this file relies on.
 *
 * THE INVARIANT, AND IT IS LOAD-BEARING: every `setScene` is followed by a wait on the
 * counter that scene must move. A stage cut short inside the 250ms refractory loses its
 * verdict outright — at two delivered frames per stage BOTH gap verdicts vanish and `same 1`
 * never appears. The machine DEFERS a verdict; it does not survive the scene moving on. Do
 * not "simplify" `feed` into set-the-scene-then-poll-the-outer-assertion: that reintroduces
 * this flake in a shape nobody would recognise. */
const CARD_A = 170
const CARD_B = 110

/* THE FEEDER'S DARK GAP, AND SINCE D81 ALSO THE SESSION'S BASELINE. The scene is injected
   at this level and the machine is armed over it, which is the tuning protocol's own
   instruction — arm on an empty stand — expressed as a driver. Everything downstream reads
   from that: a gap frame is zero distance from the baseline and can only ever reach `empty`,
   and a card is 90 or 150 luma levels away from it and can only ever reach a fire or a
   novelty suppression. The old driver injected CARD_A first, which under the distance gate
   would have made a card the definition of "nothing". */
const GAP_LUMA = 20

/* Only has to DISCRIMINATE: the nearest scene pair is 110/170 at 60 apart, and the historical
   wrong fire was at 220 or 40. Measured exact — flat grey survives Rec.601 losslessly, since
   `toLuma`'s weights sum to 256 — so this is headroom against a future colour-space round
   trip rather than a fudge for a number that drifts today. */
const LUMA_TOLERANCE = 15

/** Inject a synthetic scene into the screen's video element. Page-side control is one handle:
 *  setScene(base) recolours the whole frame, flat.
 *
 *  FLAT, AND NO JITTER SQUARE. The old one drew at canvas x 40-98, which is grid x 4.0-9.8,
 *  against motion.ts's `ROI_X0` of 13 — entirely OUTSIDE the watch region. Its comment
 *  claimed it "keeps consecutive frames from being byte-identical, as a real sensor would";
 *  it never contributed one unit of `d` or of novelty, and the captured failure's own
 *  `watching d 0.00` line is the proof. Deleted rather than moved inside: a still scene here
 *  must be EXACTLY still, because rig noise is a rig property and `motion.spec.ts` is where
 *  the machine is held against a noisy answer key. This file tests wiring, and in-ROI jitter
 *  would only eat margin against `tLo` 4.5 for nothing. */
async function injectScene(page: Page): Promise<void> {
  await page.evaluate((first) => {
    const video = document.querySelector<HTMLVideoElement>('.capture-media')
    if (video === null) throw new Error('no video element on the capture screen')
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    const context = canvas.getContext('2d')
    if (context === null) throw new Error('no 2d context')
    const scene = { base: first }
    const draw = () => {
      context.fillStyle = `rgb(${scene.base},${scene.base},${scene.base})`
      context.fillRect(0, 0, 640, 360)
      window.requestAnimationFrame(draw)
    }
    draw()
    ;(window as unknown as { __scene: typeof scene }).__scene = scene
    video.srcObject = canvas.captureStream(30)
    void video.play()
  }, GAP_LUMA)
}

async function setScene(page: Page, base: number): Promise<void> {
  await page.evaluate((value) => {
    ;(window as unknown as { __scene: { base: number } }).__scene.base = value
  }, base)
}

function hud(page: Page) {
  return page.locator('.capture-motion-hud')
}

/* THE INSTRUMENTS MOVED INTO A DISCLOSURE THAT STAYS SHUT (owner's ruling, 2026-09-03). The
 * HUD, Re-baseline and Save trace are inside `details.capture-tuning` in the stage foot, and
 * the ruling is about where a tuning instrument BELONGS rather than about whether it works —
 * so this file opens it once and asserts the same numbers it always did. What it does NOT do
 * is assert that a readout is visible with nothing pressed: that was a fact about the old
 * layout, and the behaviour underneath it — the screen says the machine is armed, and says how
 * many fires and drops it has reached — is asserted against the SUMMARY, which is the part
 * that is on screen shut. */
function tuning(page: Page) {
  return page.locator('details.capture-tuning')
}

function tuningSummary(page: Page) {
  return tuning(page).locator('summary')
}

async function openTuning(page: Page): Promise<void> {
  await tuningSummary(page).click()
  await expect(tuning(page)).toHaveAttribute('open', '')
}

type Hud = {
  phase: string
  d: number
  dbase: number
  floor: number
  tlo: number
  thi: number
  typ: number
  fires: number
  same: number
  empty: number
  stall: number
  /** Fires taken under the rescue bar rather than off a completed settle (`rescueK`). */
  rescue: number
  dropped: number
}

/** ONE read of the HUD, parsed. Read as SPANS rather than as a substring of the element's
 *  text, for two reasons the old assertions had wrong. The <p>'s textContent concatenates
 *  with no separator (`movingd 0.00luma 220fires 2…`), so `toContainText('same 1')` also
 *  matches `same 10`; and two `toContainText` calls a line apart are two RENDERS, which
 *  cannot say that a counter and the frame it was reached on agree. `dropped` is absent from
 *  the markup until the screen has swallowed a fire, so it reads 0 rather than throwing.
 *  Everything else must parse: a HUD that changed shape would otherwise yield NaN and spend
 *  a 5s timeout on a comparison that can never be true. */
async function hudSnapshot(page: Page): Promise<Hud> {
  const spans = await hud(page).locator('span').allTextContents()
  const read: Record<string, number> = {}
  for (const span of spans.slice(1)) {
    const match = /^([a-z]+)\s+(-?[\d.]+)$/.exec(span.trim())
    if (match !== null) read[match[1] as string] = Number(match[2])
  }
  const snapshot: Hud = {
    phase: (spans[0] ?? '').trim(),
    d: read.d ?? NaN,
    dbase: read.dbase ?? NaN,
    floor: read.floor ?? NaN,
    tlo: read.tlo ?? NaN,
    thi: read.thi ?? NaN,
    typ: read.typ ?? NaN,
    fires: read.fires ?? NaN,
    same: read.same ?? NaN,
    empty: read.empty ?? NaN,
    stall: read.stall ?? NaN,
    rescue: read.rescue ?? NaN,
    dropped: read.dropped ?? 0,
  }
  for (const [key, value] of Object.entries(snapshot)) {
    if (key !== 'phase' && !Number.isFinite(value as number)) {
      throw new Error(`HUD did not parse: ${key} from ${JSON.stringify(spans)}`)
    }
  }
  return snapshot
}

/** The snapshot plus the one derived fact the assertions want: is the scene the machine is
 *  reading the card this test just put in front of it? Asserting that in the SAME sample as
 *  `fires` is what stops a fire reached on some other frame from satisfying a count.
 *
 *  IT READS `dbase` NOW RATHER THAN `luma`, because that is the number the gate decides on
 *  (D81) and the HUD no longer carries the one it does not. For a flat synthetic scene the
 *  distance from the baseline IS the luma distance from the gap, so this still names the
 *  exact scene — via the statistic the machine actually used to judge it. */
async function settledAt(page: Page, base: number): Promise<Hud & { atBase: boolean }> {
  const snapshot = await hudSnapshot(page)
  const expected = Math.abs(base - GAP_LUMA)
  return { ...snapshot, atBase: Math.abs(snapshot.dbase - expected) <= LUMA_TOLERANCE }
}

/** Present a card: the feeder's dark gap, then the card. Each step waits on the machine's own
 *  counter rather than on a clock, so this can be neither too fast nor too slow — and a gap
 *  the machine never settled on fails HERE, naming the gap, instead of surfacing four lines
 *  later as a timeout on a counter that was never going to move. See the block above
 *  `injectScene` for why the wait is the fix and not decoration. */
async function feed(page: Page, base: number): Promise<void> {
  const before = await hudSnapshot(page)
  await setScene(page, GAP_LUMA)
  await expect
    .poll(async () => (await hudSnapshot(page)).empty, { timeout: 5_000 })
    .toBe(before.empty + 1)
  await setScene(page, base)
}

/* NOTHING HERE MAY REACH THE CAPTURE SERVER. This file registers no fixtures of its own, so it
   takes the shared small store — `app/tests/shell.ts` carries the argument for both halves. The
   call has to sit above every hook and every case, which `make docs-audit`'s `spec seal` row
   checks: the navigation below happens inside a hook, and a seal declared under it would be
   installed after the requests it exists to catch.  */
sealEveryTest({ store: true })

test('arming motion is visible, and the machine fires on a settled card', async ({ page }) => {
  await page.goto('/#/capture')

  // Before anything: manual mode, machine string says so, no HUD anywhere.
  await expect(page.locator('.capture-trigger')).toHaveText('manual:c')
  await expect(hud(page)).toHaveCount(0)

  // Arm motion. The trigger is a one-line field in the session group now (pass D,
  // 2026-08-23): the row opens the field, the `motion` cell in the track arms it, and
  // selecting closes the field again. The assertions are unchanged — what moved is only
  // the path to the control. All three indicators change: the pressed cell, the machine
  // string, and the HUD placeholder (no camera is open yet, and the readout says so
  // rather than rendering zeros that look like a working machine seeing nothing).
  await page.getByRole('button', { name: /Trigger/ }).click()
  await page.getByRole('button', { name: 'motion', exact: true }).click()
  await expect(page.locator('.capture-trigger')).toHaveText('motion')
  /* ARMED, AND THE SCREEN SAYS SO WITH NOTHING OPENED. The disclosure's summary is the
     readout's public face now, and it carries the machine's state: no camera is open, so it
     reads `armed · no frames yet` rather than zeros that would look like a working machine
     seeing nothing. That is the claim the old `toBeVisible` on the placeholder was making. */
  await expect(tuningSummary(page)).toContainText('armed · no frames yet')
  /* Open it once; everything below reads instruments. */
  await openTuning(page)
  await expect(page.getByText('Motion is armed but no frame has reached it yet')).toBeVisible()
  // The C-key chip leaves the capture button: the key is genuinely disarmed in this mode.
  await expect(page.locator('.capture-controls kbd', { hasText: 'C' })).toHaveCount(0)

  // Frames arrive: the HUD replaces the placeholder and shows a live signal.
  await injectScene(page)
  await expect(hud(page)).toBeVisible({ timeout: 5_000 })

  /* THE EMPTY STAND AT ARM TIME IS THE BASELINE (D81), and the machine says so on the way
     past: one `empty` verdict, no fire, and the seeded thresholds are Gate C's hand-tuned
     pair to the last digit — which is the claim that the adaptive form did not move the
     numbers the 85/85 run was confirmed on, asserted rather than promised. */
  await expect
    .poll(() => hudSnapshot(page), { timeout: 5_000 })
    .toMatchObject({ phase: 'watching', fires: 0, empty: 1, same: 0, stall: 0 })
  const seeded = await hudSnapshot(page)
  expect(seeded.tlo).toBeCloseTo(4.5, 2)
  expect(seeded.thi).toBeCloseTo(8.0, 2)

  /* A bright card is placed at the lens: exactly one fire — and with no box selected the
     screen declines it for a stated reason and COUNTS it. One fire, one drop, nothing written
     anywhere.

     ONE SNAPSHOT, NOT A PAIR OF SUBSTRING MATCHES. `toContainText('fires 1')` then
     `toContainText('dropped 1')` is two renders, so it cannot say the counter and the frame it
     was reached on agree — which is exactly how `fires 2` used to pass on a mid-swap frame.
     `atBase` pins the verdict to the scene this test put up. */
  await setScene(page, CARD_A)
  await expect
    .poll(() => settledAt(page, CARD_A), { timeout: 5_000 })
    .toMatchObject({ phase: 'watching', atBase: true, fires: 1, same: 0, dropped: 1, stall: 0 })

  // The feeder swaps in a different card: the gap between the two, then the card, then a
  // second fire.
  await feed(page, CARD_B)
  await expect
    .poll(() => settledAt(page, CARD_B), { timeout: 5_000 })
    .toMatchObject({ phase: 'watching', atBase: true, fires: 2, same: 0, dropped: 2, stall: 0 })

  /* The tray gets bumped and the SAME card settles again: the novelty gate suppresses instead
     of double-firing, and says so on screen. `fires` is pinned in the same snapshot, so a third
     fire cannot hide behind a `same` that arrived anyway.

     `stall: 0` is safe to assert here and would NOT be under a sustained-churn driver:
     `movingSince` is set on the single transition frame and cleared by the very next one, so
     `stalled` is unreachable at any frame period — checked at 33, 200, 700 and 2000ms. */
  await feed(page, CARD_B)
  await expect
    .poll(() => settledAt(page, CARD_B), { timeout: 5_000 })
    .toMatchObject({ phase: 'watching', atBase: true, fires: 2, same: 1, dropped: 2, stall: 0 })

  /* AND THE DROP IS ON SCREEN WITH THE DISCLOSURE SHUT, which is this file's whole reason for
     counting drops rather than writing a card: the seam fired, the screen declined for a
     stated reason, and the number is legible. With the readout behind a disclosure that claim
     needed a reader of its own — the summary is where it now has to hold. */
  await expect(tuningSummary(page)).toContainText('2 fires')
  await expect(tuningSummary(page)).toContainText('2 dropped')

  // The trace: one press hands over the whole session as a self-describing file. This
  // is D19's Tier-1 instrument and the rig's tuning data, so the assertion is not "a
  // download happened" but that the file really carries the signal — frames with time
  // moving forward, the fires and the suppression this test just caused, and the pixels
  // each verdict was reached on.
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: /Save trace/ }).click()
  const download = await downloadPromise
  const savedTo = await download.path()
  const trace = JSON.parse(readFileSync(savedTo, 'utf8')) as {
    kind: string
    version: number
    params: { moveK: number; presenceMin: number }
    grid: { w: number; h: number; roi: number[] }
    truncated: boolean
    frames: Array<[number, number, number, number]>
    events: Array<{ t: number; event: string; frame: string }>
    keyframes: Array<{ t: number; frame: string }>
  }
  expect(trace.kind).toBe('pkmnscan-motion-trace')
  /* THE VERSION IS LOAD-BEARING, not decoration: a v1 row is [t, d, luma] and a v2 row is
     [t, d, dBase, luma], so a scorer that read the third column as brightness would read a
     v2 trace as a rig with no light in it. `scripts/score-trace.py` branches on this. */
  expect(trace.version).toBe(2)
  expect(trace.truncated).toBe(false)
  expect(trace.params.moveK).toBeGreaterThan(0)
  /* No frame-RATE assertion on purpose: headless frame delivery swings from ~10 to 60
   * fps with CPU load, and a bound tuned to one machine's idle speed flakes on the next.
   * What must hold at any rate: the trace saw at least every frame a verdict was reached
   * on, plus the settle run before the first one. */
  expect(trace.frames.length).toBeGreaterThanOrEqual(trace.events.length + 3)
  // time strictly non-decreasing, starting at 0
  expect(trace.frames[0]?.[0]).toBe(0)
  for (let i = 1; i < trace.frames.length; i += 1) {
    expect(trace.frames[i]![0]).toBeGreaterThanOrEqual(trace.frames[i - 1]![0])
  }
  /* WHICH FRAME EACH VERDICT WAS REACHED ON — the assertion the HUD cannot make. The HUD is a
     live snapshot: by the time a poll reads `fires 2` the frame that caused it is gone. The
     trace can, because every event carries the exact ROI pixels its verdict was reached on, so
     their mean IS the luma the gates decided against.

     THIS DOES NOT CLOSE THE WRONG-REASON PASS ON ITS OWN, and the division of labour is worth
     stating: the driver closes it structurally (a gap frame IS the baseline and can only ever
     reach `empty`), the HUD's `atBase` fails fast, and this localises a future DRIVER
     regression that the counters alone would not see. */
  const lumaOf = (frame: string): number => {
    const bytes = Buffer.from(frame, 'base64')
    let sum = 0
    for (const value of bytes) sum += value
    return sum / bytes.length
  }
  const verdicts = trace.events.map((e) => ({ event: e.event, luma: lumaOf(e.frame) }))

  /* EVERY `empty` VERDICT WAS REACHED ON THE GAP, asserted against the gap's own luma rather
     than against a threshold. That is a stronger claim than the old one — which only said the
     frame was under `cardLumaFloor` — and it survives the constant it used to name being
     deleted. */
  const gaps = verdicts.filter((v) => v.event === 'suppressed:no-card')
  for (const gap of gaps) expect(Math.abs(gap.luma - GAP_LUMA)).toBeLessThanOrEqual(LUMA_TOLERANCE)

  /* BOUNDED, not merely filtered: the arm-time settle on the empty stand gives one, two feeds
     give two more, and leading black frames before the canvas reaches the stream can give one
     further. Unbounded would be the one place a real extra verdict could hide, in a repo whose
     hard rule is never to drop a card silently. */
  expect(gaps.length).toBeGreaterThanOrEqual(3)
  expect(gaps.length).toBeLessThanOrEqual(4)

  /* `toEqual` on a fixed array SUBSUMES the two assertions this replaces: it says the fire
     count, the order, AND which frame each verdict was reached on, where
     `kinds.filter(fire).toHaveLength(2)` said the count alone. */
  const cards = verdicts.filter((v) => v.event !== 'suppressed:no-card')
  expect(cards.map((v) => v.event)).toEqual(['fire', 'fire', 'suppressed:unchanged'])
  expect(Math.abs(cards[0]!.luma - CARD_A)).toBeLessThanOrEqual(LUMA_TOLERANCE)
  expect(Math.abs(cards[1]!.luma - CARD_B)).toBeLessThanOrEqual(LUMA_TOLERANCE)
  expect(Math.abs(cards[2]!.luma - CARD_B)).toBeLessThanOrEqual(LUMA_TOLERANCE)
  // every event carries the watch-region pixels its verdict was reached on
  const roiCells = (trace.grid.roi[2]! - trace.grid.roi[0]!) * (trace.grid.roi[3]! - trace.grid.roi[1]!)
  for (const event of trace.events) {
    expect(Buffer.from(event.frame, 'base64')).toHaveLength(roiCells)
  }
  expect(trace.keyframes.length).toBeGreaterThan(0)

  // Disarm: reopen the trigger field and take the `key` cell — the old chip said
  // `press C` beside its label and the track cell says only `key`, so the selector
  // follows the control. The key trigger is back, the HUD is gone, the cell released.
  await page.getByRole('button', { name: /Trigger/ }).click()
  await page.getByRole('button', { name: 'key', exact: true }).click()
  await expect(page.locator('.capture-trigger')).toHaveText('manual:c')
  await expect(hud(page)).toHaveCount(0)
})

