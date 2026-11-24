#!/usr/bin/env python3
"""Research-/Strategy-Stufe der Opportunity Engine (vor Gate 1).

Jede CREATE/OPTIMIZE/MERGE-Opportunity bekommt ein Dossier `clients/<client>/state/research/<OPP>.json`
mit den Abschnitten A–J. Dieses Modul prüft Dossiers, leitet den Research-Status ab und entscheidet,
ob eine Gate-1-Freigabe die Produktion erlaubt. Ablauf und Kostenreihenfolge: docs/research-strategy.md.

    python3 tools/research.py status   <client>            -> Status aller Opportunities
    python3 tools/research.py validate <client> [OPP ...]  -> Exit 1 bei Schemafehlern
    python3 tools/research.py skeleton <client> <OPP>      -> leeres Dossier (state=not_started) anlegen
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
    elif cmd == "skeleton":
        p = path(client, sys.argv[3])
        if os.path.exists(p):
            sys.exit(f"existiert bereits: {p}")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(skeleton(client, sys.argv[3]), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(p)
    else:
        sys.exit(__doc__)
