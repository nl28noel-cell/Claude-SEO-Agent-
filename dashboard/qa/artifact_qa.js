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

function serve() {
  return new Promise(res => {
    const srv = http.createServer((req, rsp) => {
      let u = decodeURIComponent(req.url.split('?')[0]); if (u === '/') u = '/index.html';
      const f = path.join(DIST, u);
      if (!f.startsWith(DIST) || !fs.existsSync(f)) { rsp.writeHead(404); return rsp.end(); }
      let body = fs.readFileSync(f, 'utf8');
      if (u === '/index.html' && !/^<!doctype/i.test(body)) body = SKELETON(body);
      rsp.writeHead(200, { 'content-type': u.endsWith('.json') ? 'application/json' : 'text/html; charset=utf-8' }); rsp.end(body);
    }).listen(0, '127.0.0.1', () => res(srv));
  });
}
// Mock der Artifact-Runtime: db (collections, set/update/onSnapshot, persistiert in sessionStorage → überlebt Reload), user (Owner), mcp (fire_trigger)
const MOCK = () => {
  const KEY = '__mockdb'; const load = () => { try { return JSON.parse(sessionStorage.getItem(KEY) || '{}'); } catch (e) { return {}; } };
  const all = load(); const save = () => sessionStorage.setItem(KEY, JSON.stringify(all)); const subs = {};
  const merge = (t, s) => { for (const [k, v] of Object.entries(s)) { if (v && typeof v === 'object' && !Array.isArray(v) && t[k] && typeof t[k] === 'object') merge(t[k], v); else t[k] = v; } return t; };
  const snap = c => { const docs = Object.entries(all[c] || {}).map(([id, v]) => ({ id, exists: true, data: () => v, metadata: { fromCache: false, hasPendingWrites: false } })); return { docs, size: docs.length, empty: !docs.length, metadata: { fromCache: false, hasPendingWrites: false }, docChanges: () => [] }; };
  const emit = c => (subs[c] || []).forEach(f => f(snap(c)));
  const db = { collection: c => ({ doc: id => ({
      set: async v => { (all[c] ||= {})[id] = JSON.parse(JSON.stringify(v)); save(); window.__writes = (window.__writes || 0) + 1; emit(c); },
      update: async v => { if (!all[c]?.[id]) throw { code: 'invalid_argument', message: 'missing' }; merge(all[c][id], JSON.parse(JSON.stringify(v))); save(); window.__writes = (window.__writes || 0) + 1; emit(c); } }),
    onSnapshot: n => { (subs[c] ||= []).push(n); setTimeout(() => n(snap(c)), 30); return () => {}; } }) };
  const mcp = { listTools: async () => ({ servers: [{ server: 'Claude Code Remote', authStatus: 'connected', tools: [{ name: 'fire_trigger', description: '' }] }] }),
    callTool: async (srv, tool, input) => { (window.__fired ||= []).push({ srv, tool, input }); return { content: [], payload: { ok: true } }; } };
  window.claude = { use: async name => (name === 'db' ? db : name === 'user' ? { isOwner: async () => true } : name === 'mcp' ? mcp : null) };
  window.__all = all;
};

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const ok = [], bad = [];
  const check = (n, c, i = '') => (c ? ok : bad).push(n + (i ? ' — ' + i : ''));
  const b = await chromium.launch();
  const srv = await serve(); const base = `http://127.0.0.1:${srv.address().port}/`;
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
    check('without Claude runtime: approve disabled', await p.click('.wf-card').then(() => p.locator('[data-act="approve"]').isDisabled()));
    await ctx.close();
  }
  srv.close();
  // Workflow-Flow mit Mock-Runtime (Gate 1 per Button und per Drag & Drop, Kommentar, Trigger, Reload, Revision, Gate 2)
  {
    const srv2 = await serve(); const base2 = `http://127.0.0.1:${srv2.address().port}/`;
    const ctx = await b.newContext({ viewport: { width: 1440, height: 950 } }); await ctx.route(/fonts\./, r => r.abort());
    await ctx.addInitScript(MOCK); const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.goto(base2 + '#approvals', { waitUntil: 'networkidle' }); await p.waitForTimeout(250);
    const dd = JSON.parse(fs.readFileSync(path.join(DIST, 'data', 'spreewald-luftaufnahmen', 'dashboard.json'), 'utf8'));
    const nProd = dd.opportunities.filter(o => ['CREATE', 'OPTIMIZE', 'MERGE'].includes(o.type)).length;
    check('board: all production-type opportunities start in "Zur Prüfung"', (await p.locator('.wf-col[data-col="review"] .wf-card').count()) === nProd, String(nProd));
    check('board: nothing approved without interaction', (await p.locator('.wf-col[data-col="production"] .wf-card').count()) === 0);
    check('board: store connected', /Connected/.test(await p.locator('#store-notice').innerText()));
    // Gate 1 per Button mit Kommentar
    const first = dd.opportunities.find(o => ['CREATE', 'OPTIMIZE', 'MERGE'].includes(o.type)).id;
    await p.click(`[data-card="${first}"]`); await p.waitForTimeout(150);
    check('card opens decision basis', /entscheidungsgrundlage/i.test(await p.locator('#wf-panel-body').innerText()));
    await p.fill('#wf-c1', 'Bitte stärker auf Hausverwaltungen ausrichten.'); await p.click('[data-act="approve"]'); await p.waitForTimeout(300);
    let w = await p.evaluate(id => window.__all.workflow?.[id], first);
    check('gate1 persisted with timestamp + comment', w?.gate1?.status === 'approved' && !!Date.parse(w.gate1.at) && w.gate1.comment.includes('Hausverwaltungen') && w.production?.status === 'waiting', JSON.stringify(w));
    const fired = await p.evaluate(() => window.__fired || []);
    check('agent trigger fired (fire_trigger with trigger_id)', fired.length === 1 && fired[0].tool === 'fire_trigger' && !!fired[0].input.trigger_id, JSON.stringify(fired));
    check('trigger result recorded', /angestoßen/.test(w?.trigger?.result || ''), JSON.stringify(w?.trigger));
    check('decision event logged', await p.evaluate(id => Object.values(window.__all.decisions || {}).some(x => x.item_id === id && x.gate === 1), first));
    await p.click('#wf-panel-body [data-close]'); await p.waitForTimeout(100);
    check('card moved to "Freigegeben / Produktion" with honest label', /Waiting for agent/.test(await p.locator(`.wf-col[data-col="production"] [data-card="${first}"]`).innerText()));
    // Gate 1 per Drag & Drop (öffnet Bestätigung)
    const second = dd.opportunities.filter(o => ['CREATE', 'OPTIMIZE', 'MERGE'].includes(o.type))[1].id;
    await p.dragAndDrop(`[data-card="${second}"]`, '.wf-col[data-col="production"]'); await p.waitForTimeout(200);
    check('drag & drop opens approval confirmation', (await p.locator('#wf-drawer').isVisible()) && /Drag & Drop/.test(await p.locator('#wf-panel-body').innerText()));
    await p.click('[data-act="approve"]'); await p.waitForTimeout(300);
    check('drag & drop approval persisted', await p.evaluate(id => window.__all.workflow?.[id]?.gate1?.status === 'approved', second));
    await p.click('#wf-panel-body [data-close]');
    // Reload → Status bleibt
    await p.reload({ waitUntil: 'networkidle' }); await p.waitForTimeout(300);
    check('persists across reload', (await p.locator('.wf-col[data-col="production"] .wf-card').count()) === 2);
    // Agent liefert Entwurf (simuliert wie ArtifactData-Update)
    await p.evaluate(id => window.claude.use('db').then(db => db.collection('workflow').doc(id).update({ production: { status: 'draft_ready', version: 1, doc_id: 'x', doc_url: 'https://docs.google.com/document/d/x/edit', doc_title: id + ' – Entwurf', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), qa_status: 'PASS', strategy_summary: 'QA', history: [{ version: 1, doc_url: 'https://docs.google.com/document/d/x/edit' }] }, review: { status: 'pending' } })), first);
    await p.waitForTimeout(200);
    check('draft column shows card + nav badge', (await p.locator(`.wf-col[data-col="draft"] [data-card="${first}"]`).count()) === 1 && (await p.locator('#nav-approvals').innerText()) === '1');
    await p.click(`[data-card="${first}"]`); await p.waitForTimeout(150);
    check('draft shows "Entwurf öffnen" link', (await p.locator('#wf-panel-body a', { hasText: 'Entwurf öffnen' }).getAttribute('href')).includes('docs.google.com'));
    await p.click('[data-act="revise"]'); await p.waitForTimeout(150);
    check('revision requires comment', await p.evaluate(id => window.__all.workflow[id].review.status === 'pending', first));
    await p.fill('#wf-c2', 'FAQ zu Kosten ergänzen'); await p.click('[data-act="revise"]'); await p.waitForTimeout(300);
    w = await p.evaluate(id => window.__all.workflow[id], first);
    check('revision requested persisted', w.review.status === 'revision_requested' && w.review.comment === 'FAQ zu Kosten ergänzen' && w.review.for_version === 1);
    await p.click('#wf-panel-body [data-close]');
    check('revision card back in production with label', /Revision requested/.test(await p.locator(`.wf-col[data-col="production"] [data-card="${first}"]`).innerText()));
    // Agent liefert v2, dann Gate 2
    await p.evaluate(id => window.claude.use('db').then(db => db.collection('workflow').doc(id).update({ production: { status: 'draft_ready', version: 2 }, review: { status: 'pending' } })), first);
    await p.waitForTimeout(200); await p.click(`[data-card="${first}"]`); await p.waitForTimeout(150);
    await p.click('[data-act="final"]'); await p.waitForTimeout(300);
    w = await p.evaluate(id => window.__all.workflow[id], first);
    check('gate2 persisted', w.gate2?.status === 'approved' && !!Date.parse(w.gate2.at));
    await p.click('#wf-panel-body [data-close]');
    check('final column label "Ready for WordPress Draft"', /Ready for WordPress Draft/.test(await p.locator(`.wf-col[data-col="final"] [data-card="${first}"]`).innerText()));
    check('after reload: revision fired trigger, gate 2 did not (nothing to publish)', (await p.evaluate(() => (window.__fired || []).length)) === 1, String(await p.evaluate(() => (window.__fired || []).length)));
    if (SHOTS) { await p.screenshot({ path: `${out}/mock-workflow-board.png`, fullPage: true }); await p.click(`[data-card="${second}"]`); await p.waitForTimeout(150); await p.screenshot({ path: `${out}/mock-workflow-drawer.png` }); }
    check('mock: no page errors', errs.length === 0, errs.join(' | '));
    await ctx.close(); srv2.close();
  }
  await b.close();
  console.log('PASS', ok.length); console.log('FAIL', bad.length); bad.forEach(x => console.log('  ✗', x));
  process.exit(bad.length ? 1 : 0);
})();
