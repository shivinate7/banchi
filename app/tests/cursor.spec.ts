import { test, expect } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* WHAT A CONTROL SAYS TO THE POINTER, ASSERTED WHERE NOTHING ELSE COULD SEE IT.
 *
 * The owner's report, 2026-08-29: "I hate how my mouse doesn't change correctly upon what I'm
 * hovering." Measured, 41 of 65 control shapes were wrong — and `make design-check` was green
 * through every one of them, because until this file existed **nothing in `app/tests/` asserted
 * a cursor anywhere**. It would have stayed green through a total regression of the fix too.
 * That is the failure `base.css`'s own focus-ring comment warns about, and D50 is the entry.
 *
 * THE LARGEST CLASS WAS THE DISABLED STATE, WHICH IS WHY THIS FILE SPLITS ON IT. 30 of the 41
 * were controls that went on saying `pointer` while refusing the click, and 7 were text fields
 * still reading `text` while refusing a character. A sweep that accepts "pointer OR
 * not-allowed" for a button — the obvious way to write this — passes every one of them. So the
 * rule here is a FUNCTION of the element's state, never a set of acceptable answers.
 *
 * IT ASSERTS THE RULE, NEVER THE ROSTER. No selector list, no expected count per screen: it
 * walks what each route actually renders and classifies by tag, type and disabled state. A
 * pinned roster goes green on any later change that moves the defect somewhere else — and a
 * button added next month would simply not be in the list, which is the one failure a guard
 * written after a 41-defect sweep exists to prevent.
 *
 * AND THAT HAS TO HOLD FOR THE ROUTES, WHICH IT DID NOT UNTIL 2026-08-31. This paragraph was
 * written about controls, and four lines under it sat a hand-typed list of seven route hashes
 * that three later screens never reached. The block above `routesFromNav` tells it in full;
 * what belongs here is that the sentence was always meant to cover both. What this costs is that a control which does not render in
 * this worktree's empty store is not checked; what it buys is that a NEW control cannot be
 * missed. The floor below is what stops that trade going bad silently.
 *
 * OWNER AND FULFILLER ALIKE, DELIBERATELY. `docs/DESIGN.md`'s Fulfillment table has no row about
 * a cursor and this file asserts none of its floors — `app/tests/fulfillment.spec.ts` is that
 * table's instrument and is untouched. His screens are designed for touch, but touch is not the
 * only device that reaches them, and a mouse over his pull-confirm should say what a mouse over
 * the owner's says. Nothing here can weaken one of his constraints: a cursor is not a text size,
 * a tap target, a contrast ratio or a route.
 *
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is nine Python tests
 * at the Stop hook; this starts a browser. `make design-check` runs it.
 */

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
async function routesFromNav(page: import('@playwright/test').Page): Promise<string[]> {
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

type Found = {
  kind: 'click' | 'text' | 'skip'
  disabled: boolean
  cursor: string
  tag: string
  cls: string
  text: string
}

/* `pointer-events: none` IS SKIPPED, AND IT IS A REAL CASE RATHER THAN A CONVENIENCE. When a
 * control carries it the pointer never lands on the element, so the browser resolves the cursor
 * from whatever is UNDERNEATH — the computed value on the element is unobservable, and asserting
 * it would be asserting something no user can see. `BoxRuns.css`'s disabled link is the live
 * instance: its rule computes `not-allowed` and the operator sees the parent's arrow. Fixing
 * that means changing how that control is guarded rather than how it is styled, which is a
 * behaviour change and not this file's business. */
async function sweep(page: import('@playwright/test').Page): Promise<Found[]> {
  return page.evaluate(() => {
    const CLICK_INPUT = ['checkbox', 'radio', 'file', 'button', 'submit', 'reset', 'image', 'color', 'range']
    const TEXT_INPUT = ['text', 'search', 'number', 'email', 'password', 'tel', 'url', 'date', 'time']
    const out: Found[] = []
    const nodes = document.querySelectorAll<HTMLElement>(
      "button, select, textarea, input, a, label, [role='button']",
    )
    for (const el of Array.from(nodes)) {
      const box = el.getBoundingClientRect()
      if (box.width === 0 || box.height === 0) continue
      const cs = getComputedStyle(el)
      if (cs.pointerEvents === 'none' || cs.visibility === 'hidden') continue

      const tag = el.tagName
      const type = el instanceof HTMLInputElement ? el.type.toLowerCase() : ''
      const ariaOff = el.getAttribute('aria-disabled') === 'true'
      const nativeOff = 'disabled' in el && Boolean((el as HTMLInputElement).disabled)
      const disabled = ariaOff || nativeOff

      let kind: Found['kind'] = 'skip'
      if (tag === 'BUTTON' || tag === 'SELECT' || el.getAttribute('role') === 'button') kind = 'click'
      else if (tag === 'A') kind = el.hasAttribute('href') ? 'click' : 'skip'
      else if (tag === 'TEXTAREA') kind = 'text'
      else if (tag === 'INPUT') {
        if (CLICK_INPUT.includes(type)) kind = 'click'
        else if (TEXT_INPUT.includes(type) || type === '') kind = 'text'
      } else if (tag === 'LABEL') {
        /* A label is only a control when it OWNS a toggle: clicking the words checks the box, so
           the words have to say so. A label over a text field also does something — it moves the
           caret — and `text` is already the right promise there, which is why `base.css` leaves
           `.run-field` and `.pricing-field` alone and why this asserts nothing about them. */
        const owned = el.querySelector('input')
        const t = owned ? owned.type.toLowerCase() : ''
        kind = owned && ['checkbox', 'radio', 'file'].includes(t) ? 'click' : 'skip'
      }
      if (kind === 'skip') continue

      out.push({
        kind,
        disabled,
        cursor: cs.cursor,
        tag: tag + (type ? `[${type}]` : ''),
        cls: String(el.className || '').slice(0, 48),
        text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 32),
      })
    }
    return out
  })
}

