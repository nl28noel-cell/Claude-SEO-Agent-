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

1. **Claim**: `research_retry.status = "running"`, `started_at` (if_version). Läuft ein Retry länger als 45 min ohne Fortschritt, gilt er als abgebrochen und wird erneut angeboten.
2. **Plan**: `python3 tools/research.py retry-plan <client> <OPP>` – Komponenten (`complete · missing · failed · stale · blocked_budget · n/a`), `run` (nachzuholen inkl. abhängiger Auswertungen), `reuse` (vorhanden, valide, frisch – nicht erneut ausführen), `blocked` (kostenpflichtig ohne Budget – **nie** ausführen).
3. **Ausführen** nur der `run`-Schritte in Reihenfolge (Anleitung je Schritt in `steps[].how`); nach jedem Schritt `research_retry.done` ergänzen (das Artifact zeigt „x von n Schritten abgeschlossen“).
4. **Fehlschlag** eines Schritts (z. B. Host nicht erreichbar): im Dossier `status.failed[<key>] = "<Ursache>"` vermerken, weitere unabhängige Schritte fortsetzen; neue Evidence ergänzen, alte nie löschen (fehlgeschlagene Abrufe bleiben als Quelle mit `error` sichtbar).
5. **Dossier fortschreiben**: dieselbe Datei; bei inhaltlicher Änderung `version + 1` und `changelog`-Eintrag (eine frühere Gate-1-Freigabe gilt dann nicht für die neue Version). Erfolgreich nachgeholte Schritte aus `status.failed` entfernen.
6. **Validieren**: `python3 tools/research.py validate <client> <OPP>` und `research_log.py validate`; Research-Log-Einträge je Aktion (Web Research, Competitor Analysis, Content Gap …) mit Quellen.
7. **Ergebnis**: `research_retry.status = "complete"` + `finished_at` – oder `"blocked"` + `block_reason` (verständlich, z. B. „Wettbewerber-Hosts im Netzwerk nicht freigegeben“ oder „Nur Semrush SERP fehlt – Budget-Reserve“). Commit + genau ein Push-Versuch.

Budgetregel: Eine kostenpflichtige Semrush-Abfrage läuft nur, wenn `tools/serp.py plan` → `verdict = run`. Fehlt ausschließlich kostenpflichtige Research, bietet das Artifact keinen Retry an und erklärt den Grund.
