/* SEO Autopilot Control Center – vanilla JS, keine Abhängigkeiten.
   Liest ausschließlich data/clients.json und data/<client>/dashboard.json (erzeugt von tools/build_dashboard_data.py). */
"use strict";

const S = { clients: [], client: null, d: null, range: "3M", perfRange: "3M", ui: {} };
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
  return days <= staleDays ? chip(`Fresh · ${days} d`, "green", true) : chip(`Stale · ${days} d`, "amber", true);
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
function svgEl(tag, attrs = {}, parent) { const e = document.createElementNS(SVGNS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); parent && parent.appendChild(e); return e; }
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
  const ticks = Math.min(6, n); for (let k = 0; k < ticks; k++) { const i = Math.round(k * (n - 1) / Math.max(1, ticks - 1)); const t = svgEl("text", { x: X(i), y: H - 6, "text-anchor": k === 0 ? "start" : k === ticks - 1 ? "end" : "middle" }, svg); const x = points[i].x; t.textContent = xMode === "month" ? x.slice(5, 7) + "/" + x.slice(2, 4) : fmtDate(x).slice(0, 6); }
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
  const cross = svgEl("line", { y1: m.t, y2: m.t + ih, stroke: "#9aa4b2", "stroke-dasharray": "3 3", opacity: 0, "vector-effect": "non-scaling-stroke" }, svg);
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
    <div class="row"><span class="mini">GSC data through <b>${fmtDate(d.gsc.last)}</b> · fetched ${fmtDate(src.gsc.last_fetch)}</span>${chip(h.status, healthColor, true)}</div></div>
  <div class="strip">
    ${chip("GSC " + (src.gsc.status === "connected" ? "Connected" : src.gsc.status), src.gsc.status === "connected" ? "green" : "red", true)}
    ${chip("Semrush " + (src.semrush.status === "connected" ? "Connected" : src.semrush.status), src.semrush.status === "connected" ? "green" : "red", true)}
    ${chip("Website Monitoring " + (src.website.monitors?.length ? "Active" : "Off"), src.website.monitors?.length ? "green" : "", true)}
    <a href="#/changes">${chip(`${h.freezes} Change Freeze`, h.freezes ? "amber" : "")}</a>
    <a href="#/approvals">${chip(`${h.pending_approvals} Pending Approvals`, h.pending_approvals ? "red" : "")}</a>
    <a href="#/findings">${chip(`${h.open_findings} Open Findings`, h.open_findings ? "amber" : "")}</a>
    ${h.blocked_tasks ? `<a href="#/activity">${chip(`${h.blocked_tasks} Blocked Task`, "red")}</a>` : ""}
  </div>
  <div class="kpis">
    ${kpi("Clicks", fmtN(cur.clicks), delta(cur.clicks, prev?.clicks), "Letzte 28 Tage vs. 28 Tage davor")}
    ${kpi("Impressions", fmtN(cur.impressions), delta(cur.impressions, prev?.impressions), "Letzte 28 Tage vs. 28 Tage davor")}
    ${kpi("Avg. Position", fmtD(cur.position), delta(cur.position, prev?.position, { invert: true, abs: true, unit: "" }), "Impressions-gewichtet, 28 Tage; niedriger = besser")}
    ${kpi("Tracked Opportunities", fmtN(h.tracked_opportunities), `<span class="flat">excl. IGNORE</span>`)}
    ${kpi("Open Findings", fmtN(h.open_findings), `<a href="#/findings">View findings</a>`)}
    ${kpi("Pending Decisions", fmtN(h.pending_decisions), `<span class="flat">${h.pending_approvals} approvals · ${h.pending_decisions - h.pending_approvals} business</span>`)}
  </div>
  <div class="grid g-main">
    <div class="card"><div class="card-h"><h2>Needs your attention</h2><span class="hint">${d.attention.length} items · rule-based</span></div>
      <div class="att">${d.attention.length ? d.attention.map(attItem).join("") : `<div class="empty">Nothing needs your attention.</div>`}</div></div>
    <div class="card"><div class="card-h"><h2>Agent Activity</h2><a href="#/activity" class="mini">All activity →</a></div>
      <div class="act">${actOrder.slice(0, 7).map(actItem).join("")}</div>
      <div class="card-b mini" style="padding-top:8px">Agent runs on demand in Claude Code sessions – there is no permanently running background process.</div></div>
  </div>
  <div class="card mt"><div class="card-h"><div><h2>Organic Search Performance</h2><div class="hint">Google Search Console · ${S.range === "16M" ? "all available data" : "range " + S.range} · ${modeFor(S.range) === "week" ? "weekly" : "daily"}</div></div>
    <div class="row">${legend([{ label: "Clicks", color: "var(--c3)" }, { label: "Impressions", color: "var(--c1)" }])}${rangeSel("range")}</div></div>
    <div class="card-b"><div id="ch-clicks"></div><div id="ch-imp" style="margin-top:6px"></div></div></div>
  <div class="grid g2 mt">
    <div class="card"><div class="card-h"><h2>Top opportunities</h2><a href="#/opportunities" class="mini">All →</a></div><div class="card-b flush" id="ov-opps"></div></div>
    <div class="card"><div class="card-h"><div><h2>Visibility by business segment</h2><div class="hint">Monthly impressions · ${esc("Strategic B2B vs. Price vs. B2C")}</div></div><a href="#/performance" class="mini">Details →</a></div>
      <div class="card-b">${legend(segSeries())}<div id="ch-seg"></div><div class="mini" style="margin-top:6px">${esc(d.client.segments_note)}</div></div></div>
  </div>`;
  drawPerf(S.range, "range", "ch-clicks", "ch-imp");
  mount("ov-opps", table({ rows: d.opportunities.filter(o => o.type !== "IGNORE").slice(0, 6), pageSize: 6, onRow: o => go("opportunities/" + o.id),
    columns: [{ key: "name", label: "Opportunity", render: o => `<div class="q">${esc(o.name)}</div><div class="s">${esc(o.status)}</div>` },
      { key: "type", label: "Type", render: o => typeChip(o.type) }, { key: "priority", label: "Priority", render: o => prioChip(o.priority), sort: false },
      { key: "business_fit", label: "Fit", num: true, render: o => o.business_fit + "/10" }] }));
  $(".tbl-tools", $("#ov-opps")).remove(); $(".tbl-foot", $("#ov-opps")).remove();
  drawSeg("ch-seg");
};
const kpi = (label, val, dl, t = "") => `<div class="card kpi"><div class="k-label"><span ${t ? `data-tip="${esc(t)}"` : ""}>${esc(label)}${t ? " ⓘ" : ""}</span></div><div class="k-val">${val}</div><div class="k-delta">${dl}</div></div>`;
function attItem(a) {
  const href = a.kind === "opportunity" ? "#/opportunities/" + a.ref : a.kind === "task" ? "#/activity" : a.kind === "approval" ? "#/approvals" : a.kind === "change" ? "#/changes" : "#/market";
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
  const which = b.parentElement.dataset.range; S[which] = b.dataset.r; route();
});
function drawPerf(range, _which, idClicks, idImp, idPos, hc = 120) {
  const w = windowRows(range), mode = modeFor(range), pts = bucket(w.cur, mode);
  chartInto(idClicks, { points: pts, series: [{ key: "clicks", label: "Clicks", color: "var(--c3)", type: "bar" }], height: hc, xMode: mode });
  chartInto(idImp, { points: pts, series: [{ key: "impressions", label: "Impressions", color: "var(--c1)", type: "area" }], height: 160, xMode: mode });
  if (idPos) chartInto(idPos, { points: pts, series: [{ key: "position", label: "Avg. position", color: "#7a5af8", type: "line", fmt: v => fmtD(v) }], height: 160, invert: true, xMode: mode, yFmt: v => fmtD(v, 0) });
}
const SEGC = { "Strategic B2B": "#1f8a4c", "Price": "#2f6fdb", "B2C": "#b7740b", "Unknown": "#9aa4b2", "Brand": "#7a5af8" };
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
  $("#otype").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { S.ui.otype = b.dataset.t; route(); } });
  const sv = o => { const k = o.semrush.keywords.find(k => k.status === "ok"); return k ? k.volume : null; };
  mount("opp-table", table({ rows, pageSize: 20, onRow: o => go("opportunities/" + o.id), search: ["name", "primary_keyword", "id"],
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
      { key: "existing_page", label: "Existing page", render: o => o.existing_page ? `<span class="s">${esc(o.existing_page)}</span>` : `<span class="chip blue">New page</span>` },
    ] }));
};

pages.opportunity = id => {
  const o = S.d.opportunities.find(x => x.id === id);
  if (!o) { view().innerHTML = `<a class="back" href="#/opportunities">← Opportunities</a><div class="card empty">Opportunity ${esc(id)} not found.</div>`; return; }
  const p = o.page_info, inv = o.investigation;
  view().innerHTML = `<a class="back" href="#/opportunities">← Opportunities</a>
  <div class="page-head"><div><div class="detail-head"><h1>${esc(o.name)}</h1>${typeChip(o.type)}${prioChip(o.priority)}${confChip(o.confidence)}${statusChip(o.status)}${o.freeze ? chip("Change freeze", "amber", true) : ""}</div>
    <div class="sub">${esc(o.id)} · Business fit ${o.business_fit}/10 · Primary keyword „${esc(o.primary_keyword)}“</div></div></div>
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
      <div class="card"><div class="card-h"><h2>Agent reasoning</h2></div><div class="card-b"><ul class="list">${o.reasoning.map(r => `<li>${esc(r)}</li>`).join("")}</ul></div></div>
      <div class="card"><div class="card-h"><h2>Risks</h2></div><div class="card-b">${o.risks.length ? `<ul class="list">${o.risks.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : `<span class="mini">None documented.</span>`}</div></div>
      <div class="card"><div class="card-h"><h2>Technical findings</h2></div><div class="card-b">${o.findings_detail.length ? o.findings_detail.map(f => `<div style="margin-bottom:8px"><div class="row">${sevChip(f.severity)}<b>${esc(f.id)}</b> ${esc(f.title)} ${statusChip(f.status)}</div><div class="s">${esc(f.description)}</div></div>`).join("") : `<span class="mini">None linked.</span>`}
        ${o.related_changes.length ? `<div class="mt">Related changes: ${o.related_changes.map(c => `<a href="#/changes">${esc(c)}</a>`).join(", ")}</div>` : ""}</div></div>
      <div class="card"><div class="card-h"><h2>Next step</h2></div><div class="card-b"><div class="callout">${esc(o.next_step)}</div>${o.gate1_candidate ? `<div class="mini mt">Gate-1 candidate – will be submitted to the Approval Center when the evidence is complete. Not submitted yet.</div>` : ""}</div></div>
    </div>
  </div>`;
  const cm = o.gsc.cluster_monthly_impressions.map(x => ({ x: x.month + "-01", impressions: x.impressions }));
  chartInto("opp-cl", { points: cm, series: [{ key: "impressions", label: "Cluster impressions / month", color: "var(--c1)", type: "bar" }], height: 120, xMode: "month" });
};

