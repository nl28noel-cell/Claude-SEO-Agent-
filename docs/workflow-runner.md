# Workflow-Runner (Cold-Start-Lauf aus dem Artifact)

Ein Klick im Artifact (Gate 1, „Änderungen anfordern“, „Erneut versuchen“) speichert die Entscheidung in der Artifact-db und ruft `fire_trigger` für die geplante Aufgabe **„SEO Autopilot – Workflow-Runner“** auf. Diese Aufgabe startet bei jedem Anstoß eine **frische Cloud-Session** in der Umgebung `Claude-SEO-Agent` mit dem Konnektor **Google Drive**. Die Session weiß nichts von früheren Läufen; alles, was sie braucht, steht im Trigger-Prompt und in diesem Dokument.

## Ursache des Fehlers vom 23.11.2026 (behoben)

| Symptom | Ursache | Behebung |
|---|---|---|
| Lauf ohne Repository (`/home/user` leer) | Die Anstöße aus dem Artifact liefen nicht in der interaktiven Session, sondern als eigener Lauf; der Prompt setzte ein vorhandenes Repo voraus | Runner stellt das Repo selbst her (prüfen → sonst `add_repo` + Klonen → Branch auschecken → aktualisieren) |
| Google Drive nicht verfügbar | Die geplante Aufgabe hatte **keine Konnektoren gespeichert** (`mcp_connections: []`); Konnektoren eines Laufs kommen aus der Aufgabe, nicht aus der interaktiven Session | Neue Aufgabe mit hinterlegtem Konnektor Google Drive; Runner lädt die Drive-Tools per ToolSearch und prüft Schreibrecht auf den Zielordner |
| Karte zeigte weiter „Waiting“ | Kein Statusmodell für technische Blockaden | `blocked` + `block_reason`, Button „Erneut versuchen“ |

## Statusmodell (`workflow/<OPP>.production.status`)

| Status | Gesetzt von | Anzeige im Artifact |
|---|---|---|
| `waiting` | Artifact (Gate 1 / Erneut versuchen) | „Approved · Waiting for agent“ bzw. „Agent starting“ (Anstoß < 20 min) |
| `running` | Runner nach bestandenem Preflight (mit `run_id`, `started_at`, `attempt`) | „Producing“ |
| `blocked` | Runner, wenn der Preflight scheitert (`block_reason`, `block_detail`, `preflight`) | „Blocked – environment unavailable“ + „Erneut versuchen“ |
| `draft_ready` | Runner nach erstelltem Google Doc | „Entwurf vN · Review“ |

`block_reason` (maschinenlesbar): `workflow_state_unavailable`, `repository_unavailable`, `wrong_branch`, `repository_outdated`, `runbook_missing`, `business_profile_missing`, `style_guide_missing`, `drive_tool_unavailable`, `drive_folder_unavailable`, `production_error`.

## Ablauf eines Laufs

