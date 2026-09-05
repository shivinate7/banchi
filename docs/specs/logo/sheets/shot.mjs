import { chromium } from '/Users/shivinate/Developer/pkmnscan/app/node_modules/playwright/index.mjs'
const [,, src, out, w, h] = process.argv
const b = await chromium.launch()
const p = await b.newPage({ viewport:{width:+w,height:+h}, deviceScaleFactor:2 })
await p.goto('file://'+src); await p.waitForTimeout(300)
await p.screenshot({ path: out, fullPage: true }); await b.close()
