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
3. **CREATE**: Vorlage = **„Landingpage-Vorlage 2026“ (6813, `client.json → wordpress.create_template`)** – nie eine Live-Seite klonen. Vorlage lesen → neue Element-IDs → Platzhalter-Inhalte nur über `set_content` (Content Layer) gemäß Change Set ersetzen → fehlende Text+Bild-Abschnitte per `duplicate_section(…, mirror=True)` → `alternation` muss ok sein → `firewall_risk` muss frei sein (sonst Stopp: Trustindex-Referenz fehlt) → `pages-create` mit `status: draft`, Slug, Titel; Yoast über `update-post-seo-data` am Draft.
4. **OPTIMIZE**: Ranking Protection Snapshot (GSC-Queries, Klicks, Impressionen, Positionen, Title/H1/H2, Canonical, Robots, interne Links) als `wordpress.baseline` speichern → Live-Seite **nur lesen** (`context=edit`) → Review-Version als **eigene Draft-Seite** (Slug + `-entwurf-seo-autopilot`, Titel mit Präfix) mit kopiertem `_elementor_data`; darin nur [EDIT] per Widget-ID (`set_content`) und [NEW] durch Duplizieren eines passenden Blocks derselben Seite (`duplicate_section`, alternierend) ändern, [KEEP] byte-gleich, [REMOVE] nur mit Freigabe. Vorlage 6813 wird bei OPTIMIZE nicht verwendet.
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

## Sandbox-Schreibtest 24.11.2026 – Ergebnis: Elementor Write **PARTIAL**

Freigegeben als isolierter Sandbox-Test. Quelle: Baudoku-Seite 5401 (`/drohnen-baudokumentation/`), **ausschließlich gelesen** – vorher/nachher `modified 2026-07-16T14:27:04`, Status `publish`, unverändert. Alle Schreibaufrufe gingen nur an den neuen Entwurf **6955 „[TEST SEO-Autopilot] Elementor-Kopie“** (`test-seo-autopilot-elementor-kopie`, Status `draft`, nie veröffentlicht).

| # | Schreibaufruf (nur 6955) | Ergebnis |
|---|---|---|
| 1 | `pages-create` (draft): Hero-Container (3.078 Zeichen) + `_elementor_edit_mode`, `_elementor_template_type`, `_elementor_page_settings` | OK, keine `_content_warnings`; Rücklesen **strukturell identisch** |
| 2 | `pages-update`: Hero + Abschnitte 1, 2, 5, 6 (~30.000 Zeichen, alle Widget-Typen der Seite) | **HTTP 403, Antwort kein JSON** (Firewall – vermutlich das aktive Plugin NinjaFirewall, nicht das Hosting; Firewall-Log nicht eingesehen) – nichts geschrieben (atomar) |
| 3 | Diagnose: nur ein HTML-Widget mit `<script>` (Trustindex-Loader) | **HTTP 403** – Ursache bestätigt |

**Strukturvergleich (Probe):** *identical* – Hero `5592b59e` inkl. H1, Responsive-Werte, `__globals__`, Bild-ID 5165, Page Settings (Schlüsselreihenfolge anders) · *different but functionally equivalent* – Kodierung (`/` statt `\/`, echte Umlaute statt `\u…`), JSON-identisch · *field lost* – keine · *not writable* – HTML-Widgets mit `<script>` (`d8af34e` Abschnitt 1, `568d6a7` Abschnitt 9) · *unknown* – übrige Abschnitte, `post_content`, Yoast (Test gestoppt).

**Gemäß Vorgabe gestoppt** – keine Umgehung (z. B. Kodierung des `<script>`-Tags), Tests 2–5 (Vorschau mit Volltext, H2-Änderung, Restore, Yoast) nicht ausgeführt. Der Test-Draft bleibt bestehen, bis Noel das Löschen bestätigt.

Weitere Erkenntnisse:
- Kein serverseitiger Kopier-/Elementor-Weg: jeder Schreibvorgang muss das **komplette** `_elementor_data` inline übertragen (Baudoku: 91.626 Zeichen ≈ 35k+ Tokens pro Schreibvorgang; Kopie + Änderung + Restore = 3×).
- Meta-only-Änderungen erzeugen **keine WordPress-Revision** (Draft 6955: 0 Revisionen) → Revisionen sind für Elementor kein verlässlicher Rollback-Weg.
- Code: `tools/wordpress.py firewall_risk` / `firewall-check` erkennt blockierte Widgets **vor** dem Schreibaufruf; `guard(..., payload=…)` liefert `payload_blocked_by_firewall`. Statusmatrix `capabilities_verified.elementor` → Guard: `live_optimize_blocked` (OPTIMIZE live), `create_automation_pending` (CREATE veröffentlichen); Drafts bleiben erlaubt.
- Runner-Routine hat weiterhin keinen WordPress-Konnektor → `wp_connector_unavailable` (kein automatisierter Runner-Schreibtest).

