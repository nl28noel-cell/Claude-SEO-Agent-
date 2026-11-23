// QA der Artifact-Fassung (dashboard/artifact/dist), so nah wie lokal möglich am echten Artifact:
//  - Seite wird in dasselbe Dokument-Skelett gesetzt, das claude.ai beim Veröffentlichen ergänzt
//  - Light/Dark über prefers-color-scheme und data-theme
//  - mehrere Breiten, Overflow-Check, Console-Fehler, Screenshots
//  - Approval-Flow gegen einen In-Memory-Mock von window.claude (db + user)
// node dashboard/qa/artifact_qa.js [outDir] [--shots]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), http = require('http');
const ROOT = path.join(__dirname, '..', '..');
// QA_DIST=<Ordner> prüft stattdessen die vom Artifact zurückgelesenen, veröffentlichten Dateien (index.html ist dann bereits ein vollständiges Dokument)
const DIST = process.env.QA_DIST || path.join(ROOT, 'dashboard', 'artifact', 'dist');
const out = process.argv[2] || path.join(ROOT, 'qa-shots', 'artifact');
const SHOTS = process.argv.includes('--shots');
const SKELETON = (body) => `<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style></head><body>${body}</body></html>`;

// Test-Fixture: ein künstlicher Gate-1-Eintrag NUR für den Approval-Flow-Test (nie veröffentlicht)
const FIXTURE_ITEM = { id: 'QA-G1-TEST', title: 'QA fixture – not real', status: 'pending', submitted: '2026-11-23', fields: { Purpose: 'Automated QA of the approval flow' } };

