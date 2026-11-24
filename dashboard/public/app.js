/* SEO Autopilot Control Center – vanilla JS, keine Abhängigkeiten.
   Liest ausschließlich data/clients.json und data/<client>/dashboard.json (erzeugt von tools/build_dashboard_data.py). */
"use strict";

const S = { clients: [], client: null, d: null, range: "3M", perfRange: "3M", gaRange: "12M", ui: {} };
const $ = (sel, el = document) => el.querySelector(sel);
const view = () => $("#view");

/* ------------------------------------------------------------ formatting */
const nf = new Intl.NumberFormat("de-DE");
const fmtN = v => (v === null || v === undefined || Number.isNaN(v)) ? "–" : nf.format(Math.round(v));
const fmtD = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v)) ? "–" : v.toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtPct = (v, d = 2) => (v === null || v === undefined) ? "–" : (v * 100).toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d }) + " %";
const fmtDate = iso => { if (!iso) return "Unknown"; const [y, m, d] = iso.slice(0, 10).split("-"); return `${d}.${m}.${y}`; };
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const chip = (text, color = "", dot = false) => `<span class="chip ${color}">${dot ? '<span class="dot"></span>' : ""}${esc(text)}</span>`;
const typeChip = t => chip(t, { CREATE: "blue", OPTIMIZE: "green", MERGE: "amber", MONITOR: "amber", IGNORE: "" }[t] || "", false).replace('class="chip', 'class="chip type');
const prioChip = p => chip({ critical: "Critical", high: "High", medium: "Medium", low: "Low" }[p] || p, { critical: "red", high: "amber", medium: "blue", low: "" }[p]);
const confChip = c => chip("Confidence: " + ({ high: "High", medium: "Medium", low: "Low" }[c] || "Unknown"), "outline");
const sevChip = s => chip({ high: "High", medium: "Medium", low: "Low" }[s] || s, { high: "red", medium: "amber", low: "" }[s]);
const statusChip = s => {
  const l = (s || "").toLowerCase();
  const c = /block|overdue|critical/.test(l) ? "red" : /monitor|wait|freeze|review|candidate|due|decision|planned|ready/.test(l) ? "amber" : /resolved|done|completed|connected|healthy|fresh|ok/.test(l) ? "green" : /ignored|not pursued|note/.test(l) ? "" : "blue";
  return chip(s, c, true);
};
function delta(cur, prev, { invert = false, unit = "%", abs = false } = {}) {
  if (cur === null || cur === undefined || prev === null || prev === undefined) return `<span class="flat">no comparison</span>`;
  if (abs) {
    const dv = cur - prev; const good = invert ? dv < 0 : dv > 0;
    const cls = Math.abs(dv) < 0.05 ? "flat" : good ? "up" : "down";
    const word = Math.abs(dv) < 0.05 ? "" : invert ? (dv < 0 ? " better" : " worse") : "";
    return `<span class="${cls}">${dv > 0 ? "+" : ""}${fmtD(dv)}${unit ? " " + unit : ""}${word}</span>`;
  }
  if (prev === 0) return `<span class="flat">prev. 0</span>`;
  const p = (cur - prev) / prev * 100; const good = invert ? p < 0 : p > 0;
  const cls = Math.abs(p) < 0.5 ? "flat" : good ? "up" : "down";
  return `<span class="${cls}">${p > 0 ? "▲ +" : p < 0 ? "▼ " : ""}${fmtD(p)} %</span>`;
}
function freshness(iso, staleDays = 7) {
  if (!iso) return chip("Unknown", "");
  const t = new Date(); const today = Date.UTC(t.getFullYear(), t.getMonth(), t.getDate());
  const [y, m, dd] = iso.slice(0, 10).split("-").map(Number);
  const days = Math.max(0, Math.round((today - Date.UTC(y, m - 1, dd)) / 864e5));
  return days <= staleDays ? chip(`Fresh · ${ageText(days)}`, "green", true) : chip(`Stale · ${ageText(days)}`, "amber", true);
}

/* ------------------------------------------------------------ data helpers */
const RANGES = { "28D": 28, "3M": 91, "6M": 182, "12M": 365, "16M": null };
function windowRows(range) {
  const daily = S.d.gsc.daily; const n = RANGES[range];
  if (!n) return { cur: daily, prev: null, from: daily[0]?.date, to: daily.at(-1)?.date };
  const cur = daily.slice(-n); const prevRows = daily.slice(-2 * n, -n);
  return { cur, prev: prevRows.length === n ? prevRows : null, from: cur[0]?.date, to: cur.at(-1)?.date };
}
function sumRows(rows) {
  if (!rows) return null;
  const c = rows.reduce((a, r) => a + r.clicks, 0), i = rows.reduce((a, r) => a + r.impressions, 0);
  const pw = rows.reduce((a, r) => a + r.position * r.impressions, 0);
  return { clicks: c, impressions: i, ctr: i ? c / i : null, position: i ? pw / i : null };
}
function bucket(rows, mode) {
  if (mode === "day") return rows.map(r => ({ x: r.date, clicks: r.clicks, impressions: r.impressions, position: r.position, n: 1 }));
  const map = new Map();
  for (const r of rows) {
    let key;
    if (mode === "week") { const d = new Date(r.date + "T00:00:00Z"); const wd = (d.getUTCDay() + 6) % 7; d.setUTCDate(d.getUTCDate() - wd); key = d.toISOString().slice(0, 10); }
    else key = r.date.slice(0, 7) + "-01";
    const b = map.get(key) || { x: key, clicks: 0, impressions: 0, pw: 0, n: 0 };
    b.clicks += r.clicks; b.impressions += r.impressions; b.pw += r.position * r.impressions; b.n++;
    map.set(key, b);
  }
  return [...map.values()].map(b => ({ ...b, position: b.impressions ? b.pw / b.impressions : null }));
}
const modeFor = range => (range === "28D" || range === "3M") ? "day" : "week";
const pagePath = p => p || "–";

/* ------------------------------------------------------------ tooltip */
const tip = { el: null, show(html, e) { this.el ||= $("#tooltip"); this.el.innerHTML = html; this.el.classList.add("on"); this.move(e); },
  move(e) { const w = this.el.offsetWidth, h = this.el.offsetHeight; let x = e.clientX + 14, y = e.clientY + 14; if (x + w > innerWidth - 8) x = e.clientX - w - 14; if (y + h > innerHeight - 8) y = e.clientY - h - 14; this.el.style.left = x + "px"; this.el.style.top = y + "px"; },
  hide() { this.el?.classList.remove("on"); } };
document.addEventListener("mouseover", e => { const t = e.target.closest("[data-tip]"); if (t) tip.show(esc(t.dataset.tip), e); });
document.addEventListener("mouseout", e => { if (e.target.closest("[data-tip]")) tip.hide(); });

/* ------------------------------------------------------------ chart (SVG) */
const SVGNS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs = {}, parent) {
  const e = document.createElementNS(SVGNS, tag); let style = "";
  // CSS-Variablen funktionieren nicht in SVG-Präsentationsattributen -> als Inline-Style setzen (Theme-fähig)
  for (const [k, v] of Object.entries(attrs)) { if ((k === "fill" || k === "stroke") && String(v).startsWith("var(")) style += `${k}:${v};`; else e.setAttribute(k, v); }
  if (style) e.setAttribute("style", style);
  parent && parent.appendChild(e); return e;
}
function niceMax(v) { if (v <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))); const n = v / p; const step = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find(x => n <= x); return step * p; }
/** series: [{key,label,color,type:'line'|'area'|'bar'}], points: [{x, ...}] */
function chart({ points, series, height = 180, invert = false, yFmt = fmtN, xMode = "day", yMin = null, width = 800 }) {
  const wrap = document.createElement("div");
  const W = Math.max(300, Math.round(width)), H = height, m = { l: 44, r: 12, t: 10, b: 22 };
  const svg = svgEl("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, width: "100%", height: H });
  wrap.appendChild(svg);
  if (!points.length) { wrap.innerHTML = `<div class="empty">No data</div>`; return wrap; }
  const vals = series.flatMap(s => points.map(p => p[s.key]).filter(v => v !== null && v !== undefined));
  let lo = yMin ?? (invert ? Math.max(1, Math.floor(Math.min(...vals))) : 0), hi = invert ? Math.ceil(Math.max(...vals)) : niceMax(Math.max(...vals) * 1.05);
  if (hi === lo) hi = lo + 1;
  const iw = W - m.l - m.r, ih = H - m.t - m.b, n = points.length;
  const X = i => m.l + (n === 1 ? iw / 2 : i * iw / (n - 1));
  const Y = v => invert ? m.t + (v - lo) / (hi - lo) * ih : m.t + ih - (v - lo) / (hi - lo) * ih;
  const g = svgEl("g", { class: "grid" }, svg);
  for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4; const y = Y(v); svgEl("line", { x1: m.l, x2: W - m.r, y1: y, y2: y }, g); const t = svgEl("text", { x: m.l - 6, y: y + 4, "text-anchor": "end" }, svg); t.textContent = yFmt(v); }
  const ticks = Math.max(2, Math.min(6, n, Math.floor(iw / 72))); for (let k = 0; k < ticks; k++) { const i = Math.round(k * (n - 1) / Math.max(1, ticks - 1)); const t = svgEl("text", { x: X(i), y: H - 6, "text-anchor": k === 0 ? "start" : k === ticks - 1 ? "end" : "middle" }, svg); const x = points[i].x; t.textContent = xMode === "month" ? x.slice(5, 7) + "/" + x.slice(2, 4) : fmtDate(x).slice(0, 6); }
  for (const s of series) {
    const pts = points.map((p, i) => [X(i), p[s.key] === null || p[s.key] === undefined ? null : Y(p[s.key])]);
    if (s.type === "bar") {
      const bw = Math.max(1.5, iw / n * 0.62);
      pts.forEach(([x, y]) => { if (y !== null) svgEl("rect", { x: x - bw / 2, y, width: bw, height: Math.max(0, Y(lo) - y), fill: s.color, rx: 1.5, opacity: .85 }, svg); });
    } else {
      const d = pts.filter(p => p[1] !== null).map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");
      if (s.type === "area") svgEl("path", { d: d + `L${pts.at(-1)[0]},${Y(lo)}L${pts[0][0]},${Y(lo)}Z`, fill: s.color, opacity: .12 }, svg);
      svgEl("path", { d, fill: "none", stroke: s.color, "stroke-width": 1.8, "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round" }, svg);
    }
  }
  const cross = svgEl("line", { class: "cross", y1: m.t, y2: m.t + ih, "stroke-dasharray": "3 3", opacity: 0, "vector-effect": "non-scaling-stroke" }, svg);
  const hit = svgEl("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent" }, svg);
  hit.addEventListener("mousemove", e => {
    const r = svg.getBoundingClientRect(); const px = (e.clientX - r.left) / r.width * W;
    const i = Math.max(0, Math.min(n - 1, Math.round((px - m.l) / iw * (n - 1)))); const p = points[i];
    cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("opacity", 1);
    const lab = xMode === "week" ? "Week of " + fmtDate(p.x) : xMode === "month" ? p.x.slice(0, 7) : fmtDate(p.x);
    tip.show(`<b>${lab}</b><br>` + series.map(s => `<span style="color:${s.color}">●</span> ${esc(s.label)}: ${p[s.key] === null || p[s.key] === undefined ? "–" : (s.fmt || yFmt)(p[s.key])}`).join("<br>"), e);
  });
  hit.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); tip.hide(); });
  return wrap;
}
function legend(series) { return `<div class="chart-legend">${series.map(s => `<span><i style="background:${s.color}"></i>${esc(s.label)}</span>`).join("")}</div>`; }
function chartInto(id, opts) { const el = document.getElementById(id); if (!el) return; el.innerHTML = ""; el.appendChild(chart({ ...opts, width: el.clientWidth || 800 })); el._chart = opts; }
function mount(id, node) { const el = document.getElementById(id); if (el) { el.innerHTML = ""; el.appendChild(node); } }

/* ------------------------------------------------------------ table component */
function table({ columns, rows, search = [], filters = [], pageSize = 15, onRow, sort = null, empty = "No rows", toolsExtra = "" }) {
  const st = { q: "", f: {}, sort: sort || { key: null, dir: -1 }, page: 0 };
  const root = document.createElement("div");
  root.innerHTML = `<div class="tbl-tools">${search.length ? `<input type="search" placeholder="Search…" aria-label="Search">` : ""}
    ${filters.map(f => `<select class="f" data-f="${f.key}" aria-label="${esc(f.label)}"><option value="">${esc(f.label)}: All</option>${f.options.map(o => `<option>${esc(o)}</option>`).join("")}</select>`).join("")}
    <span class="spacer"></span>${toolsExtra}<span class="mini count"></span></div>
    <div class="tbl-wrap"><table><thead><tr>${columns.map(c => `<th class="${c.num ? "num" : ""} ${c.sort === false ? "" : "sortable"}" data-k="${c.key}" ${c.tip ? `data-tip="${esc(c.tip)}"` : ""}>${esc(c.label)}<span class="arr"></span></th>`).join("")}</tr></thead><tbody></tbody></table></div>
    <div class="tbl-foot"><span class="info"></span><span class="row"><button class="btn prev">‹ Prev</button><button class="btn next">Next ›</button></span></div>`;
  const tbody = $("tbody", root);
  const getv = (r, c) => c.value ? c.value(r) : r[c.key];
  function filtered() {
    let out = rows;
    if (st.q) { const q = st.q.toLowerCase(); out = out.filter(r => search.some(k => String(r[k] ?? "").toLowerCase().includes(q))); }
    for (const [k, v] of Object.entries(st.f)) if (v) { const f = filters.find(x => x.key === k); out = out.filter(r => (f.match ? f.match(r, v) : String(r[k]) === v)); }
    if (st.sort.key) { const c = columns.find(c => c.key === st.sort.key); out = [...out].sort((a, b) => { const x = getv(a, c), y = getv(b, c); if (x === y) return 0; if (x === null || x === undefined) return 1; if (y === null || y === undefined) return -1; return (x > y ? 1 : -1) * st.sort.dir; }); }
    return out;
  }
  function render() {
    const all = filtered(); const pages = Math.max(1, Math.ceil(all.length / pageSize)); st.page = Math.min(st.page, pages - 1);
    const slice = all.slice(st.page * pageSize, (st.page + 1) * pageSize);
    tbody.innerHTML = slice.length ? slice.map((r, i) => `<tr class="${onRow ? "click" : ""}" data-i="${st.page * pageSize + i}">${columns.map(c => `<td class="${c.num ? "num" : ""}">${c.render ? c.render(r) : esc(getv(r, c) ?? "–")}</td>`).join("")}</tr>`).join("")
      : `<tr><td colspan="${columns.length}" class="empty">${esc(empty)}</td></tr>`;
    $(".info", root).textContent = all.length ? `${st.page * pageSize + 1}–${Math.min(all.length, (st.page + 1) * pageSize)} of ${all.length}` : "0 rows";
    $(".prev", root).disabled = st.page === 0; $(".next", root).disabled = st.page >= pages - 1;
    root.querySelectorAll("th").forEach(th => { const a = $(".arr", th); a.textContent = th.dataset.k === st.sort.key ? (st.sort.dir > 0 ? "▲" : "▼") : ""; });
    root._rows = all;
  }
  $("input[type=search]", root)?.addEventListener("input", e => { st.q = e.target.value; st.page = 0; render(); });
  root.querySelectorAll("select[data-f]").forEach(s => s.addEventListener("change", e => { st.f[s.dataset.f] = e.target.value; st.page = 0; render(); }));
  root.querySelectorAll("th.sortable").forEach(th => th.addEventListener("click", () => { const k = th.dataset.k; st.sort = { key: k, dir: st.sort.key === k ? -st.sort.dir : (columns.find(c => c.key === k).num ? -1 : 1) }; render(); }));
  $(".prev", root).addEventListener("click", () => { st.page--; render(); });
  $(".next", root).addEventListener("click", () => { st.page++; render(); });
  if (onRow) tbody.addEventListener("click", e => { const tr = e.target.closest("tr[data-i]"); if (tr && !e.target.closest("a")) onRow(root._rows[+tr.dataset.i]); });
  render();
  return root;
}
const qCols = (withPage = true) => [
  { key: "query", label: "Query", render: r => `<div class="q">${esc(r.query)}</div><div class="s">${esc(r.segment)} · ${esc(r.cluster)}</div>` },
  { key: "clicks", label: "Clicks", num: true, render: r => fmtN(r.clicks) },
  { key: "impressions", label: "Impressions", num: true, render: r => fmtN(r.impressions) },
  { key: "ctr", label: "CTR", num: true, render: r => fmtPct(r.ctr) },
  { key: "position", label: "Position", num: true, render: r => fmtD(r.position) },
  { key: "imp_change", label: "Δ Impr. (90d)", num: true, tip: "Impressionen letzte 90 Tage minus die 90 Tage davor", render: r => `<span class="${r.imp_change > 0 ? "up" : r.imp_change < 0 ? "down" : "flat"}">${r.imp_change > 0 ? "+" : ""}${fmtN(r.imp_change)}</span>` },
  ...(withPage ? [{ key: "page", label: "Landing page", render: r => `<span class="s">${esc(pagePath(r.page))}</span>${r.n_pages > 1 ? ` <span class="chip amber" data-tip="Query rankt mit ${r.n_pages} URLs">${r.n_pages} URLs</span>` : ""}` }] : []),
];
const segFilter = () => ({ key: "segment", label: "Segment", options: ["Strategic B2B", "Price", "B2C", "Brand", "Unknown"] });

/* ------------------------------------------------------------ pages */
const pages = {};

pages.overview = () => {
  const d = S.d, h = d.health, src = d.sources;
  const w = windowRows("28D"), cur = sumRows(w.cur), prev = sumRows(w.prev);
  const tasks = d.tasks;
  const last = tasks.filter(t => t.state === "completed").slice(-4).reverse();
  const actOrder = [...tasks.filter(t => t.state === "blocked"), ...tasks.filter(t => t.state === "needs_review"), ...tasks.filter(t => t.state === "monitoring"), ...tasks.filter(t => t.state === "planned").slice(0, 2), ...last];
  const healthColor = { Healthy: "green", Attention: "amber", Critical: "red" }[h.status];
  view().innerHTML = `
  <div class="page-head"><div><h1>SEO Autopilot</h1><div class="sub">${esc(d.client.name)} · ${esc(d.client.region)}</div></div>
    <div class="row"><span class="mini">GSC data through <b>${fmtDate(d.gsc.last)}</b> · fetched ${fmtDate(src.gsc.last_fetch)}</span>${chip("Health: " + h.status, healthColor, true)}</div></div>
  <div class="strip">
    ${chip("GSC " + (src.gsc.status === "connected" ? "Connected" : src.gsc.status), src.gsc.status === "connected" ? "green" : "red", true)}
    ${chip("Semrush " + (src.semrush.status === "connected" ? "Connected" : src.semrush.status), src.semrush.status === "connected" ? "green" : "red", true)}
    ${chip("GA4 " + (src.ga4?.status === "connected" ? "Connected" : src.ga4?.status || "Unknown"), src.ga4?.status === "connected" ? "green" : "red", true)}
    <a href="#ads">${chip("Google Ads Connected · Historie via GA4", src.google_ads?.status?.startsWith("connected") ? "green" : "amber", true)}</a>
    ${chip("Website Monitoring " + (src.website.monitors?.length ? "Active" : "Off"), src.website.monitors?.length ? "green" : "", true)}
    <a href="#changes">${chip(`${h.freezes} Change Freeze`, h.freezes ? "amber" : "")}</a>
    <a href="#approvals">${chip(`${h.pending_approvals} Pending Approvals`, h.pending_approvals ? "red" : "")}</a>
    <a href="#findings">${chip(`${h.open_findings} Open Findings`, h.open_findings ? "amber" : "")}</a>
    ${h.blocked_tasks ? `<a href="#activity">${chip(`${h.blocked_tasks} Blocked Task`, "red")}</a>` : ""}
    <span class="mini" style="align-self:center">Decisions: <span id="ov-dec">${decisionSummary()}</span></span>
  </div>
  <div class="kpis">
    ${kpi("Clicks", fmtN(cur.clicks), delta(cur.clicks, prev?.clicks), "Letzte 28 Tage vs. 28 Tage davor")}
    ${kpi("Impressions", fmtN(cur.impressions), delta(cur.impressions, prev?.impressions), "Letzte 28 Tage vs. 28 Tage davor")}
    ${kpi("Avg. Position", fmtD(cur.position), delta(cur.position, prev?.position, { invert: true, abs: true, unit: "" }), "Impressions-gewichtet, 28 Tage; niedriger = besser")}
    ${kpi("Tracked Opportunities", fmtN(h.tracked_opportunities), `<span class="flat">excl. IGNORE</span>`)}
    ${kpi("Open Findings", fmtN(h.open_findings), `<a href="#findings">View findings</a>`)}
    ${kpi("Pending Decisions", fmtN(h.pending_decisions), `<span class="flat">${h.pending_approvals} approvals · ${h.pending_decisions - h.pending_approvals} business</span>`)}
  </div>
  <div class="grid g-main">
    <div class="card"><div class="card-h"><h2>Needs your attention</h2><span class="hint">${d.attention.length} items · rule-based</span></div>
      <div class="att">${d.attention.length ? d.attention.map(attItem).join("") : `<div class="empty">Nothing needs your attention.</div>`}</div></div>
    <div class="card"><div class="card-h"><h2>Agent Activity</h2><a href="#activity" class="mini">All activity →</a></div>
      <div class="act">${actOrder.slice(0, 7).map(actItem).join("")}</div>
      <div class="card-b mini" style="padding-top:8px">Agent runs on demand in Claude Code sessions – there is no permanently running background process.</div></div>
  </div>
  <div class="card mt"><div class="card-h"><div><h2>Organic Search Performance</h2><div class="hint">Google Search Console · ${S.range === "16M" ? "all available data" : "range " + S.range} · ${modeFor(S.range) === "week" ? "weekly" : "daily"}</div></div>
    <div class="row">${legend([{ label: "Clicks", color: "var(--c3)" }, { label: "Impressions", color: "var(--c1)" }])}${rangeSel("range")}</div></div>
    <div class="card-b"><div id="ch-clicks"></div><div id="ch-imp" style="margin-top:6px"></div></div></div>
  <div class="grid g2 mt">
    <div class="card"><div class="card-h"><h2>Top opportunities</h2><a href="#opportunities" class="mini">All →</a></div><div class="card-b flush" id="ov-opps"></div></div>
    <div class="card"><div class="card-h"><div><h2>Visibility by business segment</h2><div class="hint">Monthly impressions · ${esc("Strategic B2B vs. Price vs. B2C")}</div></div><a href="#performance" class="mini">Details →</a></div>
      <div class="card-b">${legend(segSeries())}<div id="ch-seg"></div><div class="mini" style="margin-top:6px">${esc(d.client.segments_note)}</div></div></div>
  </div>
  <div class="card mt"><div class="card-h"><div><h2>Search → Business: wichtigste Themen</h2><div class="hint">Nachfrage, Sichtbarkeit, Paid-Historie, Funnel Intent und Leads je Thema (Priorität ≥ 8)</div></div><a href="#funnel" class="mini">Funnel →</a></div><div class="card-b flush"><div class="tbl-wrap"><table><thead><tr><th>Thema</th><th class="num">Nachfrage</th><th class="num">Ø Pos.</th><th class="num">Paid (hist.)</th><th class="num">Funnel Intent</th><th class="num">Leads</th><th>Signal</th></tr></thead><tbody>
    ${d.funnel.clusters.filter(x => (x.priority || 0) >= 8).sort((a, b) => b.priority - a.priority || b.demand.semrush_volume - a.demand.semrush_volume).slice(0, 6).map(x => `<tr class="click" data-go="funnel"><td class="q">${esc(CL_LABEL(x.cluster))}<div class="s">Prio ${x.priority}/10${x.opportunities.length ? " · " + x.opportunities.map(esc).join(", ") : ""}</div></td><td class="num">${x.demand.keywords ? fmtN(x.demand.semrush_volume) : "–"}</td><td class="num">${fmtD(x.organic.position)}</td><td class="num">${x.paid.keyword_cost ? fmtEur(x.paid.keyword_cost) : "–"}</td><td class="num">${intentCell(x.engagement)}</td><td class="num">${leadCell(x.engagement)}</td><td class="s">${esc((x.signals.find(s => s.kind === "weak") || x.signals[0] || {}).text || "")}</td></tr>`).join("")}
  </tbody></table></div></div></div>
  ${freshPanel()}`;
  drawPerf(S.range, "range", "ch-clicks", "ch-imp");
  mount("ov-opps", table({ rows: d.opportunities.filter(o => o.type !== "IGNORE").slice(0, 6), pageSize: 6, onRow: o => go("opp-" + o.id),
    columns: [{ key: "name", label: "Opportunity", render: o => `<div class="q">${esc(o.name)}</div><div class="s">${esc(o.status)}</div>` },
      { key: "type", label: "Type", render: o => typeChip(o.type) }, { key: "priority", label: "Priority", render: o => prioChip(o.priority), sort: false },
      { key: "business_fit", label: "Fit", num: true, render: o => o.business_fit + "/10" }] }));
  $(".tbl-tools", $("#ov-opps")).remove(); $(".tbl-foot", $("#ov-opps")).remove();
  drawSeg("ch-seg");
};
const kpi = (label, val, dl, t = "") => `<div class="card kpi"><div class="k-label"><span ${t ? `data-tip="${esc(t)}"` : ""}>${esc(label)}${t ? " ⓘ" : ""}</span></div><div class="k-val">${val}</div><div class="k-delta">${dl}</div></div>`;
function attItem(a) {
  const href = a.kind === "opportunity" ? "#opp-" + a.ref : a.kind === "task" ? "#activity" : a.kind === "approval" ? "#approvals" : a.kind === "change" ? "#changes" : "#market";
  return `<div class="att-item"><div class="att-bar ${a.level}"></div><div><div class="att-title"><a href="${href}">${esc(a.title)}</a> <span class="mini">${esc(a.ref)}</span></div><div class="att-detail">${esc(a.detail || "")}</div></div><div>${statusChip(a.status)}</div></div>`;
}
const STATE = { completed: ["Completed", "green"], planned: ["Planned", "blue"], blocked: ["Blocked", "red"], monitoring: ["Monitoring", "amber"], waiting_for_approval: ["Waiting for approval", "amber"], needs_review: ["Needs review", "amber"] };
function actItem(t) {
  const [l, c] = STATE[t.state] || [t.state, ""];
  const extra = t.state === "blocked" ? `Reason: ${t.blocked_reason}` : t.next_check ? `Next check: ${fmtDate(t.next_check)}` : t.detail;
  return `<div class="act-item"><div>${chip(l, c, true)}</div><div><div class="t">${esc(t.title)}</div><div class="d">${esc(extra || "")}${t.state === "completed" ? ` · ${fmtDate(t.date)}` : ""}</div></div></div>`;
}
const rangeSel = which => `<div class="seg" data-range="${which}">${Object.keys(RANGES).map(r => `<button class="${S[which] === r ? "on" : ""}" data-r="${r}">${r}</button>`).join("")}</div>`;
document.addEventListener("click", e => {
  const b = e.target.closest(".seg[data-range] button"); if (!b) return;
  const which = b.parentElement.dataset.range; S[which] = b.dataset.r; route(true);
});
function drawPerf(range, _which, idClicks, idImp, idPos, hc = 120) {
  const w = windowRows(range), mode = modeFor(range), pts = bucket(w.cur, mode);
  chartInto(idClicks, { points: pts, series: [{ key: "clicks", label: "Clicks", color: "var(--c3)", type: "bar" }], height: hc, xMode: mode });
  chartInto(idImp, { points: pts, series: [{ key: "impressions", label: "Impressions", color: "var(--c1)", type: "area" }], height: 160, xMode: mode });
  if (idPos) chartInto(idPos, { points: pts, series: [{ key: "position", label: "Avg. position", color: "var(--violet)", type: "line", fmt: v => fmtD(v) }], height: 160, invert: true, xMode: mode, yFmt: v => fmtD(v, 0) });
}
const SEGC = { "Strategic B2B": "var(--seg-b2b)", "Price": "var(--seg-price)", "B2C": "var(--seg-b2c)", "Unknown": "var(--seg-unknown)", "Brand": "var(--seg-brand)" };
const segSeries = () => ["Strategic B2B", "Price", "B2C", "Unknown"].map(s => ({ key: s, label: s, color: SEGC[s], type: "line" }));
function drawSeg(id) {
  const sm = S.d.gsc.segments_monthly; const months = [...new Set(Object.values(sm).flatMap(v => v.map(x => x.month)))].sort();
  const pts = months.map(m => { const p = { x: m + "-01" }; for (const s of Object.keys(sm)) p[s] = sm[s].find(x => x.month === m)?.impressions ?? 0; return p; });
  chartInto(id, { points: pts, series: segSeries(), height: 190, xMode: "month" });
}

