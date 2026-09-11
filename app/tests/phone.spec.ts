import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'

/* THE OWNER'S SCREENS AT A PHONE'S WIDTH, WHICH NOTHING IN THIS SUITE HAD EVER LOOKED AT.
 *
 * CLAUDE.md publishes two floors for this width and neither had a reader:
 *   "Look at it at 1440, 820 and 390 … No horizontal page scroll at 390."
 *   "Anything a thumb presses is 40px or more. The control-height tokens raise themselves under
 *    767px and on a coarse pointer, so do not hand-roll a mouse-sized control on a phone."
 *
 * WHY THE EXISTING SPECS COULD NOT SEE IT. `nav.spec.ts` scopes itself to `.bn-side` on purpose.
 * `cursor.spec.ts` harvests its routes from `.bn-side a.bn-nav-link`, which is `display: none`
 * below 768 — so that file cannot run here even in principle, and its own comment says the phone
 * drawer is a second copy it does not walk. Of the twenty specs in this directory only
 * `fulfillment.spec.ts` sets a phone viewport at all, and that is the Fulfiller's one route.
 * The owner-side shell had no test at any width.
 *
 * THE STATES ARE THE POINT. A sweep over routes alone finds three short controls; a sweep that
 * OPENS things finds twenty-five. The menus, the sheets, the palette, the hold panel and the
 * toast stack are where the kit's own controls actually appear, and a phone reaches all of them.
 * Every case below therefore opens something.
 *
 * THE HIT AREA IS THE MEASUREMENT, NOT THE BOX, and that is what makes this checkable without an
 * allow-list. `BoxBrowse`'s ticks draw at 22px and take the tap at 46 through an `::after` with a
 * negative inset; the composer's stage chips do the same. A box-only assertion calls both of
 * those failures and needs a list of names to forgive them — and a list of names is a list
 * somebody adds to. Probing the four cardinal points of the required 40px box answers the
 * question the floor is actually about: can a thumb landing 19px off-centre still press it.
 */

const PHONE = { width: 390, height: 844 }

/* NOTHING HERE MAY REACH THE CAPTURE SERVER. This spec registers no fixtures of its own, so it
   takes the shared small store. Above every hook, which `make docs-audit`'s `spec seal` row
   checks. */
sealEveryTest({ store: true, cards: 122 })

/** The floor, and the probe radius that answers it: a thumb landing 19px off the centre. */
const FLOOR = 40

/* Measured INSIDE the page, in one pass, because a round trip per control over ~300 controls a
   route is minutes of wall clock. Returns only what fails. */
