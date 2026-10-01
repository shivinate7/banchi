// Protects: The theme flips in one crossfade that never paints a frame matching neither theme; the capture flash is a light 200ms shot.
// Governs: D50
import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'
import { setViewport } from './phoneSwitch'

sealEveryTest({ store: true, cards: 4 })

test.beforeEach(async ({ page }) => {
  await page.route(/\/orders$/, (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify({ summary: '', orders: [], resolution: { orders: [], counts: {} } }) }),
  )
})

/* docs/specs/motion.md, P4 and P5. THE THEME GUARD SAMPLES THE BODY'S OWN COLOUR EVERY FRAME OF
 * THE SWITCH. The old flip eased every node's colours at once and the page went mid-grey for ~60ms,
 * so a sample landed on a colour that is neither theme's ground. A View Transition draws two whole
 * snapshots, so `body` itself is never in between: its computed colour is the old ground or the new. */
const GROUND = async (page: import('@playwright/test').Page) =>
  page.evaluate(() => {
    const read = (theme: 'light' | 'dark') => {
      const root = document.documentElement
      const had = root.getAttribute('data-theme')
      if (theme === 'dark') root.setAttribute('data-theme', 'dark')
      else root.removeAttribute('data-theme')
      const c = getComputedStyle(document.body).backgroundColor
      if (had === null) root.removeAttribute('data-theme')
      else root.setAttribute('data-theme', had)
      return c
    }
    return { light: read('light'), dark: read('dark') }
  })

for (const from of ['light', 'dark'] as const) {
  test(`the theme switch from ${from} never shows a body colour of neither theme`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: from })
    await setViewport(page, { width: 1440, height: 900 })
    await page.goto('/#/')
    await expect(page.locator('main.home')).toBeVisible()
    await page.evaluate((t) => localStorage.setItem('banchi.theme', t), from)
    await page.reload()
    await expect(page.locator('main.home')).toBeVisible()
    const ground = await GROUND(page)
    const seen = await page.evaluate(async () => {
      const toggle = [...document.querySelectorAll<HTMLElement>('button')].find((b) => b.textContent?.trim() === 'Theme')
      if (!toggle) throw new Error('no theme toggle')
      const colours = new Set<string>()
      let running = true
      const sample = () => {
        colours.add(getComputedStyle(document.body).backgroundColor)
        if (running) requestAnimationFrame(sample)
      }
      sample()
      toggle.click()
      await new Promise((r) => setTimeout(r, 700))
      running = false
      return [...colours]
    })
    for (const colour of seen) expect([ground.light, ground.dark], `sampled ${colour}`).toContain(colour)
    expect(seen.length, 'the theme did flip').toBeGreaterThan(0)
  })
}

test('the capture flash is 0.6 at its peak and 200ms long', async ({ page }) => {
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()
  const { peak, duration, token } = await page.evaluate(() => {
    const span = document.createElement('span')
    span.className = 'bn-flash'
    document.body.append(span)
    const a = span.getAnimations()[0]!
    const out = {
      peak: Number((a.effect as KeyframeEffect).getKeyframes()[0]!.opacity),
      duration: Number(a.effect!.getComputedTiming().duration),
      token: parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--bn-t-flash')),
    }
    span.remove()
    return out
  })
  expect(peak).toBe(0.6)
  expect(duration).toBe(200)
  expect(token, 'the duration is the token').toBe(200)
})
