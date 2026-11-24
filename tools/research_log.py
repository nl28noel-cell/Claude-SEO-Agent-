#!/usr/bin/env python3
"""Research Log / Audit Trail der Opportunity Engine.

Modell:  Event (Aktion des Agenten) → Sources (Belege) → Findings (Erkenntnisse mit source_ids) → Opportunity/Dossier
Dateien: clients/<client>/state/evidence.json      {sources: [SRC-…], findings: [FND-…]}
         clients/<client>/state/research_log.json  {events: [EVT-…]}
Semrush-Rohdaten bezahlter Abfragen: data/serp-cache/raw/<SERP-…>.json (unveränderlich, wiederverwendbar ohne Units).

Regeln: keine erfundenen Zeitpunkte, Quellen oder Kosten. Fehlt eine Angabe → None + "metadata unavailable".
`at_precision`: exact (Uhrzeit protokolliert) · date (nur Datum bekannt) · commit (Zeitpunkt = Git-Commit des Ergebnisses).

    python3 tools/research_log.py validate <client>
    python3 tools/research_log.py add-profiles <client> <OPP> <profile_dir> [--competitor-type competitor]
    python3 tools/research_log.py summary <client>
"""
import datetime as dt, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTIONS = {
    "gsc_analysis": "GSC-Auswertung", "ga4_analysis": "GA4-Auswertung", "semrush_keyword": "Semrush Keyword Research",
    "semrush_serp": "Semrush SERP Research", "web_research": "Independent Web Research", "competitor_analysis": "Wettbewerberseiten analysiert",
    "own_page_analysis": "Eigene Seite analysiert", "cannibalization": "Kannibalisierung geprüft", "content_gap": "Content Gap erstellt",
    "ia_review": "Information Architecture geprüft", "dossier": "Research Dossier", "reassessment": "Opportunity neu bewertet",
    "monitoring": "Monitoring", "draft": "Entwurf produziert", "revision": "Revision produziert", "workflow_cleanup": "Workflow Cleanup",
}
SOURCE_TYPES = {"gsc": "GSC", "ga4": "GA4", "semrush": "Semrush", "website": "Website", "competitor": "Competitor", "web_search": "Web Search", "agent": "Agent"}
PRECISION = ("exact", "date", "commit")
NA = "metadata unavailable"


def _p(client, name):
    return os.path.join(ROOT, "clients", client, "state", name + ".json")


def load(client):
    ev = json.load(open(_p(client, "evidence"), encoding="utf-8")) if os.path.exists(_p(client, "evidence")) else {"sources": [], "findings": []}
    lg = json.load(open(_p(client, "research_log"), encoding="utf-8")) if os.path.exists(_p(client, "research_log")) else {"events": []}
    return ev, lg


