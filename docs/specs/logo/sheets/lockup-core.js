/* THE LOCKUP'S DRAWING, IN ONE PLACE.
 *
 * IT EXISTS BECAUSE A SECOND COPY OF IT ALREADY COST A ROUND. `lockup-round.html` was generated
 * from `lockup-tails.html` at round 1 and then kept its own frozen copy of `frame()`. At round 6
 * the option being swept -- the corner radius -- did not exist in that copy, so every specimen
 * fell through to the same value and the row was six drawings of one bracket, presented as a
 * sweep. docs/specs/logo.md section 6 records the ancestor: "three images approved as different
 * were the same image."
 *
 * A sheet that draws the lockup and does not load this file is that bug coming back.
 *
 * `frame()` records every option it actually used on the element, so a sheet can assert that the
 * variables it claims to hold were held and that the one it claims to sweep actually moved.
 */
const SQ=(function(){const a=50,N=220,p=[]
 for(let i=0;i<=N;i++){const t=i/N*2*Math.PI,ct=Math.cos(t),st=Math.sin(t)
  p.push((a+a*Math.sign(ct)*Math.pow(Math.abs(ct),.4)).toFixed(2)+' '+(a+a*Math.sign(st)*Math.pow(Math.abs(st),.4)).toFixed(2))}
 return 'M'+p.join('L')+'Z'})()
function taperParts(x0,y0,aX,aY,r,w,tip,tlf){
 const L1=Math.max(aY-r,0),L2=r*Math.PI/2,L3=Math.max(aX-r,0),L=L1+L2+L3,N=300,pts=[]
 const tl=Math.min(tlf*Math.max(aX,aY),L/2)
 for(let i=0;i<=N;i++){const s=L*i/N;let x,y,tx,ty
  if(s<=L1){x=x0;y=y0+aY-s;tx=0;ty=-1}
  else if(s<=L1+L2){const th=Math.PI+(s-L1)/r;x=x0+r+r*Math.cos(th);y=y0+r+r*Math.sin(th);tx=-Math.sin(th);ty=Math.cos(th)}
  else{const d=s-L1-L2;x=x0+r+d;y=y0;tx=1;ty=0}
  const dE=Math.min(s,L-s);const f=dE<tl?tip+(1-tip)*(dE/tl):1
  pts.push({x:x,y:y,nx:-ty,ny:tx,w:Math.max(w*f,0.001)})}
 const q=function(v){return v.toFixed(3)}
 const out=pts.map(function(p){return q(p.x+p.nx*p.w/2)+' '+q(p.y+p.ny*p.w/2)})
 const inn=pts.map(function(p){return q(p.x-p.nx*p.w/2)+' '+q(p.y-p.ny*p.w/2)}).reverse()
 return {body:'M'+out[0]+out.slice(1).map(function(s){return 'L'+s}).join('')+
   'L'+inn[0]+inn.slice(1).map(function(s){return 'L'+s}).join('')+'Z',
  caps:[[pts[0].x,pts[0].y,pts[0].w/2],[pts[pts.length-1].x,pts[pts.length-1].y,pts[pts.length-1].w/2]]}}
let n=0
/* THE ROMAN'S THREE NUMBERS WERE LITERALS IN THIS LINE, and that is why nothing guarded them.
   `pad`, `gap`, `stroke`, `arm`, `rrMul`, `tip` and `tl` are all parameters, all published in
   the spec's settled table, and all reconciled against it by `make docs-audit`'s `lockup params`
   row. The roman's size ratio, tracking and opacity were typed into the markup instead -- so
   they could not be swept, could not be held, could not be asserted, and could not disagree
   with the spec in a way anything would notice. They are options now, with the recovered
   pass's values as defaults, so they answer to the same machinery as everything else. */
function stamp(size,gap,pd,col,o){
 o=o||{}
 const rs = o.romanSize===undefined ? 0.36 : o.romanSize
 const rt = o.romanTrack===undefined ? 0.14 : o.romanTrack
 const ro = o.romanOpacity===undefined ? 0.62 : o.romanOpacity
 const el=document.createElement('div');el.className='lk'
 el.style.padding=(size*pd).toFixed(2)+'px '+(size*pd*1.05).toFixed(2)+'px'
 el.innerHTML='<div style="color:'+(col||'#0f1217')+'">'+
  '<span class="go k" style="font-size:'+size+'px;letter-spacing:.07em">番地</span>'+
  '<span class="rom r" style="font-size:'+(size*rs).toFixed(2)+'px;letter-spacing:'+rt+'em;margin-top:'+(size*gap).toFixed(2)+'px;opacity:'+ro+'">BANCHI</span></div>'
 Object.assign(el.dataset,{size:size,col:col||'#0f1217',gap:gap,pad:pd,
   romanSize:rs,romanTrack:rt,romanOpacity:ro});return el}

