// Funktionale QA: Filter, Suche, Tabs, Sortierung, Detailansichten, KPI-Abgleich.
// node dashboard/qa/functional.js [baseUrl]
const { chromium } = require('playwright');
const fs = require('fs');
const base = process.argv[2] || 'http://127.0.0.1:8765/';
const d = JSON.parse(fs.readFileSync(__dirname + '/../public/data/spreewald-luftaufnahmen/dashboard.json'));
const ok = [], bad = [];
const check = (name, cond, info = '') => (cond ? ok : bad).push(name + (info ? ' — ' + info : ''));
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && errs.push(m.text()));
  const nf = n => new Intl.NumberFormat('de-DE').format(n);
  const rowsOf = sel => p.locator(sel + ' tbody tr').allInnerTexts();

  // KPI 28D gegen Rohdaten
  await p.goto(base + '#/overview', { waitUntil: 'networkidle' });
  const last28 = d.gsc.daily.slice(-28);
  const c = last28.reduce((a, r) => a + r.clicks, 0), i = last28.reduce((a, r) => a + r.impressions, 0);
  const kpis = await p.locator('.kpi .k-val').allInnerTexts();
  check('KPI clicks 28D', kpis[0] === nf(c), `${kpis[0]} vs ${c}`);
  check('KPI impressions 28D', kpis[1] === nf(i), `${kpis[1]} vs ${i}`);
  check('KPI open findings', kpis[4] === String(d.health.open_findings));
  check('Attention items rendered', (await p.locator('.att-item').count()) === d.attention.length);
  await p.click('.seg[data-range="range"] button[data-r="16M"]'); await p.waitForTimeout(150);
  check('Range 16M active', (await p.locator('.seg[data-range="range"] button.on').getAttribute('data-r')) === '16M');

  // Performance: Suche, Filter, Sortierung, Pagination, Tabs
  await p.goto(base + '#/performance', { waitUntil: 'networkidle' });
  await p.fill('#ptab-body input[type=search]', 'baudokumentation'); await p.waitForTimeout(100);
  const r1 = await rowsOf('#ptab-body');
  check('Search filters queries', r1.length > 0 && r1.every(t => t.toLowerCase().includes('baudokumentation')), r1.length + ' rows');
  await p.fill('#ptab-body input[type=search]', '');
  await p.selectOption('#ptab-body select[data-f="segment"]', 'Strategic B2B'); await p.waitForTimeout(100);
  const info = await p.locator('#ptab-body .info').innerText();
  check('Segment filter count', info.endsWith('of ' + d.gsc.segment_totals['Strategic B2B'].queries), info);
  await p.click('#ptab-body th[data-k="position"]'); await p.waitForTimeout(80);
  const pos = (await p.locator('#ptab-body tbody tr td:nth-child(5)').allInnerTexts()).map(x => parseFloat(x.replace(',', '.')));
  const asc = [...pos].sort((a, b) => a - b).join(), desc = [...pos].sort((a, b) => b - a).join();
  check('Sort by position', pos.length > 0 && (pos.join() === asc || pos.join() === desc));
  await p.click('#ptab-body .next'); await p.waitForTimeout(80);
  check('Pagination next', (await p.locator('#ptab-body .info').innerText()).startsWith('16'));
  for (const t of ['Pages', 'Query × Page', 'Winners', 'Losers', 'Quick Wins', 'Cannibalization']) {
    await p.click(`#ptabs button[data-t="${t}"]`); await p.waitForTimeout(80);
    check('Tab ' + t, (await p.locator('#ptab-body tbody tr').count()) > 0);
  }
  await p.click('.seg[data-range="perfRange"] button[data-r="28D"]'); await p.waitForTimeout(120);
  check('Perf range 28D KPI', (await p.locator('.kpi .k-val').first().innerText()) === nf(c));

  // Opportunities: Typfilter, Detail, unbekannte ID
  await p.goto(base + '#/opportunities', { waitUntil: 'networkidle' });
  await p.click('#otype button[data-t="CREATE"]'); await p.waitForTimeout(80);
  const n = await p.locator('#opp-table tbody tr').count();
  check('Type filter CREATE', n === d.opportunities.filter(o => o.type === 'CREATE').length, String(n));
  await p.click('#otype button[data-t="All"]'); await p.waitForTimeout(80);
  await p.click('#opp-table tbody tr:first-child'); await p.waitForTimeout(150);
  check('Row opens detail', p.url().includes('#/opportunities/' + d.opportunities[0].id), p.url());
  check('Detail has evidence sections', (await p.locator('.card h2').allInnerTexts()).includes('Agent reasoning'));
  await p.goto(base + '#/opportunities/NOPE', { waitUntil: 'networkidle' });
  check('Unknown opportunity handled', (await p.locator('#view').innerText()).includes('not found'));

  // Market / Findings Detail
  await p.goto(base + '#/market', { waitUntil: 'networkidle' });
  await p.click('#mk tbody tr:first-child'); await p.waitForTimeout(80);
  check('Market row expands', (await p.locator('#mk-detail h2').count()) === 1);
  await p.goto(base + '#/findings', { waitUntil: 'networkidle' });
  await p.click('#fd tbody tr:first-child'); await p.waitForTimeout(80);
  check('Finding detail opens', (await p.locator('#fd-detail .kv').count()) === 1);

  // Approvals: keine Entscheidungs-Buttons ohne echte Einträge
  await p.goto(base + '#/approvals', { waitUntil: 'networkidle' });
  const pending = d.approvals.gate1.length + d.approvals.gate2.length;
  check('Approval buttons only for real items', (await p.locator('button[data-dec]').count()) === pending * 3);

  // Tote interne Links
  const hrefs = new Set();
  for (const r of ['overview', 'opportunities/OPP-02', 'findings', 'changes', 'approvals', 'local', 'activity']) {
    await p.goto(base + '#/' + r, { waitUntil: 'networkidle' });
    for (const h of await p.locator('a[href^="#/"]').evaluateAll(a => a.map(x => x.getAttribute('href')))) hrefs.add(h);
  }
  for (const h of hrefs) {
    await p.goto(base + h, { waitUntil: 'networkidle' });
    const t = await p.locator('#view').innerText();
    if (t.includes('failed to render') || t.includes('not found')) bad.push('Dead link ' + h);
  }
  check('Internal links checked', true, hrefs.size + ' links');
  check('No console/page errors', errs.length === 0, errs.join(' | '));
  await b.close();
  console.log('PASS', ok.length); ok.forEach(x => console.log('  ✓', x));
  console.log('FAIL', bad.length); bad.forEach(x => console.log('  ✗', x));
  process.exit(bad.length ? 1 : 0);
})();