const auditSource = (mode: Mode) => `(() => {
  const FLOOR = ${FLOOR}, r = FLOOR / 2 - 1
  const mode = '${mode}'
  const out = []
  const seen = new Set()
  /* WHEN SOMETHING IS OPEN OVER THE PAGE, ONLY THAT IS IN SCOPE. A scrim covers everything
     behind it, so a sweep of the whole document while the drawer is open reports the tab bar,
     the brand and every stage card as unpressable — which is true, and is the modal working.
     The first run of this file said exactly that, in five confident lines. */
  const over = document.querySelector('.bn-scrim') === null
    ? document
    : document.querySelector('.bn-cmdk, .bn-drawer, .bn-sheet, .bn-dialog') ?? document
  /* THE SHELL'S OWN FIXED CHROME IS NOT AN OBSTRUCTION. Content scrolls UNDER the top bar and
     the tab bar by design: .bn-shell-main pads its foot by the tab bar's height plus the safe
     area precisely so anything can be scrolled clear of them. A sticky bar INSIDE the scroller is
     a different thing and is deliberately still counted: the pricing screen's ship bar sat on
     top of Pick a run, with no padding anywhere that could have moved it.
     THE LIST IS NAMED RATHER THAN DERIVED, and that is the point. "Anything sticky" would excuse
     the ship bar, which is the case this file exists to catch; "anything fixed" would miss the
     kit sheet's own index strip, which is sticky. Three strips scroll content under themselves
     on purpose and each is written here: the phone's top bar, its tab bar, and #/gallery's
     index. A fourth is a deliberate edit. */
  const chrome = (n) => n !== null && n.closest('.bn-topbar, .bn-tabbar, .kit-index') !== null
  for (const el of over.querySelectorAll('button, a[href], input, select, textarea, summary, [role="button"]')) {
    // A checkbox's own box is 16px by design; the label that wraps it is the target.
    const t = el.closest('label') ?? el
    const box = t.getBoundingClientRect()
    if (box.width === 0 || box.height === 0) continue
    if (el.closest('[aria-hidden="true"]')) continue
    if (getComputedStyle(t).visibility === 'hidden') continue
    const cx = box.left + box.width / 2, cy = box.top + box.height / 2
    // Off-screen or hard against an edge: the probe would leave the viewport and elementFromPoint
    // answers null, which is not a fact about the control.
    if (cx < r || cy < r || cx > innerWidth - r || cy > innerHeight - r) continue
    /* CLIPPED BY A SCROLLER IS NOT COVERED BY A CONTROL. The palette's list is a 50vh scroller,
       and a row near its fold is real ordinary scroll behaviour — not a neighbour crowding it —
       so a PROBE that falls outside the scroller's own box is excluded rather than counted as a
       miss. A whole-row skip on the CENTRE alone is not enough: a row whose centre sits just
       inside the fold can still have its lower probe land past it, on the chrome below the
       scroller (the palette's own footer, in one measured case), which reads as a miss on a row
       that is mostly visible and fully reachable one scroll-line down. Anything whose centre is
       outside its nearest scrolling ancestor is still skipped outright — that row is not
       rendered where a person would look for it at all. */
    let clip = t.parentElement
    while (clip !== null && clip !== document.body) {
      const o = getComputedStyle(clip).overflowY
      if (o === 'auto' || o === 'scroll') break
      clip = clip.parentElement
    }
    let clipBox = null
    if (clip !== null && clip !== document.body) {
      const c = clip.getBoundingClientRect()
      if (cy < c.top || cy > c.bottom || cx < c.left || cx > c.right) continue
      clipBox = c
    }
    const owns = (n) => n !== null && (t.contains(n) || n.contains(t) || chrome(n))
    /* BEHIND THE CHROME IS SCROLLED AWAY, NOT CROWDED (D139), and this is the third exclusion
       of the same kind as the two above it: off-screen, clipped by a scroller, and now under
       the shell's own fixed bars. A control whose OWN CENTER is painted over by the top bar or
       the tab bar is not somewhere a person is looking — it has scrolled under the chrome, and
       every probe around it is measuring the chrome rather than the control.

       The chrome() test below already excuses a single probe that lands on a bar; what it could
       not see is the control ITSELF sitting under one, where the probes that happen to land on
       a screen control instead of on chrome are counted as misses. That is what produced the
       long-running #/inventory failure this exclusion was written for, and it took two attempts
       to find because the number it reports is so plausible: "misses 1 of 4 probes" reads as a
       control crowded by one neighbour.

       MEASURED, by reproducing the CI position locally rather than reasoning about it. The
       queued notice's "Open the review queue" link at top=37: left and right probes hit
       header.bn-topbar, the top probe hits span.bn-topbar-wordmark, the bottom probe hits
       button.browse-boxchip — the screen's own sticky box chip, pinned under the bar. Three
       misses excused as chrome, one counted, and the center itself resolving to
       header.bn-topbar. At rest the same link sits at top=576 with all four probes clean.

       WHAT THIS REPLACES IS A CSS FIX THAT COULD NOT HAVE WORKED. The link takes its floor from
       an ::after with a negative inset, and the previous attempt widened that inset from -12px
       to -16px on a font-metric theory; its own commit message records that the wider inset
       applied correctly on CI and the job failed identically. No inset reaches a hit area that
       a fixed bar is painted over.

       IT CANNOT HIDE A REAL DEFECT, which is the test any exclusion here has to pass. At rest
       no owner control is painted over by a fixed bar — if one were, that is a louder bug than
       a thumb floor and belongs to whatever put it there. Box mode is untouched, so a control
       that is genuinely too small is still caught wherever it sits. */
    const center = document.elementFromPoint(cx, cy)
    if (center !== null && chrome(center) && !t.contains(center) && !center.contains(t)) continue
    const inClip = (x, y) => clipBox === null || (x >= clipBox.left && x <= clipBox.right && y >= clipBox.top && y <= clipBox.bottom)
    const probeNames = [['left', -r, 0], ['right', r, 0], ['top', 0, -r], ['bottom', 0, r]]
    const hitDetail = probeNames
      .filter(([, dx, dy]) => inClip(cx + dx, cy + dy))
      .map(([name, dx, dy]) => {
        const n = document.elementFromPoint(cx + dx, cy + dy)
        return { name, x: Math.round(cx + dx), y: Math.round(cy + dy), tag: n ? n.tagName.toLowerCase() + (n.className ? '.' + (n.className + '').split(' ')[0] : '') : null, owns: owns(n) }
      })
    const misses = hitDetail.filter((h) => !h.owns).length
    // rounded, because a 39.6px control reports 40 and a floor nobody can see is a floor nobody fixes
    const small = Math.round(box.width) < FLOOR || Math.round(box.height) < FLOOR
    const covered = !owns(document.elementFromPoint(cx, cy))
    const fails = mode === 'box' ? small : misses > 0
    if (!fails) continue
    const cls = (t.className + '').split(' ').filter(Boolean)
    const key = t.tagName.toLowerCase() + (cls.length ? '.' + cls[0] : '')
    if (seen.has(key)) continue
    seen.add(key)
    const label = (el.getAttribute('aria-label') ?? t.textContent ?? '').trim().replace(/\\s+/g, ' ').slice(0, 40)
    out.push({ key, w: Math.round(box.width), h: Math.round(box.height), misses, covered, label })
  }
  return out
})()`

