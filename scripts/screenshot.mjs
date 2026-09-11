#!/usr/bin/env node
// One headless render, and the proof that it is complete. Driven by scripts/screenshot.sh,
// which owns the manifest loop and every message a person reads; this file owns the browser.
//
// WHY THIS EXISTS AT ALL: `make screenshot` could only ever fail one way — no PNG on disk.
// A render MISSING AN ELEMENT writes a perfectly valid, non-empty PNG, so the check passed
// and a session looked at an incomplete page and concluded a screen was fine. That is the
// defect. The transform-below-the-fold report this was built from is one instance of a class:
// a render that cannot detect its own incompleteness.
//
// WHY NODE AND NOT THE PLAYWRIGHT CLI. screenshot.sh used `npx playwright@<pin> screenshot`,
// and its header argues the pin: two Playwright versions in one repo is two browser downloads
// and two behaviours. That argument is why this file drives `app/node_modules`'s
// @playwright/test — the SAME pinned copy `make design-check` runs — rather than adding a
// second one. It removes a version surface rather than adding one: nothing is downloaded here.
// The cost is real and is stated in screenshot.sh's guard: `make screenshot` now needs
// `npm --prefix app install`, which the Makefile's NPM_GUARD already required of this target.
// EXPECTED_PLAYWRIGHT is checked against app/package.json below, so the pin is now MECHANICAL
// where it used to be a comment in two files hoping to stay in step.
//
// WHY `fullPage` SURVIVED. The report this was built from proposed replacing it: measure
// `document.documentElement.scrollHeight`, `setViewportSize` to it, screenshot without
// `fullPage`. Measured on this tree at the pinned 1.55.1, both halves of that came out wrong:
//
//   the defect did not reproduce   a rotated element below the fold renders correctly under
//                                  `--full-page`, synthetically and on `#/`'s own deck, whose
//                                  three cards carry rotate(-9deg)/(-4deg)/(3deg)
//   the remedy breaks this app     the shell is `min-height: 100dvh` (App.css:8), so growing
//                                  the viewport GROWS THE DOCUMENT: `#/` 944 -> 988, `#/capture`
//                                  1101 -> 1189, `#/gallery` 18810 -> 18854. A shot sized to the
//                                  pre-resize height then crops the bottom 44px, silently —
//                                  the very failure this file exists to end. Every vh-derived
//                                  size renders wrong besides: `#/review`'s photo is
//                                  `calc(100dvh - chrome)` and `#/capture`'s stage is
//                                  `calc(100dvh - --cap-chrome)`.
//
// So the sizing is unchanged and the CHECK is what is new. If a future Playwright does lose
// paint under `captureBeyondViewport`, the `--require` proof below is what will say so, by
// name and with a non-zero exit, instead of writing a plausible-looking picture.
//
//   node scripts/screenshot.mjs --url <url> --out <path> [--viewport WxH] [--wait-ms N]
//                               [--require <selector>[,<selector>...]]

import { createRequire } from 'node:module'
import { inflateSync } from 'node:zlib'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import fs from 'node:fs'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function fail(message, hint) {
  process.stderr.write(`screenshot: ${message}\n`)
  if (hint) process.stderr.write(`  Fix: ${hint}\n`)
  process.exit(1)
}

// ------------------------------------------------------------------ arguments

const args = { viewport: '1280,900', 'wait-ms': '600', require: '' }
for (let i = 2; i < process.argv.length; i += 2) {
  const key = process.argv[i]
  if (!key.startsWith('--')) fail(`unexpected argument \`${key}\``)
  args[key.slice(2)] = process.argv[i + 1] ?? ''
}
if (!args.url || !args.out) fail('--url and --out are both required')

const [vw, vh] = args.viewport.split(/[,x]/).map(Number)
if (!vw || !vh) fail(`--viewport ${args.viewport} is not <width>,<height>`)
const waitMs = Number(args['wait-ms'])
const required = args.require.split(',').map((s) => s.trim()).filter(Boolean)

// ------------------------------------------------------------------ the pin

