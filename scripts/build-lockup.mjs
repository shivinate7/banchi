// GENERATE THE LOCKUP'S GEOMETRY. Reads docs/specs/logo.md section 13's settled table and
// docs/specs/logo/sheets/lockup-core.js, and writes app/src/kit/lockupGeometry.ts.
//
// THIS SCRIPT DOES NOT CONTAIN THE DESIGN. Section 13 is the store of record for all eleven
// parameters and this reads them from it, so there is no third copy to drift — `build-mark.mjs`
// re-declares its constants because the mark's are not in a machine-readable table, and the
// lockup's are.
//
// WHY IT DRIVES A BROWSER WHERE `build-mark.mjs` USES `new Function`. That script slices a
// DOM-free region out of `small-cut.html`. This one cannot: `lockup-core.js`'s `frame()` measures
// text with `document.createRange()` to solve the roman's tracking. So the solve runs in
// Playwright, once, and its answer is baked — section 15's argument for baking is that shipping
// the solve would mean measuring text in a layout effect on every mount.
//
// WHY OUTLINES RATHER THAN A WEBFONT. A subset webfont was section 15's original plan and it has
// a silent failure: if the font does not arrive, the browser draws a fallback CJK face at
// letter-spacing computed for IBM Plex, and nothing reports it. Outlines cannot fail that way,
// they render identically on every rasterizer, and they make the lockup the same KIND of artifact
// as the mark — `markGeometry.ts` already ships path data rather than text.
//
// THE FONTS ARE NEVER COMMITTED. They come from `@ibm/plex-sans-jp` and `@fontsource/manrope`,
// both OFL-1.1, both devDependencies. Only the two extracted paths land in the repo, which is
// artwork rather than font software.
//
// D18: a generator may write, and nothing that writes may gate a commit. Run by hand.
//
//   node scripts/build-lockup.mjs

import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SPEC = resolve(ROOT, 'docs/specs/logo.md')
const CORE = resolve(ROOT, 'docs/specs/logo/sheets/lockup-core.js')
const KANJI_WOFF = resolve(ROOT, 'app/node_modules/@ibm/plex-sans-jp/fonts/complete/woff/hinted/IBMPlexSansJP-Regular.woff')
const ROMAN_WOFF = resolve(ROOT, 'app/node_modules/@fontsource/manrope/files/manrope-latin-700-normal.woff')
const OUT = resolve(ROOT, 'app/src/kit/lockupGeometry.ts')

const must = (cond, why) => { if (!cond) { console.error('build-lockup: ' + why); process.exit(1) } }

/* ---- 1 · the settled table, read rather than retyped ---------------------------------------- */

const spec = readFileSync(SPEC, 'utf8')
const marker = '### The settled values, and the one place they live'
must(spec.includes(marker), 'section 13\'s settled table is gone; there is nothing to generate from')
let table = spec.slice(spec.indexOf(marker))
table = table.slice(0, table.indexOf('\n### ', 10))
const P = Object.fromEntries(
  [...table.matchAll(/^\| `(\w+)` \| ([0-9.]+) \|/gm)].map(([, k, v]) => [k, Number(v)]),
)
for (const k of ['pad', 'gap', 'stroke', 'rrMul', 'arm', 'tl', 'tip',
                 'romanSize', 'romanFill', 'romanOpacity'])
  must(k in P, `section 13's table does not settle \`${k}\``)

/* THE REFERENCE SIZE IS 100 AND EVERY EMITTED NUMBER IS A RATIO OF IT. Every parameter in the
   table is a fraction of the kanji size or of the block, so one geometry serves every size and
   the component scales it with a viewBox. That is also strictly better than live text at 8px:
   a vector scaled by a viewBox cannot re-layout, so the roman cannot reflow between sizes. */
const REF = 100

/* ---- 2 · the solve, in a real browser -------------------------------------------------------- */

const { chromium } = await import(
  pathToFileURL(resolve(ROOT, 'app/node_modules/playwright/index.mjs')).href
)
const opentype = await import(
  pathToFileURL(resolve(ROOT, 'app/node_modules/opentype.js/dist/opentype.mjs')).href
).then((m) => m.default ?? m)

const b64 = (p) => readFileSync(p).toString('base64')
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 900, height: 500 }, deviceScaleFactor: 1 })

