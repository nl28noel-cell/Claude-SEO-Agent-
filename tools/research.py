#!/usr/bin/env python3
"""Research-/Strategy-Stufe der Opportunity Engine (vor Gate 1).

Jede CREATE/OPTIMIZE/MERGE-Opportunity bekommt ein Dossier `clients/<client>/state/research/<OPP>.json`
mit den Abschnitten A–J. Dieses Modul prüft Dossiers, leitet den Research-Status ab und entscheidet,
ob eine Gate-1-Freigabe die Produktion erlaubt. Ablauf und Kostenreihenfolge: docs/research-strategy.md.

    python3 tools/research.py status   <client>            -> Status aller Opportunities
    python3 tools/research.py validate <client> [OPP ...]  -> Exit 1 bei Schemafehlern
    python3 tools/research.py skeleton <client> <OPP>      -> leeres Dossier (state=not_started) anlegen
    python3 tools/research.py export-db <client> <OPP> <out.json>  -> Dossier + Log + Quellen als db-Dokument research/<OPP> (ArtifactData set file_path)
    python3 tools/research.py import-db <client> <dir>     -> db-Export (ArtifactData list collection=research out_dir) ins Repository übernehmen
    python3 tools/research.py retry-plan <client> <OPP>    -> Komponenten-Status + gezielter Retry-Plan (führt nichts aus)
"""
import json, os, re, sys

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
    cq = competitor_quality(doc.get("D_competitors"), C)
    if state == "complete" and cq["total"] and cq["analyzed"] < 3:
        state = "complete_with_limits"
        limits = limits + [f"Wettbewerber: {cq['analyzed']} analysierte Seite(n), {cq['snippet_only']} nur Suchergebnis-Snippets"]
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


STEP_STATES = ("not_started", "queued", "running", "complete", "complete_with_limits", "blocked", "failed", "budget_hold", "stale", "n/a")
DONE = ("complete", "complete_with_limits")
NETWORK_PATTERNS = ("proxy 403", "connect tunnel failed", "not allowed", "nicht freigegeben", "no rule allows", "dns")
# Wettbewerber-Evidenz: Qualität je Eintrag in D_competitors[].evidence
EVIDENCE = {"page_analyzed": "Seite vollständig analysiert", "cached_profile": "aus Cache/früherer Analyse", "fetch_summary": "per Web-Abruf zusammengefasst",
            "snippet_only": "nur Suchergebnis-Snippet (keine analysierte Seite)"}


def classify_failure(reason):
    """network_blocked (Proxy/Allowlist der Umgebung) · site_blocked (Website antwortet 403/401) · tool_missing · error."""
    r = str(reason or "").lower()
    if any(x in r for x in NETWORK_PATTERNS):
        return "network_blocked"
    if "tool" in r and ("fehlt" in r or "missing" in r or "nicht verfügbar" in r):
        return "tool_missing"
    if any(x in r for x in ("http 403", "http 401", "status 403", "forbidden")):
        return "site_blocked"
    return "error"


def competitor_quality(D, C=None):
    """Bewertet die vorhandene Wettbewerber-Evidenz: analysierte Seiten vs. Snippets."""
    D = D or []
    q = {k: sum(1 for x in D if (x.get("evidence") or "page_analyzed") == k) for k in EVIDENCE}
    full = q["page_analyzed"] + q["cached_profile"] + q["fetch_summary"]
    return {"counts": q, "analyzed": full, "snippet_only": q["snippet_only"], "total": len(D),
            "research_competitors": len((C or {}).get("research_competitors") or [])}


def competitors_from_snippets(C, failure=None, limit=8):
    """Fallback-Stufe 4: Wettbewerber aus der Independent Web Research (Suchergebnis-Beschreibungen) – ausdrücklich als
    Snippet-Evidenz gekennzeichnet. Keine Seite gilt dadurch als analysiert."""
    out = []
    for r in (C or {}).get("research_competitors") or []:
        if r.get("relevance") not in (None, "business_competitor", "competitor", "direct"):
            continue
        out.append({"domain": r.get("domain"), "url": r.get("url"), "page_type": r.get("page_type"), "region": r.get("region"),
                    "evidence": "snippet_only", "evidence_note": EVIDENCE["snippet_only"] + (f" · Live-Abruf: {failure}" if failure else ""),
                    "topics": [], "observations": r.get("note"), "takeaway": None, "found_via": r.get("found_via")})
        if len(out) >= limit:
            break
    return out


