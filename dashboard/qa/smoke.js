// QA: alle Routen laden, Console-Fehler sammeln, Screenshots erzeugen.
// node dashboard/qa/smoke.js [baseUrl] [outDir] [width] [height] [scale]
const { chromium } = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765/';
const out = process.argv[3] || 'qa-shots';
const W = +(process.argv[4] || 1440), H = +(process.argv[5] || 900), DPR = +(process.argv[6] || 1);
const routes = ['overview', 'performance', 'opportunities', 'opp-OPP-02', 'opp-OPP-04', 'approvals', 'changes', 'market', 'local', 'findings', 'activity', 'sources', 'doesnotexist'];
(async () => {
  require('fs').mkdirSync(out, { recursive: true });
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: DPR });
  const errors = [];
  p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`[${m.type()}] ${m.text()}`); });
  p.on('pageerror', e => errors.push('[pageerror] ' + e.message));
  p.on('requestfailed', r => errors.push('[requestfailed] ' + r.url()));
  for (const r of routes) {
    await p.goto(base + '#' + r, { waitUntil: 'networkidle' });
    await p.waitForTimeout(250);
    const failed = await p.$eval('#view', el => el.innerText.includes('failed to render') || el.innerText.includes('Could not load'));
    const overflowX = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    const active = await p.$eval('#nav a.active', a => a.dataset.route).catch(() => null);
    console.log(`${r.padEnd(24)} render=${failed ? 'FAIL' : 'ok'} pageOverflowX=${overflowX} activeNav=${active} url=${p.url().split('#')[1]}`);
    await p.screenshot({ path: `${out}/${r.replace('/', '_')}.png`, fullPage: true });
  }
  console.log('CONSOLE/NETWORK ISSUES:', errors.length ? '\n' + errors.join('\n') : 'none');
  await b.close();
})();
