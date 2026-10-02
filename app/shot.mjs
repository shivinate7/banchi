// throwaway mock-branch screenshot helper: node shot.mjs <name> <hash> [full] [clickSelector]
import { chromium } from 'playwright'
const OUT = '/private/tmp/claude-501/-Users-shivinate-Developer-pkmnscan/e2ca9a2c-5545-4424-987e-bf4b5f36e119/scratchpad/graveyard-rethink'
const [name, hash, full, click, scrollSel] = process.argv.slice(2)
const browser = await chromium.launch()
for (const [w, theme] of [[1440, 'light'], [1440, 'dark'], [820, 'light']]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 1000 }, colorScheme: theme })
  await ctx.addInitScript((t) => localStorage.setItem('banchi.theme', t), theme)
  const page = await ctx.newPage()
  await page.goto(`http://localhost:5205/${hash}`)
  await page.waitForTimeout(2500)
  if (click && click !== '-') { await page.click(click); await page.waitForTimeout(1500) }
  if (scrollSel) { await page.locator(scrollSel).first().evaluate((e) => e.scrollIntoView({ block: 'nearest' })); await page.waitForTimeout(1200) }
  await page.screenshot({ path: `${OUT}/${name}-${w}-${theme}.png`, fullPage: full === 'full' })
  await ctx.close()
}
await browser.close()