pages.approvals = () => {
  const a = S.d.approvals;
  const decided = JSON.parse(localStorage.getItem("seo-local-decisions-" + S.client) || "{}");
  const item = (x, gate) => `<div class="card" style="margin-bottom:10px"><div class="card-h"><div><h2>${esc(x.title)}</h2><div class="hint">${esc(x.id)} · submitted ${fmtDate(x.submitted)}</div></div>${statusChip(decided[x.id] ? "Local decision: " + decided[x.id] : "Approval required")}</div>
    <div class="card-b"><div class="kv">${Object.entries(x.fields || {}).map(([k, v]) => `<div class="k">${esc(k)}</div><div>${esc(v)}</div>`).join("")}</div>
    <div class="row mt">${["Approve", "Request changes", "Reject"].map(b => `<button class="btn ${b === "Approve" ? "primary" : ""}" data-dec="${b}" data-id="${esc(x.id)}">${b}</button>`).join("")}<span class="mini">Stored locally in this browser only – not yet synced to the agent; triggers no website action.</span></div></div></div>`;
  view().innerHTML = `<div class="page-head"><div><h1>Approval Center</h1><div class="sub">Gate 1 = strategy · Gate 2 = publication. The dashboard never publishes or changes the website.</div></div></div>
  <div class="grid g2">
    <div><h3>Gate 1 – Strategy</h3>${a.gate1.length ? a.gate1.map(x => item(x, 1)).join("") : `<div class="card"><div class="empty">No strategy decisions pending.</div></div>`}
      <div class="card mt"><div class="card-h"><div><h2>Pipeline – Gate-1 candidates</h2><div class="hint">Not submitted. The agent submits a candidate once evidence (e.g. SERP check) is complete.</div></div></div><div class="card-b flush">
      <table><thead><tr><th>Opportunity</th><th>Type</th><th>Status</th><th>Next step</th></tr></thead><tbody>${a.gate1_candidates.map(c => `<tr class="click" onclick="go('opportunities/${esc(c.id)}')"><td class="q">${esc(c.name)}<div class="s">${esc(c.id)}</div></td><td>${typeChip(c.type)}</td><td>${statusChip(c.status)}</td><td class="s">${esc(c.next_step)}</td></tr>`).join("")}</tbody></table></div></div></div>
    <div><h3>Gate 2 – Publication</h3>${a.gate2.length ? a.gate2.map(x => item(x, 2)).join("") : `<div class="card"><div class="empty">No WordPress drafts awaiting review.<br><span class="mini">Drafts appear here with URL/preview, target keyword, metadata and QA status once content production has started.</span></div></div>`}</div>
  </div>`;
  view().querySelectorAll("button[data-dec]").forEach(b => b.addEventListener("click", () => { decided[b.dataset.id] = b.dataset.dec; localStorage.setItem("seo-local-decisions-" + S.client, JSON.stringify(decided)); route(); }));
};

