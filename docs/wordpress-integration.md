# WordPress-Integration – Preflight (24.11.2026)

Nur Diagnose, ausschließlich lesend. Nichts erstellt, geändert, gespeichert, veröffentlicht oder gelöscht. Keine Zugangsdaten im Repository oder Artifact.

## Ergebnis

| Prüfpunkt | Ergebnis |
|---|---|
| **WordPress Access** | **YES** (lesend geprüft) |
| Access Method | Claude-Konnektor **WordPress.com** (OAuth) → Website über **Jetpack** verbunden (Blog-ID 174454219, Plattform „jetpack“, Site-Werkzeuge verfügbar). Zusätzlich öffentliche WP-REST-API (`/wp-json`) ohne Anmeldung |
| Authentication | vorhanden über den Konnektor (OAuth des WordPress.com-Kontos). In der Umgebung **keine** Secrets/Application Passwords hinterlegt, kein Browser-/Computer-Zugriff |
| Permissions | Rolle **administrator** (`core/get-user-info`, nur Feld „roles“ gelesen) – volle Schreib- und Veröffentlichungsrechte technisch vorhanden |
| Weitere Seite im Konto | Ein zweiter Standort ist sichtbar (nicht Teil des Projekts) – wird nie angefasst; Ziel immer per Blog-ID 174454219 |
| Editor / Page Architecture | **Elementor (+ Elementor Pro), Theme Hello Elementor.** Alle 17 veröffentlichten Seiten + 1 private Testseite („testumgebung“) sind Elementor-Seiten (`_elementor_edit_mode: builder`). Inhalt liegt als JSON-Baum in `_elementor_data` (Baudoku-Seite: ~92 KB, 13 Hauptcontainer, 50 Container, 14 Überschriften, 6 Text-Editor-, 6 Bild-, 6 Icon-Box-, 6 Button-, 3 HTML-Widgets, Karussell, CTA). Keine Beiträge, keine Gutenberg-Blöcke, keine eigenen Post-Types (nur page/post/attachment/Menü/Templates) |
| Yoast / SEO Access | **YES** über die von der Website veröffentlichten Yoast-Fähigkeiten: lesen (`yoast-seo/get-post-seo-data`: SEO-Title, Meta Description, Fokus-Keyphrase, Canonical, Robots, Schema-Typ, Scores) und schreiben (`yoast-seo/update-post-seo-data`) |
| Weitere Plugins (REST-Namespaces) | Jetpack (+ Boost, Stats), Google Site Kit, Duplicator, BackWPup, WP Super Cache, Post SMTP, All-in-One Security, Elementor AI, Elementor MCP Composer, WordPress Abilities/MCP-Adapter |
| Backups | **Duplicator: keine abgeschlossenen Backups** („Not protected“). BackWPup-Status über lesende Werkzeuge nicht abrufbar → vor dem ersten Schreibzugriff manuell prüfen bzw. Backup anlegen |
| Umgebung | Produktion, WordPress 7.1.5, PHP 8.3 |
| **CREATE Draft technically possible** | **YES** – Seite mit `status: draft` anlegen (Titel, Slug, Inhalt, Medien, Yoast-Daten). Einschränkung: Für ein Layout wie die bestehenden Landingpages muss `_elementor_data` (JSON) erzeugt werden, idealerweise als Kopie einer bestehenden Seite mit ersetzten Texten; reines HTML im Inhaltsfeld ergibt eine Seite ohne das Elementor-Layout |
| **OPTIMIZE existing page safely possible** | **WITH LIMITATIONS** (siehe unten) |
| Preview link retrievable | **YES** für Entwürfe (`?page_id=<ID>&preview=true`, nur eingeloggt sichtbar). Öffentliche Vorschau-Links ohne Login: für Jetpack-Seiten nicht bestätigt |
| Publish technically possible | **YES – ausdrücklich gesperrt** (Administrator-Rechte; der Workflow ruft Veröffentlichen nie automatisch auf) |

## OPTIMIZE: Risiken bei Elementor

