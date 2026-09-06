// How much ink survives at the floor size.  node ink.mjs <sheet.html>
//
// An opacity is the one parameter here whose failure is not a matter of taste: past some point
// the letterforms stop being carried by enough pixels to read. The eye can see that and cannot
// quantify it, so this does -- at deviceScaleFactor 1, the pixels a 1x display actually gets.
//
// IT REPORTS A SWEEP OF THRESHOLDS AND THE PEAK, NEVER ONE CUTOFF. The first version counted
// pixels at or above a distance of 64 from the ground and reported "0% strong" for alpha 0.27 on
// the dark ground -- which reads as a collapse and is nothing of the kind: that specimen's peak
// is 61, three units under the cutoff, and the underlying curve is smooth and monotonic. A single
// threshold manufactures a cliff wherever a value lands just beneath it, and a cliff is exactly
// the kind of finding that gets believed.
import { chromium } from '/Users/shivinate/Developer/pkmnscan/.claude/worktrees/logo-specs-integration-85265a/app/node_modules/playwright/index.mjs'
const b = await chromium.launch()
const p = await b.newPage({ viewport:{width:1400,height:1200}, deviceScaleFactor:1 })
await p.goto('file://'+process.argv[2])
await p.waitForFunction(()=>window.__sheetReady===true,null,{timeout:20000}).catch(()=>{})
const pageH = await p.evaluate(()=>document.documentElement.scrollHeight)
await p.setViewportSize({width:1400,height:Math.min(pageH+40,12000)})

for (const [name, strip] of [['light',1],['dark',3]]) {
  const boxes = await p.evaluate((i)=>{
    const s=document.querySelectorAll('.strip')[i]
    return [...s.querySelectorAll('.lk')].map(lk=>{
      const r=lk.querySelector('.r').getBoundingClientRect()
      return {v:JSON.parse(lk.dataset.used).romanOpacity,
              x:Math.floor(r.left), y:Math.floor(r.top+scrollY),
              w:Math.ceil(r.width), h:Math.ceil(r.height)}})}, strip)
  const rows=[]
  for (const bx of boxes) {
    const png = await p.screenshot({clip:{x:bx.x,y:bx.y,width:bx.w,height:bx.h}})
    const st = await p.evaluate(async ({b64})=>{
      const img=new Image(); await new Promise(r=>{img.onload=r;img.src='data:image/png;base64,'+b64})
      const c=document.createElement('canvas'); c.width=img.width; c.height=img.height
      const x=c.getContext('2d'); x.drawImage(img,0,0)
      const d=x.getImageData(0,0,c.width,c.height).data
      // the ground is the modal corner pixel; measure every pixel's distance from it
      const g=[d[0],d[1],d[2]]
      /* A SINGLE THRESHOLD IS A CLIFF THIS MEASUREMENT DOES NOT HAVE. Report the peak distance
         and a sweep of thresholds, so a value landing one unit under a cutoff reads as one unit
         under rather than as a collapse. */
      let peak=0, sum=0, n=0
      const bands=[16,32,48,64,80,96]
      const counts=bands.map(()=>0)
      for(let i=0;i<d.length;i+=4){
        const dist=(Math.abs(d[i]-g[0])+Math.abs(d[i+1]-g[1])+Math.abs(d[i+2]-g[2]))/3
        n++; sum+=dist; if(dist>peak) peak=dist
        bands.forEach((t,j)=>{ if(dist>=t) counts[j]++ })
      }
      return {n, peak:Math.round(peak), mean:+(sum/n).toFixed(1), bands, counts}
    }, {b64: png.toString('base64')})
    rows.push({v:bx.v, ...st})
  }
  console.log('\n' + name + ' ground, kanji 32 — peak ink distance from the ground, and how many')
  console.log('pixels reach each level (the letterforms touch ~140 pixels):')
  console.log('  alpha   peak  mean | ' + rows[0].bands.map(t=>('>='+t).padStart(5)).join(''))
  for (const r of rows)
    console.log('  ' + String(r.v).padEnd(7) + String(r.peak).padStart(4) +
                String(r.mean).padStart(6) + ' | ' + r.counts.map(c=>String(c).padStart(5)).join(''))
}
await b.close()
