// Cut a sheet into ONE IMAGE PER SECTION, framed on the section's own bounding box.
//   node sections.mjs <sheet.html> <outdir> [width]
//
// It exists because blind pixel crops of a tall sheet cut panels in half and sliced a whole
// row away, twice, and the only reason that was ever noticed is that somebody looked. A crop
// offset is a guess about a layout that changes every round; a bounding box is not.
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, resolve, join } from 'node:path'
import { mkdirSync } from 'node:fs'

const here = dirname(fileURLToPath(import.meta.url))
const { chromium } = await import(pathToFileURL(resolve(here, '../../../../app/node_modules/playwright/index.mjs')).href)

const [, , src, outdir, w] = process.argv
mkdirSync(outdir, { recursive: true })
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: +(w || 1500), height: 1200 }, deviceScaleFactor: 2 })
await p.goto('file://' + src)
await p.waitForFunction(() => window.__sheetReady === true, null, { timeout: 20000 }).catch(() => {})
await p.waitForTimeout(400)

// A section is a heading and everything up to the next heading. The lede and the banner have no
// heading of their own, so they are the implicit first one.
const boxes = await p.evaluate(() => {
  const out = []
  const marks = [...document.querySelectorAll('h2')]
  const R = el => { const r = el.getBoundingClientRect(); return { top: r.top + scrollY, bottom: r.bottom + scrollY } }
  const page = document.documentElement.scrollHeight
  const head = marks.length ? R(marks[0]).top : page
  out.push({ name: '00-lede', top: 0, bottom: head })
  marks.forEach((m, i) => {
    const top = R(m).top
    // stop SHORT of the next heading rather than at it -- ending exactly on it leaves a sliver of
    // the next section's title in the image, which reads as a crop that went wrong
    const bottom = i + 1 < marks.length ? R(marks[i + 1]).top - 22 : page
    const slug = m.textContent.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40)
    out.push({ name: String(i + 1).padStart(2, '0') + '-' + slug, top, bottom })
  })
  return out
})

// The viewport is opened to the WHOLE page once, before any clip. A clip is measured in page
// coordinates but only resolves against what the viewport has laid out, so clipping a tall sheet
// through a short window fails outright on the second section -- which is at least a loud failure
// rather than a silently short image.
const pageH = await p.evaluate(() => document.documentElement.scrollHeight)
await p.setViewportSize({ width: +(w || 1500), height: Math.min(pageH + 40, 12000) })
await p.waitForTimeout(300)

// The clip's WIDTH is the widest thing actually drawn, not the viewport. A specimen row is
// whatever its cells add up to, and a fixed width pads every image with a band of empty sheet
// that shrinks the specimens once the client scales the image to fit.
const contentW = await p.evaluate(() => {
  let m = 0
  /* every block a sheet lays specimens out in, not just the two the round sheet happens to use --
     a sheet with a row this list does not name gets its images silently cropped */
  document.querySelectorAll('.strip, table, .big, .row').forEach(e => { const r = e.getBoundingClientRect(); if (r.width) m = Math.max(m, r.right) })
  return Math.ceil(m)
})
const W = Math.min(+(w || 1500), Math.max(560, contentW + 28))

for (const s of boxes) {
  const h = Math.round(s.bottom - s.top)
  if (h < 24) continue
  await p.screenshot({ path: join(outdir, s.name + '.png'),
                       clip: { x: 0, y: Math.max(0, s.top - 10), width: W, height: h + 16 } })
  console.log(s.name + '.png  ' + W + ' x ' + h)
}
await b.close()
