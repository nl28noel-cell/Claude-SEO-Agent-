#!/usr/bin/env python3
"""Mini-Sitemap / Architecture Map je Opportunity (CREATE · OPTIMIZE · MERGE).

Quellen – ausschließlich echte Daten, nichts erfunden:
  * Website-Inventar (alle gecrawlten URLs)            → EXISTING
  * planned_url einer Opportunity                       → PROPOSED (mit OPP-ID)
  * Research-Dossier H_ia (parent/target/siblings/children/child_candidates/hub_assessment/internal_links)
  * Dossier G_structure (Abschnitte mit action NEW)     → SECTION ONLY (Thema gehört als Abschnitt auf die Seite, keine eigene URL)
  * Kannibalisierungs-Engine (affected/companions)      → Kannibalisierungs-Markierung

Status je Knoten: existing | proposed | future | section
Beziehungen (Parent/Child) sind nur „confirmed“, wenn ein bestehender interner Link Parent → Ziel belegt ist;
sonst kennzeichnet die Karte sie als „Proposed Architecture“.

    python3 tools/architecture.py <dashboard.json> <OPP-ID>
"""
import json, re, sys

STATUSES = ("existing", "proposed", "future", "section")


def _norm(u):
    if not u:
        return None
    u = re.sub(r"^https?://[^/]+", "", str(u).strip())
    if not u.startswith("/"):
        return None
    return u if u.endswith("/") else u + "/"


