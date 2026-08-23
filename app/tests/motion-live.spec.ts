import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'
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

/** Inject a synthetic scene into the screen's video element. Returns page-side controls
 *  via window handles: setScene(base) recolours the whole frame; the per-frame jitter
 *  square keeps consecutive frames from being byte-identical, as a real sensor would. */
async function injectScene(page: Page): Promise<void> {
  await page.evaluate(() => {
    const video = document.querySelector<HTMLVideoElement>('.capture-media')
    if (video === null) throw new Error('no video element on the capture screen')
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    const context = canvas.getContext('2d')
    if (context === null) throw new Error('no 2d context')
    const scene = { base: 170, tick: 0 }
    const draw = () => {
      context.fillStyle = `rgb(${scene.base},${scene.base},${scene.base})`
      context.fillRect(0, 0, 640, 360)
      scene.tick = (scene.tick + 1) % 5
      context.fillStyle = `rgb(${scene.base + 3},${scene.base + 3},${scene.base + 3})`
      context.fillRect(40 + scene.tick * 12, 40, 10, 10)
      window.requestAnimationFrame(draw)
    }
    draw()
    ;(window as unknown as { __scene: typeof scene }).__scene = scene
    video.srcObject = canvas.captureStream(30)
    void video.play()
  })
}

async function setScene(page: Page, base: number): Promise<void> {
  await page.evaluate((value) => {
    ;(window as unknown as { __scene: { base: number } }).__scene.base = value
  }, base)
}

/** A swap the machine must read as motion: several frames of violent change. */
async function swapTo(page: Page, base: number): Promise<void> {
  /* Alternate faster than the settle window can complete: at 30 fps captureStream,
   * stillFrames 2 means ~3 consistent frames read as a settle, so each violent scene must
   * hold for well under that. 30 ms keeps every dwell near one frame period even with
   * timer overshoot; 10 alternations make the swap unmissable. */
  for (let i = 0; i < 10; i += 1) {
    await setScene(page, i % 2 === 0 ? 40 : 220)
    await page.waitForTimeout(30)
  }
  await setScene(page, base)
}

function hud(page: Page) {
  return page.locator('.capture-motion-hud')
}

test('arming motion is visible, and the machine fires on a settled card', async ({ page }) => {
  await page.goto('/#/')

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
  await expect(page.getByText('Motion is armed but no frame has reached it yet')).toBeVisible()
  // The C-key chip leaves the capture button: the key is genuinely disarmed in this mode.
  await expect(page.locator('.capture-controls kbd', { hasText: 'C' })).toHaveCount(0)

  // Frames arrive: the HUD replaces the placeholder and shows a live signal.
  await injectScene(page)
  await expect(hud(page)).toBeVisible({ timeout: 5_000 })

  // A bright card sits settled at the lens: exactly one fire — and with no box selected
  // the screen declines it for a stated reason and COUNTS it. One fire, one drop,
  // nothing written anywhere.
  await expect(hud(page)).toContainText('fires 1', { timeout: 5_000 })
  await expect(hud(page)).toContainText('dropped 1')

  // The feeder swaps in a different card: motion, settle, second fire.
  await swapTo(page, 110)
  await expect(hud(page)).toContainText('fires 2', { timeout: 5_000 })
  await expect(hud(page)).toContainText('dropped 2')

  // The tray gets bumped and the SAME card settles again: the novelty gate suppresses
  // instead of double-firing, and says so on screen.
  await swapTo(page, 110)
  await expect(hud(page)).toContainText('same 1', { timeout: 5_000 })
  await expect(hud(page)).toContainText('fires 2')

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
    params: { tHi: number }
    grid: { w: number; h: number; roi: number[] }
    truncated: boolean
    frames: Array<[number, number, number]>
    events: Array<{ t: number; event: string; frame: string }>
    keyframes: Array<{ t: number; frame: string }>
  }
  expect(trace.kind).toBe('pkmnscan-motion-trace')
  expect(trace.truncated).toBe(false)
  expect(trace.params.tHi).toBeGreaterThan(0)
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
  const kinds = trace.events.map((e) => e.event)
  expect(kinds.filter((k) => k === 'fire')).toHaveLength(2)
  expect(kinds).toContain('suppressed:unchanged')
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
