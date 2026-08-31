import { test, expect } from '@playwright/test'
import { settleFonts } from './fontsReady'

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
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is seven Python tests
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
 * render cannot disagree — so every registered route has a link in it and a route added next
 * month arrives here with no edit to this file. That is the same claim the sweep makes about
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
 * saying: the strip is read once, on `#/`, and his route is in the owner's table like every
 * other. Nothing here renders his chrome or asserts one of his floors — see the header. */
async function routesFromNav(page: import('@playwright/test').Page): Promise<string[]> {
  await page.goto('/#/')
  await settleFonts(page)
  await expect(page.locator('main.capture'), 'the capture screen is the way in').toBeVisible()

  const hashes = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLAnchorElement>('nav.app-nav a.app-nav-link')).map(
      (a) => a.getAttribute('href') ?? '',
    ),
  )

  /* THE HARVEST IS GUARDED, because a selector that matches nothing would turn this whole
     sweep into a loop over an empty list — green, instantly, forever. That is a test that
     cannot fail, which this file's own synthetic case exists to say is not coverage. A FLOOR
     rather than a count: it fails loudly when the nav stops rendering or is renamed, and it
     cannot go stale in the direction that matters, since a route ADDED still gets swept. */
  expect(hashes.length, 'the nav rendered no links — is `nav.app-nav a.app-nav-link` still it?')
    .toBeGreaterThan(3)
  expect(hashes, 'the capture screen must be in the strip the roster is read from').toContain('#/')
  return hashes
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

test('every rendered control tells the pointer what it is', async ({ page }) => {
  const wrong: string[] = []
  let total = 0

  for (const route of await routesFromNav(page)) {
    await page.goto(`/${route}`)
    await settleFonts(page)
    await page.waitForLoadState('networkidle').catch(() => {})
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

  expect(
    wrong,
    `${wrong.length} of ${total} controls say the wrong thing to the pointer:\n${wrong.join('\n')}`,
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
     and is stated only so the next person knows what was walked. */
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
