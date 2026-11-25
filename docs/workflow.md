# SEO-Autopilot Workflow: Gate 1 → Google-Drive-Entwurf → Review → Gate 2

Stand 23.11.2026. WordPress folgt separat – **in diesem Workflow wird nichts veröffentlicht und die Website nie verändert.**

## Zustände (Board im Artifact, Seite „Workflow“)

| Spalte | Bedingung (db `workflow/<OPP>`) | Anzeige |
|---|---|---|
| Zur Prüfung | kein Dokument, `gate1.status ≠ approved` oder Gate 1 ohne Bezug zur aktuellen Research-Version | Standard für **alle** Opportunities (CREATE/OPTIMIZE/MERGE); Research-Status auf der Karte; alte Freigaben: „Strategie-Freigabe ausstehend“ |
| Freigegeben / Produktion | `gate1.status = approved`, Entwurf noch nicht fertig, oder `review.status = revision_requested` | „Approved · Waiting for agent“ · „In Produktion“ · „Revision requested · Waiting for agent“ · „Produktion fehlgeschlagen“ |
| Entwurf fertig / Review | `production.status = draft_ready` | Drive-Link, erstellt/geändert, QA, Content-Strategie, Buttons „Änderungen anfordern“ / „Final freigeben“ |
| WordPress-Draft & QA | `gate2.status = approved`, `wordpress.status` queued … qa_failed/blocked | „WordPress Draft queued/ready“, Links Preview/Edit/Original, QA |
| Ready for Publish | `wordpress.status = qa_passed` (bzw. publish_queued/publishing/publish_failed) | Gate 3: Preview, Original, Drive Change Set, Changes, Ranking Risk, Cannibalization, QA, Rollback, „Was wird verändert?“, Button „Änderungen veröffentlichen“ |
| Live / Monitoring | `wordpress.status = published` | „Published · Monitoring“ (T+7…T+90) |

## Gate 1 = Strategie-Freigabe

Vor Gate 1 durchläuft jede Opportunity die Research-/Strategy-Stufe (Dossier A–J, Research-Status). Gate 1 speichert die freigegebene Research-Version; ohne vollständige Research nur mit protokolliertem Override. Details: [`research-strategy.md`](research-strategy.md). Die Queue liefert für Einträge ohne gültige Strategie `hold` – diese werden nicht produziert.

## Single Source of Truth

Artifact-db, Collection **`workflow`**, ein Dokument je Opportunity (Schema in `tools/workflow.py`). Das Artifact schreibt Noels Aktionen (`gate1`, `review`, `gate2`, `trigger`), der Agent schreibt `production` und setzt `review.status` nach einer Revision auf `pending`. Zusätzlich Audit-Log in `decisions`. Git-Spiegel: `clients/<client>/state/workflow.json` (vom Agenten nach jedem Lauf). Zugriff: nur der Owner schreibt und liest.

## Was technisch passiert, wenn Noel freigibt

1. Die Seite speichert die Entscheidung sofort persistent in `workflow/<OPP>` (+ Eintrag in `decisions`).
2. Danach ruft die Seite über den Konnektor **„Claude Code Remote“** das Tool `fire_trigger` für die geplante Aufgabe **„SEO Autopilot – Workflow-Runner“** (`trig_01RNrjTJmYFQFN3P85xNcQkp`) auf. Ergebnis wird in `workflow/<OPP>.trigger` vermerkt.
3. Jeder Anstoß startet eine **frische Cloud-Session** (Cold Start). Sie stellt Repository und Branch selbst her, liest den Workflow-State aus der Artifact-db, führt den Preflight aus und produziert oder meldet `blocked`. Details: [`workflow-runner.md`](workflow-runner.md).
4. Ist der Konnektor in der Ansicht nicht verfügbar (z. B. Mobile-App ohne Konnektor, abgelehnte Berechtigung), bleibt der Status ehrlich „Approved · Waiting for agent“; die Freigabe wird beim nächsten Agentenlauf erkannt (`queue`).

