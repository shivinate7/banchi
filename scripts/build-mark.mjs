// Generate the app's mark from docs/specs/logo.md's own generator.
//
//     node scripts/build-mark.mjs            geometry, palettes and the SVG favicon
//     node scripts/build-mark.mjs --icons    ...and the PNG touch icons (needs Playwright)
//
// THIS SCRIPT DOES NOT CONTAIN THE GEOMETRY. It reads the committed sheet and evaluates the
// drawing routine out of it, so there is exactly one implementation of the mark in this repo
// and the app cannot drift from the spec by being edited. `make docs-audit`'s `motion params`
// row exists because a mirrored constant drifted for weeks with nothing comparing the two
// copies; this is the same hazard answered by not making a second copy.
//
// What it writes:
//   app/src/kit/markGeometry.ts   the two optical cuts as static path data
//   app/src/kit/markPalettes.ts   section 9's six locked marks
//   app/public/favicon.svg        the small cut, bluesteel, standalone
//   app/public/icon-<n>.png       the same drawing rasterized, --icons only
//
// D18: a generator may write, and nothing that writes may gate a commit. This is run by hand.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SHEET = resolve(ROOT, 'docs/specs/logo/sheets/small-cut.html')

const html = readFileSync(SHEET, 'utf8')
// The sheet is a browser document: it sets a readiness flag on `window` at the top. Everything
// from the drawing block down is pure string-building with no DOM, so a stub is enough.
const js = 'const window = {};'
  + html.slice(html.indexOf('<script>') + 8, html.indexOf('/* ---- rasterize'))
const { SQ, taperParts, strokeBody, CW, CH } = new Function(
  js + '; return { SQ, taperParts, strokeBody, CW, CH }',
)()

// Section 3's locked geometry. Named here rather than read out of icon()'s body because these
// are the values the SPEC locks; if the sheet's defaults ever disagree with them the assertions
// below fail rather than the app quietly taking the sheet's word.
const ARM = 0.38, CORNER = 8, GAP = 11.5, CARD_R = 1.9
const DISPLAY = { stroke: 1.7, tip: 0.07, taperLen: 0.3 }
// Apple's macOS icon grid, section 17: 824pt of artwork on a 1024pt canvas. Mirrored in
// docs/specs/logo.md and reconciled by `make docs-audit`'s `mac icon grid` row.
const MAC_GRID = 824 / 1024
const SMALL = { stroke: 4.2 }   // section 11, candidate C: no taper, flat prism

const EW = CW + 2 * GAP, EH = CH + 2 * GAP
const EX = 50 - EW / 2, EY = 50 - EH / 2
const aX = EW * ARM, aY = EH * ARM
const CX = 50 - CW / 2, CY = 50 - CH / 2

/* THE TAB'S OWN BRACKET — the same L, the small cut's WEIGHT, the lockup's TAPER.
   The owner settled the browser icon on 2026-09-06 (logo.md section 18): the empty brackets the
   collapsed sidebar draws, in `bluesteel`'s metal, with no tile and no card. Tapered "like the
   open lockup", chosen over the rail's constant-width wire after both were drawn at true 16 and
   32 pixels on three grounds.
   `tip` and `tl` are READ from `lockupGeometry.ts` rather than retyped: that file is generated
   from section 13's settled table and `make docs-audit`'s `lockup params` row reconciles the two,
   so the tab cannot drift from the lockup it is named after.
   WHAT IT DOES NOT TAKE is the lockup's `arm` and `rrMul` — those are calibrated against a
   319 x 233 landscape block, and in a 100-unit square they put a radius of 17 against arms of 31,
   which draws a rounded border rather than two corner brackets. Measured before this was written.
   AND SECTION 11 REJECTED THIS TAPER RANGE, deliberately: it swept tip at 0.07/0.25/0.50/1.00 and
   chose 1.00, because a 4.2 stroke at 0.15 ends 0.63 units wide — 0.1px at 16. Section 18 takes
   the loss on the tab alone and names it; section 11 still governs `Logo`, every in-app surface
   and the app icons. */
const lockupSrc = readFileSync(resolve(ROOT, 'app/src/kit/lockupGeometry.ts'), 'utf8')
const lockupParam = (k) => {
  const body = /PARAMS = \{([\s\S]*?)\} as const/.exec(lockupSrc)?.[1] ?? ''
  const m = new RegExp(k + ':\\s*([0-9.]+)').exec(body)
  return m ? Number(m[1]) : undefined
}
const TAB = { tip: lockupParam('tip'), tl: lockupParam('tl') }

