/**
 * The published demo, as built: every screen a reviewer grades on it must draw its data.
 *
 * WHY THIS EXISTS. Every reviewer of the 2026-09 UX overhaul graded the product on the public
 * demo, and the demo could not show photographs (the recorder copied from a folder the seed
 * stopped writing when D183 moved them), undo, the order walk, the graveyard, product history,
 * value bands, facet counts or a typed search. Each of those failed as a quiet refusal or a
 * broken image, so a reviewer could not tell a demo gap from a product defect. This spec reads
 * the BUILT artefact, `dist-demo/`, and fails when one of those screens goes back to refusing.
 *
 * WHAT IT RUNS AGAINST. The files `make demo-static` wrote, served on this checkout's own dev
 * origin under the demo's base path, exactly as a static host serves them (every request under
 * the base path is answered from `dist-demo/` and nothing reaches Vite). With
 * `DEMO_PREVIEW_URL` set — for example `http://localhost:4173` while `make demo-preview`
 * runs — each file is fetched from that preview server instead, so the same assertions read
 * what the preview serves. Either way the page itself talks to one origin only, and
 * `sealEveryTest` still refuses anything else.
 *
 * SKIPPED, BY NAME, WHEN THERE IS NO BUILD. `make design-check` does not build the demo, so a
 * tree without `dist-demo/` skips these cases with the reason rather than failing them.
 * Run `make demo-static` first.
 */
import { test, expect, type Page } from '@playwright/test'
import { existsSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'
import { DEV_URL } from '../devPort'
import { sealEveryTest } from './shell'

const HERE = dirname(fileURLToPath(import.meta.url))
const DIST = join(HERE, '..', '..', 'dist-demo')
const BUNDLE = join(HERE, '..', 'demo', 'bundle.json')
const BUILT = existsSync(join(DIST, 'index.html'))
const PREVIEW = process.env.DEMO_PREVIEW_URL?.replace(/\/$/, '') ?? null

/** The base path the build was made for (`DEMO_BASE`), read off its own index.html. */
function basePath(): string {
  const html = readFileSync(join(DIST, 'index.html'), 'utf-8')
  const found = /(?:src|href)="(\/[^"]*?)assets\//.exec(html)
  return found?.[1] ?? '/'
}

const REFUSAL = 'Not in this demo.'
const HOME = '#/'
/** The Fulfiller's screen. Its sidebar row opens a new window, so it is opened by hash. */
const FULFILLER = '#/fulfillment'

sealEveryTest()

test.skip(!BUILT, 'no dist-demo/ in this checkout: run `make demo-static` first')

/** Serve the built demo on this checkout's own origin, the way a static host would. */
async function serveDemo(page: Page): Promise<string> {
  const base = basePath()
  await page.route(`${DEV_URL}${base}**`, async (route) => {
    const url = new URL(route.request().url())
    if (PREVIEW !== null) {
      const response = await route.fetch({ url: `${PREVIEW}${url.pathname}` })
      await route.fulfill({ response })
      return
    }
    let file = normalize(join(DIST, decodeURIComponent(url.pathname.slice(base.length))))
    if (!file.startsWith(DIST)) {
      await route.fulfill({ status: 403, body: '' })
      return
    }
    if (existsSync(file) && statSync(file).isDirectory()) file = join(file, 'index.html')
    if (!existsSync(file)) {
      await route.fulfill({ status: 404, body: '' })
      return
    }
    await route.fulfill({ path: file })
  })
  return `${DEV_URL}${base}`
}

/** Open the built demo at a hash and wait for its first read to land. */
async function open(page: Page, hash: string): Promise<void> {
  const origin = await serveDemo(page)
  await page.goto(`${origin}${hash}`)
  await page.locator('main').first().waitFor()
  // The demo answers every read after a 45-135 ms pause, on purpose (`demoRequest`).
  await page.waitForTimeout(600)
}

/**
 * Arrive at a screen the way a visitor does: land on Home, press its row in the sidebar.
 *
 * BY THE SIDEBAR, NOT BY A TYPED HASH. This spec names the screens reviewers could not grade,
 * one case each. It is not a roster of every route, and it must not read as one
 * (`make docs-audit`'s `route rosters` row). Arriving by the sidebar also proves the hash
 * router works under the demo's base path, which only a published build can get wrong.
 */
async function visit(page: Page, screen: string): Promise<void> {
  await open(page, HOME)
  await page.locator('.bn-side').getByRole('link', { name: new RegExp(`^${screen}`) }).first().click()
  await page.locator('main').first().waitFor()
  await page.waitForTimeout(600)
}

/** Every demo photograph the page asked for, with the status it got. */
function watchPhotos(page: Page): Array<{ url: string; status: number }> {
  const seen: Array<{ url: string; status: number }> = []
  page.on('response', (response) => {
    if (response.url().includes('/demo/photos/')) seen.push({ url: response.url(), status: response.status() })
  })
  return seen
}