function serve(fixture) {
  return new Promise(res => {
    const srv = http.createServer((req, rsp) => {
      let u = decodeURIComponent(req.url.split('?')[0]); if (u === '/') u = '/index.html';
      const f = path.join(DIST, u);
      if (!f.startsWith(DIST) || !fs.existsSync(f)) { rsp.writeHead(404); return rsp.end(); }
      let body = fs.readFileSync(f, 'utf8');
      if (u === '/index.html' && !/^<!doctype/i.test(body)) body = SKELETON(body);
      if (fixture && u.endsWith('dashboard.json')) { const d = JSON.parse(body); d.approvals.gate1 = [FIXTURE_ITEM]; d.health.pending_approvals = 1; body = JSON.stringify(d); }
      rsp.writeHead(200, { 'content-type': u.endsWith('.json') ? 'application/json' : 'text/html; charset=utf-8' }); rsp.end(body);
    }).listen(0, '127.0.0.1', () => res(srv));
  });
}
// Minimaler Mock der Artifact-Runtime (db: collection/doc/set/onSnapshot; user: isOwner)
const MOCK = () => {
  const store = new Map(), subs = [];
  const snap = () => { const docs = [...store.entries()].map(([id, v]) => ({ id, exists: true, data: () => v, metadata: { fromCache: false, hasPendingWrites: false } })); return { docs, size: docs.length, empty: !docs.length, metadata: { fromCache: false, hasPendingWrites: false }, docChanges: () => [] }; };
  const db = { collection: c => ({ doc: id => ({ set: async v => { store.set(id, JSON.parse(JSON.stringify(v))); window.__writes = (window.__writes || 0) + 1; subs.forEach(f => f(snap())); } }), onSnapshot: (n) => { subs.push(n); setTimeout(() => n(snap()), 30); return () => {}; } }) };
  const user = { isOwner: async () => true };
  window.claude = { use: async name => (name === 'db' ? db : name === 'user' ? user : null) };
  window.__store = store;
};

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const ok = [], bad = [];
  const check = (n, c, i = '') => (c ? ok : bad).push(n + (i ? ' — ' + i : ''));
  const b = await chromium.launch();
  const srv = await serve(false); const base = `http://127.0.0.1:${srv.address().port}/`;
  const routes = ['overview', 'performance', 'funnel', 'analytics', 'ads', 'opportunities', 'opp-OPP-02', 'approvals', 'changes', 'market', 'local', 'findings', 'activity', 'sources'];
  const widths = [1440, 1180, 900, 400];
  for (const scheme of ['light', 'dark']) {
    for (const W of widths) {
      const ctx = await b.newContext({ viewport: { width: W, height: 900 }, colorScheme: scheme, deviceScaleFactor: 1 });
      await ctx.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort()); // Container hat keinen Zugriff auf Google Fonts
      const p = await ctx.newPage(); const errs = [];
      p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && !/fonts\.g/.test(m.text()) && !m.text().includes('ERR_FAILED') && errs.push(m.text()));
      for (const r of routes) {
        await p.goto(base + '#' + r, { waitUntil: 'networkidle' }); await p.waitForTimeout(150);
        const t = await p.locator('#view').innerText();
        check(`[${scheme} ${W}] ${r} renders`, !t.includes('failed to render') && !t.includes('Could not load') && t.length > 50);
        const ov = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        check(`[${scheme} ${W}] ${r} no horizontal page scroll`, ov <= 1, ov + 'px');
        const bg = await p.evaluate(() => getComputedStyle(document.body).backgroundColor);
        const dark = await p.evaluate(() => { const c = getComputedStyle(document.body).backgroundColor.match(/\d+/g).map(Number); return (c[0] + c[1] + c[2]) / 3 < 80; });
        check(`[${scheme} ${W}] ${r} body background follows theme`, scheme === 'dark' ? dark : !dark, bg);
        if (SHOTS && (W === 1440 || (W === 400 && ['overview', 'opp-OPP-02', 'approvals', 'funnel', 'analytics'].includes(r)) || (W === 1180 && ['overview', 'performance'].includes(r))))
          await p.screenshot({ path: `${out}/${scheme}-${W}-${r}.png`, fullPage: true });
      }
      check(`[${scheme} ${W}] no console/page errors`, errs.length === 0, errs.join(' | '));
      await ctx.close();
    }
  }
  // Explizites data-theme gewinnt gegen das System-Schema (beide Richtungen)
  for (const [scheme, theme] of [['dark', 'light'], ['light', 'dark']]) {
    const ctx = await b.newContext({ viewport: { width: 1200, height: 800 }, colorScheme: scheme }); const p = await ctx.newPage();
    await ctx.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort());
    await p.goto(base + '#overview', { waitUntil: 'networkidle' });
    await p.evaluate(t => document.documentElement.setAttribute('data-theme', t), theme);
    const dark = await p.evaluate(() => { const c = getComputedStyle(document.body).backgroundColor.match(/\d+/g).map(Number); return (c[0] + c[1] + c[2]) / 3 < 80; });
    check(`data-theme=${theme} overrides system ${scheme}`, theme === 'dark' ? dark : !dark);
    await ctx.close();
  }
  // Legacy-Links (#/opportunities/OPP-02) werden auf #opp-OPP-02 umgeschrieben
  {
    const ctx = await b.newContext(); const p = await ctx.newPage(); await ctx.route(/fonts\./, r => r.abort());
    await p.goto(base + '#/opportunities/OPP-02', { waitUntil: 'networkidle' });
    check('legacy hash rewritten', p.url().endsWith('#opp-OPP-02'), p.url());
    await p.click('#nav a[data-route="findings"]'); await p.waitForTimeout(100);
    check('nav click routes', p.url().endsWith('#findings') && (await p.locator('#nav a.active').getAttribute('data-route')) === 'findings');
    await p.goBack(); await p.waitForTimeout(150);
    check('browser back works', p.url().endsWith('#opp-OPP-02') && (await p.locator('h1').first().innerText()).length > 3);
    const noDb = await p.goto(base + '#approvals', { waitUntil: 'networkidle' }).then(() => p.locator('#store-notice').innerText());
    check('without Claude runtime: store shown as not available', /Not available/.test(noDb), noDb.slice(0, 80));
    check('without Claude runtime: no decision buttons enabled', (await p.locator('.dec-form [data-choice]:enabled').count()) === 0);
    await ctx.close();
  }
  srv.close();
  // Approval-Flow mit Mock-Runtime und Test-Fixture
  {
    const srv2 = await serve(true); const base2 = `http://127.0.0.1:${srv2.address().port}/`;
    const ctx = await b.newContext({ viewport: { width: 1300, height: 900 } }); await ctx.route(/fonts\./, r => r.abort());
    await ctx.addInitScript(MOCK); const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.goto(base2 + '#approvals', { waitUntil: 'networkidle' }); await p.waitForTimeout(200);
    check('mock: store connected', /Connected/.test(await p.locator('#store-notice').innerText()));
    check('mock: nav badge counts undecided item', (await p.locator('#nav-approvals').innerText()) === '1');
    check('mock: save disabled before choice', await p.locator('[data-save]').isDisabled());
    await p.click('[data-choice="request_changes"]'); await p.fill('textarea', 'QA comment');
    await p.click('[data-save]'); await p.waitForTimeout(200);
    const doc = await p.evaluate(() => [...window.__store.values()][0]);
    check('mock: decision written with all fields', doc && doc.item_id === 'QA-G1-TEST' && doc.gate === 1 && doc.decision === 'request_changes' && doc.comment === 'QA comment' && doc.agent_status === 'pending' && !!Date.parse(doc.decided_at) && doc.client === 'spreewald-luftaufnahmen', JSON.stringify(doc));
    check('mock: exactly one write', (await p.evaluate(() => window.__writes)) === 1);
    check('mock: log shows decision + waiting for agent', /Request changes[\s\S]*Waiting for agent/.test(await p.locator('#dec-log').innerText()));
    check('mock: item status updated', /Waiting for agent/.test(await p.locator('[data-status-for="QA-G1-TEST"]').innerText()));
    check('mock: nav badge cleared after decision', (await p.locator('#nav-approvals').innerText()) === '');
    // Agent verarbeitet -> Status im Log
    await p.evaluate(() => { const [k, v] = [...window.__store.entries()][0]; window.claude.use('db').then(db => db.collection('decisions').doc(k).set({ ...v, agent_status: 'processed', agent_processed_at: new Date().toISOString(), agent_note: 'QA processed' })); });
    await p.waitForTimeout(200);
    check('mock: processed status visible', /Processed by agent[\s\S]*|QA processed/.test(await p.locator('#dec-log').innerText()));
    if (SHOTS) await p.screenshot({ path: `${out}/mock-approvals-flow.png`, fullPage: true });
    check('mock: no page errors', errs.length === 0, errs.join(' | '));
    await ctx.close(); srv2.close();
  }
  await b.close();
  console.log('PASS', ok.length); console.log('FAIL', bad.length); bad.forEach(x => console.log('  ✗', x));
  process.exit(bad.length ? 1 : 0);
})();