await page.setContent(`<style>
  @font-face{font-family:LKJ;src:url(data:font/woff;base64,${b64(KANJI_WOFF)}) format('woff');font-weight:400}
  @font-face{font-family:LKR;src:url(data:font/woff;base64,${b64(ROMAN_WOFF)}) format('woff');font-weight:700}
  body{margin:0;background:#fff}
  .lk{position:relative;display:inline-block}
  .lk svg{position:absolute;inset:0;overflow:visible;pointer-events:none}
  .go{font-family:LKJ;font-weight:400;line-height:1;display:block}
  .rom{font-family:LKR;font-weight:700;line-height:1;display:block;white-space:nowrap}
</style><div id="host"></div>`)
await page.addScriptTag({ content: readFileSync(CORE, 'utf8') })
await page.evaluate(async () => {
  await document.fonts.load('400 100px LKJ')
  await document.fonts.load('700 40px LKR')
  await document.fonts.ready
})

const measured = await page.evaluate(({ P, REF }) => {
  const lk = stamp(REF, P.gap, P.pad, '#000',
                   { romanSize: P.romanSize, romanOpacity: 1 })
  document.getElementById('host').appendChild(lk)
  frame(lk, { stroke: P.stroke, arm: P.arm, tl: P.tl, rrMul: P.rrMul, tip: P.tip,
              romanFill: P.romanFill })
  const box = lk.getBoundingClientRect()
  // the INK box of each run, taken from a Range rather than the block-level span, because
  // `.go`/`.rom` are `display:block` and their own rects are the container's width
  /* THE PEN, NOT THE INK BOX. A Range's rect is the LINE BOX — its top is the top of the line,
     not the top of the ink — so matching it against an outline's bounding box drew the type
     several pixels high. `opentype.getPath(x, y, size)` wants the PEN: x at the run's start and y
     on the alphabetic baseline, which is exactly what these two measurements are.
     The baseline is measured rather than derived: a zero-sized inline-block aligned to `baseline`
     has its top ON the baseline, whatever Chrome decided to do with the font's hhea and OS/2
     metrics. Deriving it instead would be a guess about which table the browser trusts. */
  const pen = (sel) => {
    const el = lk.querySelector(sel)
    const r = document.createRange(); r.selectNodeContents(el)
    const q = r.getBoundingClientRect()
    const probe = document.createElement('span')
    probe.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline'
    el.appendChild(probe)
    const baseline = probe.getBoundingClientRect().top
    probe.remove()
    return { x: q.left - box.left, baseline: baseline - box.top }
  }
  const svg = lk.querySelector('svg')
  return {
    w: lk.offsetWidth, h: lk.offsetHeight,
    bracket: svg.innerHTML,
    kanji: pen('.k'), roman: pen('.r'),
    track: +lk.dataset.romanTrackSolved,
    kanjiSize: REF, romanSize: REF * P.romanSize,
  }
}, { P, REF })

must(measured.w > 0 && measured.h > 0, 'the lockup measured zero')
must(measured.bracket.includes('<path'), 'the bracket did not draw')

/* ---- 3 · the outlines, placed against the measured ink ------------------------------------- */

/* NO BASELINE ARITHMETIC. Where Chrome puts a baseline inside a `line-height: 1` box depends on
   which of hhea/OS-2 it trusts, and getting that subtly wrong shifts the type by a pixel that no
   reviewer would catch. So each run is laid out at an arbitrary baseline, its own ink bbox is
   measured, and it is translated so that bbox lands on the one the BROWSER produced. The
   placement is then a measurement rather than a derivation, and step 4 checks it. */
const layout = (fontPath, text, fontSize, trackPx) => {
  const buf = readFileSync(fontPath)
  const font = opentype.parse(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength))
  const path = new opentype.Path()
  let x = 0
  for (const ch of text) {
    const g = font.charToGlyph(ch)
    must(g && g.index !== 0, `\`${ch}\` is not in ${fontPath.split('/').pop()}`)
    path.extend(g.getPath(x, 0, fontSize))
    x += (g.advanceWidth / font.unitsPerEm) * fontSize + trackPx
  }
  return path
}

const place = (path, pen) => {
  for (const c of path.commands)
    for (const k of ['x', 'y', 'x1', 'y1', 'x2', 'y2'])
      if (k in c) c[k] += k[0] === 'x' ? pen.x : pen.baseline
  return path
}

// the kanji carries a fixed 0.07em of tracking, set in `stamp`; the roman carries the SOLVED
// value, which is the whole reason a browser had to run at all
const kanjiPath = place(layout(KANJI_WOFF, '番地', measured.kanjiSize, 0.07 * measured.kanjiSize),
                        measured.kanji)
const romanPath = place(layout(ROMAN_WOFF, 'BANCHI', measured.romanSize, measured.track * REF),
                        measured.roman)

/* THE BRACKET, TAKEN APART. `frame()` emits one arm plus its 180-degree twin as a markup string,
   and a component that injected that string would need `dangerouslySetInnerHTML` for artwork this
   repo generates itself. Split into a path, its two end discs and the rotation, the component
   renders real JSX and React can key it. */