1. **Tools laden**: `ArtifactData`, Google-Drive-Tools (`create_file`, `search_files`, `get_file_metadata`, `read_file_content`) per ToolSearch.
2. **Workflow-State** (SSOT) aus der Artifact-db exportieren: `ArtifactData list collection=workflow out_dir=/tmp/wf`. Git (`state/workflow.json`) ist nur Spiegel und wird nie als Quelle gelesen.
3. **Repository**: `/home/user/Claude-SEO-Agent-` prüfen; fehlt es → `add_repo(nl28noel-cell, Claude-SEO-Agent-, access=push)` + Klon-Befehl, oder – falls das Tool im Lauf nicht verfügbar ist – `git clone -b <branch> https://github.com/nl28noel-cell/Claude-SEO-Agent-` (im Cold-Start-Test 23.11. so erfolgreich); dann `git fetch origin claude/semsharks-seo-autopilot-6j1cxc && git checkout … && git pull --ff-only`.
4. **Drive-Check**: Tool `create_file` geladen = `--drive-ok`; `get_file_metadata` des Zielordners `1x0fEXsxRh_xcxKFaCjh_jw9dcFQILpY9` mit `capabilities.canAddChildren = true` = `--folder-ok`.
5. **Preflight**: `python3 tools/workflow.py preflight /tmp/wf [--drive-ok] [--folder-ok]`. Exit 2 → alle wartenden Einträge auf `blocked` setzen (mit `if_version`), Lauf beenden. **Nie** selbst erneut anstoßen.
6. **Claim** je Eintrag aus `queue` mit `action` = `produce`/`revise` (Einträge `hold` = Strategie nicht freigegeben → nicht anfassen): `production.status=running`, `run_id`, `started_at`, `attempt` (+1) mit `if_version` – scheitert der Claim (Version geändert), Eintrag überspringen.
7. **Produktion** gemäß `docs/workflow.md` (Briefing, Content-Paket, QA, Render).
8. **Idempotenz**: Titel per `python3 tools/workflow.py doc-title /tmp/wf <OPP>`; vor dem Anlegen im Zielordner nach exakt diesem Titel suchen (nicht im Papierkorb). Existiert er → dieses Dokument verwenden, kein zweites anlegen.
8a. **Change Set**: Enthält `gate1.change_set.companions` Einträge, je Companion-Seite ein zweites Dokument erzeugen (Titel per `doc-title … --companion <url>`, gleiche Idempotenz-Regel). In `production.documents` alle Dokumente mit `role` (`primary`/`companion`), `url`, `doc_id`, `doc_url`, `doc_title` speichern; `draft_ready` erst, wenn alle Dokumente existieren. Der Gate-1-Kommentar ist eine verbindliche Scope-Änderung.
9. **Ergebnis** zurückschreiben (`draft_ready`, Doc-ID/-URL, Version, Historie, QA, Strategie; `review.status=pending`). Bei Fehlern: `blocked` + `block_reason=production_error` + Detail; Gate 1 bleibt unverändert.
10. **Spiegel (optional)**: `python3 tools/workflow.py mirror /tmp/wf`, committen, `git pull --rebase`, **genau ein** Push-Versuch. Scheitert er (z. B. 403, weil das Repo nicht als Quelle an der Routine hängt), nicht wiederholen: der Spiegel wird von der nächsten Session mit Push-Zugriff neu erzeugt. Die Artifact-db bleibt maßgeblich.

Eine Opportunity hat genau einen Workflow-Eintrag und eine Produktionshistorie (`production.history`); ein technischer Fehler setzt nie Gate 1 zurück.

## Cold-Start-Test 23.11.2026, 15:18 UTC (Session `session_01ACEsmK9gecbqhAG46XmMfD`)

| Prüfpunkt | Ergebnis |
|---|---|
| Frische Session in Umgebung `Claude-SEO-Agent` | ✓ |
| Repository selbst hergestellt (`git clone`, Branch korrekt, aktuell) | ✓ |
| Runbook, Business-Profil, Style-Guide, Workflow-State (Artifact-db) | ✓ |
| Google Drive (create_file, Zielordner) | ✗ – Routine ohne hinterlegten Konnektor |
| Ehrlicher Status zurück ins Artifact (`blocked` / `drive_tool_unavailable`, Preflight-Checks) | ✓ |
| Bereits blockierte Echt-Einträge unverändert | ✓ |

**Technische Grenze:** Konnektoren einer Routine können über die API dieser Organisation nicht gesetzt werden (`connectors`-Parameter nicht verfügbar). Der Google-Drive-Konnektor muss einmalig in der claude.ai-Oberfläche an der Routine „SEO Autopilot – Workflow-Runner“ hinterlegt werden. Danach: „Erneut versuchen“ auf der TEST-Karte = echter End-to-End-Test.

## Cold-Start-Test 23.11.2026, 15:30 UTC – mit Google Drive (Session `session_01ACEsmJxfc5rFNmj5RE3qFe`) ✅

Konnektor Google Drive von Noel an der Routine hinterlegt (`mcp_connections`: Google_Drive, Semrush). Ergebnis: frische Session → Repo geklont → Preflight 9/9 grün → TEST-Doc im Ordner „Claude Landingpages“ → `draft_ready` mit Doc-Link, QA und Historie zurück in die Artifact-db. Echte Einträge unverändert.
Nebenbefunde (behoben): `brief` baut `dashboard.json` jetzt selbst, wenn es fehlt; Git-Push des Spiegels scheitert ohne Repo-Quelle an der Routine (403) → nur ein Versuch, nicht blockierend.

## Research-Retry („Fehlende Research nachholen“)