pages.performance = () => {
  const d = S.d, r = S.perfRange, w = windowRows(r), cur = sumRows(w.cur), prev = sumRows(w.prev);
  const st = d.gsc.segment_totals;
  view().innerHTML = `
  <div class="page-head"><div><h1>Performance</h1><div class="sub">Google Search Console · ${fmtDate(w.from)} – ${fmtDate(w.to)}${w.prev ? " · compared with the previous period of equal length" : " · no previous period available"}</div></div>${rangeSel("perfRange")}</div>
  <div class="kpis k4">
    ${kpi("Clicks", fmtN(cur.clicks), delta(cur.clicks, prev?.clicks))}
    ${kpi("Impressions", fmtN(cur.impressions), delta(cur.impressions, prev?.impressions))}
    ${kpi("CTR", fmtPct(cur.ctr), prev ? delta(cur.ctr * 100, prev.ctr * 100, { abs: true, unit: "pp" }) : delta(null, null))}
    ${kpi("Avg. Position", fmtD(cur.position), delta(cur.position, prev?.position, { invert: true, abs: true, unit: "" }), "Impressions-gewichtet; niedriger = besser")}
  </div>
  <div class="grid g3">
    <div class="card"><div class="card-h"><h2>Clicks</h2></div><div class="card-b" id="p-clicks"></div></div>
    <div class="card"><div class="card-h"><h2>Impressions</h2></div><div class="card-b" id="p-imp"></div></div>
    <div class="card"><div class="card-h"><h2>Average position</h2><span class="hint">inverted axis</span></div><div class="card-b" id="p-pos"></div></div>
  </div>
  <div class="grid g-main mt">
    <div class="card"><div class="card-h"><div><h2>Business segments</h2><div class="hint">16 months, query level. Δ = last 90 days vs. 90 days before.</div></div></div>
      <div class="card-b flush"><div class="tbl-wrap"><table><thead><tr><th>Segment</th><th class="num">Queries</th><th class="num">Clicks</th><th class="num">Impressions</th><th class="num">Avg. pos.</th><th class="num">Impr. 90d</th><th class="num">Δ vs prev. 90d</th></tr></thead><tbody>
      ${Object.entries(st).map(([k, v]) => k === "Brand" && !v.queries ? `<tr><td>${chip(k, "", false).replace("chip", "chip outline")}</td><td colspan="6" class="s">Not measurable – brand queries are anonymized by Google (see note below)</td></tr>` : `<tr><td>${chip(k, "", false).replace("chip", "chip outline")}</td><td class="num">${fmtN(v.queries)}</td><td class="num">${fmtN(v.clicks)}</td><td class="num">${fmtN(v.impressions)}</td><td class="num">${fmtD(v.position)}</td><td class="num">${fmtN(v.imp_90d)}</td><td class="num">${delta(v.imp_90d, v.imp_prev90d)}</td></tr>`).join("")}
      </tbody></table></div><div class="card-b mini" style="padding-top:10px">${esc(d.client.segments_note)} Brand-Suchen sind von Google anonymisiert (nur ${fmtN(d.gsc.queries.reduce((a, q) => a + q.clicks, 0))} von ${fmtN(d.gsc.daily.reduce((a, q) => a + q.clicks, 0))} Klicks sind einer Query zugeordnet) – Brand ist daher <b>nicht messbar</b>, nicht „0“.</div></div></div>
    <div class="card"><div class="card-h"><h2>Devices & countries</h2><span class="hint">16 months</span></div><div class="card-b flush">
      <table><thead><tr><th>Device</th><th class="num">Clicks</th><th class="num">Impressions</th><th class="num">Share</th></tr></thead><tbody>
      ${(() => { const t = d.gsc.devices.reduce((a, x) => a + x.impressions, 0); return d.gsc.devices.map(x => `<tr><td>${esc(x.device)}</td><td class="num">${fmtN(x.clicks)}</td><td class="num">${fmtN(x.impressions)}</td><td class="num">${fmtD(x.impressions / t * 100)} %</td></tr>`).join(""); })()}
      </tbody></table>
      <table class="mt"><thead><tr><th>Country</th><th class="num">Clicks</th><th class="num">Impressions</th></tr></thead><tbody>
      ${d.gsc.countries.slice(0, 5).map(x => `<tr><td>${esc(x.country.toUpperCase())}</td><td class="num">${fmtN(x.clicks)}</td><td class="num">${fmtN(x.impressions)}</td></tr>`).join("")}
      </tbody></table></div></div>
  </div>
  <div class="card mt"><div class="tabs" id="ptabs">${["Queries", "Pages", "Query × Page", "Winners", "Losers", "Quick Wins", "Cannibalization"].map(t => `<button data-t="${t}" class="${(S.ui.ptab || "Queries") === t ? "on" : ""}">${t}</button>`).join("")}</div><div id="ptab-body"></div></div>`;
  drawPerf(r, "perfRange", "p-clicks", "p-imp", "p-pos", 160);
  $("#ptabs").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; S.ui.ptab = b.dataset.t; $("#ptabs").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); renderPTab(); });
  renderPTab();
};
function renderPTab() {
  const g = S.d.gsc, t = S.ui.ptab || "Queries"; let node;
  if (t === "Queries") node = table({ rows: g.queries, columns: qCols(), search: ["query", "page"], filters: [segFilter(), { key: "pos", label: "Position", options: ["1–3", "4–10", "11–20", "21–50", ">50"], match: (r, v) => ({ "1–3": r.position <= 3.5, "4–10": r.position > 3.5 && r.position <= 10.5, "11–20": r.position > 10.5 && r.position <= 20.5, "21–50": r.position > 20.5 && r.position <= 50.5, ">50": r.position > 50.5 }[v]) }] });
  if (t === "Pages") node = table({ rows: g.pages.filter(p => !p.page.includes("?")), search: ["page", "title"], columns: [
    { key: "page", label: "Page", render: p => `<div class="q">${esc(p.page)}</div><div class="s">${esc(p.title || "Not in inventory")}</div>` },
    { key: "clicks", label: "Clicks", num: true, render: p => fmtN(p.clicks) }, { key: "impressions", label: "Impressions", num: true, render: p => fmtN(p.impressions) },
    { key: "ctr", label: "CTR", num: true, render: p => fmtPct(p.ctr) }, { key: "position", label: "Position", num: true, render: p => fmtD(p.position) },
    { key: "imp_change_pct", label: "Δ Impr. (90d)", num: true, render: p => delta(p.imp_90d, p.imp_prev90d) },
    { key: "inlinks", label: "Content inlinks", num: true, render: p => p.inlinks ?? "–" }, { key: "modified", label: "Last modified", render: p => fmtDate(p.modified) }] });
  if (t === "Query × Page") node = table({ rows: g.query_page, search: ["query", "page"], filters: [segFilter()], columns: [
    { key: "query", label: "Query", render: r => `<div class="q">${esc(r.query)}</div><div class="s">${esc(r.segment)}</div>` }, { key: "page", label: "Page", render: r => `<span class="s">${esc(r.page)}</span>` },
    { key: "clicks", label: "Clicks", num: true, render: r => fmtN(r.clicks) }, { key: "impressions", label: "Impressions", num: true, render: r => fmtN(r.impressions) },
    { key: "ctr", label: "CTR", num: true, render: r => fmtPct(r.ctr) }, { key: "position", label: "Position", num: true, render: r => fmtD(r.position) }] });
  if (t === "Winners" || t === "Losers") node = table({ rows: t === "Winners" ? g.winners : g.losers, columns: qCols(), search: ["query"], filters: [segFilter()], sort: { key: "imp_change", dir: t === "Winners" ? -1 : 1 } });
  if (t === "Quick Wins") node = table({ rows: g.quickwins, search: ["query"], filters: [segFilter()], sort: null, toolsExtra: `<span class="mini" data-tip="Position 4–20, ≥ 50 Impressionen; sortiert nach Business-Priorität laut Profil, dann Impressionen">Pos. 4–20 · ≥50 impr. · sorted by business priority ⓘ</span>`,
    columns: [{ key: "business_priority", label: "Biz prio", num: true, render: r => r.business_priority ? r.business_priority + "/10" : "–" }, ...qCols()] });
  if (t === "Cannibalization") node = table({ rows: g.cannibalization, search: ["query"], filters: [segFilter()], columns: [
    { key: "query", label: "Query", render: r => `<div class="q">${esc(r.query)}</div><div class="s">${esc(r.segment)}</div>` },
    { key: "total_impressions", label: "Impressions", num: true, render: r => fmtN(r.total_impressions) },
    { key: "pages", label: "Competing pages", sort: false, render: r => r.pages.map(p => `<div class="s">${esc(p.page)} · ${fmtN(p.impressions)} impr. · pos ${fmtD(p.position)}</div>`).join("") }] });
  mount("ptab-body", node);
}

pages.opportunities = () => {
  const d = S.d, types = ["All", "CREATE", "OPTIMIZE", "MERGE", "MONITOR", "IGNORE"], cur = S.ui.otype || "All";
  const rows = d.opportunities.filter(o => cur === "All" || o.type === cur);
  const cnt = t => t === "All" ? d.opportunities.length : d.opportunities.filter(o => o.type === t).length;
  view().innerHTML = `<div class="page-head"><div><h1>Opportunities</h1><div class="sub">Source of truth: state/opportunities.json · metrics joined from GSC, Semrush cache and website inventory at build time</div></div>
    <div class="seg" id="otype">${types.map(t => `<button data-t="${t}" class="${cur === t ? "on" : ""}">${t} <span class="mini">${cnt(t)}</span></button>`).join("")}</div></div>
    <div class="card" id="opp-table"></div>`;
  $("#otype").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { S.ui.otype = b.dataset.t; route(true); } });
  const sv = o => { const k = o.semrush.keywords.find(k => k.status === "ok"); return k ? k.volume : null; };
  mount("opp-table", table({ rows, pageSize: 20, onRow: o => go("opp-" + o.id), search: ["name", "primary_keyword", "id"],
    filters: [{ key: "priority", label: "Priority", options: ["critical", "high", "medium", "low"] }, { key: "status", label: "Status", options: [...new Set(d.opportunities.map(o => o.status))] },
      { key: "confidence", label: "Confidence", options: ["high", "medium", "low"] }, { key: "fit", label: "Business fit", options: ["8–10", "5–7", "0–4"], match: (o, v) => ({ "8–10": o.business_fit >= 8, "5–7": o.business_fit >= 5 && o.business_fit < 8, "0–4": o.business_fit < 5 }[v]) }],
    columns: [
      { key: "name", label: "Opportunity", render: o => `<div class="q">${esc(o.name)}</div><div class="s">${esc(o.id)} · ${esc(o.recommendation.length > 90 ? o.recommendation.slice(0, 90).replace(/\s+\S*$/, "") + " …" : o.recommendation)}</div>` },
      { key: "type", label: "Type", render: o => typeChip(o.type) },
      { key: "priority", label: "Priority", value: o => ({ critical: 4, high: 3, medium: 2, low: 1 }[o.priority]), render: o => prioChip(o.priority) },
      { key: "status", label: "Status", render: o => statusChip(o.status) },
      { key: "business_fit", label: "Fit", num: true, render: o => o.business_fit + "/10" },
      { key: "confidence", label: "Conf.", value: o => ({ high: 3, medium: 2, low: 1 }[o.confidence]), render: o => esc({ high: "High", medium: "Medium", low: "Low" }[o.confidence]) },
      { key: "primary_keyword", label: "Primary keyword / cluster", render: o => `<div>${esc(o.primary_keyword)}</div><div class="s">${esc(o.gsc_cluster)}</div>` },
      { key: "gsc_imp", label: "GSC cluster impr.", num: true, value: o => o.gsc.cluster_total?.impressions ?? null, tip: "Impressionen aller Queries des Clusters, 16 Monate", render: o => fmtN(o.gsc.cluster_total?.impressions) },
      { key: "sem_vol", label: "Semrush vol.", num: true, value: sv, tip: "Suchvolumen des ersten gemessenen Keywords (DE)", render: o => sv(o) === null ? `<span class="s">Not measured</span>` : fmtN(sv(o)) },
      { key: "cur_pos", label: "GSC pos.", num: true, value: o => o.gsc.queries.find(q => !q.missing)?.position ?? null, tip: "Position der Primary-Query (16 Monate)", render: o => { const q = o.gsc.queries.find(q => q.query === o.primary_keyword) || o.gsc.queries.find(q => !q.missing); return q && !q.missing ? fmtD(q.position) : "–"; } },
      { key: "leads", label: "Leads (Cluster)", num: true, tip: "Leads/Contacts auf den Haupt-Landingpages des Clusters, 16 Monate (GA4); darunter Funnel-Intent-Sitzungen", value: o => { const f = S.d.funnel?.clusters.find(c => c.cluster === o.gsc_cluster); return f ? leadsOf(f.engagement) : null; }, render: o => { const f = S.d.funnel?.clusters.find(c => c.cluster === o.gsc_cluster); return f ? `${fmtN(leadsOf(f.engagement))}<div class="s">Intent ${fmtN(f.engagement.micro_sessions)}</div>` : "–"; } },
      { key: "existing_page", label: "Existing page", render: o => o.existing_page ? `<span class="s">${esc(o.existing_page)}</span>` : `<span class="chip blue">New page</span>` },
    ] }));
};

