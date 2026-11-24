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
