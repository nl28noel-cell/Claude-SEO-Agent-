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
  const routes = ['overview', 'performance', 'funnel', 'analytics', 'ads', 'opportunities', 'opp-OPP-02', 'approvals', 'changes', 'market', 'local', 'findings', 'activity', 'sources', 'research-log'];
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
        if (SHOTS && (W === 1440 || (W === 400 && ['overview', 'opp-OPP-02', 'approvals', 'funnel', 'analytics', 'research-log'].includes(r)) || (W === 1180 && ['overview', 'performance'].includes(r))))
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
    const fr = dd.opportunities.find(o => o.id === first).research_status;
    check('gate1 = strategy approval: research version stored', w.gate1.research_version === fr.version && w.gate1.research_state === fr.state && w.gate1.research_override === false, JSON.stringify(w.gate1));
    const fired = await p.evaluate(() => window.__fired || []);
    check('agent trigger fired (fire_trigger with trigger_id)', fired.length === 1 && fired[0].tool === 'fire_trigger' && !!fired[0].input.trigger_id, JSON.stringify(fired));
    check('trigger result recorded', /angestoßen/.test(w?.trigger?.result || ''), JSON.stringify(w?.trigger));
    check('decision event logged', await p.evaluate(id => Object.values(window.__all.decisions || {}).some(x => x.item_id === id && x.gate === 1), first));
    await p.click('#wf-panel-body [data-close]'); await p.waitForTimeout(100);
    check('card moved to "Freigegeben / Produktion" with honest label', /Agent starting/.test(await p.locator(`.wf-col[data-col="production"] [data-card="${first}"]`).innerText()));
    // Gate 1 per Drag & Drop (öffnet Bestätigung)
    const second = dd.opportunities.filter(o => ['CREATE', 'OPTIMIZE', 'MERGE'].includes(o.type))[1].id;
    await p.dragAndDrop(`[data-card="${second}"]`, '.wf-col[data-col="production"]'); await p.waitForTimeout(200);
    check('drag & drop opens approval confirmation', (await p.locator('#wf-drawer').isVisible()) && /Drag & Drop/.test(await p.locator('#wf-panel-body').innerText()));
    const secRes = dd.opportunities.find(o => o.id === second).research_status.state;
    if (!['complete', 'complete_with_limits'].includes(secRes)) {
      check('incomplete research: override checkbox shown', (await p.locator('#wf-ovr').count()) === 1 && /Research not started|Research incomplete/.test(await p.locator('#wf-panel-body').innerText()));
      await p.click('[data-act="approve"]'); await p.waitForTimeout(200);
      check('incomplete research: approve without override refused', await p.evaluate(id => !window.__all.workflow?.[id], second));
      await p.check('#wf-ovr');
    }
    await p.click('[data-act="approve"]'); await p.waitForTimeout(300);
    const secCz = dd.opportunities.find(o => o.id === second).cannibalization;
    if (secCz?.warning) {
      check('gate 1: cannibalization warning dialog with 3 choices', (await p.locator('.gate-dialog').count()) === 1 && /Cannibalization Risk detected/.test(await p.locator('.gate-dialog').innerText()) && (await p.locator('.gate-dialog [data-g]').count()) === 3);
      await p.click('.gate-dialog [data-g="cancel"]'); await p.waitForTimeout(200);
      check('gate 1: cancel saves nothing', await p.evaluate(id => !window.__all.workflow?.[id], second));
      await p.click('[data-act="approve"]'); await p.waitForTimeout(200);
      await p.click('.gate-dialog [data-g="recommendation"]'); await p.waitForTimeout(300);
      const g1 = await p.evaluate(id => window.__all.workflow?.[id]?.gate1, second);
      check('gate 1: recommendation stored as change set incl. companion', g1?.cannibalization?.choice === 'recommendation' && g1?.change_set?.action === secCz.action && (g1?.change_set?.companions || []).length >= (second === 'OPP-01' ? 1 : 0), JSON.stringify(g1?.change_set));
      check('gate 1: no scroll lock left after dialog', !(await p.evaluate(() => document.documentElement.classList.contains('scroll-locked'))) || await p.locator('#wf-drawer').isVisible());
    }
    check('drag & drop approval persisted', await p.evaluate(id => window.__all.workflow?.[id]?.gate1?.status === 'approved', second));
    if (!['complete', 'complete_with_limits'].includes(secRes)) check('override recorded in gate1 + decision log', await p.evaluate(id => window.__all.workflow[id].gate1.research_override === true && Object.values(window.__all.decisions).some(x => x.item_id === id && x.decision === 'approve_override'), second));
    await p.click('#wf-panel-body [data-close]');
    // Reload → Status bleibt
    await p.reload({ waitUntil: 'networkidle' }); await p.waitForTimeout(300);
    check('persists across reload', (await p.locator('.wf-col[data-col="production"] .wf-card').count()) === 2);
    // Runner blockiert (Preflight) → Anzeige + „Erneut versuchen“ ohne neue Gate-1-Freigabe
    await p.evaluate(id => window.claude.use('db').then(db => db.collection('workflow').doc(id).update({ production: { status: 'blocked', block_reason: 'drive_tool_unavailable', block_detail: 'Drive fehlt', blocked_at: new Date().toISOString(), preflight: { repository: true, google_drive_write: false } } })), second);
    await p.waitForTimeout(200);
    check('blocked shows honest label', /Blocked – environment unavailable/.test(await p.locator(`[data-card="${second}"]`).innerText()));
    await p.click(`[data-card="${second}"]`); await p.waitForTimeout(150);
    check('blocked drawer shows reason + preflight', /drive_tool_unavailable/.test(await p.locator('#wf-panel-body').innerText()) && /✗ google_drive_write/.test(await p.locator('#wf-panel-body').innerText()));
    const g1Before = await p.evaluate(id => JSON.stringify(window.__all.workflow[id].gate1), second);
    await p.click('[data-act="retry"]'); await p.waitForTimeout(300);
    const wr = await p.evaluate(id => window.__all.workflow[id], second);
    check('retry → waiting, gate1 unchanged, trigger fired', wr.production.status === 'waiting' && JSON.stringify(wr.gate1) === g1Before && (await p.evaluate(() => (window.__fired || []).length)) === 1, JSON.stringify(wr.production));
    check('retry shows "Agent starting"', /Agent starting/.test(await p.locator('#wf-panel-body').innerText()));
    await p.click('#wf-panel-body [data-close]');
    await p.evaluate(() => { window.__fired = []; });
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
    check('gate2 persisted + WordPress draft queued (never publish)', w.gate2?.status === 'approved' && !!Date.parse(w.gate2.at) && w.wordpress?.status === 'queued' && !w.gate3, JSON.stringify(w.wordpress));
    await p.click('#wf-panel-body [data-close]');
    check('after gate 2: card in „WordPress-Draft & QA“ with honest label', /WordPress Draft queued/.test(await p.locator(`.wf-col[data-col="wordpress"] [data-card="${first}"]`).innerText()));
    check('revision and gate 2 both triggered the agent', (await p.evaluate(() => (window.__fired || []).length)) === 2, String(await p.evaluate(() => (window.__fired || []).length)));
    // Simulierte WordPress-Ergebnisse (kein echter WordPress-Zugriff)
    const wpSim = { status: 'qa_passed', mode: 'OPTIMIZE', draft_version: 1, documents: [{ role: 'primary', url: '/drohnen-baudokumentation/', wp_post_id: 5401, draft_post_id: 9001, edit_link: 'https://www.spreewald-luftaufnahmen.de/wp-admin/post.php?post=9001&action=elementor', preview_link: 'https://www.spreewald-luftaufnahmen.de/?page_id=9001&preview=true', original_link: 'https://www.spreewald-luftaufnahmen.de/drohnen-baudokumentation/' }],
      change_counts: { NEW: 5, EDIT: 4, KEEP: 6, REMOVE: 0 }, publish_summary: ['Title: „A“ → „B“', 'NEW: Häufige Fragen zur Baustellendokumentation mit Drohne', 'Unverändert: URL/Slug, Canonical, Indexierung, Menüs, Einstellungen'],
      qa: { content: { status: 'passed', issues: [] }, seo: { status: 'passed', issues: [] }, technical: { status: 'passed', issues: [] }, visual: { status: 'manual_review_required', note: 'Vorschau nur eingeloggt' }, overall: 'passed_manual_visual' },
      snapshots: [], rollback: { status: 'unavailable', why: ['Schreiben von _elementor_data nicht durch Schreibtest bestätigt'] } };
    await p.evaluate(([id, wp]) => window.claude.use('db').then(db => db.collection('workflow').doc(id).update({ wordpress: wp })), [first, wpSim]); await p.waitForTimeout(300);
    check('qa passed → card in „Ready for Publish“', (await p.locator(`.wf-col[data-col="publish"] [data-card="${first}"]`).count()) === 1);
    await p.click(`[data-card="${first}"]`); await p.waitForTimeout(200);
    let g3 = await p.locator('#wf-panel-body').innerText();
    check('gate 3 panel: preview + original + change set + counts + risks + QA + summary', (await p.locator('#wf-panel-body a', { hasText: 'WordPress Preview' }).count()) === 1 && (await p.locator('#wf-panel-body a', { hasText: 'Original Page' }).count()) === 1 && /Drive Change Set/.test(g3) && /5 NEW · 4 EDIT · 6 KEEP · 0 REMOVE/.test(g3) && /Ranking Risk/.test(g3) && /Cannibalization/.test(g3) && /Visual: manual review/.test(g3) && /Was wird beim Publish tatsächlich verändert/i.test(g3));
    check('gate 3 locked without rollback protection', /Rollback protection unavailable/.test(g3) && await p.locator('#wf-panel-body [data-act="gate3"]').isDisabled());
    await p.click('#wf-panel-body [data-close]');
    await p.evaluate(([id, wp]) => window.claude.use('db').then(db => db.collection('workflow').doc(id).update({ wordpress: { ...wp, snapshots: [{ post: 5401, verified: true, stored_doc_id: 'd1', taken_at: new Date().toISOString() }], rollback: { status: 'available', secondary: 'WordPress-Revisionen' } } })), [first, wpSim]); await p.waitForTimeout(300);
    await p.click(`[data-card="${first}"]`); await p.waitForTimeout(200);
    const firedG3 = await p.evaluate(() => (window.__fired || []).length);
    await p.click('#wf-panel-body [data-act="gate3"]'); await p.waitForTimeout(250);
    check('gate 3 requires confirmed visual review (nothing saved)', !(await p.evaluate(id => window.__all.workflow[id].gate3, first)));
    await p.check('#wf-vis'); await p.click('#wf-panel-body [data-act="gate3"]'); await p.waitForTimeout(400);
    w = await p.evaluate(id => window.__all.workflow[id], first);
    check('gate 3 stored for exact draft version → publish queued + agent triggered', w.gate3?.status === 'approved' && w.gate3.for_draft_version === 1 && w.gate3.visual_review_confirmed === true && w.wordpress.status === 'publish_queued' && (await p.evaluate(() => (window.__fired || []).length)) === firedG3 + 1, JSON.stringify(w.gate3));
    await p.click('#wf-panel-body [data-close]');
    await p.evaluate(id => window.claude.use('db').then(db => db.collection('workflow').doc(id).update({ wordpress: { ...window.__all.workflow[id].wordpress, status: 'published', published: { at: new Date().toISOString() } } })), first); await p.waitForTimeout(300);
    check('published → „Live / Monitoring“', /Published · Monitoring/.test(await p.locator(`.wf-col[data-col="live"] [data-card="${first}"]`).innerText()));
    if (SHOTS) { await p.screenshot({ path: `${out}/mock-workflow-wp-board.png`, fullPage: true }); }
    if (SHOTS) { await p.screenshot({ path: `${out}/mock-workflow-board.png`, fullPage: true }); await p.click(`[data-card="${second}"]`); await p.waitForTimeout(150); await p.screenshot({ path: `${out}/mock-workflow-drawer.png` }); }
    // Alte Gate-1-Freigabe ohne Strategie-Bezug → zurück in „Zur Prüfung“, keine Produktion
    const third = dd.opportunities.filter(o => ['CREATE', 'OPTIMIZE', 'MERGE'].includes(o.type))[2].id;
    await p.evaluate(id => window.claude.use('db').then(db => db.collection('workflow').doc(id).set({ opp_id: id, schema: 1, gate1: { status: 'approved', at: '2026-11-23T10:00:00Z', comment: 'alt' }, production: { status: 'blocked', block_reason: 'drive_tool_unavailable' } })), third);
    await p.waitForTimeout(200);
    check('legacy gate1 (before research stage) → "Strategie-Freigabe ausstehend" in review', /Strategie-Freigabe ausstehend/.test(await p.locator(`.wf-col[data-col="review"] [data-card="${third}"]`).innerText()));
    check('workflow cards show research status chip', (await p.locator('.wf-card .wf-res .chip').count()) >= nProd - 2);
    // Opportunity-Detail: A–J + Gate 1
    const rOpp = dd.opportunities.find(o => o.research);
    if (rOpp) {
      await p.goto(base2 + '#opp-' + rOpp.id, { waitUntil: 'networkidle' }); await p.waitForTimeout(250);
      check('detail: research sections A–J rendered', (await p.locator('section.rs').count()) === 10);
      const tx = await p.locator('#view, main, body').first().innerText();
      check('detail: research status banner', tx.includes(rOpp.research_status.label));
      check('detail: SERP quality labelled', /Indikativ|Validiert/.test(tx));
      check('detail: SERP competitors vs. research competitors separated', /SERP competitors · von Semrush als rankend bestätigt/.test(tx) && /Research competitors · Independent Web Research/.test(tx));
      check('detail: SERP Validation block (Semrush × Independent Web Research)', /SERP Validation/.test(tx) && /Semrush SERP/.test(tx) && /Independent Web Research/.test(tx) && /Cross-source agreement/.test(tx) && /keine Google\.de-SERP/.test(tx));
      check('detail: Semrush SERP plan + budget shown', /Semrush Organic Results/.test(tx) && /(Budget-Reserve – wartet|Wird ausgeführt|Cache aktuell|Freigabe nötig)/.test(tx));
      check('detail: IA current vs. recommended', /Current Architecture/.test(tx) && /Recommended Architecture/.test(tx));
      check('detail: no SERP dominance claim without real SERP', rOpp.research.C_serp.serp_competitors?.length || !/dominier/i.test(tx));
      check('detail: "Gate 1 – Strategie freigeben" after A–J', (await p.locator('.rs-gate').count()) === 1 && await p.evaluate(() => { const a = [...document.querySelectorAll('section.rs')].pop(), g = document.querySelector('.rs-gate'); return !!(a.compareDocumentPosition(g) & Node.DOCUMENT_POSITION_FOLLOWING); }));
      await p.click('.rs-toc [data-rs="H"]'); await p.waitForTimeout(400);
      check('detail: TOC jumps without changing route', (await p.evaluate(() => location.hash)) === '#opp-' + rOpp.id);
      if (SHOTS) await p.screenshot({ path: `${out}/mock-research-detail.png`, fullPage: true });
    }
    // Research Log / Evidence
    const RLd = dd.research_log;
    await p.goto(base2 + '#research-log', { waitUntil: 'networkidle' }); await p.waitForTimeout(250);
    check('research log: nav item is last', await p.evaluate(() => [...document.querySelectorAll('#nav a')].pop()?.dataset.route === 'research-log'));
    check('research log: all events listed', (await p.locator('.rl-ev').count()) === RLd.events.length, String(await p.locator('.rl-ev').count()));
    check('research log: newest first', await p.evaluate(() => document.querySelector('.rl-ev')?.dataset.ev) === RLd.events[RLd.events.length - 1].id);
    await p.selectOption('[data-f="type"]', 'semrush'); await p.waitForTimeout(100);
    const nSem = RLd.events.filter(e => e.source_ids.some(i => RLd.sources.find(s => s.id === i)?.type === 'semrush')).length;
    check('research log: source-type filter', (await p.locator('.rl-ev').count()) === nSem, String(nSem));
    const semTxt = await p.locator('#rl-list').innerText();
    check('research log: Semrush evidence (report, endpoint, DB, units/unknown, mode, no invented link)', /Batch Keyword Overview/.test(semTxt) && /phrase_these/.test(semTxt) && /DE/.test(semTxt) && /metadata unavailable/.test(semTxt) && /Cache hit|Live query/.test(semTxt) && /keine Report-URL/.test(semTxt) && (await p.locator('#rl-list a', { hasText: 'In Semrush öffnen' }).count()) === 0);
    await p.selectOption('[data-f="type"]', ''); await p.fill('[data-f="q"]', 'techpic'); await p.waitForTimeout(100);
    check('research log: search by domain', (await p.locator('.rl-ev').count()) >= 1 && (await p.locator('.rl-ev').count()) < RLd.events.length);
    await p.fill('[data-f="q"]', ''); await p.selectOption('[data-f="action"]', 'competitor_analysis'); await p.waitForTimeout(100);
    const compLinks = await p.locator('.rl-ev a[href^="https://"]').evaluateAll(as => as.map(a => a.href));
    check('research log: competitor URLs clickable', compLinks.some(h => h.includes('berlinskycrew.de')) && compLinks.some(h => h.includes('techpic.de')), compLinks.length);
    check('research log: exact fetch time shown for page analysis', !/Uhrzeit nicht protokolliert/.test(await p.locator('.rl-ev .rl-when').first().innerText()));
    await p.selectOption('[data-f="action"]', 'gsc_analysis'); await p.waitForTimeout(100);
    const gTxt = await p.locator('#rl-list').innerText();
    check('research log: GSC source with property/period/dimensions; missing time marked', /Property/.test(gTxt) && /2025-07-21 – 2026-11-20/.test(gTxt) && /query \+ page|query/.test(gTxt) && /Uhrzeit nicht protokolliert/.test(gTxt));
    if (SHOTS) { await p.selectOption('[data-f="action"]', ''); await p.waitForTimeout(100); await p.screenshot({ path: `${out}/mock-research-log.png`, fullPage: true }); }
    // Evidence je Opportunity + Findings mit Quellen
    await p.goto(base2 + '#opp-OPP-02', { waitUntil: 'networkidle' }); await p.waitForTimeout(250);
    const evTxt = await p.locator('#rs-evidence').innerText();
    check('evidence card: grouped counts', /GSC \(3\)/.test(evTxt) && /Semrush \(1\)/.test(evTxt) && /Competitor Websites \(8\)/.test(evTxt) && /Own Website \(3\)/.test(evTxt) && /GA4 \(1\)/.test(evTxt), evTxt.slice(0, 200));
    check('findings link to sources ("Quellen anzeigen")', (await p.locator('section.rs summary', { hasText: 'Quellen anzeigen' }).count()) >= 3);
    await p.click('#rs-evidence [data-rl-opp]'); await p.waitForTimeout(250);
    check('evidence → research log filtered by opportunity', (await p.evaluate(() => location.hash)) === '#research-log' && (await p.locator('[data-f="opp"]').inputValue()) === 'OPP-02');
    await p.goto(base2 + '#activity', { waitUntil: 'networkidle' }); await p.waitForTimeout(200);
    check('agent activity: research groups from same log + link', /Research \(\d+ Aktionen\)/.test(await p.locator('body').innerText()) && (await p.locator('a[data-rl-opp]').count()) >= 1);
    // Gate-1-Entscheidungsvorlage (4 Fragen) + Kannibalisierung
    await p.goto(base2 + '#opp-OPP-02', { waitUntil: 'networkidle' }); await p.waitForTimeout(250);
    let gb = await p.locator('#g1-brief').innerText();
    check('gate-1 brief: four questions', ['Warum sollten wir das machen?', 'Was genau werden wir machen?', 'Was wird auf der Seite behandelt?', 'Was passiert mit unseren anderen Seiten?'].every(q => gb.toLowerCase().includes(q.toLowerCase())));
    check('gate-1 brief OPP-02: H1 KEEP + diagnosis', /Current Page Diagnosis/i.test(gb) && /baudokumentation drohne berlin/i.test(gb) && /KEEP/.test(gb));
    check('gate-1 brief OPP-02: page preview (purpose, topics, excluded, structure)', /Page Purpose/.test(gb) && /Themen auf der Seite/.test(gb) && /Bewusst nicht enthalten/.test(gb) && /Rough Page Structure/.test(gb) && /Cannibalization: Low/.test(gb));
    await p.goto(base2 + '#opp-OPP-01', { waitUntil: 'networkidle' }); await p.waitForTimeout(250);
    gb = await p.locator('#g1-brief').innerText();
    check('gate-1 brief OPP-01: high risk + companion + affected URL', /Cannibalization: High/.test(gb) && /Companion Optimization required/.test(gb) && /drohne-dach-gebaeude-inspektion/.test(gb) && /OPP-03/.test(gb));
    check('gate-1 brief OPP-01: current page diagnosis + protection + loss risk + sensitive changes', /Current Page Diagnosis/i.test(gb) && /Ranking Protection/i.test(gb) && /Risk of Ranking Loss/i.test(gb) && /Sensitive Changes/i.test(gb) && /dachkontrolle mit drohne/i.test(gb));
    const dg = await p.locator('#rs-diagnosis').innerText();
    check('diagnosis card: KEEP/IMPROVE/ADD/REMOVE + change summary + protection list', /KEEP/.test(dg) && /IMPROVE/.test(dg) && /ADD/.test(dg) && /REMOVE/.test(dg) && /Change Summary/i.test(dg) && /Ranking Protection List/i.test(dg));
    if (SHOTS) await p.screenshot({ path: `${out}/mock-gate1-OPP-01.png`, fullPage: true });
    await p.goto(base2 + '#opp-OPP-09', { waitUntil: 'networkidle' }); await p.waitForTimeout(200);
    check('cannibalization shown for opportunity without dossier too', /Cannibalization/.test(await p.locator('#view, main').first().innerText()));
    await p.goto(base2 + '#opp-OPP-07', { waitUntil: 'networkidle' }); await p.waitForTimeout(200);
    const d7 = await p.locator('#rs-diagnosis').innerText();
    check('ranking protection shown for OPTIMIZE without dossier (list + loss risk)', /Ranking Protection List/i.test(d7) && /Ranking loss: Medium/i.test(d7) && (await p.locator('#rs-diagnosis tbody tr').count()) >= 40, String(await p.locator('#rs-diagnosis tbody tr').count()));
    // Research-Retry (simulierte Zustände; kein echter Agentenlauf)
    await p.goto(base2 + '#opp-OPP-01', { waitUntil: 'networkidle' }); await p.waitForTimeout(250);
    let rb = await p.locator('.rr.banner').innerText();
    check('retry: missing components listed + primary button', /Fehlend:/.test(rb) && /Independent Web Research: ?Missing/i.test(rb.replace(/\n/g, ' ')) && /GSC-Auswertung: ?Complete/i.test(rb.replace(/\n/g, ' ')) && (await p.locator('.rr.banner [data-rr="OPP-01"]').innerText()) === 'Fehlende Research nachholen');
    check('retry: paid SERP stays blocked (budget) and is explained', /Budget-Reserve/.test(rb));
    const firedBefore = await p.evaluate(() => (window.__fired || []).length);
    await p.click('.rr.banner [data-rr="OPP-01"]'); await p.waitForTimeout(400);
    let rr = await p.evaluate(() => window.__all.workflow['OPP-01']?.research_retry);
    check('retry: queued on the existing workflow entry (no new record), only missing steps', rr?.status === 'queued' && JSON.stringify(rr.components) === JSON.stringify(['web_research', 'competitors', 'content_gap', 'strategy']) && JSON.stringify(rr.blocked) === '["serp"]' && (await p.evaluate(() => Object.keys(window.__all.workflow).filter(k => k.startsWith('OPP-01')).length)) === 1, JSON.stringify(rr));
    check('retry: agent triggered + decision logged', (await p.evaluate(() => (window.__fired || []).length)) === firedBefore + 1 && /research_retry/.test(await p.evaluate(() => JSON.stringify((window.__fired || []).slice(-1)))) && await p.evaluate(() => Object.values(window.__all.decisions).some(x => x.decision === 'research_retry' && x.item_id === 'OPP-01')));
    await p.waitForTimeout(200);
    check('retry: button disabled while queued (no double click)', await p.locator('.rr.banner [data-rr="OPP-01"]').isDisabled() && /Research retry queued/.test(await p.locator('.rr.banner').innerText()));
    await p.evaluate(() => window.claude.use('db').then(db => db.collection('workflow').doc('OPP-01').update({ research_retry: { ...window.__all.workflow['OPP-01'].research_retry, status: 'running', started_at: new Date().toISOString(), done: ['web_research', 'competitors'] } })));
    await p.waitForTimeout(300);
    check('retry: progress „2 von 4“ while running', /Research running/.test(await p.locator('.rr.banner').innerText()) && /2 von 4 fehlenden Schritten abgeschlossen/.test(await p.locator('.rr.banner').innerText()));
    await p.evaluate(() => window.claude.use('db').then(db => db.collection('workflow').doc('OPP-01').update({ research_retry: { ...window.__all.workflow['OPP-01'].research_retry, status: 'blocked', block_reason: 'Wettbewerber-Hosts im Netzwerk nicht freigegeben' } })));
    await p.waitForTimeout(300);
    rb = await p.locator('.rr.banner').innerText();
    check('retry: blocked with understandable cause, retry possible again', /Research blocked/.test(rb) && /Wettbewerber-Hosts im Netzwerk nicht freigegeben/.test(rb) && !(await p.locator('.rr.banner [data-rr="OPP-01"]').isDisabled()));
    await p.goto(base2 + '#opp-OPP-02', { waitUntil: 'networkidle' }); await p.waitForTimeout(250);
    check('retry: only paid research missing → no retry button, explanation', (await p.locator('[data-rr="OPP-02"]').count()) === 0 && /Nur kostenpflichtige Research fehlt/.test(await p.locator('.rr.banner').innerText()));
    await p.goto(base2 + '#approvals', { waitUntil: 'networkidle' }); await p.waitForTimeout(250);
    await p.click('[data-card="OPP-05"]'); await p.waitForTimeout(200);
    check('drawer (not started): primary „Research starten“, override secondary + collapsed', (await p.locator('#wf-panel-body [data-rr="OPP-05"]').innerText()) === 'Research starten' && await p.locator('#wf-panel-body [data-rr="OPP-05"]').evaluate(b => b.classList.contains('primary')) && !(await p.locator('#wf-panel-body details.ovr').evaluate(d => d.open)) && !(await p.locator('#wf-panel-body [data-act="approve"]').evaluate(b => b.classList.contains('primary'))));
    if (SHOTS) await p.screenshot({ path: `${out}/mock-research-retry-drawer.png` });
    await p.click('#wf-panel-body [data-close]'); await p.waitForTimeout(100);
    await p.goto(base2 + '#sources', { waitUntil: 'networkidle' }); await p.waitForTimeout(200);
    const wpc = await p.locator('#wp-card').innerText();
    check('data sources: WordPress card (read-only tested, publish locked, no credentials)', /administrator/.test(wpc) && /gesperrt/.test(wpc) && /Elementor/.test(wpc) && !/password|passwort|token/i.test(wpc.replace(/Zugangsdaten: keine im Repository\/Artifact/, '')));
    check('WordPress sandbox: PARTIAL status matrix (6 rows, VERIFIED/BLOCKED/PENDING/NOT YET VERIFIED)', (await p.locator('#wp-matrix tr').count()) === 6 && /Elementor Write: PARTIAL/.test(wpc) && /Standard Elementor widgets\s*VERIFIED/.test(wpc) && /Live OPTIMIZE automation\s*BLOCKED/.test(wpc) && /PENDING FULL SANDBOX VALIDATION/.test(wpc) && /NOT YET VERIFIED/.test(wpc) && !/insufficient/i.test(wpc));
    check('WordPress: Trustindex analysis + architecture options + next test proposed (not executed)', (await p.locator('#wp-trustindex').count()) === 1 && (await p.locator('#wp-architecture tbody tr').count()) === 5 && /nicht ausgeführt/.test(await p.locator('#wp-next-test').innerText()) && /kein Trustindex-Plugin/.test(await p.locator('#wp-trustindex').textContent()));
    check('WordPress sandbox: test draft 6955 kept (not deleted)', /nicht löschen/.test(wpc));
    check('WordPress sandbox: status, test draft 6955 (draft), live page unchanged, stop result, options', /PARTIAL/.test(wpc) && /6955/.test(wpc) && /draft/.test(wpc) && /unverändert/.test(wpc) && /HTTP 403/.test(wpc) && /Optionen/.test(wpc) && (await p.locator('#wp-sandbox a[href*="post=6955"]').count()) === 1 && (await p.locator('#wp-sandbox a[href*="post=5401"]').count()) === 0);
    // Local Opportunity Matrix
    await p.goto(base2 + '#local', { waitUntil: 'networkidle' }); await p.waitForTimeout(300);
    const lm = await p.locator('#local-matrix').innerText();
    check('local matrix: all cells with engine recommendation + transparent gaps', (await p.locator('#local-matrix tbody tr').count()) === dd.local.cells.length && /USE MAIN SERVICE PAGE/.test(lm) && /nicht erhoben/.test(lm) && /nicht gemessen/.test(lm), String(await p.locator('#local-matrix tbody tr').count()));
    // Scroll-Regression: Drawer → Link → andere Seite, Escape, Navigation, zurück
    const canScroll = async () => { await p.evaluate(() => window.scrollTo(0, 0)); await p.mouse.move(700, 400); await p.mouse.wheel(0, 900); await p.waitForTimeout(250); return (await p.evaluate(() => window.scrollY)) > 100 && !(await p.evaluate(() => document.documentElement.classList.contains('scroll-locked'))); };
    await p.goto(base2 + '#approvals', { waitUntil: 'networkidle' }); await p.waitForTimeout(250);
    await p.click('[data-card="OPP-05"]'); await p.waitForTimeout(150);
    await p.click('#wf-panel-body a[href="#opp-OPP-05"]'); await p.waitForTimeout(300);
    check('scroll: after leaving drawer via link to opportunity detail', await canScroll());
    await p.goBack(); await p.waitForTimeout(300);
    check('scroll: after going back to workflow', await canScroll());
    await p.click('[data-card="OPP-02"]'); await p.waitForTimeout(150); await p.keyboard.press('Escape'); await p.waitForTimeout(150);
    check('scroll: after closing drawer with Escape', await canScroll());
    await p.click('[data-card="OPP-02"]'); await p.waitForTimeout(150); await p.evaluate(() => { location.hash = '#opportunities'; }); await p.waitForTimeout(300);
    check('scroll: drawer open + hash navigation → opportunities scrollable', await canScroll());
    await p.goto(base2 + '#opp-OPP-02', { waitUntil: 'networkidle' }); await p.waitForTimeout(250); await p.click('[data-gate1="OPP-02"]'); await p.waitForTimeout(350);
    check('scroll: detail → Gate-1 button opens drawer in workflow', await p.locator('#wf-drawer').isVisible());
    await p.click('#wf-panel-body [data-close]'); await p.waitForTimeout(150);
    check('scroll: after closing drawer via ✕', await canScroll());
    const nOpp = dd.opportunities.find(o => ['CREATE', 'OPTIMIZE', 'MERGE'].includes(o.type) && !o.research);
    if (nOpp) { await p.goto(base2 + '#opp-' + nOpp.id, { waitUntil: 'networkidle' }); await p.waitForTimeout(200);
      check('detail without dossier: "Research not started" visible', /Research not started/.test(await p.locator('body').innerText())); }
    check('mock: no page errors', errs.length === 0, errs.join(' | '));
    await ctx.close(); srv2.close();
  }
  await b.close();
  console.log('PASS', ok.length); console.log('FAIL', bad.length); bad.forEach(x => console.log('  ✗', x));
  process.exit(bad.length ? 1 : 0);
})();
