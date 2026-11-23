#!/usr/bin/env python3
"""Erzeugt seo-findings.md und seo-change-log.md aus den State-Dateien (Single Source of Truth).

Aufruf: python3 tools/render_state_md.py [client_slug]
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = {"open": "OPEN", "monitoring": "MONITOR", "resolved": "RESOLVED", "note": "HINWEIS"}
SEV = {"high": "hoch", "medium": "mittel", "low": "niedrig"}


def main(slug):
    cdir = os.path.join(ROOT, "clients", slug)
    f = json.load(open(os.path.join(cdir, "state", "findings.json"), encoding="utf-8"))
    lines = ["# SEO Issues & Opportunities – Findings", "",
             "> **Generiert aus `state/findings.json`** – bitte dort ändern, nicht hier. (`python3 tools/render_state_md.py`)", "",
             "| ID | Datum | Schwere | Kategorie | Befund | URL | Status | Bezug |", "|---|---|---|---|---|---|---|---|"]
    for x in f["findings"]:
        rel = " / ".join(filter(None, [x.get("related_opportunity"), x.get("related_change")])) or "–"
        lines.append(f"| {x['id']} | {x['date']} | {SEV.get(x['severity'], x['severity'])} | {x['category']} | **{x['title']}** – {x['description']} _Evidenz: {x['evidence']}_ | {x.get('url') or '–'} | {STATUS.get(x['status'], x['status'])} | {rel} |")
    open(os.path.join(cdir, "seo-findings.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    c = json.load(open(os.path.join(cdir, "state", "changes.json"), encoding="utf-8"))
    lines = ["# SEO Change Log", "", "> **Generiert aus `state/changes.json`** – bitte dort ändern, nicht hier.", "",
             "| ID | Datum | URL | Maßnahme | Durch | Status | Bezug |", "|---|---|---|---|---|---|---|"]
    for x in c["changes"]:
        lines.append(f"| {x['id']} | {x['date']} | {x['url']} | {x['action']} | {x['by']} | {x['status']}{' · Change Freeze' if x.get('freeze') else ''} | {x['related_opportunity']}, {', '.join(x['related_findings'])} |")
    for x in c["changes"]:
        lines += ["", f"## {x['id']} – {x['title']}", "", f"- Grund: {x['reason']}", f"- Vorher: {x['previous_state']}", f"- Nachher: {x['new_state']}",
                  f"- Einschätzung: {x['impact_assessment']}", "", "| Checkpoint | Fällig | Status | Ergebnis |", "|---|---|---|---|"]
        for cp in x["checkpoints"]:
            lines.append(f"| {cp['label']} | {cp['due']} | {cp['status']} | {cp['result']} |")
    open(os.path.join(cdir, "seo-change-log.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("rendered seo-findings.md, seo-change-log.md")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "spreewald-luftaufnahmen")