/* THE RULE, IN ONE PLACE, SO THE TWO CASES BELOW CANNOT DISAGREE ABOUT IT. */
function expected(f: Found): string {
  if (f.disabled) return 'not-allowed'
  return f.kind === 'click' ? 'pointer' : 'text'
}

/* NOTHING HERE MAY REACH THE CAPTURE SERVER, AND THIS FILE'S OWN HEADER IS WHY IT MATTERS
   MOST HERE. It says the sweep costs "a control which does not render in this worktree's empty
   store" — but it registered no handlers at all, so in the main checkout the store it swept was
   the owner's 767 real cards and the number of controls it looked at was a property of which
   checkout ran it. The shared small store makes every screen draw the same populated controls
   in every tree, which is more than the empty answer and reproducible, unlike the other.

   MEASURED RATHER THAN ASSUMED, on this worktree 2026-09-06: 354 controls swept against the
   small store, 332 against the dead capture port this tree had before. The gain is where the
   store is — `#/inventory` 16 to 33, because the walk draws no rows and no search field over
   an empty store, `#/review` 17 to 21, and `#/fulfillment` 1 to 3. `#/gallery`'s 153 come off
   the build and move either way. `app/tests/shell.ts` carries the rest of the argument. */
sealEveryTest({ store: true })

