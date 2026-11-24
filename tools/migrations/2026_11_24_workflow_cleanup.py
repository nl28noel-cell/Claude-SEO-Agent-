#!/usr/bin/env python3
"""Workflow-Cleanup 24.11.2026: Testphase-Entwürfe in den Audit Trail übernehmen (als superseded) + Cleanup-Event.

Zeitpunkte stammen aus der Workflow-Historie der Artifact-db (Export vor dem Reset) und dem Zeitpunkt des Resets.
Es werden keine bestehenden Events gelöscht oder verändert. Idempotent.
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import research_log as RL  # noqa: E402

C = "spreewald-luftaufnahmen"
RESET_AT = "2026-11-24T07:17:45Z"
NOTE = "Previous production drafts were created during system testing and removed before productive use. Opportunities reset for approval under the new Research/Strategy workflow."
DRAFTS = [  # aus workflow/<OPP>.production (db-Export vor dem Reset)
    {"opp": "OPP-05", "at": "2026-11-23T15:39:59Z", "doc_id": "1L38pK8SRcWTdFI1Oh2_WOS121uRLUjNCXOb1jzxS-PQ", "title": "OPP-05 – Bestandsaufnahme Gebäude / Beweissicherung – Entwurf",
     "gate1": "2026-11-23T15:10:05Z", "run": "run-20261123T153807Z-OPP-05"},
    {"opp": "OPP-03", "at": "2026-11-23T16:07:30Z", "doc_id": "1RmXbup0kwvrjMRu-ff0zwbAK5PH7MMkkxV7oJ5It390", "title": "OPP-03 – Gebäudeinspektion-Hub – Optimierung",
     "gate1": "2026-11-23T16:03:13Z", "run": "run-20261123T1610Z-OPP-03"},
]
RESET = {"OPP-01": "Gate 1 (Testphase) · Produktion blocked", "OPP-02": "Gate 1 (Testphase) · Produktion blocked", "OPP-03": "Gate 1 (Testphase) · Entwurf v1",
         "OPP-04": "Gate 1 (Testphase) · Produktion blocked", "OPP-05": "Gate 1 (Testphase) · Entwurf v1"}

ev, lg = RL.load(C)
if any(e["action"] == "workflow_cleanup" for e in lg["events"]):
    sys.exit("bereits migriert")
dsrc = []
for d in DRAFTS:
    sid = RL.add_source(ev, {"type": "agent", "key": "gdoc-" + d["doc_id"], "opp_ids": [d["opp"]], "title": f"Google Doc · {d['title']}",
                             "url": f"https://docs.google.com/document/d/{d['doc_id']}/edit", "fetched": d["at"], "fetched_precision": "exact",
                             "meta": {"note": f"Testentwurf ({d['run']}); am 24.11.2026 in den Drive-Papierkorb verschoben"}})
    dsrc.append(sid)
    RL.add_event(lg, {"at": d["at"], "at_precision": "exact", "opp": d["opp"], "action": "draft", "title": "Entwurf produziert (Testphase)",
                      "summary": f"Workflow-Runner erstellte „{d['title']}“ nach Gate 1 vom {d['gate1'][:16].replace('T', ' ')} UTC (altes Modell ohne Research-Stufe).",
                      "found": "Entwurf v1 · QA passed_with_notes", "source_ids": [sid], "superseded": "Test phase · superseded"})
RL.add_event(lg, {"at": RESET_AT, "at_precision": "exact", "opp": None, "action": "workflow_cleanup", "title": "Workflow Cleanup",
                  "summary": NOTE,
                  "found": "Zurückgesetzt: " + " · ".join(f"{k} ({v})" for k, v in RESET.items()) + ". 2 Drive-Entwürfe in den Papierkorb verschoben. Research-Dossiers, Evidence und Log unverändert.",
                  "source_ids": dsrc})
RL.save(C, ev, lg)
print("✓ Cleanup im Research Log erfasst")