test.describe('the published demo draws what reviewers grade', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('every card in the recorded store has its photograph in the build', () => {
    const bundle = JSON.parse(readFileSync(BUNDLE, 'utf-8')) as {
      responses: Record<string, { body: { cards?: Record<string, { box: number; index: number; photo?: string | null }> } }>
    }
    const cards = Object.values(bundle.responses['/inventory']?.body.cards ?? {})
    const withPhoto = cards.filter((card) => typeof card.photo === 'string' && card.photo !== '')
    expect(withPhoto.length, 'the recorded store holds no card with a photograph').toBeGreaterThan(0)
    const missing = withPhoto
      .filter((card) => !existsSync(join(DIST, 'demo', 'photos', String(card.box), `${card.index}.jpg`)))
      .map((card) => `${card.box}/${card.index}`)
    expect(missing, 'cards whose photograph the build does not carry').toEqual([])
  })

  for (const screen of ['Inventory', 'Review', 'Pricing', 'Home', 'Cards to pull'] as const) {
    test(`${screen} draws its photographs, and every one answers 200`, async ({ page }) => {
      const photos = watchPhotos(page)
      if (screen === 'Cards to pull') await open(page, FULFILLER)
      else await visit(page, screen)
      await expect.poll(() => photos.length, { message: `${screen} asked for no photograph` }).toBeGreaterThan(0)
      expect(photos.filter((photo) => photo.status !== 200)).toEqual([])
      const broken = await page.evaluate(
        () => [...document.images].filter((img) => img.src.includes('/demo/photos/') && img.complete && img.naturalWidth === 0).length,
      )
      expect(broken, 'a photograph the page drew as broken').toBe(0)
    })
  }

  test('Capture draws its recent strip once a box is picked, and every photograph answers 200', async ({ page }) => {
    const photos = watchPhotos(page)
    await visit(page, 'Capture')
    await page.getByRole('button', { name: 'Pick a box' }).first().click()
    await page.getByText('RB Origins').first().click()
    await expect.poll(() => photos.length, { message: 'Capture asked for no photograph' }).toBeGreaterThan(0)
    expect(photos.filter((photo) => photo.status !== 200)).toEqual([])
  })

  test('Inventory: Mark sold, then Undo, puts the card and the box counts back', async ({ page }) => {
    await visit(page, 'Inventory')
    const box = page.locator('button:has-text("RB Origins")').first()
    await expect(box).toContainText('34 on hand')
    await page.getByRole('button', { name: 'Mark sold' }).first().click()
    await expect(box).toContainText('33 on hand')
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
    await page.getByRole('button', { name: /^Undo/ }).first().click()
    await expect(box).toContainText('34 on hand')
    await expect(page.getByRole('button', { name: 'Mark sold' }).first()).toBeVisible()
  })

  test('Inventory: a Game pick draws a count on every box', async ({ page }) => {
    await visit(page, 'Inventory')
    // The native menu `BoxBrowse` draws today. When the shared filter control replaces it,
    // this line follows it; the assertion below is what the case is about.
    await page.locator('select[aria-label="Filter by game"]').first().selectOption({ index: 2 })
    const rows = page.locator('button:has-text("match")')
    await expect(rows.first()).toBeVisible()
    expect(await rows.count()).toBeGreaterThanOrEqual(4)
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Inventory: a typed search finds a card the recorder never searched for', async ({ page }) => {
    await visit(page, 'Inventory')
    await page.getByPlaceholder(/Card name/).pressSequentially('Crowd Favorite', { delay: 40 })
    await expect(page.getByRole('heading', { name: 'Crowd Favorite' })).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Cards to pull: search finds a card', async ({ page }) => {
    await open(page, FULFILLER)
    await page.getByPlaceholder(/For example/).pressSequentially('Crowd', { delay: 40 })
    await expect(page.getByText('Crowd Favorite').first()).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Orders draws a walk', async ({ page }) => {
    await visit(page, 'Orders')
    const walk = page.getByRole('list', { name: /cards this walk covers/i })
    await expect(walk).toBeVisible()
    expect(await walk.getByRole('button').count()).toBeGreaterThan(0)
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Review: an answer, then Undo, puts the question back', async ({ page }) => {
    await visit(page, 'Review')
    await expect(page.getByText(/Card 1 of 9/)).toBeVisible()
    await page.locator('button:has-text("Near Mint Foil")').first().click()
    await expect(page.getByText(/Answered as/).first()).toBeVisible()
    await page.getByRole('button', { name: /^Undo/ }).first().click()
    await expect(page.getByText(/Card 1 of 9/)).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Graveyard lists the departed', async ({ page }) => {
    await visit(page, 'Graveyard')
    await expect(page.getByRole('row').filter({ hasText: 'Sold' }).first()).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Product history draws the one real reading the demo carries', async ({ page }) => {
    await open(page, '#/product?sku=9189317')
    await expect(page.getByRole('heading', { name: 'Vilemaw' })).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Pricing: the value band draws its cards', async ({ page }) => {
    await open(page, '#/pricing?band=top')
    await expect(page.getByRole('heading', { name: /worth pulling/i })).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Sales: "Value my stock" draws a figure', async ({ page }) => {
    await visit(page, 'Sales')
    await page.getByRole('button', { name: /Value my stock/ }).click()
    await expect(page.getByText(/Priced for \d+ of \d+ names on hand/)).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })
})
