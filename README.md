# SEMSHARKS SEO Autopilot

Datengetriebenes SEO-Research-, Strategie- und Monitoring-System. Pilotkunde: **Spreewald Luftaufnahmen**.

## Control Center (primär: privates Claude-Artifact)

**Primäre Oberfläche:** https://claude.ai/artifact/4dvRn79XhQRBTy21GkmVLk (privat, nur Owner). In Claude öffnen und über das Artifact-Menü anpinnen. Details, Approval-Ablauf und Workflow: [`docs/artifact.md`](docs/artifact.md).

```bash
python3 tools/build_artifact.py        # Daten neu bauen + Artifact-Dateien erzeugen (inkl. Security-Scan)
# danach veröffentlicht der Agent dashboard/artifact/dist/ unter derselben URL (Artifact-Tool)
```

**Lokaler Fallback** (Entwicklung/Debugging, gleiche UI):

```bash
python3 dashboard/serve.py             # http://127.0.0.1:8765/
```

Optionen: `--port 9000`, `--no-build`. Approvals sind lokal nicht speicherbar (nur im Artifact).

## Wie die Daten ins Dashboard kommen

```
Raw Sources                      Normalisierung / Analyse          Dashboard Data Layer                  UI
─────────────────────────        ──────────────────────────        ──────────────────────────────        ─────────────────
GSC-Exporte (CSV)          ─┐
Semrush-Ergebnisse + Cache ─┤──▶  tools/build_dashboard_data.py ──▶ dashboard/public/data/<client>/    ──▶ dashboard/public/
Website-Inventar (JSON)    ─┤     (Cluster, Segmente, Zeiträume,      dashboard.json                       (index.html, app.js,
State-Dateien (JSON)       ─┘      Joins, Attention-Regeln)                                                styles.css)
```

| Quelle | Datei(en) | Aktualisierung |
|---|---|---|
| Google Search Console | `clients/<client>/data/gsc-YYYY-MM/gsc_*.csv` | `tools/gsc_client.py query …` (API, automatisierbar) |
| GSC URL Inspection | Ergebnis in `state/changes.json` (Checkpoint) | `tools/gsc_client.py inspect …` |
| GA4 | `clients/<client>/data/ga4-YYYY-MM/ga4_*.csv` + `ga4_admin.json` | `tools/ga4_client.py baseline <property> <start> <end> <dir>` (read-only) |
| Google Ads | `clients/<client>/data/ads-YYYY-MM/ads_discovery.json` (+ Paid-Historie über GA4) | `tools/ads_client.py discover "<name>" <out.json>` / `query` (read-only, MCC) |
| Conversion-Klassifizierung | `clients/<client>/state/conversions.json` | vom Agenten gepflegt |
| Semrush | `data/keyword-cache.csv`, `clients/<client>/data/baseline-*/semrush-*.csv` | Semrush-MCP-Connector im Claude-Chat, danach `tools/keyword_cache.py import …` |
| Website-Inventar | `clients/<client>/data/baseline-*/inventory.json` | `tools/site_inventory.py <url> <dir>` |
| Technisches Monitoring | `state/sources.json` | `tools/monitor_url.py <url>` |
| Opportunities, Findings, Changes, Tasks, Market, Local, Approvals | `clients/<client>/state/*.json` | vom Agenten gepflegt (**Single Source of Truth**) |

`seo-findings.md` und `seo-change-log.md` werden aus den State-Dateien **generiert** (`python3 tools/render_state_md.py`) – nicht von Hand ändern.

Neue GSC-Daten → `python3 dashboard/serve.py` → Dashboard zeigt sie. Kein Code-Änderungsbedarf.

## Was automatisch ist – und was (noch) nicht

| Bereich | Stand |
|---|---|
| Daten-Build, KPIs, Zeiträume, Vergleiche, Segmente, Attention-Liste | automatisch bei jedem Start |
| GSC-Abruf | per Skript, ausgelöst vom Agenten (noch kein Zeitplan) |
| Semrush-Abruf | nur über den Connector im Claude-Chat (kein eigener API-Key) |
| Opportunity-Bewertung, Findings, Change Log | vom Agenten in `state/*.json` gepflegt |
| Workflow (Gate 1 → Drive-Entwurf → Review → Gate 2) | Board im Artifact, SSOT = Artifact-`db` Collection `workflow`, Anstoß des Agenten über geplante Aufgabe; Ablauf: [`docs/workflow.md`](docs/workflow.md) |
| Approvals (Protokoll) | im Artifact-`db` gespeichert (Collection `decisions`), vom Agenten in der nächsten Session verarbeitet; Spiegel in `state/approvals.json → decision_log`; **keine Website-Aktion** |
| Website-/WordPress-Aktionen | **nicht vorhanden** (bewusst) |
| Live-Agentenstatus | nicht vorhanden – es werden nur echte Zustände gezeigt (Completed, Planned, Monitoring, Blocked, Needs review) |

## QA

```bash
python3 -m unittest tests/test_dashboard.py -v      # Daten- und Security-Checks
node dashboard/qa/smoke.js                           # alle Routen, Console-Fehler, Screenshots (Server muss laufen)
node dashboard/qa/functional.js                      # Filter, Suche, Tabs, Detailansichten, KPI-Abgleich
node dashboard/qa/artifact_qa.js [out] --shots      # Artifact-Fassung: Light/Dark, 4 Breiten, Overflow, Approval-Flow (Mock)
python3 tools/qa_artifact_data.py <dashboard.json>   # veröffentlichte Daten gegen Rohquellen
```

## Sicherheit

- Credentials (GSC Service Account) liegen **nie** im Repo: Umgebungsvariable `GSC_SERVICE_ACCOUNT_JSON_B64` oder Datei außerhalb des Repos (`~/.config/semsharks/`). `.gitignore` blockiert Credential-Dateien.
- Der Dashboard-Build liest keine Credentials; der Server liefert ausschließlich `dashboard/public/` aus.
- Details: `docs/integrations.md`.

## Struktur

```
clients/index.json                    Kunden-Registry (Client Switcher)
clients/<client>/client.json          Kunden-Konfiguration (Property, Segmente, Prioritäten)
clients/<client>/business-profile.md  Business-Profil
clients/<client>/state/*.json         Single Source of Truth (Opportunities, Findings, Changes, …)
clients/<client>/data/                Rohdaten + Analysen
clients/<client>/reports/             Reports (Erklärung, nicht Datenquelle)
tools/                                Fetch-, Analyse- und Build-Skripte
dashboard/                            Control Center (public/ = UI, artifact/ = Claude-Artifact-Build, serve.py, qa/)
docs/integrations.md                  Semrush, GSC, Secrets, Setup-Skript
```
