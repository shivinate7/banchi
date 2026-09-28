// STEP 1 + inspect DOM for selectors (rendered DOM only, not source files)
const { chromium } = require('playwright');
const path = require('path');

const OUT = '/private/tmp/claude-501/-Users-shivinate-Developer-pkmnscan/8d51bb04-23aa-47ca-ada1-d62b265fd9a4/scratchpad/cyberpunk/blind2';
const BASE = 'https://shivinate7.github.io/banchi/';

const routes = {
  home: '#/',
  pricing: '#/pricing',
  orders: '#/orders',
  sales: '#/revenue',
  inventory: '#/inventory',
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // force light mode before any script runs
  await page.addInitScript(() => {
    try {
      localStorage.setItem('banchi.theme', 'light');
      document.documentElement.dataset.theme = 'light';
    } catch (e) {}
  });

  for (const [name, hash] of Object.entries(routes)) {
    await page.goto(BASE + hash, { waitUntil: 'networkidle' });
    await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
    await page.waitForTimeout(900); // theme fade + render settle
    await page.screenshot({ path: path.join(OUT, `light-${name}.png`) });
    console.log('shot', name);
  }

  // Inspect rendered DOM for class hooks on nav, tabs, stat tiles (rendered DOM, not source)
  const classInfo = await page.evaluate(() => {
    const uniq = new Set();
    document.querySelectorAll('[class]').forEach(el => {
      el.className.toString().split(/\s+/).forEach(c => {
        if (c && (c.includes('nav') || c.includes('tab') || c.includes('tile') || c.includes('sidebar') || c.includes('stat') || c.includes('pill') || c.includes('badge'))) {
          uniq.add(c);
        }
      });
    });
    return [...uniq];
  });
  console.log('CLASS HOOKS:', JSON.stringify(classInfo, null, 2));

  await browser.close();
})();