def components(doc, opp=None, ctx=None):
    """Status je Research-Schritt: not_started · complete · complete_with_limits · failed · blocked · budget_hold · stale · n/a.
    Ein fehlgeschlagener/blockierter Schritt blockiert keine unabhängigen Schritte; abhängige Auswertungen werden mit
    eingeschränkter Basis als complete_with_limits geführt."""
    doc, opp, ctx = doc or {}, opp or {}, ctx or {}
    out = {}
    B, C, E, F, G, H, P = (doc.get(k) or {} for k in ("B_demand", "C_serp", "E_gap", "F_scope", "G_structure", "H_ia", "P_diagnosis"))
    D = doc.get("D_competitors") or []
    kws = B.get("keywords") or []
    failed = (doc.get("status") or {}).get("failed") or {}       # vom Runner gemeldete Fehlschläge {key: Ursache}
    def put(k, st, why="", **extra):
        if k in failed and st not in DONE:
            kind = classify_failure(failed[k])
            st, why = ("blocked" if kind == "network_blocked" else "failed"), failed[k]
            extra["failure_kind"] = kind
        out[k] = {"key": k, "label": COMPONENTS[k][0], "cost": COMPONENTS[k][1], "status": st, "why": why, **extra}
    put("gsc", "complete" if (B.get("cluster") or any(x.get("gsc_impr") is not None for x in kws)) else "not_started")
    sem_ok = [x for x in kws if x.get("volume") is not None]
    put("semrush_keywords", ("complete" if len(sem_ok) == len(kws) else "complete_with_limits") if sem_ok else "not_started",
        "" if len(sem_ok) == len(kws) else f"{len(kws) - len(sem_ok)} Keyword(s) nicht im Cache – Abfrage nur mit Budgetfreigabe")
    decision = (doc.get("A_decision") or {}).get("decision") or opp.get("type")
    if opp.get("existing_page") or decision in ("OPTIMIZE", "MERGE"):
        prof = ctx.get("profile")
        if not prof:
            put("own_page", "not_started", "Kein Seitenprofil mit Abschnitten")
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
        old = (_age_days(web.get("date"), ctx.get("today")) or 0) > STALE_DAYS["web_research"]
        put("web_research", "stale" if old else "complete", f"älter als {STALE_DAYS['web_research']} Tage" if old else "")
    else:
        put("web_research", "failed" if web.get("status") == "failed" else "not_started")
    cq = competitor_quality(D, C)
    if cq["analyzed"] >= 3:
        put("competitors", "complete", f"{cq['analyzed']} Seiten analysiert", quality=cq)
    elif cq["total"]:
        out["competitors"] = {"key": "competitors", "label": COMPONENTS["competitors"][0], "cost": "free", "status": "complete_with_limits", "quality": cq,
                              "why": f"{cq['analyzed']} analysierte Seite(n), {cq['snippet_only']} nur als Suchergebnis-Snippet" + (f" · Live-Abruf: {failed['competitors']}" if failed.get("competitors") else ""),
                              "failure_kind": classify_failure(failed.get("competitors")) if failed.get("competitors") else None}
    else:
        put("competitors", "not_started", quality=cq)
    plan = ctx.get("serp_plan") or {}
    if C.get("serp_competitors"):
        put("serp", "complete")
    elif plan.get("verdict") == "run":
        put("serp", "not_started", "Budget erlaubt die Abfrage")
        out["serp"]["budget_ok"] = True
    else:
        put("serp", "budget_hold", plan.get("why") or ("Freigabe für kostenpflichtige Abfrage nötig" if plan.get("verdict") == "approval_required"
                                                         else "Budget-Reserve – keine kostenpflichtige Abfrage ohne Freigabe"))
    limited_base = out["competitors"]["status"] != "complete"
    if E.get("competitors_cover") and E.get("we_miss"):
        put("content_gap", "complete_with_limits" if limited_base else "complete", "vorläufig – Wettbewerberbasis eingeschränkt" if limited_base else "")
    else:
        put("content_gap", "not_started")
    if decision in ("OPTIMIZE", "MERGE"):
        put("diagnosis", "complete" if all(P.get(f) for f in ("keep", "improve", "add", "change_summary")) else "not_started")
    if F.get("core_message") and G.get("sections") and H.get("decision"):
        put("strategy", "complete_with_limits" if limited_base or out["serp"]["status"] != "complete" else "complete",
            "auf eingeschränkter Wettbewerber-/SERP-Basis" if limited_base or out["serp"]["status"] != "complete" else "")
    else:
        put("strategy", "not_started")
    return out