def build(o, inventory_urls, opps, titles=None):
    """o = Opportunity (dashboard.json), inventory_urls = Set aller gecrawlten Pfade, opps = alle Opportunities,
    titles = {Pfad: Seitentitel aus dem Inventar} für Knoten ohne Dossier-Label."""
    titles = {_norm(k): v for k, v in (titles or {}).items()}
    inv = {_norm(u) for u in inventory_urls if _norm(u)}
    planned = {_norm(x.get("planned_url")): x["id"] for x in opps if x.get("planned_url")}
    nodes, edges, seen = [], [], {}
    ia = ((o.get("research") or {}).get("H_ia") or {})
    rec, cur = ia.get("recommended") or {}, ia.get("current") or {}
    cz = o.get("cannibalization") or {}
    cannibal = {_norm(a.get("url")): a for a in (cz.get("affected") or []) if _norm(a.get("url"))}

    def status_of(url):
        if url in inv:
            return "existing"
        if url in planned:
            return "proposed"
        return None  # unbekannte URL → wird NICHT gezeichnet

    def add(role, url=None, label=None, status=None, note=None, opp=None):
        u = _norm(url)
        if u:
            st = status or status_of(u)
            if st is None:
                return None
            if u in seen:
                n = seen[u]
                n["roles"] = sorted(set(n["roles"]) | {role})
                return n
            n = {"id": u, "url": u, "label": label or (titles.get(u) or "").split("|")[0].strip() or u, "status": st, "roles": [role], "note": note,
                 "opp": opp or planned.get(u), "cannibal": u in cannibal and u != _norm(o.get("existing_page") or o.get("planned_url"))}
            if n["cannibal"]:
                a = cannibal[u]
                n["cannibal_detail"] = {"impressions": a.get("impressions"), "share": a.get("share"), "position": a.get("position")}
            seen[u] = n
        else:
            if status not in ("future", "section"):
                return None
            n = {"id": f"{role}:{len(nodes)}", "url": None, "label": label, "status": status, "roles": [role], "note": note, "opp": opp, "cannibal": False}
        nodes.append(n)
        return n

    target_url = _norm(o.get("existing_page") or o.get("planned_url") or (rec.get("target") or {}).get("url"))
    inv_title = (titles.get(target_url) or "").split("|")[0].strip() if target_url in inv else ""
    t = add("target", target_url, inv_title or (rec.get("target") or cur.get("target") or {}).get("label") or o.get("name"),
            status="existing" if target_url in inv else "proposed", opp=o["id"])
    # Parent: Dossier (empfohlen > aktuell), sonst Startseite als nicht bestätigte Annahme
    par = rec.get("parent") or cur.get("parent")
    p = add("parent", par.get("url"), par.get("label"), note=par.get("note")) if par else None
    if not p and "/" in inv:
        p = add("parent", "/", "Startseite", note="Keine IA-Analyse – Einordnung unter der Startseite angenommen")
    links = ia.get("internal_links") or []
    parent_confirmed = bool(p and t and any(_norm(x.get("from")) == p["url"] and _norm(x.get("to")) == t["url"] and x.get("type") == "exists" for x in links))
    if p and t:
        edges.append({"from": p["id"], "to": t["id"], "type": "hierarchy", "confirmed": parent_confirmed})
    # Geschwister / Nachbarn
    for s in (rec.get("siblings") or cur.get("siblings") or []):
        n = add("sibling", s.get("url"), s.get("label"), note=s.get("relation"))
        if n and p:
            edges.append({"from": p["id"], "to": n["id"], "type": "hierarchy", "confirmed": False})
    for u in (o.get("competing_pages") or []):
        add("sibling", u, None, note="rankt ebenfalls für das Thema")
    # Kinder: bestehende Unterseiten, Kandidaten (SECTION ONLY / FUTURE)
    for c in (rec.get("children") or cur.get("children") or []):
        n = add("child", c.get("url"), c.get("label"), note=c.get("relation"))
        if n and t:
            edges.append({"from": t["id"], "to": n["id"], "type": "hierarchy", "confirmed": False})
    for c in (rec.get("child_candidates") or []):
        v = (c.get("verdict") or "").lower()
        st = "section" if v.startswith("nein") else "future"
        n = add("section" if st == "section" else "future", None, c.get("topic"), status=st, note=c.get("verdict"))
        if n and t:
            edges.append({"from": t["id"], "to": n["id"], "type": "contains" if st == "section" else "optional", "confirmed": False})
    hub = rec.get("hub_assessment")
    if hub and hub.get("option"):
        add("future", None, re.split(r"[,(]", hub["option"])[0].strip(), status="future", note=hub.get("verdict"))
    for s in ((o.get("research") or {}).get("G_structure") or {}).get("sections") or []:
        if s.get("action") == "NEW" and sum(1 for x in nodes if x["status"] == "section") < 4:
            n = add("section", None, s.get("h2") or s.get("heading"), status="section", note="neuer Abschnitt auf der Zielseite – keine eigene URL")
            if n and t:
                edges.append({"from": t["id"], "to": n["id"], "type": "contains", "confirmed": False})
    # Kannibalisierung + Companions
    for u, a in cannibal.items():
        add("cannibal", u, None, note=f"Kannibalisierung: {round((a.get('share') or 0) * 100)} % der Impressionen")
    for c in (cz.get("companions") or []):
        add("companion", c.get("url"), None, note=c.get("reason"))
    # Interne Links (nur zwischen gezeichneten Knoten)
    ids = {n["url"] for n in nodes if n["url"]}
    for x in links:
        a, b = _norm(x.get("from")), _norm(x.get("to"))
        if a in ids and b in ids and (a == target_url or b == target_url):
            edges.append({"from": a, "to": b, "type": "link_exists" if x.get("type") == "exists" else "link_add", "anchor": x.get("anchor"), "confirmed": x.get("type") == "exists"})
    for n in nodes:
        if n["cannibal"] and t:
            edges.append({"from": t["id"], "to": n["id"], "type": "cannibal", "confirmed": True})
    proposed = (not parent_confirmed) or any(n["status"] in ("proposed", "future") for n in nodes)
    return {"opp": o["id"], "type": o.get("type"), "target": target_url, "nodes": nodes, "edges": edges,
            "label": "Proposed Architecture" if proposed else "Current Architecture",
            "source": "IA-Dossier H_ia + Website-Inventar + Kannibalisierung" if ia else "Website-Inventar + Kannibalisierung (kein IA-Dossier)",
            "has_dossier": bool(ia), "parent_confirmed": parent_confirmed}


def validate(arch, inventory_urls, opps):
    """Keine erfundenen Seiten: jeder URL-Knoten ist im Inventar oder geplante URL einer Opportunity."""
    inv = {_norm(u) for u in inventory_urls}
    planned = {_norm(x.get("planned_url")) for x in opps if x.get("planned_url")}
    err = []
    for n in arch["nodes"]:
        if n["status"] not in STATUSES:
            err.append(f"{n['id']}: status {n['status']}")
        if n["url"] and n["url"] not in inv and n["url"] not in planned:
            err.append(f"{n['url']}: weder im Inventar noch geplant")
        if n["status"] == "existing" and n["url"] not in inv:
            err.append(f"{n['url']}: EXISTING, aber nicht im Inventar")
        if n["status"] in ("section", "future") and n["url"]:
            err.append(f"{n['id']}: {n['status']} darf keine URL haben")
    return err


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    d = json.load(open(a[0], encoding="utf-8"))
    o = next(x for x in d["opportunities"] if x["id"] == a[1])
    r = build(o, d.get("site_urls") or [], d["opportunities"])
    print(json.dumps(r, ensure_ascii=False, indent=2))