type Short = { key: string; w: number; h: number; misses: number; covered: boolean; label: string }

/* TWO PROPERTIES, AND THE KIT SHEET CAN ONLY ANSWER ONE OF THEM.
 *
 * ON AN OPERATING SCREEN the question is whether a thumb landing 19px off centre still lands on
 * the control. That is a fact about the control AND ITS NEIGHBOURS, and both halves matter: it is
 * what caught the ship bar sitting on Pick a run, and what proves a 22px tick with a negative-
 * inset pad really does answer at 46. Crowding counts here, because two controls 8px apart are
 * two controls a thumb cannot tell apart.
 *
 * ON `#/gallery` it cannot be asked. That page exists to draw specimens side by side so they can
 * be compared, so every probe lands on the next specimen and the assertion would demand 12px of
 * air between things whose whole job is to sit together. What CAN be asked there is the box —
 * CLAUDE.md's floor verbatim, 40px in both dimensions — and that is the question worth asking of
 * a component sheet, because it is the one surface in the product that draws every kit control.
 * Measured: with the sheet swept for the box, deleting `.bn-check`'s floor from `kit.css` turns
 * this file red. With it swept for the probe, it does not. */
type Mode = 'probe' | 'box'



/* THE WHOLE PAGE, A SCREEN AT A TIME. A control is only measurable where it is DRAWN, and
   `elementFromPoint` answers about the viewport — so a single pass at the top of a route measures
   the first 844px of it and reports the rest as clean. `#/gallery` is thirteen thousand pixels
   long: its checkbox sits at y=13124, and with one pass this file stayed green through three
   mutations that deleted kit floors outright. Scroll, measure, repeat. */