**Statusmatrix (ersetzt das pauschale „insufficient“):**

| Bereich | Status |
|---|---|
| Elementor Write | PARTIAL |
| Standard Elementor widgets | VERIFIED |
| Script-containing widgets | BLOCKED BY FIREWALL (vermutlich NinjaFirewall) |
| Live OPTIMIZE automation | BLOCKED |
| CREATE automation | PENDING FULL SANDBOX VALIDATION |
| Rollback | NOT YET VERIFIED |

Test-Draft 6955 bleibt als isolierte Sandbox bestehen (nicht löschen).

## Trustindex – technische Analyse (24.11.2026, nur lesend)

- **Einbindung:** Elementor-**HTML-Widget**, Inhalt nur `<script defer async src='https://cdn.trustindex.io/loader.js?<ID>'>`. Das Script lädt das Widget aus der Trustindex-Cloud und rendert es an seiner Position. Auslöser des 403 ist dieses `<script>` in `settings.html`.
- **Plugin:** keins – Trustindex ist reine Cloud-Einbindung (21 Plugins geprüft). Keine Trustindex-Shortcodes/-Elementor-Widgets verfügbar.
- **Verbreitung:** 12 von 13 Sitemap-URLs (Startseite, Kontakt, alle Leistungsseiten) laden **dieselben zwei** Widget-IDs (`486a09d6…`, `4b8ac4b6…`) – jeweils als **eigene Kopie** im `_elementor_data` der Seite (unterschiedliche Elementor-IDs), nicht über Header/Footer/Template. Konfiguration liegt zentral in der Trustindex-Cloud → überall gleich.
- **Vorbild auf der eigenen Website:** Heyflow ist bereits modular: Script zentral im Elementor-Custom-Code „Heyflow-Verknüpfung“ (`<head>`), Seiten enthalten nur `<heyflow-wrapper>` (kein `<script>`).
- Das vorhandene Template „Trust: Bewertungen“ (5479) ist ein älterer statischer Testimonial-Block ohne Trustindex.
- Firewall-Plugins aktiv: NinjaFirewall (WP Edition), All-In-One Security. Der Elementor-Editor (eingeloggter Admin) speichert Script-Widgets offenbar problemlos; abgewiesen wird der Schreibweg über die REST-API/Jetpack.

## Architektur: Referenz statt Script

Ziel: `Elementor-Seite → Template-Referenz → zentrales Template mit Trustindex → Trustindex rendert` statt `Elementor-Seite → HTML-Widget mit <script>`.

| Option | Darstellung | SEO | Neues Plugin | Ladezeit | API-kompatibel | Zentral | Sicherheit | Bewertung |
|---|---|---|---|---|---|---|---|---|
| T1 Zentrales Elementor-Template + Pro-Widget „Template“ | gleich | neutral | nein | gleich | ja (nur `template_id`) | ja | gut | **empfohlen** |
| T2 Shortcode `[elementor-template id=…]` | gleich | neutral | nein | gleich | ja | ja | gut | gleichwertig |
| T3 Custom Code + Platzhalter (wie Heyflow) | unklar (Trustindex rendert an Script-Position) | neutral | nein | gleich/leicht schlechter | ja | ja | gut | nur nach Prüfung Trustindex-Doku |
| T4 Trustindex-WordPress-Plugin | wahrscheinlich gleich | neutral | **ja** | eher schlechter | ja | ja | mehr Angriffsfläche | nicht empfohlen |
| T5 Firewall-Ausnahme | gleich | neutral | nein | gleich | ja | nein (12 Kopien bleiben) | schwächer | **nur Fallback** |

Umsetzung T1 (später, freigabepflichtig): Noel legt im Elementor-Editor zwei Templates an („Trustindex – Bewertungen A/B“) – das Script wird dabei vom eingeloggten Editor gespeichert, nicht über die API. Seiten referenzieren nur noch die Template-ID. Live-Seiten werden erst nach eigener Freigabe umgestellt.

## Brauchen wir überhaupt 1:1-Kopien? – CREATE ≠ OPTIMIZE

