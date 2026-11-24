#!/usr/bin/env python3
"""Current Page Diagnosis & Ranking Protection – für jede OPTIMIZE-/MERGE-Opportunity vor Gate 1.

Prinzip: Preserve what works → fix what is weak → add what is missing. Nicht: Rewrite everything.
Je stärker eine URL bereits rankt, desto konservativer der Umgang mit bestehenden Inhalten.

Quellen (keine neuen API-Abfragen): GSC Query × Page (16 Monate, inkl. 90-Tage-Werte), vorhandene Semrush-Rankings je URL,
Seitenprofil mit Abschnitten (tools/page_profile.py, kostenloser Live-Abruf der eigenen Seite).

    python3 tools/page_diagnosis.py baseline <client> <url>      -> Ranking Protection List als JSON (Baseline vor Veröffentlichung)
"""
import json, os, re, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERIC = {"drohne", "drohnen", "mit", "per", "für", "die", "der", "das", "und", "in", "von", "aus", "der", "luft"}
TIERS = ("critical", "high", "watch", "off_topic")


def _norm(p):
    return (p or "").split("?")[0].lower().rstrip("/") + "/" if p else None


def _tokens(q):
    toks = [t for t in re.split(r"[^a-zäöüß0-9]+", q.lower()) if t and t not in GENERIC]
    return [t[:-1] if len(t) > 6 and t.endswith(("n", "s")) else t for t in toks]   # baustellen→baustelle (grob)


def supporting(query, profile):
    """Welche bestehenden Elemente tragen die Relevanz für diese Query? (Title, Meta, H1, Abschnitte)"""
    if not profile:
        return []
    toks = _tokens(query)
    if not toks:
        return []
    hits = []
    def has(txt):
        t = (txt or "").lower()
        return all(any(tok in w for w in re.split(r"[^a-zäöüß0-9]+", t)) for tok in toks)
    if has(profile.get("title")):
        hits.append({"element": "Title", "text": profile.get("title")})
    if has(" ".join(profile.get("h1") or [])):
        hits.append({"element": "H1", "text": (profile.get("h1") or [""])[0]})
    if has(profile.get("meta_description")):
        hits.append({"element": "Meta Description", "text": profile.get("meta_description")[:120]})
    for s in profile.get("sections") or []:
        if s["tag"] in ("h2", "h3", "intro") and (has(s["heading"]) or has(s["text"])):
            hits.append({"element": s["tag"].upper() if s["tag"] != "intro" else "Einleitung", "text": s["heading"], "in": "Überschrift" if has(s["heading"]) else "Text"})
    return hits[:4]


def protection_list(target, qp, qmeta, cluster_of, relevant_clusters, sem_rank=None, profile=None):
    """Ranking Protection List: wofür rankt die URL heute – und welcher Inhalt trägt das?"""
    t = _norm(target)
    rows = [r for r in qp if _norm(r["page"]) == t]
    out = []
    for r in sorted(rows, key=lambda x: (-x["clicks"], -x["impressions"])):
        q, m, cl = r["query"], qmeta.get(r["query"], {}), cluster_of.get(r["query"])
        pos = r["position"]
        relevant = cl in relevant_clusters
        if r["clicks"] >= 1 or (pos <= 10 and r["impressions"] >= 20):
            tier = "critical"
        elif pos <= 20 and r["impressions"] >= 20:
            tier = "high"
        elif r["impressions"] >= 50 and relevant:
            tier = "watch"
        else:
            continue
        if not relevant and tier != "critical":
            tier = "off_topic"
        p90 = m.get("pos_90d")
        trend = None if p90 is None else ("besser" if p90 < pos - 2 else "schlechter" if p90 > pos + 2 else "stabil")
        out.append({"query": q, "tier": tier, "clicks": r["clicks"], "impressions": r["impressions"], "position": round(pos, 1),
                    "pos_90d": p90, "imp_90d": m.get("imp_90d"), "trend": trend, "cluster": cl, "supported_by": supporting(q, profile)})
    for k in sem_rank or []:
        if _norm(k.get("url")) == t and not any(x["query"] == k["keyword"] for x in out):
            out.append({"query": k["keyword"], "tier": "high" if (k.get("position") or 99) <= 20 else "watch", "clicks": None, "impressions": None,
                        "position": k.get("position"), "pos_90d": None, "imp_90d": None, "trend": None, "cluster": cluster_of.get(k["keyword"]),
                        "source": "Semrush-Ranking (23.11.)", "supported_by": supporting(k["keyword"], profile)})
    order = {x: i for i, x in enumerate(TIERS)}
    out.sort(key=lambda x: (order[x["tier"]], -(x["impressions"] or 0)))
    return out


def strength(plist, page_stats=None):
    crit = sum(1 for x in plist if x["tier"] == "critical")
    high = sum(1 for x in plist if x["tier"] == "high")
    clicks = sum(x["clicks"] or 0 for x in plist)
    if clicks >= 10 or crit >= 5:
        lvl = "strong"
    elif crit + high >= 3:
        lvl = "moderate"
    else:
        lvl = "weak"
    mode = {"strong": "Konservativ: bestehende Abschnitte erhalten, nur gezielt ergänzen; Title/H1/zentrale H2 nur mit starker Begründung.",
            "moderate": "Behutsam: tragende Abschnitte erhalten (siehe Schutzliste), schwache Abschnitte überarbeiten, Lücken ergänzen.",
            "weak": "Gezielte Überarbeitung vertretbar: wenige gesicherte Rankings – trotzdem alle Schutz-Queries im Text behalten."}[lvl]
    return {"level": lvl, "critical": crit, "high": high, "clicks": clicks, "mode": mode}