async function sweep(page: Page, where: string, mode: Mode = 'probe'): Promise<string[]> {
  const found: string[] = []
  const seen = new Set<string>()
  const height = await page.evaluate(() => window.innerHeight)
  let y = 0
  for (let step = 0; step < 40; step++) {
    for (const line of await audit(page, where, mode)) {
      const key = line.replace(/ — ".*$/, '')
      if (seen.has(key)) continue
      seen.add(key)
      found.push(line)
    }
    const next = await page.evaluate((dy) => {
      const before = window.scrollY
      window.scrollBy(0, dy)
      return { before, after: window.scrollY }
    }, height * 0.9)
    if (next.after <= next.before) break
    y = next.after
    await page.waitForTimeout(120)
  }
  void y
  return found
}

async function audit(page: Page, where: string, mode: Mode): Promise<string[]> {
  const short = (await page.evaluate(auditSource(mode))) as Short[]
  const lines: string[] = []
  for (const s of short) {
    const name = s.label === '' ? '' : ` — "${s.label}"`
    lines.push(
      s.covered
        ? `${where}: ${s.key} draws ${s.w}x${s.h} and its centre is covered — it cannot be pressed at all${name}`
        : mode === 'box'
          ? `${where}: ${s.key} draws ${s.w}x${s.h}, under the ${FLOOR}px floor${name}`
          : `${where}: ${s.key} draws ${s.w}x${s.h} and misses ${s.misses} of 4 probes at ${FLOOR / 2 - 1}px — its hit area does not reach the floor${name}`,
    )
  }
  return lines
}

async function overflow(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
}

/* THE ROUTES COME OFF THE PHONE'S OWN DRAWER, never a hand-typed list of hashes. `cursor.spec.ts`
   records what a typed list costs: a sweep over "every route" silently walks the routes somebody
   remembered. The drawer is the phone's nav, so it is the phone's roster. */
async function phoneRoutes(page: Page): Promise<string[]> {
  await page.goto('/')
  await page.getByText('More', { exact: true }).click()
  await expect(page.locator('.bn-drawer')).toBeVisible()
  const hrefs = await page.locator('.bn-drawer .bn-nav a.bn-nav-link').evaluateAll((els) =>
    els.map((el) => (el as HTMLAnchorElement).getAttribute('href') ?? '').filter((h) => h.startsWith('#/')))
  expect(hrefs.length, 'the drawer drew no nav links — the harvest is broken, not the app').toBeGreaterThan(5)
  /* AND THE KIT SHEET, WHICH THE DRAWER DELIBERATELY DOES NOT HOLD. `#/gallery` is `OFF_NAV` and
     reachable from the palette only, so a roster taken off the nav misses it — and it is the one
     screen that draws EVERY kit component on purpose, which makes it the only surface where a
     kit-level floor can be caught at all. Measured: with it out of this list, deleting
     `.bn-check`'s floor from `kit.css` left all four cases in this file green, because the two
     screens that draw a check need a loaded run to draw one. */
  hrefs.push('#/gallery')
  /* CLOSE IT AGAIN, AND THIS IS NOT TIDINESS. The drawer's scrim covers the page, so every probe
     below would land on `.bn-scrim` and every control on every route would be reported as
     covered — which is what the first run of this file said, in five confident lines about the
     tab bar and the brand. */
  await page.keyboard.press('Escape')
  await expect(page.locator('.bn-drawer')).toHaveCount(0)
  return hrefs
}

test('every owner screen holds the thumb floor at 390, and none scrolls sideways', async ({ page }) => {
  await page.setViewportSize(PHONE)
  const routes = await phoneRoutes(page)
  const failures: string[] = []
  for (const hash of routes) {
    await page.goto(hash)
    await page.waitForTimeout(400)
    failures.push(...(await sweep(page, hash, hash === '#/gallery' ? 'box' : 'probe')))
    const over = await overflow(page)
    expect(over, `${hash} scrolls sideways by ${over}px at 390 — CLAUDE.md: "No horizontal page scroll at 390."`).toBeLessThanOrEqual(0)
  }
  expect(failures, failures.join('\n')).toEqual([])
})

/* THE SHELL'S OWN SURFACES, which belong to no screen and so were in no spec's scope. The palette
   is the only way to `#/gallery` on a phone and the fastest way to the six screens behind More;
   its field measured 24px and its rows 37 before D117. */
/* THE EXCLUSION ABOVE, PROVED BY SETTING UP THE CASE IT EXISTS FOR (D139). Without a test of
   its own it is a `continue` anybody can delete and every screen stays green — which is exactly
   how the thing it fixes survived two attempts.

   IT ASSERTS ITS OWN SETUP FIRST, and that is the half that matters: a guard that cannot see
   its subject passes for the wrong reason. If the queued notice does not render, or the scroll
   does not put it under the bar, this test says so instead of reporting a clean sweep. */
test('a control scrolled under the chrome is not reported as crowded (D139)', async ({ page }) => {
  await page.setViewportSize(PHONE)
  /* THE SCREEN IS FOUND, NOT NAMED. A hand-typed route goes stale silently — `route rosters`
     blocks a commit over exactly that — and the subject here is the QUEUED NOTICE rather than
     any particular screen, so the honest way to reach it is to walk the nav and stop at the
     screen that draws one. If the notice moves, this test follows it. */
  const routes = await phoneRoutes(page)
  let where: string | null = null
  for (const hash of routes) {
    await page.goto(hash)
    await page.waitForTimeout(400)
    if ((await page.locator('.browse-queued .bn-notice a').count()) > 0) {
      where = hash
      break
    }
  }
  expect(where, 'no screen drew a queued-card notice, so this test proves nothing').not.toBeNull()

  const top = await page.evaluate(() => {
    const a = document.querySelector('.browse-queued .bn-notice a')
    if (a === null) return null
    window.scrollBy(0, a.getBoundingClientRect().top - 37)
    return Math.round(a.getBoundingClientRect().top)
  })
  expect(top, 'the queued notice never rendered, so this test proves nothing').not.toBeNull()
  expect(top, 'the link did not land under the top bar, so the case under test is not set up')
    .toBeLessThan(50)

  const center = await page.evaluate(() => {
    const a = document.querySelector('.browse-queued .bn-notice a')
    if (a === null) return null
    const b = a.getBoundingClientRect()
    const n = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2)
    return n === null ? null : n.className + ''
  })
  expect(center ?? '', 'the chrome is not painted over the link, so the exclusion is not exercised')
    .toContain('bn-topbar')

  expect(
    await sweep(page, where as string),
    'a control the shell has scrolled under its own fixed bar is scrolled away, not crowded',
  ).toEqual([])
})