test('every rendered control tells the pointer what it is', async ({ page }) => {
  /* THE ONE TEST IN THIS SUITE THAT LOADS EVERY SCREEN, AND THE ONLY ONE THAT ASKS THE REAL
     SERVER FOR ALL OF THEM. Both facts follow from what it is for and neither is a smell: a
     sweep that discovers controls cannot stub routes it has not been told about, and a roster
     read off the sidebar is a roster of every screen. So this case alone pays the whole module
     graph's cold Vite compile AND every screen's real fetches, while six other workers compile
     against the same dev server and the same single-threaded capture server behind it.
     Measured on this rig: 1.8s alone against a warm server, 41.4s alone against a cold one.

     THE RAISE IS FOR THE COLD COMPILE AND NOTHING ELSE, and it is not what was actually wrong —
     see `networkidle` below, which is the real fault and is fixed there rather than paid for
     here. Raising a budget WEAKENS NOTHING, the same distinction `playwright.config.ts` argues
     for its own `expect.timeout`: it does not change which routes are walked, which controls
     are classified, or the rule they are held to. It changes how long a true statement is given
     to become true, and a control saying `pointer` while disabled is still saying it at 60s. */
  test.setTimeout(60_000)

  const wrong: string[] = []
  let total = 0

  for (const route of await routesFromNav(page)) {
    await page.goto(`/${route}`)
    await settleFonts(page)
    /* BEST-EFFORT, AND NOW BOUNDED, WHICH IS THE WHOLE OF THE BUG THIS FILE SPENT TWO FULL
       `make design-check` RUNS FAILING ON. The `.catch(() => {})` already said this wait is a
       courtesy — let a screen's fetches land so the sweep classifies the controls they draw —
       but with no timeout of its own it inherits the test's, so a route that never goes idle
       does not fall through to the sweep, it eats the entire budget and reports as a timeout on
       the NEXT line. Instrumented under a real seven-worker run, `#/` alone burned 119.6s of a
       120s budget here and the sweep never reached route two: Home fires six unstubbed loads at
       a single-threaded capture server that six other workers are also queued against, and
       `networkidle`'s 500ms of quiet never arrives. Alone against a warm server the same route
       settles in 1.4s, which is why this only ever failed in the full suite.

       THE BOUND WEAKENS NOTHING AND WIDENS THE SWEEP. Nothing is asserted about the network
       here; what is asserted is below, and the `<main>` wait that follows still has the config's
       15s to become true. A route whose data never lands is now swept for whatever it did draw,
       rather than taking the other ten routes down with it — and this file's header already
       accepts that a control the empty store never renders is not checked. */
    await page.waitForLoadState('networkidle', { timeout: 2_000 }).catch(() => {})
    /* THE ORDER OF THESE TWO IS NOT ARBITRARY. `toHaveCount(0)` is satisfied by an element
       that has not rendered YET, so asking it first would pass vacuously on a slow mount and
       then be satisfied a second time by `main.no-such-view` itself, which is a `<main>`. So
       wait for the screen to draw, and only then ask which screen it was. */
    await expect(
      page.locator('main').first(),
      `${route} drew no <main> — a crashed screen, or a screen that rooted itself in a <div>`,
    ).toBeVisible()
    await expect(
      page.locator('main.no-such-view'),
      `${route} is drawn in the nav but resolves to nothing — is the row still in App.tsx's ROUTES?`,
    ).toHaveCount(0)

    const found = await sweep(page)
    total += found.length
    for (const f of found) {
      const want = expected(f)
      if (f.cursor !== want) {
        wrong.push(
          `${route}  ${f.tag} .${f.cls}${f.disabled ? ' [disabled]' : ''}` +
            `  says "${f.cursor}", should say "${want}"  ${f.text ? `— "${f.text}"` : ''}`,
        )
      }
    }
  }

  /* A FLOOR ON THE SWEEP ITSELF, WHICH THIS FILE ALREADY INVENTED FOR ITS ROSTER HARVEST AND
     NEEDS TWICE AS BADLY HERE. The screens draw their controls out of `shell.ts`'s shared
     fixture now, and a regression in that fixture — a payload gone short, a route stopped
     matching — leaves every screen on its empty state and turns the richest sweep in this
     suite into a loop over nothing. It would pass, instantly, forever: exactly the vacuous
     green the harvest's own floor exists to refuse, one level down.

     300 AGAINST A MEASURED 354, on this worktree 2026-09-06. Not a pin — the number moves with
     every control the product gains — but far enough below to survive ordinary drift and far
     enough above the 40-odd an all-empty store draws that no fixture regression can hide under
     it. */
  expect(total, 'the sweep classified almost nothing — are `shell.ts`\'s fixtures still populating every screen?')
    .toBeGreaterThan(300)

  expect(
    wrong,
    `${wrong.length} of ${total} controls say the wrong thing to the pointer:\n${wrong.join('\n')}`,
  ).toHaveLength(0)
})

