#!/usr/bin/env python3
"""Dashboard Data Layer: Rohdaten + State → dashboard/public/data/<client>/dashboard.json

Datenfluss:  Raw Sources (GSC/Semrush/Inventar)  →  Normalisierung/Analyse (hier)
             →  Dashboard Data Layer (JSON)  →  UI (dashboard/public)

Liest NIEMALS Credentials. Liest nur: clients/<slug>/client.json, state/*.json,
data/** (CSV/JSON), data/keyword-cache.csv. Ausgabe enthält nur aggregierte SEO-Daten.

Aufruf: python3 tools/build_dashboard_data.py [--today YYYY-MM-DD]
"""
import argparse, csv, datetime as dt, json, os, re, sys
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from gsc_analyze import cluster as classify_cluster, places as find_places  # noqa: E402

OUT_ROOT = os.path.join(ROOT, "dashboard", "public", "data")


# ---------------------------------------------------------------- helpers
def jload(p, default=None):
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rcsv(p, delim=","):
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=delim))


def num(v, cast=float):
    try:
        return cast(v)
    except (TypeError, ValueError):
        return None


def wavg(rows, key="position", w="impressions"):
    tw = sum(r[w] for r in rows)
    return round(sum(r[key] * r[w] for r in rows) / tw, 2) if tw else None


def agg(rows):
    c = sum(r["clicks"] for r in rows)
    i = sum(r["impressions"] for r in rows)
    return {"clicks": c, "impressions": i, "ctr": round(c / i, 5) if i else None, "position": wavg(rows)}


def short(text, n):
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


def pct(cur, prev):
    if prev in (None, 0) or cur is None:
        return None
    return round((cur - prev) / prev * 100, 1)


def gsc_rows(path, host):
    rows = rcsv(path)
    for r in rows:
        r["clicks"] = int(r["clicks"]); r["impressions"] = int(r["impressions"])
        r["ctr"] = float(r["ctr"]); r["position"] = float(r["position"])
        if "page" in r:
            r["page"] = r["page"].replace(host, "") or "/"
    return rows


# ---------------------------------------------------------------- segments
def make_segmenter(cfg):
    seg = cfg["segments"]
    strat, b2c, brand = set(seg["strategic_b2b_clusters"]), set(seg["b2c_clusters"]), set(seg["brand_clusters"])
    price = re.compile(seg["price_pattern"])

    def segment(query, cl):
        if cl in brand:
            return "Brand"
        if cl in strat:
            return "Strategic B2B"
        if cl == "preis" or price.search(query):
            return "Price"
        if cl in b2c:
            return "B2C"
        return "Unknown"
    return segment