- **CREATE:** nie eine Live-Seite klonen. Kontrollierte SEO-Landingpage-Vorlage: wenige Template-Widgets (Hero-Stil, Trust/Bewertungen, Ablauf, CTA/Heyflow) + SEO-Inhalte als Standard-Widgets (Heading, Text, Bild, FAQ). Payload ca. 5–15 KB statt ~92 KB, keine Scripts, gleichbleibendes Design. Ausgangsmaterial vorhanden: „Landingpage-Vorlage 2026“ (6813), „Vorlage: Dachinspektion LP“ (6905), „Hero-Area“ (6758), Bausteine Trust/Preise/Ablauf.
- **OPTIMIZE:** bestehende Struktur erhalten; nur freigegebene Widgets (per Elementor-ID) ändern, alle übrigen Knoten unverändert übernehmen. Solange die Seite Script-Widgets enthält, bleibt Live OPTIMIZE blockiert; nach Umstellung auf Template-Referenzen ist sie API-schreibbar. Die Payload bleibt seitengroß, sinkt aber mit jeder modularisierten Sektion.

## Nächster Test (vorgeschlagen, nicht ausgeführt) – S2 Template-Referenz

Nur Draft 6955; keine Live-Seite, kein Plugin, keine Firewall, kein neues Template. In 6955 einen Container mit dem Elementor-Pro-Widget „Template“ schreiben, das auf das bestehende statische Template 5479 verweist, plus Abschnitt 2 (Icon-Boxen). Prüfen: kein 403 · Rücklesen strukturell identisch · Vorschau zeigt Template-Inhalt · 5401 und 5479 unverändert.

## Fallback: Firewall-Ausnahme

Möglich (Whitelist für den REST-Schreibweg in NinjaFirewall bzw. beim Hosting), aber **nicht bevorzugt**: Scripts blieben über die API schreibbar, die 12 Kopien blieben dezentral. Die Firewall wird nicht umgangen und ihre Regeln werden nicht verändert.

## Separater Blocker (nicht WordPress): F-025 Runner repository write/push unavailable

Die Runner-Routine kann nicht ins Repository pushen (403); Ergebnisse wie das OPP-01-Research-Nachholen gehen im Repository verloren. Wird separat gelöst.

## Rollback

Primär: eigener Pre-change Snapshot (Elementor-Daten, Content, Yoast, Seiteneinstellungen, Zeitstempel, SHA-256) in Drive. Sekundär: WordPress-Revisionen (lesbar, z. B. Baudoku-Seite mit Revisionen vom 16.07.2026). Duplicator ist nicht Voraussetzung (aktuell ohne Backups). Rollback gilt erst als verfügbar, wenn ein Sandbox-Test bestätigt, dass `_elementor_data` per Konnektor vollständig geschrieben und identisch zurückgelesen werden kann – Stand 24.11.2026: **unavailable** (Firewall blockiert `<script>`-Widgets, siehe oben).

## Produktionsstandard ab 25.11.2026: Vorlage für CREATE, bestehende Seite für OPTIMIZE

Entscheidung Noel: Neue SEO-Landingpages entstehen aus dem vorhandenen Elementor-Template **„Landingpage-Vorlage 2026“ (ID 6813)**. Keine Live-Seite klonen, keine eigene Landingpage-Struktur bauen. Bei OPTIMIZE ist die bestehende Seite selbst die Vorlage.

**CREATE:** Gate 2 → neuer Draft → Vorlage 6813 anwenden → Platzhalter-Inhalte durch das Drive-Change-Set ersetzen → bei Bedarf passende Text+Bild-Blöcke duplizieren/spiegeln → Yoast → WordPress QA → visuelle Prüfung → Gate 3 → Publish.

**OPTIMIZE:** Live-Seite → separate Draft-Kopie → KEEP unverändert · EDIT gezielt · NEW durch Duplizieren eines passenden Blocks derselben Seite · REMOVE nur nach Freigabe → Preview → QA → visuelle Prüfung → Gate 3 → kontrollierte Übernahme.

### Layer-Trennung (Code: `tools/wordpress.py`)

| CONTENT LAYER – Agent bearbeitet | DESIGN/TEMPLATE LAYER – bleibt erhalten |
|---|---|
| H1/H2/H3, Fließtext, FAQ, CTA-Texte/-Ziele, interne Links, Bildzuordnung, Yoast | Container, Abstände, Responsive, Farben, Typografie, Trustindex, Formulare/Heyflow, Karussells, wiederkehrende Komponenten |

`set_content(tree, id, …)` erlaubt nur Content-Schlüssel je Widget-Typ (Überschrift `title`, Text `editor`, Button `text`/`link`, Bild `image`/`link` …) und lehnt Design-Schlüssel sowie HTML/Formular/Karussell-Widgets ab.