/* THE RESPONSE ITSELF, ASSERTED AS A RULE OVER EVERY `:hover` RULE THE APP LOADED — which is
 * the half of D50 this file did not have. Everything above is about `cursor`, and the one case
 * below it about hover reaches exactly ONE element, `.search-field-box` on `#/gallery`. D50 is
 * titled for an interactive element's FEEDBACK; a guard that checks one control's border colour
 * is not holding that entry to its own name, and the owner's report of 2026-09-06 landed in the
 * gap: `.bn-brand`, the sidebar's rail toggle, painted a 109px hover slab in a single frame on
 * all ten routes while the nav links under it faded over 120ms. Every assertion in this file
 * was green through it, because none of them looks at time.
 *
 * MEASURED BEFORE IT WAS WRITTEN, by hovering all 315 controls the eleven routes draw and
 * letting the transition settle: 293 responded, 276 eased and 17 SNAPPED, across six classes in
 * five sheets. `base.css`'s response floor took that to 0 of 294 in one block.
 *
 * IT READS THE CSSOM RATHER THAN HOVERING, and that is the difference between a rule and a
 * roster one level down. Hovering finds only what this store happens to draw and costs ~100s at
 * one worker; walking `document.styleSheets` finds every `:hover` rule in every sheet whether or
 * not something renders it today, which is the same widening D50 recorded when it re-measured
 * its own reflow claim over "all 64 :hover rules in all 26 sheets" instead of over the routes a
 * browser drew. There are 164 of those rules now and 31 sheets; the count is not pinned here,
 * because the point is that the walk discovers them.
 *
 * THE FOUR PROPERTIES ARE THE FLOOR'S OWN FOUR, deliberately, so the guard and the guarantee
 * cannot drift apart. `transform` and `opacity` are outside both: mount animations own opacity,
 * and a transform is contained micro-motion a screen may want to time itself — `Codes.css`'s
 * 4px-to-7px arrow nudge is transitioned on its own rule and is not this rule's business.
 * `text-decoration` is outside because `base.css`'s own `a:hover` underline is an affordance
 * rather than a repaint, and easing it would look wrong.
 *
 * A SCREEN MAY STILL SAY `transition: none` AND THIS WILL FAIL IT, which is correct and is the
 * cheap exception D50 describes: an exception costs one rule and one comment saying why, and
 * this is what makes somebody write the comment. */
