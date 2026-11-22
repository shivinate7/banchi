import { expect, type Locator, type Page } from '@playwright/test'

/* The Orders page's Filters sheet. One home for the facet picks that `orders.spec.ts` and
 * `order-walk.spec.ts` both make, so a case that asks whether a buyer is under Open or Done calls
 * these instead of copying them. */

/** THE FILTER BAR IS ONE LINE (the owner, 2026-09-24): every facet, the sort and the hide toggle
 *  are in the Filters sheet. Open it, returning the sheet's body. */
export async function openFilters(page: Page): Promise<Locator> {
  await page.locator('main.orders .bn-filterbar-trigger').click()
  const body = page.locator('.bn-filterbar-sheet-body')
  await expect(body).toBeVisible()
  return body
}

/** Close the Filters sheet: a first Escape may only close a pick list inside it. */
export async function closeFilters(page: Page): Promise<void> {
  const body = page.locator('.bn-filterbar-sheet-body')
  await page.keyboard.press('Escape')
  if (await body.isVisible()) await page.keyboard.press('Escape')
  await expect(body).toBeHidden()
}

/** Pick one option of a facet, through the Filters sheet. */
export async function pickFacet(page: Page, facet: string, option: RegExp): Promise<void> {
  const body = await openFilters(page)
  await body.getByRole('button', { name: new RegExp(`^${facet}`) }).click()
  await page.getByRole('listbox', { name: facet }).getByRole('option', { name: option }).click()
  await closeFilters(page)
}

/** Done buyers only: the Open pick comes off, then Done goes on. */
export async function showDoneOnly(page: Page): Promise<void> {
  await pickFacet(page, 'Show', /^Open/)
  await pickFacet(page, 'Show', /^Done/)
}

/** The default view, Open buyers only: the Done pick comes off, then Open goes on. */
export async function showOpenOnly(page: Page): Promise<void> {
  await pickFacet(page, 'Show', /^Done/)
  await pickFacet(page, 'Show', /^Open/)
}