def progress(comps):
    """Gesamtfortschritt aus den Schritten (ohne n/a; kostenpflichtige SERP zählt separat als Budget Hold)."""
    rel = {k: c for k, c in comps.items() if c["status"] != "n/a" and c["cost"] != "paid"}
    done = [k for k, c in rel.items() if c["status"] in DONE]
    lim = [k for k, c in rel.items() if c["status"] == "complete_with_limits"]
    bad = [k for k, c in rel.items() if c["status"] in ("blocked", "failed")]
    hold = [k for k, c in comps.items() if c["status"] == "budget_hold"]
    n, t = len(done), len(rel)
    if n == 0 and not bad:
        overall, label = "not_started", "Research not started"
    elif n == t:
        overall, label = ("complete_with_limits" if lim or hold else "complete"), (f"Research complete with limitations – {n}/{t} steps" if lim or hold else f"Research complete – {n}/{t} steps")
    else:
        overall, label = "partial", f"Research partially completed – {n}/{t} steps"
    return {"overall": overall, "label": label, "done": n, "total": t, "limited": lim, "problems": bad, "budget_hold": hold,
            "steps": {k: c["status"] for k, c in comps.items()}}


def retry_plan(comps):
    """Welche Schritte holt ein Retry nach? Nicht gestartet/fehlgeschlagen/veraltet + abhängige Auswertungen; nie Budget-Schutz
    umgehen. Netzwerk-blockierte Schritte werden NICHT mit derselben Methode wiederholt, sondern mit der Fallback-Kette."""
    todo = {k for k, c in comps.items() if c["status"] in ("not_started", "failed", "stale") and c["cost"] != "paid"}
    fallback = {k for k, c in comps.items() if c["status"] == "blocked" and c.get("failure_kind") == "network_blocked"}
    todo |= fallback
    if comps.get("competitors", {}).get("status") == "complete_with_limits" and comps["competitors"].get("failure_kind") != "network_blocked":
        todo.add("competitors")                # erneuter Versuch für die nicht analysierten Seiten (andere Methode/Hosts)
    paid_ok = [k for k, c in comps.items() if c["cost"] == "paid" and c["status"] in ("not_started", "failed", "stale") and c.get("budget_ok")]
    todo |= set(paid_ok)
    changed = True
    while changed:
        changed = False
        for k, (_, _, deps) in COMPONENTS.items():
            if k in comps and comps[k]["status"] not in ("n/a",) and k not in todo and any(d in todo for d in deps):
                todo.add(k); changed = True
    run = [k for k in COMPONENTS if k in todo]
    hold = [k for k, c in comps.items() if c["status"] == "budget_hold"]
    reuse = [k for k, c in comps.items() if c["status"] in DONE and k not in todo]
    steps = []
    for k in run:
        how = HOW[k]
        if k == "competitors":
            how = COMPETITOR_FALLBACK if k in fallback or comps[k]["status"] == "complete_with_limits" else HOW[k] + " · bei Netzwerkfehler sofort Fallback-Kette: " + COMPETITOR_FALLBACK
        steps.append({"key": k, "label": COMPONENTS[k][0], "cost": COMPONENTS[k][1], "how": how,
                      "reason": comps[k]["status"] if k in comps and comps[k]["status"] not in DONE else "abhängig",
                      "method": "fallback" if k in fallback else "standard"})
    blockers = []
    if comps.get("competitors", {}).get("failure_kind") == "network_blocked":
        blockers.append({"step": "competitors", "action": "Optional: Wettbewerber-Hosts in der Umgebung „Claude-SEO-Agent“ (Settings → Network) freigeben, damit Seiten vollständig analysiert werden können. Ohne Freigabe läuft die Analyse mit Snippet-Evidenz weiter (eingeschränkt)."})
    return {"run": run, "blocked": hold, "budget_hold": hold, "reuse": reuse, "fallback": sorted(fallback),
            "only_paid_missing": not run and bool(hold), "steps": steps, "blockers": blockers,
            "explain": ("Alle kostenfreien Schritte sind erledigt; offen ist nur die kostenpflichtige SERP (" + ", ".join(comps[k]["label"] + ": " + (comps[k]["why"] or comps[k]["status"]) for k in hold) + ") – Budget-Freigabe nötig.")
                       if not run and hold else ""}