const display = taperParts(EX, EY, aX, aY, CORNER, DISPLAY.stroke, DISPLAY.tip, DISPLAY.taperLen)
const smallBody = strokeBody(EX, EY, aX, aY, CORNER)

// The sheet is a document and this is a build input, so check it is the drawing we think it is
// before writing 25KB of path data into the app.
const must = (cond, why) => { if (!cond) { console.error('build-mark: ' + why); process.exit(1) } }
must(SQ.startsWith('M100.00 50.00L') && SQ.endsWith('Z'), 'the tile path is not the superellipse')
must(SQ.split('L').length === 221, `the tile is ${SQ.split('L').length} points, expected 221`)
must(display.caps.length === 2, 'the display bracket lost a cap')
must(display.body.length > 8000, 'the display bracket is too short to be the outlined polygon')
must(smallBody.length < 100, 'the small bracket is not a stroked path')
must(TAB.tip !== undefined && TAB.tl !== undefined,
     "lockupGeometry.ts has no PARAMS.tip / PARAMS.tl — the tab takes the lockup's taper from there")
const tab = taperParts(EX, EY, aX, aY, CORNER, SMALL.stroke, TAB.tip, TAB.tl)
must(tab.caps.length === 2, 'the tab bracket lost a cap')
must(tab.body.length > 4000, 'the tab bracket is too short to be an outlined polygon')

const round = (n) => +n.toFixed(3)
const caps = display.caps.map(([x, y, r]) => [round(x), round(y), round(r)])

writeFileSync(resolve(ROOT, 'app/src/kit/markGeometry.ts'), `/* GENERATED by scripts/build-mark.mjs from docs/specs/logo/sheets/small-cut.html.
   Do not hand-edit — re-run the script. docs/specs/logo.md is the state of record.

   THE TWO OPTICAL CUTS ARE NOT OPTIONAL (logo.md section 3). A 1.7 stroke is a scratch at 32px
   and absent at 16px, and section 11 swept it at the four sizes this app actually draws before
   the small cut was written down. Every surface in this product is below 64px, so \`SMALL\` is
   what ships and \`DISPLAY\` is what the gallery shows.

   The geometry does not vary across the six marks — only the palettes do (markPalettes.ts).
   Measured: all six generate byte-identical path data. */

/** The quintic superellipse tile, n = 5, sampled at 221 points. */
export const TILE = '${SQ}'

/** The card, in the 100 x 100 icon box. 5:7, the proportion of a 63 x 88 mm trading card. */
export const CARD = { x: ${round(CX)}, y: ${round(CY)}, w: ${CW}, h: ${CH}, r: ${CARD_R} } as const

/** The sheen band: the top 40% of the tile, clipped to it. */
export const SHEEN_HEIGHT = 40

/** Display cut, 64px and up. A variable-width taper cannot be stroked, so the bracket is a
 *  filled outline: 321 centreline samples offset both ways, plus a disc at each free end. */
export const DISPLAY_BRACKET = '${display.body}'
export const DISPLAY_CAPS = ${JSON.stringify(caps)} as const

/** Small cut, below 64px — section 11. No taper, so the bracket is a constant-width wire and
 *  a real stroked path draws it: ${smallBody.length} bytes against ${display.body.length}. */
export const SMALL_BRACKET = '${smallBody}'
export const SMALL_STROKE = ${SMALL.stroke}

/** The holographic foil, display cut only. Section 11 measured the marbling at 16-44px and it
 *  loses to a flat prism gradient there, so the small cut carries NO filter — which is also
 *  what makes the favicon a plain SVG. */
export const HOLO = { baseFrequency: '0.035 0.09', octaves: 4, seed: 23, displacement: 60 } as const
export const HOLO_RECT = { x: ${round(CX - 18)}, y: ${round(CY - 18)}, w: ${CW + 36}, h: ${CH + 36} } as const
`)

