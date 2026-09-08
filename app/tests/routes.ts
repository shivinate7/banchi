import { expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'

/* THE ROUTE ROSTER, DISCOVERED RATHER THAN TYPED, FOR EVERY SPEC THAT SWEEPS THE OWNER'S APP.
 *
 * Moved out of `cursor.spec.ts` on 2026-09-07 when `wide.spec.ts` needed the same harvest at
 * the other end of the width ladder (D122). It lives beside `fontsReady.ts` rather than inside
 * `shell.ts`, whose one argument is the capture-port seal and whose map entry opens "one call,
 * `sealEveryTest()`" — a route harvester there blunts both.
 *
 * THE THREE GUARDS BELOW ARE THE ANTI-VACUITY CONTRACT, and duplicating them in each sweeping
 * spec is how two copies of one invariant drift. There is exactly one copy, and every caller
 * gets it.
 *
 * It cannot run below 768: `.bn-side a.bn-nav-link` is `display: none` there, which is why
 * `phone.spec.ts` harvests its own roster from the phone chrome instead. */

/* THE ROSTER IS DERIVED FROM `App.tsx`'S OWN TABLE, AND UNTIL 2026-08-31 IT WAS PINNED HERE —
 * which is the failure the header above spends a paragraph warning about, committed in this
 * file, four lines under the warning. Seven hashes were typed out by hand on 2026-08-30; D69
 * added `#/orders` and `#/shipping` the same day and D70 added `#/codes`, and none of the
 * three was added here. Three whole screens were swept by nothing, `make design-check` was
 * green through all of them, and the defect the sweep found the moment they were included was
 * the exact class D50 was written for — a disabled control still saying something other than
 * `not-allowed`. A pinned roster does not go stale loudly; it goes green.
 *
 * SO THE HASHES COME OFF THE NAV, WHICH IS `ROUTES` RENDERED. `App.tsx` builds that strip by
 * mapping the same table it routes from — one table, deliberately, so the chrome and the
 * render cannot disagree — so every route the chrome offers has a link in it and a route added
 * next month arrives here with no edit to this file. The two routes the chrome does NOT offer
 * are accounted for in the block above `routesFromNav`. That is the same claim the sweep makes about
 * controls, applied one level up: discover them, never be handed them.
 *
 * WHAT IS ASSERTED PER ROUTE IS THE ARRIVAL, not a per-route selector, because a selector list
 * is the roster again in a second column. `App.tsx` renders `main.no-such-view` for a hash it
 * does not recognise, so its ABSENCE says the route resolved, and a visible `<main>` says the
 * screen drew. Between them they catch an unregistered route, a renamed hash and a crashed
 * screen — everything the old view column caught — and they stay quiet about a store with
 * nothing in it. That last part is why a control COUNT is not the instrument, and this file
 * tried a count first: the floor was three controls per route, on the reasoning that a route
 * drawing nothing has crashed, and `#/fulfillment` against an empty store legitimately draws
 * one. Emptiness and breakage are different facts and a count cannot tell them apart.
 *
 * EVERY ROUTE DRAWS A `<main>`, which is a real rule of this app and not a convenience for
 * this test. It was true of nine screens and false of `#/codes`, which rooted itself in a
 * `<div>` — so that route had no main landmark at all while the nav was on screen, and a
 * screen reader offered no way past the links. `Codes.tsx` is a `<main>` now. Asserting the
 * rule rather than exempting the exception is the same choice the disabled arm makes below.
 *
 * `#/fulfillment` IS REACHED BY THE HARVEST AND DRAWS NO NAV ITSELF, which is fine and worth
 * saying: the sidebar is read once, on `#/`, and his route is a link in it like every other.
 * Nothing here renders his chrome or asserts one of his floors — see the header.
 *
 * RE-POINTED AT THE BANCHI SIDEBAR, 2026-09-03, AND THE HARVEST HAD TO WIDEN TO KEEP WHAT IT
 * HAD. The rebuild moved the strip along the top into a collapsible sidebar, made `#/` Home
 * and moved capture to `#/capture` — all of which this reads off the markup and none of which
 * is a change to what is asserted. What IS a change: the Fulfiller's link and the kit gallery
 * are no longer inside `<nav>`. His now sits in the sidebar's foot, so the harvest takes every
 * `.bn-nav-link` in the sidebar rather than only the ones the `<nav>` holds — otherwise this
 * file would have quietly stopped sweeping the one persona its header spends a paragraph
 * insisting on. The gallery has left the chrome altogether and is reached from the command
 * palette, so it is named below: it is where this repo renders every control shape against the
 * tokens, and a sweep that dropped it would have lost the richest route it walks. Naming ONE
 * route is not the pinned roster this file's header refuses — the roster is still discovered,
 * and a screen added to the sidebar next month is still swept with no edit here. */
export async function routesFromNav(page: Page): Promise<string[]> {
  await page.goto('/#/')
  await settleFonts(page)
  await expect(page.locator('main.home'), 'Home is the way in').toBeVisible()

  /* EVERY LINK THE SIDEBAR DRAWS, `<nav>` OR FOOT. The phone drawer builds a second copy of
     the same list from the same table, and it is not mounted here — scoping to `.bn-side`
     keeps this reading one of them rather than depending on which. */
  const hashes = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLAnchorElement>('.bn-side a.bn-nav-link')).map(
      (a) => a.getAttribute('href') ?? '',
    ),
  )

  /* THE HARVEST IS GUARDED, because a selector that matches nothing would turn this whole
     sweep into a loop over an empty list — green, instantly, forever. That is a test that
     cannot fail, which this file's own synthetic case exists to say is not coverage. A FLOOR
     rather than a count: it fails loudly when the sidebar stops rendering or is renamed, and
     it cannot go stale in the direction that matters, since a route ADDED still gets swept. */
  expect(hashes.length, 'the sidebar rendered no links — is `.bn-side a.bn-nav-link` still it?')
    .toBeGreaterThan(3)
  expect(hashes, 'Home must be in the sidebar the roster is read from').toContain('#/')

  /* AND THE HARVEST STILL REACHES PAST THE `<nav>`, asserted as the structural fact rather
     than by naming his hash — a route named here is a roster of one, and this file's whole
     argument is that a roster goes green when it goes stale. The Fulfiller's link is the only
     `.bn-nav-link` the sidebar draws outside `<nav>`; if it moves back inside, or out of the
     sidebar altogether, this says so instead of the sweep quietly shrinking by a persona. */
  const outsideNav = await page.evaluate(
    () =>
      Array.from(document.querySelectorAll('.bn-side a.bn-nav-link')).filter(
        (a) => a.closest('nav') === null,
      ).length,
  )
  expect(outsideNav, 'the sidebar foot drew no link — the Fulfiller has left the sweep').toBe(1)

  /* `#/gallery` IS NAMED, and it is the one route here that is not discovered. The rebuild took
     it out of the chrome — it is reached from the command palette now — and it is where this
     repo renders every control shape against the tokens: 169 of the 418 elements this sweep
     looks at are on it. Dropping it to keep the roster purely derived would have halved the
     coverage of a file written after a 41-defect sweep. One named route beside a discovered
     list is not the pinned roster the header refuses: a screen added to the sidebar next month
     is still swept with no edit here. */
  return [...hashes, '#/gallery']
}