pages.opportunity = id => {
  const o = S.d.opportunities.find(x => x.id === id);
  if (!o) { view().innerHTML = `<a class="back" href="#opportunities">← Opportunities</a><div class="card empty">Opportunity ${esc(id)} not found.</div>`; return; }
  const p = o.page_info, inv = o.investigation;
  view().innerHTML = `<a class="back" href="#opportunities">← Opportunities</a>
  <div class="page-head"><div><div class="detail-head"><h1>${esc(o.name)}</h1>${typeChip(o.type)}${prioChip(o.priority)}${confChip(o.confidence)}${statusChip(o.status)}${o.freeze ? chip("Change freeze", "amber", true) : ""}</div>
    <div class="sub">${esc(o.id)} · Business fit ${o.business_fit}/10 · Primary keyword „${esc(o.primary_keyword)}“</div></div></div>
  ${resStatus(o) ? `${researchBanner(o)}<div class="card mt" id="g1-brief"><div class="card-h"><div><h2>Gate 1 – Entscheidungsvorlage</h2><div class="hint">Freigabe = SEO-Maßnahme UND fachlicher Scope der Seite. Änderungen am Scope bitte im Gate-1-Kommentar.</div></div>${gate1Card(o, true)}</div><div class="card-b">${gate1Brief(o)}</div></div>` : `<div class="card mt"><div class="card-h"><h2>Cannibalization Risk</h2></div><div class="card-b">${cannibalBlock(o, true)}</div></div><div class="mt">${diagnosisCard(o)}</div>`}
  ${resStatus(o) ? `<div class="grid mt"><div class="card" id="rs-cannibal"><div class="card-h"><h2>Cannibalization &amp; Architecture</h2></div><div class="card-b">${cannibalBlock(o, true)}</div></div>${diagnosisCard(o)}${evidenceCard(o)}${researchView(o)}${gate1Card(o)}</div><h2 class="sec-h">Evidenz &amp; Rohdaten</h2>` : ""}
  <div class="grid g-main">
    <div class="grid">
      <div class="card"><div class="card-h"><h2>Why this matters</h2></div><div class="card-b"><p style="margin:0 0 10px">${esc(o.why)}</p><div class="callout"><b>Recommendation:</b> ${esc(o.recommendation)}</div>
        ${inv ? `<div class="callout amber mt"><div class="row"><b>${esc(inv.title)}</b><span class="tag-hyp">${esc(inv.label)}</span></div><p style="margin:6px 0">${esc(inv.result)}</p><div class="mini"><b>Implication:</b> ${esc(inv.implication)}</div></div>` : ""}</div></div>
      <div class="card"><div class="card-h"><div><h2>Google Search Console</h2><div class="hint">16 months · Δ = last 90 days vs. 90 days before</div></div></div><div class="card-b flush"><div class="tbl-wrap">
        <table><thead><tr><th>Query</th><th class="num">Clicks</th><th class="num">Impressions</th><th class="num">Position</th><th class="num">Pos. 90d</th><th class="num">Impr. 90d vs prev.</th><th>Page</th></tr></thead><tbody>
        ${o.gsc.queries.map(q => q.missing ? `<tr><td>${esc(q.query)}</td><td colspan="6" class="s">No GSC data for this query</td></tr>` : `<tr><td class="q">${esc(q.query)}</td><td class="num">${fmtN(q.clicks)}</td><td class="num">${fmtN(q.impressions)}</td><td class="num">${fmtD(q.position)}</td><td class="num">${fmtD(q.pos_90d)}</td><td class="num">${fmtN(q.imp_90d)} ${delta(q.imp_90d, q.imp_prev90d)}</td><td class="s path">${esc(q.page || "–")}</td></tr>`).join("")}
        </tbody></table></div>
        <div class="card-b" style="padding-top:12px"><div class="row"><b>Cluster „${esc(o.gsc.cluster)}“</b><span class="mini">${fmtN(o.gsc.cluster_queries)} queries · ${fmtN(o.gsc.cluster_total?.clicks)} clicks · ${fmtN(o.gsc.cluster_total?.impressions)} impressions · avg. pos. ${fmtD(o.gsc.cluster_total?.position)}</span></div><div id="opp-cl"></div></div></div></div>
      <div class="card"><div class="card-h"><div><h2>Semrush</h2><div class="hint">Keyword cache (DE) · SERP: ${esc(o.semrush.serp_note)}</div></div></div><div class="card-b flush">
        <table><thead><tr><th>Keyword</th><th class="num">Volume</th><th class="num">KD</th><th class="num">CPC €</th><th>Measured</th></tr></thead><tbody>
        ${o.semrush.keywords.map(k => `<tr><td>${esc(k.keyword)}</td>${k.status === "ok" ? `<td class="num">${fmtN(k.volume)}</td><td class="num">${fmtD(k.kd, 0)}</td><td class="num">${fmtD(k.cpc, 2)}</td><td>${fmtDate(k.fetched)}</td>` : `<td colspan="3" class="s">${k.status === "no_data" ? "No data in Semrush (≠ no demand)" : "Not measured yet"}</td><td>${k.fetched ? fmtDate(k.fetched) : "–"}</td>`}</tr>`).join("") || `<tr><td colspan="5" class="empty">No Semrush keywords assigned</td></tr>`}
        </tbody></table>
        ${o.semrush.rankings.length ? `<div class="card-b" style="padding-top:12px"><b>Semrush rankings of this page</b>${o.semrush.rankings.map(r => `<div class="s">${esc(r.keyword)} · pos ${r.position} · vol ${fmtN(r.volume)}</div>`).join("")}</div>` : ""}</div></div>
    </div>
    <div class="grid" style="align-content:start">
      <div class="card"><div class="card-h"><h2>Existing website</h2></div><div class="card-b">
        ${p ? `<div class="kv"><div class="k">URL</div><div><a href="${esc(S.d.client.website.replace(/\/$/, "") + p.page)}" target="_blank" rel="noopener">${esc(p.page)}</a></div>
          <div class="k">Title</div><div>${esc(p.title || "–")}</div><div class="k">H1</div><div>${esc(p.h1 || "–")}</div>
          <div class="k">Last modified</div><div>${fmtDate(p.modified)}</div><div class="k">Words (main)</div><div>${fmtN(p.words)}</div>
          <div class="k">Content inlinks / outlinks</div><div>${p.inlinks ?? "–"} / ${p.outlinks ?? "–"}</div><div class="k">In sitemap</div><div>${p.in_sitemap === undefined ? "Unknown" : p.in_sitemap ? "Yes (crawl 22.11.)" : "No (crawl 22.11.)"}</div>
          <div class="k">GSC 16 months</div><div>${fmtN(p.clicks)} clicks · ${fmtN(p.impressions)} impr. · pos ${fmtD(p.position)}</div>
          <div class="k">Impr. 90d</div><div>${fmtN(p.imp_90d)} ${delta(p.imp_90d, p.imp_prev90d)}</div></div>`
          : `<div class="callout">No existing page – this is a <b>new page</b> candidate.</div>`}
        ${o.competing_pages_info?.length ? `<div class="mt"><b>Pages currently ranking for the topic</b>${o.competing_pages_info.map(c => `<div class="s">${esc(c.page)} · ${fmtN(c.impressions)} impr. · pos ${fmtD(c.position)}</div>`).join("")}</div>` : ""}</div></div>
      ${oppBusinessCard(o)}
      <div class="card"><div class="card-h"><h2>Agent reasoning</h2></div><div class="card-b"><ul class="list">${o.reasoning.map(r => `<li>${esc(r)}</li>`).join("")}</ul></div></div>
      <div class="card"><div class="card-h"><h2>Risks</h2></div><div class="card-b">${o.risks.length ? `<ul class="list">${o.risks.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : `<span class="mini">None documented.</span>`}</div></div>
      <div class="card"><div class="card-h"><h2>Technical findings</h2></div><div class="card-b">${o.findings_detail.length ? o.findings_detail.map(f => `<div style="margin-bottom:8px"><div class="row">${sevChip(f.severity)}<b>${esc(f.id)}</b> ${esc(f.title)} ${statusChip(f.status)}</div><div class="s">${esc(f.description)}</div></div>`).join("") : `<span class="mini">None linked.</span>`}
        ${o.related_changes.length ? `<div class="mt">Related changes: ${o.related_changes.map(c => `<a href="#changes">${esc(c)}</a>`).join(", ")}</div>` : ""}</div></div>
      <div class="card"><div class="card-h"><h2>Next step</h2></div><div class="card-b"><div class="callout">${esc(o.next_step)}</div>${o.gate1_candidate ? `<div class="mini mt">Gate-1 candidate – will be submitted to the Approval Center when the evidence is complete. Not submitted yet.</div>` : ""}</div></div>
    </div>
  </div>`;
  view().querySelectorAll("[data-rs]").forEach(a => a.addEventListener("click", e => { e.preventDefault(); $("#rs-" + a.dataset.rs)?.scrollIntoView({ behavior: "smooth", block: "start" }); }));
  view().querySelectorAll("[data-gate1]").forEach(b => b.addEventListener("click", e => { e.preventDefault(); WF_PENDING_OPEN = b.dataset.gate1; go("approvals"); }));
  const cm = o.gsc.cluster_monthly_impressions.map(x => ({ x: x.month + "-01", impressions: x.impressions }));
  chartInto("opp-cl", { points: cm, series: [{ key: "impressions", label: "Cluster impressions / month", color: "var(--c1)", type: "bar" }], height: 120, xMode: "month" });
};

/* ------------------------------------------------------------ Search → Business (Funnel) */
const CL_LABEL = c => ({ baudokumentation: "Baudokumentation", dachinspektion: "Dachinspektion", fassadeninspektion: "Fassadeninspektion", inspektion_allgemein: "Inspektion allgemein", dachvermessung: "Dachvermessung", fassadenvermessung: "Fassadenvermessung", vermessung_allgemein: "Vermessung allgemein", bestandsaufnahme: "Bestandsaufnahme", immobilien: "Immobilien", firma_imagefilm: "Firma / Imagefilm", video: "Video", haus_privat: "Haus privat", hochzeit_event: "Hochzeit / Event", preis: "Preis-Suchen", generisch_drohne: "Generisch (Drohne/Luftbild)" }[c] || c);
const SIG = { demand: "blue", paid: "amber", value: "", weak: "red", strong: "green", page: "green", lead: "green", intent: "blue", nolead: "amber", prio: "blue" };
const SIG_LABEL = { demand: "Nachfrage", paid: "Paid-Historie", value: "Klickwert", weak: "Organisch schwach", strong: "Organisch stark", page: "Seite vorhanden", lead: "Leads", intent: "Funnel Intent", nolead: "Kein Lead/Intent", prio: "Priorität" };
const leadsOf = x => (x.lead_form || 0) + (x.lead_contact || 0);
const leadCell = x => `<b>${fmtN(leadsOf(x))}</b><div class="s" style="white-space:nowrap" data-tip="Form Submissions (F) · Direct Contact Actions Telefon/E-Mail/Chat (K)">${fmtN(x.lead_form || 0)} F · ${fmtN(x.lead_contact || 0)} K</div>`;
const intentCell = x => x.micro_sessions ? `${fmtN(x.micro_sessions)}<div class="s" style="white-space:nowrap">${fmtN(x.micro)} Ev.</div>` : `<span class="s">–</span>`;
const fmtEur = v => (v === null || v === undefined) ? "–" : v.toLocaleString("de-DE", { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + " €";
const fmtSec = v => (v === null || v === undefined) ? "–" : `${Math.floor(v / 60)}:${String(Math.round(v % 60)).padStart(2, "0")} min`;
pages.funnel = () => {
  const f = S.d.funnel, w = f.window;
  view().innerHTML = `<div class="page-head"><div><h1>Search → Business</h1><div class="sub">Je Thema: Search Demand → Visibility → Clicks → Sessions → Engaged Sessions → Funnel Intent → Leads / Contacts → Business-Priorität. Zeitraum GSC/GA4: ${fmtDate(w[0])} – ${fmtDate(w[1])}.</div></div></div>
  <div class="notice">Lesehilfe: GA4 erfasst nur etwa ${fmtPct(S.d.ga4.quality?.capture_ratio, 0)} der organischen Klicks (Consent). Leads und Funnel Intent sind kleine Zahlen – sie zeigen Richtung, keine Statistik. Funnel Intent (Heyflow-Interaktion) wird nie zu Leads addiert. Paid-Werte stammen aus der GA4-Verknüpfung des gekündigten Ads-Kontos (2023–24, Keyword-Ebene).</div>
  <div class="card mt" id="fn-table"></div>
  <div class="card mt"><div class="card-h"><div><h2>Landingpages: GSC × GA4 × Ads</h2><div class="hint">Zusammengeführt über den URL-Pfad. Sitzungen, Funnel Intent und Leads aus GA4 im selben Zeitraum wie GSC; Paid-Sitzungen = Ads-Historie gesamt.</div></div></div><div id="fn-pages"></div></div>`;
  mount("fn-table", table({ rows: f.clusters, pageSize: 20, onRow: x => renderFunnelDetail(x), sort: { key: "priority", dir: -1 },
    columns: [
      { key: "cluster", label: "Thema", render: x => `<div class="q">${esc(CL_LABEL(x.cluster))}</div><div class="s">${x.opportunities.map(esc).join(", ") || "keine Opportunity"}</div>` },
      { key: "priority", label: "Prio", num: true, value: x => x.priority ?? -1, render: x => x.priority === null || x.priority === undefined ? `<span class="s">–</span>` : x.priority + "/10" },
      { key: "demand", label: "Nachfrage", num: true, tip: "Summe Suchvolumen/Monat der gemessenen Semrush-Keywords dieses Themas (DE)", value: x => x.demand.semrush_volume, render: x => x.demand.keywords ? `${fmtN(x.demand.semrush_volume)}<div class="s">${x.demand.keywords} Keywords</div>` : `<span class="s">Not measured</span>` },
      { key: "imp", label: "Visibility", num: true, tip: "GSC-Impressionen (16 Monate) und Ø Position", value: x => x.organic.impressions, render: x => `${fmtN(x.organic.impressions)}<div class="s">Pos. ${fmtD(x.organic.position)}</div>` },
      { key: "clk", label: "Clicks", num: true, value: x => x.organic.clicks, render: x => fmtN(x.organic.clicks) },
      { key: "ses", label: "Sessions", num: true, tip: "GA4-Sitzungen auf den Haupt-Landingpages (darunter: engagiert)", value: x => x.engagement.sessions, render: x => `${fmtN(x.engagement.sessions)}<div class="s">${fmtN(x.engagement.engaged)} eng.</div>` },
      { key: "intent", label: "Funnel Intent", num: true, tip: "Sitzungen mit Heyflow-Interaktion (Micro Conversion) – kein Lead", value: x => x.engagement.micro_sessions, render: x => intentCell(x.engagement) },
      { key: "leads", label: "Leads", num: true, tip: "Lead / Contact: Form Submissions (F) + Direct Contact Actions (K)", value: x => leadsOf(x.engagement), render: x => leadCell(x.engagement) },
      { key: "paid", label: "Paid (hist.)", num: true, tip: "Google-Ads-Kosten auf Keyword-Ebene 2023–24 (über GA4)", value: x => x.paid.keyword_cost, render: x => x.paid.keyword_cost ? `${fmtEur(x.paid.keyword_cost)}<div class="s">${x.paid.keyword_clicks} Kl.</div>` : x.paid.campaigns.length ? `<span class="s">nur Kampagne</span>` : `<span class="s">–</span>` },
      { key: "sig", label: "Signale", sort: false, render: x => x.signals.filter(s => ["weak", "paid", "lead", "intent", "nolead"].includes(s.kind)).map(s => chip(SIG_LABEL[s.kind], SIG[s.kind])).join(" ") },
    ] }));
  $("#fn-table").insertAdjacentHTML("beforeend", `<div id="fn-detail"></div>`);
  mount("fn-pages", table({ rows: f.pages, pageSize: 15, search: ["page", "title"],
    columns: [
      { key: "page", label: "Landingpage", render: p => `<div class="q path">${esc(p.page)}</div><div class="s">${esc(p.title || (p.in_inventory ? "" : "Nicht im Website-Inventar"))}</div>` },
      { key: "gsc_impressions", label: "GSC Impr.", num: true, render: p => fmtN(p.gsc_impressions) },
      { key: "gsc_clicks", label: "GSC Klicks", num: true, render: p => fmtN(p.gsc_clicks) },
      { key: "gsc_position", label: "Pos.", num: true, render: p => fmtD(p.gsc_position) },
      { key: "ga4_organic", label: "GA4 organisch", num: true, render: p => fmtN(p.ga4_organic) },
      { key: "ga4_sessions", label: "GA4 gesamt", num: true, render: p => fmtN(p.ga4_sessions) },
      { key: "eng_rate", label: "Engagement", num: true, render: p => p.eng_rate === null || p.eng_rate === undefined ? "–" : fmtPct(p.eng_rate, 0) },
      { key: "micro_sessions", label: "Funnel Intent", num: true, render: p => intentCell(p) },
      { key: "leads", label: "Leads", num: true, value: p => leadsOf(p), render: p => leadCell(p) },
      { key: "paid_sessions_hist", label: "Paid-Sitz. (hist.)", num: true, render: p => fmtN(p.paid_sessions_hist) },
    ] }));
};
function renderFunnelDetail(x) {
  const el = $("#fn-detail"); if (!el) return;
  if (S.ui.fnOpen === x.cluster) { S.ui.fnOpen = null; el.innerHTML = ""; return; } S.ui.fnOpen = x.cluster;
  const stage = (n, t, body) => `<div class="fstage"><div class="fnum">${n}</div><div><div class="ft">${t}</div><div class="s">${body}</div></div></div>`;
  el.innerHTML = `<div class="card-b" style="border-top:1px solid var(--border);padding-top:14px"><div class="row"><h2>${esc(CL_LABEL(x.cluster))}</h2>${x.priority ? chip("Business-Priorität " + x.priority + "/10", x.priority >= 8 ? "blue" : "") : ""}${x.opportunities.map(o => `<a href="#opp-${esc(o)}">${chip(o, "outline")}</a>`).join("")}</div>
    <div class="grid g2 mt"><div class="funnel">
      ${stage("1", "Search Demand", (x.demand.keywords ? `Semrush: ${fmtN(x.demand.semrush_volume)} Suchen/Monat · ${x.demand.top.map(k => `${esc(k.keyword)} (${fmtN(k.volume)}, KD ${fmtD(k.kd, 0)})`).join(" · ")}` : "Semrush: nicht gemessen") + (x.demand.semrush_volume === 0 || !x.demand.keywords ? "<br>Kein/geringes Volumen ≠ IGNORE – GSC, Business Fit und Intent zählen mit" : ""))}
      ${stage("2", "Organische Sichtbarkeit", `${fmtN(x.organic.impressions)} Impressionen · Ø Position ${fmtD(x.organic.position)} · ${x.organic.queries} Queries`)}
      ${stage("2b", "Paid-Sichtbarkeit (historisch)", x.paid.keyword_cost ? `${fmtEur(x.paid.keyword_cost)} für ${x.paid.keyword_clicks} Klicks · ${x.paid.keywords.map(esc).join(", ")}` : x.paid.campaigns.length ? "Kampagnen: " + x.paid.campaigns.map(esc).join(", ") + " (Kampagnenwerte unplausibel, s. Google Ads)" : "Keine Paid-Daten")}
      ${stage("3", "Clicks", `${fmtN(x.organic.clicks)} organische Klicks (GSC) · CTR ${fmtPct(x.organic.ctr)}`)}
      ${stage("4", "Sessions", `${fmtN(x.engagement.sessions)} GA4-Sitzungen (${fmtN(x.engagement.organic_sessions)} organisch) auf ${x.pages.map(p => esc(p.page) + (p.exists ? "" : " (nicht im Inventar)")).join(", ") || "–"}`)}
      ${stage("5", "Engaged Sessions", `${fmtN(x.engagement.engaged)} engagierte Sitzungen`)}
      ${stage("6", "Funnel Intent", x.engagement.micro_sessions ? `≈ ${fmtN(x.engagement.micro_sessions)} Sitzungen mit Heyflow-Interaktion (${fmtN(x.engagement.micro)} Events) – Kontaktabsicht, kein Lead` : "Keine Heyflow-Interaktion gemessen")}
      ${stage("7", "Leads / Contacts", `<b>${fmtN(leadsOf(x.engagement))}</b> = ${fmtN(x.engagement.lead_form)} Form Submissions + ${fmtN(x.engagement.lead_contact)} Direct Contact Actions (Telefon/E-Mail/Chat)`)}
      ${stage("8", "Business Value", x.priority ? `Priorität ${x.priority}/10 laut Business-Profil` : "Keine Leistungspriorität (Querschnittsthema)")}
    </div><div><h3>Signale für den Agenten</h3><ul class="list">${x.signals.map(s => `<li>${chip(SIG_LABEL[s.kind] || s.kind, SIG[s.kind] || "")} ${esc(s.text)}</li>`).join("")}</ul>
      <h3 class="mt">Landingpages im Detail</h3><div class="tbl-wrap"><table><thead><tr><th>Seite</th><th class="num">Sitz.</th><th class="num">organisch</th><th class="num">Engagement</th><th class="num">Intent</th><th class="num">Leads</th></tr></thead><tbody>${x.pages.map(p => `<tr><td class="s path">${esc(p.page)}</td><td class="num">${fmtN(p.sessions)}</td><td class="num">${fmtN(p.organic_sessions)}</td><td class="num">${p.eng_rate === null || p.eng_rate === undefined ? "–" : fmtPct(p.eng_rate, 0)}</td><td class="num">${fmtN(p.micro_sessions)}</td><td class="num">${fmtN(leadsOf(p))} <span class="s">(${p.lead_form}F · ${p.lead_contact}K)</span></td></tr>`).join("")}</tbody></table></div></div></div></div>`;
}

/* ------------------------------------------------------------ Analytics (GA4) */
function gaWindow(range) {
  const daily = S.d.ga4.daily, n = RANGES[range]; if (!daily.length) return { cur: [], prev: null };
  // Kalenderfenster bis zum letzten GA4-Tag (Tage ohne Sitzungen fehlen in den Rohdaten -> nach Datum filtern, nicht nach Anzahl)
  const end = S.d.ga4.fetch_range?.[1] || daily.at(-1).date;
  if (!n) return { cur: daily, prev: null, from: daily[0].date, to: end };
  const from = addDays(end, -(n - 1)), pfrom = addDays(end, -(2 * n - 1)), pto = addDays(end, -n);
  return { cur: daily.filter(r => r.date >= from && r.date <= end), prev: daily[0].date <= pfrom ? daily.filter(r => r.date >= pfrom && r.date <= pto) : null, from, to: end };
}
const gaSum = rows => { if (!rows) return null; const s = k => rows.reduce((a, r) => a + r[k], 0); const ses = s("sessions"); return { sessions: ses, users: s("users"), organic: s("organic"), engaged: s("engaged"), er: ses ? s("engaged") / ses : null, avg: ses ? s("eng_time") / ses : null, lf: s("lead_form"), lc: s("lead_contact"), ms: s("micro_sessions"), mi: s("micro") }; };
pages.analytics = () => {
  const g = S.d.ga4;
  if (!g.available) { view().innerHTML = `<div class="page-head"><div><h1>Analytics (GA4)</h1></div></div><div class="card empty">GA4 not available.</div>`; return; }
  const r = S.gaRange || "12M", w = gaWindow(r), cur = gaSum(w.cur), prev = gaSum(w.prev), q = g.quality;
  view().innerHTML = `<div class="page-head"><div><h1>Analytics (GA4)</h1><div class="sub">${esc(g.property.name)} · Property ${esc(g.property.id)} · ${fmtDate(w.from)} – ${fmtDate(w.to)}${w.prev ? " · vs. Vorperiode gleicher Länge" : ""}</div></div>
    <div class="seg" data-range="gaRange">${Object.keys(RANGES).map(x => `<button class="${r === x ? "on" : ""}" data-r="${x}">${x}</button>`).join("")}</div></div>
  <div class="notice row">${chip("Erfassung ≈ " + fmtPct(q.capture_ratio, 0) + " der GSC-Klicks", "amber", true)}<span>Kleine Fallzahlen. ${fmtN(q.test_sessions_excluded)} Tag-Assistant-Testsitzungen und ${fmtN(q.test_conversion_events_excluded)} Test-Events sind aus Kanälen, Landingpages und Conversions ausgeschlossen. Leads, Funnel Intent und Engagement folgen der Business-Klassifizierung des SEO Autopiloten (state/conversions.json) – unabhängig davon, welche Events in GA4 als Key Event markiert sind.</span></div>
  <div class="kpis mt">
    ${kpi("Users", fmtN(cur.users), delta(cur.users, prev?.users))}
    ${kpi("Sessions", fmtN(cur.sessions), delta(cur.sessions, prev?.sessions))}
    ${kpi("Organic Search Sessions", fmtN(cur.organic), delta(cur.organic, prev?.organic))}
    ${kpi("Engagement Rate", fmtPct(cur.er, 0), prev && prev.er !== null && cur.er !== null ? delta(cur.er * 100, prev.er * 100, { abs: true, unit: "pp" }) : delta(null, null))}
    ${kpi("Avg. Engagement Time", fmtSec(cur.avg), `<span class="flat">je Sitzung</span>`)}
    ${kpi("Leads / Contacts", fmtN(cur.lf + cur.lc), `<span class="flat">${fmtN(cur.lf)} Form · ${fmtN(cur.lc)} Kontakt · Intent ${fmtN(cur.ms)} Sitz.</span>`, "Form Submissions + Direct Contact Actions (Telefon/E-Mail/Chat). Funnel Intent (Heyflow) separat, nicht addiert.")}
  </div>
  <div class="card"><div class="card-h"><div><h2>Sitzungen je Kanal</h2><div class="hint">monatlich, seit ${fmtDate(g.first)} · ohne Testverkehr</div></div>${legend(gaSeries())}</div><div class="card-b"><div id="ga-ch"></div></div></div>
  <div class="grid g2 mt">
    <div class="card"><div class="card-h"><div><h2>Default Channel Group</h2><div class="hint">${fmtDate(S.d.funnel.window[0])} – ${fmtDate(S.d.funnel.window[1])} (GSC-Zeitraum)</div></div></div><div class="card-b flush" id="ga-chan"></div></div>
    <div class="card"><div class="card-h"><div><h2>Source / Medium</h2><div class="hint">gesamt seit ${fmtDate(g.first)}</div></div></div><div class="card-b flush" id="ga-sm"></div></div>
  </div>
  <div class="card mt"><div class="card-h"><div><h2>Landingpages</h2><div class="hint">${fmtDate(S.d.funnel.window[0])} – ${fmtDate(S.d.funnel.window[1])} · Pfade normalisiert · alle Kanäle</div></div></div><div id="ga-lp"></div></div>
  <div class="card mt"><div class="card-h"><div><h2>Events – Business-Klassifizierung</h2><div class="hint">Eigene Mapping-Schicht (state/conversions.json) nach deiner Definition: Lead / Contact · Micro Conversion / Funnel Intent · Engagement · Outbound. GA4-Key-Events sind eine separate Spalte und werden nicht verändert.</div></div></div><div id="ga-ev"></div></div>
  <div class="grid g2 mt">
    <div class="card"><div class="card-h"><h2>Geräte</h2><span class="hint">gesamt</span></div><div class="card-b flush"><table><thead><tr><th>Gerät</th><th class="num">Sitzungen</th><th class="num">organisch</th><th class="num">Engagement</th></tr></thead><tbody>${g.devices.map(x => `<tr><td>${esc(x.device)}</td><td class="num">${fmtN(x.sessions)}</td><td class="num">${fmtN(x.organic || 0)}</td><td class="num">${fmtPct(x.engaged / x.sessions, 0)}</td></tr>`).join("")}</tbody></table></div></div>
    <div class="card"><div class="card-h"><h2>Regionen</h2><span class="hint">gesamt · Sitzungen</span></div><div class="card-b flush"><table><thead><tr><th>Region</th><th class="num">Sitzungen</th></tr></thead><tbody>${g.regions.map(x => `<tr><td>${esc(x.region)}</td><td class="num">${fmtN(x.sessions)}</td></tr>`).join("")}</tbody></table></div></div>
  </div>`;
  drawGaChannels("ga-ch");
  const chanCols = [{ key: "channel", label: "Kanal" }, { key: "sessions", label: "Sitzungen", num: true, render: x => fmtN(x.sessions) },
    { key: "eng_rate", label: "Engagement", num: true, render: x => fmtPct(x.eng_rate, 0) }, { key: "avg_eng_time", label: "Ø Zeit", num: true, render: x => fmtSec(x.avg_eng_time) },
    { key: "micro_sessions", label: "Funnel Intent", num: true, render: x => intentCell(x) }, { key: "leads", label: "Leads", num: true, value: x => leadsOf(x), render: x => leadCell(x) }];
  mount("ga-chan", table({ rows: g.channels_window, columns: chanCols, pageSize: 12 })); $(".tbl-tools", $("#ga-chan"))?.remove();
  mount("ga-sm", table({ rows: g.source_medium, pageSize: 10, columns: [{ key: "source_medium", label: "Source / Medium", render: x => `${esc(x.source_medium)}${x.test ? ` ${chip("Test", "amber")}` : ""}<div class="s">${esc(x.channel)}</div>` }, { key: "sessions", label: "Sitzungen", num: true, render: x => fmtN(x.sessions) }, { key: "engaged", label: "Engagiert", num: true, render: x => fmtN(x.engaged) }] })); $(".tbl-tools", $("#ga-sm"))?.remove();
  mount("ga-lp", table({ rows: g.landing, pageSize: 15, search: ["page"], columns: [
    { key: "page", label: "Landingpage", render: x => `<span class="q path">${esc(x.page)}</span>` }, { key: "sessions", label: "Sitzungen", num: true, render: x => fmtN(x.sessions) },
    { key: "organic", label: "organisch", num: true, render: x => fmtN(x.organic || 0) }, { key: "paid", label: "Paid", num: true, render: x => fmtN(x.paid || 0) },
    { key: "eng_rate", label: "Engagement", num: true, render: x => fmtPct(x.eng_rate, 0) }, { key: "avg_eng_time", label: "Ø Zeit", num: true, render: x => fmtSec(x.avg_eng_time) },
    { key: "micro_sessions", label: "Funnel Intent", num: true, render: x => intentCell(x) }, { key: "leads", label: "Leads", num: true, value: x => leadsOf(x), render: x => leadCell(x) }] }));
  const LVL = { lead: ["Lead / Contact", "green"], micro: ["Micro Conversion / Funnel Intent", "blue"], engagement: ["Engagement", ""], outbound: ["Outbound / sonstige", ""], system: ["System", ""], unused: ["Nicht genutzt", ""], unmapped: ["Nicht zugeordnet", "amber"] };
  const SUB = { form_submission: "Form Submission", contact_action: "Direct Contact Action" };
  mount("ga-ev", table({ rows: g.events, pageSize: 30, search: ["event", "label"], filters: [{ key: "level", label: "Ebene", options: Object.keys(LVL) }], sort: null, columns: [
    { key: "event", label: "Event", render: x => `<div class="q">${esc(x.event)}</div><div class="s">${esc(x.label || "")}</div>` },
    { key: "level", label: "Business-Klassifizierung (SEO Autopilot)", render: x => `${chip(LVL[x.level]?.[0] || x.level, LVL[x.level]?.[1] || "")}${x.subtype ? `<div class="s">${esc(SUB[x.subtype] || x.subtype)}</div>` : ""}${x.duplicate_of ? `<div class="s down">Duplikat von ${esc(x.duplicate_of)} – nicht gezählt</div>` : ""}` },
    { key: "key_event_now", label: "GA4 Key Event", tip: "Deine GA4-Konfiguration – wird nicht bewertet und nicht verändert", render: x => x.key_event_now ? chip("Key Event", "outline") : `<span class="s">–</span>` },
    { key: "total", label: "gesamt", num: true, render: x => fmtN(x.total) }, { key: "window", label: "16 Mon.", num: true, render: x => fmtN(x.window) },
    { key: "test_events", label: "davon Test", num: true, tip: "Tag-Assistant-Testverkehr – wird ausgeschlossen", render: x => x.test_events ? `<span class="down">${fmtN(x.test_events)}</span>` : "–" },
    { key: "last", label: "zuletzt", render: x => `<span style="white-space:nowrap">${x.last ? esc(x.last.slice(5) + "/" + x.last.slice(0, 4)) : "–"}</span>` },
    { key: "note", label: "Hinweis", sort: false, render: x => `<div class="s">${esc(x.note || "")}</div>` }] }));
};
const gaSeries = () => [{ key: "Organic Search", label: "Organic Search", color: "var(--seg-b2b)", type: "line" }, { key: "Paid", label: "Paid (Search + P-Max)", color: "var(--seg-b2c)", type: "line" }, { key: "Direct", label: "Direct", color: "var(--seg-price)", type: "line" }, { key: "Other", label: "Andere", color: "var(--seg-unknown)", type: "line" }];
function drawGaChannels(id) {
  const pts = S.d.ga4.channel_month.map(m => { const o = { x: m.month + "-01", "Organic Search": m["Organic Search"] || 0, Paid: (m["Paid Search"] || 0) + (m["Cross-network"] || 0) + (m["Paid Other"] || 0), Direct: m.Direct || 0 };
    o.Other = Object.entries(m).filter(([k]) => !["month", "Organic Search", "Paid Search", "Cross-network", "Paid Other", "Direct"].includes(k)).reduce((a, [, v]) => a + v, 0); return o; });
  chartInto(id, { points: pts, series: gaSeries(), height: 200, xMode: "month" });
}

/* ------------------------------------------------------------ Google Ads */
pages.ads = () => {
  const a = S.d.ads, dsc = a.discovery || {}, acc = dsc.account || {}, t = dsc.tests || {};
  const st = (k, label) => { const v = t[k]; return `<tr><td>${label}</td><td>${v === "ok" ? chip("Verfügbar", "green", true) : v ? chip("Nicht verfügbar", "red", true) : chip("Unknown", "")}</td><td class="s">${v && v !== "ok" ? esc(v) : ""}</td></tr>`; };
  view().innerHTML = `<div class="page-head"><div><h1>Google Ads</h1><div class="sub">Read-only über das MCC ${esc(dsc.mcc?.name || "")} (${esc(dsc.mcc?.id || "")}) · API ${esc(dsc.api_version || "")} · geprüft ${fmtDateTime(dsc.checked_at)}</div></div></div>
  <div class="grid g2">
    <div class="card"><div class="card-h"><h2>Konto Spreewald Luftaufnahmen</h2>${chip(acc.status === "ENABLED" ? "Aktiv" : acc.status === "CANCELED" ? "Bewusst gekündigt" : (acc.status || "Unknown"), acc.status === "ENABLED" ? "green" : "", true)}</div><div class="card-b"><div class="kv">
      <div class="k">Customer ID</div><div>${esc(acc.id || "–")}</div><div class="k">Status</div><div>${esc(acc.status || "–")}</div><div class="k">Währung / Zeitzone</div><div>${esc(acc.currency || "–")} · ${esc(acc.time_zone || "–")}</div>
      <div class="k">MCC</div><div>${esc(dsc.mcc?.name || "–")} · ${fmtN(dsc.client_accounts?.total)} Kundenkonten · Berechtigung ${esc(dsc.mcc?.permission || "–")}</div>
      <div class="k">Bedeutung</div><div>Account intentionally canceled · historical paid data via GA4 where reliable. Bewusst gekündigt und nicht reaktiviert. Über die API daher keine Kampagnen-, Search-Term- und Conversion-Action-Daten (<b>Not available</b>); historische Paid-Daten kommen aus GA4 (unten, mit Qualitätskennzeichnung).</div></div></div></div>
    <div class="card"><div class="card-h"><h2>API-Fähigkeiten (Explorer, read-only)</h2></div><div class="card-b flush"><div class="tbl-wrap"><table><thead><tr><th>Funktion</th><th>Status</th><th>Hinweis</th></tr></thead><tbody>
      ${st("list_accessible_customers", "Account Discovery")}${st("gaql_mcc", "Reporting (GAQL) im MCC")}<tr><td>Reporting Spreewald-Konto</td><td>${chip("Nicht verfügbar", "", true)}</td><td class="s">Konto bewusst gekündigt – Paid-Historie über GA4</td></tr><tr><td>Keyword Planner</td><td>${chip("Nicht genutzt", "", true)}</td><td class="s">Bewusste Entscheidung – Semrush ist die primäre Keyword-Quelle</td></tr>
      </tbody></table></div><div class="card-b mini" style="padding-top:10px">Zugriffsstufe des Cloud-Projekts: Explorer (Reporting und Account-Funktionen, nur lesend). Keyword-Daten kommen aus Semrush und GSC.</div></div></div>
  </div>
  ${a.available ? `<div class="card mt"><div class="card-h"><div><h2>Paid-Historie über GA4</h2><div class="hint">${esc(a.source)} · ${esc(a.range?.[0])} – ${esc(a.range?.[1])}</div></div></div><div class="card-b">
    <div class="kpis k4" style="margin-bottom:10px">${kpi("Kosten (Keyword-Ebene)", fmtEur(a.totals.keyword_level_cost), `<span class="flat">${fmtN(a.totals.keyword_level_clicks)} Klicks · plausibel</span>`)}${kpi("Ø CPC (Keyword-Ebene)", a.totals.keyword_level_clicks ? (a.totals.keyword_level_cost / a.totals.keyword_level_clicks).toLocaleString("de-DE", { maximumFractionDigits: 2, minimumFractionDigits: 2 }) + " €" : "–", `<span class="flat">Search-Kampagnen</span>`)}${kpi("Paid-Sitzungen (GA4)", fmtN(a.totals.paid_sessions), `<span class="flat">Search + P-Max</span>`)}${kpi("Kampagnen-Ebene", fmtEur(a.totals.campaign_level_cost), `<span class="down">${a.totals.flagged_rows} von ${a.history_months.length} Zeilen auffällig – nicht verwenden</span>`)}</div>
    <div class="callout amber">Kampagnenwerte aus der GA4-Verknüpfung sind unplausibel (identische Werte in mehreren Monaten, bis zu 150 Klicks je Sitzung). Für Entscheidungen nur die Keyword-Ebene verwenden und im Zweifel im Google-Ads-Konto gegenprüfen. CPA/ROAS sind nicht belastbar berechenbar: keine Conversion-Werte, Conversions nur als GA4-Events.</div></div>
    <div class="tabs" id="adtabs">${["Keywords", "Suchanfragen", "Landingpages", "Kampagnen × Monat"].map(x => `<button data-t="${x}" class="${(S.ui.adtab || "Keywords") === x ? "on" : ""}">${x}</button>`).join("")}</div><div id="ad-body"></div></div>` : `<div class="card mt empty">Keine historischen Paid-Daten über GA4 verfügbar.</div>`}`;
  if (!a.available) return;
  $("#adtabs").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; S.ui.adtab = b.dataset.t; $("#adtabs").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); renderAdTab(); });
  renderAdTab();
};
function renderAdTab() {
  const a = S.d.ads, t = S.ui.adtab || "Keywords"; let node;
  if (t === "Keywords") node = table({ rows: a.keywords, pageSize: 15, columns: [{ key: "keyword", label: "Keyword", render: k => `<div class="q">${esc(k.keyword)}</div><div class="s">${esc(CL_LABEL(k.cluster))}</div>` },
    { key: "clicks", label: "Klicks", num: true }, { key: "cost", label: "Kosten", num: true, render: k => fmtEur(k.cost) }, { key: "cpc", label: "Ø CPC", num: true, render: k => k.cpc === null ? "–" : k.cpc.toLocaleString("de-DE", { minimumFractionDigits: 2 }) + " €" },
    { key: "sessions", label: "Sitzungen", num: true }, { key: "engaged", label: "Engagiert", num: true }, { key: "key_events", label: "Key Events*", num: true, tip: "GA4-Key-Events inkl. Nicht-Conversions (siehe Analytics)" }] });
  if (t === "Suchanfragen") node = table({ rows: a.search_queries, pageSize: 15, columns: [{ key: "query", label: "Search Term", render: k => `<div class="q">${esc(k.query)}</div><div class="s">${esc(CL_LABEL(k.cluster))}</div>` }, { key: "sessions", label: "Sitzungen", num: true }, { key: "engaged", label: "Engagiert", num: true }] });
  if (t === "Landingpages") node = table({ rows: a.landing, pageSize: 15, columns: [{ key: "page", label: "Final URL / Landingpage", render: k => `<span class="q path">${esc(k.page)}</span>` }, { key: "sessions", label: "Paid-Sitzungen", num: true }, { key: "engaged", label: "Engagiert", num: true }] });
  if (t === "Kampagnen × Monat") node = table({ rows: a.history_months, pageSize: 20, sort: { key: "month", dir: 1 }, columns: [{ key: "month", label: "Monat" }, { key: "campaign", label: "Kampagne", render: k => `<div class="q">${esc(k.campaign)}</div>${k.flags.length ? `<div class="s down">${k.flags.map(esc).join(" · ")}</div>` : ""}` },
    { key: "impressions", label: "Impr.", num: true, render: k => fmtN(k.impressions) }, { key: "clicks", label: "Klicks", num: true, render: k => fmtN(k.clicks) }, { key: "cost", label: "Kosten", num: true, render: k => fmtEur(k.cost) }, { key: "sessions", label: "Sitzungen", num: true }] });
  mount("ad-body", node);
}

/* ------------------------------------------------------------ approvals (Claude artifact db) */
/* Entscheidungen werden im db-Speicher des Claude-Artifacts abgelegt (Collection "decisions", ein Dokument je Entscheidung).
   Der Agent liest sie in seiner nächsten Session (ArtifactData), verarbeitet sie und setzt agent_status = "processed".
   Keine Entscheidung löst hier eine Website-Aktion aus. Lokal (ohne Claude-Viewer) ist der Speicher nicht verfügbar. */
const DB = { state: "loading", reason: "", ns: null, canWrite: false, decisions: [], fromCache: false, error: "" };
const DEC = { wp_retry: ["WordPress-Draft erneut", "blue"], research_retry: ["Research nachholen", "blue"], approve: ["Approve", "green"], approve_override: ["Approve (Override)", "amber"], request_changes: ["Request changes", "amber"], reject: ["Reject", "red"], retry: ["Erneut versucht", "blue"] };
const AGENT = { pending: ["Waiting for agent", "amber"], processed: ["Processed by agent", "green"], superseded: ["Test phase · superseded", ""] };
async function initDb() {
  const fail = (reason, error = "") => { DB.state = "unavailable"; DB.reason = reason; DB.error = error; dbChanged(); };
  if (!window.claude || typeof window.claude.use !== "function") return fail("local");
  const timer = setTimeout(() => { if (DB.state === "loading") fail("timeout"); }, 10000);
  let db = null;
  try { db = await window.claude.use("db"); } catch (e) { db = null; }
  if (!db) { clearTimeout(timer); return fail("not_granted"); }
  DB.ns = db;
  try { const user = await window.claude.use("user"); DB.canWrite = user ? ((await user.isOwner()) ?? false) : false; } catch (e) { DB.canWrite = false; }
  db.collection("decisions").onSnapshot(snap => {
    clearTimeout(timer);
    DB.decisions = snap.docs.map(d => ({ _id: d.id, ...d.data() })).sort((a, b) => String(b.decided_at).localeCompare(String(a.decided_at)));
    DB.fromCache = snap.metadata.fromCache; DB.state = "ready"; dbChanged();
  }, err => { clearTimeout(timer); fail("error", err.code + ": " + err.message); });
  db.collection("workflow").onSnapshot(snap => {
    WF.items = Object.fromEntries(snap.docs.map(d => [d.id, { _id: d.id, ...d.data() }])); WF.live = !snap.metadata.fromCache || snap.size > 0;
    if (parseHash().key === "approvals") { renderBoard(); if (WF_OPEN && !document.activeElement?.matches("textarea")) openCard(WF_OPEN); }
    document.querySelectorAll("[data-rr-opp]").forEach(el => { const o = S.d.opportunities.find(x => x.id === el.dataset.rrOpp); if (o && !el.closest("#wf-drawer")) el.outerHTML = researchActions(o, el.dataset.rrPlace); });
    updateBadges();
  }, () => { /* Board fällt auf den Git-Spiegel zurück */ });
}
const clientDecisions = () => DB.decisions.filter(x => x.client === S.client);
const latestDecision = itemId => clientDecisions().find(x => x.item_id === itemId);
function dbChanged() {
  updateBadges();
  const k = parseHash().key;
  if (k === "approvals") { renderDecisionLog(); renderStoreNotice(); renderBoard(); }
  if (k === "sources") { const el = $("#store-card"); if (el) el.outerHTML = storeCard(); }
  if (k === "overview") { const el = $("#ov-dec"); if (el) el.innerHTML = decisionSummary(); }
}
function storeStatus() {
  if (DB.state === "loading") return ["Connecting…", "", "Connecting to the artifact's decision store."];
  if (DB.state === "ready") return DB.canWrite ? ["Connected", "green", "Freigaben werden persistent im Artifact gespeichert. Nach einer Aktion wird Claude über eine geplante Aufgabe angestoßen; ist das nicht möglich, verarbeitet Claude sie beim nächsten Lauf."] : ["Read-only", "amber", "Nur der Owner des Artifacts kann Freigaben erteilen."];
  const why = { local: "Lokale Vorschau – Freigaben sind nur im Claude-Artifact möglich.", timeout: "The decision store did not answer within 10 seconds. Saved decisions may not be shown.", not_granted: "Decision storage is not available in this view (signed out or not granted).", error: "The decision store reported an error: " + DB.error }[DB.reason] || "Not available.";
  return ["Not available", "red", why];
}
const storeCard = () => { const [l, c, t] = storeStatus(); const pend = clientDecisions().filter(x => x.agent_status === "pending").length;
  return `<div class="card" id="store-card"><div class="card-h"><h2>Approval store</h2>${chip(l, c, true)}</div><div class="card-b"><div class="kv">
    <div class="k">Storage</div><div>Claude artifact <code>db</code> · collection <code>decisions</code></div>
    <div class="k">Status</div><div>${esc(t)}</div>
    <div class="k">Decisions recorded</div><div>${DB.state === "ready" ? `${fmtN(clientDecisions().length)} · ${fmtN(pend)} waiting for the agent` : "Unknown"}</div>
    <div class="k">Mirror in Git</div><div><code>state/approvals.json → decision_log</code> · ${fmtN(S.d.approvals.decision_log.length)} entries (written by the agent after processing)</div>
    <div class="k">Website actions</div><div>None. A decision never changes the website.</div></div></div></div>`; };
function ga4Card() {
  const g = S.d.ga4, src = S.d.sources.ga4 || {};
  if (!g.available) return `<div class="card"><div class="card-h"><h2>Google Analytics 4</h2>${chip("Not available", "red", true)}</div></div>`;
  return `<div class="card"><div class="card-h"><h2>Google Analytics 4</h2>${statusChip(src.status === "connected" ? "Connected" : src.status || "Unknown")}</div><div class="card-b"><div class="kv">
    <div class="k">Property</div><div>${esc(g.property.name)} · ${esc(g.property.id)}</div><div class="k">Zugriff</div><div>${esc(src.access || "–")}</div>
    <div class="k">APIs</div><div>Data API ${esc(src.apis?.analytics_data_api || "?")} · Admin API ${esc(src.apis?.analytics_admin_api || "?")}</div>
    <div class="k">Last successful sync</div><div>${fmtDate(src.last_fetch)} ${freshness(src.last_fetch, 7)}</div>
    <div class="k">Data range</div><div>${fmtDate(g.first)} – ${fmtDate(g.fetch_range?.[1])} <span class="mini">(letzte Sitzung ${fmtDate(g.last)})</span></div>
    <div class="k">Qualität</div><div>Thresholding ${g.quality.thresholding ? "ja" : "nein"} · Sampling ${g.quality.sampling ? "ja" : "nein"} · Erfassung ≈ ${fmtPct(g.quality.capture_ratio, 0)} der GSC-Klicks · ${fmtN(g.quality.test_sessions_excluded)} Testsitzungen ausgeschlossen</div>
    <div class="k">Retention</div><div>${esc(g.property.retention || "–")}</div>
    <div class="k">Ads-Verknüpfung</div><div>${g.property.ads_links.map(esc).join(", ") || "keine"}</div>
    <div class="k">Limitierungen</div><div class="s">${(src.limitations || []).map(esc).join(" · ")}</div></div></div></div>`;
}
function adsCard() {
  const src = S.d.sources.google_ads || {}, a = S.d.ads, acc = src.account || {};
  const c = src.status === "connected_account_canceled" ? ["Connected", "green"] : src.status === "connected" ? ["Connected", "green"] : [src.status || "Unknown", ""];
  return `<div class="card"><div class="card-h"><h2>Google Ads</h2>${chip(c[0], c[1], true)}</div><div class="card-b"><div class="kv">
    <div class="k">Zugriff</div><div>${esc(src.access || "–")} · API ${esc(src.api_version || "–")}</div>
    <div class="k">MCC</div><div>${esc(src.mcc?.name || "–")} · ${esc(src.mcc?.id || "–")} · ${fmtN(src.client_accounts_total)} Kundenkonten</div>
    <div class="k">Spreewald</div><div>${esc(src.status_label || "")}</div>
    <div class="k">Konto</div><div>${esc(acc.name || "–")} · ${esc(acc.id || "–")} · <b>${esc(acc.status || "–")}</b>${acc.note ? `<div class="s">${esc(acc.note)}</div>` : ""}</div>
    <div class="k">Last check</div><div>${fmtDate(src.last_check)} ${freshness(src.last_check, 30)}</div>
    <div class="k">Last successful sync</div><div>${src.last_fetch ? fmtDate(src.last_fetch) : "Not available – Konto liefert keine API-Daten"}</div>
    <div class="k">Data range</div><div>${a.range ? `${esc(a.range[0])} – ${esc(a.range[1])} (Historie über GA4)` : "Not available"}</div>
    <div class="k">Fähigkeiten</div><div class="s">${Object.entries(src.capabilities || {}).map(([k, v]) => `${esc(k)}: ${esc(v)}`).join("<br>")}</div>
    <div class="k">Limitierungen</div><div class="s">${(src.limitations || []).map(esc).join(" · ")}</div></div></div></div>`;
}
function wpCard() {
  const w = S.d.sources.wordpress; if (!w) return "";
  const c = w.capabilities || {};
  return `<div class="card" id="wp-card"><div class="card-h"><h2>WordPress</h2>${chip("Verbunden · nur lesend geprüft", "green", true)}</div><div class="card-b"><div class="kv">
    <div class="k">Zugriff</div><div>${esc(w.access)}</div><div class="k">Rolle</div><div>${esc(w.role)}</div>
    <div class="k">Editor</div><div>${esc(w.editor)}</div><div class="k">SEO</div><div>${esc(w.seo)}</div>
    <div class="k">CREATE Draft</div><div>${esc(c.create_draft)}</div><div class="k">OPTIMIZE</div><div>${esc(c.optimize_existing)}</div>
    <div class="k">Preview</div><div>${esc(c.preview)}</div><div class="k">Publish</div><div><b>${esc(c.publish)}</b></div>
    <div class="k">Geprüft</div><div>${fmtDate(w.checked)} · Zugangsdaten: ${esc(w.credentials)}</div></div>
    ${(w.risks || []).length ? `<div class="callout amber mt"><b>Vor dem ersten Schreibzugriff</b>${ul(w.risks)}</div>` : ""}
    <div class="s mt">Workflow-Ziel: Gate 2 → WordPress-Draft → QA → finale Freigabe → Veröffentlichen. Nie automatisch: Veröffentlichen, URL/Slug, Redirects, Canonical, Indexierung, Plugin-/Server-Konfiguration.</div></div></div>`;
}
function kpCard() {
  const k = S.d.sources.keyword_planner || {};
  return `<div class="card"><div class="card-h"><h2>Google Keyword Planner</h2>${chip(k.label || "Not used", "", true)}</div><div class="card-b"><div class="kv">
    <div class="k">Status</div><div>Bewusst nicht genutzt (Entscheidung ${fmtDate(k.decided)})</div>
    <div class="k">Begründung</div><div class="s">${esc(k.reason || "–")}</div>
    <div class="k">Keyword-Quelle</div><div>Semrush (primär) + GSC (tatsächliche Queries)</div></div></div></div>`;
}
function decisionSummary() {
  if (DB.state !== "ready") return `<span class="mini">${esc(storeStatus()[2])}</span>`;
  const d = clientDecisions(), pend = d.filter(x => x.agent_status === "pending").length;
  return d.length ? `${fmtN(d.length)} decisions recorded · <b>${fmtN(pend)}</b> waiting for the agent` : `No decisions recorded yet.`;
}
function updateBadges() {
  if (!S.d) return;
  const drafts = wfCards().filter(c => wfCol(wfDoc(c.id)) === "draft").length; // Entwürfe, die auf dein Review warten
  $("#nav-approvals").textContent = drafts || "";
}
/** Search → Business für eine Opportunity: Cluster-Funnel + eigene Landingpage (GA4/Ads), gleiche Zahlen wie auf der Funnel-Seite */
function oppBusinessCard(o) {
  const f = S.d.funnel?.clusters.find(c => c.cluster === o.gsc_cluster);
  const norm = p => p ? (p.split("?")[0].toLowerCase().replace(/\/+$/, "") || "/") : null;
  const lp = o.existing_page ? S.d.funnel.pages.find(p => p.page === norm(o.existing_page)) : null;
  if (!f && !lp) return `<div class="card"><div class="card-h"><h2>Search → Business</h2></div><div class="card-b"><span class="mini">Kein passender Cluster mit GA4-/Ads-Daten.</span></div></div>`;
  const e = f?.engagement;
  return `<div class="card"><div class="card-h"><div><h2>Search → Business</h2><div class="hint">GA4 + Ads-Historie · ${fmtDate(S.d.funnel.window[0])} – ${fmtDate(S.d.funnel.window[1])}</div></div><a href="#funnel" class="mini">Funnel →</a></div><div class="card-b"><div class="kv">
    ${f ? `<div class="k">Cluster „${esc(CL_LABEL(f.cluster))}“</div><div>${fmtN(e.sessions)} Sitzungen · ${fmtN(e.engaged)} engagiert · Funnel Intent ${fmtN(e.micro_sessions)} Sitz. · <b>${fmtN(leadsOf(e))} Leads</b> (${e.lead_form} Form · ${e.lead_contact} Kontakt)</div>
    <div class="k">Paid-Historie</div><div>${f.paid.keyword_cost ? `${fmtEur(f.paid.keyword_cost)} für ${f.paid.keyword_clicks} Klicks (2023–24, Keyword-Ebene)` : f.paid.campaigns.length ? "nur Kampagnenwerte (unplausibel)" : "keine"}</div>` : ""}
    ${lp ? `<div class="k">Diese Seite</div><div>${fmtN(lp.ga4_sessions)} Sitzungen (${fmtN(lp.ga4_organic)} organisch) · Engagement ${lp.eng_rate === null || lp.eng_rate === undefined ? "–" : fmtPct(lp.eng_rate, 0)} · Intent ${fmtN(lp.micro_sessions)} · <b>${fmtN(leadsOf(lp))} Leads</b> (${lp.lead_form} F · ${lp.lead_contact} K)${lp.paid_sessions_hist ? ` · ${fmtN(lp.paid_sessions_hist)} Paid-Sitzungen (hist.)` : ""}</div>` : o.existing_page ? `<div class="k">Diese Seite</div><div class="s">Keine GA4-Sitzungen im Zeitraum</div>` : ""}
    </div>${f ? `<div class="row mt">${f.signals.filter(x => ["weak", "paid", "lead", "intent", "nolead"].includes(x.kind)).map(x => chip(SIG_LABEL[x.kind], SIG[x.kind])).join("")}</div>` : ""}</div></div>`;
}
/* ------------------------------------------------------------ Research Log / Evidence (Audit Trail) */
/* Eine Event-Quelle (state/research_log.json + evidence.json) für Research Log, Research Evidence und Agent Activity. */
const RLD = () => S.d.research_log || { events: [], sources: [], findings: [], summary: {}, actions: {}, source_types: {} };
const srcMap = () => Object.fromEntries(RLD().sources.map(s => [s.id, s]));
const ST_COLOR = { gsc: "blue", ga4: "blue", semrush: "amber", website: "green", competitor: "red", web_search: "", agent: "" };
const RLF = { opp: "", type: "", action: "", date: "", q: "" };
const NA_TXT = "metadata unavailable";
function rlWhen(at, prec) {
  if (!at) return NA_TXT;
  if (prec === "date" || at.length === 10) return `${fmtDate(at)} <span class="s">· Uhrzeit nicht protokolliert</span>`;
  return `${fmtDateTime(at)}${prec === "commit" ? ` <span class="s">· Zeitpunkt des Commits</span>` : ""}`;
}
function semrushBlock(s) {
  const m = s.semrush || {};
  const rows = (m.results || []).map(r => r.url ? `<div>#${esc(r.position)} ${esc(r.domain)} → <a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.url)}</a></div>` : `<div>${esc(r.keyword)} · Vol. ${fmtN(r.volume)} · KD ${fmtD(r.kd, 0)} · CPC ${fmtD(r.cpc, 2)}</div>`).join("");
  return `<div class="rl-sem"><div class="kv"><div class="k">Report</div><div><b>Semrush · ${esc(m.report)}</b> <code>${esc(m.endpoint)}</code></div>
    <div class="k">Keyword</div><div>${esc(m.keyword)}</div><div class="k">Database</div><div>${esc(m.database)}${m.display_limit ? ` · Top ${esc(m.display_limit)}` : ""}</div>
    <div class="k">Ergebnisse</div><div>${fmtN(m.results_count)}</div>
    <div class="k">Kosten</div><div>${Number.isInteger(m.units) ? `<b>${fmtN(m.units)} Units</b>` : `<span class="s">${esc(m.units_note || NA_TXT)}</span>`}</div>
    <div class="k">Abruf</div><div>${chip(m.mode === "live" ? "Live query" : "Cache hit", m.mode === "live" ? "amber" : "green")} ${rlWhen(s.fetched, s.fetched_precision)}${m.mode_note ? `<div class="s">${esc(m.mode_note)}</div>` : ""}</div>
    <div class="k">Rohdaten</div><div class="s path">${esc(m.raw_id || m.raw_path || "–")}</div></div>
    ${rows ? `<div class="rl-res">${rows}</div>` : ""}
    <div class="s mt">${m.link ? `<a href="${esc(m.link)}" target="_blank" rel="noopener">In Semrush öffnen ↗</a>` : esc(m.link_note || "Kein Semrush-Link verfügbar – Parameter und Ergebnisse oben dokumentiert.")}</div></div>`;
}
function srcItem(s, full = false) {
  const t = RLD().source_types[s.type] || s.type, m = s.meta || {};
  const head = `${chip(t, ST_COLOR[s.type] || "")} ${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a>` : `<b>${esc(s.title)}</b>`} <span class="mini">${esc(s.id)}</span>`;
  const sub = [s.domain && s.url ? esc(s.domain) : "", s.url ? `<span class="path">${esc(s.url)}</span>` : "", `Abruf: ${rlWhen(s.fetched, s.fetched_precision)}`, s.error ? `<span class="down">nicht abrufbar (${esc(s.error.slice(0, 60))})</span>` : "",
    m.property ? `Property ${esc(m.property)}` : "", m.period ? `Zeitraum ${esc(m.period)}` : "", m.dimensions ? `Dimensionen ${esc(m.dimensions)}` : "", m.filter ? `Filter ${esc(m.filter)}` : "", m.tool ? esc(m.tool) : "", m.note ? esc(m.note) : ""].filter(Boolean).join(" · ");
  return `<div class="rl-src">${head}<div class="s">${sub}</div>${full && s.type === "semrush" ? semrushBlock(s) : ""}</div>`;
}
/** „N Quellen anzeigen“ für ein Finding */
function findingRefs(f) {
  const M = srcMap(), ss = f.source_ids.map(i => M[i]).filter(Boolean);
  return `<div class="rl-find"><div>${esc(f.text)}</div>${ss.length ? `<details><summary class="mini">${ss.length} ${ss.length === 1 ? "Quelle" : "Quellen"} anzeigen</summary>${ss.map(s => srcItem(s)).join("")}</details>` : `<span class="mini">ohne Quellenbeleg</span>`}</div>`;
}
const oppFindings = (opp, sec) => RLD().findings.filter(f => f.opp === opp && (!sec || f.section === sec));
function evidenceCard(o) {
  const D = RLD(), src = D.sources.filter(s => (s.opp_ids || []).includes(o.id));
  if (!src.length && !oppFindings(o.id).length) return "";
  const LABEL = { gsc: "GSC", semrush: "Semrush", competitor: "Competitor Websites", website: "Own Website", ga4: "GA4", web_search: "Web Search", agent: "Agent" };
  const order = ["gsc", "semrush", "competitor", "website", "ga4", "web_search", "agent"].filter(t => src.some(s => s.type === t));
  const ev = D.events.filter(e => e.opp === o.id);
  return `<div class="card" id="rs-evidence"><div class="card-h"><div><h2>Research Evidence</h2><div class="hint">${fmtN(src.length)} Quellen · ${fmtN(oppFindings(o.id).length)} belegte Erkenntnisse · ${fmtN(ev.length)} Log-Einträge</div></div><a href="#research-log" class="mini" data-rl-opp="${esc(o.id)}">Im Research Log ansehen →</a></div>
    <div class="card-b">${order.map(t => { const xs = src.filter(s => s.type === t); return `<details class="rl-grp"><summary>${chip(`${LABEL[t]} (${xs.length})`, ST_COLOR[t] || "")}</summary>${xs.map(s => srcItem(s, true)).join("")}</details>`; }).join("")}
    ${oppFindings(o.id).length ? `<h4>Belegte Erkenntnisse</h4>${oppFindings(o.id).map(f => `<div class="row" style="align-items:flex-start"><span class="chip outline">${esc(f.section)}</span>${findingRefs(f)}</div>`).join("")}` : ""}</div></div>`;
}
function rlEvent(e) {
  const D = RLD(), M = srcMap(), o = S.d.opportunities.find(x => x.id === e.opp), ss = (e.source_ids || []).map(i => M[i]).filter(Boolean);
  const fs = (e.finding_ids || []).map(i => D.findings.find(f => f.id === i)).filter(Boolean);
  return `<article class="rl-ev" data-ev="${esc(e.id)}"><div class="rl-head"><span class="rl-when">${rlWhen(e.at, e.at_precision)}</span>${e.opp ? ` — <a href="#opp-${esc(e.opp)}">${esc(e.opp)}${o ? " " + esc(o.name) : ""}</a>` : ""}</div>
    <h3>${esc(e.title || D.actions[e.action] || e.action)} ${chip(D.actions[e.action] || e.action, "outline")}${e.units ? chip(fmtN(e.units) + " Units", "amber") : ""}${e.units === null ? chip("Units: " + NA_TXT, "") : ""}${e.superseded ? chip(e.superseded, "") : ""}</h3>
    ${e.summary ? `<p>${esc(e.summary)}</p>` : ""}
    ${e.found ? `<div><b>Gefunden:</b> ${esc(e.found)}</div>` : ""}
    ${e.insight ? `<div class="mt"><b>Erkenntnis:</b> ${esc(e.insight)}</div>` : ""}
    ${fs.length ? `<div class="mt">${fs.map(findingRefs).join("")}</div>` : ""}
    ${ss.length ? `<details class="mt" ${ss.length <= 3 ? "open" : ""}><summary><b>Quellen (${ss.length})</b></summary>${ss.map(s => srcItem(s, true)).join("")}</details>` : ""}
    ${(e.links || []).map(l => `<a class="mini" href="${esc(l.url)}" target="_blank" rel="noopener">→ ${esc(l.label)}</a>`).join(" ")}</article>`;
}
function rlMatch(e) {
  const M = srcMap(), ss = (e.source_ids || []).map(i => M[i]).filter(Boolean);
  if (RLF.opp && e.opp !== RLF.opp) return false;
  if (RLF.action && e.action !== RLF.action) return false;
  if (RLF.type && !ss.some(s => s.type === RLF.type) && !(RLF.type === "agent" && !ss.length)) return false;
  if (RLF.date && (e.at || "").slice(0, 10) !== RLF.date) return false;
  if (RLF.q) { const q = RLF.q.toLowerCase(); const hay = [e.opp, e.title, e.summary, e.found, e.insight, ...ss.map(s => [s.title, s.domain, s.url, s.semrush?.keyword].join(" "))].join(" ").toLowerCase(); if (!hay.includes(q)) return false; }
  return true;
}
pages["research-log"] = () => {
  const D = RLD(), sm = D.summary || {}, b = D.semrush_budget || {};
  const dates = [...new Set(D.events.map(e => (e.at || "").slice(0, 10)))].sort().reverse();
  const opts = (arr, cur) => arr.map(([v, l]) => `<option value="${esc(v)}" ${v === cur ? "selected" : ""}>${esc(l)}</option>`).join("");
  view().innerHTML = `<div class="page-head"><div><h1>Research Log</h1><div class="sub">Arbeitsprotokoll des SEO-Agenten: was gemacht wurde, was gefunden wurde, auf welchen Quellen es beruht. Kein Debug-Log, keine internen Gedankengänge.</div></div></div>
    <div class="kpis k4">
      <div class="kpi card"><div class="k-label">Log-Einträge</div><div class="k-val">${fmtN(sm.events)}</div><div class="s">${fmtN(sm.sources)} Quellen · ${fmtN(sm.findings)} belegte Erkenntnisse</div></div>
      <div class="kpi card"><div class="k-label">Semrush-Units (protokolliert)</div><div class="k-val">${fmtN(sm.semrush_units_known)}</div><div class="s">${Object.entries(sm.semrush_by_report || {}).map(([r, x]) => `${esc(r)}: ${x.queries} Abfr. · ${fmtN(x.units)} Units${x.unknown ? ` (${x.unknown}× Kosten unbekannt)` : ""}`).join("<br>") || "keine Abfragen"}</div></div>
      <div class="kpi card"><div class="k-label">Semrush-Kontostand</div><div class="k-val">${fmtN(b.balance)}</div><div class="s">Reserve ${fmtN(b.reserve)} · Stand ${fmtDate(b.checked_at)} · ${b.automatic_read ? "automatisch gelesen" : "fortgeschrieben (Konnektor liefert keinen Kontostand)"}</div></div>
      <div class="kpi card"><div class="k-label">SERP-Kosten</div><div class="k-val">${fmtN(b.cost_per_line * b.display_limit)}</div><div class="s">Units je Keyword (Top ${fmtN(b.display_limit)} × ${fmtN(b.cost_per_line)})</div></div>
    </div>
    <div class="card mt"><div class="card-b rl-filters">
      <label>Opportunity<select data-f="opp"><option value="">Alle</option>${opts([...new Set(D.events.map(e => e.opp).filter(Boolean))].map(x => [x, x]), RLF.opp)}</select></label>
      <label>Source Type<select data-f="type"><option value="">Alle</option>${opts(Object.entries(D.source_types), RLF.type)}</select></label>
      <label>Action Type<select data-f="action"><option value="">Alle</option>${opts(Object.entries(D.actions).filter(([k]) => D.events.some(e => e.action === k)), RLF.action)}</select></label>
      <label>Datum<select data-f="date"><option value="">Alle</option>${opts(dates.map(d => [d, fmtDate(d)]), RLF.date)}</select></label>
      <label class="grow">Suche<input type="search" data-f="q" value="${esc(RLF.q)}" placeholder="Keyword, Domain, Opportunity …"></label>
    </div></div>
    ${(() => { const live = Object.entries(wfAll()).filter(([, w]) => w.research_retry); return live.length ? `<div class="card mt"><div class="card-h"><div><h2>Research-Retries</h2><div class="hint">Live aus dem Workflow · der Agent protokolliert Ergebnisse anschließend als Log-Einträge</div></div></div><div class="card-b">${live.map(([id, w]) => { const rr = w.research_retry, [l, c] = RR_LABEL[rr.status] || [rr.status, ""]; return `<div class="row">${chip(l, c, true)}<a href="#opp-${esc(id)}">${esc(id)}</a><span class="s">angefordert ${fmtDateTime(rr.requested_at)} · ${esc((rr.components || []).join(", "))} · ${fmtN((rr.done || []).length)}/${fmtN((rr.components || []).length)}${rr.block_reason ? ` · ${esc(rr.block_reason)}` : ""}</span></div>`; }).join("")}</div></div>` : ""; })()}
    <div id="rl-list" class="mt"></div>`;
  const draw = () => { const xs = D.events.filter(rlMatch).slice().reverse(); $("#rl-list").innerHTML = xs.length ? xs.map(rlEvent).join("") : `<div class="card empty">Keine Einträge für diese Filter.</div>`; };
  view().querySelectorAll("[data-f]").forEach(el => el.addEventListener(el.tagName === "INPUT" ? "input" : "change", () => { RLF[el.dataset.f] = el.value; draw(); }));
  draw();
};
document.addEventListener("click", e => { const a = e.target.closest("[data-rl-opp]"); if (a) { Object.assign(RLF, { opp: a.dataset.rlOpp, type: "", action: "", date: a.dataset.rlDate || "", q: "" }); } });
/* ------------------------------------------------------------ Current Page Diagnosis & Ranking Protection (OPTIMIZE/MERGE) */
const TIER = { critical: ["Kritisch", "red"], high: ["Wichtig", "amber"], watch: ["Beobachten", "blue"], off_topic: ["Themenfremd", ""], release: ["Abgeben", ""] };
const ACT = { KEEP: "green", EDIT: "amber", "KEEP/EDIT": "amber", NEW: "blue", REMOVE: "red", REDUCE: "red" };
const actChip = a => chip(a, ACT[a] || "");
const itemList = xs => (xs || []).length ? `<ul class="list">${xs.map(x => typeof x === "string" ? `<li>${esc(x)}</li>` : `<li><b>${esc(x.item)}</b><div class="s">${esc(x.reason || "")}${x.evidence ? ` · Beleg: ${esc(x.evidence)}` : ""}${x.accepted_loss ? ` · In Kauf genommen: ${esc(x.accepted_loss)}` : ""}</div></li>`).join("")}</ul>` : `<span class="mini">–</span>`;
function protectionTable(rp, limit = 0) {
  const qs = limit ? rp.queries.filter(q => ["critical", "high"].includes(q.tier)).slice(0, limit) : rp.queries;
  return `<div class="tbl-wrap"><table><thead><tr><th>Query</th><th>Schutz</th><th class="num">Klicks</th><th class="num">Impr.</th><th class="num">Pos.</th><th class="num">Pos. 90d</th><th>Getragen von (bestehender Inhalt)</th></tr></thead><tbody>
    ${qs.map(q => `<tr><td class="q">${esc(q.query)}${q.source ? `<div class="s">${esc(q.source)}</div>` : ""}</td><td>${chip(...(TIER[q.tier] || [q.tier, ""]))}</td><td class="num">${q.clicks == null ? "–" : fmtN(q.clicks)}</td><td class="num">${q.impressions == null ? "–" : fmtN(q.impressions)}</td><td class="num">${fmtD(q.position)}</td><td class="num">${q.pos_90d == null ? "–" : fmtD(q.pos_90d)}</td>
      <td class="s">${(q.supported_by || []).map(h => `${esc(h.element)}: „${esc((h.text || "").slice(0, 60))}“${h.in === "Text" ? " (Text)" : ""}`).join("<br>") || (rp.content_mapped ? "nicht eindeutig zugeordnet" : "Seitenprofil fehlt")}</td></tr>`).join("") || `<tr><td colspan="7" class="empty">Keine Schutz-Queries</td></tr>`}</tbody></table></div>`;
}
/** Gate-1-Block: Warum überhaupt ändern? */
function diagnosisBrief(o) {
  const P = o.research?.P_diagnosis, rp = o.ranking_protection;
  if (!rp && !P) return "";
  const lr = rp?.loss_risk;
  return `<div class="g1-diag"><h4>Warum überhaupt ändern? – Current Page Diagnosis</h4>
    ${P ? `<div class="grid g2"><div><b>Funktioniert bereits gut</b>${ul(P.works_well)}</div><div><b>Aktuell schwach</b>${ul(P.weak)}</div><div><b>Fehlt</b>${ul(P.missing)}</div><div><b>Empfohlene Änderungen</b>${ul(P.recommended_changes)}<b>Expected SEO Benefit</b>${ul(P.expected_benefit)}</div></div>` : `<div class="notice">Diagnose im Dossier ausstehend – unten die automatisch ermittelte Ranking Protection.</div>`}
    ${rp ? `<div class="mt"><b>Ranking Protection</b> <span class="s">${fmtN(rp.strength.critical)} kritische · ${fmtN(rp.strength.high)} wichtige Queries · Seite ${esc({ strong: "stark", moderate: "moderat", weak: "schwach" }[rp.strength.level])} → ${esc(rp.strength.mode)}</span>${protectionTable(rp, 6)}</div>` : ""}
    ${lr ? `<div class="row mt"><b>Risk of Ranking Loss</b> ${riskChip(lr.level, "")}<span class="s">${esc(lr.reason)}</span></div>` : ""}
    ${P?.sensitive_changes?.length ? `<h4>Sensitive Changes</h4><div class="tbl-wrap"><table><thead><tr><th>Element</th><th>Current</th><th>Proposed</th><th>Reason</th><th>Ranking risk</th></tr></thead><tbody>${P.sensitive_changes.map(x => `<tr><td><b>${esc(x.element)}</b></td><td class="s">${esc(x.current)}</td><td>${esc(x.proposed)}</td><td class="s">${esc(x.reason)}</td><td class="s">${esc(x.ranking_risk)}</td></tr>`).join("")}</tbody></table></div>` : ""}
    ${P?.not_changed?.length ? `<div class="s mt">Unverändert: ${esc(P.not_changed.join(" · "))}. URL-/Canonical-/Redirect-Änderungen werden nie automatisch umgesetzt.</div>` : ""}</div>`;
}
/** Detail: KEEP / IMPROVE / ADD / REMOVE + Change Summary + vollständige Schutzliste (inkl. Companion) */
function diagnosisCard(o) {
  const P = o.research?.P_diagnosis, rp = o.ranking_protection;
  if (!rp && !P) return "";
  return `<div class="card" id="rs-diagnosis"><div class="card-h"><div><h2>Current Page Diagnosis &amp; Ranking Protection</h2><div class="hint">Preserve what works → fix what is weak → add what is missing. ${P?.principle ? esc(P.principle) : ""}</div></div>${rp ? riskChip(rp.loss_risk.level, "Ranking loss: ") : ""}</div><div class="card-b">
    ${P ? `<div class="grid g2"><div><h4>${actChip("KEEP")} unbedingt erhalten</h4>${itemList(P.keep)}</div><div><h4>${actChip("EDIT")} IMPROVE – verbessern</h4>${itemList(P.improve)}</div>
      <div><h4>${actChip("NEW")} ADD – fehlt aktuell</h4>${itemList(P.add)}</div><div><h4>${actChip("REMOVE")} REMOVE / REDUCE</h4>${itemList(P.remove)}</div></div>
      ${P.change_summary?.length ? `<h4>Change Summary</h4><div class="tbl-wrap"><table><thead><tr><th>Bereich</th><th>Aktion</th><th>Grund</th><th>SEO-Risiko</th></tr></thead><tbody>${P.change_summary.map(x => `<tr><td>${esc(x.area)}</td><td>${actChip(x.action)}</td><td class="s">${esc(x.reason)}</td><td>${esc(x.seo_risk)}</td></tr>`).join("")}</tbody></table></div>` : ""}` : ""}
    ${rp ? `<h4>Ranking Protection List · ${esc(rp.url)}</h4><div class="s">GSC Query × Page (16 Monate) + vorhandene Semrush-Rankings · Inhalte zugeordnet per Seitenprofil ${rp.profile_fetched ? fmtDateTime(rp.profile_fetched) : "– fehlt"} · Monitoring nach Veröffentlichung T+7/14/30/60/90 gegen diese Baseline</div>${protectionTable(rp)}
      ${(rp.companions || []).map(c => `<h4>Companion ${esc(c.url)}: eigene Rankings schützen</h4><div class="s">„Abgeben“ = Queries, die bewusst zur Zielseite wandern sollen; alle anderen bleiben geschützt.</div>${protectionTable({ ...c, content_mapped: false })}`).join("")}` : ""}
  </div></div>`;
}
/* ------------------------------------------------------------ Gate 1: vier Fragen + Kannibalisierung (eine Darstellung für Drawer und Detail) */
const RISK = { high: ["High", "red"], medium: ["Medium", "amber"], low: ["Low", "green"], unknown: ["Nicht bewertbar", ""] };
const riskChip = (r, pre = "Cannibalization: ") => { const [l, c] = RISK[r] || [r, ""]; return chip(pre + l, c, true); };
/** Companion-Maßnahmen: vom Agenten im Dossier geprüft (Vorrang) oder von der Engine erkannt */
const companionsOf = o => (o.research?.H_ia?.companion?.length ? o.research.H_ia.companion.map(c => ({ ...c, reviewed: true })) : (o.cannibalization?.companions || []));
/** Was genau wird gemacht: Agent-Empfehlung (kann vom Opportunity-Typ abweichen, z. B. DO NOT CREATE → OPTIMIZE) */
function agentPlan(o) {
  const c = o.cannibalization || {}, comp = companionsOf(o).filter(x => x.direction !== "release");
  return { action: c.action || o.type, url: c.action_url || o.existing_page || o.planned_url, changed: !!c.changed, decision: c.decision || o.type, companions: comp };
}
function pagePreview(o) {
  const F = o.research?.F_scope, G = o.research?.G_structure;
  if (!F) return `<div class="notice">Seiten-Scope noch nicht recherchiert – Research ausstehend. Gate 1 wäre nur als Override möglich.</div>`;
  const topics = F.topics || (G?.sections || []).map(s => s.h2);
  return `${F.page_purpose || F.core_message ? `<div class="callout"><b>Page Purpose:</b> ${esc(F.page_purpose || F.core_message)}</div>` : ""}
    <div class="grid g2 mt"><div><h4>Themen auf der Seite</h4>${ul(topics)}</div>
    <div><h4>Bewusst nicht enthalten</h4>${(F.not_on_page || []).length ? `<ul class="list">${F.not_on_page.map(x => `<li>${esc(x.topic)}</li>`).join("")}</ul>` : "–"}
      ${F.audience?.length ? `<h4>Zielgruppen</h4><div>${esc(F.audience.join(" · "))}</div>` : ""}
      ${F.delimitation?.length ? `<h4>Geplante Abgrenzung</h4><div>${F.delimitation.map(d => esc(d.service.replace(/ \(.*\)$/, ""))).join(" ≠ ")}</div>` : ""}</div></div>
    ${G ? `<h4>Rough Page Structure</h4><ol class="rs-outline compact"><li><span class="chip outline">H1</span> ${G.h1_action ? actChip(G.h1_action) : ""} ${esc(G.h1)}</li>${(G.sections || []).map(s => `<li><span class="chip outline">H2</span> ${s.action ? actChip(s.action) : ""} ${esc(s.h2)}${s.existing && s.existing !== "gleich" ? ` <span class="s">(bisher: ${esc(s.existing)})</span>` : ""}</li>`).join("")}</ol>` : ""}`;
}
function cannibalBlock(o, full = false) {
  const c = o.cannibalization; if (!c) return "";
  const comp = companionsOf(o), plan = agentPlan(o);
  const rows = (c.affected || []).filter(a => a.share >= 0.02 || full);
  return `<div class="row">${riskChip(c.risk)}${plan.changed ? chip(`Agent: ${o.type} → ${plan.decision}`, "amber", true) : chip(`Agent: ${c.decision}`, "outline")}</div>
    <div class="mt">${(c.why || []).map(w => `<div>${esc(w)}</div>`).join("")}</div>
    ${rows.length ? `<h4>Affected URLs</h4><div class="tbl-wrap"><table><thead><tr><th>URL</th><th class="num">Impr.</th><th class="num">Anteil</th><th class="num">Ø Pos.</th><th>Top-Queries</th></tr></thead><tbody>
      ${c.target_stats ? `<tr><td class="path"><b>${esc(c.target)}</b> <span class="s">Ziel</span></td><td class="num">${fmtN(c.target_stats.impressions)}</td><td class="num">${fmtPct(c.target_stats.share, 0)}</td><td class="num">${fmtD(c.target_stats.position)}</td><td class="s">${esc((c.target_stats.top_queries || []).join(" · "))}</td></tr>` : ""}
      ${rows.map(a => `<tr><td class="path">${esc(a.url)}${a.semantic_overlap ? ` <span class="s">· thematisch überlappend</span>` : ""}</td><td class="num">${fmtN(a.impressions)}</td><td class="num">${fmtPct(a.share, 0)}</td><td class="num">${fmtD(a.position)}</td><td class="s">${esc((a.top_queries || []).join(" · "))}</td></tr>`).join("")}</tbody></table></div>` : ""}
    ${(c.foreign_intents || []).length ? `<div class="s mt">Zielseite zieht auch: ${c.foreign_intents.map(f => `„${esc(f.cluster)}“ ${fmtN(f.impressions)} Impr. (${fmtPct(f.share, 0)})${f.other_url ? ` – gehört zu ${esc(f.other_url)}` : ""}`).join(" · ")}</div>` : ""}
    ${full && (c.split_queries || []).length ? `<h4>Queries mit mehreren rankenden URLs</h4>${c.split_queries.slice(0, 5).map(q => `<div class="s">„${esc(q.query)}“ (${fmtN(q.impressions)}): ${q.pages.map(p => `${esc(p.url)} Pos. ${fmtD(p.position)}`).join(" · ")}</div>`).join("")}` : ""}
    <div class="callout ${c.risk === "high" ? "red" : c.risk === "medium" ? "amber" : "green"} mt"><b>Agent Recommendation:</b> ${esc(c.recommendation)}</div>
    ${comp.length ? comp.map(x => `<div class="callout amber mt"><b>${x.direction === "release" ? "Abgrenzung" : "Companion Optimization required"}</b>${x.linked_opp ? ` · verknüpft mit <a href="#opp-${esc(x.linked_opp)}">${esc(x.linked_opp)}</a>` : ""}${x.reviewed ? ` ${chip("vom Agenten geprüft", "outline")}` : ` ${chip("von der Engine erkannt", "outline")}`}
      <div>Affected page: <span class="path">${esc(x.url)}</span></div><div class="s">Reason: ${esc(x.reason)}</div>${x.required_changes?.length ? `<div class="s">Required changes:</div>${ul(x.required_changes)}` : ""}</div>`).join("") : ""}
    <div class="mini mt">Basis: ${esc(c.basis?.source || "")} · ${fmtN(c.basis?.queries)} Queries · ${fmtN(c.basis?.impressions)} Impr.</div>`;
}
/** Gate-1-Entscheidungsvorlage: 1 Warum · 2 Was · 3 Was steht auf der Seite · 4 Was passiert mit anderen Seiten */
function gate1Brief(o) {
  const A = o.research?.A_decision, B = o.research?.B_demand, plan = agentPlan(o), f = S.d.funnel?.clusters.find(c => c.cluster === o.gsc_cluster);
  const pk = (o.semrush?.keywords || []).find(k => k.status === "ok"), ct = o.gsc?.cluster_total;
  const why = [ `Nachfrage: ${pk ? `„${esc(pk.keyword)}“ ${fmtN(pk.volume)}/Monat (KD ${fmtD(pk.kd, 0)})` : "Semrush nicht gemessen"}${ct ? ` · GSC-Cluster ${fmtN(ct.impressions)} Impr., ${fmtN(ct.clicks)} Klicks, Ø Pos. ${fmtD(ct.position)}` : ""}`,
    `Business Value: Fit ${esc(o.business_fit)}/10 · Priorität ${esc(o.priority)}${f ? ` · ${fmtN(leadsOf(f.engagement))} Leads im Cluster (GA4)` : ""}`,
    A?.why?.[0] ? esc(A.why[0]) : esc(o.why || "") ];
  return `<div class="g1-brief">
    <section><h3><span class="g1-n">1</span>Warum sollten wir das machen?</h3><ul class="list">${why.map(x => `<li>${x}</li>`).join("")}</ul></section>
    <section><h3><span class="g1-n">2</span>Was genau werden wir machen?</h3>
      <div class="row">${typeChip(plan.action)}<span class="path">${esc(plan.url || "–")}</span>${plan.companions.length ? chip(`+ ${plan.companions.length} Companion Optimization`, "amber") : ""}${plan.changed ? chip(`Abweichend von ${o.type}`, "amber", true) : ""}</div>
      <p>${esc(A?.summary || o.recommendation || "")}</p>
      ${plan.companions.length ? `<div class="s">Change Set: Hauptmaßnahme + ${plan.companions.map(c => esc(c.url)).join(", ")} – werden gemeinsam produziert und reviewt (je ein Drive-Dokument).</div>` : ""}
      ${["OPTIMIZE", "MERGE"].includes(plan.action) ? diagnosisBrief(o) : ""}</section>
    <section><h3><span class="g1-n">3</span>Was wird auf der Seite behandelt?</h3>${pagePreview(o)}</section>
    <section><h3><span class="g1-n">4</span>Was passiert mit unseren anderen Seiten?</h3>${cannibalBlock(o)}
      ${o.research?.H_ia?.recommended?.parent ? `<div class="s mt">Architecture: Parent ${esc(o.research.H_ia.recommended.parent.url)} · ${esc(o.research.H_ia.consolidation?.decision || "")}</div>` : ""}</section>
  </div>`;
}
/** Warnung vor Gate 1 bei Kannibalisierungsrisiko oder Abweichung von der Agent-Empfehlung – nie stillschweigend */
function gateDialog(o) {
  return new Promise(resolve => {
    const c = o.cannibalization, plan = agentPlan(o);
    const el = document.createElement("div"); el.className = "gate-dialog"; el.setAttribute("role", "alertdialog"); el.setAttribute("aria-modal", "true");
    el.innerHTML = `<div class="gd-box"><h2>Cannibalization Risk detected ${riskChip(c.risk, "")}</h2>
      <p>Diese ${o.type === "CREATE" ? "neue" : "überarbeitete"} Seite überschneidet sich mit:</p>
      <ul class="list">${[...(c.affected || []).filter(a => a.share >= 0.1), ...(c.foreign_intents || []).filter(f => f.other_url).map(f => ({ url: f.other_url, share: f.share, foreign: f.cluster }))].map(a => `<li>→ <span class="path">${esc(a.url)}</span> <span class="s">${a.foreign ? `Zielseite zieht ${fmtPct(a.share, 0)} des Clusters „${esc(a.foreign)}“` : `${fmtPct(a.share, 0)} der Impressionen`}</span></li>`).join("") || "<li>–</li>"}</ul>
      <h4>Warum?</h4>${(c.why || []).map(w => `<div class="s">${esc(w)}</div>`).join("")}
      <h4>Empfehlung des Agenten</h4><div>${typeChip(plan.action)} <span class="path">${esc(plan.url)}</span>${plan.companions.length ? ` + Companion: ${plan.companions.map(x => esc(x.url)).join(", ")}` : ""}</div><div class="s">${esc(c.recommendation)}</div>
      <div class="row mt"><button class="btn" data-g="cancel">Cancel</button><button class="btn primary" data-g="recommendation">Recommendation übernehmen</button><button class="btn danger" data-g="override">Trotzdem freigeben (${esc(o.type)}${plan.companions.length ? ", ohne Companion" : ""})</button></div></div>`;
    document.body.appendChild(el); lockScroll(true);
    const done = v => { el.remove(); lockScroll(!$("#wf-drawer")?.hidden); resolve(v); };
    el.addEventListener("click", e => { const b = e.target.closest("[data-g]"); if (b) done(b.dataset.g); else if (e.target === el) done("cancel"); });
    el.addEventListener("keydown", e => { if (e.key === "Escape") { e.stopPropagation(); done("cancel"); } });
    setTimeout(() => el.querySelector('[data-g="recommendation"]').focus(), 20);
  });
}
/* ------------------------------------------------------------ Local Opportunity Matrix (Service × Region, gleiche Kannibalisierungslogik) */
const LREC = { "CREATE CITY PAGE": "blue", "USE MAIN SERVICE PAGE": "green", "OPTIMIZE EXISTING PAGE": "amber", MONITOR: "", IGNORE: "" };
function localMatrix() {
  const l = S.d.local, svc = Object.fromEntries(l.services.map(s => [s.key, s])), loc = Object.fromEntries(l.locations.map(x => [x.key, x]));
  const rows = l.cells.map(c => ({ ...c, s: svc[c.service], l: loc[c.location], e: c.engine }));
  return table({ rows, pageSize: 50, search: ["service", "location"], sort: { key: "fit", dir: -1 },
    filters: [{ key: "rec", label: "Recommendation", options: Object.keys(LREC), match: (r, v) => r.e.recommendation === v }, { key: "can", label: "Cannibalization", options: ["High", "Medium", "Low"], match: (r, v) => r.e.cannibalization === v.toLowerCase() }],
    columns: [
      { key: "service", label: "Service", render: r => `<b>${esc(r.s.label)}</b><div class="s path">${esc(r.s.page)}</div>` },
      { key: "location", label: "Region", render: r => esc(r.l.label) },
      { key: "demand", label: "Demand", num: true, value: r => r.e.demand.gsc_impressions, tip: "GSC-Impressionen von Queries mit Leistung + Ort (16 Monate); Semrush-Lokalvolumen nur, wenn im Cache", render: r => `${r.e.demand.gsc_impressions ? `${fmtN(r.e.demand.gsc_impressions)} Impr.` : `<span class="s">keine GSC-Impr.</span>`}<div class="s">Semrush: ${r.e.demand.semrush_volume != null ? fmtN(r.e.demand.semrush_volume) : "nicht gemessen"}</div>` },
      { key: "rank", label: "Current Ranking", value: r => r.e.ranking?.position ?? 999, render: r => r.e.ranking ? `Pos. ${fmtD(r.e.ranking.position)}<div class="s path">${esc(r.e.ranking.url)}</div>` : `<span class="s">–</span>` },
      { key: "comp", label: "Competition", render: () => `<span class="s">nicht erhoben</span>` },
      { key: "fit", label: "Business Fit", num: true, value: r => r.e.business_fit, render: r => `${r.e.business_fit}/10` },
      { key: "can", label: "Cannibalization", value: r => ({ high: 3, medium: 2, low: 1 }[r.e.cannibalization] || 0), render: r => riskChip(r.e.cannibalization, "") },
      { key: "rec", label: "Recommendation", render: r => `${chip(r.e.recommendation, LREC[r.e.recommendation] || "", true)}<div class="s">${esc(r.e.why)}</div>${r.recommendation ? `<div class="s">Notiz: ${esc(r.recommendation)}</div>` : ""}` },
    ] });
}
/* ------------------------------------------------------------ WordPress: Gate 2 → Draft → QA → Gate 3 → Live (Schreibsperre im Runner: tools/wordpress.py guard) */
const WP_LABEL = { queued: ["WordPress Draft queued", "blue"], preparing: ["WordPress Draft wird vorbereitet", "blue"], draft_ready: ["WordPress Draft ready · QA läuft", "blue"],
  qa_failed: ["WordPress QA failed", "red"], qa_passed: ["Ready for Publish", "green"], blocked: ["WordPress blocked", "red"], publish_queued: ["Publish freigegeben · Agent startet", "blue"],
  publishing: ["Wird veröffentlicht …", "blue"], published: ["Published · Monitoring", "green"], publish_failed: ["Publish fehlgeschlagen", "red"], rolled_back: ["Zurückgerollt", "amber"] };
const QA_ST = { passed: ["Passed", "green"], failed: ["Failed", "red"], manual_review_required: ["Manual review required", "amber"] };
function wpLinks(wp, mode) {
  return (wp.documents || []).map(d => `<div class="row">${d.role === "companion" ? chip("Companion", "amber") : ""}
    ${d.preview_link ? `<a class="btn primary" href="${esc(d.preview_link)}" target="_blank" rel="noopener">WordPress Preview ↗</a>` : ""}
    ${mode === "OPTIMIZE" && d.original_link ? `<a class="btn" href="${esc(d.original_link)}" target="_blank" rel="noopener">Original Page ↗</a>` : ""}
    ${d.edit_link ? `<a class="btn" href="${esc(d.edit_link)}" target="_blank" rel="noopener">In Elementor bearbeiten ↗</a>` : ""}<span class="s path">${esc(d.url || "")}</span></div>`).join("") || `<span class="mini">Noch kein WordPress-Draft.</span>`;
}
function wpQa(qa) {
  if (!qa) return `<span class="mini">QA noch nicht gelaufen.</span>`;
  const row = (k, l) => { const x = qa[k] || {}, [t, c] = QA_ST[x.status] || [x.status || "–", ""]; return `<div class="k">${l}</div><div>${chip(t, c, true)}${(x.issues || []).length ? ul(x.issues) : ""}${x.note ? `<div class="s">${esc(x.note)}</div>` : ""}</div>`; };
  return `<div class="kv">${row("content", "Content QA")}${row("seo", "SEO QA")}${row("technical", "Technical/Layout QA")}${row("visual", "Visual QA")}</div>`;
}
function wpCounts(c) { return c ? `${fmtN(c.NEW)} NEW · ${fmtN(c.EDIT)} EDIT · ${fmtN(c.KEEP)} KEEP · ${fmtN(c.REMOVE)} REMOVE` : "–"; }
/** Drawer-Abschnitt für WordPress-Spalten; Gate 3 nur in „Ready for Publish“ */
function wpAction(o, w, col, canWrite) {
  const wp = w.wordpress || {}, [l, c] = WP_LABEL[wp.status] || ["WordPress: nicht gestartet", ""];
  const head = `<div class="wf-action"><h3>${esc(l)}</h3><div class="kv"><div class="k">Modus</div><div>${typeChip(wp.mode || o.type)} ${wp.mode === "OPTIMIZE" ? `<span class="s">Review-Version als separater Draft – die Live-Seite bleibt bis Gate 3 unverändert</span>` : `<span class="s">neue Elementor-Seite, Status draft</span>`}</div>
    <div class="k">Gate 2</div><div>${fmtDateTime(w.gate2?.at)}${w.gate2?.comment ? ` · „${esc(w.gate2.comment)}“` : ""}</div>
    ${wp.block_reason ? `<div class="k">Blockiert</div><div class="down"><code>${esc(wp.block_reason)}</code> ${esc(wp.block_detail || "")}</div>` : ""}</div>
    <div class="mt">${wpLinks(wp, wp.mode)}</div>`;
  if (col === "live") return `${head}<div class="kv mt"><div class="k">Veröffentlicht</div><div>${fmtDateTime(wp.published?.at)}</div><div class="k">Monitoring</div><div>T+7 · T+14 · T+30 · T+60 · T+90 (Ranking Protection + Kannibalisierung)</div></div></div>`;
  if (col !== "publish") return `${head}<h4>WordPress QA</h4>${wpQa(wp.qa)}${["blocked", "qa_failed"].includes(wp.status) ? `<div class="row mt"><button class="btn primary" data-act="wp_retry" ${canWrite ? "" : "disabled"}>WordPress-Draft erneut vorbereiten</button><span class="mini" data-msg></span></div>` : ""}</div>`;
  // Gate 3
  const rb = wp.rollback || {}, needRb = wp.mode === "OPTIMIZE", rbOk = !needRb || rb.status === "available";
  const visualManual = (wp.qa || {}).overall === "passed_manual_visual";
  return `${head}<div class="kv mt">
      <div class="k">Drive Change Set</div><div>${w.production?.doc_url ? `<a href="${esc(w.production.doc_url)}" target="_blank" rel="noopener">${esc(w.production.doc_title || "Entwurf")} ↗</a>` : "–"}</div>
      <div class="k">Changes</div><div><b>${esc(wpCounts(wp.change_counts))}</b></div>
      <div class="k">Ranking Risk</div><div>${o.ranking_protection ? riskChip(o.ranking_protection.loss_risk.level, "") : wp.mode === "CREATE" ? "– (neue Seite)" : "–"}</div>
      <div class="k">Cannibalization</div><div>${o.cannibalization ? riskChip(o.cannibalization.risk, "") : "–"}</div>
      <div class="k">WordPress QA</div><div>${chip(visualManual ? "Passed · Visual: manual review" : (wp.qa?.overall === "passed" ? "Passed" : wp.qa?.overall || "–"), wp.qa?.overall?.startsWith("passed") ? "green" : "red", true)}</div>
      <div class="k">Rollback</div><div>${needRb ? (rbOk ? chip("Pre-change snapshot gesichert", "green", true) + `<span class="s"> ${fmtDateTime((wp.snapshots || [])[0]?.taken_at)}${rb.secondary ? " · zusätzlich " + esc(rb.secondary) : ""}</span>` : chip("Rollback protection unavailable", "red", true) + ul(rb.why || [])) : `<span class="s">Neue Seite – Rollback = wieder auf Entwurf setzen</span>`}</div></div>
    <h4>Was wird beim Publish tatsächlich verändert?</h4>${ul(wp.publish_summary || [])}
    <details class="mt"><summary class="mini">WordPress QA im Detail</summary>${wpQa(wp.qa)}</details>
    ${visualManual ? `<label class="row mt"><input type="checkbox" id="wf-vis"> Ich habe die Vorschau auf Desktop, Tablet und Mobile geprüft (Visual QA ist automatisch nicht möglich)</label>` : ""}
    <label class="mini mt" for="wf-c3" style="display:block">Kommentar (optional)</label><textarea id="wf-c3"></textarea>
    <div class="row"><button class="btn primary" data-act="gate3" ${canWrite && rbOk ? "" : "disabled"}>Änderungen veröffentlichen</button><span class="mini" data-msg></span></div>
    <p class="s">Gate 3: Erst jetzt darf der Agent ${wp.mode === "OPTIMIZE" ? "die freigegebene Draft-Version in die Live-Seite übernehmen (URL, Slug, Canonical, Indexierung bleiben unverändert)" : "den Draft veröffentlichen"}. ${rbOk ? "" : "<b>Gesperrt: Rollback protection unavailable.</b>"}</p></div>`;
}
/* ------------------------------------------------------------ Research-Retry: fehlende Research gezielt nachholen (generisch für alle Opportunities) */
const COMP_ST = { complete: ["Complete", "green"], missing: ["Missing", "amber"], failed: ["Failed", "red"], stale: ["Veraltet", "amber"], blocked_budget: ["Budget-Reserve", ""], blocked: ["Blockiert", "red"], "n/a": ["n/a", ""] };
const RR_LABEL = { queued: ["Research retry queued", "blue"], running: ["Research running", "blue"], complete: ["Research complete", "green"], blocked: ["Research blocked", "red"] };
const rrOf = id => wfDoc(id)?.research_retry || null;
const rrActive = rr => rr && (rr.status === "queued" || rr.status === "running");
function researchActions(o, place = "banner") {
  const r = resStatus(o); if (!r?.components) return "";
  const plan = r.retry || { run: [], blocked: [] }, rr = rrOf(o.id), active = rrActive(rr);
  const missingLabels = r.components.filter(c => ["missing", "failed", "stale"].includes(c.status)).map(c => c.label);
  const comps = `<div class="rr-comps">${r.components.filter(c => c.status !== "n/a").map(c => `<span data-tip="${esc(c.why || "")}">${esc(c.label)}: ${chip(COMP_ST[c.status]?.[0] || c.status, COMP_ST[c.status]?.[1] || "")}</span>`).join("")}</div>`;
  let st = "";
  if (rr) {
    const [l, c] = RR_LABEL[rr.status] || [rr.status, ""], n = (rr.components || []).length, d = (rr.done || []).length;
    st = `<div class="rr-status">${chip(l, c, true)}${active ? ` <span>Research wird nachgeholt … ${rr.status === "running" ? `${d} von ${n} fehlenden Schritten abgeschlossen` : `(${n} Schritte: ${esc((rr.components || []).map(k => r.components.find(x => x.key === k)?.label || k).join(" · "))})`}</span>` : ""}
      ${rr.status === "blocked" ? `<div class="down s">Ursache: ${esc(rr.block_reason || "unbekannt")}</div>` : ""}${rr.status === "complete" && rr.finished_at ? `<span class="s"> · ${fmtDateTime(rr.finished_at)}</span>` : ""}
      ${(rr.blocked || []).length ? `<div class="s">Nicht ausgeführt: ${esc(rr.blocked.map(k => (r.components.find(x => x.key === k)?.label || k) + " – Budget-Reserve").join(" · "))}</div>` : ""}</div>`;
  }
  const canRun = plan.run.length > 0;
  const btnLabel = r.state === "not_started" ? "Research starten" : missingLabels.length ? "Fehlende Research nachholen" : "Research neu anstoßen";
  const btn = canRun ? `<button class="btn primary" data-rr="${esc(o.id)}" ${active ? "disabled" : ""}>${active ? "Research wird nachgeholt …" : esc(btnLabel)}</button>` : "";
  const blockedNote = plan.blocked.length ? `<div class="s">${plan.only_paid_missing ? esc(plan.explain) : `Semrush SERP weiterhin blockiert – Budget-Reserve (wird nicht ausgeführt, kostenlose Schritte laufen trotzdem).`}</div>` : "";
  return `<div class="rr ${place}" data-rr-opp="${esc(o.id)}" data-rr-place="${esc(place)}">${missingLabels.length ? `<div><b>Fehlend:</b> ${esc(missingLabels.join(" · "))}</div>` : ""}${comps}${st}
    ${canRun ? `<div class="row mt">${btn}<span class="mini" data-rr-msg="${esc(o.id)}"></span></div><div class="s">Holt nur fehlende/fehlgeschlagene/veraltete Schritte nach (${esc(plan.run.map(k => r.components.find(x => x.key === k)?.label || k).join(" · "))}); vorhandene Research (${esc(plan.reuse.map(k => r.components.find(x => x.key === k)?.label || k).join(" · ") || "–")}) wird wiederverwendet. Dasselbe Dossier wird fortgeschrieben und versioniert.</div>` : ""}
    ${blockedNote}</div>`;
}
/** Retry anstoßen: Auftrag am bestehenden Workflow-Eintrag (kein neuer Datensatz), Protokoll, Agentenlauf */
async function researchRetry(id) {
  const msg = $(`[data-rr-msg="${CSS.escape(id)}"]`), say = t => { document.querySelectorAll(`[data-rr-msg="${CSS.escape(id)}"]`).forEach(m => m.textContent = t); };
  const o = S.d.opportunities.find(x => x.id === id), r = resStatus(o), plan = r?.retry;
  if (!(DB.state === "ready" && DB.canWrite)) return say("Speichern ist in dieser Ansicht nicht möglich.");
  if (!plan?.run?.length) return say(plan?.explain || "Keine nachholbaren Schritte.");
  const cur = WF.items[id];
  if (rrActive(cur?.research_retry)) return say("Research wird bereits nachgeholt.");
  document.querySelectorAll(`[data-rr="${CSS.escape(id)}"]`).forEach(b => { b.disabled = true; b.textContent = "Research wird nachgeholt …"; });
  const now = new Date().toISOString();
  const rr = { status: "queued", requested_at: now, components: plan.run, blocked: plan.blocked, done: [], attempt: (cur?.research_retry?.attempt || 0) + 1, research_version: r.version ?? null };
  try {
    const ref = DB.ns.collection("workflow").doc(id);
    if (cur) await ref.update({ research_retry: rr }); else await ref.set({ opp_id: id, title: o.name, client: S.client, schema: 1, gate1: { status: "pending" }, production: { status: "not_started" }, review: { status: "not_started" }, research_retry: rr });
    const eid = `${S.client}--${id}--rr--${Date.now()}`.replace(/[^A-Za-z0-9_.~:@+-]/g, "-");
    await DB.ns.collection("decisions").doc(eid).set({ schema: 1, client: S.client, item_id: id, item_title: o.name, gate: 0, decision: "research_retry", comment: `Nachholen: ${plan.run.join(", ")}${plan.blocked.length ? ` · nicht ausgeführt (Budget): ${plan.blocked.join(", ")}` : ""}`, decided_at: now, agent_status: "pending", agent_processed_at: null, agent_note: null });
    say("Research retry queued.");
    await wfTrigger(id, "research_retry"); say("Research retry queued. " + WF.trigger.note);
  } catch (e) { say(`Nicht gespeichert (${e.code || "error"}): ${e.message || ""}`); document.querySelectorAll(`[data-rr="${CSS.escape(id)}"]`).forEach(b => { b.disabled = false; b.textContent = "Fehlende Research nachholen"; }); }
}
document.addEventListener("click", e => { const b = e.target.closest("[data-rr]"); if (b && !b.disabled) { e.preventDefault(); researchRetry(b.dataset.rr); } });
/* ------------------------------------------------------------ Research-/Strategy-Stufe (A–J, vor Gate 1) */
const RES_READY = ["complete", "complete_with_limits"];
const RES_COLOR = { complete: "green", complete_with_limits: "blue", incomplete: "amber", not_started: "" };
const resStatus = o => o?.research_status || (["CREATE", "OPTIMIZE", "MERGE"].includes(o?.type) ? { state: "not_started", label: "Research not started", missing: [], limits: [] } : null);
const resChip = o => { const r = resStatus(o); return r ? chip(r.label, RES_COLOR[r.state], true) : ""; };
const REL = { business_competitor: ["Wettbewerber", "red"], platform: ["Plattform", "amber"], software: ["Software", ""], guide: ["Ratgeber", ""], directory: ["Verzeichnis", ""], partner: ["Partner", "green"], own: ["Eigene Seite", "blue"], other: ["Sonstiges", ""] };
const ROLE = { primary: ["Primary", "blue"], secondary: ["Secondary", "green"], supporting: ["Supporting", ""], do_not_target: ["Do not target", "red"] };
const ul = a => a?.length ? `<ul class="list">${a.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : `<span class="mini">–</span>`;
let RS_OPP = null; // Opportunity, deren Dossier gerade gerendert wird (für belegte Erkenntnisse je Abschnitt)
const rsCard = (key, title, body, hint = "") => { const fs = RS_OPP ? oppFindings(RS_OPP, key) : [];
  return `<section class="card rs" id="rs-${key}"><div class="card-h"><div><h2>${esc(title)}</h2>${hint ? `<div class="hint">${esc(hint)}</div>` : ""}</div></div><div class="card-b">${body}${fs.length ? `<div class="rs-ev"><h4>Belegt durch</h4>${fs.map(findingRefs).join("")}</div>` : ""}</div></section>`; };
const RS_TITLES = [["A", "Executive Decision"], ["B", "Search Demand"], ["C", "Live SERP"], ["D", "Competitor Insights"], ["E", "Content Gap"], ["F", "Recommended Page Scope"], ["G", "Proposed Structure"], ["H", "Information Architecture"], ["I", "How We Can Win"], ["J", "Risks / Unknowns"]];
/** Statuszeile über dem Dossier – fehlende Research wird nie still übergangen */
function researchBanner(o) {
  const r = resStatus(o); if (!r) return "";
  const w = wfDoc(o.id), legacy = w?.gate1?.status === "approved" && !wfStrategy(w).ok && w.production?.status !== "draft_ready";
  const cls = { complete: "green", complete_with_limits: "", incomplete: "amber", not_started: "amber" }[r.state];
  return `<div class="callout ${cls} rs-banner"><div class="row">${resChip(o)}${r.version ? `<span class="mini">Research v${esc(r.version)} · ${fmtDateTime(r.updated)} · Semrush-Units ${fmtN(r.units || 0)} · SERP ${esc({ validated: "validiert", indicative: "indikativ", missing: "fehlt" }[r.serp_quality] || "–")}</span>` : ""}</div>
    ${r.limits?.length ? `<div class="mt"><b>Grenzen</b>${ul(r.limits)}</div>` : ""}
    ${r.state === "incomplete" || r.state === "not_started" ? `<div class="mt">${researchActions(o)}<div class="s mt">Ohne vollständige Research startet keine Produktion. Gate 1 ist sonst nur mit ausdrücklichem Override möglich.</div></div>` : r.components ? `<div class="mt">${researchActions(o)}</div>` : ""}
    ${o.research?.status?.optional_validation ? `<div class="s mt">Optional: ${esc(o.research.status.optional_validation)}</div>` : ""}
    ${legacy ? `<div class="mt"><b>Gate 1 vom ${fmtDateTime(w.gate1.at)}</b> wurde vor der Research-Stufe erteilt und gilt nicht als Strategie-Freigabe. Bitte Strategie neu freigeben.</div>` : ""}</div>`;
}
/** SERP Validation: Source A Semrush SERP × Source B Independent Web Research (keine zweite Google-SERP) */
function serpValidation(o) {
  const v = o.research_status?.serp_validation; if (!v) return "";
  const sc = { confirmed: "green", pending_budget_hold: "amber", pending_run: "blue", pending: "amber" }[v.semrush.status] || "";
  const ag = { high: ["High", "green"], medium: ["Medium", "blue"], low: ["Low", "red"], "n/a": ["Nicht bewertbar", ""] }[v.cross.agreement] || [v.cross.agreement, ""];
  const w = v.independent_web || {};
  const list = a => a?.length ? esc(a.join(", ")) : "–";
  return `<div class="rs-val"><h4>SERP Validation</h4><div class="kv">
    <div class="k">Semrush SERP</div><div>${chip(v.semrush.label, sc, true)} <span class="s">${esc(v.semrush.why || "")}</span></div>
    <div class="k">Independent Web Research</div><div>${chip(w.label || "Pending", w.status === "completed" ? "green" : "amber", true)} ${w.date ? `<span class="s">${fmtDate(w.date)} · ${esc((w.keywords || []).join(", "))}</span>` : ""}${w.tool ? `<div class="s">${esc(w.tool)} – Discovery-/Validierungsquelle, keine Google.de-SERP, keine Positionen</div>` : ""}</div>
    <div class="k">Cross-source agreement</div><div>${chip(ag[0], ag[1], true)} <span class="s">${esc(v.cross.reason || "")}</span>
      ${v.cross.agreement !== "n/a" ? `<div class="s">In beiden: ${list(v.cross.both)} · nur Semrush: ${list(v.cross.semrush_only)} · nur Web Research: ${list(v.cross.web_only)}</div>` : ""}
      ${(v.cross.flags || []).map(f => `<div class="down s">⚑ ${esc(f)}</div>`).join("")}</div></div></div>`;
}
function researchView(o) {
  const R = o.research;
  if (!R) return `<div class="card"><div class="card-h"><h2>Research & Strategy (A–J)</h2></div><div class="card-b"><div class="rs-toc">${RS_TITLES.map(([k, t]) => `<span class="chip">${k} · ${esc(t)}</span>`).join("")}</div><p class="mini mt">Noch kein Dossier. Der Agent erstellt es in der Kostenreihenfolge Cache → GSC → Website → vorhandene Semrush-Daten → Web/SERP → Semrush nur nach Freigabe.</p></div></div>`;
  RS_OPP = o.id;
  const A = R.A_decision || {}, B = R.B_demand || {}, C = R.C_serp || {}, E = R.E_gap || {}, F = R.F_scope || {}, G = R.G_structure || {}, H = R.H_ia || {};
  const pos = v => v === null || v === undefined ? "–" : fmtD(v);
  const out = [];
  out.push(rsCard("A", "A · Executive Decision", `<div class="row">${typeChip(A.decision)}${A.confidence ? confChip(A.confidence) : ""}${A.target_url ? `<span class="mini path">${esc(A.target_url)}</span>` : ""}</div>
    <p>${esc(A.summary)}</p>${ul(A.why)}
    ${A.alternatives?.length ? `<h4>Geprüfte Alternativen</h4><div class="tbl-wrap"><table><thead><tr><th>Option</th><th>Ergebnis</th><th>Begründung</th></tr></thead><tbody>${A.alternatives.map(x => `<tr><td>${esc(x.option)}</td><td>${esc(x.verdict)}</td><td class="s">${esc(x.reason)}</td></tr>`).join("")}</tbody></table></div>` : ""}
    <div class="callout mt"><b>Gate-1-Frage:</b> ${esc(A.gate1_question)}</div>`));
  out.push(rsCard("B", "B · Search Demand", `<div class="tbl-wrap"><table><thead><tr><th>Keyword</th><th>Rolle</th><th class="num">Vol.</th><th class="num">KD</th><th class="num">CPC €</th><th class="num">GSC Impr.</th><th class="num">Pos.</th><th class="num">Pos. 90d</th><th>Intent</th></tr></thead><tbody>
    ${(B.keywords || []).map(k => `<tr><td class="q">${esc(k.keyword)}</td><td>${chip(...(ROLE[k.role] || [k.role, ""]))}</td><td class="num">${k.volume === null || k.volume === undefined ? "–" : fmtN(k.volume)}</td><td class="num">${k.kd === null || k.kd === undefined ? "–" : fmtD(k.kd, 0)}</td><td class="num">${k.cpc === null || k.cpc === undefined ? "–" : fmtD(k.cpc, 2)}</td><td class="num">${k.gsc_impr === null || k.gsc_impr === undefined ? "–" : fmtN(k.gsc_impr)}</td><td class="num">${pos(k.gsc_pos)}</td><td class="num">${pos(k.gsc_pos_90d)}</td><td class="s">${esc(k.intent)}</td></tr>`).join("")}</tbody></table></div>
    ${B.cluster ? `<div class="mini mt">Cluster: ${fmtN(B.cluster.queries)} Queries · ${fmtN(B.cluster.impressions)} Impr. · ${fmtN(B.cluster.clicks)} Klicks · Ø Pos. ${fmtD(B.cluster.avg_position)}${B.ga4 ? ` · ${esc(B.ga4)}` : ""}</div>` : ""}${ul(B.notes)}`, "Semrush-Cache (DE) + GSC 16 Monate · Volumen „–“ = nicht gemessen, nicht „keine Nachfrage“"));
  const sp = o.research_status?.serp_plan;
  const compTable = (rows, withPos) => rows?.length ? `<div class="tbl-wrap"><table><thead><tr><th>Domain</th>${withPos ? "<th class=\"num\">Pos.</th><th>Keyword</th>" : ""}<th>Seitentyp</th><th>Einordnung</th><th>Region</th><th>Notiz</th></tr></thead><tbody>
    ${rows.map(x => `<tr><td>${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.domain)}</a>` : esc(x.domain)}</td>${withPos ? `<td class="num">${esc(x.position)}</td><td class="s">${esc(x.keyword)}</td>` : ""}<td class="s">${esc(x.page_type || "–")}</td><td>${chip(...(REL[x.relevance] || [x.relevance, ""]))}</td><td class="s">${esc(x.region || "–")}</td><td class="s">${esc(x.note || "")}${x.found_via ? `<div>Gefunden: ${esc(x.found_via)}</div>` : ""}</td></tr>`).join("")}</tbody></table></div>` : "";
  out.push(rsCard("C", "C · Live SERP", `<div class="callout ${C.quality === "validated" ? "green" : "amber"}"><b>Quelle:</b> ${esc(C.source)} · ${chip(C.quality === "validated" ? "Validiert (Semrush)" : C.quality === "indicative" ? "Indikativ" : "Fehlt", C.quality === "validated" ? "green" : "amber")}${C.quality_note ? `<div class="s">${esc(C.quality_note)}</div>` : ""}</div>
    <p><b>Intent:</b> ${esc(C.intent_verdict)}</p>${C.own_position ? `<p class="s">Eigene Position: ${esc(C.own_position)}</p>` : ""}
    ${serpValidation(o)}
    <h4>SERP competitors · von Semrush als rankend bestätigt</h4>${compTable(C.serp_competitors, true) || `<div class="notice">Noch keine echte SERP. ${esc(C.serp_status || "")}</div>`}
    ${sp ? `<div class="kv mt"><div class="k">SERP-Plan</div><div>${sp.items.map(i => `<div>${esc(i.keyword)} · ${esc({ query: "Abfrage", cache: "aus Cache", skip_similar: "ähnlich → übersprungen" }[i.action] || i.action)}${i.units ? ` · ${fmtN(i.units)} Units` : ""}</div>`).join("") || "–"}<div class="s">Semrush Organic Results · ${esc(sp.database)} · Top ${esc(sp.display_limit)} · 10 Units je Ergebniszeile</div></div>
      <div class="k">Budget</div><div>${chip({ run: "Wird ausgeführt", budget_hold: "Budget-Reserve – wartet", none: "Cache aktuell", approval_required: "Freigabe nötig" }[sp.verdict] || sp.verdict, { run: "green", budget_hold: "amber", none: "green", approval_required: "amber" }[sp.verdict] || "")} <span class="s">${esc(sp.why)} · Stand ${fmtDate(sp.balance_checked_at)}</span></div></div>` : ""}
    <h4>Research competitors · Independent Web Research (gefunden, keine Positionen)</h4>${compTable(C.research_competitors, false) || `<span class="mini">–</span>`}`));
  out.push(rsCard("D", "D · Competitor Insights", `${R.D_pattern ? `<div class="callout">${esc(R.D_pattern)}</div>` : ""}<div class="mt">${(R.D_competitors || []).map(c => `<details class="rs-comp"><summary><b>${esc(c.domain)}</b> <span class="s">${esc(c.location || "")} · ${esc(c.h1 || "")}</span></summary>
    <div class="kv"><div class="k">Positionierung</div><div>${esc(c.positioning)}</div><div class="k">Themen</div><div>${esc((c.topics || []).join(" · "))}</div><div class="k">Zielgruppe</div><div>${esc((c.audience || []).join(" · "))}</div>
    <div class="k">FAQ</div><div>${esc(c.faq || "–")}</div><div class="k">Trust / Proof</div><div>${esc(c.trust || "–")}</div><div class="k">Lokaler Fokus</div><div>${esc(c.local || "–")}</div><div class="k">Conversion</div><div>${esc(c.conversion || "–")}</div></div>
    <div class="callout mt">${esc(c.takeaway)}</div></details>`).join("") || `<span class="mini">–</span>`}</div>`, (C.serp_competitors || []).length ? "SERP competitors + Research competitors · keine Textübernahme, kein Wortzahl-Vergleich" : "Research competitors (nicht als rankend bestätigt) · keine Textübernahme, kein Wortzahl-Vergleich"));
  out.push(rsCard("E", "E · Content Gap", `<div class="grid g2"><div><h4>Competitors cover</h4>${ul(E.competitors_cover)}</div><div><h4>We already cover</h4>${ul(E.we_cover)}</div><div><h4>We are missing</h4>${ul(E.we_miss)}</div><div><h4>Opportunity to outperform</h4>${ul(E.outperform)}</div></div>`, "Nur belegte Business-Assets (Business-Profil) – keine erfundenen Vorteile"));
  const kq = (F.key_questions || []).map(q => typeof q === "string" ? { group: "", questions: [q] } : q);
  const svc = (F.service_info || []).map(x => typeof x === "string" ? { text: x } : x);
  out.push(rsCard("F", "F · Recommended Page Scope", `<div class="callout"><b>Kernbotschaft:</b> ${esc(F.core_message)}</div>
    <div class="kv mt"><div class="k">Search Intent</div><div>${esc(F.search_intent)}</div><div class="k">Zielgruppe</div><div>${esc((F.audience || []).join(" · "))}</div><div class="k">Conversion-Ziel</div><div>${esc(F.conversion_goal)}</div></div>
    <h4>Fachliche Fragen, die die Seite beantworten muss</h4><div class="grid g2">${kq.map(g => `<div>${g.group ? `<b>${esc(g.group)}</b>` : ""}${ul(g.questions)}</div>`).join("")}</div>
    <div class="grid g2 mt"><div><h4>Notwendige Leistungsinformationen</h4><ul class="list">${svc.map(x => `<li>${esc(x.text)}${x.evidence ? `<div class="s">Beleg: ${esc(x.evidence)}</div>` : ""}</li>`).join("")}</ul></div><div><h4>Trust / Proof</h4>${ul(F.trust_proof)}</div></div>
    ${F.delimitation?.length ? `<h4>Abgrenzung</h4><div class="tbl-wrap"><table><thead><tr><th>Leistung</th><th>Beantwortet</th><th>Zeitpunkt</th><th>Ergebnis</th><th>Seite</th></tr></thead><tbody>${F.delimitation.map(x => `<tr><td><b>${esc(x.service)}</b></td><td>${esc(x.question)}</td><td class="s">${esc(x.timing)}</td><td class="s">${esc(x.output)}</td><td class="s path">${esc(x.page)}</td></tr>`).join("")}</tbody></table></div>` : ""}
    <h4>Bewusst NICHT auf dieser Seite</h4>${(F.not_on_page || []).length ? `<ul class="list">${F.not_on_page.map(x => `<li><b>${esc(x.topic)}</b><div class="s">${esc(x.reason)} → ${esc(x.goes_to)}</div></li>`).join("")}</ul>` : "–"}`));
  out.push(rsCard("G", "G · Proposed Structure", `<div class="kv"><div class="k">Title (Vorschlag)</div><div>${esc(G.title_proposal || "–")}</div><div class="k">Meta</div><div>${esc(G.meta_note || "–")}</div></div>
    <ol class="rs-outline"><li class="h1"><span class="chip outline">H1</span> ${G.h1_action ? actChip(G.h1_action) : ""} ${esc(G.h1)}</li>${(G.sections || []).map(x => `<li><span class="chip outline">H2</span> ${x.action ? actChip(x.action) : ""} <b>${esc(x.h2)}</b>${x.existing && x.existing !== "gleich" ? ` <span class="s">(bisher: ${esc(x.existing)})</span>` : ""}<div class="s">${esc(x.purpose)}${x.covers?.length ? ` · beantwortet: ${esc(x.covers.join(", "))}` : ""}</div>${x.h3?.length ? `<ul>${x.h3.map(h => `<li><span class="chip outline">H3</span> ${esc(h)}</li>`).join("")}</ul>` : ""}</li>`).join("")}</ol>
    ${G.scope_check ? `<div class="callout mt"><b>Abgleich mit Scope F:</b> ${esc(G.scope_check)}</div>` : ""}${G.derivation ? `<p class="s">Herleitung: ${esc(G.derivation)}</p>` : ""}`, "Grobgliederung vor Gate 1 – kein Text, keine Formulierungen"));
  const ko = H.keyword_ownership || {}, Hc = H.current || H, Hr = H.recommended || {};
  const iaBlock = (x, rec) => `<div class="kv"><div class="k">Parent</div><div><span class="path">${esc(x.parent?.url)}</span> <span class="s">${esc(x.parent?.label || "")}${x.parent?.note ? " · " + esc(x.parent.note) : ""}</span></div>
    <div class="k">Target</div><div><b class="path">${esc(x.target?.url)}</b> <span class="s">${esc(x.target?.label || "")}</span></div>
    <div class="k">Children</div><div>${(x.children || []).length ? x.children.map(c => `<span class="path">${esc(c.url || c)}</span>`).join(", ") : "keine"}${x.children_note ? `<div class="s">${esc(x.children_note)}</div>` : ""}</div>
    <div class="k">Siblings</div><div>${(x.siblings || []).map(s => `<div><span class="path">${esc(s.url)}</span> <span class="s">${esc(s.label)} – ${esc(s.relation)}</span></div>`).join("")}</div>
    ${!rec && x.inbound_links ? `<div class="k">Interne Links rein / raus</div><div class="s">${x.inbound_links.map(l => `${esc(l.from)} „${esc(l.anchor)}“`).join(", ")} · ${esc(x.outbound_links || "")}</div>` : ""}</div>`;
  const hub = Hr.hub_assessment, cons = H.consolidation;
  out.push(rsCard("H", "H · Information Architecture", `<div class="grid g2"><div><h4>Current Architecture</h4>${iaBlock(Hc, false)}</div><div><h4>Recommended Architecture</h4>${H.recommended ? iaBlock(Hr, true) : "–"}</div></div>
    ${hub ? `<div class="callout mt"><b>Hub-Prüfung: ${esc(hub.option)}</b><div>${esc(hub.verdict)}</div>${ul(hub.reasoning)}</div>` : ""}
    ${Hr.child_candidates?.length ? `<h4>Geprüfte Child-Kandidaten (nur bei eigenständigem Intent)</h4><div class="tbl-wrap"><table><thead><tr><th>Thema</th><th>Intent</th><th>Ergebnis</th></tr></thead><tbody>${Hr.child_candidates.map(c => `<tr><td>${esc(c.topic)}</td><td class="s">${esc(c.intent)}</td><td class="s">${esc(c.verdict)}</td></tr>`).join("")}</tbody></table></div>` : ""}
    ${cons ? `<div class="callout mt"><b>Konsolidierung: ${esc(cons.decision)}</b>${ul(cons.reasoning)}${cons.revisit_if ? `<div class="s">Neu prüfen, wenn: ${esc(cons.revisit_if)}</div>` : ""}</div>` : ""}
    <div class="row mt"><b>Entscheidung</b> ${typeChip(H.decision)}</div>
    <div class="grid g2 mt"><div><h4>Keyword Ownership (diese Seite)</h4>${ul(ko.owns)}</div><div><h4>Do not target here</h4>${(ko.do_not_target || []).length ? `<ul class="list">${ko.do_not_target.map(x => `<li><b>${esc(x.keyword)}</b><div class="s">${esc(x.reason)} → ${esc(x.owner)}</div></li>`).join("")}</ul>` : "–"}</div></div>
    <h4>Interne Verlinkung (Empfehlung)</h4><div class="tbl-wrap"><table><thead><tr><th>Von</th><th>Nach</th><th>Anker</th><th>Status</th></tr></thead><tbody>${(H.internal_links || []).map(l => `<tr><td class="s path">${esc(l.from)}</td><td class="s path">${esc(l.to)}</td><td>${esc(l.anchor)}</td><td>${chip(l.type === "exists" ? "besteht" : l.type === "add" ? "ergänzen" : l.type, l.type === "exists" ? "green" : l.type === "add" ? "blue" : "")}</td></tr>`).join("")}</tbody></table></div>
    <div class="callout ${H.cannibalization?.risk === "low" ? "green" : "amber"} mt"><b>Kannibalisierung: ${esc({ low: "gering", medium: "mittel", high: "hoch" }[H.cannibalization?.risk] || H.cannibalization?.risk || "–")}</b><div class="s">${esc(H.cannibalization?.evidence || "")}</div>${H.cannibalization?.watch ? `<div class="s">Beobachten: ${esc(H.cannibalization.watch)}</div>` : ""}</div>`));
  out.push(rsCard("I", "I · How We Can Win", ul(R.I_win)));
  const JT = { unknown: ["Unknown", "blue"], risk: ["Risk", "amber"], resolved: ["Geklärt", "green"] };
  out.push(rsCard("J", "J · Risks / Unknowns", (R.J_risks || []).length ? `<ul class="list">${R.J_risks.map(x => `<li>${chip(...(JT[x.type] || JT.risk))} ${esc(x.item)}<div class="s">→ ${esc(x.mitigation)}</div></li>`).join("")}</ul>` : "–"));
  return `<nav class="rs-toc" aria-label="Research-Abschnitte">${RS_TITLES.map(([k, t]) => `<a class="chip" href="#opp-${esc(o.id)}" data-rs="${k}">${k} · ${esc(t)}</a>`).join("")}</nav>${out.join("")}`;
}
function gate1Card(o, compact = false) {
  const r = resStatus(o); if (!r) return "";
  const w = wfDoc(o.id), col = wfCol(w), [l, c] = wfLabel(w);
  if (compact) return `<div class="row">${chip(l, c, true)}${col === "review" ? `<button class="btn primary" data-gate1="${esc(o.id)}">Zur Gate-1-Freigabe</button>` : ""}</div>`;
  return `<div class="card rs-gate"><div class="card-h"><div><h2>Gate 1 – Strategie freigeben</h2><div class="hint">Freigabe der Strategie A–J. Danach erstellt Claude den Entwurf als Google Doc. Keine Website-Änderung.</div></div>${chip(l, c, true)}</div>
    <div class="card-b"><div class="row">${resChip(o)}${col === "review" ? `<button class="btn primary" data-gate1="${esc(o.id)}">${RES_READY.includes(r.state) ? "Gate 1 – Strategie freigeben" : "Zur Freigabe (Override nötig)"}</button>` : `<a class="btn" href="#approvals" data-gate1="${esc(o.id)}">Im Workflow öffnen</a>`}</div></div></div>`;
}
/* ------------------------------------------------------------ Workflow-Board (Gate 1 → Drive-Entwurf → Review → Gate 2) */
/* SSOT: db-Collection "workflow" (ein Dokument je Opportunity). Noel schreibt Entscheidungen, der Agent schreibt den Produktionsstatus.
   Eine Aktion speichert zuerst persistent und stößt danach – falls verfügbar – den Agentenlauf über den Konnektor
   "Claude Code Remote" (fire_trigger) an. Keine Aktion verändert Website oder WordPress. */
const WF_COLS = [
  ["review", "Zur Prüfung", "Gate 1 steht aus"],
  ["production", "Freigegeben / Produktion", "Gate 1 erteilt · Claude produziert"],
  ["draft", "Entwurf fertig / Review", "Dein Review"],
  ["wordpress", "WordPress-Draft & QA", "Gate 2 erteilt · Draft in WordPress"],
  ["publish", "Ready for Publish", "Gate 3 · deine Sichtprüfung"],
  ["live", "Live / Monitoring", "veröffentlicht · T+7…T+90"],
];
const WF = { items: {}, live: false, trigger: { state: "unknown", note: "" } };
const BLOCK_TEXT = { workflow_state_unavailable: "Workflow-State aus dem Artifact nicht lesbar", repository_unavailable: "Repository im Agentenlauf nicht verfügbar", wrong_branch: "Falscher Branch im Agentenlauf", repository_outdated: "Repository nicht aktuell", runbook_missing: "Ablaufbeschreibung fehlt", business_profile_missing: "Business-Profil fehlt", style_guide_missing: "Content-Style-Guide fehlt", drive_tool_unavailable: "Google Drive ist im Agentenlauf nicht verfügbar (Konnektor nicht an der Routine hinterlegt)", drive_folder_unavailable: "Kein Schreibzugriff auf den Ordner „Claude Landingpages“", production_error: "Fehler während der Produktion" };
/** Live-db hat Vorrang; ohne Live-Verbindung (lokal, offline) gilt der vom Agenten geschriebene Git-Spiegel */
const wfAll = () => WF.live ? WF.items : { ...Object.fromEntries((S.d.workflow?.items || []).map(x => [x.id, x])), ...WF.items };
const wfDoc = id => wfAll()[id] || null;
/** Gate 1 = Strategie-Freigabe: gilt nur, wenn sie sich auf die aktuelle Research-Version bezieht (oder bewusster Override). Spiegel von tools/research.py strategy_ok */
function wfStrategy(w) {
  if (!w || w.test) return { ok: true, why: "test" };
  if (w.gate1?.research_override) return { ok: true, why: "override" };
  const r = resStatus(S.d.opportunities.find(x => x.id === (w.opp_id || w.id)));
  if (!r) return { ok: true, why: "no_stage" };
  if (!RES_READY.includes(r.state)) return { ok: false, why: r.state === "not_started" ? "research_missing" : "research_incomplete" };
  if (w.gate1?.research_version !== r.version) return { ok: false, why: "strategy_not_approved" };
  return { ok: true, why: "ok" };
}
const wfLegacy = w => w?.gate1?.status === "approved" && !wfStrategy(w).ok && w.production?.status !== "draft_ready" && w.gate2?.status !== "approved" && w.review?.status !== "revision_requested";
let WF_PENDING_OPEN = null;
function wfCol(w) {
  if (!w || w.gate1?.status !== "approved") return "review";
  if (w.gate2?.status === "approved") { const s = w.wordpress?.status; return s === "published" || s === "rolled_back" ? "live" : ["qa_passed", "publish_queued", "publishing", "publish_failed"].includes(s) ? "publish" : "wordpress"; }
  if (wfLegacy(w)) return "review";
  if (w.review?.status === "revision_requested") return "production";
  if (w.production?.status === "draft_ready") return "draft";
  return "production";
}
function wfLabel(w) {
  const c = wfCol(w);
  if (c === "review") return wfLegacy(w) || w?.gate1?.superseded?.length ? ["Strategie-Freigabe ausstehend", "amber"] : ["Zur Prüfung", ""];
  if (["wordpress", "publish", "live"].includes(c)) return WP_LABEL[w.wordpress?.status] || ["Gate 2 erteilt · WordPress Draft ausstehend", "amber"];
  if (c === "draft") return [`Entwurf v${w.production.version || 1} · Review`, "blue"];
  if (w.review?.status === "revision_requested" && w.production?.status !== "blocked") return [w.production?.status === "running" ? "Revision in Arbeit" : "Revision requested · Waiting for agent", "amber"];
  if (w.production?.status === "running" || w.production?.status === "in_progress") return ["Producing", "blue"];
  if (w.production?.status === "blocked" || w.production?.status === "failed") return ["Blocked – environment unavailable", "red"];
  const t = w.trigger?.requested_at && /angestoßen/.test(w.trigger?.result || "") ? (Date.now() - Date.parse(w.trigger.requested_at)) / 60000 : null;
  if (t !== null && t < 20) return ["Agent starting", "blue"];
  return ["Approved · Waiting for agent", "amber"];
}
/** Aktiver Zustand kompakt: Gate 1 · Production · Draft (Testphase-Daten zählen nicht) */
const PROD_LABEL = { not_started: "Not started", waiting: "Waiting", running: "Producing", in_progress: "Producing", blocked: "Blocked", failed: "Failed", draft_ready: "Draft ready" };
function wfStateLine(w) {
  const g = w?.gate1?.status === "approved" ? (wfStrategy(w).ok ? "Approved" : "Approved (alt, ohne Strategie)") : "Pending";
  const p = PROD_LABEL[w?.production?.status] || "Not started", d = w?.production?.doc_url ? `v${w.production.version || 1}` : "—";
  return `Gate 1: ${esc(g)} · Production: ${esc(p)} · Draft: ${esc(d)}${w?.test_phase ? ` · <span data-tip="Frühere Testläufe sind im Verlauf erhalten">Test phase · superseded</span>` : ""}`;
}
/** Karten: alle CREATE/OPTIMIZE/MERGE-Opportunities + TEST-Einträge aus der db (nur für technische Tests, deutlich markiert) */
function wfCards() {
  const opps = S.d.opportunities.filter(o => ["CREATE", "OPTIMIZE", "MERGE"].includes(o.type)).map(o => ({ id: o.id, o }));
  const tests = Object.entries(wfAll()).filter(([, w]) => w.test).map(([k, w]) => ({ id: w.opp_id || k, o: { id: w.opp_id || k, name: w.title || "TEST", type: w.card?.type || "CREATE", priority: "low", confidence: "low", business_fit: 0, primary_keyword: w.card?.primary_keyword || "test", gsc_cluster: null, why: "Technischer Workflow-Test – kein echter Content.", recommendation: "TEST", reasoning: [], risks: [], gsc: { queries: [] }, semrush: { keywords: [] }, test: true } }));
  return [...opps, ...tests];
}
function wfSignals(o) {
  if (o.test) return [chip("TEST", "amber")];
  const s = [], f = S.d.funnel?.clusters.find(c => c.cluster === o.gsc_cluster);
  const ct = o.gsc?.cluster_total; if (ct) s.push(`<span data-tip="GSC-Cluster, 16 Monate">GSC ${fmtN(ct.impressions)} Impr. · Pos. ${fmtD(ct.position)}</span>`);
  const sv = o.semrush?.keywords?.find(k => k.status === "ok"); if (sv) s.push(`<span data-tip="Semrush-Volumen des Primär-Keywords (DE)">Semrush ${fmtN(sv.volume)}</span>`);
  if (f) s.push(`<span data-tip="GA4, Haupt-Landingpages des Clusters, 16 Monate">GA4 ${fmtN(leadsOf(f.engagement))} Leads · Intent ${fmtN(f.engagement.micro_sessions)}</span>`);
  return s;
}
function wfCard({ id, o }) {
  const w = wfDoc(id), col = wfCol(w), [l, c] = wfLabel(w);
  const short = (o.why || o.recommendation || "").length > 150 ? (o.why || o.recommendation).slice(0, 150).replace(/\s+\S*$/, "") + " …" : (o.why || o.recommendation || "");
  return `<article class="wf-card${o.test ? " test" : ""}" data-card="${esc(id)}" tabindex="0" ${col === "review" && !o.test ? `draggable="true"` : col === "review" ? `draggable="true"` : ""} aria-label="${esc(id)} ${esc(o.name)}">
    <div class="wf-top"><span class="wf-id">${esc(id)}</span>${typeChip(o.type)}${o.test ? chip("TEST", "amber") : prioChip(o.priority)}</div>
    <h4>${esc(o.name)}</h4>
    <div class="wf-meta"><span>Conf. ${esc({ high: "High", medium: "Medium", low: "Low" }[o.confidence] || "–")}</span><span>Fit ${esc(o.business_fit ?? "–")}/10</span>${o.freeze ? chip("Change freeze", "amber") : ""}</div>
    <div class="wf-kw">${esc(o.primary_keyword || "–")}${o.gsc_cluster ? ` <span class="s">· ${esc(CL_LABEL(o.gsc_cluster))}</span>` : ""}</div>
    <div class="wf-url s">${o.existing_page ? `Bestehend: ${esc(o.existing_page)}` : o.planned_url ? `Geplant: ${esc(o.planned_url)}` : o.test ? "Testdatei" : "Neue Seite (URL offen)"}</div>
    <p class="wf-why">${esc(short)}</p>
    <div class="wf-sig">${wfSignals(o).join("")}</div>
    ${o.test ? "" : `<div class="wf-res">${resChip(o)}${o.cannibalization ? riskChip(o.cannibalization.risk) : ""}${agentPlan(o).companions.length ? chip("+ Companion", "amber") : ""}${rrOf(id) ? chip(...(RR_LABEL[rrOf(id).status] || [rrOf(id).status, ""]), true) : ""}</div><div class="wf-state s">${wfStateLine(w)}</div>`}
    <div class="wf-foot">${chip(l, c, true)}${w?.production?.doc_url && col !== "review" ? `<a href="${esc(w.production.doc_url)}" target="_blank" rel="noopener" class="mini">Entwurf ↗</a>` : ""}</div>
  </article>`;
}
pages.approvals = () => {
  view().innerHTML = `<div class="page-head"><div><h1>Workflow</h1><div class="sub">Gate 1 (Strategie) → Entwurf in Google Drive → Gate 2 (Inhalt) → WordPress-Draft + QA → Gate 3 (Publish) → Live + Monitoring. Gate 1 und 2 ändern nie die Website; veröffentlicht wird nur nach Gate 3.</div></div>
    <a class="btn" href="${esc(S.d.workflow?.drive_folder_url || "#")}" target="_blank" rel="noopener">Drive-Ordner „Claude Landingpages“ ↗</a></div>
    <div id="store-notice"></div>
    <div class="wf-board mt" id="wf-board"></div>
    <div class="card mt"><div class="card-h"><div><h2>Entscheidungsprotokoll</h2><div class="hint">Jede Aktion, neueste zuerst</div></div></div><div id="dec-log"></div></div>
    <div class="wf-drawer" id="wf-drawer" hidden><div class="wf-backdrop" data-close></div><aside class="wf-panel" role="dialog" aria-modal="true" aria-labelledby="wf-title"><div id="wf-panel-body"></div></aside></div>`;
  renderBoard(); renderStoreNotice(); renderDecisionLog();
  const board = $("#wf-board");
  if (WF_PENDING_OPEN) { const id = WF_PENDING_OPEN; WF_PENDING_OPEN = null; setTimeout(() => openCard(id), 0); }
  board.addEventListener("click", e => { const c = e.target.closest("[data-card]"); if (c && !e.target.closest("a")) openCard(c.dataset.card); });
  board.addEventListener("keydown", e => { const c = e.target.closest("[data-card]"); if (c && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openCard(c.dataset.card); } });
  board.addEventListener("dragstart", e => { const c = e.target.closest("[data-card]"); if (!c) return; e.dataTransfer.setData("text/plain", c.dataset.card); e.dataTransfer.effectAllowed = "move"; board.classList.add("dragging"); });
  board.addEventListener("dragend", () => { board.classList.remove("dragging"); board.querySelectorAll(".wf-col.over").forEach(x => x.classList.remove("over")); });
  board.addEventListener("dragover", e => { const col = e.target.closest('.wf-col[data-col="production"]'); if (col) { e.preventDefault(); col.classList.add("over"); } });
  board.addEventListener("dragleave", e => { const col = e.target.closest(".wf-col"); if (col && !col.contains(e.relatedTarget)) col.classList.remove("over"); });
  board.addEventListener("drop", e => { const col = e.target.closest('.wf-col[data-col="production"]'); if (!col) return; e.preventDefault(); col.classList.remove("over");
    const id = e.dataTransfer.getData("text/plain"); if (id && wfCol(wfDoc(id)) === "review") openCard(id, { approve: true }); });
  $("#wf-drawer").addEventListener("click", e => { if (e.target.closest("[data-close]")) closeCard(); });
};
document.addEventListener("keydown", e => wfEsc(e));
function wfEsc(e) { if (e.key === "Escape" && $("#wf-drawer") && !$("#wf-drawer").hidden) closeCard(); }
function renderBoard() {
  const el = $("#wf-board"); if (!el) return;
  const cards = wfCards(), by = Object.fromEntries(WF_COLS.map(([k]) => [k, []]));
  for (const c of cards) by[wfCol(wfDoc(c.id))].push(c);
  el.innerHTML = WF_COLS.map(([k, t, h]) => `<section class="wf-col" data-col="${k}" aria-label="${esc(t)}"><header><div><h3>${esc(t)}</h3><div class="s">${esc(h)}</div></div><span class="wf-count">${by[k].length}</span></header>
    <div class="wf-list">${by[k].map(wfCard).join("") || `<div class="wf-empty">${k === "production" ? "Karte hierher ziehen oder in der Karte „Zur Produktion freigeben“ wählen" : "Keine Einträge"}</div>`}</div></section>`).join("");
  updateBadges();
}
let WF_OPEN = null;
function openCard(id, opts = {}) {
  const c = wfCards().find(x => x.id === id); if (!c) return;
  WF_OPEN = id; const o = c.o, w = wfDoc(id), col = wfCol(w), [l, lc] = wfLabel(w), f = S.d.funnel?.clusters.find(x => x.cluster === o.gsc_cluster);
  const canWrite = DB.state === "ready" && DB.canWrite;
  const hist = clientDecisions().filter(x => x.item_id === id);
  let action = "";
  const rs = o.test ? null : resStatus(o), rsReady = !rs || RES_READY.includes(rs.state);
  if (col === "review") action = `<div class="wf-action"><h3>Gate 1 · Strategie freigeben</h3>
      ${rs ? `<div class="row">${resChip(o)}${rs.version ? `<span class="mini">Research v${esc(rs.version)}</span>` : ""}${o.research?.A_decision?.decision ? typeChip(o.research.A_decision.decision) : ""}<a class="mini" href="#opp-${esc(id)}">Strategie A–J lesen →</a></div>
        ${o.research?.A_decision?.summary ? `<p>${esc(o.research.A_decision.summary)}</p>` : ""}
        ${rs.limits?.length ? `<div class="s"><b>Grenzen:</b> ${esc(rs.limits.join(" "))}</div>` : ""}
        ${wfLegacy(w) ? `<div class="notice mt">Die Gate-1-Freigabe vom ${fmtDateTime(w.gate1.at)}${w.gate1.comment ? ` („${esc(w.gate1.comment)}“)` : ""} wurde vor der Research-Stufe erteilt. Sie bleibt im Verlauf, startet aber keine Produktion.</div>` : ""}` : ""}
      ${o.test ? "" : gate1Brief(o)}
      <p class="s">Bedeutet: Du gibst die Strategie UND den fachlichen Scope der Seite frei (Entscheidung, Themen, Abgrenzung, Struktur, Auswirkungen auf andere Seiten). Danach erstellt Claude einen vollständigen Content-Entwurf als Google Doc im Ordner „Claude Landingpages“. Bedeutet nicht: Website/WordPress ändern, bestehende Seite überschreiben, veröffentlichen oder URLs ändern.</p>
      ${rsReady ? "" : `<div class="callout amber"><b>${esc(rs.label)}</b>${researchActions(o, "drawer")}</div>`}
      <label class="mini" for="wf-c1">Kommentar / Scope-Änderungen (werden verbindlich in die Produktionsvorgabe übernommen, Vorrang vor dem Dossier)</label><textarea id="wf-c1" placeholder="z. B. Bodenaufnahmen bitte nicht als Standardleistung darstellen. · Versicherungen als zusätzliche Zielgruppe berücksichtigen."></textarea>
      ${rsReady ? `<div class="row"><button class="btn primary" data-act="approve" ${canWrite ? "" : "disabled"}>Strategie freigeben</button>${opts.approve ? `<span class="mini">Per Drag & Drop gewählt – zum Freigeben bestätigen.</span>` : ""}<span class="mini" data-msg></span></div>`
        : `<details class="ovr" ${opts.approve ? "open" : ""}><summary>Ohne vollständige Research freigeben (Override)</summary><div class="s">Die Strategie ist nicht vollständig recherchiert. Ein Override wird im Entscheidungsprotokoll deutlich vermerkt.</div><label class="row mt"><input type="checkbox" id="wf-ovr"> Ich gebe bewusst ohne vollständige Research frei</label>
          <div class="row"><button class="btn" data-act="approve" ${canWrite ? "" : "disabled"}>Mit Override freigeben</button>${opts.approve ? `<span class="mini">Per Drag & Drop gewählt.</span>` : ""}<span class="mini" data-msg></span></div></details>`}</div>`;
  else if (col === "production") action = `<div class="wf-action"><h3>${esc(l)}</h3>
      <div class="kv"><div class="k">Gate 1</div><div>${fmtDateTime(w.gate1.at)}${w.gate1.comment ? ` · „${esc(w.gate1.comment)}“` : ""}</div>
      ${w.review?.status === "revision_requested" ? `<div class="k">Änderungswunsch</div><div>„${esc(w.review.comment)}“ · ${fmtDateTime(w.review.at)}</div>` : ""}
      <div class="k">Agentenlauf</div><div>${w.trigger?.requested_at ? `${fmtDateTime(w.trigger.requested_at)} · ${esc(w.trigger.result || "")}` : "Noch kein Anstoß – wird beim nächsten Agentenlauf verarbeitet"}</div>
      ${w.production?.status === "running" ? `<div class="k">Lauf</div><div>gestartet ${fmtDateTime(w.production.started_at)} · Versuch ${esc(w.production.attempt || 1)}</div>` : ""}
      ${w.production?.status === "blocked" ? `<div class="k">Blockiert</div><div class="down"><code>${esc(w.production.block_reason || "unknown")}</code> · ${fmtDateTime(w.production.blocked_at)}</div>
        <div class="k">Ursache</div><div>${esc(w.production.block_detail || BLOCK_TEXT[w.production.block_reason] || "–")}</div>
        ${w.production.preflight ? `<div class="k">Preflight</div><div class="s">${Object.entries(w.production.preflight).map(([k, v]) => `${v ? "✓" : "✗"} ${esc(k)}`).join(" · ")}</div>` : ""}` : ""}</div>
      ${w.production?.status === "blocked" ? `<div class="row mt"><button class="btn primary" data-act="retry" ${canWrite ? "" : "disabled"}>Erneut versuchen</button><span class="mini" data-msg></span></div><p class="s">Stößt den Agenten erneut an. Deine Gate-1-Freigabe und dein Kommentar bleiben unverändert.</p>`
        : w.production?.status === "running" ? "" : `<div class="row mt"><button class="btn" data-act="retrigger" ${canWrite ? "" : "disabled"}>Agentenlauf erneut anstoßen</button><span class="mini" data-msg></span></div>`}</div>`;
  else if (["wordpress", "publish", "live"].includes(col)) action = wpAction(o, w, col, canWrite);
  else if (col === "draft") { const p = w.production || {};
    action = `<div class="wf-action"><h3>${esc(l)}</h3>
      <div class="row"><a class="btn primary" href="${esc(p.doc_url)}" target="_blank" rel="noopener">Entwurf öffnen ↗</a><span class="s">${esc(p.doc_title || "")}</span></div>
      ${(p.documents || []).filter(d => d.role === "companion").map(d => `<div class="row mt"><a class="btn" href="${esc(d.doc_url)}" target="_blank" rel="noopener">Companion öffnen ↗</a><span class="s">${esc(d.doc_title || d.url)} · gehört zum selben Change Set</span></div>`).join("")}
      <div class="kv mt"><div class="k">Erstellt</div><div>${fmtDateTime(p.created_at)}</div><div class="k">Letzte Änderung</div><div>${fmtDateTime(p.updated_at)}</div>
      <div class="k">Version</div><div>v${esc(p.version || 1)}${(p.history || []).length > 1 ? ` · frühere: ${(p.history || []).filter(h => h.version !== p.version).map(h => `<a href="${esc(h.doc_url)}" target="_blank" rel="noopener">v${esc(h.version)}</a>`).join(", ")}` : ""}</div>
      <div class="k">QA</div><div>${chip(p.qa_status || "Unknown", /pass/i.test(p.qa_status || "") ? "green" : "amber", true)}${p.qa_notes ? `<div class="s">${esc(p.qa_notes)}</div>` : ""}</div>
      <div class="k">Content-Strategie</div><div>${esc(p.strategy_summary || "–")}</div>
      ${w.gate2?.status === "approved" ? `<div class="k">Gate 2</div><div>${fmtDateTime(w.gate2.at)}${w.gate2.comment ? ` · „${esc(w.gate2.comment)}“` : ""}</div>` : ""}</div>
      ${col === "draft" ? `<label class="mini mt" for="wf-c2" style="display:block">Kommentar (Pflicht bei „Änderungen anfordern“)</label><textarea id="wf-c2" placeholder="z. B. Einstieg kürzer, FAQ zu Kosten ergänzen"></textarea>
      <div class="row"><button class="btn" data-act="revise" ${canWrite ? "" : "disabled"}>Änderungen anfordern</button><button class="btn primary" data-act="final" ${canWrite ? "" : "disabled"}>Inhalt freigeben (Gate 2)</button><span class="mini" data-msg></span></div>
      <p class="s">Gate 2: Der Inhalt ist freigegeben. Claude bereitet danach einen <b>WordPress-Draft</b> vor (CREATE: neue Seite als Entwurf · OPTIMIZE: separate Review-Version, die Live-Seite bleibt unverändert). Es wird nichts veröffentlicht – dafür gibt es Gate 3.</p>` : ""}</div>`; }
  $("#wf-panel-body").innerHTML = `<div class="wf-ph"><div><div class="row"><span class="wf-id">${esc(id)}</span>${typeChip(o.type)}${o.test ? chip("TEST", "amber") : prioChip(o.priority)}${chip(l, lc, true)}</div><h2 id="wf-title">${esc(o.name)}</h2></div><button class="btn" data-close aria-label="Schließen">✕</button></div>
    ${canWrite ? "" : `<div class="notice">${esc(storeStatus()[2])}</div>`}
    ${action}
    <div class="wf-basis"><h3>Entscheidungsgrundlage</h3>
      ${rs ? `<div class="row">${resChip(o)}${o.research ? `<a class="mini" href="#opp-${esc(id)}">Research A–J →</a>` : ""}</div>` : ""}
      <div class="kv"><div class="k">Primary Keyword</div><div>${esc(o.primary_keyword || "–")}${o.gsc_cluster ? ` · Cluster ${esc(CL_LABEL(o.gsc_cluster))}` : ""}</div>
      <div class="k">URL</div><div>${o.existing_page ? `bestehend ${esc(o.existing_page)}` : o.planned_url ? `geplant ${esc(o.planned_url)} <span class="s">(${esc(o.planned_url_note || "Vorschlag")})</span>` : "–"}</div>
      <div class="k">Priorität · Confidence · Fit</div><div>${prioChip(o.priority)} ${esc({ high: "High", medium: "Medium", low: "Low" }[o.confidence] || "–")} · ${esc(o.business_fit)}/10</div>
      <div class="k">Warum</div><div>${esc(o.why || "–")}</div><div class="k">Empfehlung</div><div>${esc(o.recommendation || "–")}</div></div>
      ${o.reasoning?.length ? `<h4>Reasoning</h4><ul class="list">${o.reasoning.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
      ${o.risks?.length ? `<h4>Risiken</h4><ul class="list">${o.risks.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
      ${o.gsc?.queries?.length ? `<h4>GSC (16 Monate)</h4><div class="tbl-wrap"><table><thead><tr><th>Query</th><th class="num">Impr.</th><th class="num">Klicks</th><th class="num">Pos.</th></tr></thead><tbody>${o.gsc.queries.map(q => q.missing ? `<tr><td>${esc(q.query)}</td><td colspan="3" class="s">keine GSC-Daten</td></tr>` : `<tr><td>${esc(q.query)}</td><td class="num">${fmtN(q.impressions)}</td><td class="num">${fmtN(q.clicks)}</td><td class="num">${fmtD(q.position)}</td></tr>`).join("")}</tbody></table></div>` : ""}
      ${o.semrush?.keywords?.length ? `<h4>Semrush (DE)</h4><div class="tbl-wrap"><table><thead><tr><th>Keyword</th><th class="num">Vol.</th><th class="num">KD</th><th class="num">CPC</th></tr></thead><tbody>${o.semrush.keywords.map(k => k.status === "ok" ? `<tr><td>${esc(k.keyword)}</td><td class="num">${fmtN(k.volume)}</td><td class="num">${fmtD(k.kd, 0)}</td><td class="num">${fmtD(k.cpc, 2)}</td></tr>` : `<tr><td>${esc(k.keyword)}</td><td colspan="3" class="s">nicht gemessen</td></tr>`).join("")}</tbody></table></div>` : ""}
      ${f ? `<h4>Search → Business (GA4)</h4><div class="s">${fmtN(f.engagement.sessions)} Sitzungen · ${fmtN(f.engagement.engaged)} engagiert · Intent ${fmtN(f.engagement.micro_sessions)} · ${fmtN(leadsOf(f.engagement))} Leads (${f.engagement.lead_form} F · ${f.engagement.lead_contact} K)</div><div class="row mt">${f.signals.map(x => chip(SIG_LABEL[x.kind] || x.kind, SIG[x.kind] || "")).join("")}</div>` : ""}
      ${o.test ? "" : `<p class="mt"><a href="#opp-${esc(id)}">Vollständige Analyse öffnen →</a></p>`}
    </div>
    ${hist.length || w?.test_phase ? `<div class="wf-basis"><h3>Verlauf</h3>${hist.map(x => `<div class="s">${fmtDateTime(x.decided_at)} · Gate ${esc(x.gate)} · ${esc((DEC[x.decision] || [x.decision])[0])}${x.comment ? ` · „${esc(x.comment)}“` : ""}${x.superseded ? ` · ${chip("Test phase · superseded", "")}` : ""}</div>`).join("")}
      ${w?.test_phase ? `<div class="callout mt"><b>Test phase · superseded</b>${(w.gate1?.superseded || []).map(g => `<div class="s">Gate 1 vom ${fmtDateTime(g.at)}${g.comment ? ` („${esc(g.comment)}“)` : ""} – ${esc(g.superseded_as)}, löst keine Produktion aus</div>`).join("")}
        ${w.test_phase.production?.status ? `<div class="s">Produktion in der Testphase: ${esc(PROD_LABEL[w.test_phase.production.status] || w.test_phase.production.status)}${w.test_phase.production.doc_title ? ` · „${esc(w.test_phase.production.doc_title)}“ (${esc(w.test_phase.production.doc_trashed_note || "")})` : ""}</div>` : ""}
        ${w.cleanup ? `<div class="s">${fmtDateTime(w.cleanup.at)} · Workflow Cleanup: ${esc(w.cleanup.note)}</div>` : ""}</div>` : ""}</div>` : ""}`;
  $("#wf-drawer").hidden = false; lockScroll(true);
  $("#wf-panel-body").querySelectorAll("[data-act]").forEach(b => b.addEventListener("click", () => wfAct(b.dataset.act, c)));
  setTimeout(() => ($("#wf-c1") || $("#wf-panel-body [data-close]"))?.focus(), 30);
}
function closeCard() { WF_OPEN = null; const d = $("#wf-drawer"); if (d) d.hidden = true; lockScroll(false); }
/** Scroll-Sperre nur solange ein Drawer/Dialog offen ist. Jede Navigation hebt sie auf (route → lockScroll(false)),
    damit ein über einen Link verlassener Drawer die nächste Seite nicht blockiert. */
function lockScroll(on) { document.documentElement.classList.toggle("scroll-locked", !!on); document.body.style.overflow = ""; }
async function wfAct(act, c) {
  const msg = $("#wf-panel-body [data-msg]"), id = c.id, o = c.o, now = new Date().toISOString();
  const say = t => { if (msg) msg.textContent = t; };
  if (!(DB.state === "ready" && DB.canWrite)) return say("Speichern ist in dieser Ansicht nicht möglich.");
  const ref = DB.ns.collection("workflow").doc(id), cur = WF.items[id];
  let patch, ev;
  if (act === "approve") {
    const comment = ($("#wf-c1")?.value || "").trim(), rs = o.test ? null : resStatus(o), ready = !rs || RES_READY.includes(rs.state);
    const override = !ready && !!$("#wf-ovr")?.checked;
    if (!ready && !override) return say("Research unvollständig – bitte Override bestätigen oder Research abwarten.");
    const plan = o.test ? null : agentPlan(o), cz = o.cannibalization;
    let choice = "recommendation";
    if (cz && cz.warning && !o.test) { choice = await gateDialog(o); if (choice === "cancel") return say("Abgebrochen – nichts gespeichert."); }
    const cs = plan ? (choice === "override" ? { action: o.type, url: o.existing_page || o.planned_url || null, companions: [] }
      : { action: plan.action, url: plan.url || null, companions: plan.companions.map(c => ({ url: c.url, reason: c.reason, required_changes: c.required_changes || [], linked_opp: c.linked_opp || null })) }) : null;
    patch = { gate1: { status: "approved", at: now, comment, research_version: rs?.version ?? null, research_state: rs?.state ?? null, research_override: override,
        change_set: cs, cannibalization: cz ? { risk: cz.risk, engine_decision: cz.decision, choice: cz.warning ? choice : "no_warning" } : null },
      production: { ...(cur?.production || {}), status: "waiting", block_reason: null, block_detail: null }, review: { status: "none" } };
    ev = { gate: 1, decision: override || choice === "override" ? "approve_override" : "approve", comment: (override ? "[Override ohne vollständige Research] " : rs?.version ? `[Strategie Research v${rs.version}] ` : "") + (cz?.warning ? `[Kannibalisierung ${cz.risk}: ${choice === "override" ? "trotzdem freigegeben" : "Empfehlung übernommen"}] ` : "") + (cs?.companions?.length ? `[Change Set + ${cs.companions.map(c => c.url).join(", ")}] ` : "") + comment };
  } else if (act === "revise") {
    const comment = ($("#wf-c2")?.value || "").trim();
    if (!comment) return say("Bitte beschreibe kurz, was geändert werden soll.");
    patch = { review: { status: "revision_requested", comment, at: now, for_version: cur?.production?.version || 1 } };
    ev = { gate: 2, decision: "request_changes", comment };
  } else if (act === "final") {
    const comment = ($("#wf-c2")?.value || "").trim(), mode = cur?.gate1?.change_set?.action || (o.test ? "CREATE" : agentPlan(o).action);
    patch = { gate2: { status: "approved", at: now, comment }, review: { status: "approved", at: now, comment },
      wordpress: { status: "queued", mode: mode === "CREATE" ? "CREATE" : "OPTIMIZE", requested_at: now, draft_version: 0 } };
    ev = { gate: 2, decision: "approve", comment };
  } else if (act === "wp_retry") {
    patch = { wordpress: { ...(cur?.wordpress || {}), status: "queued", block_reason: null, block_detail: null, retry_requested_at: now } };
    ev = { gate: 2, decision: "wp_retry", comment: "" };
  } else if (act === "gate3") {
    const wp = cur?.wordpress || {}, comment = ($("#wf-c3")?.value || "").trim(), vis = !!$("#wf-vis")?.checked;
    if (wp.status !== "qa_passed") return say("Gate 3 ist nur für eine Version mit bestandener WordPress QA möglich.");
    if (wp.qa?.overall === "passed_manual_visual" && !vis) return say("Bitte zuerst die Sichtprüfung (Desktop/Tablet/Mobile) bestätigen.");
    if (wp.mode === "OPTIMIZE" && wp.rollback?.status !== "available") return say("Rollback protection unavailable – Gate 3 gesperrt.");
    patch = { gate3: { status: "approved", at: now, comment, for_draft_version: wp.draft_version, visual_review_confirmed: vis }, wordpress: { ...wp, status: "publish_queued" } };
    ev = { gate: 3, decision: "approve", comment: `[Publish v${wp.draft_version}${vis ? " · Sichtprüfung bestätigt" : ""}] ${comment}` };
  } else if (act === "retry") {
    if (cur?.production?.status !== "blocked") return say("Nur blockierte Aufträge können erneut versucht werden.");
    patch = { production: { status: "waiting", retry_requested_at: now, block_reason: null, block_detail: null } };
    ev = { gate: 1, decision: "retry", comment: "" };
  } else if (act === "retrigger") { say("Stoße Agentenlauf an…"); await wfTrigger(id, "retrigger"); return say(WF.trigger.note); }
  say("Speichere…"); $("#wf-panel-body").querySelectorAll("[data-act]").forEach(b => b.disabled = true);
  try {
    if (cur) await ref.update(patch); else await ref.set({ opp_id: id, title: o.name, client: S.client, schema: 1, ...patch });
    const eid = `${S.client}--${id}--g${ev.gate}--${Date.now()}`.replace(/[^A-Za-z0-9_.~:@+-]/g, "-");
    await DB.ns.collection("decisions").doc(eid).set({ schema: 1, client: S.client, item_id: id, item_title: o.name, gate: ev.gate, decision: ev.decision, comment: ev.comment, decided_at: now, agent_status: "pending", agent_processed_at: null, agent_note: act === "final" ? "Gate 2 – WordPress-Draft wird vorbereitet (kein Publishing)" : null });
    say("Gespeichert.");
    if (["approve", "revise", "retry", "final", "wp_retry", "gate3"].includes(act) && !(o.test && act === "final")) { await wfTrigger(id, act); say("Gespeichert. " + WF.trigger.note); }
  } catch (e) { say(`Nicht gespeichert (${e.code || "error"}): ${e.message || ""}`); $("#wf-panel-body").querySelectorAll("[data-act]").forEach(b => b.disabled = false); }
}
/** Agentenlauf anstoßen: geplante Aufgabe (nur auf Anstoß) über den Konnektor "Claude Code Remote". Ohne Konnektor bleibt die Freigabe gespeichert und wird beim nächsten Lauf verarbeitet. */
async function wfTrigger(id, act) {
  const tid = S.d.workflow?.trigger_id, srv = "Claude Code Remote";
  let result;
  try {
    const mcp = await window.claude?.use?.("mcp");
    if (!mcp || !tid) throw { code: "unavailable", message: "Konnektor nicht verfügbar" };
    const lt = await mcp.listTools(srv).catch(() => null);
    const has = lt?.servers?.some(s => s.server === srv && s.tools.some(t => t.name === "fire_trigger"));
    if (!has) throw { code: "not_available", message: "fire_trigger in dieser Ansicht nicht verfügbar" };
    await mcp.callTool(srv, "fire_trigger", { trigger_id: tid, text: `Workflow-Aktion „${act}“ für ${id} im Artifact (Zeitpunkt ${new Date().toISOString()}).` }, { cache: false });
    result = "Agentenlauf angestoßen"; WF.trigger = { state: "ok", note: "Claude wurde angestoßen und verarbeitet die Freigabe." };
  } catch (e) {
    result = "nicht angestoßen (" + (e.code || "error") + ")"; WF.trigger = { state: "off", note: "Kein automatischer Anstoß möglich – Status bleibt „Waiting for agent“ und wird beim nächsten Agentenlauf verarbeitet." };
  }
  try { await DB.ns.collection("workflow").doc(id).update({ trigger: { requested_at: new Date().toISOString(), result } }); } catch (e) { /* Status bleibt ohne Trigger-Vermerk korrekt */ }
}

function renderStoreNotice() {
  const el = $("#store-notice"); if (!el) return; const [l, c, t] = storeStatus();
  el.innerHTML = `<div class="notice row">${chip("Approval store: " + l, c, true)}<span>${esc(t)}</span></div>`;
}
function renderDecisionLog() {
  const el = $("#dec-log"); if (!el) return;
  if (DB.state !== "ready") { el.innerHTML = `<div class="empty">${esc(storeStatus()[2])}</div>`; return; }
  const d = clientDecisions();
  el.innerHTML = d.length ? `<div>${d.map(x => `<div class="dl-item"><div><div class="row"><b>${esc(x.item_title || x.item_id)}</b><span class="mini">${esc(x.item_id)} · Gate ${esc(x.gate)}</span></div>
      <div class="s">Decided ${fmtDateTime(x.decided_at)}${x.comment ? ` · „${esc(x.comment)}“` : ""}</div>
      ${x.agent_status === "processed" || x.superseded ? `<div class="s">Agent: ${fmtDateTime(x.agent_processed_at)}${x.agent_note ? ` · ${esc(x.agent_note)}` : ""}</div>` : ""}</div>
      <div class="row" style="align-content:start">${chip(DEC[x.decision]?.[0] || x.decision, DEC[x.decision]?.[1] || "", true)}${chip((AGENT[x.agent_status] || [x.agent_status])[0], (AGENT[x.agent_status] || [, ""])[1])}</div></div>`).join("")}</div>`
    : `<div class="empty">No decisions recorded yet.</div>`;
}

pages.changes = () => {
  const ch = S.d.changes;
  view().innerHTML = `<div class="page-head"><div><h1>Changes & Impact</h1><div class="sub">Every relevant SEO change with monitoring checkpoints. Correlation is not causation.</div></div></div>
  ${ch.length ? ch.map(c => {
    const today = S.d.meta.today;
    return `<div class="card" style="margin-bottom:14px"><div class="card-h"><div><div class="row"><span class="mini">${fmtDate(c.date)}</span><b>${esc(c.id)}</b><h2>${esc(c.title)}</h2>${statusChip(c.status === "monitoring" ? "Monitoring" : c.status)}${c.freeze ? chip("Change freeze", "amber", true) : ""}</div>
      <div class="hint">${esc(c.url)} · by ${esc(c.by)} · <a href="#opp-${esc(c.related_opportunity)}">${esc(c.related_opportunity)}</a> · findings ${c.related_findings.map(esc).join(", ")}</div></div>${chip("Assessment: " + c.impact_assessment, "outline")}</div>
      <div class="card-b"><div class="grid g3">
        <div><h3>Reason</h3><div>${esc(c.reason)}</div></div><div><h3>Previous state</h3><div class="s" style="font-family:var(--mono)">${esc(c.previous_state)}</div></div><div><h3>New state</h3><div class="s" style="font-family:var(--mono)">${esc(c.new_state)}</div></div></div>
        <h3 class="mt">Monitoring</h3><div class="timeline">${c.checkpoints.map(cp => { const due = cp.status === "pending" && cp.due <= addDays(today, 7); return `<div class="tl-step ${cp.status === "done" ? "done" : due ? "due" : ""}"><div class="pt"></div><div class="l">${esc(cp.label)} ${cp.status === "done" ? "✓" : ""}</div><div class="d">${fmtDate(cp.due)} · ${cp.status === "done" ? "done" : due ? "due soon" : "pending"}</div></div>`; }).join("")}</div>
        <div class="grid g2 mt"><div>${c.checkpoints.filter(x => x.status === "done").map(cp => `<div class="callout"><b>${esc(cp.label)} result</b><div class="s" style="margin-top:4px">${esc(cp.result)}</div>${cp.inspection ? `<div class="kv mt"><div class="k">Verdict</div><div>${esc(cp.inspection.verdict)} · ${esc(cp.inspection.coverage)}</div><div class="k">Google canonical</div><div>${esc(cp.inspection.google_canonical)}</div><div class="k">Declared canonical</div><div>${esc(cp.inspection.user_canonical)}</div><div class="k">Last crawl</div><div>${fmtDate(cp.inspection.last_crawl)}</div></div>` : ""}</div>`).join("")}</div>
        <div><h3>Impact (GSC, page level)</h3><table><thead><tr><th></th><th class="num">Clicks</th><th class="num">Impressions</th><th class="num">Position</th></tr></thead><tbody>
          <tr><td>28 days before</td><td class="num">${fmtN(c.impact.before_28d.clicks)}</td><td class="num">${fmtN(c.impact.before_28d.impressions)}</td><td class="num">${fmtD(c.impact.before_28d.position)}</td></tr>
          <tr><td>After change</td>${c.impact.after ? `<td class="num">${fmtN(c.impact.after.clicks)}</td><td class="num">${fmtN(c.impact.after.impressions)}</td><td class="num">${fmtD(c.impact.after.position)}</td>` : `<td colspan="3" class="s">${esc(c.impact.note)}</td>`}</tr></tbody></table>
          <div class="mini mt">Assessment options: Likely positive · No measurable effect · Negative · Too early to tell.</div></div></div>
      </div></div>`;
  }).join("") : `<div class="card empty">No changes logged.</div>`}`;
};
const addDays = (iso, n) => { const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };

pages.market = () => {
  const m = S.d.market, cc = m.capability_classes;
  view().innerHTML = `<div class="page-head"><div><h1>Market Opportunities</h1><div class="sub">Search demand that may reveal new business fields. Never treated as an existing service until you decide.</div></div>
    <div class="row">${Object.entries(cc).map(([k, v]) => `<span class="chip outline">${k} · ${esc(v)}</span>`).join("")}</div></div>
  <div class="card" id="mk"></div>`;
  const best = x => x.semrush.find(k => k.status === "ok"); // erstes (kuratiertes Primär-)Keyword, nicht das größte
  mount("mk", table({ rows: m.items, pageSize: 20, search: ["name", "recommendation"], filters: [{ key: "capability", label: "Capability", options: [...new Set(m.items.map(x => x.capability))] }],
    onRow: x => { S.ui.mkOpen = S.ui.mkOpen === x.id ? null : x.id; renderMkDetail(x); },
    columns: [
      { key: "name", label: "Opportunity", render: x => `<div class="q">${esc(x.name)}</div><div class="s">${esc(x.id)} · fit ${esc(x.business_fit)} · ${esc(x.segments.join(", ") || "–")}</div>` },
      { key: "capability", label: "Capability", render: x => `<span class="chip ${x.capability.startsWith("D") ? "" : x.capability.startsWith("C") ? "amber" : "green"}" data-tip="${esc(cc[x.capability[0]] || "")}">${esc(x.capability)}</span>` },
      { key: "demand", label: "Search demand (DE)", tip: "Volumen des Primär-Keywords (erstes gemessenes Keyword der Liste); weitere Keywords in der Detailansicht", num: true, value: x => best(x)?.volume ?? null, render: x => { const b = best(x); return b ? `${fmtN(b.volume)}<div class="s">${esc(b.keyword)}</div>` : `<span class="s">Not measured</span>`; } },
      { key: "kd", label: "KD", num: true, value: x => best(x)?.kd ?? null, render: x => best(x) ? fmtD(best(x).kd, 0) : "–" },
      { key: "cpc", label: "CPC €", num: true, value: x => best(x)?.cpc ?? null, render: x => best(x) ? fmtD(best(x).cpc, 2) : "–" },
      { key: "gsc", label: "GSC signal", num: true, value: x => x.gsc.impressions, tip: "Impressionen von Queries, die zum Thema passen (16 Monate)", render: x => x.gsc.queries ? `${fmtN(x.gsc.impressions)}<div class="s">${x.gsc.queries} queries</div>` : `<span class="s">none</span>` },
      { key: "coverage", label: "Existing coverage", render: x => `<span class="s">${esc(x.coverage)}</span>` },
      { key: "status", label: "Status", render: x => statusChip(x.status) },
    ] }));
  $("#mk").insertAdjacentHTML("beforeend", `<div id="mk-detail"></div>`);
}
function renderMkDetail(x) {
  const el = $("#mk-detail"); if (!el) return;
  if (S.ui.mkOpen !== x.id) { el.innerHTML = ""; return; }
  el.innerHTML = `<div class="card-b" style="border-top:1px solid var(--border);padding-top:14px"><div class="row"><h2>${esc(x.name)}</h2><span class="mini">${esc(x.id)}</span></div>
    <div class="grid g2 mt"><div><div class="callout"><b>Recommendation:</b> ${esc(x.recommendation)}</div>${x.note ? `<div class="mini mt">${esc(x.note)}</div>` : ""}
      <h3 class="mt">GSC queries</h3>${x.gsc.top.length ? x.gsc.top.map(q => `<div class="s">${esc(q.query)} · ${fmtN(q.impressions)} impr. · pos ${fmtD(q.position)}</div>`).join("") : `<div class="s">No matching queries – the website does not cover this topic.</div>`}</div>
    <div><h3>Semrush keywords</h3><table><thead><tr><th>Keyword</th><th class="num">Vol.</th><th class="num">KD</th><th class="num">CPC</th></tr></thead><tbody>${x.semrush.map(k => `<tr><td>${esc(k.keyword)}</td>${k.status === "ok" ? `<td class="num">${fmtN(k.volume)}</td><td class="num">${fmtD(k.kd, 0)}</td><td class="num">${fmtD(k.cpc, 2)}</td>` : `<td colspan="3" class="s">${k.status === "no_data" ? "No data" : "Not measured"}</td>`}</tr>`).join("")}</tbody></table><div class="mini">Measured ${fmtDate(x.semrush.find(k => k.fetched)?.fetched)}</div></div></div></div>`;
  wrapTables(el);
}

pages.local = () => {
  const l = S.d.local;
  setTimeout(() => { const m = $("#local-matrix"); if (m) mount("local-matrix", localMatrix()); }, 0);
  const cell = (s, loc) => l.cells.find(c => c.service === s && c.location === loc);
  view().innerHTML = `<div class="page-head"><div><h1>Local SEO</h1><div class="sub">Service × location. Only measured data is shown – „Not measured“ is not „0 demand“, and 0 search volume never means IGNORE.</div></div></div>
  <div class="card"><div class="card-h"><div><h2>Local Opportunity Matrix</h2><div class="hint">Service × Region × Demand × Ranking × Competition × Business Fit × Cannibalization → Recommendation. Nur vorhandene Daten (GSC, Semrush-Cache, Inventar) – fehlende Werte sind markiert, keine Units für Vollständigkeit verbraucht. 0 Volumen ≠ IGNORE; City Pages nur mit eigenständigem lokalem Nutzen (keine Doorway Pages).</div></div></div><div id="local-matrix"></div></div>
  <div class="card mt"><div class="card-h"><div><h2>GSC-Signal je Service × Ort</h2><div class="hint">GSC: impressions of queries containing service + location (16 months) · Semrush: local combinations not yet measured · Competition: not measured (SERP check pending)</div></div></div>
    <div class="card-b" style="padding-bottom:10px"><div class="row mini"><span>◐ regional page (Berlin &amp; Brandenburg in page)</span><span>○ service page exists, location not addressed</span><span>– no page</span><span>Empty recommendation = not assessed yet</span></div></div><div class="card-b flush"><div class="tbl-wrap"><table class="matrix"><thead><tr><th>Service (prio)</th>${l.locations.map(x => `<th data-tip="${esc(`Einwohner ${x.population} · Entfernung ab Schönefeld ${x.distance_km} km (gerundet, zu verifizieren)`)}">${esc(x.label)}</th>`).join("")}</tr></thead><tbody>
    ${l.services.map(s => `<tr><td><b>${esc(s.label)}</b><div class="s">${s.priority}/10 · ${esc(s.page)}</div></td>${l.locations.map(loc => { const c = cell(s.key, loc.key); return `<td class="cell ${c.gsc.impressions ? "has" : ""}">
      ${c.gsc.impressions ? `<div class="v" data-tip="${esc(c.gsc.examples.join(" · "))}">${fmtN(c.gsc.impressions)} impr. · pos ${fmtD(c.gsc.best_position)}</div>` : `<div class="s">no GSC signal</div>`}
      <div class="s">${{ "Regional page (Berlin & Brandenburg)": "◐ regional page", "Service page exists, location not addressed": "○ location not addressed", "No page": "– no page" }[c.coverage] || esc(c.coverage)}</div>${c.recommendation ? `<div style="margin-top:3px">${esc(c.recommendation)}</div>` : ""}</td>`; }).join("")}</tr>`).join("")}
    </tbody></table></div></div></div>
  <div class="grid g2 mt"><div class="card"><div class="card-h"><h2>Locations seen in GSC queries</h2><span class="hint">16 months</span></div><div class="card-b">${l.discovered_places.map(([p, n]) => `<span class="chip outline" style="margin:0 6px 6px 0">${esc(p)} · ${n}</span>`).join("")}</div></div>
    <div class="card"><div class="card-h"><h2>Notes</h2></div><div class="card-b mini">${esc(l.population_note)}<br>Doorway pages are explicitly excluded: every future city page needs its own local relevance (target groups, projects, FAQs, internal links).</div></div></div>`;
};

pages.findings = () => {
  const f = S.d.findings;
  view().innerHTML = `<div class="page-head"><div><h1>Findings</h1><div class="sub">Source of truth: state/findings.json (seo-findings.md is generated from it)</div></div></div><div class="card" id="fd"></div><div id="fd-detail" class="mt"></div>`;
  mount("fd", table({ rows: f, pageSize: 25, search: ["id", "title", "description", "url"], sort: { key: "id", dir: 1 },
    filters: [{ key: "severity", label: "Severity", options: ["high", "medium", "low"] }, { key: "status", label: "Status", options: [...new Set(f.map(x => x.status))] }, { key: "category", label: "Category", options: [...new Set(f.map(x => x.category))] }],
    onRow: x => renderFinding(x),
    columns: [{ key: "id", label: "ID", render: x => `<b>${esc(x.id)}</b>` }, { key: "severity", label: "Severity", value: x => ({ high: 3, medium: 2, low: 1 }[x.severity]), render: x => sevChip(x.severity) },
      { key: "category", label: "Category" }, { key: "title", label: "Finding", render: x => `<div class="q">${esc(x.title)}</div><div class="s">${esc(x.description.slice(0, 120))}${x.description.length > 120 ? "…" : ""}</div>` },
      { key: "url", label: "Affected URL", render: x => `<span class="s">${esc(x.url || "–")}</span>` }, { key: "status", label: "Status", render: x => statusChip(x.status) },
      { key: "related_opportunity", label: "Related", render: x => [x.related_opportunity && `<a href="#opp-${esc(x.related_opportunity)}">${esc(x.related_opportunity)}</a>`, x.related_change && `<a href="#changes">${esc(x.related_change)}</a>`].filter(Boolean).join(" · ") || "–" }] }));
};
function renderFinding(x) {
  $("#fd-detail").innerHTML = `<div class="card"><div class="card-h"><div class="row"><b>${esc(x.id)}</b><h2>${esc(x.title)}</h2>${sevChip(x.severity)}${statusChip(x.status)}</div><span class="mini">${fmtDate(x.date)}</span></div>
    <div class="card-b"><div class="kv"><div class="k">Category</div><div>${esc(x.category)}</div><div class="k">Description</div><div>${esc(x.description)}</div><div class="k">Evidence</div><div>${esc(x.evidence)}</div><div class="k">Affected URL</div><div>${esc(x.url || "–")}</div>
    <div class="k">Related opportunity</div><div>${x.related_opportunity ? `<a href="#opp-${esc(x.related_opportunity)}">${esc(x.related_opportunity)}</a>` : "–"}</div><div class="k">Related change</div><div>${x.related_change ? `<a href="#changes">${esc(x.related_change)}</a>` : "–"}</div></div></div></div>`;
}

pages.activity = () => {
  const t = S.d.tasks, groups = [["blocked", "Blocked"], ["needs_review", "Needs review"], ["waiting_for_approval", "Waiting for approval"], ["monitoring", "Monitoring"], ["planned", "Planned"], ["completed", "Completed"]];
  view().innerHTML = `<div class="page-head"><div><h1>Agent Activity</h1><div class="sub">Honest states only. The agent works on demand in Claude Code sessions – nothing is shown as „running“.</div></div></div>
  <div class="grid g2">${groups.filter(([k]) => t.some(x => x.state === k)).map(([k, l]) => `<div class="card"><div class="card-h"><h2>${l}</h2><span class="hint">${t.filter(x => x.state === k).length}</span></div><div class="act">${t.filter(x => x.state === k).map(x => `<div class="act-item"><div>${chip(STATE[k][0], STATE[k][1], true)}<div class="s" style="margin-top:4px">${fmtDate(x.date)}</div></div><div><div class="t">${esc(x.title)} <span class="mini">${esc(x.id)}</span></div><div class="d">${esc(x.detail || "")}</div>${x.blocked_reason ? `<div class="d down">Reason: ${esc(x.blocked_reason)}</div>` : ""}${x.next_check ? `<div class="d">Next check: ${fmtDate(x.next_check)}</div>` : ""}${x.log ? `<div class="d"><a href="#research-log" data-rl-opp="${esc(x.log.opp)}" data-rl-date="${esc(x.log.date)}">Im Research Log ansehen →</a></div>` : ""}</div></div>`).join("")}</div></div>`).join("")}</div>`;
};

pages.sources = () => {
  const s = S.d.sources, c = S.d.client;
  view().innerHTML = `<div class="page-head"><div><h1>Data Sources & System Health</h1><div class="sub">Dashboard data built ${fmtDateTime(S.d.meta.built_at)} · freshness is calculated in your browser from the source dates</div></div></div>
  <div class="grid g3">
    <div class="card"><div class="card-h"><h2>Google Search Console</h2>${statusChip(s.gsc.status === "connected" ? "Connected" : s.gsc.status)}</div><div class="card-b"><div class="kv">
      <div class="k">Property</div><div>${esc(c.gsc.property)}</div><div class="k">Property type</div><div>${esc(c.gsc.property_type)}</div><div class="k">Permission</div><div>${esc(c.gsc.permission)}</div>
      <div class="k">Last successful fetch</div><div>${fmtDate(s.gsc.last_fetch)} ${freshness(s.gsc.last_fetch)}</div><div class="k">Data range</div><div>${fmtDate(s.gsc.data_from)} – ${fmtDate(s.gsc.data_to)}</div>
      <div class="k">Rows</div><div>${fmtN(s.gsc.rows.queries)} queries · ${fmtN(s.gsc.rows.pages)} pages · ${fmtN(s.gsc.rows.days)} days · ${fmtN(s.gsc.rows.query_date)} query×day</div>
      <div class="k">Last inspection</div><div>${esc(s.gsc.last_inspection.url)} · ${esc(s.gsc.last_inspection.verdict)} · ${fmtDate(s.gsc.last_inspection.date)}</div>
      <div class="k">Role</div><div>${esc(s.gsc.role || "–")}</div>
      <div class="k">Credential</div><div>${esc(s.gsc.credential)}</div></div></div></div>
    <div class="card"><div class="card-h"><h2>Semrush</h2>${statusChip(s.semrush.status === "connected" ? "Connected" : s.semrush.status)}</div><div class="card-b"><div class="kv">
      <div class="k">Role</div><div><b>${esc(s.semrush.role || "Keyword research")}</b>${s.semrush.rule ? `<div class="s">${esc(s.semrush.rule)}</div>` : ""}</div>
      <div class="k">Access</div><div>${esc(s.semrush.access)}</div><div class="k">Database</div><div>${esc(s.semrush.database.toUpperCase())}</div>
      <div class="k">Last query</div><div>${fmtDate(s.semrush.last_query)} ${freshness(s.semrush.last_query, 30)}</div>
      <div class="k">Last known API units</div><div><b>${fmtN(s.semrush.last_known_units)}</b> <span class="mini">(as of ${fmtDate(s.semrush.units_checked)})</span></div>
      <div class="k">Keyword cache</div><div>${fmtN(s.semrush.cache.entries)} entries · ${fmtN(s.semrush.cache.no_data)} without data · latest ${fmtDate(s.semrush.cache.latest)}</div>
      <div class="k">Note</div><div class="s">${esc(s.semrush.units_note)}</div></div></div></div>
    <div class="card"><div class="card-h"><h2>Website</h2>${statusChip(s.website.monitors.length ? "Monitoring active" : "No monitors")}</div><div class="card-b"><div class="kv">
      <div class="k">Inventory</div><div>${fmtN(s.website.urls)} URLs (${fmtN(s.website.indexable)} indexable)</div><div class="k">Last crawl</div><div>${fmtDate(s.website.last_inventory)} ${freshness(s.website.last_inventory, 14)}</div></div>
      <h3 class="mt">Active monitors</h3>${s.website.monitors.map(m => `<div class="callout" style="margin-bottom:6px"><b>${esc(m.url)}</b><div class="s">${esc(m.type)}</div><div class="s">Last check ${fmtDate(m.last_check)} · ${esc(m.result)} · next ${fmtDate(m.next_check)}</div></div>`).join("")}</div></div>
  </div>
  <div class="grid g3 mt">${ga4Card()}${adsCard()}${kpCard()}</div>
  ${S.d.sources.wordpress ? `<div class="grid g2 mt">${wpCard()}</div>` : ""}
  <div class="grid g2 mt">${storeCard()}<div class="card"><div class="card-h"><h2>Where this dashboard runs</h2>${chip(window.claude && typeof window.claude.use === "function" ? "Claude artifact" : "Local preview", window.claude && typeof window.claude.use === "function" ? "green" : "", true)}</div><div class="card-b"><div class="kv">
    <div class="k">Primary surface</div><div>Private Claude artifact (pin it in the Claude sidebar)</div>
    <div class="k">Data delivery</div><div>The agent rebuilds <code>dashboard.json</code> and republishes it beside the page after each work session</div>
    <div class="k">Live queries</div><div>None. GSC and Semrush are never queried when the page opens (no credentials in the page, no API units spent)</div>
    <div class="k">Fallback</div><div><code>python3 dashboard/serve.py</code> – same UI on localhost for development</div></div></div></div></div>
  ${freshPanel()}
  <div class="card mt"><div class="card-h"><h2>Data flow</h2></div><div class="card-b mini">Raw sources (GSC API export, Semrush connector results, website crawl) → normalization & analysis (<code>tools/build_dashboard_data.py</code>) + structured state (<code>clients/&lt;client&gt;/state/*.json</code>) → dashboard data layer (<code>dashboard/public/data/&lt;client&gt;/dashboard.json</code>) → UI. No credentials are read by the build or shipped to the browser.${S.d.meta.warnings.length ? `<div class="down mt">Build warnings: ${S.d.meta.warnings.map(esc).join("; ")}</div>` : ""}</div></div>`;
};

/* ------------------------------------------------------------ router */
/* Artifact-taugliches Routing: nur einfache Hash-Namen (#overview, #opp-OPP-02). Alte #/pfad-Links werden umgeschrieben. */
const TITLES = { overview: "Overview", performance: "Performance", funnel: "Search → Business", analytics: "Analytics (GA4)", ads: "Google Ads", opportunities: "Opportunities", approvals: "Workflow", changes: "Changes & Impact", market: "Market Opportunities", local: "Local SEO", findings: "Findings", activity: "Agent Activity", sources: "Data Sources", "research-log": "Research Log" };
/** Jede Tabelle scrollt in ihrem eigenen Container – die Seite selbst scrollt nie horizontal. */
function wrapTables(root = view()) { root.querySelectorAll("table").forEach(t => { if (!t.parentElement.classList.contains("tbl-wrap")) { const w = document.createElement("div"); w.className = "tbl-wrap"; t.replaceWith(w); w.appendChild(t); } }); }
function parseHash() {
  let h = decodeURIComponent(location.hash.replace(/^#/, ""));
  if (h.startsWith("/")) { const [n, id] = h.slice(1).split("/"); h = n === "opportunities" && id ? "opp-" + id : n; }
  if (h.startsWith("opp-")) return { key: "opportunities", id: h.slice(4), raw: h };
  return { key: TITLES[h] ? h : "overview", id: null, raw: h, unknown: !!h && !TITLES[h] };
}
function go(name) { if (location.hash === "#" + name) route(); else location.hash = "#" + name; }
window.go = go;
document.addEventListener("click", e => { const t = e.target.closest("[data-go]"); if (t && !e.target.closest("a,button")) go(t.dataset.go); });
function route(keepScroll = false) {
  tip.hide();
  WF_OPEN = null; lockScroll(false); $(".gate-dialog")?.remove();
  if (!S.d) return;
  const r = parseHash();
  if (location.hash.startsWith("#/")) { history.replaceState(null, "", "#" + (r.id ? "opp-" + r.id : r.key)); }
  document.querySelectorAll("#nav a").forEach(a => { const on = a.dataset.route === r.key; a.classList.toggle("active", on); on ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"); });
  $("#crumbs").innerHTML = `${esc(S.d.client.name)} / ${r.id ? `<a href="#opportunities">${esc(TITLES[r.key])}</a> / <b>${esc(r.id)}</b>` : `<b>${esc(TITLES[r.key])}</b>`}`;
  try { (r.id ? pages.opportunity(r.id) : pages[r.key]()); }
  catch (e) { console.error(e); view().innerHTML = `<div class="card empty">This view failed to render: ${esc(e.message)}</div>`; }
  wrapTables();
  if (!keepScroll) window.scrollTo(0, 0);
}
/* ------------------------------------------------------------ freshness */
function ageDays(iso) { if (!iso) return null; const t = new Date(); const today = Date.UTC(t.getFullYear(), t.getMonth(), t.getDate()); const [y, m, d] = iso.slice(0, 10).split("-").map(Number); return Math.max(0, Math.round((today - Date.UTC(y, m - 1, d)) / 864e5)); }
const fmtDateTime = iso => { if (!iso) return "Unknown"; const d = new Date(iso); return isNaN(d) ? fmtDate(iso) : d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); };
const ageText = n => n === null ? "unknown" : n === 0 ? "today" : n === 1 ? "1 day ago" : `${n} days ago`;
function freshClass(iso, ok, stale) { const n = ageDays(iso); return n === null ? "" : n <= ok ? "ok" : n <= stale ? "stale" : "old"; }
/** [label, iso, okDays, staleDays, explanation] – Schwellen je Quelle */
function freshSpec() {
  const f = S.d.meta.freshness || {};
  return [
    ["GSC data through", f.gsc_data_through, 5, 14, "Letzter Tag mit Search-Console-Daten (Google liefert mit 2–3 Tagen Verzögerung)"],
    ["GSC fetched", f.gsc_fetched, 7, 21, "Letzter erfolgreicher API-Abruf durch den Agenten"],
    ["Semrush last query", f.semrush_last_query, 30, 90, "Letzte Semrush-Abfrage (Keyword-Cache, Rankings)"],
    ["GA4 data through", f.ga4_data_through, 7, 21, "Ende des abgerufenen GA4-Zeitraums. Letzte Sitzung: " + fmtDate(f.ga4_last_session)],
    ["GA4 fetched", f.ga4_fetched, 7, 21, "Letzter erfolgreicher GA4-API-Abruf"],
    ["Google Ads checked", f.ads_checked, 30, 90, "Letzter Konto-/Fähigkeitscheck. Paid-Daten: Historie bis " + (f.ads_data_through || "–")],
    ["Website crawl", f.website_crawl, 14, 45, "Letztes Website-Inventar (Titles, H1, Links, Sitemap)"],
    ["Website monitor", f.website_monitor, 7, 21, "Letzter technischer Check der überwachten URLs"],
    ["SEO state", f.state_updated, 7, 30, "Letzte Aktualisierung von Opportunities, Findings, Changes, Tasks (state/*.json)"],
    ["Dashboard build", S.d.meta.built_at, 7, 30, "Zeitpunkt, zu dem diese Dashboard-Daten gebaut und veröffentlicht wurden"],
  ];
}
function freshTopbar() {
  const f = S.d.meta.freshness || {};
  const it = (l, iso, ok, st, t) => `<span class="fresh ${freshClass(iso, ok, st)}" data-tip="${esc(t + " · " + ageText(ageDays(iso)))}"><i></i>${l} <b>${iso && iso.length > 10 ? fmtDateTime(iso) : fmtDate(iso)}</b></span>`;
  return it("GSC", f.gsc_data_through, 5, 14, "GSC-Daten bis") + it("Semrush", f.semrush_last_query, 30, 90, "Letzte Semrush-Abfrage") + it("GA4", f.ga4_data_through, 7, 21, "GA4-Daten bis") + it("Crawl", f.website_crawl, 14, 45, "Letzter Website-Crawl") + it("State", f.state_updated, 7, 30, "SEO-State zuletzt aktualisiert") + it("Build", S.d.meta.built_at, 7, 30, "Dashboard gebaut");
}
function freshPanel() {
  return `<div class="card mt" id="fresh-card"><div class="card-h"><div><h2>Data freshness</h2><div class="hint">Snapshot published with the last build. Opening this page does not fetch GSC or Semrush live.</div></div><a href="#sources" class="mini">Data sources →</a></div>
    <div class="fgrid">${freshSpec().map(([l, iso, ok, st, t]) => { const c = freshClass(iso, ok, st); return `<div class="fitem"><div class="fl" data-tip="${esc(t)}">${esc(l)}</div><div class="fv">${iso && iso.length > 10 ? fmtDateTime(iso) : fmtDate(iso)}</div><div class="fs">${chip(iso ? ageText(ageDays(iso)) : "Unknown", { ok: "green", stale: "amber", old: "red" }[c] || "", true)}</div></div>`; }).join("")}</div></div>`;
}
/* ------------------------------------------------------------ load */
async function load(slug) {
  const r = await fetch(`data/${slug}/dashboard.json`, { cache: "no-store" });
  if (!r.ok) throw new Error(`dashboard.json for ${slug}: HTTP ${r.status}`);
  S.d = await r.json(); S.client = slug;
  $("#client-region").textContent = S.d.client.region;
  $("#nav-findings").textContent = S.d.health.open_findings || "";
  $("#topbar-right").innerHTML = freshTopbar() + chip(S.d.health.status, { Healthy: "green", Attention: "amber", Critical: "red" }[S.d.health.status], true);
  updateBadges();
  route();
}
let _rz; addEventListener("resize", () => { clearTimeout(_rz); _rz = setTimeout(() => document.querySelectorAll("[id]").forEach(el => { if (el._chart) chartInto(el.id, el._chart); }), 150); });
(async function init() {
  try {
    const r = await fetch("data/clients.json", { cache: "no-store" });
    if (!r.ok) throw new Error("data/clients.json missing – run the build first (python3 dashboard/serve.py).");
    S.clients = (await r.json()).clients;
    const sel = $("#client-switch");
    sel.innerHTML = S.clients.map(c => `<option value="${esc(c.slug)}">${esc(c.name)}</option>`).join("");
    sel.addEventListener("change", () => load(sel.value));
    await load(S.clients[0].slug);
    addEventListener("hashchange", () => route());
  } catch (e) { console.error(e); view().innerHTML = `<div class="card empty">Could not load dashboard data: ${esc(e.message)}</div>`; }
  initDb();
})();
