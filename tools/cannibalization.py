#!/usr/bin/env python3
"""Cannibalization Engine – fester Bestandteil jeder Opportunity, jeder Local-Kombination und des Monitorings.

Quellen (keine neuen API-Abfragen): GSC Query × Page (16 Monate), Query-Cluster, Website-Inventar (Title/H1/URL),
vorhandene Semrush-Rankings je URL. Entscheidet selbst – Warnungen nur bei Grenzfällen oder Abweichung von der Empfehlung.

Entscheidungen Opportunity:  CREATE · OPTIMIZE · MERGE · DO NOT CREATE (→ OPTIMIZE bestehende Seite) · + Companion Optimization
Entscheidungen Local:        CREATE CITY PAGE · USE MAIN SERVICE PAGE · OPTIMIZE EXISTING PAGE · MONITOR · IGNORE
Risiko:                      low · medium · high

Regeln (nachvollziehbar, im Artifact angezeigt):
- Fremdanteil = Anteil der Cluster-Impressionen auf einer anderen eigenen URL (Startseite/Preisseite/Kontakt zählen nur als Info).
- Semantische Überschneidung = Stamm des Primary Keywords in URL/Title/H1 der anderen Seite.
- OPTIMIZE: andere Seite ≥ 40 % oder rankt besser auf den Kern-Queries → high; 15–40 % → medium; sonst low.
  Zieht die Zielseite selbst ≥ 30 % eines fremden Clusters (≥ 100 Impr.), gilt das als umgekehrte Kannibalisierung.
- CREATE: bestehende Seite hält ≥ 50 % bei Ø-Pos. ≤ 20 UND semantische Überschneidung → high → DO NOT CREATE, OPTIMIZE diese Seite.
  Ist die Nachfrage generisch (Cluster „…_allgemein“) und die rankende Seite eine spezifischere Leistung → CREATE nur mit
  Companion Optimization (generischer Intent wandert auf die neue Seite) → high + Grenzfall-Warnung.
  ≥ 30 % bei Ø-Pos. ≤ 30 oder thematischer Überschneidung → medium (Abgrenzung nötig); schwach rankende Fremdseiten → low.
"""
import re
from collections import defaultdict

UTILITY = {"/", "/kontakt/", "/drohnenaufnahmen-preis-kosten/", "/impressum/", "/datenschutzerklarung/"}
STOP = {"drohne", "drohnen", "mit", "per", "berlin", "brandenburg", "und", "für", "die", "der"}


def _norm(p):
    return (p or "").split("?")[0].lower().rstrip("/") + "/" if p else None


def stem(primary_keyword):
    toks = [t for t in re.split(r"[^a-zäöüß0-9]+", (primary_keyword or "").lower()) if t and t not in STOP]
    return toks[0][:9] if toks else None     # „dachinspektion“ → „dachinspe“, „baudokumentation“ → „baudokume“


def semantic(url, inv_rec, st):
    if not st:
        return False
    hay = " ".join([url or "", (inv_rec or {}).get("title") or "", " ".join((inv_rec or {}).get("h1") or [])]).lower()
    return st in hay.replace("-", "")


def page_stats(rows):
    agg = defaultdict(lambda: {"impressions": 0, "clicks": 0, "pw": 0.0, "queries": defaultdict(int)})
    for r in rows:
        a = agg[_norm(r["page"])]
        a["impressions"] += r["impressions"]; a["clicks"] += r["clicks"]; a["pw"] += r["position"] * r["impressions"]
        a["queries"][r["query"]] += r["impressions"]
    tot = sum(a["impressions"] for a in agg.values()) or 1
    out = []
    for p, a in agg.items():
        out.append({"url": p, "impressions": a["impressions"], "clicks": a["clicks"], "share": round(a["impressions"] / tot, 3),
                    "position": round(a["pw"] / a["impressions"], 1) if a["impressions"] else None,
                    "top_queries": [q for q, _ in sorted(a["queries"].items(), key=lambda kv: -kv[1])[:3]]})
    return sorted(out, key=lambda x: -x["impressions"]), tot


