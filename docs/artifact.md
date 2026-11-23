# Control Center als Claude-Artifact

Das private Claude-Artifact ist die **primäre Oberfläche** des SEO Autopiloten. Die lokale Web-App (`dashboard/serve.py`) bleibt als Entwicklungs- und Fallback-Variante mit derselben UI bestehen.

- URL: https://claude.ai/artifact/4dvRn79XhQRBTy21GkmVLk
- Sichtbarkeit: privat (nur Owner). Nicht teilen – Freigaben nur bewusst über das Share-Menü.
- Konfiguration: `dashboard/artifact/artifact.json`

## Öffnen und anpinnen

Link in Claude öffnen (Web, Desktop-App, Mobile). Im Artifact-Menü „Pin“ wählen – danach steht das Control Center dauerhaft in der Claude-Seitenleiste. Im Claude-Code-Terminal listet `/artifacts` alle Artifacts.

## Aufbau

```
state/*.json + GSC-CSV + Semrush-Cache + Inventar
        │  tools/build_dashboard_data.py
        ▼
dashboard/public/data/<client>/dashboard.json        (Datenschicht, Single Source für die UI)
        │  tools/build_artifact.py  (inline CSS/JS, Kopie der Daten, Security-Scan)
        ▼
dashboard/artifact/dist/index.html + data/…          → Artifact-Tool: Veröffentlichung unter derselben URL
```

- Die Seite lädt `data/<client>/dashboard.json` per relativer URL (Datei liegt neben der Seite im Artifact).
- **Keine Live-Abfragen**: GSC und Semrush werden beim Öffnen nicht abgefragt – keine Credentials in der Seite, keine API Units.
- Routing über einfache Hash-Namen (`#overview`, `#opp-OPP-02`); alte `#/…`-Links werden umgeschrieben.
- Light/Dark über Farb-Tokens (`prefers-color-scheme` und `data-theme`).

## Datenfrische

Oben rechts und im Overview/Data Sources: GSC-Datenstand, GSC-Abruf, letzte Semrush-Abfrage, Website-Crawl, Website-Monitor, SEO-State (`state/*.json → updated`) und Dashboard-Build. Ampel nach Alter je Quelle (z. B. GSC-Daten ≤ 5 Tage grün, ≤ 14 gelb, sonst rot).

## Approvals (db)

| Feld | Inhalt |
|---|---|
| Collection | `decisions`, ein Dokument je Entscheidung (Historie bleibt erhalten) |
| Doc-ID | `<client>--<item_id>--g<gate>--<epoch_ms>` |
| `item_id`, `item_title`, `gate` | Gegenstand und Gate (1 = Strategie, 2 = Veröffentlichung) |
| `decision` | `approve` · `request_changes` · `reject` |
| `comment` | optionales Feedback |
| `decided_at` | Zeitpunkt (ISO, UTC) |
| `agent_status` | `pending` → `processed` (oder `superseded`) |
| `agent_processed_at`, `agent_note` | vom Agenten gesetzt |

Zugriffsregel: `read: admin, write: owner` – nur der Owner schreibt; geteilte Betrachter sehen keine Entscheidungen.

Entscheidungs-Buttons erscheinen **nur** für Einträge, die der Agent in `state/approvals.json` (gate1/gate2, `status: pending`) eingereicht hat. Ein Approve – auch in Gate 2 – ändert nie die Website; es ist eine Entscheidung, die der Agent anschließend verarbeitet. Veröffentlichungen bleiben WordPress-Drafts.

### Verarbeitung durch den Agenten

1. `ArtifactData list` auf `decisions` (mit `out_dir`) → offene Entscheidungen (`agent_status = pending`).
2. Fachlich umsetzen (z. B. Opportunity-Status, Gate-Eintrag in `state/approvals.json`).
3. `ArtifactData update` (mit `if_version`): `agent_status: processed`, `agent_processed_at`, `agent_note`.
4. `python3 tools/record_decisions.py <out_dir>/decisions` → Spiegel in `state/approvals.json → decision_log` (Git-Historie).
5. `python3 tools/build_artifact.py` und neu veröffentlichen.

## Normaler Workflow nach SEO-Arbeit

1. Daten holen/aktualisieren (GSC-Skript, Semrush-Connector + `keyword_cache.py`, Crawl/Monitoring).
2. State-Dateien pflegen (Opportunities, Findings, Changes, Tasks, Approvals), `render_state_md.py`.
3. `python3 -m unittest tests/test_dashboard.py` und `python3 tools/build_artifact.py`.
4. Artifact unter derselben URL neu veröffentlichen; geöffnete Ansichten laden automatisch nach.
5. Veröffentlichte Daten zurücklesen und `python3 tools/qa_artifact_data.py` laufen lassen.
6. Commit + Push.

## Grenzen

- Snapshot-basiert: Werte stammen aus dem letzten Build (Datum sichtbar), nicht live.
- Kein Hintergrundprozess: Aktualisierung nur in Agent-Sessions oder per geplanter Aufgabe.
- Lokal (serve.py) ist der db-Speicher nicht verfügbar – Approvals nur im Artifact.