test('a control that answers the pointer eases into it', async ({ page }) => {
  test.setTimeout(60_000)

  /* THE FLOOR'S FOUR, NAMED ONCE. `background` and `border` are the shorthands a sheet actually
     writes; they set the longhand this asks about, so both spellings count as a repaint. */
  const REPAINT = ['background', 'background-color', 'border-color', 'border-top-color',
    'border-bottom-color', 'border-left-color', 'border-right-color', 'border', 'color',
    'box-shadow', 'outline-color']

  const offenders: string[] = []
  let rulesWalked = 0
  let elementsChecked = 0

  for (const route of await routesFromNav(page)) {
    await page.goto(`/${route}`)
    await settleFonts(page)
    await page.waitForLoadState('networkidle', { timeout: 2_000 }).catch(() => {})
    await expect(page.locator('main').first()).toBeVisible()

    const result = await page.evaluate((REPAINT) => {
      const bad: string[] = []
      let walked = 0
      let checked = 0

      /* MEDIA AND SUPPORTS BLOCKS ARE RECURSED INTO, because the phone's rules live in one and a
         hover rule that only exists under a breakpoint is still a hover rule. A cross-origin
         sheet throws on `.cssRules` — the font CDN is one — so the read is guarded and skipped
         rather than allowed to fail the case for a sheet this product does not own. */
      const collect = (list: CSSRuleList, out: CSSStyleRule[]) => {
        for (const r of Array.from(list)) {
          if (r instanceof CSSStyleRule) out.push(r)
          else if ('cssRules' in r) { try { collect((r as CSSGroupingRule).cssRules, out) } catch { /* opaque */ } }
        }
      }
      const rules: CSSStyleRule[] = []
      for (const sheet of Array.from(document.styleSheets)) {
        try { collect(sheet.cssRules, rules) } catch { /* cross-origin, not ours */ }
      }

      for (const rule of rules) {
        if (!rule.selectorText || !rule.selectorText.includes(':hover')) continue
        const repaints = REPAINT.filter((p) => rule.style.getPropertyValue(p) !== '')
        if (!repaints.length) continue
        walked++

        /* THE ELEMENT THE RULE PAINTS IS THE ONE THAT HAS TO CARRY THE TRANSITION, and for a
           descendant rule that is not the element carrying `:hover`. Dropping the pseudo-class
           turns `.a:hover .b` into `.a .b`, which selects exactly what the rule paints, and
           `.a:hover` into `.a`, which is the element itself. Both are what we must ask. */
        const rest = rule.selectorText.replace(/:hover/g, '')
        let targets: HTMLElement[] = []
        try { targets = Array.from(document.querySelectorAll<HTMLElement>(rest)) } catch { continue }

        for (const el of targets) {
          const b = el.getBoundingClientRect()
          if (b.width === 0 || b.height === 0) continue
          checked++
          const cs = getComputedStyle(el)
          /* THE ONE EXEMPTION IN THIS FILE, AND IT IS STATED RATHER THAN SPELLED AROUND.
             `app/eslint.config.js` bans splitting on a comma because v1 shredded a TCGplayer
             export that way, and it deliberately catches the regex form too — its own comment
             calls that "the same bug wearing a coat", which is right about a CSV. This is not
             one. `transition-property` and `transition-duration` are comma-separated CSS lists
             read back out of `getComputedStyle`, where the browser has already normalised the
             separator and no field can contain a comma or a quote. The two lists are also
             POSITIONAL — `durs[i]` is the duration of `props[i]` — so a parse that did not
             preserve order would answer the wrong question, which is the opposite of the CSV
             hazard rather than an instance of it. */
          // eslint-disable-next-line no-restricted-syntax -- a CSS list from getComputedStyle, not a CSV; see above
          const props = cs.transitionProperty.split(',').map((s) => s.trim())
          // eslint-disable-next-line no-restricted-syntax -- ditto, and positionally paired with `props`
          const durs = cs.transitionDuration.split(',').map((s) => s.trim())
          const eased = (want: string) => {
            const norm = want === 'background' ? 'background-color'
              : want === 'border' ? 'border-color'
              : want.startsWith('border-') && want.endsWith('-color') ? 'border-color'
              : want
            for (let i = 0; i < props.length; i++) {
              const p = props[i] ?? ''
              const d = durs[i % durs.length] ?? '0s'
              if (d === '0s' || d === '') continue
              if (p === 'all' || p === norm || p === want) return true
              if (norm === 'border-color' && p.startsWith('border-') && p.endsWith('-color')) return true
            }
            return false
          }
          const snapped = repaints.filter((p) => !eased(p))
          if (snapped.length) {
            bad.push(`${rule.selectorText}  repaints ${snapped.join(', ')} with no transition on ` +
              `${el.tagName.toLowerCase()}.${String(el.className || '').slice(0, 40)}`)
          }
        }
      }
      return { bad, walked, checked }
    }, REPAINT)

    rulesWalked += result.walked
    elementsChecked += result.checked
    for (const b of result.bad) if (!offenders.includes(`${b}`)) offenders.push(b)
  }

  /* THE SAME FLOOR THE SWEEP ABOVE KEEPS, FOR THE SAME REASON. A selector that stops matching,
     a sheet that stops loading, or a fixture regression that empties every screen would turn
     this into a walk over nothing — green, instantly, forever. Measured on this worktree
     2026-09-06 at 300 rule-element pairs; the floor is set well under it so ordinary drift does
     not trip it, and well over the handful an all-empty store would leave. */
  expect(elementsChecked, 'the walk checked almost nothing — are the stylesheets still loading?')
    .toBeGreaterThan(100)
  expect(rulesWalked, 'no repainting :hover rule was found at all — is the CSSOM read still valid?')
    .toBeGreaterThan(20)

  expect(
    offenders,
    `${offenders.length} hover rules repaint a control without easing it:\n${offenders.join('\n')}`,
  ).toHaveLength(0)
})