def split_queries(rows, min_impr=20, min_share=0.2):
    byq = defaultdict(list)
    for r in rows:
        byq[r["query"]].append(r)
    out = []
    for q, rs in byq.items():
        t = sum(r["impressions"] for r in rs)
        pages = [(_norm(r["page"]), r["impressions"], r["position"]) for r in rs if t and r["impressions"] / t >= min_share and _norm(r["page"]) not in UTILITY]
        if t >= min_impr and len(pages) >= 2:
            out.append({"query": q, "impressions": t, "pages": [{"url": p, "impressions": i, "position": round(pos, 1)} for p, i, pos in sorted(pages, key=lambda x: -x[1])]})
    return sorted(out, key=lambda x: -x["impressions"])[:8]


def analyze(o, qp, cluster_of, inv, opps=None, sem_rank=None):
    """Kannibalisierungs-Analyse einer Opportunity. qp: GSC-Zeilen Query×Page; cluster_of: query→cluster; inv: url→Inventar."""
    target = _norm(o.get("existing_page") or o.get("planned_url"))
    exists = bool(o.get("existing_page"))
    cl = o.get("gsc_cluster")
    qset = {q for q, c in cluster_of.items() if c == cl} | set(o.get("gsc_queries") or [])
    rows = [r for r in qp if r["query"] in qset]
    stats, tot = page_stats(rows)
    st = stem(o.get("primary_keyword"))
    others = [s for s in stats if s["url"] != target and s["url"] not in UTILITY]
    for s in others:
        s["semantic_overlap"] = semantic(s["url"], inv.get(s["url"]) or inv.get(s["url"].rstrip("/")), st)
        if sem_rank:
            s["semrush_rankings"] = [k for k in sem_rank if _norm(k.get("url")) == s["url"]][:3]
    tgt = next((s for s in stats if s["url"] == target), None)
    utility = [s for s in stats if s["url"] in UTILITY and s["url"] != target and s["impressions"]]
    # umgekehrte Kannibalisierung: Zielseite zieht fremde Cluster
    foreign = []
    if exists and target not in UTILITY:          # Sammelseiten (Start, Preise, Kontakt) ziehen naturgemäß viele Cluster
        byc = defaultdict(lambda: defaultdict(int))
        for r in qp:
            c = cluster_of.get(r["query"])
            if c and c != cl:
                byc[c][_norm(r["page"])] += r["impressions"]
        for c, pages in byc.items():
            t = sum(pages.values())
            if pages.get(target, 0) >= 100 and t and pages[target] / t >= 0.3:
                owner = max(((p, i) for p, i in pages.items() if p != target and p not in UTILITY), key=lambda x: x[1], default=(None, 0))
                if owner[1] < 50:
                    owner = (None, 0)
                foreign.append({"cluster": c, "impressions": pages[target], "share": round(pages[target] / t, 2), "other_url": owner[0], "other_impressions": owner[1]})
        foreign.sort(key=lambda x: -x["impressions"])
    top = others[0] if others else None
    generic = (cl or "").endswith("_allgemein")
    risk, decision, why, companions = "low", o["type"], [], []
    linked = lambda url: next((x["id"] for x in (opps or []) if x["id"] != o["id"] and _norm(x.get("existing_page") or x.get("planned_url")) == url), None)  # noqa: E731
    if not rows:
        risk, why = "unknown", ["Keine GSC-Daten für die Cluster-Queries – Kannibalisierung nicht bewertbar (bestehende Seitenstruktur prüfen)."]
    elif o["type"] in ("CREATE",) and top:
        if top["share"] >= 0.5 and (top["position"] or 99) <= 20 and generic:
            risk, decision = "high", "CREATE + COMPANION"
            why.append(f"{top['url']} erhält {round(top['share'] * 100)} % der Impressionen für generische Queries (Ø Pos. {top['position']}), ist aber eine spezifischere Leistung.")
            companions.append({"url": top["url"], "reason": "Generischer Intent muss auf die neue übergeordnete Seite wechseln; die bestehende Seite auf ihren spezifischen Intent schärfen.",
                               "required_changes": [f"Title/H1/Description auf den spezifischen Leistungsbegriff schärfen, generische Begriffe ({', '.join(top['top_queries'][:2])}) nicht mehr als Hauptziel",
                                                    "Abschnitt mit Link zur neuen Übersichtsseite (beschreibender Anker)", "FAQ/Abschnitte ohne generische Überschneidung"],
                               "queries_to_release": top["top_queries"], "linked_opp": linked(top["url"])})
        elif top["share"] >= 0.5 and (top["position"] or 99) <= 20 and top.get("semantic_overlap"):
            risk, decision = "high", "DO NOT CREATE"
            why.append(f"{top['url']} bedient den Intent bereits ({round(top['share'] * 100)} % der Impressionen, Ø Pos. {top['position']}). Eine neue Seite würde sie kannibalisieren.")
        elif top["share"] >= 0.3 and ((top["position"] or 99) <= 30 or top.get("semantic_overlap")):
            risk, decision = "medium", "CREATE"
            why.append(f"{top['url']} erhält {round(top['share'] * 100)} % der Impressionen, deckt den Intent aber {'inhaltlich' if top.get('semantic_overlap') else 'nicht ausdrücklich'} ab → klare Abgrenzung nötig.")
            companions.append({"url": top["url"], "reason": "Abgrenzung zur neuen Seite, damit beide nebeneinander bestehen.",
                               "required_changes": ["Begriffe der neuen Seite nicht als Hauptziel verwenden", "Verweis/Link auf die neue Seite"], "queries_to_release": top["top_queries"], "linked_opp": linked(top["url"]), "optional": True})
        else:
            why.append("Keine bestehende Seite bedient den Intent nennenswert.")
    elif top:
        tpos = (tgt or {}).get("position") or 99
        if top["share"] >= 0.4 or ((top["position"] or 99) < tpos and top["share"] >= 0.2):
            risk = "high"
            why.append(f"{top['url']} erhält {round(top['share'] * 100)} % der Cluster-Impressionen (Ø Pos. {top['position']}) gegenüber {round((tgt or {}).get('share', 0) * 100)} % auf der Zielseite (Ø Pos. {(tgt or {}).get('position')}).")
            decision = "OPTIMIZE + COMPANION"
            companions.append({"url": top["url"], "reason": "Die konkurrierende Seite muss die Queries dieses Intents an die Zielseite abgeben (Rollen klären).",
                               "required_changes": [f"Queries {', '.join(top['top_queries'][:3])} nicht mehr als Hauptziel (Title/H1/Abschnitte)", "Kurzer Abschnitt mit Link zur Zielseite (beschreibender Anker)", "Eigenen Intent der Seite schärfen"],
                               "queries_to_release": top["top_queries"], "linked_opp": linked(top["url"])})
        elif top["share"] >= 0.15:
            risk = "medium"
            why.append(f"{top['url']} erhält {round(top['share'] * 100)} % der Cluster-Impressionen – Abgrenzung beobachten.")
        else:
            why.append(f"Zielseite erhält {round((tgt or {}).get('share', 0) * 100)} % der Cluster-Impressionen; keine andere Seite konkurriert nennenswert.")
    if foreign:
        f = foreign[0]
        if f["share"] >= 0.5 and f["impressions"] >= 300:
            risk = "high" if risk != "high" else risk
            why.append(f"Umgekehrt: Die Zielseite zieht {f['impressions']} Impressionen ({round(f['share'] * 100)} %) aus dem Cluster „{f['cluster']}“, der zu {f['other_url'] or 'einer anderen Seite'} gehört.")
            if f["other_url"] and decision in ("OPTIMIZE",):
                decision = "OPTIMIZE + RELEASE"
            if f["other_url"]:
                companions.append({"url": f["other_url"], "reason": f"Abgrenzung: Queries aus „{f['cluster']}“ sollen auf {f['other_url']} landen, nicht auf der Zielseite.",
                                   "required_changes": ["Zielseite verweist für diesen Intent auf die Fachseite", "Fachseite stärken (siehe verknüpfte Opportunity)"],
                                   "queries_to_release": [], "linked_opp": linked(f["other_url"]), "direction": "release"})
        else:
            why.append(f"Hinweis: Zielseite erhält auch {f['impressions']} Impressionen aus „{f['cluster']}“ – durch klare Abgrenzung lösen.")
            if risk == "low":
                risk = "low"
    rec = {"DO NOT CREATE": f"Keine neue Seite. {top['url'] if top else 'Bestehende Seite'} schärfen (OPTIMIZE) und Themen abgrenzen." if top else "Keine neue Seite.",
           "CREATE + COMPANION": "Neue Seite nur zusammen mit Companion Optimization der bestehenden Seite (ein Change Set).",
           "OPTIMIZE + COMPANION": "Zielseite schärfen UND konkurrierende Seite abgrenzen (Companion Optimization, gemeinsames Change Set).",
           "OPTIMIZE + RELEASE": "Zielseite schärfen und fremden Intent bewusst an die Fachseite abgeben.",
           }.get(decision, {"CREATE": "Neue Seite erstellen" + (" – Abgrenzung beachten" if risk == "medium" else ""),
                            "OPTIMIZE": "Bestehende Seite schärfen", "MERGE": "Seiten zusammenführen"}.get(decision, decision))
    if o["type"] in ("MONITOR", "IGNORE"):          # keine Produktion: Risiko zeigen, Entscheidung nicht automatisch umstellen
        if risk in ("high", "medium"):
            rec = f"{o['type']} beibehalten – Kannibalisierung beobachten" + (f"; bei Ausbau zuerst: {rec}" if decision != o["type"] else ".")
        decision, companions = o["type"], []
    action = {"DO NOT CREATE": "OPTIMIZE", "CREATE + COMPANION": "CREATE", "OPTIMIZE + COMPANION": "OPTIMIZE", "OPTIMIZE + RELEASE": "OPTIMIZE"}.get(decision, decision)
    action_url = top["url"] if decision == "DO NOT CREATE" and top else target
    return {"risk": risk, "decision": decision, "action": action, "action_url": action_url, "changed": action != o["type"],
            "recommendation": rec, "why": why, "target": target, "target_stats": tgt, "affected": others[:5], "utility": utility[:3],
            "foreign_intents": foreign[:3], "split_queries": split_queries(rows), "companions": [c for c in companions if not c.get("optional") or risk != "low"],
            "warning": risk == "high" or (risk == "medium" and o["type"] == "CREATE") or action != o["type"],
            "basis": {"queries": len(qset), "rows": len(rows), "impressions": tot if rows else 0, "source": "GSC Query × Page (16 Monate) · Website-Inventar · Semrush-Rankings je URL (vorhanden)"}}


