#!/usr/bin/env python3
"""SEO-Autopilot Workflow: Gate 1 → Google-Drive-Entwurf → Review → Gate 2.

Single Source of Truth ist die Artifact-db-Collection `workflow` (ein Dokument je Opportunity).
Das Artifact schreibt Noels Entscheidungen hinein, der Agent schreibt Produktionsstatus zurück.
`state/workflow.json` ist der Git-Spiegel (vom Agenten nach jedem Lauf geschrieben).

Dokumentschema workflow/<OPP-ID>:
  opp_id, test(bool), title
  gate1:      {status: "approved", at, comment}
  production: {status: waiting|in_progress|draft_ready|failed, version, doc_id, doc_url, doc_title,
               created_at, updated_at, qa_status, qa_notes, strategy_summary, error, history:[...]}
  review:     {status: pending|revision_requested|approved, comment, at, for_version}
  gate2:      {status: "approved", at, comment}
  trigger:    {requested_at, result}

Befehle (Export vorher per ArtifactData list collection=workflow out_dir=<dir>):
  python3 tools/workflow.py queue  <dir>                   -> offene Arbeit (produce / revise) als JSON
  python3 tools/workflow.py brief  <dir> <OPP-ID> <out.md> -> Produktionsbriefing (Fakten, Freigabe-/Revisionskommentar)
  python3 tools/workflow.py render <draft.md> <out.html>   -> Entwurf (Markdown-Subset) → HTML für Google-Doc-Konvertierung
  python3 tools/workflow.py mirror <dir> [--client SLUG]   -> state/workflow.json aktualisieren
Keine Website-, WordPress- oder URL-Aktion.
"""
import glob, html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CLIENT = "spreewald-luftaufnahmen"


def load_export(d):
    """Liest exportierte db-Dokumente (<dir>/workflow/<id>.json oder <dir>/<id>.json)."""
    files = glob.glob(os.path.join(d, "workflow", "*.json")) or glob.glob(os.path.join(d, "*.json"))
    docs = {}
    for f in files:
        j = json.load(open(f, encoding="utf-8"))
        data = j.get("data", j) if isinstance(j, dict) else {}
        did = j.get("id") if isinstance(j, dict) and "data" in j else os.path.splitext(os.path.basename(f))[0]
        data["_version"] = j.get("version") if isinstance(j, dict) else None
        docs[did or data.get("opp_id")] = data
    return docs


def actions(docs):
    """Was ist zu tun? Nur explizite Freigaben – nie aus dem bloßen Vorhandensein einer Opportunity."""
    out = []
    for did, w in sorted(docs.items()):
        g1 = (w.get("gate1") or {}).get("status")
        prod = w.get("production") or {}
        rev = w.get("review") or {}
        if (w.get("gate2") or {}).get("status") == "approved":
            continue
        if g1 != "approved":
            continue
        if prod.get("status") in (None, "waiting", "failed"):
            out.append({"doc": did, "action": "produce", "comment": (w.get("gate1") or {}).get("comment"), "test": bool(w.get("test")), "version": w.get("_version")})
        elif rev.get("status") == "revision_requested" and prod.get("status") != "in_progress":
            out.append({"doc": did, "action": "revise", "comment": rev.get("comment"), "for_version": rev.get("for_version") or prod.get("version"),
                        "test": bool(w.get("test")), "version": w.get("_version")})
    return out


def _dash(client):
    return json.load(open(os.path.join(ROOT, "dashboard", "public", "data", client, "dashboard.json"), encoding="utf-8"))


