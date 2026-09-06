// Rasterize a sheet section at TRUE pixels and magnify the BITMAP, nearest-neighbour.
//   node pixels.mjs <sheet.html> <out.png> <section-index> [zoom]
//
// A sweep whose step has fallen below a pixel cannot be answered by drawing it larger: scaling
// the vector shows a rendering no screen ever produces, and section 9's small row made exactly
// that mistake -- shot at deviceScaleFactor 2, so its "28px" tiles carried 56 real pixels, in
// the one row whose whole job was to demonstrate a failure.
// The honest instrument is the opposite: render at deviceScaleFactor 1, which is what a 1x
// display gets, then blow the RESULTING PIXELS up with smoothing off. What you then look at is
// the rounding the screen actually performs -- whether 0.23 and 0.24 land on the same 7px of
// type or on different ones -- which is the only difference that exists at this step.
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, resolve } from 'node:path'
import { readFileSync } from 'node:fs'

const here = dirname(fileURLToPath(import.meta.url))
const { chromium } = await import(pathToFileURL(resolve(here, '../../../../app/node_modules/playwright/index.mjs')).href)

const [, , src, out, idxArg, zoomArg] = process.argv
const idx = +idxArg, zoom = +(zoomArg || 6)
const b = await chromium.launch()

// 1 -- the sheet at TRUE pixels
const p = await b.newPage({ viewport: { width: 1400, height: 1200 }, deviceScaleFactor: 1 })
await p.goto('file://' + src)
await p.waitForFunction(() => window.__sheetReady === true, null, { timeout: 20000 }).catch(() => {})
const pageH = await p.evaluate(() => document.documentElement.scrollHeight)
await p.setViewportSize({ width: 1400, height: Math.min(pageH + 40, 12000) })

/* ONE CROP PER SPECIMEN, STACKED DOWN THE PAGE rather than one crop of the whole row. A row of
   five magnified specimens is six thousand pixels wide, and every client that receives it scales
   it back down to fit -- which undoes the magnification exactly, and leaves an image that looks
   like evidence and is not. Stacked, each specimen keeps its real pixels at full zoom. */
const boxes = await p.evaluate((i) => {
  const s = document.querySelectorAll('.strip')[i]
  return [...s.querySelectorAll('.lk')].map(lk => {
    const r = lk.querySelector('.r').getBoundingClientRect()
    return { label: (+lk.dataset.romanSize).toString(),
             x: Math.floor(r.left) - 2, y: Math.floor(r.top + scrollY) - 2,
             w: Math.ceil(r.width) + 4, h: Math.ceil(r.height) + 4 }
  })
}, idx)

const shots = []
for (const bx of boxes) {
  const png = await p.screenshot({ clip: { x: bx.x, y: bx.y, width: bx.w, height: bx.h } })
  shots.push({ label: bx.label, b64: png.toString('base64'), w: bx.w, h: bx.h })
}

// 2 -- magnify each BITMAP with smoothing off, stacked, labelled
const p2 = await b.newPage({ viewport: { width: 400, height: 400 }, deviceScaleFactor: 1 })
await p2.setContent('<body style="margin:0;background:#dde1e6"><div id="w"></div>')
const dims = await p2.evaluate(async ({ shots, z }) => {
  const w = document.getElementById('w')
  w.style.cssText = 'padding:14px;display:flex;flex-direction:column;gap:12px;width:max-content'
  for (const s of shots) {
    const img = new Image()
    await new Promise(r => { img.onload = r; img.src = 'data:image/png;base64,' + s.b64 })
    const row = document.createElement('div')
    row.style.cssText = 'display:flex;align-items:center;gap:14px'
    const tag = document.createElement('div')
    tag.textContent = s.label
    tag.style.cssText = 'font:700 15px ui-monospace,monospace;color:#22262d;width:52px;text-align:right'
    const c = document.createElement('canvas')
    c.width = img.width * z; c.height = img.height * z
    c.style.cssText = 'display:block;background:#fff;border-radius:3px'
    const x = c.getContext('2d')
    x.imageSmoothingEnabled = false
    x.drawImage(img, 0, 0, c.width, c.height)
    row.append(tag, c); w.appendChild(row)
  }
  const r = w.getBoundingClientRect()
  return { w: Math.ceil(r.width), h: Math.ceil(r.height) }
}, { shots, z: zoom })
await p2.setViewportSize({ width: Math.min(dims.w, 4000), height: Math.min(dims.h, 8000) })
await p2.locator('#w').screenshot({ path: out })
console.log(out + '  ' + shots.length + ' specimens, ' + shots[0].w + 'x' + shots[0].h +
            ' true pixels each, magnified ' + zoom + 'x')
await b.close()
