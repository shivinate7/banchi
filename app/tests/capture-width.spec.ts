// Protects: The Capture screen leaves no unused horizontal band inside its page frame at 1440 and 820.
// Governs: D118, D195, D197
import { expect, test } from '@playwright/test'
import { sealEveryTest, settleAnimations } from './shell'

/* THE WIDTH THE VIEWFINDER GAVE UP MUST GO TO SOMETHING (owner, 2026-09-28; spec §5.7).
 * `fc90e00c` made the stage panel hug its 9:16 frame and handed the freed width to a `1fr` last
 * capture column. That photo is 9:16 and height-bound, so it could not use the width: the panel
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
/** The deliberate right-hand margin: what is left of the shell once the controls sit at their cap. */
const RIGHT_MARGIN = (w: { rightBand: number; railW: number }) => (w.railW >= 459 ? w.rightBand : 0)

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
      await page.setViewportSize({ width, height })
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
          const railW = Math.round(document.querySelector('.capture-card-run')!.getBoundingClientRect().width)
          return { colGap, railW, rightBand: Math.round(shell.right - lastRight), worstGap: Math.round(worstGap), worstY, shellWidth: Math.round(shell.width) }
        },
        { painted: PAINTED, step: 8 },
      )
      expect(
        worst.worstGap,
        `${worst.worstGap}px of the ${worst.shellWidth}px shell is unpainted at y=${worst.worstY}`,
      ).toBeLessThanOrEqual(2 * worst.colGap + SLACK + RIGHT_MARGIN(worst))
      // Width the controls cannot use (they stop at 460px) is page margin on the right, and only then.
      expect(worst.rightBand, `${worst.rightBand}px of empty shell right of Last capture`).toBeLessThanOrEqual(worst.railW >= 459 ? 400 : 48)
    })
  }
}
