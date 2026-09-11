import { expect, test } from '@playwright/test'
import { sealEveryTest } from './shell'
import type { Page } from '@playwright/test'
import type { GameRegistry } from '../src/types'
const GAMES: GameRegistry = {
  default: 'pokemon',
  /* C10's vocabulary, as `GET /games` really answers it — see the annotation note above. */
  products: [
    { key: 'booster', display: 'Booster pack', premium: false, redeem_limit: 400 },
    { key: 'pc_etb', display: 'Pokémon Center ETB', premium: true, redeem_limit: 4 },
  ],
  product_game: 'pokemon_code',
  games: [
    {
      key: 'pokemon',
      display: 'Pokémon',
      product_line: 'Pokemon',
      rarities: ['Common', 'Uncommon', 'Rare'],
      finishes: ['normal', 'holo', 'reverse_holo'],
      condition_by_finish: {
        normal: 'Near Mint',
        holo: 'Near Mint Holofoil',
        reverse_holo: 'Near Mint Reverse Holofoil',
      },
      finish_by_rarity: {
        Common: ['normal'],
        Uncommon: ['normal', 'reverse_holo'],
        Rare: ['normal', 'holo', 'reverse_holo'],
      },
      located: true,
      join_key: 'number_over_printed_total',
      prompt: 'pokemon',
      crop_bands: ['title', 'number'],
      card_aspect: 0.716,
      unverified: false,
      catalogued: true,
    },
  ],
}

/** Pokemon's THIRTEEN rarities, verbatim from `pipeline/games.py` — stack order and matrix
 *  both. The three-rarity fixture above cannot see the case these last cases are about: the
 *  option alphabet only runs past the digits when a vocabulary does, and Pokemon's is the
 *  longest one any game authors. Copied rather than trimmed for the header's reason — a
 *  fixture that invented a rarity would be testing itself. */
sealEveryTest()

const RATE = Number(process.env.PROBE_CPU ?? '1')
const logs: string[] = []

test.beforeEach(async ({ page }) => {
  logs.length = 0
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE })
  page.on('console', (m) => {
    const t = m.text()
    if (t.startsWith('PROBE')) logs.push(`${Date.now() % 100000} ${t}`)
  })
  await page.addInitScript(() => {
    const track = () => document.querySelectorAll('.capture-track[aria-label="Finish"] .capture-cell').length
    window.addEventListener(
      'keydown',
      (e) => {
        const el = document.activeElement
        console.log(`PROBE KD ${e.key} active=${el?.tagName}.${(el as HTMLElement)?.className} track=${track()}`)
        setTimeout(() => console.log(`PROBE KD-after ${e.key} prevented=${e.defaultPrevented} track=${track()}`), 0)
      },
      true,
    )
  })
  await page.route(/\/games$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GAMES) })
  })
  await page.route(/\/boxes$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ boxes: [] }) })
  })
})

test.afterEach(async ({}, info) => {
  if (info.status !== info.expectedStatus) console.log(logs.join('\n'))
})

function finishRow(page: Page) {
  return page.locator('.capture-row, .capture-open').filter({ hasText: /Finish/ }).first()
}
function finishCells(page: Page) {
  return page.locator('.capture-track[aria-label="Finish"] .capture-cell')
}

test('probe: open helper under throttle', async ({ page }) => {
  await page.goto('/#/capture')
  await expect(finishRow(page)).toBeVisible()
  await expect(async () => {
    await page.keyboard.press('f')
    await expect(finishCells(page).first()).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.press('Escape')
  await expect(finishCells(page)).toHaveCount(0, { timeout: 5_000 })
})