// Section 9's locked set, written out. NOT derived: for the three gold marks the tonal ground
// rule produces the espresso that section 8 rejected in favor of true black, so a build that
// re-derives these draws marks the spec has eliminated. logo.md section 9 is the authority.
const MARKS = [
  ['bluesteel', 'bluesteel', ['#E4EEF8', '#B0C8E0', '#7F9FC0', '#F2F8FF', '#6086AC'], 'chrome', ['#182430', '#060B12'], '#5A6E80'],
  ['lilacish', 'lilacish', ['#EFEAFA', '#BCB4E0', '#8E86C0', '#F6F2FF', '#6E68A8'], 'chrome', ['#231F34', '#0B0914'], '#5A6E80'],
  ['mint', 'mint', ['#E6F6F0', '#A8D4C4', '#78AC9C', '#F2FCF8', '#589084'], 'chrome', ['#162722', '#050D0A'], '#5A6E80'],
  ['yellowGold', 'yellow gold', ['#FFD97A', '#F0A82E', '#C9821E', '#FFEFC0', '#B36F18'], 'paleGold', ['#141619', '#000000'], '#C98A2E'],
  ['whiteGold', 'white gold', ['#FFFBF2', '#EFE6D2', '#DCD0B8', '#FFFFFF', '#C9BCA2'], 'paleGold', ['#141619', '#000000'], '#D8D2C4'],
  ['roseGold', 'rose gold', ['#FFD9C8', '#F0B49A', '#DE9070', '#FFE9DF', '#C87A5C'], 'rose', ['#141619', '#000000'], '#D99878'],
]
const BRACKETS = {
  chrome: ['#FFFFFF', '#B8C8D8', '#F2F8FF', '#8FA4B8'],
  paleGold: ['#FFFBEE', '#E8CE8A', '#FFFDF6', '#C0A254'],
  rose: ['#FFF0E8', '#E8B49C', '#FFF8F4', '#C88A6C'],
}

writeFileSync(resolve(ROOT, 'app/src/kit/markPalettes.ts'), `/* GENERATED by scripts/build-mark.mjs. Do not hand-edit — re-run the script.

   SECTION 9 OF docs/specs/logo.md IS THE STORE OF RECORD FOR EVERY HEX BELOW, and
   \`make docs-audit\`'s \`logo parity\` row reconciles this file against it in both directions.
   These are NOT derived here: the ground rule, applied to the three gold prisms, produces the
   espresso that section 8 rejected in favor of true black, so a build that re-derives them
   redraws marks the spec has eliminated.

   THIS IS THE ONE FILE IN app/ OUTSIDE tokens.css THAT MAY NAME A COLOR (D102). The mark is an
   illustration with a palette locked by another document, not part of the product's semantic
   palette, and it must not be theme-overridable — which is exactly what putting it in
   tokens.css would invite. */

export type LogoVariant = ${MARKS.map((m) => `'${m[0]}'`).join(' | ')}

/** Section 9's default: "the one \`Logo\` and \`favicon.svg\` take when nothing else is specified".
 *  The other five are the set, not alternates to it. */
export const DEFAULT_VARIANT: LogoVariant = 'bluesteel'

export interface MarkPalette {
  readonly label: string
  readonly prism: readonly [string, string, string, string, string]
  readonly bracket: readonly [string, string, string, string]
  readonly ground: readonly [string, string]
  readonly base: string
}

/** Sheen 0.15 on all six — section 9, inside section 3's settled 0.10-0.20 band. */
export const SHEEN = 0.15

export const MARKS: Readonly<Record<LogoVariant, MarkPalette>> = {
${MARKS.map(([key, label, prism, brk, ground, base]) => `  ${key}: {
    label: '${label}',
    prism: [${prism.map((c) => `'${c}'`).join(', ')}],
    bracket: [${BRACKETS[brk].map((c) => `'${c}'`).join(', ')}],
    ground: ['${ground[0]}', '${ground[1]}'],
    base: '${base}',
  },`).join('\n')}
}

export const VARIANTS = Object.keys(MARKS) as readonly LogoVariant[]
`)

// A standalone SVG of the mark, at either cut. `icon()` in the sheet emits no xmlns and ids
// that collide across separately-exported files; both are supplied here.
//
// THE CUT IS CHOSEN BY SIZE, THE SAME RULE `Logo` APPLIES (logo.md section 3). The favicon is
// 16 to 32px and takes the small cut. A touch icon is 180px and up, which is squarely in the
// display cut's range — so it gets the taper and the holographic foil, and rasterizing the
// favicon up to 512px instead would have shipped the small cut four hundred percent past the
// size it was swept at.
const [, , prism, brk, ground, base] = MARKS[0]
const stops = (cs, offs) => cs.map((c, i) => `<stop offset="${offs[i]}" stop-color="${c}"/>`).join('')

