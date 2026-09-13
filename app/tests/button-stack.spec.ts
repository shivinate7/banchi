import { test, expect } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { routesFromNav } from './routes'
import { sealEveryTest } from './shell'

/* SAME-ROLE BUTTONS THAT STACK IN ONE SECTOR TAKE THE SAME WIDTH — the owner's ruling,
 * 2026-09-13: "Buttons should be the same sizes if they're in the same sort of sector."
 * `D195` is the entry, `.bn-actions-stack` in `kit.css` and the
 * `.capture-block-list` grid in `CaptureScreen.css` are the two shapes of the one mechanism —
 * a single `max-content` grid column sized by its widest child.
 *
 * THIS FILE FINDS ITS SUBJECTS RATHER THAN READING A DECLARED CLASS, on the same argument
 * `cursor.spec.ts` already makes about controls: a guard that only checks a `.bn-actions-stack`
 * someone remembered to wrap is blind to the exact case the owner pointed at — a stack built
 * without the wrapper at all. So this sweeps every rendered `.bn-btn`, groups by the nearest
 * SECTOR ancestor and by identical variant+size class set, keeps only groups whose members are
 * vertically stacked with left edges aligned, and asserts every member's width equals the
 * group's widest within 1px.
 *
 * A SECTOR IS A PANEL, NOT THE PAGE. `.bn-panel`, `.bn-well`, `.bn-sheet`, `.bn-dialog`,
 * `[role=group]`, `section`, `.capture-block` (the flagship instance) and the kit `EmptyState`
 * (`.bn-empty`) are read as sector boundaries — the nearest one wins, so a button inside a
 * panel inside a page is grouped with its panel siblings and never with the whole screen's.
 *
 * SAME ROLE ONLY: variant and size must match exactly, so a primary beside a ghost Cancel is
 * two different groups and never compared. STACKED ONLY: a horizontal row is exempt by the
 * owner's own words, so a pair is kept only when each member's top is at or past the previous
 * member's bottom (allowing the small row gap this app uses) and their left edges agree within
 * 1px — a horizontal row fails the top-vs-bottom test and drops out on its own. `block` buttons
 * are excluded outright: they are already equal, by definition of `.bn-btn-block`.
 */

const SECTOR_SELECTOR =
  '.bn-panel, .bn-well, .bn-sheet, .bn-dialog, [role="group"], section, .capture-block, .bn-empty'

async function sweepButtonGroups(page: import('@playwright/test').Page, route: string) {
  return page.evaluate(
    ({ route, sectorSelector }) => {
      function sectorFor(el: Element): Element | null {
        return el.closest(sectorSelector)
      }

      /* THE ROLE KEY IS EVERY `bn-btn-*` CLASS THE BUTTON CARRIES, NEVER A HAND-TYPED LIST —
         a fixed roster missed `bn-btn-quiet` the first time this ran and silently folded a
         quiet Close beside a plain Reload into one 'plain' group, which is the exact defect
         a discovered roster (this file's own argument, made once already about routes and
         controls) exists to catch. `bn-btn-block` is excluded upstream, so it never reaches
         here. */
      function roleKey(el: Element): string {
        return Array.from(el.classList)
          .filter((c) => c.startsWith('bn-btn-'))
          .sort()
          .join(' ') || 'plain'
      }

      const buttons = Array.from(document.querySelectorAll<HTMLElement>('.bn-btn'))
      const bySector = new Map<Element, Map<string, BtnInfoRaw[]>>()

      type BtnInfoRaw = {
        el: HTMLElement
        label: string
        cls: string
        x: number
        top: number
        bottom: number
        width: number
      }

      for (const el of buttons) {
        if (el.classList.contains('bn-btn-block')) continue
        const box = el.getBoundingClientRect()
        if (box.width === 0 || box.height === 0) continue
        const cs = getComputedStyle(el)
        if (cs.visibility === 'hidden' || cs.display === 'none') continue
        const sector = sectorFor(el)
        if (sector === null) continue
        const key = roleKey(el)
        if (!bySector.has(sector)) bySector.set(sector, new Map())
        const byRole = bySector.get(sector)!
        if (!byRole.has(key)) byRole.set(key, [])
        byRole.get(key)!.push({
          el,
          label: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40),
          cls: el.className,
          x: box.left,
          top: box.top,
          bottom: box.bottom,
          width: box.width,
        })
      }

      const out: {
        route: string
        sector: string
        role: string
        members: { label: string; cls: string; width: number }[]
      }[] = []

      let sectorIdx = 0
      for (const [sector, byRole] of bySector) {
        sectorIdx += 1
        const sectorName =
          sector.getAttribute('aria-label') ||
          sector.className.toString().slice(0, 40) ||
          sector.tagName.toLowerCase()
        for (const [role, members] of byRole) {
          if (members.length < 2) continue
          // sort top-to-bottom
          members.sort((a, b) => a.top - b.top)
          let stacked = true
          for (let i = 1; i < members.length; i++) {
            const prev = members[i - 1]
            const cur = members[i]
            if (!prev || !cur) continue
            const leftAligned = Math.abs(cur.x - prev.x) <= 1
            const verticallyAfter = cur.top >= prev.bottom - 1
            if (!leftAligned || !verticallyAfter) {
              stacked = false
              break
            }
          }
          if (!stacked) continue
          out.push({
            route,
            sector: `#${sectorIdx} ${sectorName}`,
            role,
            members: members.map((m) => ({ label: m.label, cls: m.cls, width: m.width })),
          })
        }
      }
      return out
    },
    { route, sectorSelector: SECTOR_SELECTOR },
  )
}

sealEveryTest({ store: true })

test('same-role buttons stacked in one sector share a width', async ({ page }) => {
  test.setTimeout(60_000)

  const wrong: string[] = []
  let groupsChecked = 0

  for (const route of await routesFromNav(page)) {
    await page.goto(`/${route}`)
    await settleFonts(page)
    await page.waitForLoadState('networkidle', { timeout: 2_000 }).catch(() => {})
    await expect(page.locator('main').first()).toBeVisible()

    const groups = await sweepButtonGroups(page, route)
    for (const group of groups) {
      groupsChecked += 1
      const widths = group.members.map((m) => m.width)
      const max = Math.max(...widths)
      const off = group.members.filter((m) => Math.abs(m.width - max) > 1)
      if (off.length > 0) {
        wrong.push(
          `${group.route}  sector ${group.sector}  role [${group.role}]\n` +
            group.members
              .map((m) => `    "${m.label}"  ${m.width.toFixed(1)}px  .${m.cls.slice(0, 60)}`)
              .join('\n'),
        )
      }
    }
  }

  /* A FLOOR ON THE SWEEP ITSELF, the same shape as `cursor.spec.ts`'s and `routesFromNav`'s —
     a guard that finds zero groups everywhere is a guard that passes on a broken fixture, not
     on a correct app. The capture block alone contributes at least one group whenever a store
     is empty of a camera and a box, which `shell.ts`'s fixture arranges for at least one route
     in this sweep. */
  expect(
    groupsChecked,
    'the sweep found no stacked same-role button groups anywhere — is the fixture still ' +
      'rendering the capture prerequisites block, or did the sector/role selectors stop matching?',
  ).toBeGreaterThan(0)

  expect(
    wrong,
    `${wrong.length} sector(s) have unequal same-role button widths:\n\n${wrong.join('\n\n')}`,
  ).toHaveLength(0)
})