/* THE HOVER STATE THE OWNER GRANTED A TOKEN FOR, ASSERTED AS A CHANGE RATHER THAN AS A VALUE.
 * Pinning `rgb(107, 110, 115)` would go red the day the owner picks a different grey, which is
 * a token decision and not a regression. What must stay true is that the edge RESPONDS — a
 * field with no hover response at all is the defect D50 was granted to fix. */
test('a typed-into field darkens its edge under the pointer, and nothing moves', async ({ page }) => {
  /* ON `#/gallery`, AND THE ROUTE WAS CHOSEN BY MEASUREMENT AFTER TWO GUESSES MISSED. The
     screens draw their typed-into controls only once there is something to type against, so
     against this worktree's own empty store (D43) `#/inventory` renders no search field and
     `#/` renders no Box field — both first attempts failed on ABSENCE rather than on colour,
     which is a test reporting a defect that is not there. The gallery is what a route for this
     is: it renders components against the tokens without needing a store behind them, and it is
     already what `make screenshot` and step 6's own spec point at.

     RE-PROBED ACROSS ALL TEN ROUTES ON 2026-08-31, and the sentence that stood here has been
     rewritten rather than renumbered. It said "probed across all seven routes, the gallery is
     the only one drawing a `--field` edge at all" — the seven were the pinned roster this file
     no longer keeps, and the claim is no longer true either: `#/codes` (D70) draws that edge on
     a bare `input` AND on a bare `button`, which is a token question for D50 rather than a
     cursor one and is left alone here. What is still true, and is what this case actually
     needs, is that the gallery is the only route drawing a `.search-field-box` against an empty
     store. That is the measurement; the count of routes it was taken over is not load-bearing
     and is stated only so the next person knows what was walked.

     TWO ROUTES IN THAT SENTENCE MOVED ON 2026-09-03 and the measurement did not: `#/` is Home
     now and the Box field it names is on `#/capture`. Re-probed there, the gallery is still the
     only route drawing a `.search-field-box` with nothing in the store, which is the fact this
     case rests on. */
  await page.goto('/#/gallery')
  await settleFonts(page)
  await expect(page.locator('main.gallery')).toBeVisible()

  const field = page.locator('.search-field-box').first()
  await expect(field).toBeVisible()

  const before = await field.evaluate((el) => {
    const cs = getComputedStyle(el)
    const b = el.getBoundingClientRect()
    return { colour: cs.borderTopColor, w: cs.borderTopWidth, box: [b.width, b.height].join('x') }
  })

  await field.hover()
  const after = await field.evaluate((el) => {
    const cs = getComputedStyle(el)
    const b = el.getBoundingClientRect()
    return { colour: cs.borderTopColor, w: cs.borderTopWidth, box: [b.width, b.height].join('x') }
  })

  expect(after.colour, 'the edge must respond to the pointer').not.toBe(before.colour)

  /* NO REFLOW, WHICH IS THE HALF THAT COULD ACTUALLY HURT SOMEBODY. A hover that changes border
     width, padding or type size moves a target under a finger already travelling toward it —
     the review queue's recorded defect, reproduced on every screen at once. `border-color` is
     the only property these rules are allowed to touch. */
  expect(after.w, 'a hover may not change border width').toBe(before.w)
  expect(after.box, 'a hover may not resize the control').toBe(before.box)
})