SENSITIVE = ("URL", "Title", "H1", "Zentrale H2", "Entfernung bestehender Texte", "Primary Intent", "Canonical", "Indexierung", "Interne Links", "Zusammenlegung", "Redirect")


def loss_risk(plist, st, sensitive_changes):
    """Risk of Ranking Loss: Stärke der Seite × Eingriffstiefe (sensitive Änderungen an Elementen, die Schutz-Queries tragen)."""
    carried = {h["element"] for x in plist if x["tier"] in ("critical", "high") for h in x["supported_by"]}
    touched = [s for s in sensitive_changes or [] if s.get("element") in ("Title", "H1", "URL", "Canonical", "Redirect", "Primary Intent", "Zusammenlegung", "Indexierung")
               or (s.get("element") in ("Zentrale H2", "Entfernung bestehender Texte") and carried)]
    hard = [s for s in touched if s.get("element") in ("URL", "Canonical", "Redirect", "Zusammenlegung", "Indexierung", "Primary Intent")]
    carrying = [s for s in touched if s.get("element") in carried]     # geändertes Element trägt kritische/wichtige Schutz-Queries
    if hard or (st["level"] == "strong" and touched):
        lvl = "high"
    elif carrying or (touched and st["level"] == "moderate") or st["level"] == "strong":
        lvl = "medium"
    else:
        lvl = "low"
    why = f"Seite {st['level']} ({st['critical']} kritische, {st['high']} wichtige Schutz-Queries, {st['clicks']} Klicks); " + \
          (f"sensible Änderungen: {', '.join(s['element'] for s in touched)}" if touched else "keine sensible Änderung an tragenden Elementen") + \
          (f"; davon tragen Schutz-Queries: {', '.join(s['element'] for s in carrying)}" if carrying else "")
    return {"level": lvl, "reason": why}


def protection_check(baseline, current, days_base, days_now, target_queries=()):
    """Monitoring nach OPTIMIZE (T+7/14/30/60/90): Schutzliste vorher vs. nachher (Werte je Tag normiert)."""
    cur = {r["query"]: r for r in current}
    lost, dropped, ok = [], [], []
    for b in baseline:
        if b["tier"] not in ("critical", "high"):
            continue
        c = cur.get(b["query"])
        bi = (b["impressions"] or 0) / max(days_base, 1)
        if not c or c["impressions"] == 0:
            lost.append({"query": b["query"], "before_pos": b["position"]})
            continue
        ci = c["impressions"] / max(days_now, 1)
        pos_drop = (c["position"] - b["position"]) if b["position"] else 0
        if (bi and ci < bi * 0.5) or pos_drop > 5 or ((b["clicks"] or 0) >= 3 and c["clicks"] == 0):
            dropped.append({"query": b["query"], "before_pos": b["position"], "after_pos": round(c["position"], 1), "impr_change": round((ci - bi) / bi, 2) if bi else None})
        else:
            ok.append(b["query"])
    gained = [q for q in target_queries if q in cur and not any(b["query"] == q for b in baseline)]
    important = len(lost) + len(dropped)
    status = "negative_impact" if important >= 2 or any(x["query"] for x in lost if any(b["query"] == x["query"] and b["tier"] == "critical" for b in baseline)) else "ok"
    finding = None
    if status == "negative_impact":
        finding = {"title": "Potential negative impact detected", "severity": "high",
                   "affected_queries": [x["query"] for x in lost + dropped],
                   "recommendation": "Änderungen mit der Schutzliste abgleichen: entfernte/geänderte Abschnitte, die diese Queries trugen, gezielt wiederherstellen (Teil-Rollback); bei Title/H1-Änderung Rücknahme prüfen."}
    return {"status": status, "lost": lost, "dropped": dropped, "stable": ok, "gained_targets": gained, "finding": finding}


def merge_winner(page_stats):
    """MERGE: Gewinnerseite = meiste Klicks, dann Impressionen, dann bessere Position. Signale der anderen Seiten erhalten."""
    if not page_stats:
        return None
    w = sorted(page_stats, key=lambda s: (-(s.get("clicks") or 0), -(s.get("impressions") or 0), s.get("position") or 99))[0]
    return {"winner": w["url"], "losers": [s["url"] for s in page_stats if s["url"] != w["url"]],
            "keep": "Inhalte der zusammengeführten Seiten, die deren Schutz-Queries tragen, auf der Gewinnerseite erhalten; 301 nur nach Freigabe, keine automatische Umsetzung."}


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "baseline":
        d = json.load(open(os.path.join(ROOT, "dashboard", "public", "data", a[1], "dashboard.json"), encoding="utf-8"))
        o = next((x for x in d["opportunities"] if _norm(x.get("existing_page")) == _norm(a[2])), None)
        print(json.dumps((o or {}).get("ranking_protection"), ensure_ascii=False, indent=2))
    else:
        sys.exit(__doc__)
