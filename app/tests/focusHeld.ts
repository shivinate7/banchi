import type { Page } from '@playwright/test'

/** THE ONE WAY A TEST READS WHICH ELEMENT HOLDS FOCUS, for the Mark sold / Undo swap in both the order walk and
 *  `#/inventory`. It returns the held element's class, so a case asserts the button that replaces the one pressed,
 *  or its tag when focus has dropped to the page (`BODY`). A caller reads it once the write has settled and never
 *  inside a retrying assertion: a button that takes focus and then loses it would pass a retry during the moment it
 *  holds it. */
export function heldFocus(page: Page): Promise<string> {
  return page.evaluate(() => document.activeElement?.getAttribute('class') ?? document.activeElement?.tagName ?? '')
}
