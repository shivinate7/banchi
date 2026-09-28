const fs = require('fs');
const path = require('path');
const palettes = require('./palettes');

const order = ['championship', 'driftKing', 'overclock', 'lanternDistrict'];
const screens = ['home', 'pricing', 'orders', 'sales'];

function swatch(hex, label) {
  return `<div class="sw"><div class="chip" style="background:${hex}"></div><div class="lbl"><code>${hex}</code><span>${label}</span></div></div>`;
}

const rows = order.map(key => {
  const p = palettes[key];
  const shots = screens.map(s => `
    <figure>
      <img src="${key}-${s}.png" alt="${p.name} — ${s}">
      <figcaption>${s}</figcaption>
    </figure>`).join('\n');

  const swatches = [
    swatch(p.accent, 'accent — buttons, links, focus, Home nav'),
    swatch(p.navWorkflow, 'Workflow nav group + its active row'),
    swatch(p.navSell, 'Sell nav group + active row + 2nd tab'),
    swatch(p.navLibrary, 'Library nav group'),
    swatch(p.live, 'live — capture / live indicator'),
    swatch(p.ok, 'ok — success, bullish, go states'),
    swatch(p.warn, 'warn — caution, held pills'),
    swatch(p.danger, 'danger — destructive actions'),
    swatch(p.money, 'money — every dollar figure'),
    swatch(p.stageAccent, 'stage accent — camera/photo stage only'),
    swatch(p.bg, 'page ground'),
    swatch(p.surface, 'panel ground'),
  ].join('\n');

  return `
  <section class="palette">
    <div class="pal-head">
      <h2>${p.name}</h2>
      <p class="mood">${p.mood}</p>
    </div>
    <div class="shots">${shots}</div>
    <div class="swatches">${swatches}</div>
  </section>`;
}).join('\n');

const html = `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Banchi dark palettes — cyberpunk anime esque, round 2 (blind)</title>
<style>
  :root { color-scheme: dark; }
  body {
    background: #08090c;
    color: #eef0f4;
    font: 14px/1.5 -apple-system, 'Inter', system-ui, sans-serif;
    margin: 0;
    padding: 32px;
  }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .intro { color: #9aa0ac; margin: 0 0 32px; max-width: 900px; }
  .palette { margin-bottom: 56px; padding-bottom: 40px; border-bottom: 1px solid rgba(255,255,255,0.1); }
  .pal-head h2 { font-size: 20px; margin: 0 0 4px; }
  .pal-head .mood { color: #b9bfc9; margin: 0 0 16px; max-width: 900px; font-style: italic; }
  .shots { display: flex; gap: 12px; overflow-x: auto; margin-bottom: 20px; }
  .shots figure { margin: 0; flex: 0 0 auto; }
  .shots img { width: 340px; height: auto; border-radius: 8px; border: 1px solid rgba(255,255,255,0.12); display: block; }
  .shots figcaption { text-align: center; color: #838b98; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 6px; }
  .swatches { display: flex; flex-wrap: wrap; gap: 10px 20px; }
  .sw { display: flex; align-items: center; gap: 8px; }
  .chip { width: 28px; height: 28px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2); flex: none; }
  .lbl { display: flex; flex-direction: column; font-size: 11px; }
  .lbl code { font-family: 'JetBrains Mono', ui-monospace, monospace; color: #eef0f4; }
  .lbl span { color: #9aa0ac; }
</style>
</head>
<body>
  <h1>Banchi — dark-mode palettes, round 2 (blind, fresh eyes)</h1>
  <p class="intro">Four novel palettes over the same light-mode layout, colors only. Each targets Banchi's
  <code>--bn-*</code> tokens plus color-only rules on nav groups, active links, tabs and the camera stage,
  so different regions of the UI clash on purpose while every hue still has one job.</p>
  ${rows}
</body>
</html>
`;

fs.writeFileSync(path.join(__dirname, 'index.html'), html);
console.log('wrote index.html');