COMPETITOR_FALLBACK = ("1) vorhandene Wettbewerber-Evidenz aus evidence.json/Profilen wiederverwenden · 2) Independent Web Research (WebSearch) für Anbieter + Beschreibungen · "
                       "3) nur erreichbare Seiten per tools/page_profile.py bzw. WebFetch analysieren (Hosts ohne Freigabe NICHT erneut abrufen) · "
                       "4) Suchergebnis-Snippets: research.py competitors_from_snippets → D_competitors mit evidence=snippet_only („Ein Suchsnippet ist keine vollständig analysierte Wettbewerber-Seite“). Jede Quelle mit Evidenzqualität kennzeichnen; kein Umgehen von Proxy/Firewall.")


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


# ---------------------------------------------------------------- Persistenz unabhängig von Git (Artifact-db, Collection "research")
# Der Runner kann nicht ins Repository pushen (F-025). Jeder Research-Schritt schreibt deshalb das Dossier plus die zugehörigen
# Research-Log-Ereignisse und Quellen als Dokument research/<OPP> in die Artifact-db (ArtifactData set, file_path).
# Das Dashboard liest dieses Dokument live; Sessions mit Repo-Zugriff übernehmen es per import-db ins Repository.
def export_db(client, opp, comps=None):
    import research_log as RL
    doc = load(client, opp)
    if not doc:
        raise SystemExit(f"{opp}: kein Dossier")
    ev, lg = RL.load(client)
    events = [e for e in lg["events"] if e.get("opp") == opp]
    sids = {i for e in events for i in e.get("source_ids", [])} | {s["id"] for s in ev["sources"] if opp in (s.get("opp_ids") or [])}
    comps = comps or comps_for(client, opp)
    import datetime as dt
    return {"schema": 1, "opp_id": opp, "client": client, "version": doc.get("version"), "updated": doc.get("updated"),
            "synced_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "status": derive(doc), "summary": summary(doc), "progress": progress(comps),
            "components": [{"key": k, "label": c["label"], "status": c["status"], "why": c.get("why", ""), "cost": c["cost"],
                            **{x: c[x] for x in ("failure_kind", "quality") if c.get(x)}} for k, c in comps.items()],
            "retry_plan": retry_plan(comps),
            "dossier": doc, "events": events, "sources": [x for x in ev["sources"] if x["id"] in sids],
            "findings": [f for f in ev["findings"] if f.get("opp") == opp]}