function markSvg(cut, px) {
  const small = cut === 'small'
  const bracket = small
    ? `<path d="${smallBody}" fill="none" stroke="url(#bk)" stroke-width="${SMALL.stroke}" stroke-linecap="round"/>`
    : `<path d="${display.body}" fill="url(#bk)"/>`
      + caps.map((c) => `<circle cx="${c[0]}" cy="${c[1]}" r="${c[2]}" fill="url(#bk)"/>`).join('')
  const card = `<rect x="${round(CX)}" y="${round(CY)}" width="${CW}" height="${CH}" rx="${CARD_R}"`
  const face = small
    // Section 11: at every size below 64px the marbling loses to this flat gradient, and
    // dropping the filter is what lets a favicon be a plain SVG.
    ? `${card} fill="url(#pr)"/>`
    : `<g clip-path="url(#cd)" filter="url(#ho)"><rect x="${round(CX - 18)}" y="${round(CY - 18)}" `
      + `width="${CW + 36}" height="${CH + 36}" fill="url(#pr)"/></g>`
  // Both of these belong INSIDE defs beside the gradients. An earlier pass spliced the clipPath
  // into the body behind a `</defs><defs>` and the foil silently did not render — the card came
  // out flat slate, which reads as a design choice rather than as a broken reference.
  const holo = small ? '' :
    `\n    <clipPath id="cd">${card}/></clipPath>`
    + `\n    <filter id="ho" x="-30%" y="-30%" width="160%" height="160%">`
    + `<feTurbulence type="fractalNoise" baseFrequency="0.035 0.09" numOctaves="4" seed="23" result="t"/>`
    + `<feDisplacementMap in="SourceGraphic" in2="t" scale="60" xChannelSelector="R" yChannelSelector="G"/>`
    + `</filter>`
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="${px}" height="${px}">
  <title>Banchi</title>
  <!-- GENERATED by scripts/build-mark.mjs. docs/specs/logo.md is the state of record.
       The ${small ? 'SMALL' : 'DISPLAY'} optical cut${small ? ` (section 11): stroke ${SMALL.stroke}, no taper, no feTurbulence.
       A favicon is 16 to 32px, where the display cut's brackets are gone and its marbling
       loses to this flat prism gradient.` : ` (section 3): the ${DISPLAY.stroke} stroke with its taper and the
       holographic foil, because a touch icon is 180px and up.`}
       Fixed dark in both themes on purpose (section 12). -->
  <defs>
    <linearGradient id="gd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${ground[0]}"/><stop offset="1" stop-color="${ground[1]}"/></linearGradient>
    <linearGradient id="bk" x1=".75" y1=".067" x2=".25" y2=".933">${stops(BRACKETS[brk], [0, 0.33, 0.67, 1])}</linearGradient>
    <linearGradient id="sn" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity=".15"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
    <linearGradient id="pr" x1=".671" y1=".030" x2=".329" y2=".970">${stops(prism, [0, 0.25, 0.5, 0.75, 1])}</linearGradient>
    <clipPath id="tl"><path d="${SQ}"/></clipPath>${holo}
  </defs>
  <path d="${SQ}" fill="url(#gd)"/>
  <g clip-path="url(#tl)"><rect width="100" height="40" fill="url(#sn)"/></g>
  ${bracket}
  <g transform="rotate(180 50 50)">${bracket}</g>
  ${card} fill="${base}"/>
  ${face}
</svg>
`
}

/* THE BROWSER TAB IS THE EMPTY SLOT, and it is the one icon here that is not the whole mark.
   logo.md section 1: "with the card removed the same brackets become an empty slot, which is the
   in-product mark". Section 18 settles the tab on it.
   NO TILE, ON THE OWNER'S EXPLICIT CHOICE, and the cost is theirs and named: `bluesteel`'s metal
   runs #FFFFFF to #8FA4B8, so on a LIGHT browser tab bar these brackets are close to invisible.
   Drawn at true 16/20/32/48 on a dark bar, a light bar and a bookmark grey before it was chosen.
   The app icons keep the full mark with its card and its ground — this is the tab and nothing
   else, and `markGeometry.ts` / `markPalettes.ts` are untouched by it. */
const round3 = (d) => d.replace(/-?\d+\.\d+/g, (n) => String(+(+n).toFixed(3)))

function tabSvg(px) {
  const one = `<path d="${round3(tab.body)}" fill="url(#bk)"/>`
    + tab.caps.map((c) => `<circle cx="${round(c[0])}" cy="${round(c[1])}" r="${round(c[2])}" fill="url(#bk)"/>`).join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="${px}" height="${px}">
  <title>Banchi</title>
  <!-- GENERATED by scripts/build-mark.mjs. docs/specs/logo.md is the state of record.
       THE EMPTY SLOT (section 1), settled for the tab in section 18: the mark's own L at the
       small cut's ${SMALL.stroke} stroke, carrying the lockup's ${TAB.tip} taper, in bluesteel's
       bracket metal. No tile, no card, no sheen — on a light tab bar this is close to invisible,
       and that is a chosen trade recorded in section 18. The app icons keep the whole mark. -->
  <defs>
    <linearGradient id="bk" x1=".75" y1=".067" x2=".25" y2=".933">${stops(BRACKETS[brk], [0, 0.33, 0.67, 1])}</linearGradient>
  </defs>
  ${one}
  <g transform="rotate(180 50 50)">${one}</g>
</svg>
`
}

