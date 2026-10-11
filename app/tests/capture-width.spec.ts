// Protects: The Capture screen leaves no unused horizontal band inside its page frame at 1440 and 820.
// Governs: D118, D195, D197
import { expect, test } from '@playwright/test'
import { sealEveryTest, settleAnimations } from './shell'
import { setViewport } from './phoneSwitch'

/* SPARE WIDTH GOES TO THE BLACK STAGE PANEL, NEVER TO A WHITE BAND (owner, 2026-09-28, 2026-09-29).
 * The stage panel flexes with the sidebar and its 9:16 frame stays centred (a painted box, so its
 * width is not a band); the last-capture column hugs its photo. `fc90e00c` once handed the freed
 * width to a `1fr` last capture column instead. That photo is 9:16 and height-bound, so it could not use the width: the panel
 * went from 320 to 403px at 1440 and the frame inside stayed narrower, a white band either side.
 *
 * WHAT THIS MEASURES: for every 8px row from the stage's top to the photo's bottom, the width of the shell that no
 * painted box covers. The boxes are the four cards, the filmstrip, the stage, the last-capture
 * head and its frame (the photo, or the empty frame). The unspent width in a row may be the grid's
 * own gaps plus a small tolerance, never a band. Nothing is captured and no camera is opened. */

sealEveryTest({ store: true })

const PAINTED = [
  '.capture-card-run',
  '.capture-film',
  '.capture-card-stack',
  '.capture-card-rig',
  '.capture-stage',
  '.capture-last .capture-panel-head',
  '.capture-frame-last',
]

/** 24px for a frame's own padding and rounding, on top of the grid's two column gaps (read live). */
const SLACK = 24

for (const theme of ['light', 'dark'] as const) {
  for (const [width, height] of [
    [1440, 900],
    [820, 1100],
    // The owner's real window: ~2000 wide, rail collapsed, where the page hits its 1600px cap.
    [2000, 1300],
  ] as const) {
    test(`Capture leaves no unused horizontal band at ${width}, ${theme}`, async ({ page }) => {
      if (width === 2000) {
        await page.addInitScript(() => {
          try {
            /* eslint-disable-next-line no-restricted-syntax -- seeding the shell's own device key before first paint, as `wide.spec.ts:withRail` does. */
            window.localStorage.setItem('banchi.rail', 'rail')
          } catch {
            /* unreadable storage reads as the sidebar, a real default */
          }
        })
      }
      await setViewport(page, { width, height })
      await page.emulateMedia({ colorScheme: theme })
      await page.goto('/#/capture')
      await page.locator('.capture-shell').waitFor()
      await page.locator('.capture-frame-last').waitFor()
      // The frame is 9:16 and shrinks once a receipt sits under it (`data-has-last`), which is
      // the state every real session is in after the first capture; put the empty frame in it.
      await page.locator('.capture-last').evaluate((e) => e.setAttribute('data-has-last', 'true'))
      // Entrance animations move boxes; measure the settled layout.
      await settleAnimations(page)

      const worst = await page.evaluate(
        ({ painted, step }) => {
          const shell = document.querySelector('.capture-shell')!.getBoundingClientRect()
          const stage = document.querySelector('.capture-stage')!.getBoundingClientRect()
          // Below the photo sits the receipt, which this empty state does not draw.
          const photoEnd = document.querySelector('.capture-frame-last')!.getBoundingClientRect().bottom
          // Each box counts 16px past its bottom: the grid's own row gap is not a band.
          const boxes = painted.flatMap((s) =>
            [...document.querySelectorAll(s)].map((e) => {
              const b = e.getBoundingClientRect()
              return { left: b.left, right: b.right, top: b.top, bottom: b.bottom + 16, width: b.width }
            }),
          )
          let worstY = 0
          let worstGap = 0
          for (let y = stage.top + 1; y < Math.min(stage.bottom, photoEnd); y += step) {
            const spans = boxes
              .filter((b) => b.width > 0 && b.top <= y && b.bottom > y)
              .map((b): [number, number] => [Math.max(b.left, shell.left), Math.min(b.right, shell.right)])
              .sort((a, b) => a[0] - b[0])
            let covered = 0
            let end = shell.left
            for (const [l, r] of spans) {
              if (r <= end) continue
              covered += r - Math.max(l, end)
              end = r
            }
            const gap = shell.width - covered
            if (gap > worstGap) {
              worstGap = gap
              worstY = Math.round(y)
            }
          }
          const colGap = parseFloat(getComputedStyle(document.querySelector('.capture-shell')!).columnGap) || 0
          // Nothing may sit between Last capture and the shell's right edge but a small margin.
          const lastRight = document.querySelector('.capture-last')!.getBoundingClientRect().right
          return { colGap, rightBand: Math.round(shell.right - lastRight), worstGap: Math.round(worstGap), worstY, shellWidth: Math.round(shell.width) }
        },
        { painted: PAINTED, step: 8 },
      )
      expect(
        worst.worstGap,
        `${worst.worstGap}px of the ${worst.shellWidth}px shell is unpainted at y=${worst.worstY}`,
      ).toBeLessThanOrEqual(2 * worst.colGap + SLACK)
      // The stage panel (black, a painted box) takes the spare width, so nothing is left beside Last capture.
      expect(worst.rightBand, `${worst.rightBand}px of empty shell right of Last capture`).toBeLessThanOrEqual(48)
    })
  }
}