// The one-version rule, read rather than restated. screenshot.sh carries the same constant
// for its error messages; app/package.json is the tree's actual answer, and disagreement
// between them is the drift the old pair of comments could only ask for politely.
const appPackage = JSON.parse(fs.readFileSync(resolve(ROOT, 'app/package.json'), 'utf8'))
const installed = appPackage.devDependencies?.['@playwright/test']
if (process.env.EXPECTED_PLAYWRIGHT && installed !== process.env.EXPECTED_PLAYWRIGHT) {
  fail(
    `app/package.json pins @playwright/test ${installed}, scripts/screenshot.sh pins ` +
      `${process.env.EXPECTED_PLAYWRIGHT}. Two Playwright versions in one repo is two ` +
      `behaviours; this render would not be the one make design-check measures.`,
    'bump both together or neither',
  )
}

const require_ = createRequire(import.meta.url)
let chromium
try {
  ;({ chromium } = require_(resolve(ROOT, 'app/node_modules/@playwright/test')))
} catch {
  fail('app/ dependencies are not installed.', 'npm --prefix app install')
}

// ------------------------------------------------------------------ PNG

/** Decode an 8-bit non-interlaced PNG, keeping only the pixels inside `rects`.
 *
 * Playwright writes exactly that shape, and the alternative to sixty lines here is a
 * dependency in a repo that deliberately has almost none. Anything else THROWS rather than
 * guessing — a check that silently mis-reads its own evidence is the disease, not the cure.
 *
 * REGIONS RATHER THAN THE WHOLE IMAGE because `#/gallery` is 18,810px tall: decoded whole it
 * is 96 MB of RGBA to answer a question about three rectangles. Every row still has to be
 * walked — a PNG row is filtered against the one above it — but only the wanted slices are
 * kept.
 */
function decodePngRegions(buffer, rects) {
  if (buffer.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') throw new Error('not a PNG')
  let offset = 8
  let width = 0
  let height = 0
  let channels = 0
  const idat = []
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset)
    const type = buffer.subarray(offset + 4, offset + 8).toString('ascii')
    const body = buffer.subarray(offset + 8, offset + 8 + length)
    if (type === 'IHDR') {
      width = body.readUInt32BE(0)
      height = body.readUInt32BE(4)
      const depth = body[8]
      const color = body[9]
      const interlace = body[12]
      if (depth !== 8 || interlace !== 0) {
        throw new Error(`unsupported PNG: depth ${depth}, interlace ${interlace}`)
      }
      channels = { 0: 1, 2: 3, 4: 2, 6: 4 }[color]
      if (!channels) throw new Error(`unsupported PNG color type ${color}`)
    } else if (type === 'IDAT') {
      idat.push(body)
    } else if (type === 'IEND') {
      break
    }
    offset += 12 + length
  }

  const raw = inflateSync(Buffer.concat(idat))
  const stride = width * channels
  const crops = rects.map((r) => ({
    rect: r,
    pixels: Buffer.alloc(Math.max(0, r.width * r.height * channels)),
  }))
  let prior = Buffer.alloc(stride)
  let line = Buffer.alloc(stride)
  let read = 0
  for (let y = 0; y < height; y++) {
    const filter = raw[read++]
    raw.copy(line, 0, read, read + stride)
    read += stride
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? line[x - channels] : 0
      const b = prior[x]
      const c = x >= channels ? prior[x - channels] : 0
      if (filter === 1) line[x] = (line[x] + a) & 255
      else if (filter === 2) line[x] = (line[x] + b) & 255
      else if (filter === 3) line[x] = (line[x] + ((a + b) >> 1)) & 255
      else if (filter === 4) {
        const p = a + b - c
        const pa = Math.abs(p - a)
        const pb = Math.abs(p - b)
        const pc = Math.abs(p - c)
        line[x] = (line[x] + (pa <= pb && pa <= pc ? a : pb <= pc ? b : c)) & 255
      } else if (filter !== 0) throw new Error(`unknown PNG filter ${filter}`)
    }
    for (const crop of crops) {
      const { x, y: top, width: w, height: h } = crop.rect
      if (y < top || y >= top + h) continue
      line.copy(crop.pixels, (y - top) * w * channels, x * channels, (x + w) * channels)
    }
    const swap = prior
    prior = line
    line = swap
  }
  return { width, height, channels, crops }
}

