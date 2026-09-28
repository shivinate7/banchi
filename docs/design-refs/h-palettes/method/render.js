const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT = __dirname;
const BASE = 'https://shivinate7.github.io/banchi/';

const routes = {
  home: '#/',
  pricing: '#/pricing',
  orders: '#/orders',
  sales: '#/revenue',
};

const palettes = ['championship', 'driftKing', 'overclock', 'lanternDistrict'];

(async () => {
  const browser = await chromium.launch();

  for (const key of palettes) {
    const css = fs.readFileSync(path.join(OUT, `${key}.css`), 'utf8');
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.addInitScript(() => {
      try {
        localStorage.setItem('banchi.theme', 'dark');
        document.documentElement.dataset.theme = 'dark';
      } catch (e) {}
    });

    for (const [name, hash] of Object.entries(routes)) {
      await page.goto(BASE + hash, { waitUntil: 'networkidle' });
      await page.evaluate(() => { document.documentElement.dataset.theme = 'dark'; });
      await page.waitForTimeout(600);
      await page.addStyleTag({ content: css });
      await page.waitForTimeout(400); // let cross-fade / transitions settle
      const file = path.join(OUT, `${key}-${name}.png`);
      await page.screenshot({ path: file });
      console.log('shot', key, name);
    }
    await page.close();
  }

  await browser.close();
})();