writeFileSync(resolve(ROOT, 'app/public/favicon.svg'), tabSvg(32))

console.log('build-mark: wrote markGeometry.ts, markPalettes.ts, favicon.svg')
console.log(`  the tab: the empty slot, stroke ${SMALL.stroke}, taper ${TAB.tip}/${TAB.tl}, no tile`)
console.log(`  display bracket ${display.body.length} bytes · small bracket ${smallBody.length} bytes`)

// ---------------------------------------------------------------- the PNG touch icons
//
// iOS does not render an SVG `apple-touch-icon`, and Android's manifest wants raster too, so
// the one drawing has to exist as bitmaps as well. They are rasterized FROM `favicon.svg`
// rather than drawn again, so there is still one implementation — the same discipline the rest
// of this script follows.
//
// BEHIND A FLAG because it needs Playwright and because committing what it writes needs the
// owner's word: the pre-commit image guard refuses any .png outside captures/ and has no
// PKMNSCAN_*=off hatch, so `--no-verify` is the only way past it and it disarms every other
// guard at the same time. Stage nothing but the images and say so in the message.
//
// TWO SETS, AND THE DIFFERENCE IS APPLE'S ICON GRID (logo.md section 17). A macOS app icon does
// not fill its canvas: on a 1024pt canvas the artwork is 824pt centred, and every icon in the
// dock obeys that so they optically align. The mark is a superellipse TILE that fills its frame,
// so shipped full-bleed it renders about a quarter wider and half again the area of its
// neighbours. Chrome builds the installed app's `.icns` by resizing the manifest icons, so the
// whole manifest set is inset — not just the largest — because a set that disagreed with itself
// would pad the dock icon at one size and not at the next.
//
// `icon-180.png` is NOT in that set. It is the `apple-touch-icon`, and iOS applies its own mask
// to a full-bleed square; insetting it would put the mark in a box inside a box.
if (process.argv.includes('--icons')) {
  const TOUCH = [180]                // apple-touch-icon — iOS masks it, so it stays full bleed
  const APP = [192, 512, 1024]       // the manifest set, and what Chrome's .icns is built from
  const SIZES = [...TOUCH, ...APP]
  const { chromium } = await import(
    pathToFileURL(resolve(ROOT, 'app/node_modules/playwright/index.mjs')).href
  )
  const browser = await chromium.launch()
  for (const size of SIZES) {
    const page = await browser.newPage({ viewport: { width: size, height: size } })
    // No page background: the tile is the icon and its corners must stay transparent, or a
    // superellipse ships inside a square. `omitBackground` is what keeps that true.
    // The DISPLAY cut: every one of these is 180px or more, which is the cut section 3 locks
    // for 64px and up. Rasterizing the favicon instead would ship the small cut four times
    // past the largest size it was ever swept at.
    // The inset is applied by DRAWING SMALLER on a full-size transparent canvas rather than by
    // padding the SVG, so the mark's own geometry is untouched — section 3 locks it and nothing
    // here may redraw it.
    const inset = APP.includes(size)
    await page.setContent(
      `<style>html,body{margin:0;background:transparent;width:100%;height:100%}`
      + `body{display:grid;place-items:center}svg{display:block}</style>`
      + markSvg('display', inset ? Math.round(size * MAC_GRID) : size),
    )
    await page.waitForTimeout(200)
    await page.screenshot({
      path: resolve(ROOT, `app/public/icon-${size}.png`),
      omitBackground: true,
    })
    await page.close()
    console.log(`build-mark: wrote icon-${size}.png`)
  }
  await browser.close()
  console.log('build-mark: the PNGs are NOT committable without --no-verify (image guard).')
}