/** A PNG's dimensions, from IHDR alone — no inflate, no defilter. */
function pngSize(buffer) {
  if (buffer.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') throw new Error('not a PNG')
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) }
}

/** How many pixels differ between two same-sized RGB(A) buffers. */
function differingPixels(a, b, channels) {
  let differing = 0
  for (let at = 0; at < a.length; at += channels) {
    for (let c = 0; c < Math.min(3, channels); c++) {
      if (a[at + c] !== b[at + c]) {
        differing++
        break
      }
    }
  }
  return differing
}

// ------------------------------------------------------------------ the render

const browser = await chromium.launch().catch((error) => {
  fail(
    `chromium would not launch: ${error.message.split('\n')[0]}`,
    `npx playwright@${installed} install chromium`,
  )
})
const context = await browser.newContext({ viewport: { width: vw, height: vh } })
const page = await context.newPage()

const failures = []
const notes = []
try {
  await page.goto(args.url, { waitUntil: 'load' })
  await page.waitForTimeout(waitMs)

  // Where each required element sits in DOCUMENT space, which is the space a full-page
  // capture is in. A selector matching nothing is a failure and not a skip: a guard that
  // quietly passes when it cannot see its subject is the shape of every green check this
  // repo has caught lying.
  const boxes = await page.evaluate((selectors) =>
    selectors.map((selector) => {
      const found = [...document.querySelectorAll(selector)].map((el) => {
        const r = el.getBoundingClientRect()
        return { x: r.x + scrollX, y: r.y + scrollY, right: r.right + scrollX, bottom: r.bottom + scrollY }
      })
      const drawn = found.filter((r) => r.right > r.x && r.bottom > r.y)
      if (!drawn.length) return { selector, rect: null, matched: found.length }
      const x = Math.min(...drawn.map((r) => r.x))
      const y = Math.min(...drawn.map((r) => r.y))
      return {
        selector,
        matched: found.length,
        rect: {
          x,
          y,
          width: Math.max(...drawn.map((r) => r.right)) - x,
          height: Math.max(...drawn.map((r) => r.bottom)) - y,
        },
      }
    }), required)

  const shot = await page.screenshot({ fullPage: true })
  fs.mkdirSync(dirname(args.out), { recursive: true })
  fs.writeFileSync(args.out, shot)

  for (const box of boxes.filter((b) => !b.rect)) {
    failures.push(
      `\`${box.selector}\` ` +
        (box.matched
          ? `matched ${box.matched} element(s), every one of them zero-sized`
          : 'matched nothing on this page') +
        ' — this render cannot prove it drew that.',
    )
  }

  // Integer document-space rectangles, clamped to the image. The same numbers address the
  // captured PNG and Playwright's `clip`, so the two views of a region cannot drift apart by
  // a rounding rule.
  const png = pngSize(shot)
  const targets = []
  for (const box of boxes.filter((b) => b.rect)) {
    const x = Math.max(0, Math.floor(box.rect.x))
    const y = Math.max(0, Math.floor(box.rect.y))
    const width = Math.min(png.width, Math.ceil(box.rect.x + box.rect.width)) - x
    const height = Math.min(png.height, Math.ceil(box.rect.y + box.rect.height)) - y
    if (width <= 0 || height <= 0) {
      failures.push(
        `\`${box.selector}\` is laid out at ${Math.round(box.rect.width)}x` +
          `${Math.round(box.rect.height)} at ${Math.round(box.rect.x)},${Math.round(box.rect.y)}, ` +
          `outside the ${png.width}x${png.height} render.`,
      )
      continue
    }
    targets.push({ selector: box.selector, rect: { x, y, width, height } })
  }

  if (targets.length) {
    // THE PROOF: capture one required element's rectangle, hide that element, capture the
    // same rectangle again. Whatever the element contributes to a render is exactly what
    // changes. `visibility: hidden` rather than `display: none` on purpose — it holds the
    // layout still, so the second capture is the first one MINUS this element and nothing
    // else has moved.
    //
    // ONE ELEMENT AT A TIME, AND THAT IS NOT AN OPTIMISATION IN REVERSE. Hiding the whole
    // list at once was the first build of this and it passed a real mutation: `.home` is an
    // ancestor of `.home-deck-card-1`, so hiding both meant the ancestor's disappearance
    // supplied the pixels the descendant was supposed to prove, and a card forced to
    // `opacity: 0` still scored 91.8%.
    //
    // BOTH COMPARISON SHOTS FREEZE ANIMATION, AND THE ARTIFACT ON DISK DOES NOT. Measured on
    // this tree: two back-to-back captures of `#/`'s deck region are NOT byte-identical while
    // motion is live — the page animates, so a plain re-capture disagrees with itself and a
    // zero-tolerance floor would be meaningless. With `animations: 'disabled'` the same pair
    // is byte-identical on every region tried. So the proof is a controlled A/B over the same
    // capture path a moment later, rather than a diff against the bytes just written. What
    // that gives up is named: a defect that afflicts only the animated capture is invisible
    // to this. What it buys is a floor with nothing to tune.
    //
    // The floor is zero. If hiding an element changes not one pixel inside its own rectangle,
    // it painted nothing, which is precisely what a lost element looks like.
    for (const target of targets) {
      const shotOptions = { fullPage: true, clip: target.rect, animations: 'disabled' }
      const withElement = await page.screenshot(shotOptions)
      const style = await page.addStyleTag({
        content: `${target.selector} { visibility: hidden !important; }`,
      })
      const reflowed = await page.evaluate(() => document.documentElement.scrollHeight)
      const withoutElement = await page.screenshot(shotOptions)
      await style.evaluate((node) => node.remove())

      const where = `${target.rect.width}x${target.rect.height} at ${target.rect.x},${target.rect.y}`

      if (Math.abs(reflowed - png.height) > 1) {
        // `visibility: hidden` holds layout. A page that resizes anyway is reacting to its
        // own visibility, and the comparison below would be measuring the reflow.
        failures.push(
          `\`${target.selector}\` — hiding it moved the page from ${png.height}px to ` +
            `${reflowed}px. \`visibility: hidden\` holds layout, so this render's ` +
            `completeness cannot be read for that element.`,
        )
        continue
      }

      if (Buffer.compare(withElement, withoutElement) === 0) {
        failures.push(
          `\`${target.selector}\` is laid out at ${where} and painted NOTHING into this ` +
            `render — the file shows page background where that element is.`,
        )
        continue
      }

      // It painted. How MUCH is not a pass/fail question — 4.6% is a correct answer for a
      // heading and 97.6% for a card — but it is the number a person reads to notice that a
      // screen changed shape, so it is printed rather than swallowed.
      const before = decodePngRegions(withElement, [{ x: 0, y: 0, width: target.rect.width, height: target.rect.height }])
      const after = decodePngRegions(withoutElement, [{ x: 0, y: 0, width: target.rect.width, height: target.rect.height }])
      const differing = differingPixels(before.crops[0].pixels, after.crops[0].pixels, before.channels)
      const area = target.rect.width * target.rect.height
      notes.push(`${target.selector}: ${differing} px (${((differing / area) * 100).toFixed(1)}% of ${where})`)
    }
  }
} catch (error) {
  failures.push(error.message.split('\n')[0])
} finally {
  await browser.close()
}

for (const note of notes) process.stderr.write(`  ${note}\n`)

if (failures.length) {
  process.stderr.write(`screenshot: INCOMPLETE ${args.out} (${args.url})\n`)
  for (const line of failures) process.stderr.write(`  ${line}\n`)
  // Only when there is one. A render that never got past `goto` writes nothing, and telling
  // someone to go and look at a file that is not there is how a real error reads as two.
  if (fs.existsSync(args.out)) {
    process.stderr.write('  The PNG was kept: look at it, that is the evidence.\n')
  }
  process.exit(1)
}