### Layoutregel: Text+Bild alternieren

Text | Bild → Bild | Text → Text | Bild … – nie zwei aufeinanderfolgende Text+Bild-Abschnitte mit gleicher Ausrichtung, sofern kein bewusster Designgrund dagegen spricht. `alternation(tree)` prüft das; zusätzliche Abschnitte entstehen mit `duplicate_section(tree, id, mirror=True)` (neue eindeutige Elementor-IDs, Design/Abstände/Responsive/Styling identisch, Text- und Bild-Spalte getauscht). Kein eigenes Design, wenn ein Baustein existiert.

### Analyse „Landingpage-Vorlage 2026“ (25.11.2026, nur lesend)

- **Gefunden:** eindeutig, ID **6813**, `elementor_library`, Elementor-Typ **page**, zuletzt geändert 05.06.2026.
- **Umfang:** 81.793 Zeichen, 12 Abschnitte: 0 Hero (H1) · 1 Text\|Bild + CTA + **Trustindex A** · 2 Bild\|Text + CTA · 3 Heyflow-Formular · 4 Logo-Karussell · 5 Bild\|Text + CTA · 6 Kundenstimmen (**Trustindex B**) · 7 Text\|Bild · 8 Bild\|Text + CTA · 9 Prozess (Icon-Liste) + Call-to-Action · 10 Benefits (3 Icon-Boxen) · 11 Text\|Bild.
- **CTAs:** 4 Buttons → /kontakt/, Heyflow-Formular, Call-to-Action-Bild. **Formulare:** kein Elementor-Formular, Heyflow-Platzhalter ohne Script.
- **Scripts:** 2 Trustindex-HTML-Widgets (`77052669`, `1349b3ec`), dieselben IDs wie auf allen Seiten.
- **Global/Responsive:** 33 globale Farb-/Typo-Referenzen, 57 verschiedene Tablet/Mobile-Einstellungen.
- **Alternation:** 1 Text\|Bild · 2 Bild\|Text · 5 Bild\|Text · 7 Text\|Bild · 8 Bild\|Text · 11 Text\|Bild – einzige Wiederholung 2→5 (dazwischen Formular + Logos).
- **Wie Elementor einfügt:** im Editor „Bibliothek → Einfügen“ = **Kopie** der Template-Daten mit neuen Element-IDs, gespeichert per admin-ajax als eingeloggter Admin. Die Pro-Referenz („Template“-Widget) bettet live ein – dann wären Inhalte nicht seitenindividuell.
- **Über den Konnektor:** kein Elementor-Insert-Mechanismus (keine Elementor-Fähigkeit, kein admin-ajax). Die Vorlage lässt sich nur als ganzes `_elementor_data` schreiben – inkl. der zwei Trustindex-Scripts → 403. Dasselbe gilt für jede spätere Inhaltsänderung an einer Seite, die die Scripts enthält.

**Antworten:** (1) ja, eindeutig · (2) 6813 · (3) Editor-Kopie per admin-ajax · (4) **nein, solange die Vorlage Trustindex als `<script>` enthält** · (5) ja technisch (lesen → Content-Widget per ID ändern → ganzes `_elementor_data` zurückschreiben), nur ohne Script · (6) ja – offline an der Vorlage verifiziert.

**Kleinste Änderung, die den Vorlagen-Weg vollständig API-tauglich macht (freigabepflichtig, nicht umgesetzt):** in Vorlage 6813 die zwei Trustindex-HTML-Widgets durch je ein Pro-Widget „Template“ ersetzen, das auf ein kleines Trustindex-Template verweist (im Elementor-Editor angelegt). Trustindex bleibt Template Layer, das Design bleibt gleich.

### S3 Sandbox Test – Landingpage-Vorlage 2026 (vorgeschlagen, nicht ausgeführt)

Nur Draft 6955. Vorlage 6813 mit neuen IDs in 6955 schreiben – die zwei Trustindex-Widgets durch eine markierte Platzhalter-Zeile ersetzt (`script_free_copy`), alles andere 1:1. Zweiter Schreibvorgang: H1 + eine H2 + ein Text ersetzen (`set_content`), Abschnitt 11 duplizieren + spiegeln (`duplicate_section`). Prüfen: kein 403 (auch Heyflow-HTML) · Design-/Responsive-Werte identisch zur Vorlage, nur Content abweichend · gespiegelter Block korrekt · Vorschau wie Vorlage · 6813 und Live-Seiten unverändert. Aufwand: 2 Schreibvorgänge à ~80.000 Zeichen.