/* THE FLOOR ITSELF, PROBED WITH ELEMENTS THIS TEST MAKES — AND THE SWEEP ABOVE IS WHY IT HAS TO
 * EXIST. That sweep was mutation-tested by deleting `base.css`'s entire disabled arm, which is
 * the rule covering 30 of the 41 defects D50 was written for, and it PASSED. The reason is not
 * subtle once seen: this worktree has its own empty store (D43), so no screen renders a disabled
 * control, so a sweep of what renders cannot see the largest class of the defect at all.
 *
 * A test that cannot fail is not coverage — this repo's own rule, and the sweep alone was
 * exactly that for the case that mattered most.
 *
 * SO THIS ASSERTS THE RULE ON ELEMENTS IT BUILDS, which is a different claim from the sweep's
 * and neither one subsumes the other. The sweep asks "does what this app actually draws say the
 * right thing", and catches a screen that overrides the floor wrongly. This asks "does the floor
 * answer correctly for every shape a control can take", and catches the floor being weakened,
 * reordered out of the cascade, or deleted. Bare elements with no component class are the point:
 * the floor is what is under test, so anything dressed in a screen's class would be testing that
 * screen instead.
 *
 * ON `#/gallery` FOR ONE REASON — `main.tsx` imports `base.css` for every route, so any route
 * would serve; the gallery is where this repo already puts a component rendered against the
 * tokens rather than against a store.
 *
 * THE LIMIT, NAMED SO A GREEN RUN IS READ FOR WHAT IT IS: between them these two cases cover the
 * floor completely and a screen's OWN rules only where that screen renders them. A per-file
 * override on a control this empty store never draws is unchecked by either. Closing that needs
 * fixtures for seven screens, which is a bigger thing than this file and has not been argued. */
const SHAPES: [html: string, want: string, why: string][] = [
  ['<button>x</button>', 'pointer', 'a button'],
  ['<button disabled>x</button>', 'not-allowed', 'a disabled button'],
  ['<button aria-disabled="true">x</button>', 'not-allowed', 'an aria-disabled button'],
  ['<select><option>x</option></select>', 'pointer', 'a select'],
  ['<select disabled><option>x</option></select>', 'not-allowed', 'a disabled select'],
  ['<input type="text">', 'text', 'a text field'],
  ['<input type="text" disabled>', 'not-allowed', 'a disabled text field'],
  ['<input type="number">', 'text', 'a number field'],
  ['<textarea></textarea>', 'text', 'a textarea'],
  ['<textarea disabled></textarea>', 'not-allowed', 'a disabled textarea'],
  ['<input type="checkbox">', 'pointer', 'a checkbox'],
  ['<input type="checkbox" disabled>', 'not-allowed', 'a disabled checkbox'],
  ['<input type="radio">', 'pointer', 'a radio'],
  ['<input type="file">', 'pointer', 'a file input'],
  ['<div role="button">x</div>', 'pointer', 'a div promoted to a control'],
  ['<label><input type="checkbox">words</label>', 'pointer', 'a label that owns a toggle'],
  /* THE DELIBERATE NON-CONTROL, AND THE ONE SHAPE ASSERTED NEGATIVELY. A label over a TEXT
     field moves the caret, and `text` is already the right promise — `base.css` leaves
     `.run-field` and `.pricing-field` alone for this reason, and a floor that promoted them
     would be making a false offer.

     `!pointer` rather than a value, because the value is the engine's business: this was first
     written as `auto` and Chromium answered `default`, since `auto` is what the property is SET
     to and `default` is what it COMPUTES to on a non-interactive element. Pinning either one
     asserts a fact about the browser instead of a fact about this product. What must be true is
     only that the words do not claim to be clickable. */
  ['<label><input type="text">words</label>', '!pointer', 'a label over a text field, deliberately not a control'],
]

test('the cursor floor answers for every shape a control can take', async ({ page }) => {
  await page.goto('/#/gallery')
  await settleFonts(page)
  await expect(page.locator('main.gallery')).toBeVisible()

  const results = await page.evaluate((shapes) => {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const out: { why: string; got: string; want: string; ok: boolean }[] = []
    for (const [html, want, why] of shapes) {
      host.innerHTML = html
      const el = host.firstElementChild as HTMLElement
      const got = getComputedStyle(el).cursor
      out.push({ why, want, got, ok: want.startsWith('!') ? got !== want.slice(1) : got === want })
    }
    host.remove()
    return out
  }, SHAPES)

  const wrong = results.filter((r) => !r.ok)
  expect(
    wrong,
    `the floor answers wrongly for ${wrong.length} of ${results.length} shapes:\n` +
      wrong
        .map((r) =>
          r.want.startsWith('!')
            ? `  ${r.why} says "${r.got}", which it must never say`
            : `  ${r.why} says "${r.got}", should say "${r.want}"`,
        )
        .join('\n'),
  ).toHaveLength(0)
})