# ---------------------------------------------------------------- build
def build_client(slug, today):
    cdir = os.path.join(ROOT, "clients", slug)
    cfg = jload(os.path.join(cdir, "client.json"))
    st = lambda n: jload(os.path.join(cdir, "state", n + ".json"), {})  # noqa: E731
    host = cfg["website"].rstrip("/")
    gdir = os.path.join(cdir, cfg["gsc"]["data_dir"])
    segment = make_segmenter(cfg)
    warnings = []

    # ---- GSC raw
    daily = gsc_rows(os.path.join(gdir, "gsc_date.csv"), host)
    daily.sort(key=lambda r: r["date"])
    q = gsc_rows(os.path.join(gdir, "gsc_query.csv"), host)
    qp = gsc_rows(os.path.join(gdir, "gsc_query_page.csv"), host)
    pg = gsc_rows(os.path.join(gdir, "gsc_page.csv"), host)
    pdaily = gsc_rows(os.path.join(gdir, "gsc_page_date.csv"), host)
    qdaily = gsc_rows(os.path.join(gdir, "gsc_query_date.csv"), host)
    country = gsc_rows(os.path.join(gdir, "gsc_country.csv"), host)
    device = gsc_rows(os.path.join(gdir, "gsc_device.csv"), host)
    if not daily:
        warnings.append("Keine GSC-Tagesdaten gefunden.")
    last = dt.date.fromisoformat(daily[-1]["date"]) if daily else today
    first = dt.date.fromisoformat(daily[0]["date"]) if daily else today

    def window(days, end=last):
        return (end - dt.timedelta(days=days - 1)).isoformat(), end.isoformat()

    cur_from, cur_to = window(90)
    prev_from, prev_to = window(90, last - dt.timedelta(days=90))

    def in_range(d, a, b):
        return a <= d <= b

    # ---- Query-Tabelle mit Veränderung (letzte 90 Tage vs. 90 Tage davor)
    qcur, qprev = defaultdict(list), defaultdict(list)
    for r in qdaily:
        if in_range(r["date"], cur_from, cur_to):
            qcur[r["query"]].append(r)
        elif in_range(r["date"], prev_from, prev_to):
            qprev[r["query"]].append(r)
    pages_by_q = defaultdict(list)
    for r in qp:
        pages_by_q[r["query"]].append(r)
    queries = []
    for r in q:
        cl = classify_cluster(r["query"])
        ps = sorted(pages_by_q.get(r["query"], []), key=lambda x: -x["impressions"])
        c, p = agg(qcur.get(r["query"], [])), agg(qprev.get(r["query"], []))
        queries.append({
            "query": r["query"], "clicks": r["clicks"], "impressions": r["impressions"], "ctr": r["ctr"],
            "position": round(r["position"], 2), "cluster": cl, "segment": segment(r["query"], cl),
            "places": find_places(r["query"]), "page": ps[0]["page"] if ps else None, "n_pages": len(ps),
            "imp_90d": c["impressions"], "imp_prev90d": p["impressions"], "imp_change": c["impressions"] - p["impressions"],
            "clicks_90d": c["clicks"], "clicks_prev90d": p["clicks"],
            "pos_90d": c["position"], "pos_prev90d": p["position"],
        })
    queries.sort(key=lambda r: -r["impressions"])

    # ---- Pages
    inv = {r["url"].replace(host, "") or "/": r for r in jload(os.path.join(cdir, cfg["website_inventory_dir"], "inventory.json"), [])}
    pcur, pprev, pmonth = defaultdict(list), defaultdict(list), defaultdict(lambda: defaultdict(list))
    for r in pdaily:
        if r["page"].startswith("/kontakt/?"):
            continue
        pmonth[r["page"]][r["date"][:7]].append(r)
        if in_range(r["date"], cur_from, cur_to):
            pcur[r["page"]].append(r)
        elif in_range(r["date"], prev_from, prev_to):
            pprev[r["page"]].append(r)
    pages = []
    for r in pg:
        page = r["page"]
        i = inv.get(page, {})
        c, p = agg(pcur.get(page, [])), agg(pprev.get(page, []))
        pages.append({
            "page": page, "clicks": r["clicks"], "impressions": r["impressions"], "ctr": r["ctr"], "position": round(r["position"], 2),
            "imp_90d": c["impressions"], "imp_prev90d": p["impressions"], "imp_change_pct": pct(c["impressions"], p["impressions"]),
            "clicks_90d": c["clicks"], "clicks_prev90d": p["clicks"], "pos_90d": c["position"], "pos_prev90d": p["position"],
            "title": i.get("title"), "h1": (i.get("h1") or [None])[0], "words": i.get("words_main"),
            "inlinks": i.get("content_inlinks_from_pages"), "outlinks": i.get("content_links_unique_targets"),
            "modified": i.get("modified") or None, "published": i.get("published") or None,
            "in_sitemap": i.get("in_sitemap"), "robots": i.get("robots"),
            "monthly": [{"month": m, **agg(v)} for m, v in sorted(pmonth[page].items())],
        })
    pages.sort(key=lambda r: -r["impressions"])
    page_index = {p["page"]: p for p in pages}

    query_page = [{"query": r["query"], "page": r["page"], "clicks": r["clicks"], "impressions": r["impressions"],
                   "ctr": r["ctr"], "position": round(r["position"], 2),
                   "segment": segment(r["query"], classify_cluster(r["query"]))} for r in qp]
    query_page.sort(key=lambda r: -r["impressions"])

    # ---- Segment-Zeitreihen (monatlich, aus query×date) und Summen
    seg_month = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    qseg = {}
    for r in qdaily:
        s = qseg.get(r["query"])
        if s is None:
            s = qseg[r["query"]] = segment(r["query"], classify_cluster(r["query"]))
        x = seg_month[s][r["date"][:7]]
        x[0] += r["clicks"]; x[1] += r["impressions"]
    months = sorted({m for v in seg_month.values() for m in v})
    segments = {s: [{"month": m, "clicks": v[m][0], "impressions": v[m][1]} for m in months] for s, v in seg_month.items()}
    seg_totals = {}
    for s in ["Strategic B2B", "Price", "B2C", "Brand", "Unknown"]:
        rows = [x for x in queries if x["segment"] == s]
        seg_totals[s] = {"queries": len(rows), "clicks": sum(x["clicks"] for x in rows), "impressions": sum(x["impressions"] for x in rows),
                         "imp_90d": sum(x["imp_90d"] for x in rows), "imp_prev90d": sum(x["imp_prev90d"] for x in rows),
                         "position": wavg(rows) if rows else None}

    # ---- Quick Wins / Winners / Losers / Kannibalisierung
    prio = cfg.get("service_priorities", {})
    quickwins = [dict(x, business_priority=prio.get(x["cluster"])) for x in queries if 3.5 < x["position"] <= 20.5 and x["impressions"] >= 50]
    quickwins.sort(key=lambda x: (-(x["business_priority"] or 0), -x["impressions"]))
    winners = sorted([x for x in queries if x["imp_change"] > 0], key=lambda x: -x["imp_change"])[:50]
    losers = sorted([x for x in queries if x["imp_change"] < 0], key=lambda x: x["imp_change"])[:50]
    cannibal = []
    for query, ps in pages_by_q.items():
        ps = sorted(ps, key=lambda x: -x["impressions"])
        if len(ps) >= 2 and ps[0]["impressions"] >= 30 and ps[1]["impressions"] >= 0.2 * ps[0]["impressions"]:
            cannibal.append({"query": query, "segment": segment(query, classify_cluster(query)),
                             "total_impressions": sum(p["impressions"] for p in ps),
                             "pages": [{"page": p["page"], "impressions": p["impressions"], "position": round(p["position"], 1)} for p in ps[:4]]})
    cannibal.sort(key=lambda x: -x["total_impressions"])

    # ---- Semrush (Cache + Rankings)
    cache = {}
    for r in rcsv(os.path.join(ROOT, "data", "keyword-cache.csv")):
        if r["database"] == cfg["semrush"]["database"] and r["source"] == "semrush_phrase_these":
            cache[r["keyword"]] = r
    sem_rank = rcsv(os.path.join(cdir, cfg["semrush"]["baseline_dir"], "semrush-organic-de-2026-11-23.csv"), ";")

    def sem(k):
        r = cache.get(k)
        if not r:
            return {"keyword": k, "status": "not_queried"}
        if r["status"] == "no_data":
            return {"keyword": k, "status": "no_data", "fetched": r["fetched"]}
        return {"keyword": k, "status": "ok", "volume": num(r["volume"], int), "kd": num(r["kd"]), "cpc": num(r["cpc"]),
                "competition": num(r["competition"]), "fetched": r["fetched"]}

    # ---- Opportunities anreichern
    qindex = {x["query"]: x for x in queries}
    findings = st("findings").get("findings", [])
    changes = st("changes").get("changes", [])
    cl_month = defaultdict(lambda: defaultdict(int))
    for r in qdaily:
        cl_month[classify_cluster(r["query"])][r["date"][:7]] += r["impressions"]
    opps = []
    for o in st("opportunities").get("opportunities", []):
        gq = []
        for k in o.get("gsc_queries", []):
            x = qindex.get(k)
            gq.append({"query": k, **({kk: x[kk] for kk in ("clicks", "impressions", "position", "page", "imp_90d", "imp_prev90d", "pos_90d")} if x else {"missing": True})})
        cl_rows = [x for x in queries if x["cluster"] == o.get("gsc_cluster")]
        cl_agg = agg(cl_rows) if cl_rows else None
        page = page_index.get(o.get("existing_page")) if o.get("existing_page") else None
        ranks = [{"keyword": r["Keyword"], "position": num(r["Position"], int), "volume": num(r["Search Volume"], int)}
                 for r in sem_rank if o.get("existing_page") and r["Url"].replace(host, "") == o["existing_page"]]
        opps.append({**o,
                     "gsc": {"queries": gq, "cluster": o.get("gsc_cluster"), "cluster_total": cl_agg, "cluster_queries": len(cl_rows),
                             "cluster_monthly_impressions": [{"month": m, "impressions": v} for m, v in sorted(cl_month[o.get("gsc_cluster")].items())]},
                     "semrush": {"keywords": [sem(k) for k in o.get("semrush_keywords", [])], "rankings": ranks,
                                 "serp": None, "serp_note": "SERP-Analyse noch nicht durchgeführt (blockiert: API Units)."},
                     "page_info": ({k: page[k] for k in ("page", "title", "h1", "words", "inlinks", "outlinks", "modified", "in_sitemap",
                                                          "clicks", "impressions", "position", "imp_90d", "imp_prev90d", "imp_change_pct")} if page else None),
                     "findings_detail": [f for f in findings if f["id"] in o.get("related_findings", [])],
                     "competing_pages_info": [{"page": p, "impressions": page_index.get(p, {}).get("impressions"),
                                               "position": page_index.get(p, {}).get("position")} for p in o.get("competing_pages", [])],
                     })
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    opps.sort(key=lambda o: (order.get(o["priority"], 9), -o.get("business_fit", 0)))

    # ---- Market (NBO)
    market = st("market")
    for m in market.get("items", []):
        rx = re.compile(m["gsc_pattern"]) if m.get("gsc_pattern") else None
        rows = [x for x in queries if rx and rx.search(x["query"])]
        m["gsc"] = {"queries": len(rows), "impressions": sum(x["impressions"] for x in rows), "clicks": sum(x["clicks"] for x in rows),
                    "top": [{"query": x["query"], "impressions": x["impressions"], "position": x["position"]} for x in rows[:5]]}
        m["semrush"] = [sem(k) for k in m.get("semrush_keywords", [])]

    # ---- Local Matrix
    local = st("local")
    recs = {(r["service"], r["location"]): r["text"] for r in local.get("recommendations", [])}
    cells = []
    for s in local.get("services", []):
        srx = re.compile(s["gsc_pattern"])
        for loc in local.get("locations", []):
            lrx = re.compile(loc["pattern"])
            rows = [x for x in queries if srx.search(x["query"]) and lrx.search(x["query"])]
            sk = f"{s['semrush_stem']} {loc['label'].split(' ')[0].lower()}"
            cells.append({
                "service": s["key"], "location": loc["key"],
                "gsc": {"queries": len(rows), "impressions": sum(x["impressions"] for x in rows), "clicks": sum(x["clicks"] for x in rows),
                        "best_position": min((x["position"] for x in rows), default=None), "examples": [x["query"] for x in rows[:3]]},
                "semrush": sem(sk),
                "coverage": ("Regional page (Berlin & Brandenburg)" if loc["coverage_regional"] and page_index.get(s["page"]) else
                             "Service page exists, location not addressed" if page_index.get(s["page"]) or s["page"] in inv else "No page"),
                "business_fit": s["priority"],
                "competition": None,
                "recommendation": recs.get((s["key"], loc["key"])),
            })
    discovered = Counter(p for x in queries for p in x["places"])
    local_out = {**local, "cells": cells, "discovered_places": discovered.most_common()}

    # ---- Changes: Impact-Messung (vorher/nachher, nur wenn Daten nach dem Änderungsdatum existieren)
    for ch in changes:
        d = ch["date"]
        rows = [r for r in pdaily if r["page"] == ch["url"]]
        before = agg([r for r in rows if (dt.date.fromisoformat(d) - dt.timedelta(days=28)).isoformat() <= r["date"] < d])
        after_rows = [r for r in rows if r["date"] >= d]
        ch["impact"] = {"before_28d": before, "after": agg(after_rows) if after_rows else None,
                        "after_days": len({r["date"] for r in after_rows}),
                        "note": "Noch keine GSC-Daten nach dem Änderungsdatum." if not after_rows else "Korrelation ≠ Kausalität."}

    # ---- Approvals
    appr = st("approvals")
    candidates = [{"id": o["id"], "name": o["name"], "type": o["type"], "status": o["status"], "next_step": o["next_step"]}
                  for o in opps if o.get("gate1_candidate")]

    # ---- Tasks / Sources
    tasks = st("agent_tasks").get("tasks", [])
    sources = st("sources")
    cache_rows = rcsv(os.path.join(ROOT, "data", "keyword-cache.csv"))
    sources["semrush"]["cache"] = {"entries": len(cache_rows), "no_data": sum(1 for r in cache_rows if r["status"] == "no_data"),
                                   "latest": max((r["fetched"] for r in cache_rows), default=None)}
    sources["gsc"]["rows"] = {"queries": len(q), "pages": len(pg), "query_page": len(qp), "days": len(daily), "query_date": len(qdaily)}
    sources["gsc"]["data_from"] = first.isoformat(); sources["gsc"]["data_to"] = last.isoformat()
    sources["website"]["urls"] = len(inv)
    sources["website"]["indexable"] = sum(1 for r in inv.values() if "noindex" not in (r.get("robots") or ""))

    # ---- Attention & Health (regelbasiert, nachvollziehbar)
    attention = []
    for o in opps:
        if o["priority"] == "critical":
            inv_ = o.get("investigation")
            attention.append({"kind": "opportunity", "ref": o["id"], "title": o["name"],
                              "detail": (inv_["implication"] if inv_ else o["why"]), "status": o["status"], "level": "warning"})
    for t in tasks:
        if t["state"] == "blocked":
            attention.append({"kind": "task", "ref": t["id"], "title": t["title"], "detail": t.get("blocked_reason"), "status": "Blocked", "level": "danger"})
        if t["state"] == "needs_review":
            attention.append({"kind": "task", "ref": t["id"], "title": t["title"], "detail": t.get("detail"), "status": "Needs review", "level": "warning"})
    for g in ("gate1", "gate2"):
        for a in appr.get(g, []):
            if a.get("status") == "pending":
                attention.append({"kind": "approval", "ref": a["id"], "title": a["title"], "detail": a.get("summary"), "status": "Approval required", "level": "danger"})
    for ch in changes:
        for cp in ch.get("checkpoints", []):
            if cp["status"] == "pending":
                days = (dt.date.fromisoformat(cp["due"]) - today).days
                if days <= 7:
                    attention.append({"kind": "change", "ref": ch["id"], "title": f"{ch['title']} – {cp['label']}",
                                      "detail": f"Fällig {cp['due']} ({'überfällig' if days < 0 else f'in {days} Tagen'})",
                                      "status": "Check due" if days >= 0 else "Overdue", "level": "info" if days >= 0 else "warning"})
                break
    for o in opps:
        if o["status"].startswith("Waiting for SERP"):
            attention.append({"kind": "opportunity", "ref": o["id"], "title": o["name"], "detail": short(o["recommendation"], 160),
                              "status": o["status"], "level": "info"})
    for m in market.get("items", []):
        if m.get("status") == "Awaiting business decision":
            attention.append({"kind": "market", "ref": m["id"], "title": m["name"], "detail": m["recommendation"], "status": "Decision needed", "level": "info"})
    open_findings = [f for f in findings if f["status"] == "open"]
    pending_approvals = sum(1 for g in ("gate1", "gate2") for a in appr.get(g, []) if a.get("status") == "pending")
    blocked = [t for t in tasks if t["state"] == "blocked"]
    health = "Critical" if any(sources[s].get("status") == "error" for s in ("gsc", "semrush")) else \
             "Attention" if blocked or pending_approvals or any(f["severity"] == "high" for f in open_findings) else "Healthy"

    out = {
        "meta": {"client": slug, "built_at": dt.datetime.now().isoformat(timespec="seconds"), "today": today.isoformat(),
                 "schema": 1, "warnings": warnings},
        "client": {k: cfg[k] for k in ("slug", "name", "region", "domain", "website")} | {"gsc": {k: v for k, v in cfg["gsc"].items() if k not in ("data_dir", "service_account")}, "segments_note": cfg["segments"]["note"]},
        "health": {"status": health, "open_findings": len(open_findings), "pending_approvals": pending_approvals,
                   "freezes": sum(1 for c in changes if c.get("freeze")), "blocked_tasks": len(blocked),
                   "tracked_opportunities": len([o for o in opps if o["type"] != "IGNORE"]),
                   "pending_decisions": pending_approvals + sum(1 for m in market.get("items", []) if m.get("status") == "Awaiting business decision")},
        "attention": attention,
        "gsc": {"daily": [{k: r[k] for k in ("date", "clicks", "impressions", "ctr", "position")} for r in daily],
                "first": first.isoformat(), "last": last.isoformat(),
                "compare_window": {"current": [cur_from, cur_to], "previous": [prev_from, prev_to]},
                "queries": queries, "pages": pages, "query_page": query_page, "quickwins": quickwins,
                "winners": winners, "losers": losers, "cannibalization": cannibal,
                "segments_monthly": segments, "segment_totals": seg_totals,
                "countries": sorted([{k: r[k] for k in ("country", "clicks", "impressions", "position")} for r in country], key=lambda r: -r["impressions"])[:10],
                "devices": [{k: r[k] for k in ("device", "clicks", "impressions", "ctr", "position")} for r in device]},
        "opportunities": opps,
        "findings": findings,
        "changes": changes,
        "tasks": tasks,
        "approvals": {"gate1": appr.get("gate1", []), "gate2": appr.get("gate2", []), "gate1_candidates": candidates},
        "market": market,
        "local": local_out,
        "sources": sources,
    }
    odir = os.path.join(OUT_ROOT, slug)
    os.makedirs(odir, exist_ok=True)
    with open(os.path.join(odir, "dashboard.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=dt.date.today().isoformat())
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today)
    idx = jload(os.path.join(ROOT, "clients", "index.json"))
    os.makedirs(OUT_ROOT, exist_ok=True)
    clients = []
    for c in idx["clients"]:
        if not c.get("active"):
            continue
        out = build_client(c["slug"], today)
        clients.append({"slug": c["slug"], "name": c["name"], "region": out["client"]["region"]})
        print(f"✓ {c['slug']}: {len(out['gsc']['queries'])} queries, {len(out['opportunities'])} opportunities, health={out['health']['status']}")
    with open(os.path.join(OUT_ROOT, "clients.json"), "w", encoding="utf-8") as f:
        json.dump({"clients": clients, "built_at": dt.datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