def save(client, ev, lg):
    for name, doc in (("evidence", ev), ("research_log", lg)):
        doc["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        json.dump(doc, open(_p(client, name), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        open(_p(client, name), "a").write("\n")


def _next(items, prefix):
    n = max([int(x["id"].split("-")[-1]) for x in items if x["id"].startswith(prefix)] or [0])
    return f"{prefix}{n + 1:03d}"


def add_source(ev, src):
    """Quelle anlegen oder vorhandene (gleicher key) wiederverwenden → id."""
    key = src.get("key") or src.get("url") or src.get("title")
    for s in ev["sources"]:
        if (s.get("key") or s.get("url") or s.get("title")) == key and s["type"] == src["type"]:
            s["opp_ids"] = sorted(set(s.get("opp_ids", [])) | set(src.get("opp_ids", [])))
            return s["id"]
    src = {"id": _next(ev["sources"], "SRC-"), **src}
    ev["sources"].append(src)
    return src["id"]


def add_finding(ev, opp, section, text, source_ids):
    f = {"id": _next(ev["findings"], "FND-"), "opp": opp, "section": section, "text": text, "source_ids": source_ids}
    ev["findings"].append(f)
    return f["id"]


def add_event(lg, e):
    e = {"id": _next(lg["events"], "EVT-"), "source_ids": [], "finding_ids": [], "units": 0, **e}
    lg["events"].append(e)
    lg["events"].sort(key=lambda x: (x["at"] or "", x["id"]))
    return e["id"]


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def log_serp(client, opp, entry, raw_path):
    """Von tools/serp.py ingest aufgerufen: bezahlte SERP-Abfrage als Quelle + Event (Live Query, Kosten, Top-Ergebnisse)."""
    ev, lg = load(client)
    sid = add_source(ev, {"type": "semrush", "key": entry["raw_id"], "opp_ids": [opp] if opp else [], "title": f"Semrush Organic Results · {entry['keyword']} · {entry['database'].upper()}",
                          "fetched": entry["fetched_at"], "fetched_precision": "exact", "url": None,
                          "semrush": {"report": "Organic Results", "endpoint": "phrase_organic", "keyword": entry["keyword"], "database": entry["database"].upper(),
                                      "display_limit": entry.get("display_limit"), "results_count": entry["lines"], "units": entry["units_spent"], "mode": "live",
                                      "raw_id": entry["raw_id"], "raw_path": os.path.relpath(raw_path, ROOT), "results": entry["results"][:10],
                                      "link": None, "link_note": "Der Semrush-Konnektor liefert keine Report-URL – Parameter und Ergebnisse sind hier vollständig dokumentiert."}})
    add_event(lg, {"at": entry["fetched_at"], "at_precision": "exact", "opp": opp, "action": "semrush_serp", "title": "Semrush SERP Research",
                   "summary": f"Organic Results für „{entry['keyword']}“ ({entry['database'].upper()}, Top {entry.get('display_limit')}) live abgefragt.",
                   "found": f"{entry['lines']} Ergebnisse · {entry['units_spent']} Units", "source_ids": [sid], "units": entry["units_spent"]})
    save(client, ev, lg)
    return sid


def add_profiles(client, opp, folder, own_host="spreewald-luftaufnahmen.de"):
    """Seitenprofile (tools/page_profile.py) als Quellen registrieren – mit echtem Abrufzeitpunkt aus dem Profil."""
    ev, lg = load(client)
    ids = []
    for f in sorted(glob.glob(os.path.join(folder, "*.json"))):
        p = json.load(open(f, encoding="utf-8"))
        own = own_host in p["domain"]
        ids.append(add_source(ev, {"type": "website" if own else "competitor", "key": p.get("final_url") or p["url"], "opp_ids": [opp],
                                   "title": p.get("title") or p["domain"], "domain": p["domain"], "url": p.get("final_url") or p["url"],
                                   "fetched": p["fetched"], "fetched_precision": "exact", "status": p.get("status"), "error": p.get("error"),
                                   "raw_path": os.path.relpath(f, ROOT),
                                   "meta": {"h1": (p.get("h1") or [None])[0], "words": p.get("words"), "faq_questions": len(p.get("faq_questions") or []),
                                            "schema_types": p.get("schema_types"), "has_form": p.get("has_form")}}))
    save(client, ev, lg)
    return ids


def validate(client):
    ev, lg = load(client)
    err, sids, fids = [], {s["id"] for s in ev["sources"]}, {f["id"] for f in ev["findings"]}
    for s in ev["sources"]:
        if s["type"] not in SOURCE_TYPES:
            err.append(f"{s['id']}: type {s['type']}")
        if s.get("fetched") is None and not s.get("fetched_note"):
            err.append(f"{s['id']}: kein Abrufzeitpunkt und kein Hinweis ({NA})")
        sm = s.get("semrush")
        if s["type"] == "semrush" and (not sm or not sm.get("endpoint") or not sm.get("database") or "units" not in sm or sm.get("mode") not in ("live", "cache")):
            err.append(f"{s['id']}: Semrush-Nachweis unvollständig (endpoint/database/units/mode)")
        if sm and sm.get("link") and not str(sm["link"]).startswith("https://"):
            err.append(f"{s['id']}: ungültiger Semrush-Link")
    for f in ev["findings"]:
        bad = [x for x in f["source_ids"] if x not in sids]
        if bad:
            err.append(f"{f['id']}: unbekannte Quellen {bad}")
    for e in lg["events"]:
        if e["action"] not in ACTIONS:
            err.append(f"{e['id']}: action {e['action']}")
        if e.get("at_precision") not in PRECISION:
            err.append(f"{e['id']}: at_precision")
        if e.get("at") and e.get("at_precision") == "date" and len(e["at"]) != 10:
            err.append(f"{e['id']}: Datumsgenauigkeit, aber Uhrzeit angegeben")
        bad = [x for x in e.get("source_ids", []) if x not in sids] + [x for x in e.get("finding_ids", []) if x not in fids]
        if bad:
            err.append(f"{e['id']}: unbekannte Referenzen {bad}")
    return err


def summary(client):
    ev, lg = load(client)
    sem = [s for s in ev["sources"] if s["type"] == "semrush"]
    known = sum((s["semrush"].get("units") or 0) for s in sem if isinstance(s["semrush"].get("units"), int))
    unknown = [s["id"] for s in sem if not isinstance(s["semrush"].get("units"), int)]
    by = {}
    for s in sem:
        k = s["semrush"]["report"]
        by.setdefault(k, {"queries": 0, "units": 0, "unknown": 0})
        by[k]["queries"] += 1
        if isinstance(s["semrush"].get("units"), int):
            by[k]["units"] += s["semrush"]["units"]
        else:
            by[k]["unknown"] += 1
    return {"events": len(lg["events"]), "sources": len(ev["sources"]), "findings": len(ev["findings"]),
            "semrush_units_known": known, "semrush_unknown_cost": unknown, "semrush_by_report": by}


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "validate":
        e = validate(a[1]); print("OK" if not e else "\n".join(e)); sys.exit(1 if e else 0)
    elif a[0] == "add-profiles":
        print(add_profiles(a[1], a[2], a[3]))
    elif a[0] == "summary":
        print(json.dumps(summary(a[1]), ensure_ascii=False, indent=2))
    else:
        sys.exit(__doc__)
