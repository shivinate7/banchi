import { test, expect } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { routesFromNav } from './routes'
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
 * browser drew. There are 161 of those rules now and 31 sheets — it was 164 when this was
 * written and D110 deleted three dark-only overrides the same day; the count is not pinned here,
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

        /* A BACKGROUND *IMAGE* IS NOT ANIMATABLE, AND THIS ARM EXISTS BECAUSE THE CHECK BELOW
           WAVED ONE THROUGH. `background` is a shorthand: a rule setting it to a gradient sets
           `background-image`, and interpolation from `none` to a gradient is DISCRETE, so the
           paint lands in one frame no matter what the transition says. The `eased()` test maps
           the shorthand to `background-color`, finds that transitioned, and passes — which is
           exactly what happened to the first draft of `.bn-nav-link[aria-current='page']:hover`
           on 2026-09-07. It snapped, this file was green, and only a mid-transition sample
           caught it. A guard that cannot see the property that actually changed is the same
           class of hole as a roster that has stopped listing a route. */
        const bg = rule.style.getPropertyValue('background') + ' ' +
                   rule.style.getPropertyValue('background-image')
        if (/gradient|url\(|image-set/i.test(bg)) {
          bad.push(`${rule.selectorText}  paints a background IMAGE on hover — ` +
            `\`background-image\` interpolates discretely, so this lands in one frame however it ` +
            `is transitioned. Composite the layer with an inset \`box-shadow\` instead.`)
          continue
        }

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

/* THE PRESS, IN TWO CASES, BECAUSE THE FLOOR AND THE SCREENS CAN FAIL DIFFERENTLY — the same
 * split the cursor half of this file already makes, and for the same reason. The sweep asks
 * whether what the product draws obeys the rule; the floor case asks whether the rule answers
 * correctly for every shape a control can take. Neither subsumes the other.
 *
 * D50 DECLINED `:active` ON 2026-08-29 AND THE OWNER REOPENED IT ON 2026-09-06. Measured over
 * the 311 enabled controls the eleven routes draw: 121 pressed and 190 did not, the largest
 * silent group being every `.bn-nav-link` in the sidebar — this product's primary navigation —
 * and `.bn-brand`, which was therefore dead to the pointer and to the finger at once. */

/* THE VOCABULARY IS SPLIT ON PURPOSE AND THIS IS WHAT KEEPS IT SPLIT: `translate` is the
 * product's 1px dip and `transform: scale()` is a screen's own emphasis. They are different
 * properties so they COMPOSE — which is the only reason a press floor could be written at all
 * without destroying the one control that carries a rest transform.
 *
 * A screen that spells the dip as `transform: translateY(1px)` is not merely off-style, it
 * DOUBLES the floor to 2px, and it does so silently. Six rules were spelling it that way when
 * the floor landed and all six were moved onto it. This is the rule that stops a seventh, and
 * `translateY(0)` stays legal because that is a control CANCELLING a hover lift rather than
 * declaring a dip — five rules do exactly that and are correct. */
test('no screen spells the press dip as a transform — the floor owns it', async ({ page }) => {
  await page.goto('/#/gallery')
  await settleFonts(page)
  await expect(page.locator('main.gallery')).toBeVisible()

  const found = await page.evaluate(() => {
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
    const bad: string[] = []
    let walked = 0
    for (const rule of rules) {
      if (!rule.selectorText?.includes(':active')) continue
      walked++
      const tf = rule.style.getPropertyValue('transform')
      if (!tf) continue
      /* `translateY(0)` and `translate(…, 0)` cancel a lift and are allowed; any NONZERO
         vertical offset is the floor's job being done twice. */
      const m = tf.match(/translateY\(\s*(-?[\d.]+)([a-z%]*)\s*\)/i)
      if (m && parseFloat(m[1] ?? '0') !== 0) {
        bad.push(`${rule.selectorText}  spells the dip as \`transform: ${tf.trim()}\` — ` +
          `that doubles base.css's press floor. Keep the scale, drop the translateY.`)
      }
    }
    return { bad, walked }
  })

  expect(found.walked, 'no `:active` rule was found at all — is the CSSOM read still valid?')
    .toBeGreaterThan(10)
  expect(
    found.bad,
    `${found.bad.length} rules double the press floor:\n${found.bad.join('\n')}`,
  ).toHaveLength(0)
})

/* ---------------------------------------------------------------------------- the stability floor
 *
 * A POINTER STATE MAY REPAINT A CONTROL. IT MAY NOT RE-LAY IT OUT.
 *
 * The owner's report, 2026-09-07: "I am getting a lot of screen shake when I am in inventory and
 * am marking something sold, things should not be moving around when I hit buttons". D118 is the
 * entry, and this is the half of it that is not about one screen: the three floors above answer
 * what a control SAYS to the pointer and the finger, and nothing answered what the PAGE does
 * around it.
 *
 * TWO CASES, AND THEY CATCH DIFFERENT HALVES. This one reads the rules — a hover or a press that
 * changes a width, a padding, a border width, a type size or a gap re-flows everything beside it,
 * under a pointer that is by definition already there. `inventory.spec.ts` carries the other
 * half, which is about what a WRITE does to the panel it lands in, and needs that file's
 * fixtures to see it.
 *
 * MEASURED FIRST, over the 3,422 rules the eleven routes load: exactly one rule reflowed on a
 * pointer state — `.codes-task:hover .codes-task-go` grew a `gap` from 4px to 7px, moving the
 * ellipsised meta line beside it. That is a small number and it is the point: the floors above
 * did their work, and what remained was a rule nothing was watching. A second candidate,
 * `.pricing-cheap-input:focus-visible`, is why this reads COMPUTED values rather than matching on
 * property names — it sets `border-bottom` as a shorthand at the same 2px the rest state already
 * has, so the CSSOM lists `border-bottom-width` among its properties and nothing changes.
 *
 * WHAT IT CANNOT SEE, said plainly: a rule whose selector matches nothing on any route (this
 * worktree's store is empty, D43), and a reflow caused by JavaScript rather than by a rule. The
 * second is exactly what `inventory.spec.ts`'s cases are for. */
const REFLOWS = [
  'width', 'height', 'min-width', 'min-height', 'max-width', 'max-height',
  'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
  'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
  'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
  'font-size', 'font-weight', 'letter-spacing', 'line-height',
  'row-gap', 'column-gap', 'flex-basis', 'flex-grow',
] as const

test('a pointer state repaints a control and never re-lays it out', async ({ page }) => {
  const offenders: string[] = []
  let walked = 0

  for (const route of await routesFromNav(page)) {
    await page.goto(`/${route}`)
    await settleFonts(page)
    await page.waitForLoadState('networkidle', { timeout: 2_000 }).catch(() => {})
    await expect(page.locator('main').first()).toBeVisible()

    const found = await page.evaluate((PROPS) => {
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

      const bad: string[] = []
      let seen = 0
      for (const rule of rules) {
        const sel = rule.selectorText
        if (!sel || !/:(hover|active|focus|focus-visible|focus-within)\b/.test(sel)) continue
        seen++
        const declared = PROPS.filter((p) => rule.style.getPropertyValue(p) !== '')
        if (!declared.length) continue

        /* THE ELEMENT THE RULE PAINTS, not the one carrying the pseudo-class — the same read the
           response floor above makes, and for the same reason: `.a:hover .b` moves `.b`.
           IT IS USED ONLY TO EXONERATE, WHICH IS THE WAY ROUND THIS HAS TO BE. The first draft
           skipped a rule whose selector matched nothing, and the mutation that put the real
           defect back — `.codes-task:hover .codes-task-go { gap: 7px }` — went green, because
           against this worktree's empty store (D43) `#/codes` draws no task card at all. A guard
           that only sees what the fixture happens to render is the failure this file's own header
           spends a paragraph on. So the DECLARATION is what convicts; a rendered element can
           acquit it by already painting the same value, which is the `border-bottom: 2px solid`
           over a 2px edge case and the only false positive this check has. */
        const rest = sel.replace(/:(hover|active|focus-visible|focus-within|focus)\b/g, '')
        let el: Element | null = null
        try {
          el = Array.from(document.querySelectorAll(rest)).find((t) => {
            const b = t.getBoundingClientRect()
            return b.width > 0 && b.height > 0
          }) ?? null
        } catch { el = null }
        const cs = el === null ? null : getComputedStyle(el)

        for (const prop of declared) {
          const want = rule.style.getPropertyValue(prop).trim()
          const now = cs === null ? '(not drawn on this route)' : cs.getPropertyValue(prop).trim()
          if (want === '' || want === now) continue
          bad.push(`${sel}  changes \`${prop}\` from \`${now}\` to \`${want}\` under the pointer — ` +
            `that re-flows everything beside it. Composite the same movement with \`translate\`, ` +
            `or paint it with a colour, a shadow or an inset ring.`)
        }
      }
      return { bad, seen }
    }, REFLOWS as unknown as string[])

    walked += found.seen
    offenders.push(...found.bad)
  }

  /* THE SUBJECT HAS TO BE ON THE PAGE, AND WHAT IS COUNTED IS EVERY POINTER-STATE RULE RATHER
     THAN EVERY OFFENDING ONE. The first draft counted the rules that declared a layout property,
     which is zero once the product is clean — a liveness check that goes to zero the moment the
     thing it guards is fixed is not a liveness check. Measured over the eleven routes: 1,600-odd
     pointer-state rules, so 50 is a floor a broken CSSOM read cannot clear. */
  expect(walked, 'no pointer-state rule was walked at all — is the CSSOM read still valid?')
    .toBeGreaterThan(50)
  expect(
    offenders,
    `${offenders.length} pointer states re-lay out the page:\n${[...new Set(offenders)].join('\n')}`,
  ).toHaveLength(0)
})

/* THE DIP AND THE SQUEEZE LAND ON THE SAME FRAME (D118). `base.css`'s press floor is deliberately
 * not transitioned — its own comment says adding `translate` to the response floor's list "would
 * put 120ms of lag between the finger and the feedback" — and `.bn-btn` then transitioned
 * `transform`, which is where its `scale(0.99)` lives. So every button in the product dropped 1px
 * instantly and eased into the squeeze over 120ms, and released the two the same way in reverse.
 * One gesture on two clocks is what reads as a wobble.
 *
 * THE RULE IS A PAIR, NOT A PROPERTY BAN, and the difference is `.pull-confirm`. A control may
 * legitimately ease a `transform` — that button's hover LIFT is one, and a lift is a response to
 * the pointer arriving rather than to the finger landing. What may not happen is a control easing
 * the movement its own `:active` rule makes. So this asks three things together: does an `:active`
 * rule move the control, does that rule leave the transition alone, and does the element it
 * matches transition that property at rest. All three, or it is not this defect.
 *
 * READ OFF THE CSSOM RATHER THAN OFF A REAL PRESS, which is the one shortcut here and is stated:
 * a rule that cancels the transition inside `:active` is what the third arm looks for, and a
 * control that cancelled it from JavaScript instead would pass this and fail a person. Nothing in
 * this product does that; `app/eslint.config.js` would be the place to say so if one did. */
test('a press lands on one frame — no control eases the movement its own press makes', async ({ page }) => {
  await page.goto('/#/gallery')
  await settleFonts(page)
  await expect(page.locator('main.gallery')).toBeVisible()

  const found = await page.evaluate(() => {
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

    const MOVES = ['transform', 'translate', 'scale', 'rotate']
    const bad: string[] = []
    let walked = 0
    for (const rule of rules) {
      const sel = rule.selectorText
      if (!sel?.includes(':active')) continue
      walked++
      const moved = MOVES.filter((p) => {
        const v = rule.style.getPropertyValue(p).trim()
        return v !== '' && v !== 'none'
      })
      if (!moved.length) continue
      /* The rule cancelling its own transition is the fix, so a rule that carries one is done. */
      const own = rule.style.getPropertyValue('transition') + rule.style.getPropertyValue('transition-property')
      if (own.trim() !== '') continue

      const rest = sel.replace(/:active\b/g, '')
      let el: Element | null = null
      try { el = document.querySelector(rest) } catch { continue }
      if (el === null) continue
      /* The same exemption this file already states at its response-floor sweep: a
         comma-separated CSS list out of `getComputedStyle`, where the browser has normalised the
         separator and no field can carry a comma or a quote. Not a CSV. */
      // eslint-disable-next-line no-restricted-syntax -- a CSS list from getComputedStyle, not a CSV
      const props = getComputedStyle(el).transitionProperty.split(',').map((p) => p.trim())
      const eased = moved.filter((p) => props.includes(p) || props.includes('all'))
      if (!eased.length) continue
      bad.push(`${sel}  moves \`${moved.join(', ')}\` on the press while the control eases ` +
        `\`${eased.join(', ')}\` — the floor's dip lands on the frame the finger goes down and this ` +
        `does not, so one gesture runs on two clocks. Drop the property from the control's own ` +
        `\`transition\`, or cancel it inside the \`:active\` rule.`)
    }
    return { bad: [...new Set(bad)], walked }
  })

  expect(found.walked, 'no `:active` rule was walked at all — is the CSSOM read still valid?')
    .toBeGreaterThan(10)
  expect(
    found.bad,
    `${found.bad.length} controls ease their own press:\n${found.bad.join('\n')}`,
  ).toHaveLength(0)
})

/* THE FLOOR ITSELF, PRESSED WITH A REAL MOUSE ON ELEMENTS THIS TEST BUILDS — and it has to be a
 * real press, because `:active` cannot be forced from script the way a class can. Bare elements
 * with no component class are the point, exactly as in the cursor floor's own case below: the
 * floor is what is under test, so anything dressed in a screen's class would be testing that
 * screen instead.
 *
 * THE DISABLED SHAPE IS THE ONE THAT EARNS THIS CASE. A control refusing the click must not move
 * under it — the same claim the cursor floor's disabled arm makes with `not-allowed`, and the
 * class that was 30 of D50's original 41 defects. A floor that pressed everything including the
 * controls that refuse would be a new defect of exactly that shape. */
const PRESS_SHAPES: [html: string, moves: boolean, why: string][] = [
  ['<button>x</button>', true, 'a button'],
  ['<button disabled>x</button>', false, 'a disabled button'],
  ['<button aria-disabled="true">x</button>', false, 'an aria-disabled button'],
  ['<a href="#/gallery">x</a>', true, 'a link'],
  ['<select><option>x</option></select>', true, 'a select'],
  ['<select disabled><option>x</option></select>', false, 'a disabled select'],
  ['<summary>x</summary>', true, 'a summary'],
  ['<div role="button">x</div>', true, 'a div promoted to a control'],
  ['<div role="menuitem">x</div>', true, 'a menu item'],
  ['<input type="checkbox">', true, 'a checkbox'],
  ['<input type="checkbox" disabled>', false, 'a disabled checkbox'],
  /* NOT A CONTROL, AND ASSERTED NEGATIVELY for the same reason the cursor floor asserts one:
     a floor that reached ordinary content would be making a false offer, and `<p>` is the
     cheapest proof that the selector list is a list rather than a `*`. */
  ['<p>words</p>', false, 'a paragraph, deliberately not a control'],
]

test('the press floor answers for every shape a control can take', async ({ page }) => {
  await page.goto('/#/gallery')
  await settleFonts(page)
  await expect(page.locator('main.gallery')).toBeVisible()

  const wrong: string[] = []
  for (const [html, moves, why] of PRESS_SHAPES) {
    /* PLACED AT A FIXED POINT ON TOP OF EVERYTHING, so the press lands on the shape under test
       and not on whatever the gallery draws there. Rebuilt per shape rather than laid out in a
       row, because a press must be aimed and one known coordinate is cheaper than eleven. */
    await page.evaluate((h) => {
      document.getElementById('press-probe')?.remove()
      const host = document.createElement('div')
      host.id = 'press-probe'
      host.style.cssText = 'position:fixed;top:300px;left:500px;width:120px;height:44px;z-index:2147483647'
      host.innerHTML = h
      const el = host.firstElementChild as HTMLElement
      el.style.display = 'block'
      el.style.width = '120px'
      el.style.height = '44px'
      document.body.appendChild(host)

      /* AND THE BROWSER'S OWN DEFAULT IS SUPPRESSED FOR THE LENGTH OF THE PRESS, WHICH IS THIS
         CASE'S SECOND RECORDED FLAKE AND THE ONE THE POLL ABOVE COULD NOT SEE. `<select>` is the
         only shape here whose default action is to open a NATIVE POPUP, and that popup takes the
         press: the dip lands on the frame the mouse goes down, and then `:active` is cleared
         again before the round-trip below can read it. Measured on this tree — the dip sampled
         inside the element's own `mousedown` was there 80 times out of 80, while the read below
         missed it, so what was intermittent was the OBSERVATION and never `base.css`.
         Left alone it fails ~4% of runs at seven workers and ~16% at fourteen, always naming the
         select and always reporting the FLOOR as broken — a test telling a true-looking lie
         about the product, which is the same fault the poll above was written for.
         `preventDefault` stops the popup opening; it does not stop the browser applying
         `:active`, which is what this case reads. IT IS NOT A SUBSTITUTE FOR THE READ: sampling
         in a listener instead was tried and WEAKENS this case, because a genuinely disabled
         control dispatches no mouse event at all while still matching `:active` — so the
         disabled arm, which is 30 of D50's original 41 defects, went silently green. */
      const w = window as unknown as { __pressProbeDefault?: (e: Event) => void }
      w.__pressProbeDefault = (e: Event) => e.preventDefault()
      document.addEventListener('mousedown', w.__pressProbeDefault, true)
    }, html)

    /* THE PRESS IS AIMED AT WHAT `elementFromPoint` ACTUALLY RETURNS, AND THAT IS THIS CASE'S
       RECORDED FLAKE. Moving to a hard-coded coordinate and pressing assumes the probe is
       painted and on top by the time the mouse arrives; under seven parallel workers against a
       cold dev server it sometimes is not, and the case then reports the FLOOR as broken when
       what actually happened is that the press landed on the gallery underneath. That is a test
       telling a true-looking lie about the product, which is worse than a slow one. So: wait
       until the point resolves to the probe, then press. `expect.poll` gives it the config's
       own allowance and asserts the SETUP rather than the subject — if the probe never gets
       there, this fails saying so instead of blaming `base.css`. */
    const target = await page.evaluate(() => {
      const el = document.getElementById('press-probe')!.firstElementChild as HTMLElement
      const b = el.getBoundingClientRect()
      return { x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2) }
    })
    await page.mouse.move(target.x, target.y)
    await expect
      .poll(
        () =>
          page.evaluate((t) => {
            const at = document.elementFromPoint(t.x, t.y)
            const probe = document.getElementById('press-probe')
            return Boolean(at && probe && (at === probe.firstElementChild || probe.contains(at)))
          }, target),
        { message: `the ${why} probe never reached the point the press is aimed at` },
      )
      .toBe(true)

    await page.mouse.down()
    const translate = await page.evaluate(
      () => getComputedStyle(document.getElementById('press-probe')!.firstElementChild!).translate,
    )
    await page.mouse.up()
    await page.evaluate(() => {
      const w = window as unknown as { __pressProbeDefault?: (e: Event) => void }
      if (w.__pressProbeDefault) document.removeEventListener('mousedown', w.__pressProbeDefault, true)
    })

    const moved = translate !== 'none' && translate !== ''
    if (moved !== moves) {
      wrong.push(moves
        ? `  ${why} did not move under the press — translate is "${translate}"`
        : `  ${why} moved under the press — translate is "${translate}", and it must not move at all`)
    }
  }
  await page.evaluate(() => document.getElementById('press-probe')?.remove())

  expect(
    wrong,
    `the press floor answers wrongly for ${wrong.length} of ${PRESS_SHAPES.length} shapes:\n${wrong.join('\n')}`,
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