const armPath = /<path d="([^"]+)"/.exec(measured.bracket)
must(armPath, 'no bracket path in the drawing')
const caps = [...measured.bracket.matchAll(/<circle cx="([\d.-]+)" cy="([\d.-]+)" r="([\d.-]+)"/g)]
  .slice(0, 2).map((m) => [+m[1], +m[2], +m[3]])
const spin = /transform="(rotate\([^"]+\))"/.exec(measured.bracket)
must(spin, 'the bracket lost its 180-degree twin')

const round3 = (d) => d.replace(/-?\d+\.\d+/g, (n) => String(+(+n).toFixed(3)))
const KANJI_D = round3(kanjiPath.toPathData(3))
const ROMAN_D = round3(romanPath.toPathData(3))

must(KANJI_D.length > 400, 'the kanji outline is too short to be two glyphs')
must(ROMAN_D.length > 400, 'the roman outline is too short to be six glyphs')

/* ---- 4 · the check `build-mark.mjs` does not have ------------------------------------------- */

/* OUTLINING IS THE ONE STEP THAT CAN SILENTLY CHANGE A DRAWING THIRTY-SEVEN ROUNDS APPROVED.
   Every other assertion here is a shape check; this one renders the generated paths beside the
   live text they replace and compares the pixels. A placement off by a pixel, a wrong tracking,
   a glyph substitution — none of those trip an assertion about path length, and all of them are
   obvious to a difference. */
/* THE WHOLE LOCKUP BOTH WAYS, not just the type. The first version of this drew only the two
   outlines and compared them against a live shot that included the bracket, so it reported 77% of
   inked pixels differing and looked like a catastrophic placement error. It was measuring the
   bracket's absence. A comparison whose two sides are not the same drawing tells you nothing, and
   it is worth noting that this check caught its own bug before it caught anything else.

   Two real screenshots rather than a canvas trick: a `foreignObject` carrying a data-URI font is
   blocked, so the live run is captured as the page already draws it and the outlines are drawn on
   their own page at the same size. */
const liveShot = await page.locator('.lk').screenshot()
await page.setContent(`<style>body{margin:0;background:#fff}svg{display:block}</style>
  <svg xmlns="http://www.w3.org/2000/svg" width="${measured.w}" height="${measured.h}">
    ${measured.bracket}<path d="${KANJI_D}" fill="#000"/><path d="${ROMAN_D}" fill="#000"/></svg>`)
const outlineShot = await page.locator('svg').screenshot()

const compare = await page.evaluate(async ({ a, b }) => {
  const load = (s) => new Promise((res) => {
    const i = new Image(); i.onload = () => res(i); i.src = 'data:image/png;base64,' + s
  })
  const [ia, ib] = await Promise.all([load(a), load(b)])
  const px = (img) => {
    const c = document.createElement('canvas'); c.width = img.width; c.height = img.height
    const x = c.getContext('2d'); x.drawImage(img, 0, 0)
    return x.getImageData(0, 0, c.width, c.height).data
  }
  const A = px(ia), B = px(ib)
  if (A.length !== B.length) return { sameSize: false }
  let ink = 0, off = 0
  for (let i = 0; i < A.length; i += 4) {
    const da = 255 - A[i], db = 255 - B[i]
    if (da > 32 || db > 32) ink++
    if (Math.abs(da - db) > 96) off++
  }
  return { sameSize: true, ink, off, pct: +(100 * off / Math.max(ink, 1)).toFixed(2) }
}, { a: liveShot.toString('base64'), b: outlineShot.toString('base64') })

/* When the comparison fails, the two images are the only useful evidence — a percentage says
   something is wrong and never what. `LOCKUP_DEBUG=<dir>` writes both. */
if (process.env.LOCKUP_DEBUG) {
  const { writeFileSync: w } = await import('node:fs')
  w(resolve(process.env.LOCKUP_DEBUG, 'live.png'), liveShot)
  w(resolve(process.env.LOCKUP_DEBUG, 'outline.png'), outlineShot)
  console.log('build-lockup: wrote live.png and outline.png to ' + process.env.LOCKUP_DEBUG)
}

must(compare.sameSize, 'the outline render is a different size from the live one')
must(compare.ink > 500, 'almost nothing was drawn — the comparison would pass on two blank images')
/* 8% IS NOT A ROUND NUMBER, IT IS A MEASURED CEILING. On the settled parameters the residual is
   6.2%, and rendering the diff shows what it is: a one-pixel outline around each glyph and
   NOTHING on the bracket. The woff is Plex's HINTED build, so the browser snaps stems to the
   pixel grid and a vector path does not — which is the same reason outlines are more consistent
   across rasterizers than live text, showing up here as the cost of the comparison rather than a
   defect. A real placement error is not subtle at this threshold: the first version of this
   script, which matched an outline's bbox against a Range's LINE box, read 69%. */