/* The frame, with tails. Everything above the bracket is the recovered code untouched: the
   iterative width-match on the roman, the 0.11 stroke, the 0.32 arm, the 1.85x radius. What
   changed is that the two paths are no longer stroked -- they are the icon's tapered OUTLINE,
   so the arms thin toward their free ends the way the mark's do. `tip` is the width at the tip
   as a fraction of the stroke; `tlf` is how much of the arm the ramp takes. */
function frame(el, opt){
 opt = opt || {}
 if(el.querySelector('svg')) return 0
 const k=el.querySelector('.k'), r=el.querySelector('.r')
 /* MEASURE THE TEXT, NOT THE BOX. `.go` and `.rom` are both `display:block`, so
    `getBoundingClientRect().width` on either returns the CONTAINING BLOCK's width -- the same
    number for both, always. `kw - rw` was therefore identically zero, the loop exited on its
    first iteration having written `letter-spacing: 0px`, and that assignment DESTROYED the
    0.14em seed before anything was drawn. The width-match this file has credited to the
    recovered pass since it was written has never matched anything, and every lockup in every
    round has carried zero tracking on the roman.
    A Range measures the inline content regardless of the box's display, which is the whole
    reason to use one here. */
 const textW = function(node){
  const g=document.createRange(); g.selectNodeContents(node)
  return g.getBoundingClientRect().width
 }
 /* THE MATCH IS A FRACTION, NOT A BOOLEAN. The solve was written to drive the roman to the
    kanji's full width, and the owner's answer on seeing it work was that neither end is right:
    the roman should hang left and stop short of the right edge, by an amount worth choosing.
    So `romanFill` is the target as a fraction of the kanji's width, and both previous states are
    values of it -- 1.00 is the flush match, and the drawing judged for twenty-five rounds is
    whatever fraction the type happened to set (0.774 at roman 0.36, and DIFFERENT at every other
    roman size, which is the argument for making it a parameter rather than leaving it to
    fall out).
    Below the natural width the tracking goes negative and the letters tighten; that is a real
    floor and the sweep is meant to find it. */
 const kw=textW(k), nn=r.textContent.length
 const fill = opt.romanFill===undefined ? 1 : opt.romanFill
 const target = kw*fill
 let ls=0
 if(opt.widthMatch!==false){
  for(let i=0;i<30;i++){const rw=textW(r)
   ls+=(target-rw)/nn; r.style.letterSpacing=ls.toFixed(3)+'px'
   if(Math.abs(target-textW(r))<0.2) break}
 }
 el.dataset.romanFill = fill.toFixed(4)
 el.dataset.romanW = textW(r).toFixed(1)
 el.dataset.kanjiW = kw.toFixed(1)
 r.style.marginRight=(-ls).toFixed(3)+'px'
 /* THE SOLVED TRACKING, WHICH IS THE ONLY ONE THAT REACHES THE DRAWING. The loop above overwrites
    whatever `romanTrack` asked for -- it width-matches the roman to the kanji, which is the
    recovered pass's whole reason for existing. So `romanTrack` is a SEED for the solve and never
    an answer: it changes how many iterations run and nothing else, and publishing it as a settled
    value would have put a number in the spec that no drawing on any sheet has ever used. Recorded
    as a fraction of the kanji size so it is comparable across sizes. */
 el.dataset.romanTrackSolved = (ls/(+el.dataset.size)).toFixed(4)
 const size=+el.dataset.size, col=el.dataset.col
 const sw=size*(opt.stroke===undefined?0.11:opt.stroke), arm=opt.arm===undefined?0.32:opt.arm
 const w=el.offsetWidth, h=el.offsetHeight, i=sw/2, W=w-sw, H=h-sw
 /* The radius normally follows the stroke (1.85x), which is what keeps the bracket self-similar at
    any weight. `rrAbs` pins it instead, so a STROKE sweep moves one thing rather than two --
    section 7 rule 6. Nothing but a sweep should pass it. */
 const rrWant = opt.rrAbs!==undefined ? opt.rrAbs : sw*(opt.rrMul===undefined ? 1.85 : opt.rrMul)
 const rrCap  = Math.min(W,H)/2-.1
 const rr=Math.min(rrWant, rrCap)
 /* the cap is printed rather than applied silently -- the taper clamp already taught this file
    that a bound which binds without saying so turns a sweep into repeated specimens */
 el.dataset.rr = rr.toFixed(2) + (rr < rrWant-1e-6 ? ' CLAMPED from '+rrWant.toFixed(2) : '')
 /* THE ARM HAS A FLOOR TOO, AND IT WAS THE ONE BOUND IN THIS FILE THAT BOUND SILENTLY. The
    radius prints its cap and the ramp prints its clamp, both because a bound that binds without
    saying so has already turned a sweep into repeated specimens once. The arm's `rr+2` floor was
    written with neither, and on this geometry it engages below arm ≈ 0.076 -- so an arm sweep
    reaching into that region would have drawn identical brackets under distinct labels, which is
    exactly section 6's defect and exactly what the round sheet's clamp assertion exists to catch.
    Recorded here so it can be. */
 const aXw=W*arm, aYw=H*arm, aFloor=rr+2
 const aX=Math.max(aXw, aFloor), aY=Math.max(aYw, aFloor)
 el.dataset.armpx = aX.toFixed(2)+'/'+aY.toFixed(2) +
   ((aXw<aFloor-1e-6||aYw<aFloor-1e-6) ? ' CLAMPED from '+aXw.toFixed(2)+'/'+aYw.toFixed(2) : '')
 let body
 if(opt.tails===false){
  const TL='M'+i.toFixed(2)+' '+(i+aY).toFixed(2)+'V'+(i+rr).toFixed(2)+'A'+rr.toFixed(2)+' '+rr.toFixed(2)+' 0 0 1 '+(i+rr).toFixed(2)+' '+i.toFixed(2)+'H'+(i+aX).toFixed(2)
  const BR='M'+(i+W).toFixed(2)+' '+(i+H-aY).toFixed(2)+'V'+(i+H-rr).toFixed(2)+'A'+rr.toFixed(2)+' '+rr.toFixed(2)+' 0 0 1 '+(i+W-rr).toFixed(2)+' '+(i+H).toFixed(2)+'H'+(i+W-aX).toFixed(2)
  body=[TL,BR].map(function(d){return '<path d="'+d+'" fill="none" stroke="'+col+'" stroke-width="'+sw.toFixed(2)+'" stroke-linecap="round"/>'}).join('')
 }else{
  const tlf = opt.tl===undefined?0.45:opt.tl
  /* SECTION 6's RECORDED DEFECT, GUARDED. taperParts clamps the ramp at half the path length, so
     every tlf above that renders identically while being presented as a sweep -- "three images
     approved as different were the same image". The clamp point is computed and printed here so a
     clamped specimen cannot pose as a distinct one. */
  const _L1=Math.max(aY-rr,0), _L2=rr*Math.PI/2, _L3=Math.max(aX-rr,0), _L=_L1+_L2+_L3
  const _req=tlf*Math.max(aX,aY), _used=Math.min(_req,_L/2)
  el.dataset.ramp = _used.toFixed(1)+(_used<_req-1e-6 ? ' CLAMPED from '+_req.toFixed(1) : '')
  const p=taperParts(i, i, aX, aY, rr, sw, opt.tip===undefined?0.07:opt.tip, tlf)
  const one='<path d="'+p.body+'" fill="'+col+'"/>'+p.caps.map(function(c){
    return c[2]>0.02?'<circle cx="'+c[0].toFixed(2)+'" cy="'+c[1].toFixed(2)+'" r="'+c[2].toFixed(2)+'" fill="'+col+'"/>':''}).join('')
  body=one+'<g transform="rotate(180 '+(w/2).toFixed(2)+' '+(h/2).toFixed(2)+')">'+one+'</g>'
 }
 el.insertAdjacentHTML('beforeend','<svg width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'">'+body+'</svg>')
 /* A FINGERPRINT OF WHAT WAS ACTUALLY DRAWN, and every option that reached the drawing. A sheet
    claims some variables are held and one is swept; without these two the claim is prose. With
    them the sheet can assert the held ones were identical, the swept one moved, and no two
    specimens in a row are the same picture. */
 /* THE FINGERPRINT IS EVERYTHING THAT DETERMINES THE PIXELS, and it has had to be widened twice
    because it was written as a list of what happened to vary at the time.
      It was the SVG body alone -- enough while every swept variable moved the bracket. Round 25
    swept one that moves only the TYPE'S GEOMETRY, and five distinct specimens fingerprinted
    identically. Round 32 sweeps one that moves neither -- an OPACITY changes no coordinate at all
    -- and they fingerprinted identically again.
      So the rule is stated rather than the symptom patched: anything that can change what is
    painted belongs here, whether or not any round has swept it yet. Geometry, type metrics, ink.
    The round sheet's first assertion is only as good as this string. */
 el.dataset.geom = body.length + ':' + body.slice(0, 400) +
   '|type ' + el.dataset.romanW + '/' + el.dataset.kanjiW + '/' + ls.toFixed(3) +
   '|ink ' + el.dataset.romanOpacity + '/' + col
 el.dataset.used = JSON.stringify({
  stroke: +(sw/size).toFixed(4), arm: +arm.toFixed(4), rr: +rr.toFixed(2),
  rrMul: +(rr/sw).toFixed(3),
  tip: opt.tip===undefined?0.07:opt.tip, tl: opt.tl===undefined?0.45:opt.tl,
  tails: opt.tails!==false, size: size,
  gap: +(el.dataset.gap||0), pad: +(el.dataset.pad||0),
  romanSize: +(el.dataset.romanSize||0),
  /* BOTH: what was ASKED for and what was SOLVED. Recording only the seed publishes a number no
     drawing used; recording only the solve loses the sheet's ability to assert the seed was held
     constant across a row. They are different facts and the round sheet needs each. */
  romanTrack: +(el.dataset.romanTrack||0),
  romanTrackSolved: +(el.dataset.romanTrackSolved||0),
  romanFill: +(el.dataset.romanFill||0),
  romanOpacity: +(el.dataset.romanOpacity||0)})
 return h}