test('the phone shell holds the floor: the drawer, the palette and the tab bar', async ({ page }) => {
  await page.setViewportSize(PHONE)
  await page.goto('/')

  const failures: string[] = []
  failures.push(...(await sweep(page, 'tab bar')))

  await page.getByText('More', { exact: true }).click()
  await expect(page.locator('.bn-drawer')).toBeVisible()
  await page.waitForTimeout(300)
  failures.push(...(await sweep(page, 'drawer')))

  await page.keyboard.press('Escape')
  await page.keyboard.press('Meta+k')
  await expect(page.locator('.bn-cmdk')).toBeVisible()
  await page.waitForTimeout(300)
  failures.push(...(await sweep(page, 'palette')))

  expect(failures, failures.join('\n')).toEqual([])
})

/* THE STATES A ROUTE RENDER NEVER REACHES. Each of these is a surface a thumb opens, and each
   draws kit controls that a route sweep cannot see. */
test('the sheets and menus a phone opens hold the floor too', async ({ page }) => {
  await page.setViewportSize(PHONE)
  const failures: string[] = []

  /* THE TWO SCREENS ARE PICKED OUT OF THE HARVEST, NOT TYPED. `make docs-audit`'s `route
     rosters` row refuses a spec that pins three or more hashes by hand, and it is right to: a
     list of screens somebody typed does not go stale loudly, it goes green. The drawer already
     told this file every owner route; these two are the ones with a sheet worth opening. */
  const routes = await phoneRoutes(page)
  const find = (tail: string) => {
    const hit = routes.find((h) => h.endsWith(tail))
    expect(hit, `no route ending ${tail} in the drawer's own roster`).toBeDefined()
    return hit as string
  }

  await page.goto(find('/inventory'))
  await page.waitForTimeout(600)
  const chip = page.locator('.browse-boxchip')
  if (await chip.count()) {
    await chip.click()
    await expect(page.locator('.browse-railsheet')).toBeVisible()
    await page.waitForTimeout(400)
    failures.push(...(await sweep(page, "inventory's box sheet")))
    // the ticks draw at 22px and take the tap at 46 through a negative-inset `::after` — the
    // probe is what tells those apart from a genuinely small control
    await page.keyboard.press('Escape')
  }

  await page.goto(find('/runs'))
  await page.waitForTimeout(600)
  const identify = page.getByRole('button', { name: /Identify a box/i }).first()
  if (await identify.count()) {
    await identify.click()
    await page.waitForTimeout(500)
    failures.push(...(await sweep(page, "runs' composer sheet")))
  }

  expect(failures, failures.join('\n')).toEqual([])
})