must(compare.pct < 8,
     `the outlines do not match the live text: ${compare.pct}% of inked pixels differ ` +
     `(${compare.off} of ${compare.ink}). The drawing thirty-seven rounds approved is live text; ` +
     `an outline that disagrees with it is a different lockup.`)

await browser.close()

/* ---- 5 · write ------------------------------------------------------------------------------ */

const R = (n) => +n.toFixed(4)
const ts = `/* GENERATED by scripts/build-lockup.mjs from docs/specs/logo.md section 13 and
   docs/specs/logo/sheets/lockup-core.js. Do not hand-edit — re-run the script.
   docs/specs/logo.md is the state of record.

   EVERY NUMBER HERE IS A RATIO OF THE KANJI SIZE, and the paths are drawn in a ${measured.w} x
   ${measured.h} box at kanji ${REF}. One geometry serves every size: the component sets a viewBox
   and scales. That is not only smaller than emitting per-size data — it is more correct, because
   a vector scaled by a viewBox cannot re-layout, so the roman cannot reflow between the sidebar's
   size and the gallery's.

   THE TYPE IS OUTLINED, NOT SET. Section 15's first plan shipped a subset webfont and that has a
   silent failure: a blocked CDN draws a fallback CJK face at letter-spacing solved for IBM Plex,
   and nothing reports it. These paths cannot fail that way and render identically everywhere.
   The generator checks them against the live text they replace, pixel for pixel, before writing.

   Fonts: IBM Plex Sans JP 400 (kanji) and Manrope 700 (roman), both OFL-1.1, both devDependencies
   read at build time and never committed. Outlines are artwork, not font software. */

/** Section 13's eleven settled parameters, read out of the spec's own table.
 *  \`make docs-audit\`'s \`lockup params\` row reconciles these against it and against the round
 *  sheet's holds, so all three cannot disagree. */
export const PARAMS = {
  pad: ${P.pad}, gap: ${P.gap}, stroke: ${P.stroke}, rrMul: ${P.rrMul}, arm: ${P.arm},
  tl: ${P.tl}, tip: ${P.tip},
  romanSize: ${P.romanSize}, romanFill: ${P.romanFill}, romanOpacity: ${P.romanOpacity},
  romanTrack: ${P.romanTrack},
} as const

/** The block at kanji ${REF}, and the viewBox every drawing below is expressed in. */
export const BLOCK = { w: ${measured.w}, h: ${measured.h}, ref: ${REF} } as const

/** The tracking the width-match solved, as a fraction of the kanji size. Section 13's
 *  \`romanTrack\` 0.14 is the SEED the solve starts from, not this; the solve overwrites it. */
export const ROMAN_TRACK_SOLVED = ${R(measured.track)}

/** 番地 — IBM Plex Sans JP 400, outlined at kanji ${REF} with the 0.07em tracking \`stamp\` sets. */
export const KANJI_PATH = '${KANJI_D}'

/** BANCHI — Manrope 700 at ${P.romanSize} of the kanji, tracked to ${P.romanFill} of its advance. */
export const ROMAN_PATH = '${ROMAN_D}'

/** The bracket, as \`frame()\` drew it: a tapered filled outline plus a disc at each free end.
 *  Not a stroked path — section 6's taper cannot be stroked, which is why the mark's SMALL cut
 *  is 52 bytes and this is not.
 *  EVERY \`fill\` IS STRIPPED so the component's own \`<g>\` supplies it by inheritance and CSS can
 *  switch it per theme. A \`fill\` attribute on the child would beat an inherited value, so baking
 *  one here would make section 16's dark metal unreachable from a stylesheet. */
export const BRACKET_ARM = '${round3(armPath[1])}'
export const BRACKET_CAPS = ${JSON.stringify(caps)} as const
export const BRACKET_SPIN = '${spin[1]}'
`

writeFileSync(OUT, ts)
console.log('build-lockup: wrote app/src/kit/lockupGeometry.ts')
console.log(`  block ${measured.w} x ${measured.h} at kanji ${REF} · tracking solved to ${R(measured.track)}`)
console.log(`  kanji ${KANJI_D.length} bytes · roman ${ROMAN_D.length} bytes · bracket arm ${armPath[1].length} bytes`)
console.log(`  outlines vs live text: ${compare.off} of ${compare.ink} inked pixels differ (${compare.pct}%)`)
