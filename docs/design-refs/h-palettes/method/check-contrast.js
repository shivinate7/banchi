const { ratio } = require('./contrast');
const palettes = require('./palettes');

for (const [key, p] of Object.entries(palettes)) {
  console.log('\n==', p.name, '==');
  const checks = [
    ['ink/bg', p.ink, p.bg],
    ['ink2/bg', p.ink2, p.bg],
    ['ink3/bg', p.ink3, p.bg],
    ['ink/surface', p.ink, p.surface],
    ['ink3/surface2', p.ink3, p.surface2],
    ['money/bg', p.money, p.bg],
    ['money/surface', p.money, p.surface],
    ['accent-as-link/bg', p.accent, p.bg],
    ['live-as-text/bg', p.live, p.bg],
    ['ok-as-text/bg', p.ok, p.bg],
    ['warn-as-text/bg', p.warn, p.bg],
    ['danger-as-text/bg', p.danger, p.bg],
    ['onAccent/accent (button label)', p.onAccent, p.accent],
  ];
  for (const [name, fg, bg] of checks) {
    const r = ratio(fg, bg);
    const flag = r < 4.5 ? '  <-- LOW' : '';
    console.log(name.padEnd(30), r.toFixed(2), flag);
  }
}