def brief(d, opp_id, out, client=DEFAULT_CLIENT):
    docs = load_export(d)
    w = docs.get(opp_id) or {}
    if (w.get("gate1") or {}).get("status") != "approved":
        sys.exit(f"{opp_id}: keine Gate-1-Freigabe – Produktion verweigert.")
    dash = _dash(client)
    o = next((x for x in dash["opportunities"] if x["id"] == opp_id), None)
    if not o and not w.get("test"):
        sys.exit(f"{opp_id} nicht in den Opportunities.")
    if not o:  # TEST-Eintrag: Karte aus dem db-Dokument
        o = {"id": opp_id, "name": w.get("title", opp_id), "type": (w.get("card") or {}).get("type", "CREATE"), "primary_keyword": (w.get("card") or {}).get("primary_keyword", "test"),
             "gsc": {"queries": [], "cluster": None}, "semrush": {"keywords": []}, "existing_page": None, "why": "Technischer Test", "recommendation": "Technischer Test", "reasoning": [], "risks": [], "findings_detail": []}
    f = next((c for c in dash.get("funnel", {}).get("clusters", []) if c["cluster"] == o.get("gsc_cluster")), None)
    L = [f"# Produktionsbriefing {opp_id} – {o['name']}", ""]
    if w.get("test"):
        L += ["**TEST-Opportunity – nur technischer Workflow-Test, kein echter Content.**", ""]
    L += ["## Freigabe", f"- Gate 1: approved am {(w.get('gate1') or {}).get('at')}", f"- Kommentar von Noel: {(w.get('gate1') or {}).get('comment') or '–'}"]
    rev = w.get("review") or {}
    if rev.get("status") == "revision_requested":
        L += [f"- **Änderungswunsch (Version {rev.get('for_version')}):** {rev.get('comment')}"]
    L += ["", "## Opportunity",
          f"- Typ: {o['type']} · Priorität: {o.get('priority')} · Confidence: {o.get('confidence')} · Business Fit: {o.get('business_fit')}/10",
          f"- Primary Keyword: {o.get('primary_keyword')} · Cluster: {o.get('gsc_cluster')}",
          f"- Bestehende URL: {o.get('existing_page') or '–'} · Geplante URL: {o.get('planned_url') or '–'}",
          f"- Warum: {o.get('why')}", f"- Empfehlung: {o.get('recommendation')}"]
    L += ["- Reasoning:"] + [f"  - {r}" for r in o.get("reasoning", [])]
    L += ["- Risiken:"] + [f"  - {r}" for r in o.get("risks", [])]
    L += ["", "## Evidenz GSC (16 Monate)"] + [
        f"- {q['query']}: {q.get('impressions', 0)} Impr., {q.get('clicks', 0)} Klicks, Pos. {q.get('position')}" for q in o.get("gsc", {}).get("queries", []) if not q.get("missing")]
    L += ["", "## Evidenz Semrush (DE)"] + [
        f"- {k['keyword']}: Vol. {k.get('volume')}, KD {k.get('kd')}, CPC {k.get('cpc')}" for k in o.get("semrush", {}).get("keywords", []) if k.get("status") == "ok"]
    if f:
        e = f["engagement"]
        L += ["", "## Search → Business (GA4/Ads)", f"- Sitzungen {e['sessions']} · engagiert {e['engaged']} · Funnel Intent {e['micro_sessions']} Sitz. · Leads {e['leads']} ({e['lead_form']} Form, {e['lead_contact']} Kontakt)",
              f"- Paid-Historie: {f['paid']['keyword_cost']} € / {f['paid']['keyword_clicks']} Klicks"] + [f"- Signal: {s['text']}" for s in f["signals"]]
    L += ["", "## Findings"] + [f"- {x['id']} {x['title']} ({x['status']})" for x in o.get("findings_detail", [])]
    L += ["", "## Verbindliche Regeln",
          "- clients/spreewald-luftaufnahmen/business-profile.md (insb. §8 belegte Vorteile, §10 Niemals erfinden)",
          "- clients/spreewald-luftaufnahmen/content-style-guide.md (Hausformat, Tonalität, Nicht übernehmen)",
          "- Paketinhalt: interner Block, SEO Title, Meta Description, H1, Struktur H2/H3, Volltexte, CTAs, FAQ, interne Links, Bildhinweise, Schema, Redirect-/Canonical-Hinweis (nur Empfehlung); bei OPTIMIZE: bleibt/ändert/ergänzt/warum",
          "- Keine Website-, WordPress-, URL- oder Redirect-Änderung. Nichts veröffentlichen."]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"✓ Briefing → {out}")


def _inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def render(src, out):
    """Markdown-Subset → HTML (Überschriften, Absätze, Listen, Tabellen, Fett/Kursiv, Links, Trennlinie, Zitat)."""
    lines = open(src, encoding="utf-8").read().splitlines()
    H, i = ['<html><head><meta charset="utf-8"></head><body>'], 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            n = len(m.group(1)); H.append(f"<h{n}>{_inline(m.group(2))}</h{n}>"); i += 1; continue
        if ln.strip() == "---":
            H.append("<hr>"); i += 1; continue
        if ln.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            H.append('<table border="1" cellpadding="6">')
            for r, cells in enumerate(rows):
                tag = "th" if r == 0 else "td"
                H.append("<tr>" + "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells) + "</tr>")
            H.append("</table>"); continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", ln):
            ordered = bool(re.match(r"^\s*\d+\.", ln)); tag = "ol" if ordered else "ul"
            H.append(f"<{tag}>")
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                H.append("<li>" + _inline(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i])) + "</li>"); i += 1
            H.append(f"</{tag}>"); continue
        if ln.startswith(">"):
            H.append("<blockquote>" + _inline(ln.lstrip("> ")) + "</blockquote>"); i += 1; continue
        para = [ln]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|\||\s*([-*]|\d+\.)\s|>|---)", lines[i]):
            para.append(lines[i].rstrip()); i += 1
        H.append("<p>" + _inline(" ".join(para)) + "</p>")
    H.append("</body></html>")
    open(out, "w", encoding="utf-8").write("\n".join(H))
    print(f"✓ HTML → {out} ({os.path.getsize(out)} Bytes)")


def mirror(d, client=DEFAULT_CLIENT):
    docs = load_export(d)
    items = []
    for did, w in sorted(docs.items()):
        w = {k: v for k, v in w.items() if not k.startswith("_")}
        items.append({"id": did, **w})
    p = os.path.join(ROOT, "clients", client, "state", "workflow.json")
    import datetime as dt
    json.dump({"_doc": "Git-Spiegel der Artifact-db-Collection 'workflow' (SSOT ist die db). Vom Agenten nach jedem Workflow-Lauf geschrieben.",
               "updated": dt.date.today().isoformat(), "items": items}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(p, "a").write("\n")
    print(f"✓ {len(items)} Workflow-Einträge → {p}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "queue":
        print(json.dumps(actions(load_export(a[1])), ensure_ascii=False, indent=2))
    elif a[0] == "brief":
        brief(a[1], a[2], a[3])
    elif a[0] == "render":
        render(a[1], a[2])
    elif a[0] == "mirror":
        mirror(a[1], a[a.index("--client") + 1] if "--client" in a else DEFAULT_CLIENT)
    else:
        sys.exit(__doc__)
