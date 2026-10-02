// Protects: The theme button cycles light, dark, Abyssal Bloom and Carnival Midway and the choice survives a reload; light and dark paint as before; both palettes keep body text readable; switching moves nothing.
// Governs: D50, D313
import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { THEMES } from '../src/deviceMemory'
import { sealEveryTest } from './shell'
import { setViewport } from './phoneSwitch'

sealEveryTest({ store: true, cards: 4 })

test.beforeEach(async ({ page }) => {
  await page.route(/\/orders$/, (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify({ summary: '', orders: [], resolution: { orders: [], counts: {} } }) }),
  )
})

/* THEMES is the one list; this spec reads it and keeps no copy of its own. */
const ORDER = THEMES.map((t) => t.id)
const attrsFor = (id: string) => {
  const entry = THEMES.find((t) => t.id === id)
  return { theme: id === 'light' ? null : 'dark', palette: entry && 'palette' in entry ? entry.palette : null }
}

test('the pre-paint script in index.html lists exactly the ids in THEMES', () => {
  const html = readFileSync(fileURLToPath(new URL('../index.html', import.meta.url)), 'utf8')
  const known = /var known = \[([^\]]*)\]/.exec(html)?.[1]
  expect(known, 'index.html has no `var known = [...]`').toBeDefined()
  const ids = [...(known ?? '').matchAll(/'([^']+)'/g)].map((m) => m[1])
  expect(ids).toEqual(ORDER)
})

const attrs = (page: Page) =>
  page.evaluate(() => ({
    theme: document.documentElement.getAttribute('data-theme'),
    palette: document.documentElement.getAttribute('data-palette'),
    // eslint-disable-next-line no-restricted-syntax -- reads the theme's own device key (deviceMemory.ts), seeds nothing
    stored: window.localStorage.getItem('banchi.theme'),
  }))
const toggle = (page: Page) => page.locator('aside button', { hasText: 'Theme' }).first()

async function open(page: Page, scheme: 'light' | 'dark' = 'light'): Promise<void> {
  await page.emulateMedia({ colorScheme: scheme, reducedMotion: 'reduce' })
  await setViewport(page, { width: 1440, height: 900 })
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()
}

test('the theme button cycles all four themes in order and a reload keeps the choice', async ({ page }) => {
  await open(page)
  expect(await attrs(page)).toMatchObject({ ...attrsFor('light'), stored: null })
  for (const id of [...ORDER.slice(1), ORDER[0]]) {
    await toggle(page).click()
    expect(await attrs(page), id).toMatchObject({ ...attrsFor(id ?? ''), stored: id })
    await page.reload()
    await expect(page.locator('main.home')).toBeVisible()
    expect(await attrs(page), `${id} after reload`).toMatchObject({ ...attrsFor(id ?? ''), stored: id })
  }
})

test('the button names the next theme, and an unknown stored value falls back to the system', async ({ page }) => {
  await open(page)
  await expect(toggle(page)).toHaveAttribute('title', 'Switch to Dark')
  // eslint-disable-next-line no-restricted-syntax -- seeds the theme's own device key (deviceMemory.ts) with a value it must reject
  await page.evaluate(() => window.localStorage.setItem('banchi.theme', 'solarized'))
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' })
  await page.reload()
  await expect(page.locator('main.home')).toBeVisible()
  expect(await attrs(page)).toMatchObject({ theme: 'dark', palette: null })
  await expect(toggle(page)).toHaveAttribute('title', 'Switch to Abyssal Bloom')
})

/* "unchanged" is asserted as the literal colors the plain themes painted before palettes existed. */
const PLAIN = {
  light: { accent: 'rgb(61, 90, 241)', label: 'rgb(102, 108, 118)' },
  dark: { accent: 'rgb(127, 144, 255)', label: 'rgb(131, 139, 152)' },
} as const
for (const scheme of ['light', 'dark'] as const) {
  test(`${scheme}: the nav, the segmented tab, the page ground and the row stripe paint as before`, async ({ page }) => {
    await open(page, scheme)
    const read = () =>
      page.evaluate(() => {
        const css = (el: Element | null, p: string) => (el ? getComputedStyle(el).getPropertyValue(p) : 'missing')
        const link = document.querySelector('.bn-nav-group:nth-of-type(1) .bn-nav-link[aria-current="page"]')
        const label = document.querySelector('.bn-nav-group:nth-of-type(2) .bn-nav-group-label')
        const host = document.createElement('div')
        host.innerHTML = '<div class="pricing-row"></div><div class="pricing-row"></div>'
        document.body.append(host)
        const stripe = css(host.children[1] ?? null, 'background-color')
        host.remove()
        return {
          linkColor: css(link, 'color'),
          label: css(label, 'color'),
          image: css(document.body, 'background-image'),
          stripe,
        }
      })
    const got = await read()
    expect(got.linkColor).toBe(PLAIN[scheme].accent)
    expect(got.label).toBe(PLAIN[scheme].label)
    expect(got.image).toBe('none')
    expect(got.stripe).toBe('rgba(0, 0, 0, 0)')
  })
}

const channel = (v: number) => {
  const s = v / 255
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
const luminance = (rgb: string) => {
  const [r, g, b] = (rgb.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number) as [number, number, number]
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}
const ratio = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}

for (const id of ['abyssal-bloom', 'carnival-midway'] as const) {
  test(`${id}: body text clears 4.5:1 on the page and on a panel`, async ({ page }) => {
    await open(page, 'dark')
    while ((await attrs(page)).palette !== id) await toggle(page).click()
    const c = await page.evaluate(() => {
      const t = (name: string) => {
        const probe = document.createElement('i')
        probe.style.color = `var(${name})`
        document.body.append(probe)
        const out = getComputedStyle(probe).color
        probe.remove()
        return out
      }
      return { bg: t('--bn-bg'), surface: t('--bn-surface'), ink: t('--bn-ink'), ink2: t('--bn-ink-2'), ink3: t('--bn-ink-3') }
    })
    for (const ink of ['ink', 'ink2', 'ink3'] as const) {
      for (const ground of ['bg', 'surface'] as const) {
        expect(ratio(c[ink], c[ground]), `${ink} on ${ground}`).toBeGreaterThanOrEqual(4.5)
      }
    }
  })
}

test('switching theme moves nothing (D313)', async ({ page }) => {
  await open(page)
  const boxes = () =>
    page.evaluate(() =>
      [...document.querySelectorAll('.bn-side, .bn-nav-link, main h1, main .bn-page, main section')].map((el) => {
        const r = el.getBoundingClientRect()
        return [Math.round(r.x * 100), Math.round(r.y * 100), Math.round(r.width * 100), Math.round(r.height * 100)].join(',')
      }),
    )
  const before = await boxes()
  expect(before.length).toBeGreaterThan(5)
  for (let i = 0; i < ORDER.length; i += 1) {
    await toggle(page).click()
    expect(await boxes(), `after ${i + 1} presses`).toEqual(before)
  }
})