Ausgelöst im Artifact über den Button an einer Opportunity mit `Research incomplete`/`not started`. Das Artifact schreibt **am bestehenden Workflow-Eintrag** `research_retry = {status: "queued", components: [...], blocked: [...], done: [], attempt}` (kein neuer Datensatz, kein zweites Dossier) und stößt den Runner an. `workflow.py queue` liefert dafür `action: "research"` – unabhängig von Gate 1 und ohne Drive.

0. **Live-Stand übernehmen** (Git-unabhängig, Fix F-025): `ArtifactData list collection=research out_dir=/tmp/rdb` → `python3 tools/research.py import-db <client> /tmp/rdb`. Neuere Dossier-Version aus der Datenbank gewinnt; Quellen/Findings/Events werden per Schlüssel ergänzt (IDs werden umgemappt, nichts doppelt).
1. **Claim**: `research_retry.status = "running"`, `started_at` (if_version). Läuft ein Retry länger als 45 min ohne Fortschritt, gilt er als abgebrochen und wird erneut angeboten.
2. **Plan**: `python3 tools/research.py retry-plan <client> <OPP>` – Schritte mit Status `not_started · queued · running · complete · complete_with_limits · blocked · failed · budget_hold · stale · n/a`, `progress` (z. B. „Research partially completed – 5/6 steps“), `run` (nachzuholen inkl. abhängiger Auswertungen), `fallback` (Schritte, die wegen Netzwerk-Sperre **nicht** mit derselben Methode wiederholt werden), `reuse` (vorhanden – nicht erneut ausführen), `budget_hold` (kostenpflichtig ohne Budget – **nie** ausführen), `blockers` (konkrete Handlung für den Nutzer).
3. **Ausführen** nur der `run`-Schritte in Reihenfolge (Anleitung je Schritt in `steps[].how`). **Nach jedem Schritt sofort persistieren**: Dossier/Log im Repo aktualisieren → `python3 tools/research.py export-db <client> <OPP> /tmp/r.json` → `ArtifactData set collection=research doc_id=<OPP> file_path=/tmp/r.json` und `research_retry.steps/progress/done` per update (if_version). Erst wenn der db-Write bestätigt ist, gilt der Schritt als gespeichert – nie Erfolg melden, der nur im Container existiert.
4. **Fehlschlag** eines Schritts bricht den Lauf **nicht** ab: im Dossier `status.failed[<key>] = "<Ursache>"` vermerken (Ursache wörtlich, z. B. „Proxy 403 – Host nicht freigegeben“), mit unabhängigen Schritten fortfahren; abhängige Auswertungen laufen mit eingeschränkter Basis als `complete_with_limits`. Alte Evidence nie löschen.
   **Netzwerk-Sperre (Proxy 403 / „no rule allows host“ / ENOTFOUND im Web-Abruf)**: keine Umgehung, keine Firewall-/Allowlist-Änderung, dieselben URLs nicht erneut abrufen. Stattdessen Fallback-Kette für Wettbewerber: 1) Cache/Profile wiederverwenden · 2) Independent Web Research (WebSearch) · 3) nur erreichbare Seiten analysieren · 4) Suchergebnis-Snippets (`competitors_from_snippets`, `evidence = snippet_only`). Ein Suchsnippet ist keine vollständig analysierte Wettbewerber-Seite – es zählt nie als `page_analyzed`.
5. **Dossier fortschreiben**: dieselbe Datei; bei inhaltlicher Änderung `version + 1` und `changelog`-Eintrag (eine frühere Gate-1-Freigabe gilt dann nicht für die neue Version). Erfolgreich nachgeholte Schritte aus `status.failed` entfernen; Snippet-Fallback als Grenze in `status.limits` nennen.
6. **Validieren**: `python3 tools/research.py validate <client> <OPP>` und `research_log.py validate`; Research-Log-Einträge je Aktion (Web Research, Competitor Analysis, Content Gap …) mit Quellen und Evidenzqualität.
7. **Ergebnis**: `research_retry.status = progress.overall` (`complete` · `complete_with_limits` · `partial` · `failed`) + `finished_at`, `steps`, `progress`, `budget_hold`, `blockers`, `saved {collection, doc, version}`. Den alten Alles-oder-nichts-Status `"blocked"` nicht mehr setzen. Abschließend Commit + genau ein Push-Versuch – schlägt der Push fehl (F-025), bleiben alle Ergebnisse über die Datenbank erhalten; der nächste interaktive Lauf übernimmt sie per `import-db`.
8. **Kein Gate 1, keine Freigabe**: Ein Retry ändert nie `gate1`, `decision` oder WordPress.

