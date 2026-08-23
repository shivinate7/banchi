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

  // Arm motion. All three indicators change: the pressed chip, the machine string, and
  // the HUD placeholder (no camera is open yet, and the readout says so rather than
  // rendering zeros that look like a working machine seeing nothing).
  await page.getByRole('button', { name: /motion/ }).click()
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

  // Disarm: the key trigger is back, the HUD is gone, the chip released.
  await page.getByRole('button', { name: /press C/ }).click()
  await expect(page.locator('.capture-trigger')).toHaveText('manual:c')
  await expect(hud(page)).toHaveCount(0)
})