pages.changes = () => {
  const ch = S.d.changes;
  view().innerHTML = `<div class="page-head"><div><h1>Changes & Impact</h1><div class="sub">Every relevant SEO change with monitoring checkpoints. Correlation is not causation.</div></div></div>
  ${ch.length ? ch.map(c => {
    const today = S.d.meta.today;
    return `<div class="card" style="margin-bottom:14px"><div class="card-h"><div><div class="row"><span class="mini">${fmtDate(c.date)}</span><b>${esc(c.id)}</b><h2>${esc(c.title)}</h2>${statusChip(c.status === "monitoring" ? "Monitoring" : c.status)}${c.freeze ? chip("Change freeze", "amber", true) : ""}</div>
      <div class="hint">${esc(c.url)} · by ${esc(c.by)} · <a href="#/opportunities/${esc(c.related_opportunity)}">${esc(c.related_opportunity)}</a> · findings ${c.related_findings.map(esc).join(", ")}</div></div>${chip("Assessment: " + c.impact_assessment, "outline")}</div>
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
}

pages.local = () => {
  const l = S.d.local;
  const cell = (s, loc) => l.cells.find(c => c.service === s && c.location === loc);
  view().innerHTML = `<div class="page-head"><div><h1>Local SEO</h1><div class="sub">Service × location. Only measured data is shown – „Not measured“ is not „0 demand“, and 0 search volume never means IGNORE.</div></div></div>
  <div class="card"><div class="card-h"><div><h2>Local opportunity matrix</h2><div class="hint">GSC: impressions of queries containing service + location (16 months) · Semrush: local combinations not yet measured · Competition: not measured (SERP check pending)</div></div></div>
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
      { key: "related_opportunity", label: "Related", render: x => [x.related_opportunity && `<a href="#/opportunities/${esc(x.related_opportunity)}">${esc(x.related_opportunity)}</a>`, x.related_change && `<a href="#/changes">${esc(x.related_change)}</a>`].filter(Boolean).join(" · ") || "–" }] }));
};
function renderFinding(x) {
  $("#fd-detail").innerHTML = `<div class="card"><div class="card-h"><div class="row"><b>${esc(x.id)}</b><h2>${esc(x.title)}</h2>${sevChip(x.severity)}${statusChip(x.status)}</div><span class="mini">${fmtDate(x.date)}</span></div>
    <div class="card-b"><div class="kv"><div class="k">Category</div><div>${esc(x.category)}</div><div class="k">Description</div><div>${esc(x.description)}</div><div class="k">Evidence</div><div>${esc(x.evidence)}</div><div class="k">Affected URL</div><div>${esc(x.url || "–")}</div>
    <div class="k">Related opportunity</div><div>${x.related_opportunity ? `<a href="#/opportunities/${esc(x.related_opportunity)}">${esc(x.related_opportunity)}</a>` : "–"}</div><div class="k">Related change</div><div>${x.related_change ? `<a href="#/changes">${esc(x.related_change)}</a>` : "–"}</div></div></div></div>`;
}

pages.activity = () => {
  const t = S.d.tasks, groups = [["blocked", "Blocked"], ["needs_review", "Needs review"], ["waiting_for_approval", "Waiting for approval"], ["monitoring", "Monitoring"], ["planned", "Planned"], ["completed", "Completed"]];
  view().innerHTML = `<div class="page-head"><div><h1>Agent Activity</h1><div class="sub">Honest states only. The agent works on demand in Claude Code sessions – nothing is shown as „running“.</div></div></div>
  <div class="grid g2">${groups.filter(([k]) => t.some(x => x.state === k)).map(([k, l]) => `<div class="card"><div class="card-h"><h2>${l}</h2><span class="hint">${t.filter(x => x.state === k).length}</span></div><div class="act">${t.filter(x => x.state === k).map(x => `<div class="act-item"><div>${chip(STATE[k][0], STATE[k][1], true)}<div class="s" style="margin-top:4px">${fmtDate(x.date)}</div></div><div><div class="t">${esc(x.title)} <span class="mini">${esc(x.id)}</span></div><div class="d">${esc(x.detail || "")}</div>${x.blocked_reason ? `<div class="d down">Reason: ${esc(x.blocked_reason)}</div>` : ""}${x.next_check ? `<div class="d">Next check: ${fmtDate(x.next_check)}</div>` : ""}</div></div>`).join("")}</div></div>`).join("")}</div>`;
};

pages.sources = () => {
  const s = S.d.sources, c = S.d.client;
  view().innerHTML = `<div class="page-head"><div><h1>Data Sources & System Health</h1><div class="sub">Dashboard data built ${esc(S.d.meta.built_at.replace("T", " "))} · freshness calculated in your browser from source dates</div></div></div>
  <div class="grid g3">
    <div class="card"><div class="card-h"><h2>Google Search Console</h2>${statusChip(s.gsc.status === "connected" ? "Connected" : s.gsc.status)}</div><div class="card-b"><div class="kv">
      <div class="k">Property</div><div>${esc(c.gsc.property)}</div><div class="k">Property type</div><div>${esc(c.gsc.property_type)}</div><div class="k">Permission</div><div>${esc(c.gsc.permission)}</div>
      <div class="k">Last successful fetch</div><div>${fmtDate(s.gsc.last_fetch)} ${freshness(s.gsc.last_fetch)}</div><div class="k">Data range</div><div>${fmtDate(s.gsc.data_from)} – ${fmtDate(s.gsc.data_to)}</div>
      <div class="k">Rows</div><div>${fmtN(s.gsc.rows.queries)} queries · ${fmtN(s.gsc.rows.pages)} pages · ${fmtN(s.gsc.rows.days)} days · ${fmtN(s.gsc.rows.query_date)} query×day</div>
      <div class="k">Last inspection</div><div>${esc(s.gsc.last_inspection.url)} · ${esc(s.gsc.last_inspection.verdict)} · ${fmtDate(s.gsc.last_inspection.date)}</div>
      <div class="k">Credential</div><div>${esc(s.gsc.credential)}</div></div></div></div>
    <div class="card"><div class="card-h"><h2>Semrush</h2>${statusChip(s.semrush.status === "connected" ? "Connected" : s.semrush.status)}</div><div class="card-b"><div class="kv">
      <div class="k">Access</div><div>${esc(s.semrush.access)}</div><div class="k">Database</div><div>${esc(s.semrush.database.toUpperCase())}</div>
      <div class="k">Last query</div><div>${fmtDate(s.semrush.last_query)} ${freshness(s.semrush.last_query, 30)}</div>
      <div class="k">Last known API units</div><div><b>${fmtN(s.semrush.last_known_units)}</b> <span class="mini">(as of ${fmtDate(s.semrush.units_checked)})</span></div>
      <div class="k">Keyword cache</div><div>${fmtN(s.semrush.cache.entries)} entries · ${fmtN(s.semrush.cache.no_data)} without data · latest ${fmtDate(s.semrush.cache.latest)}</div>
      <div class="k">Note</div><div class="s">${esc(s.semrush.units_note)}</div></div></div></div>
    <div class="card"><div class="card-h"><h2>Website</h2>${statusChip(s.website.monitors.length ? "Monitoring active" : "No monitors")}</div><div class="card-b"><div class="kv">
      <div class="k">Inventory</div><div>${fmtN(s.website.urls)} URLs (${fmtN(s.website.indexable)} indexable)</div><div class="k">Last crawl</div><div>${fmtDate(s.website.last_inventory)} ${freshness(s.website.last_inventory, 14)}</div></div>
      <h3 class="mt">Active monitors</h3>${s.website.monitors.map(m => `<div class="callout" style="margin-bottom:6px"><b>${esc(m.url)}</b><div class="s">${esc(m.type)}</div><div class="s">Last check ${fmtDate(m.last_check)} · ${esc(m.result)} · next ${fmtDate(m.next_check)}</div></div>`).join("")}</div></div>
  </div>
  <div class="card mt"><div class="card-h"><h2>Data flow</h2></div><div class="card-b mini">Raw sources (GSC API export, Semrush connector results, website crawl) → normalization & analysis (<code>tools/build_dashboard_data.py</code>) + structured state (<code>clients/&lt;client&gt;/state/*.json</code>) → dashboard data layer (<code>dashboard/public/data/&lt;client&gt;/dashboard.json</code>) → UI. No credentials are read by the build or shipped to the browser.${S.d.meta.warnings.length ? `<div class="down mt">Build warnings: ${S.d.meta.warnings.map(esc).join("; ")}</div>` : ""}</div></div>`;
};

/* ------------------------------------------------------------ router */
const TITLES = { overview: "Overview", performance: "Performance", opportunities: "Opportunities", approvals: "Approvals", changes: "Changes & Impact", market: "Market Opportunities", local: "Local SEO", findings: "Findings", activity: "Agent Activity", sources: "Data Sources" };
function go(path) { location.hash = "#/" + path; }
window.go = go;
function route() {
  tip.hide();
  const [name, id] = (location.hash.replace(/^#\/?/, "") || "overview").split("/");
  const key = TITLES[name] ? name : "overview";
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("active", a.dataset.route === key));
  $("#crumbs").innerHTML = `${esc(S.d.client.name)} / <b>${esc(TITLES[key])}</b>${id ? ` / ${esc(id)}` : ""}`;
  try { (key === "opportunities" && id ? pages.opportunity(decodeURIComponent(id)) : pages[key]()); }
  catch (e) { console.error(e); view().innerHTML = `<div class="card empty">This view failed to render: ${esc(e.message)}</div>`; }
  if (!TITLES[name] && location.hash) history.replaceState(null, "", "#/overview");
  window.scrollTo(0, 0);
}
async function load(slug) {
  const r = await fetch(`data/${slug}/dashboard.json`, { cache: "no-store" });
  if (!r.ok) throw new Error(`dashboard.json for ${slug}: HTTP ${r.status}`);
  S.d = await r.json(); S.client = slug;
  $("#client-region").textContent = S.d.client.region;
  $("#nav-approvals").textContent = S.d.health.pending_approvals || "";
  $("#nav-findings").textContent = S.d.health.open_findings || "";
  $("#topbar-right").innerHTML = `<span>GSC through ${fmtDate(S.d.gsc.last)}</span><span>Built ${esc(S.d.meta.built_at.replace("T", " ").slice(0, 16))}</span>${chip(S.d.health.status, { Healthy: "green", Attention: "amber", Critical: "red" }[S.d.health.status], true)}`;
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
    addEventListener("hashchange", route);
  } catch (e) { console.error(e); view().innerHTML = `<div class="card empty">Could not load dashboard data: ${esc(e.message)}</div>`; }
})();