Gate 2 löst keinen Agentenlauf aus (es gibt nichts zu tun, außer später WordPress).

## Agentenlauf (Checkliste)

1. `ArtifactData list collection=workflow out_dir=<tmp>` → `python3 tools/workflow.py queue <tmp>`
2. Für jedes `produce`/`revise`: db-Dokument auf `production.status=in_progress` setzen (mit `if_version`).
3. `python3 tools/workflow.py brief <tmp> <OPP> <brief.md>` (enthält die freigegebene Strategie A–J als verbindliche Vorgabe; verweigert ohne gültige Strategie); Business-Profil, `content-style-guide.md`, Live-Seite (bei OPTIMIZE) und relevante Drive-Vorlage lesen.
4. Content-Paket schreiben (interner Block, SEO Title, Meta Description, H1, H2/H3, Volltexte, CTAs, FAQ, interne Links, Bildhinweise, Schema, Redirect-/Canonical-Hinweis nur als Empfehlung; bei OPTIMIZE: bleibt/ändert/ergänzt/warum).
5. QA: Profil §10 (nichts erfunden), Style-Guide §6, Keyword-Natürlichkeit, keine Doorway-Formulierung, Freigabe-/Revisionskommentar umgesetzt. Bei OPTIMIZE/MERGE zusätzlich: Change Summary + [KEEP]/[EDIT]/[NEW]/[REMOVE] mit Reason, Schutz-Queries abgedeckt – `python3 tools/workflow.py check-draft <draft.md> --opp <OPP>` muss Exit 0 liefern.
6. `python3 tools/workflow.py render <draft.md> <draft.html>` → Drive `create_file` (contentMimeType `text/html`, parentId Ordner „Claude Landingpages“) → natives Google Doc. Benennung: `OPP-04 – Drohnenvermessung Berlin & Brandenburg – Entwurf` bzw. `OPP-02 – Baudokumentation – Optimierung`; Revisionen `… – v2`.
7. db `production` = `draft_ready` + doc_id/url/title, created_at/updated_at, version, history, qa_status, qa_notes, strategy_summary; `review.status = pending`.
8. `python3 tools/workflow.py mirror <tmp>` → Artifact bauen/veröffentlichen → committen.

## Revisionen

Ohne Google-Docs-Editor-Konnektor kann der Agent bestehende Docs nicht bearbeiten. Eine Revision erzeugt daher ein **neues Doc (v2, v3 …)** im selben Ordner; frühere Versionen bleiben erhalten und sind im Artifact verlinkt. Mit eingeschaltetem Google-Docs-Konnektor könnten Revisionen künftig im selben Dokument erfolgen.

## Tests

`dashboard/qa/artifact_qa.js` testet Board, Drag & Drop, Button, Kommentar, Reload, Revision, Gate 2 und Trigger-Aufruf gegen eine simulierte Laufzeit. Echte End-to-End-Tests nur mit Dokumenten `test: true` (Karte „TEST“); Testdateien werden danach entfernt.

## Cleanup 24.11.2026 (vor dem produktiven Start)

Alle Produktions-/Testläufe der Aufbauphase wurden bereinigt: OPP-01 bis OPP-05 stehen wieder auf `gate1.status = pending`, `production.status = not_started`, `review.status = not_started`, ohne aktiven Drive-Entwurf. Die alten Gate-1-Freigaben bleiben unter `gate1.superseded[]` (`superseded_as: test-phase approval`) und im Entscheidungsprotokoll („Test phase · superseded“) erhalten und lösen keine Produktion aus. Frühere Produktionsdaten stehen unter `test_phase`; die Testentwürfe von OPP-03 und OPP-05 liegen im Drive-Papierkorb. Research Log: Ereignis „Workflow Cleanup“ plus die beiden Testentwürfe als superseded. Research-Dossiers und Evidence unverändert. Kein Agentenlauf ausgelöst.


## WordPress (ab 24.11.2026)