def import_db(client, folder):
    """db-Dokumente research/<OPP> ins Repository übernehmen: neuere Dossier-Version gewinnt; Log/Quellen per Schlüssel ergänzt (nie gelöscht)."""
    import glob as _g, research_log as RL
    files = _g.glob(os.path.join(folder, "research", "*.json")) or _g.glob(os.path.join(folder, "*.json"))
    ev, lg = RL.load(client)
    out, any_change = [], False
    for f in sorted(files):
        j = json.load(open(f, encoding="utf-8")); d = j.get("data", j)
        opp, dos = d.get("opp_id"), d.get("dossier")
        if not opp or not dos:
            continue
        cur = load(client, opp)
        newer = not cur or (dos.get("version") or 0) > (cur.get("version") or 0) or \
            ((dos.get("version") or 0) == (cur.get("version") or 0) and str(dos.get("updated") or "") > str(cur.get("updated") or ""))
        keys = {(x.get("key") or x.get("url") or x.get("title"), x["type"]) for x in ev["sources"]}
        idmap, changed = {}, False
        for src in d.get("sources") or []:
            k = (src.get("key") or src.get("url") or src.get("title"), src["type"])
            if k in keys:
                idmap[src["id"]] = next(x["id"] for x in ev["sources"] if (x.get("key") or x.get("url") or x.get("title"), x["type"]) == k)
            else:
                old = src["id"]; nid = RL.add_source(ev, {kk: v for kk, v in src.items() if kk != "id"}); idmap[old] = nid; keys.add(k); changed = True
        remap = lambda ids: [idmap.get(i, i) for i in ids or []]
        fmap = {}
        have_f = {(f.get("opp"), f.get("section"), f.get("text")): f["id"] for f in ev["findings"]}
        for f in d.get("findings") or []:
            k = (f.get("opp"), f.get("section"), f.get("text"))
            if k in have_f:
                fmap[f["id"]] = have_f[k]
            else:
                fmap[f["id"]] = RL.add_finding(ev, f.get("opp"), f.get("section"), f.get("text"), remap(f.get("source_ids"))); changed = True
        if newer:
            # Quellen-IDs im Dossier auf die lokale Nummerierung abbilden (Runner kann parallel andere IDs vergeben haben)
            txt = json.dumps(dos, ensure_ascii=False)
            moved = {a: b for a, b in idmap.items() if a != b}
            if moved:
                txt = re.sub(r"SRC-\d+", lambda m: moved.get(m.group(0), m.group(0)), txt)
            json.dump(json.loads(txt), open(path(client, opp), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            open(path(client, opp), "a").write("\n")
        have = {(e.get("at"), e.get("title"), e.get("opp")) for e in lg["events"]}
        added = 0
        for e in d.get("events") or []:
            if (e.get("at"), e.get("title"), e.get("opp")) not in have:
                RL.add_event(lg, {**{kk: v for kk, v in e.items() if kk != "id"}, "source_ids": remap(e.get("source_ids")),
                                  "finding_ids": [fmap.get(i, i) for i in e.get("finding_ids") or []]}); added += 1
        changed = changed or added > 0
        out.append({"opp": opp, "dossier": "updated" if newer else "kept (repo newer or equal)", "version": dos.get("version"), "events_added": added})
        any_change = any_change or changed
    if any_change:
        RL.save(client, ev, lg)
    return out


def skeleton(client, opp):
    return {"schema": 1, "opp_id": opp, "client": client, "version": 0, "updated": None, "author": "agent",
            "status": {"state": "not_started", "limits": [], "pending": []},
            "method": {"cost_order": [], "semrush_units_used": 0, "serp_source": None, "serp_quality": "missing"},
            **{k: ([] if k in ("D_competitors", "I_win", "J_risks") else {}) for k in SECTIONS}, "sources": []}


def comps_for(client, oid):
    """Schritt-Status mit echtem Kontext (eigenes Seitenprofil, Semrush-Budget-Plan) – identisch für retry-plan, export-db und Dashboard."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import serp, glob
    o = next((x for x in _opps(client) if x["id"] == oid), {})
    fs = sorted(glob.glob(os.path.join(ROOT, "clients", client, "data", "research", oid, "diagnosis", "*.json")))
    ctx = {"profile": json.load(open(fs[-1], encoding="utf-8")) if fs else None, "serp_plan": serp.plan(client, oid) if load(client, oid) else {}}
    return components(load(client, oid), o, ctx)


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
        oid = sys.argv[3]
        comps = comps_for(client, oid)
        print(json.dumps({"opp": oid, "components": comps, "progress": progress(comps), **retry_plan(comps)}, ensure_ascii=False, indent=2))
    elif cmd == "export-db":
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        doc = export_db(sys.argv[2], sys.argv[3])
        json.dump(doc, open(sys.argv[4], "w", encoding="utf-8"), ensure_ascii=False)
        print(json.dumps({"out": sys.argv[4], "version": doc["version"], "progress": doc["progress"]["label"], "bytes": os.path.getsize(sys.argv[4])}, ensure_ascii=False))
    elif cmd == "import-db":
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        print(json.dumps(import_db(sys.argv[2], sys.argv[3]), ensure_ascii=False, indent=2))
    elif cmd == "skeleton":
        p = path(client, sys.argv[3])
        if os.path.exists(p):
            sys.exit(f"existiert bereits: {p}")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(skeleton(client, sys.argv[3]), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(p)
    else:
        sys.exit(__doc__)
