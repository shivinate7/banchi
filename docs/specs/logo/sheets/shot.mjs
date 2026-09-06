// Render a sheet to PNG at 2x.  node shot.mjs <src.html> <out.png> <w> <h>
//
// Playwright is resolved RELATIVE to this file rather than by an absolute path into one
// person's home directory. The absolute form worked from the main checkout and from a
// worktree only because the main checkout happened to have node_modules installed; from
// any other clone it resolved to nothing. That is D47's class of defect — a path baked
// into the tree — in a file whose whole job is to be re-runnable later.
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const playwright = resolve(here, '../../../../app/node_modules/playwright/index.mjs')
const { chromium } = await import(pathToFileURL(playwright).href)

const [, , src, out, w, h, dsf] = process.argv
// deviceScaleFactor defaults to 2, which is right for reading a sheet and WRONG for judging a floor:
// section 9's small row was shot at 2 and so showed twice the detail a 1x display gets, in the one
// row whose whole job was to demonstrate a failure. Pass 1 to see what a 1x screen actually renders.
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: dsf ? +dsf : 2 })
await p.goto('file://' + src)

// A sheet that rasterizes into a canvas is not finished when load fires. Such a sheet sets
// `window.__sheetReady = false` at the top and `true` when it is done; every sheet that does
// not is `undefined` here and passes on the first evaluation, so the nine that predate this
// are unaffected.
await p.waitForFunction(() => window.__sheetReady !== false, { timeout: 30000 }).catch(() => {
  console.error('shot.mjs: window.__sheetReady never went true — shooting anyway')
})
await p.waitForTimeout(300)
await p.screenshot({ path: out, fullPage: true })
await b.close()