Budgetregel: Eine kostenpflichtige Semrush-Abfrage läuft nur, wenn `tools/serp.py plan` → `verdict = run`. Fehlt ausschließlich kostenpflichtige Research, bietet das Artifact keinen Retry an und erklärt den Grund.

## ON HOLD / REJECT (ab 25.11.2026)

- queue-Action `stopped` = Opportunity zurückgestellt oder abgelehnt → nie bearbeiten.
- Unmittelbar vor jeder schreibenden Aktion (Drive-Dokument, ArtifactData-Statusupdate, WordPress-Schreibaufruf, Research-Commit) Eintrag frisch exportieren und `python3 tools/workflow.py check-active /tmp/wf <OPP>` ausführen. Exit 3 → nichts schreiben, laufenden Status auf `stopped` setzen (`stopped_at`, Notiz), nächsten Eintrag bearbeiten.
- `decision` nie verändern; Reaktivierung macht ausschließlich Noel im Artifact.

## CREATE vs. OPTIMIZE (ab 26.11.2026)

`client.json → wordpress.optimize_automation = "disabled"`: OPTIMIZE/MERGE werden **nie** in WordPress umgesetzt (kein Draft, kein Duplizieren, kein Schreiben auf bestehende Seiten, kein Publish-Job). `tools/wordpress.py guard` verweigert jede WordPress-Operation mit `optimize_manual_only`; `workflow.py actions` liefert für alte OPTIMIZE-WordPress-States nur `wp_disabled` (nichts tun) und produziert ein fertiges Drive-Dokument nie erneut. CREATE unverändert: Gate 2 → `wp_draft` (Vorlage „Landingpage-Vorlage 2026“ bzw. freigegebene scriptfreie Variante, nur `draft`) → QA → Gate 3 → `wp_publish`.

### `verify_implementation` (read-only, nach Noels Bestätigung „vollständig“/„teilweise“)
1. `check-active`; Claim `implementation.verification.status = "running"`, `started_at` (if_version). `implementation.status`, `implemented_at`, `comment` NIE ändern.
2. Live-Seite lesen: `python3 tools/page_profile.py https://www.spreewald-luftaufnahmen.de<implementation.url> --out /tmp/verify` (nur lesend, kein Login).
3. Baseline = jüngster Seiten-Scan **vor** `implemented_at` aus dem Research (`clients/<client>/data/research/<OPP>/pages/…json`, Quelle im Research Log). Fehlt er oder ist er unvollständig, wird das als Einschränkung ausgewiesen – nie raten.
4. `python3 tools/implementation.py verify <OPP> /tmp/verify/<datei>.json --before <baseline.json> --claimed <status>` → Ergebnis (results, summary, limitations, mismatch, checked_at, live_fetched, baseline_fetched) als `implementation.verification` mit `status: "complete"` zurückschreiben (Fehler: `"failed"` + Grund). Research-Log-Eintrag „Umsetzung geprüft (read-only)“ mit den nachweisbaren Änderungen.

### `monitor` (Checkpoint T+14/30/60/90, optional T+180)
1. Fällig = `data_ready` (Checkpoint + 3 Tage GSC-Verzögerung) erreicht. Zwei gleich lange GSC-Fenster (query,page): vor `implemented_at` und ab `implemented_at` bis zum letzten GSC-Tag (`tools/gsc_client.py query …`).
2. `python3 tools/implementation.py checkpoint <OPP> <implemented_at> <gsc_last> before.csv after.csv [--existing <bekannte Re-Opt-Keys>]` → `checkpoint.result` (outcome, label, message, Fakten, assessed_at) und `status: "done"` zurückschreiben. Unter 28 Tagen Daten oder < 50 Impressionen: „Too early – insufficient data“, keine Erfolgs-/Misserfolgsaussage.
3. Nur bei `underperforming` ab T+90 und noch nicht vorhanden: `implementation.reoptimization` setzen (Vorschlag mit Bezug auf vorheriges Change Set und Nachweis; braucht wieder Gate 1, nichts wird automatisch geändert). GA4 Organic Sessions/Leads der Seite ergänzend notieren, soweit vorhanden.