def local_cell(cell, service, location, qp, inv):
    """Local Opportunity: Service × Region. Gleiche Kannibalisierungslogik – City Page nur bei eigenständigem lokalen Nutzen."""
    main = _norm(service["page"])
    pat_s, pat_l = re.compile(service["gsc_pattern"], re.I), re.compile(location["pattern"], re.I)
    rows = [r for r in qp if pat_s.search(r["query"]) and pat_l.search(r["query"])]
    stats, tot = page_stats(rows)
    best = stats[0] if stats else None
    main_s = next((s for s in stats if s["url"] == main), None)
    impr = sum(s["impressions"] for s in stats)
    fit = service.get("priority", 0)
    vol = (cell.get("semrush") or {}).get("volume")
    regional = location.get("coverage_regional")
    if main_s and (main_s["position"] or 99) <= 10:
        risk, rec, why = "high", "USE MAIN SERVICE PAGE", f"{main} rankt bereits auf Ø Pos. {main_s['position']} für diese Kombination – eine City Page würde sie kannibalisieren."
    elif regional:
        risk, rec = "high", ("OPTIMIZE EXISTING PAGE" if impr else "USE MAIN SERVICE PAGE")
        why = "Region ist Teil der bestehenden Service-Seite (Berlin & Brandenburg) – lokal dort stärken, keine eigene Seite."
        if best and best["url"] != main:
            why += f" Aktuell rankt {best['url']} (Ø Pos. {best['position']}) statt {main} → Kannibalisierung, zuerst Rollen klären."
    elif best and (best["position"] or 99) <= 20:
        risk, rec, why = "medium", "OPTIMIZE EXISTING PAGE", f"{best['url']} rankt bereits (Ø Pos. {best['position']}) – zuerst lokalen Bezug dort stärken."
    elif (impr >= 100 or (vol or 0) >= 30) and fit >= 8:
        risk, rec, why = "low", "CREATE CITY PAGE", "Eigenständige lokale Nachfrage ohne rankende Seite – City Page nur mit echtem lokalem Bezug (Projekte, Anfahrt, lokale FAQs), keine Doorway Page."
    elif fit >= 6:
        risk, rec, why = ("low" if not stats else "medium"), "MONITOR", ("Kaum gemessene Nachfrage" if impr else "Keine gemessene Nachfrage") + " – bei hohem Business Fit beobachten (0 Volumen ≠ IGNORE)."
    else:
        risk, rec, why = "low", "IGNORE", "Geringer Business Fit und keine gemessene Nachfrage."
    return {"demand": {"gsc_impressions": impr, "gsc_queries": len({r['query'] for r in rows}), "semrush_volume": vol,
                       "semrush_status": (cell.get("semrush") or {}).get("status")},
            "ranking": {"url": best["url"], "position": best["position"]} if best else None,
            "competition": None, "business_fit": fit, "cannibalization": risk, "recommendation": rec, "why": why}


