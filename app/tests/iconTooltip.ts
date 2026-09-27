import type { Locator } from '@playwright/test'

/** THE ONE WAY A TEST FINDS AN `IconButton`'s TOOLTIP, since round 3 portals it to `<body>`
 *  (`kit/index.tsx`, D288 — `#/inventory`'s first row). `button.querySelector('.bn-icon-tip')`
 *  can no longer reach it: the tip is a body-level sibling, not a DOM descendant, so a
 *  descendant locator finds nothing. `data-tip-id` on the control names the id `id` carries
 *  on the portalled span — this reads the attribute, then looks the id up globally. Async
 *  because the attribute read is: callers `await iconTip(btn)` in place of the old
 *  `btn.locator('.bn-icon-tip')`. */
export async function iconTip(control: Locator): Promise<Locator> {
  const id = await control.getAttribute('data-tip-id')
  if (id === null) throw new Error('iconTip: the control has no data-tip-id — is it an IconButton?')
  /* An attribute selector, not `#${id}`: `CSS.escape` is a browser global and this string is
   * built in the Node test process, which has none. An attribute selector needs no escaping
   * for the id's own characters (React's `useId()` produces one with colons in it). */
  return control.page().locator(`[id="${id}"]`)
}