Gate 2 stößt den Runner an (`wordpress.status = queued`) – es entstehen nur Drafts. Gate 3 (`gate3.status = approved` für genau die geprüfte Draft-Version, Sichtprüfung bestätigt) ist die einzige Freigabe für Live-Schreibvorgänge; die Sperre steckt in `tools/wordpress.py guard` und `workflow.py queue`. Details: [`wordpress-integration.md`](wordpress-integration.md).

## Entscheidungen: APPROVE · ON HOLD · REJECT (ab 25.11.2026)

Jede CREATE/OPTIMIZE/MERGE-Opportunity hat im Workflow-Drawer drei Entscheidungen:

| Aktion | Wirkung | Persistenz |
|---|---|---|
| **APPROVE** | die jeweilige Gate-Aktion (Gate 1 Strategie · Gate 2 Inhalt · Gate 3 Publish) – der nächste vorgesehene Schritt darf starten | `gate1/gate2/gate3` wie bisher |
| **ON HOLD** | bewusst zurückgestellt: keine Produktion, kein WordPress, kein Publish, aus der aktiven Queue entfernt; Grund und Wiedervorlage-Datum optional; Research/Evidence bleiben und dürfen ergänzt werden | `decision = {status: on_hold, at, reason, review_at, history[]}` |
| **REJECT** | abgelehnt: aus der Pipeline entfernt, kein Runner verarbeitet sie weiter (auch keine Research); Grund optional (Vorlagen oder Freitext); keine Löschung | `decision = {status: rejected, at, reason, reason_code, fingerprint, history[]}` |

- **Audit:** jede Entscheidung zusätzlich in `decisions` (gate 0, `hold` / `reject` / `reactivate`).
- **Reaktivieren** jederzeit im Tab „On Hold“ bzw. „Rejected / Archived“ → `decision.status = active`; vom Runner gestoppte Aufträge (`stopped`) werden auf waiting/queued zurückgesetzt, bestehende Freigaben bleiben gültig. Es startet nichts automatisch.
- **Runner-Sperre im Code:** `tools/workflow.py actions` liefert für on_hold/rejected nur `stopped` (ON HOLD: angeforderte Research weiterhin erlaubt); `tools/wordpress.py guard` verweigert jeden Schreibvorgang (`decision_on_hold` / `decision_rejected`); vor jeder schreibenden Aktion `python3 tools/workflow.py check-active <dir> <OPP>` (Exit 3 = stoppen).
- **Nicht erneut vorschlagen:** beim REJECT werden Typ, Primary Keyword, bestehende Seite, Cluster-Impressionen und -Position gespeichert (`fingerprint`). Erst bei wesentlicher Änderung (Typ/Keyword/Seite anders, Impressionen ±50 %, Position ±5) zeigt das Dashboard „Umstände geändert – erneut prüfen?“ – reaktiviert wird nie automatisch.

Das Board zeigt standardmäßig nur aktive Vorgänge; On Hold und Rejected/Archived liegen in eigenen Tabs (Wiedervorlagen mit Fälligkeit). Auch die Opportunity-Liste filtert standardmäßig auf „Active“.

## Mini-Sitemap je Opportunity

`tools/architecture.py` baut beim Build für jede CREATE/OPTIMIZE/MERGE-Opportunity eine Architektur aus Website-Inventar, IA-Dossier (H_ia), Struktur (G_structure, Abschnitte NEW) und Kannibalisierung. Status: **EXISTING** (im Inventar) · **PROPOSED** (geplante URL einer Opportunity) · **FUTURE / OPTIONAL** (Hub-Option, spätere Unterseite) · **SECTION ONLY** (Abschnitt auf der Seite, keine eigene URL). `validate` bricht den Build ab, wenn ein Knoten weder im Inventar noch geplant ist. Parent-Beziehungen gelten nur als bestätigt, wenn ein bestehender interner Link sie belegt – sonst „Proposed Architecture“. Anzeige: Opportunity-Detail (direkt unter dem Kopf, vor dem Scope) und kompakt im Gate-1-Drawer.
