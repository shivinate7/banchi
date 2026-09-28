/* Render the lane-A mockups to PNG, at 1440, 820 and 390, light and dark.
 *
 * The PNGs are NOT tracked: `scripts/githooks/pre-commit` refuses any image outside the
 * demo photo folders (a code-card photo is a bearer instrument). So they go to a folder you
 * name, outside the repository.
 *
 *   NODE_PATH=app/node_modules node docs/reviews/ux-2026-09-23/orders-a/render.cjs <out-dir>
 */
const { chromium } = require('playwright')
const path = require('path')

const here = __dirname
const out = process.argv[2]
if (!out) {
  console.error('name an output folder outside the repository')
  process.exit(2)
}
const shots = [
  ['desk', 1440, 900, 'desk-1440'],
  ['desk', 820, 1000, 'desk-820'],
  ['phone', 390, 844, 'phone-390'],
  ['desk-walk-in-rail', 1440, 900, 'alt-walk-in-rail-1440', ['light']],
]
;(async () => {
  const browser = await chromium.launch()
  for (const [file, w, h, name, themes] of shots) {
    for (const theme of themes || ['light', 'dark']) {
      const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1, reducedMotion: 'reduce' })
      await page.goto('file://' + path.join(here, `${file}.html`) + `?theme=${theme}`)
      await page.waitForTimeout(700)
      const full = await page.evaluate(() => document.documentElement.scrollHeight)
      const sideways = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
      console.log(name, theme, 'height', full, 'sideways scroll', sideways)
      if (file === 'phone') {
        await page.screenshot({ path: path.join(out, `${name}-${theme}.png`) })
        await page.addStyleTag({ content: '.browse-actionbar, .bn-tabbar, .bn-topbar { display: none !important; }' })
        await page.screenshot({ path: path.join(out, `${name}-scroll-${theme}.png`), fullPage: true, clip: { x: 0, y: 0, width: w, height: Math.min(full, 3000) } })
      } else {
        await page.screenshot({ path: path.join(out, `${name}-${theme}.png`), fullPage: true, clip: { x: 0, y: 0, width: w, height: Math.min(full, file === 'desk' ? 1500 : h) } })
      }
      await page.close()
    }
  }
  await browser.close()
})()