1. **Eine veröffentlichte Seite hat in WordPress keinen „Entwurf daneben“.** Jede Änderung über die API an einer veröffentlichten Seite ist sofort live; ein Statuswechsel auf `draft` würde die Seite offline nehmen. → Niemals die Live-Seite direkt bearbeiten.
2. **Der sichtbare Inhalt kommt aus `_elementor_data`, nicht aus dem Inhaltsfeld.** Eine Änderung am Inhaltsfeld ändert die Seite nicht (oder wird beim nächsten Elementor-Speichern überschrieben). Änderungen müssen gezielt im JSON-Baum erfolgen (bestimmte Heading-/Text-Editor-Widgets per ID), sonst droht Layoutverlust.
3. **Elementor-CSS/Caches** (Elementor-CSS-Dateien, WP Super Cache, Jetpack Boost) werden beim Speichern per API ggf. nicht neu erzeugt → Darstellung im Entwurf muss geprüft werden.
4. **Keine Backups bei Duplicator.**

**Sicherer Weg für OPTIMIZE:** Die bestehende Seite als **separaten Entwurf kopieren** (eigene Draft-Seite, z. B. „[Entwurf] OPP-02 – Baudokumentation“, Slug mit Suffix, Yoast noindex), darin nur die im Change Set markierten Widgets ändern ([KEEP] bleibt unverändert). Vorschau prüfen. Erst nach finaler Freigabe wird der geprüfte Inhalt (bzw. `_elementor_data`) in die Live-Seite übernommen – URL, Slug, Canonical und Indexierung der Live-Seite bleiben unverändert – und der Kopier-Entwurf gelöscht. Vorher: Backup bzw. WordPress-Revision der Live-Seite sichern (Rollback).

## Geplanter Workflow – geprüft gegen die Technik

| Schritt | Technisch | Anmerkung |
|---|---|---|
| Research → Gate 1 → Drive-Entwurf → Gate 2 | vorhanden | |
| **WordPress Draft** | möglich | CREATE: neue Draft-Seite; OPTIMIZE: Kopie als Draft (s. o.). Gate 2 erzeugt höchstens einen Draft |
| WordPress QA | möglich | Draft lesen (`pages-get`, Elementor-JSON, Yoast-Daten), Abgleich mit dem Drive-Entwurf und der Ranking Protection List, gerenderte Vorschau prüfen |
| „WordPress Draft created“ + Link im Artifact | möglich | Bearbeitungs-Link `wp-admin/post.php?post=<ID>&action=elementor` und Vorschau-Link (Login nötig) |
| Final Publish Approval → Publish | möglich, **gesperrt** | nur nach separater Freigabe; nie automatisch |
| Monitoring | vorhanden | Ranking Protection + Kannibalisierung T+7…T+90 |

## Sicherheitsregeln (gelten ab jetzt)

Nie automatisch: veröffentlichen · veröffentlichte Seiten löschen · URL/Slug einer veröffentlichten Seite ändern · Redirects · Canonical · Indexierung (noindex/robots) · WordPress-/Plugin-/Theme-/Server-Konfiguration · Menüs · Yoast-Website-Einstellungen · Backup-/Duplicator-/BackWPup-Aktionen. Ziel immer per Blog-ID 174454219 (nie die zweite Seite im Konto). Erlaubt nach Gate 2: genau ein WordPress-Draft je Dokument des Change Sets (CREATE: neue Draft-Seite; OPTIMIZE: Draft-Kopie), Yoast-Daten nur am Draft.

## Empfohlene Integrationsmethode

**WordPress.com-Konnektor über Jetpack** (bereits verbunden, Administrator) – keine zusätzlichen Application Passwords nötig:
- Seiten lesen/anlegen: `wpcom-mcp-pages-*` (`status: draft`, nie `publish`)
- Yoast: `remote:yoast-seo/get-post-seo-data` / `update-post-seo-data`
- Medien: `wpcom-media-upload`
- Elementor-Layout: `_elementor_data` der Vorlage kopieren und gezielt ändern

