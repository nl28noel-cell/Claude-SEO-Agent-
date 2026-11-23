#!/usr/bin/env python3
"""Spiegelt verarbeitete Approval-Entscheidungen aus dem Artifact-db in state/approvals.json (decision_log).

Ablauf in einer Agent-Session:
  1. ArtifactData list  collection=decisions  out_dir=<tmp>      (Entscheidungen als JSON-Dateien exportieren)
  2. Entscheidung fachlich verarbeiten (z. B. Gate-1-Eintrag auf approved/changes_requested/rejected setzen)
  3. ArtifactData update agent_status=processed, agent_processed_at, agent_note   (mit if_version)
  4. python3 tools/record_decisions.py <tmp>/decisions [--client spreewald-luftaufnahmen]
  5. python3 tools/build_artifact.py  → Artifact neu veröffentlichen

Es werden nur Entscheidungen mit agent_status=processed übernommen; vorhandene IDs werden aktualisiert, nicht dupliziert.
Keine Website-Aktion."""
import argparse, glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = ("item_id", "item_title", "gate", "decision", "comment", "decided_at", "agent_status", "agent_processed_at", "agent_note")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("--client", default="spreewald-luftaufnahmen")
    a = ap.parse_args()
    p = os.path.join(ROOT, "clients", a.client, "state", "approvals.json")
    st = json.load(open(p, encoding="utf-8"))
    log = {e["id"]: e for e in st.get("decision_log", [])}
    n = 0
    for f in sorted(glob.glob(os.path.join(a.dir, "*.json"))):
        doc = json.load(open(f, encoding="utf-8"))
        doc = doc.get("data", doc)
        did = os.path.splitext(os.path.basename(f))[0]
        if doc.get("client") != a.client or doc.get("agent_status") != "processed":
            continue
        if doc.get("decision") not in ("approve", "request_changes", "reject") or doc.get("gate") not in (1, 2):
            continue  # ungültige Einträge werden ignoriert, nicht übernommen
        log[did] = {"id": did, **{k: doc.get(k) for k in KEYS}}; n += 1
    st["decision_log"] = sorted(log.values(), key=lambda e: e["decided_at"] or "")
    json.dump(st, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2); open(p, "a").write("\n")
    print(f"✓ {n} verarbeitete Entscheidungen übernommen · decision_log: {len(st['decision_log'])} Einträge")


if __name__ == "__main__":
    main()
