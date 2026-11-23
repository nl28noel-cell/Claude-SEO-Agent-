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
3. **Repository**: `/home/user/Claude-SEO-Agent-` prüfen; fehlt es → `add_repo(nl28noel-cell, Claude-SEO-Agent-, access=push)`, Klon-Befehl ausführen, `register_repo_root`; dann `git fetch origin claude/semsharks-seo-autopilot-6j1cxc && git checkout … && git pull --ff-only`.
4. **Drive-Check**: Tool `create_file` geladen = `--drive-ok`; `get_file_metadata` des Zielordners `1x0fEXsxRh_xcxKFaCjh_jw9dcFQILpY9` mit `capabilities.canAddChildren = true` = `--folder-ok`.
5. **Preflight**: `python3 tools/workflow.py preflight /tmp/wf [--drive-ok] [--folder-ok]`. Exit 2 → alle wartenden Einträge auf `blocked` setzen (mit `if_version`), Lauf beenden. **Nie** selbst erneut anstoßen.
6. **Claim** je Eintrag aus `queue`: `production.status=running`, `run_id`, `started_at`, `attempt` (+1) mit `if_version` – scheitert der Claim (Version geändert), Eintrag überspringen.
7. **Produktion** gemäß `docs/workflow.md` (Briefing, Content-Paket, QA, Render).
8. **Idempotenz**: Titel per `python3 tools/workflow.py doc-title /tmp/wf <OPP>`; vor dem Anlegen im Zielordner nach exakt diesem Titel suchen (nicht im Papierkorb). Existiert er → dieses Dokument verwenden, kein zweites anlegen.
9. **Ergebnis** zurückschreiben (`draft_ready`, Doc-ID/-URL, Version, Historie, QA, Strategie; `review.status=pending`). Bei Fehlern: `blocked` + `block_reason=production_error` + Detail; Gate 1 bleibt unverändert.
10. **Spiegel**: `python3 tools/workflow.py mirror /tmp/wf` (nach erneutem Export), committen, `git pull --rebase` und pushen.

Eine Opportunity hat genau einen Workflow-Eintrag und eine Produktionshistorie (`production.history`); ein technischer Fehler setzt nie Gate 1 zurück.