Offen vor dem Bau:
1. Konnektor auch an der Routine „SEO Autopilot – Workflow-Runner“ hinterlegen (wie Google Drive), sonst kann der Runner WordPress nicht erreichen.
2. Backup-Strategie klären (Duplicator ohne Backups; BackWPup prüfen) – vor dem ersten Schreibzugriff.
3. Optional ein eingeschränkter WordPress-Benutzer (Rolle Redakteur) für den Autopiloten statt Administrator.
4. Erster Test an der privaten Seite „testumgebung“ bzw. einer neuen Test-Draft-Seite.

---

# Produktionsarchitektur (vorbereitet 24.11.2026 – noch kein Schreibzugriff ausgeführt)

```
Research → Gate 1 (Strategie) → Drive-Entwurf → Gate 2 (Inhalt) → WordPress Draft → WordPress QA → Gate 3 (Publish) → Live Update → Monitoring
```

| Gate | Bedeutung | Technische Wirkung |
|---|---|---|
| Gate 1 | Strategie, Scope, geplante Änderungen | Drive-Entwurf (Change Set) |
| Gate 2 | Inhalt aus Drive für die technische Umsetzung | `wordpress.status = queued` → Runner erstellt **nur Drafts**. Nie Publish |
| Gate 3 | Die in WordPress vorbereitete Version nach Sichtprüfung | `gate3.status = approved` + `for_draft_version` → einziger Weg zu Live-Schreibvorgängen |

## Harte Schreibsperre (`tools/wordpress.py guard`)

Vor **jedem** WordPress-Schreibaufruf: `python3 tools/wordpress.py guard <op> <wf_doc.json> [--post ID] [--fields …] [--status …] [--slug …] [--live-slugs …]`. Exit 0 = erlaubt, Exit 3 = verboten (Aufruf unterbleibt, Grund wird im Workflow vermerkt). `workflow.py queue` liefert `wp_publish` nur, wenn der Guard es erlaubt – sonst `wp_publish_blocked` mit Grund.

| Operation | Bedingung |
|---|---|
| `create_draft` | Gate 2 · status `draft` · Slug keiner veröffentlichten Seite |
| `update_draft`, `yoast_update_draft` | Gate 2 · nur vom Agenten angelegte Draft-Seiten (Registry `wordpress.documents[].draft_post_id`) · bleibt `draft` |
| `live_update`, `yoast_update_live` (OPTIMIZE) | Gate 3 für genau diese Draft-Version · QA bestanden (bei manueller Sichtprüfung: bestätigt) · verifizierter Pre-change Snapshot dieser Seite · Rollback verfügbar · Seite im Change Set |
| `publish_draft` (CREATE) | Gate 3 · QA bestanden · eigener Draft |
| `delete`, `slug_change_live`, `redirect`, `canonical_change`, `robots_change`, `unpublish`, Einstellungen/Plugins/Menüs | **nie automatisch** – nur mit gesonderter Bestätigung (`confirmations[]`) |
| sensible Felder (`slug`, `status`, `canonical`, `noindex`, …) bei Updates | immer verboten |

## Runner: Preflight WordPress

Beobachtungen sammeln (`tools` geladen, `wpcom-user-sites` gefiltert auf die Domain, Rolle via `remote:core/get-user-info` nur Feld „roles“, Fähigkeiten via `search_remote_abilities`) → `python3 tools/wordpress.py preflight obs.json`. Exit 2 → `wordpress.status = blocked` mit `block_reason` (`wp_connector_unavailable`, `wp_wrong_site`, `wp_capabilities_missing`, `wp_yoast_unavailable`). **Nie** auf eine andere verbundene Website ausweichen; Ziel immer Blog-ID aus `client.json`.

## Runner: `wp_draft`