// Protects: `setViewport` returns on a final layout; a read right after a resize across the rail breakpoint is not mid-slide.
test('setViewport leaves the shell columns final across the rail breakpoint', async ({ page }) => {
  const shell = page.locator('.bn-shell')
  const read = () => shell.evaluate((e) => getComputedStyle(e).gridTemplateColumns)
  const readLater = () =>
    shell.evaluate((e) => new Promise<string>((done) => requestAnimationFrame(() => done(getComputedStyle(e).gridTemplateColumns))))
  await setViewport(page, { width: 1440, height: 900 })
  await page.goto('/#/capture')
  await shell.waitFor()
  for (const [width, height] of [
    [820, 1100],
    [1440, 900],
  ] as const) {
    await setViewport(page, { width, height })
    const first = await read()
    expect(await readLater(), `columns at ${width} still moving right after setViewport`).toBe(first)
  }
})

/* ux-wave1 B3 (A14). The "Last capture" panel does not change height when the first capture lands
   (nothing on screen moves unless the person moved it). At the rail width the case measures the empty
   panel, then the same panel in its has-a-receipt state at the same width, and asks for the two heights
   to match. The receipt state is the attribute the screen itself sets after a capture (no capture is
   taken here). The empty sentence must sit inside the viewport. Nothing is tuned to a pixel. */
test('ux-wave1: at 820 the Last capture panel keeps its height when the first capture lands', async ({ page }) => {
  /* 820 by 900 is the audit's own rail-width viewport (the shots in the UX audit were taken at it). */
  await setViewport(page, { width: 820, height: 900 })
  await page.goto('/#/capture')
  await page.locator('.capture-shell').waitFor()
  await settleAnimations(page)
  const panel = page.locator('.capture-last')
  const note = page.locator('.capture-frame-last .capture-frame-title')
  /* THE STATE THAT SQUEEZES THE PANEL: no box picked, camera off, dispenser not connected. The Setup
     block lists the Camera and Box fixes, and the right column grows to hold it. */
  await expect(page.locator('.capture-block'), 'the Setup block is drawn (no box, camera off)').toBeVisible()
  await expect(page.getByRole('button', { name: 'Box', exact: true }), 'the Setup block offers Box').toBeVisible()
  await expect(panel).toHaveAttribute('data-has-last', 'false')
  await expect(note, 'the empty panel names its state').toHaveText(/nothing captured yet/i)
  const empty = await panel.boundingBox()
  const noteBox = await note.boundingBox()
  const viewport = await page.evaluate(() => window.innerHeight)
  expect(noteBox !== null && noteBox.y + noteBox.height <= viewport, 'the empty sentence is inside the viewport').toBe(true)
  expect.soft(
    noteBox !== null && empty !== null && noteBox.y + noteBox.height <= empty.y + empty.height + 1,
    `the empty sentence sits inside its panel at 820 (panel ${empty?.height}px, sentence bottom ${noteBox ? Math.round(noteBox.y + noteBox.height) : 'none'}, panel bottom ${empty ? Math.round(empty.y + empty.height) : 'none'})`,
  ).toBe(true)

  await panel.evaluate((el) => el.setAttribute('data-has-last', 'true'))
  await settleAnimations(page)
  const receipt = await panel.boundingBox()
  expect(empty?.height ?? 0, `empty panel ${empty?.height}px, with a receipt ${receipt?.height}px`).toBeCloseTo(receipt?.height ?? -1, 0)
})
