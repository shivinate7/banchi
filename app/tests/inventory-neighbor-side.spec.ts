// Protects: a card at a box's end says which side its one neighbor is on, and never reads as the other side's.
// Governs: D58, D260
import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'
import type { Place, PlaceNeighbor } from '../src/types'

sealEveryTest({ store: true, cards: 4 })

/* A lone neighbor keeps its side: the first card says "Next: X", the last says "Previous: X". */
const side = (name: string): PlaceNeighbor => ({ name, index: 1 }) as PlaceNeighbor
const at = (prev: string | null, next: string | null): Place =>
  ({ located: true, neighbors: { prev: prev && side(prev), next: next && side(next) } }) as unknown as Place

/* `server.ts` reads `import.meta.env`, so it loads through the dev server, not node. */
test('first, last and middle card each say which side', async ({ page }) => {
  await page.goto('/')
  const say = (p: Place) =>
    page.evaluate(async (pl) => (await import('/src/server.ts' as string)).placeSentence(pl), p)
  expect(await say(at(null, 'Shard of Undoing'))).toBe('Next: Shard of Undoing (first in the box)')
  expect(await say(at('Mantine', null))).toBe('Previous: Mantine (last in the box)')
  expect(await say(at('Mantine', 'Shard of Undoing'))).toBe('Position: Mantine / Shard of Undoing')
})