def monitor(target, before_rows, after_rows, queries):
    """Nach Veröffentlichung (T+14/30/60): Gewinnt die Zielseite? Wechseln URLs? Verliert eine bestehende Seite? Alternieren URLs?"""
    def owner(rows):
        byq = defaultdict(lambda: defaultdict(int))
        for r in rows:
            if r["query"] in queries:
                byq[r["query"]][_norm(r["page"])] += r["impressions"]
        return {q: max(p.items(), key=lambda kv: kv[1])[0] for q, p in byq.items() if p}, byq
    ob, _ = owner(before_rows)
    oa, ba = owner(after_rows)
    t = _norm(target)
    switches = [{"query": q, "before": ob.get(q), "after": oa[q]} for q in oa if ob.get(q) and ob[q] != oa[q]]
    won = [q for q in oa if oa[q] == t]
    lost = [s for s in switches if s["before"] != t and s["after"] == t]
    alternating = [q for q, p in ba.items() if len([1 for i in p.values() if i / max(sum(p.values()), 1) >= 0.25]) >= 2]
    share = round(len(won) / max(len(oa), 1), 2)
    status = "ok" if share >= 0.6 and not alternating else "watch" if share >= 0.3 else "cannibalization"
    return {"target_share": share, "switches": switches, "moved_to_target": lost, "alternating": alternating, "status": status,
            "action": {"ok": "Keine Maßnahme", "watch": "Beobachten, beim nächsten Checkpoint erneut prüfen",
                       "cannibalization": "Finding anlegen → Opportunity (Abgrenzung/Companion Optimization)"}[status]}