1. Claim `wordpress.status = preparing`, `started_at`.
2. **Change Set** aus dem freigegebenen Drive-Dokument + Dossier (`P_diagnosis.change_summary`, `G_structure.sections[].action`, Yoast-Vorschläge, `H_ia.internal_links`, Companions) als `change_set.json` aufbauen. Drive Change Set = verbindliche Produktionsanweisung.
3. **CREATE**: Vorlage = bestehende Landingpage mit gleichem Aufbau (nur lesen) → `_elementor_data` kopieren, Texte gemäß Change Set ersetzen, `pages-create` mit `status: draft`, gewünschtem Slug, Titel; Yoast über `update-post-seo-data` am Draft.
4. **OPTIMIZE**: Ranking Protection Snapshot (GSC-Queries, Klicks, Impressionen, Positionen, Title/H1/H2, Canonical, Robots, interne Links) als `wordpress.baseline` speichern → Live-Seite **nur lesen** (`context=edit`) → Review-Version als **eigene Draft-Seite** (Slug + `-entwurf-seo-autopilot`, Titel mit Präfix) mit kopiertem `_elementor_data`; darin nur [EDIT]/[NEW] ändern, [KEEP] byte-gleich, [REMOVE] nur mit Freigabe.
5. Pro Change-Set-Dokument (inkl. Companion) ein Draft; Registry `wordpress.documents[]` mit `url`, `wp_post_id` (Live), `draft_post_id`, `edit_link` (`/wp-admin/post.php?post=<ID>&action=elementor`), `preview_link` (`/?page_id=<ID>&preview=true`), `original_link`; `draft_version + 1`.
6. **QA**: Draft + Yoast zurücklesen → `python3 tools/wordpress.py qa change_set.json original.json|- draft.json yoast.json` (Content · SEO · Technical; Visual immer „Manual review required“, nie erfunden). `wordpress.qa`, `change_counts`, `publish_summary` schreiben → `qa_passed` bzw. `qa_failed`.
7. **OPTIMIZE**: Pre-change Snapshot der Live-Seite (`wordpress.py snapshot` → als JSON-Datei in Drive speichern, zurücklesen, `verify-snapshot` mit Hash) → `wordpress.snapshots[]` mit `stored_doc_id`, `verified`; `rollback = rollback_status(...)` (Schreibweg `_elementor_data` muss durch den Sandbox-Test bestätigt sein, sonst **Rollback protection unavailable** → Gate 3 gesperrt).
8. Research-Log-Eintrag „WordPress Draft vorbereitet“ (Quellen: Draft, Live-Seite, Snapshot).

## Runner: `wp_publish` (nur nach Gate 3)

1. `workflow.py queue` muss `wp_publish` liefern; vor jedem Aufruf erneut `wordpress.py guard`.
2. Snapshot unmittelbar vorher erneut prüfen (Live-Seite seit Snapshot unverändert? sonst `publish_failed`, neuer Snapshot + erneutes Gate 3).
3. **CREATE**: Draft → `status: publish` (einziger erlaubter Statuswechsel). **OPTIMIZE**: `_elementor_data` (+ Page-Settings) und Yoast-Felder des Drafts in die Live-Seite übernehmen; Titel/Slug/Canonical/Robots der Live-Seite bleiben unverändert. Danach Review-Draft **nicht** löschen (Löschen braucht Bestätigung) – nur als erledigt markieren.
4. Zurücklesen und mit dem Draft vergleichen; bei Abweichung Rollback aus Snapshot und `publish_failed`.
5. `wordpress.status = published`, `published.at`, `published.change_entry = wordpress.change_log_entry(...)` (Baseline + T+7/14/30/60/90 mit Ranking Protection + Kannibalisierung); `workflow.py mirror` übernimmt den Eintrag ins Change Log. Research-Log-Eintrag „Live-Update veröffentlicht“.

## Rollback

Primär: eigener Pre-change Snapshot (Elementor-Daten, Content, Yoast, Seiteneinstellungen, Zeitstempel, SHA-256) in Drive. Sekundär: WordPress-Revisionen (lesbar, z. B. Baudoku-Seite mit Revisionen vom 16.07.2026). Duplicator ist nicht Voraussetzung (aktuell ohne Backups). Rollback gilt erst als verfügbar, wenn der Sandbox-Test bestätigt, dass `_elementor_data` per Konnektor geschrieben und identisch zurückgelesen werden kann.
