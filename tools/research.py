#!/usr/bin/env python3
"""Research-/Strategy-Stufe der Opportunity Engine (vor Gate 1).

Jede CREATE/OPTIMIZE/MERGE-Opportunity bekommt ein Dossier `clients/<client>/state/research/<OPP>.json`
mit den Abschnitten A–J. Dieses Modul prüft Dossiers, leitet den Research-Status ab und entscheidet,
ob eine Gate-1-Freigabe die Produktion erlaubt. Ablauf und Kostenreihenfolge: docs/research-strategy.md.

    python3 tools/research.py status   <client>            -> Status aller Opportunities
    python3 tools/research.py validate <client> [OPP ...]  -> Exit 1 bei Schemafehlern
    python3 tools/research.py skeleton <client> <OPP>      -> leeres Dossier (state=not_started) anlegen
    python3 tools/research.py retry-plan <client> <OPP>    -> Komponenten-Status + gezielter Retry-Plan (führt nichts aus)
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE_TYPES = ("CREATE", "OPTIMIZE", "MERGE")

# Abschnitt -> (Titel, Pflichtfelder, die nicht leer sein dürfen)
SECTIONS = {
    "A_decision": ("A · Executive Decision", ["decision", "summary", "why", "gate1_question"]),
    "B_demand": ("B · Search Demand", ["keywords"]),
    "C_serp": ("C · Live SERP", ["source", "quality", "intent_verdict"]),
    "D_competitors": ("D · Competitor Insights", None),
    "E_gap": ("E · Content Gap", ["competitors_cover", "we_cover", "we_miss", "outperform"]),
    "F_scope": ("F · Recommended Page Scope", ["core_message", "search_intent", "audience", "key_questions", "service_info", "trust_proof", "conversion_goal", "not_on_page"]),
    "G_structure": ("G · Proposed Structure", ["h1", "sections"]),
    "H_ia": ("H · Information Architecture", ["current", "recommended", "consolidation", "keyword_ownership", "internal_links", "cannibalization", "decision"]),
    "I_win": ("I · How We Can Win", None),
    "J_risks": ("J · Risks / Unknowns", None),
}
DECISIONS = ("CREATE", "OPTIMIZE", "MERGE", "MONITOR", "IGNORE")
STATES = ("not_started", "incomplete", "complete_with_limits", "complete")
SERP_QUALITY = ("validated", "indicative", "missing")
READY = ("complete", "complete_with_limits")


def path(client, opp):
    return os.path.join(ROOT, "clients", client, "state", "research", f"{opp}.json")


def load(client, opp):
    p = path(client, opp)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def _empty(v):
    return v is None or v == "" or v == [] or v == {}


def validate(doc):
    """Schemafehler (Liste). Leere Abschnitte sind KEIN Schemafehler, sondern machen den Status unvollständig."""
    err = []
    if doc.get("schema") != 1:
        err.append("schema != 1")
    for k in ("opp_id", "client", "version", "updated", "status", "method"):
        if k not in doc:
            err.append(f"Feld fehlt: {k}")
    st = (doc.get("status") or {}).get("state")
    if st not in STATES:
        err.append(f"status.state ungültig: {st}")
    dec = (doc.get("A_decision") or {}).get("decision")
    if dec and dec not in DECISIONS:
        err.append(f"A_decision.decision ungültig: {dec}")
    hd = (doc.get("H_ia") or {}).get("decision")
    if dec and hd and hd != dec:
        err.append(f"Entscheidung widersprüchlich: A={dec}, H={hd}")
    q = (doc.get("C_serp") or {}).get("quality")
    if q and q not in SERP_QUALITY:
        err.append(f"C_serp.quality ungültig: {q}")
    m = doc.get("method") or {}
    if m.get("semrush_units_used", 0) and not m.get("semrush_approved_by"):
        err.append("Semrush-Units verbraucht ohne Freigabevermerk (method.semrush_approved_by)")
    C = doc.get("C_serp") or {}
    rel = ("business_competitor", "platform", "software", "guide", "directory", "partner", "own", "other", "unclassified")
    for r in (C.get("serp_competitors") or []) + (C.get("research_competitors") or []):
        if r.get("relevance") not in rel:
            err.append(f"C_serp relevance ungültig: {r.get('domain')}")
    # SERP competitors = von Semrush als rankend bestätigt: Quelle + Position + Keyword Pflicht
    for r in C.get("serp_competitors") or []:
        if not str(r.get("source", "")).startswith("semrush") or not isinstance(r.get("position"), int) or not r.get("keyword"):
            err.append(f"serp_competitors ohne Semrush-Quelle/Position/Keyword: {r.get('domain')}")
    for r in C.get("research_competitors") or []:
        if r.get("position") not in (None, "", "–"):
            err.append(f"research_competitors dürfen keine Rankingposition tragen: {r.get('domain')}")
    if C.get("quality") == "validated" and not C.get("serp_competitors"):
        err.append("C_serp.quality=validated ohne serp_competitors (Semrush)")
    web = (C.get("validation") or {}).get("independent_web") or {}
    if web and web.get("status") not in ("completed", "pending"):
        err.append(f"validation.independent_web.status ungültig: {web.get('status')}")
    if web.get("status") == "completed" and (not web.get("keywords") or not web.get("date")):
        err.append("Independent Web Research ohne Keywords/Datum")
    if web.get("positions"):
        err.append("Independent Web Research darf keine Rankingpositionen enthalten")
    P = doc.get("P_diagnosis") or {}
    for x in P.get("change_summary") or []:
        if x.get("action") not in ("KEEP", "EDIT", "NEW", "REMOVE", "REDUCE", "KEEP/EDIT"):
            err.append(f"change_summary action ungültig: {x.get('area')}")
    for x in P.get("sensitive_changes") or []:
        if not all(x.get(k) for k in ("element", "current", "proposed", "reason", "ranking_risk")):
            err.append(f"sensitive_change unvollständig: {x.get('element')}")
    for x in (doc.get("G_structure") or {}).get("sections") or []:
        if x.get("action") and x["action"] not in ("KEEP", "EDIT", "NEW", "REMOVE", "REDUCE"):
            err.append(f"G_structure action ungültig: {x.get('h2')}")
    if "results" in C:
        err.append("C_serp.results ist veraltet → serp_competitors / research_competitors")
    return err


def missing_sections(doc):
    out = []
    for k, (title, req) in SECTIONS.items():
        v = doc.get(k)
        if _empty(v):
            out.append(title)
        elif req:
            gaps = [f for f in req if _empty(v.get(f))]
            if gaps:
                out.append(f"{title} ({', '.join(gaps)})")
    C = doc.get("C_serp") or {}
    if C and _empty(C.get("serp_competitors")) and _empty(C.get("research_competitors")):
        out.append("C · Live SERP (keine Wettbewerber)")
    # OPTIMIZE/MERGE: Current Page Diagnosis ist Pflicht (Preserve what works → fix what is weak → add what is missing)
    if ((doc.get("A_decision") or {}).get("decision") in ("OPTIMIZE", "MERGE")):
        P = doc.get("P_diagnosis") or {}
        gaps = [f for f in ("works_well", "weak", "missing", "keep", "improve", "add", "recommended_changes", "expected_benefit", "change_summary") if _empty(P.get(f))]
        if not P:
            out.append("Current Page Diagnosis ausstehend")
        elif gaps:
            out.append(f"Current Page Diagnosis ({', '.join(gaps)})")
    # Standard: Independent Web Research je Primary Keyword (kostet keine Units) – auch wenn Semrush vorliegt
    if C and ((C.get("validation") or {}).get("independent_web") or {}).get("status") != "completed":
        out.append("Independent Web Research ausstehend")
    return out


def derive(doc):
    """Effektiver Status: der deklarierte Status wird nie „besser“ als die Daten hergeben."""
    if not doc:
        return {"state": "not_started", "label": "Research not started", "missing": ["Kein Dossier"], "limits": [], "pending": []}
    st = doc.get("status") or {}
    miss = missing_sections(doc)
    pending = list(st.get("pending") or [])
    limits = list(st.get("limits") or [])
    state = st.get("state", "incomplete")
    if state in READY and (miss or pending):
        state = "incomplete"
    C = doc.get("C_serp") or {}
    if state == "complete" and (C.get("quality") != "validated" or not C.get("serp_competitors")):
        state = "complete_with_limits"
        if not limits:
            limits = ["SERP nicht validiert (indikativ)"]
    if state == "complete_with_limits" and not limits:
        state = "complete"
    reason = (pending or miss or ["Research nicht begonnen"])[0]
    label = {"complete": "Research complete", "complete_with_limits": "Research complete · with limits",
             "incomplete": f"Research incomplete – {reason}", "not_started": "Research not started"}[state]
    return {"state": state, "label": label, "missing": miss, "limits": limits, "pending": pending}


# ---------------------------------------------------------------- Research-Komponenten & gezielter Retry
# key: (Label, Kosten: free|cache|paid|agent, Abhängigkeiten). Retry holt nur Fehlendes/Fehlgeschlagenes/Veraltetes nach
# und die davon abhängigen Auswertungen – Vorhandenes, Valides, Frisches wird wiederverwendet.
COMPONENTS = {
    "gsc": ("GSC-Auswertung", "free", []),
    "semrush_keywords": ("Semrush Keyword-Daten", "cache", []),
    "own_page": ("Eigene Seite analysiert", "free", []),
    "web_research": ("Independent Web Research", "free", []),
    "competitors": ("Competitor Analysis", "free", ["web_research"]),
    "serp": ("Semrush SERP", "paid", []),
    "content_gap": ("Content Gap", "agent", ["competitors", "own_page"]),
    "diagnosis": ("Current Page Diagnosis", "agent", ["own_page", "gsc"]),
    "strategy": ("Scope · Struktur · Architektur (F/G/H)", "agent", ["content_gap"]),
}
STALE_DAYS = {"own_page": 30, "web_research": 60, "competitors": 60, "serp": 30}
HOW = {
    "gsc": "GSC-Daten des Clusters aus dashboard.json übernehmen (Query, Query × Page, 90 Tage) → Abschnitt B",
    "semrush_keywords": "Nur aus dem Keyword-Cache (data/keyword-cache.csv); fehlende Keywords NICHT abfragen ohne Budget-Freigabe",
    "own_page": "python3 tools/page_profile.py <existing_page-URL> --out clients/<c>/data/research/<OPP>/diagnosis",
    "web_research": "WebSearch (Standard + Extended) für das Primary Keyword, Secondary nur bei anderem Intent → C.research_competitors + C.validation.independent_web (keine Positionen)",
    "competitors": "python3 tools/page_profile.py <Anbieter-URLs> --out clients/<c>/data/research/<OPP>/pages → D_competitors (Hosts müssen in der Umgebung erlaubt sein, sonst Komponente 'blocked')",
    "serp": "Nur wenn tools/serp.py plan → verdict 'run': Semrush phrase_organic, danach serp.py ingest … --client --opp",
    "content_gap": "E_gap aus Wettbewerbern + eigener Seite + Business-Profil neu ableiten",
    "diagnosis": "P_diagnosis (KEEP/IMPROVE/ADD/REMOVE, Sensitive Changes, Change Summary) mit Ranking Protection aktualisieren",
    "strategy": "F/G/H/I/J prüfen und nur anpassen, wenn sich aus den neuen Ergebnissen etwas ändert",
}


def _age_days(iso, today=None):
    import datetime as dt
    if not iso:
        return None
    try:
        d = dt.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None
    return ((today or dt.date.today()) - d).days


def components(doc, opp=None, ctx=None):
    """Status je Research-Komponente: complete · missing · failed · stale · blocked_budget · blocked · n/a."""
    doc, opp, ctx = doc or {}, opp or {}, ctx or {}
    out = {}
    B, C, D, E, F, G, H, P = (doc.get(k) or {} for k in ("B_demand", "C_serp", "D_competitors", "E_gap", "F_scope", "G_structure", "H_ia", "P_diagnosis"))
    D = doc.get("D_competitors") or []
    kws = B.get("keywords") or []
    failed = (doc.get("status") or {}).get("failed") or {}       # vom Runner gemeldete Fehlschläge {key: Ursache}
    def put(k, st, why=""):
        if k in failed and st != "complete":
            st, why = "failed", failed[k]
        out[k] = {"key": k, "label": COMPONENTS[k][0], "cost": COMPONENTS[k][1], "status": st, "why": why}
    put("gsc", "complete" if (B.get("cluster") or any(x.get("gsc_impr") is not None for x in kws)) else "missing")
    put("semrush_keywords", "complete" if any(x.get("volume") is not None for x in kws) else "missing")
    decision = (doc.get("A_decision") or {}).get("decision") or opp.get("type")
    if opp.get("existing_page") or decision in ("OPTIMIZE", "MERGE"):
        prof = ctx.get("profile")
        if not prof:
            put("own_page", "missing", "Kein Seitenprofil mit Abschnitten")
        elif prof.get("error"):
            put("own_page", "failed", f"Abruf fehlgeschlagen: {prof['error'][:80]}")
        elif (_age_days(prof.get("fetched"), ctx.get("today")) or 0) > STALE_DAYS["own_page"]:
            put("own_page", "stale", f"Profil älter als {STALE_DAYS['own_page']} Tage")
        else:
            put("own_page", "complete")
    else:
        out["own_page"] = {"key": "own_page", "label": COMPONENTS["own_page"][0], "cost": "free", "status": "n/a", "why": "Keine bestehende Seite"}
    web = (C.get("validation") or {}).get("independent_web") or {}
    if web.get("status") == "completed":
        put("web_research", "stale" if (_age_days(web.get("date"), ctx.get("today")) or 0) > STALE_DAYS["web_research"] else "complete",
            f"älter als {STALE_DAYS['web_research']} Tage" if (_age_days(web.get("date"), ctx.get("today")) or 0) > STALE_DAYS["web_research"] else "")
    else:
        put("web_research", "failed" if web.get("status") == "failed" else "missing")
    put("competitors", "complete" if D else "missing")
    plan = ctx.get("serp_plan") or {}
    if C.get("serp_competitors"):
        put("serp", "complete")
    elif plan.get("verdict") == "budget_hold":
        put("serp", "blocked_budget", plan.get("why") or "Budget-Reserve")
    elif plan.get("verdict") == "approval_required":
        put("serp", "blocked_budget", "Freigabe für kostenpflichtige Abfrage nötig")
    elif plan.get("verdict") == "run":
        put("serp", "missing", "Budget erlaubt die Abfrage")
        out["serp"]["budget_ok"] = True
    else:
        put("serp", "blocked_budget", "Kein Budget-Plan (Keywords noch nicht festgelegt) – keine kostenpflichtige Abfrage")
    put("content_gap", "complete" if (E.get("competitors_cover") and E.get("we_miss")) else "missing")
    if decision in ("OPTIMIZE", "MERGE"):
        put("diagnosis", "complete" if all(P.get(f) for f in ("keep", "improve", "add", "change_summary")) else "missing")
    put("strategy", "complete" if (F.get("core_message") and G.get("sections") and H.get("decision")) else "missing")
    return out


def retry_plan(comps):
    """Welche Schritte holt ein Retry nach? Fehlend/fehlgeschlagen/veraltet + abhängige Auswertungen; nie Budget-Schutz umgehen."""
    todo = {k for k, c in comps.items() if c["status"] in ("missing", "failed", "stale") and c["cost"] != "paid"}
    paid_ok = [k for k, c in comps.items() if c["cost"] == "paid" and c["status"] in ("missing", "failed", "stale") and c.get("budget_ok")]
    todo |= set(paid_ok)                       # kostenpflichtig nur, wenn das Budget es erlaubt (Status nicht blocked_budget)
    changed = True
    while changed:                             # abhängige Auswertungen neu ableiten
        changed = False
        for k, (_, _, deps) in COMPONENTS.items():
            if k in comps and comps[k]["status"] != "n/a" and k not in todo and any(d in todo for d in deps):
                todo.add(k); changed = True
    order = list(COMPONENTS)
    run = [k for k in order if k in todo]
    blocked = [k for k, c in comps.items() if c["status"] in ("blocked_budget", "blocked")]
    reuse = [k for k, c in comps.items() if c["status"] == "complete" and k not in todo]
    return {"run": run, "blocked": blocked, "reuse": reuse,
            "only_paid_missing": not run and bool(blocked),
            "steps": [{"key": k, "label": COMPONENTS[k][0], "cost": COMPONENTS[k][1], "how": HOW[k],
                       "reason": comps[k]["status"] if comps[k]["status"] != "complete" else "abhängig"} for k in run],
            "explain": ("Nur kostenpflichtige Research fehlt (" + ", ".join(comps[k]["label"] + ": " + (comps[k]["why"] or comps[k]["status"]) for k in blocked) + ") – Retry kann aktuell nicht ausgeführt werden.")
                       if not run and blocked else ""}


def strategy_ok(gate1, research):
    """Darf produziert werden? Gate 1 muss sich auf genau diese Research-Version beziehen
    (oder ein bewusster Override sein). Alte Gate-1-Freigaben ohne Research-Bezug zählen nicht."""
    gate1 = gate1 or {}
    if gate1.get("status") != "approved":
        return False, "gate1_missing"
    if gate1.get("research_override"):
        return True, "override"
    if not research:
        return False, "research_missing"
    if derive(research)["state"] not in READY:
        return False, "research_incomplete"
    if gate1.get("research_version") != research.get("version"):
        return False, "strategy_not_approved"
    return True, "ok"


def summary(doc):
    """Kompakte Form fürs Dashboard (Karten, Tabellen)."""
    d = derive(doc)
    a = (doc or {}).get("A_decision") or {}
    return {"state": d["state"], "label": d["label"], "version": (doc or {}).get("version"), "updated": (doc or {}).get("updated"),
            "decision": a.get("decision"), "confidence": a.get("confidence"), "summary": a.get("summary"),
            "serp_quality": ((doc or {}).get("C_serp") or {}).get("quality"),
            "units": ((doc or {}).get("method") or {}).get("semrush_units_used", 0),
            "serp_competitors": len(((doc or {}).get("C_serp") or {}).get("serp_competitors") or [])}


def all_for(client, opportunities):
    """{opp_id: {"doc":…, "status":…}} für alle Opportunities, die die Stufe durchlaufen."""
    out = {}
    for o in opportunities:
        if o.get("type") not in STAGE_TYPES:
            continue
        doc = load(client, o["id"])
        out[o["id"]] = {"doc": doc, "status": derive(doc), "summary": summary(doc)}
    return out


def skeleton(client, opp):
    return {"schema": 1, "opp_id": opp, "client": client, "version": 0, "updated": None, "author": "agent",
            "status": {"state": "not_started", "limits": [], "pending": []},
            "method": {"cost_order": [], "semrush_units_used": 0, "serp_source": None, "serp_quality": "missing"},
            **{k: ([] if k in ("D_competitors", "I_win", "J_risks") else {}) for k in SECTIONS}, "sources": []}


def _opps(client):
    return json.load(open(os.path.join(ROOT, "clients", client, "state", "opportunities.json"), encoding="utf-8"))["opportunities"]


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, client = sys.argv[1], sys.argv[2]
    if cmd == "status":
        for oid, r in all_for(client, _opps(client)).items():
            print(f"{oid}: {r['status']['label']}" + (f" · v{r['doc']['version']}" if r["doc"] else ""))
    elif cmd == "validate":
        ids = sys.argv[3:] or [o["id"] for o in _opps(client) if o.get("type") in STAGE_TYPES]
        bad = 0
        for oid in ids:
            doc = load(client, oid)
            if not doc:
                continue
            e = validate(doc)
            bad += bool(e)
            print(f"{oid}: {'OK' if not e else '; '.join(e)} · {derive(doc)['label']}")
        sys.exit(1 if bad else 0)
    elif cmd == "retry-plan":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import serp, glob
        oid = sys.argv[3]
        o = next((x for x in _opps(client) if x["id"] == oid), {})
        fs = sorted(glob.glob(os.path.join(ROOT, "clients", client, "data", "research", oid, "diagnosis", "*.json")))
        ctx = {"profile": json.load(open(fs[-1], encoding="utf-8")) if fs else None, "serp_plan": serp.plan(client, oid) if load(client, oid) else {}}
        comps = components(load(client, oid), o, ctx)
        print(json.dumps({"opp": oid, "components": comps, **retry_plan(comps)}, ensure_ascii=False, indent=2))
    elif cmd == "skeleton":
        p = path(client, sys.argv[3])
        if os.path.exists(p):
            sys.exit(f"existiert bereits: {p}")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(skeleton(client, sys.argv[3]), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(p)
    else:
        sys.exit(__doc__)
