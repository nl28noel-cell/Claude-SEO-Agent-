# Research-/Strategy-Stufe der Opportunity Engine (vor Gate 1)

Stand 23.11.2026. Gilt für jede Opportunity vom Typ **CREATE, OPTIMIZE, MERGE**. Gate 1 ist damit eine **Strategie-Freigabe**: Noel entscheidet auf Basis eines vollständigen Dossiers, nicht auf Basis einer Keyword-Zeile.

```
Opportunity erkannt → Research (A–J) → Research-Status → Gate 1 „Strategie freigeben“ → Entwurf (Drive) → Review → Gate 2
```

## Dossier

Eine Datei je Opportunity: `clients/<client>/state/research/<OPP>.json` (leeres Gerüst: `python3 tools/research.py skeleton <client> <OPP>`).
Rohdaten der Recherche (Seitenprofile, Notizen) liegen unter `clients/<client>/data/research/<OPP>/`.

| Abschnitt | Inhalt | Pflichtfelder |
|---|---|---|
| A · Executive Decision | CREATE/OPTIMIZE/MERGE/MONITOR/IGNORE, Ziel-URL, Begründung, geprüfte Alternativen, Gate-1-Frage | decision, summary, why, gate1_question |
| B · Search Demand | Keywords mit Rolle (primary/secondary/supporting/do_not_target), Volumen/KD/CPC (Semrush), GSC-Impressionen/Positionen, Intent | keywords |
| C · Live SERP | Quelle + Qualität (`validated`/`indicative`/`missing`), Intent-Urteil, **SERP competitors** (von Semrush als rankend bestätigt: Keyword, Position, URL) und **Research competitors** (Web-/Marktrecherche, ohne Positionen) | source, quality, intent_verdict, ≥ 1 Wettbewerberliste |
| D · Competitor Insights | Je relevantem Business-Wettbewerber: H1/Positionierung, Themen, Zielgruppe, FAQ, Trust/Proof, lokaler Fokus, Conversion, Takeaway | ≥ 1 Eintrag |
| E · Content Gap | Competitors cover · We already cover · We are missing · Opportunity to outperform | alle vier |
| F · Recommended Page Scope | Kernbotschaft, Intent, Zielgruppe, Key Questions, Leistungsinfos, Trust/Proof, Conversion-Ziel, **bewusst nicht auf dieser Seite** (mit Zielseite) | alle |
| G · Proposed Structure | Title-Vorschlag, H1, H2/H3 mit Zweck, Herleitung – keine ausformulierten Texte | h1, sections |
| H · Information Architecture | **Current** und **Recommended Architecture** (Parent, Target, Children, Siblings; Hub-Prüfung; Child-Kandidaten nur bei eigenständigem Intent), Konsolidierung (welche Begriffe auf eine URL und warum), Keyword Ownership + Do-not-target, interne Links, Kannibalisierung (GSC-Evidenz), Entscheidung | current, recommended, consolidation, keyword_ownership, internal_links, cannibalization, decision |
| I · How We Can Win | Hebel aus belegten Business-Assets | ≥ 1 |
| J · Risks / Unknowns | Risiken und offene Fragen mit Umgang | ≥ 1 |

Regeln: Von Rankingpositionen oder SERP-Dominanz darf nur bei **SERP competitors** gesprochen werden. Research competitors sind „gefunden“, nicht „rankend“. Wettbewerbertexte werden analysiert, nie übernommen. Wortzahlen sind Kontext, kein Ziel. Vorteile nur aus dem Business-Profil (§8), nichts erfinden (§10).

## Research-Status (`tools/research.py derive`)

| Status | Bedeutung | Gate 1 |
|---|---|---|
| `complete` | Alle Abschnitte gefüllt, echte SERP über Semrush (SERP competitors vorhanden) | normal |
| `complete_with_limits` | Alle Abschnitte gefüllt, dokumentierte Grenzen (z. B. SERP nur indikativ) | normal, Grenzen sichtbar |
| `incomplete` | Abschnitt fehlt oder offener Punkt in `status.pending` (z. B. „SERP validation pending“) | nur mit **Override** (protokolliert) |
| `not_started` | Kein Dossier | nur mit **Override** |

Der deklarierte Status wird nie besser angezeigt, als die Daten hergeben: fehlende Pflichtfelder → `incomplete`, `complete` ohne validierte SERP → `complete_with_limits`.

## Gate 1 = Strategie-Freigabe

Das Artifact speichert bei Gate 1 `gate1.research_version`, `research_state` und ggf. `research_override`. Produziert wird nur, wenn `research.strategy_ok(gate1, dossier)` wahr ist:

- `research_version` = aktuelle Dossier-Version, Research `complete`/`complete_with_limits` → ok
- `research_override = true` → ok (bewusste Entscheidung, im Briefing markiert)
- sonst: Runner-Queue liefert `hold` (`research_missing`, `research_incomplete`, `strategy_not_approved`), `workflow.py brief` verweigert. Kein „blocked“ – es ist kein technischer Fehler.

Gate-1-Freigaben **vor** Einführung dieser Stufe (ohne `research_version`) gelten nicht als Strategie-Freigabe: Die Karte steht wieder in „Zur Prüfung“ mit „Strategie-Freigabe ausstehend“; die alte Freigabe bleibt im Verlauf. Bereits fertige Entwürfe (`draft_ready`, Gate 2) und Revisionen sind davon nicht betroffen.

Ändert sich das Dossier wesentlich, wird `version` erhöht – eine frühere Freigabe gilt dann nicht mehr für die neue Strategie.

## Echte SERP: Semrush Organic Results (`tools/serp.py`)

Semrush ist die **primäre Quelle für echte SERP-Rankings**. Ablauf je Opportunity:

1. `python3 tools/serp.py plan <client> <OPP>` – Abfrageplan, führt nichts aus
   - **Primary Keyword zuerst.** Secondary nur mit `serp_check: true` im Dossier (B), d. h. wenn ein anderer Intent möglich ist oder eine Konsolidierungsfrage nur so zu klären ist.
   - Ähnliche Keywords werden auf einen Schlüssel normalisiert (Umlaute, Stoppwörter, Plural, Wortreihenfolge) und nur einmal abgefragt.
   - Frischer Cache (`data/serp-cache/<db>/`, **TTL 30 Tage** für SERP-Rankings; Keyword-/Volumendaten bis 180 Tage) → keine Abfrage.
   - Urteil: `run` · `budget_hold` · `none` (Cache) · `approval_required`.
2. Nur bei `run`: Semrush-Konnektor `get_report_schema("phrase_organic")` (kostenlos, `price` prüfen) → `execute_report("phrase_organic", {phrase, database: "de", display_limit: 10})`.
3. `python3 tools/serp.py ingest "<keyword>" <ergebnis.csv|json>` → Cache, Units verbuchen (`config/semrush_budget.json`, Log `data/serp-cache/usage-log.csv`).
4. Ranking-URLs mit `tools/page_profile.py` abrufen → C (`serp_competitors`), D, E, I aktualisieren, `C_serp.quality = validated` → Status `complete`.

### Kostenlogik (geprüft 23.11.2026, developer.semrush.com → Keyword reports → Organic Results)

| Größe | Wert |
|---|---|
| Report | `phrase_organic` (Organic Results) |
| Preis | **10 Units je zurückgegebener Ergebniszeile**; historische Daten (`display_date`) 50 Units je Zeile – nie verwenden |
| Begrenzung | `display_limit=10` → Top 10 = **max. 100 Units je Keyword**; weniger Zeilen = weniger Units |
| Formel | Kosten = Keywords × Zeilen × 10 |
| Beispiel OPP-02 | Primary only: 1 × 10 × 10 = **100 Units**; mit Secondary: 200 Units |

## SERP Validation: zwei unabhängige Quellen

| | Source A – **Semrush SERP** | Source B – **Independent Web Research** |
|---|---|---|
| Was | Echte Google-Rankingdaten (`phrase_organic`, DE) | Eigenständige Suche durch Claude (WebSearch) + Live-Abruf der gefundenen Seiten |
| Liefert | Position, Domain, Ranking-URL, SERP Features | Sichtbare Anbieter, Seitentypen, Inhalte der gefundenen Seiten |
| Liefert nicht | – | **Keine Google.de-SERP, keine Positionen.** Der Suchindex ist US-basiert, ohne Standort-/Sprachsteuerung, und je nach Modus (Standard/Extended) unterschiedlich – nicht reproduzierbar |
| Kosten | 10 Units je Zeile | 0 Units |
| Rolle | Ranking-Wahrheit; nur hier „Position“ oder „Dominanz“ | Discovery- und Validierungsquelle |
| Im Dossier | `C_serp.serp_competitors` | `C_serp.research_competitors` + `C_serp.validation.independent_web` |

**Standard:** Independent Web Research läuft für jedes Primary Keyword (Pflicht: ohne sie ist das Dossier `incomplete`). Secondary Keywords nur mit `serp_check: true` (erkennbar anderer Intent); ähnliche Keywords werden über denselben Normalisierungsschlüssel wie bei Semrush nicht wiederholt (`serp.py plan` → `web_research`).

**Cross-Validation** (`python3 tools/serp.py validate <client> <OPP>`, im Artifact Abschnitt C), vergleicht Domains, nie Positionen:
- In beiden Quellen · nur Semrush · nur Web Research
- **Cross-source agreement:** Anteil der Semrush-Top-10-Domains, die die Web Research auch gefunden hat: ≥ 50 % High, 25–50 % Medium, < 25 % Low; weicht der dominante Seitentyp ab (z. B. Semrush: Software, Web: Dienstleister), eine Stufe tiefer.
- **Auffälligkeiten (⚑, manuell prüfen):** rankende Business-Wettbewerber, die die Web Research nicht gefunden hat; abweichender Seitentyp-Mix/Intent; viele Web-Funde, die nicht ranken.
- Ohne Semrush: „Semrush SERP: Pending – budget hold · Independent Web Research: Completed · Agreement: nicht bewertbar“.

### Budget (`config/semrush_budget.json`)

- `units_balance` (Kontostand), `reserve_units` (aktuell 250 = gesamter Bestand als Reserve), `max_units_per_opportunity` (200), `auto_use`.
- Automatische Nutzung nur, wenn `units_balance − Kosten ≥ reserve_units`; sonst `budget_hold`, Research bleibt `complete_with_limits`.
- **Kontostand (geprüft 23.11.2026):** Über die vorhandene Semrush-Anbindung **nicht automatisch lesbar**. Der Claude-Konnektor (OAuth) stellt nur Report-/Projekt-Werkzeuge bereit, keinen Kontostand. Der offizielle kostenlose Endpunkt `countapiunits` braucht einen API-Key, der bewusst nicht eingerichtet wird.
- Deshalb Ledger: Jede Abfrage bucht ihre Units über `serp.py ingest` automatisch ab (Log `data/serp-cache/usage-log.csv`). Meldet der Konnektor `no_api_units` → `serp.py no-units` (Kontostand 0). Manuell nur nach Aufladung/Abgleich mit Semrush (Subscription info → API units): `python3 tools/serp.py set-balance <units>`. Danach führt der nächste Research-Lauf die geplanten SERP-Abfragen automatisch aus.
- Das Artifact zeigt in Abschnitt C den Plan, die Kosten und das Budget-Urteil.

## Kostenbewusste Reihenfolge

1. **Cache** (Semrush-Keyword-Cache, frühere Dossiers, Drive-Notizen)
2. **Google Search Console** (Queries, Query×Seite → Kannibalisierung, 90-Tage-Trend)
3. **Bestehende Website** (Live-Abruf, Inventar, interne Links)
4. **Vorhandene Semrush-Daten** (Keyword-Cache, SERP-Cache)
5. **Semrush Organic Results** für die echte SERP – nach Plan und Budget (siehe oben)
6. **Web-/Marktrecherche** ergänzend bzw. solange keine SERP vorliegt: Websuche + `python3 tools/page_profile.py <urls> --out clients/<c>/data/research/<OPP>/pages` (Hosts müssen im Netzwerk der Umgebung erlaubt sein) → Research competitors

Eine fehlende Semrush-SERP heißt nicht „keine Wettbewerbsanalyse“: Research competitors liefern die Anbieter- und Seitentyp-Landschaft, ohne Positionen (`quality: indicative`). Ist die echte SERP für die Entscheidung nötig, kommt sie in `status.pending` → Status `incomplete` → kein stiller Entwurf. Verbrauchte Units ohne Budget-Regel brauchen einen Freigabevermerk (`method.semrush_approved_by`).

## Befehle

```
python3 tools/research.py status   <client>            # Status aller Opportunities
python3 tools/research.py validate <client> [OPP ...]  # Schema prüfen (Exit 1 bei Fehlern)
python3 tools/research.py skeleton <client> <OPP>      # leeres Dossier anlegen
python3 tools/page_profile.py <url ...> --out <dir>    # Seitenprofile für C/D/E
```

Im Artifact: Opportunity-Detail zeigt Status, A–J und „Gate 1 – Strategie freigeben“; Workflow-Karten zeigen den Research-Status.

## Research Log / Audit Trail (`tools/research_log.py`)

Ziel: in 30–60 Sekunden nachvollziehen, warum der Agent zu einer Empfehlung kommt – und die Originalquellen selbst öffnen.

Modell: **Event** (Aktion) → **Sources** (Belege) → **Findings** (Erkenntnisse mit `source_ids`) → Opportunity/Dossier.

| Datei | Inhalt |
|---|---|
| `clients/<c>/state/research_log.json` | Events: Zeitpunkt + Genauigkeit (`exact` · `date` · `commit`), Opportunity, Aktionstyp, Zusammenfassung, Gefunden, Erkenntnis, `source_ids`, `finding_ids`, Units |
| `clients/<c>/state/evidence.json` | Quellen (`SRC-…`: Typ GSC/GA4/Semrush/Website/Competitor/Web Search/Agent, Titel, URL, Abrufzeitpunkt, Parameter) und Findings (`FND-…`) |
| `data/serp-cache/raw/SERP-<datum>-<keyword>-<DB>.json` | Unveränderliche Rohdaten jeder bezahlten SERP-Abfrage (wiederverwendbar ohne Units) |

Regeln:
- Keine erfundenen Zeitpunkte, Quellen, Kosten oder Links. Fehlende Angaben = `metadata unavailable`.
- Semrush-Quellen enthalten immer Report, Endpoint, Keyword, Datenbank, Ergebnisanzahl, Units (oder ausdrücklich unbekannt), Live/Cache und die Ergebnisse. Der Semrush-Konnektor liefert keine Report-URL → kein „In Semrush öffnen“-Link.
- `serp.py ingest … --client <c> --opp <OPP>` schreibt Cache, Rohdaten, Budget und Log-Eintrag in einem Schritt.
- Seitenprofile: `python3 tools/research_log.py add-profiles <c> <OPP> <ordner>` (Abrufzeit aus dem Profil).
- Agent Activity zeigt abgeschlossene Research-Aktionen aus **demselben** Log (gruppiert je Opportunity und Tag) – kein zweites Protokoll.
- `python3 tools/research_log.py validate <c>` prüft Referenzen, Zeitgenauigkeit und Semrush-Nachweise.

Im Artifact: Navigation „Research Log“ (Filter Opportunity, Source Type, Action Type, Datum, Suche; Semrush-Kosten und Kontostand oben), je Opportunity die Karte „Research Evidence“ (Quellen nach Typ) und an den Dossier-Abschnitten „N Quellen anzeigen“.

## Cannibalization Engine (`tools/cannibalization.py`) – fester Bestandteil jeder Opportunity

Bevor eine neue Seite empfohlen oder eine bestehende wesentlich neu ausgerichtet wird, prüft die Engine automatisch beim Build:
GSC Query × Page (16 Monate), Query-Cluster, Website-Inventar (URL/Title/H1, semantische Überschneidung) und vorhandene Semrush-Rankings je URL. Keine neuen API-Abfragen.

| Ergebnis | Bedeutung |
|---|---|
| **Risk** low · medium · high (· nicht bewertbar ohne GSC-Daten) | Anteil anderer eigener URLs an den Cluster-Impressionen, Positionsvergleich, Queries mit mehreren rankenden URLs, umgekehrte Kannibalisierung (Zielseite zieht fremden Cluster) |
| **Affected URLs** | URL, Impressionen, Anteil, Ø Position, Top-Queries, thematische Überschneidung |
| **Agent decision** | CREATE · OPTIMIZE · MERGE · **DO NOT CREATE** (→ OPTIMIZE der bestehenden Seite) · **+ COMPANION** · **+ RELEASE** |
| **Companion Optimization** | Bestehende Seite, die angepasst werden muss, damit beide Seiten sauber nebeneinander bestehen (Grund, nötige Änderungen, verknüpfte Opportunity). Vom Agenten im Dossier (`H_ia.companion`) geprüft hat Vorrang vor der Engine-Erkennung |

Regeln: siehe Modulkopf. Die Engine entscheidet selbst (z. B. CREATE → DO NOT CREATE/OPTIMIZE). Warnungen nur bei Grenzfällen (medium bei CREATE), hohem Risiko oder wenn die Empfehlung vom Opportunity-Typ abweicht. MONITOR/IGNORE zeigen ihr Risiko, ohne die Entscheidung umzustellen.

**Gate 1** fragt dann ausdrücklich: *Cancel* · *Recommendation übernehmen* · *Trotzdem freigeben*. Gespeichert werden `gate1.change_set` (Maßnahme, URL, Companions) und `gate1.cannibalization` (Risiko, Engine-Entscheidung, Wahl). Eine Freigabe mit Companion genehmigt beide Maßnahmen als **ein Change Set**: Der Runner erzeugt ein Drive-Dokument je Seite (`workflow.py doc-title … --companion <url>`), beide werden gemeinsam reviewt.

**Nach Veröffentlichung**: Jede neue oder stark veränderte Seite bekommt im Change Log `cannibalization_watch` + Checkpoints „Kannibalisierung T+14/T+30/T+60“ (erscheinen in Agent Activity als geplant). Prüfung mit `cannibalization.monitor(target, rows_vorher, rows_nachher, queries)`: Gewinnt die Zielseite? Wechseln URLs? Verliert eine bestehende Seite? Alternieren zwei URLs? Bei `status = cannibalization`: Finding → Opportunity → konkrete Maßnahme.

## Gate 1 beantwortet vier Fragen

1. **Warum?** Nachfrage, Rankings, Business Value, Leads · 2. **Was genau?** Maßnahme + URL + Ziel (Agent-Empfehlung, ggf. abweichend vom Typ) + Change Set · 3. **Was steht auf der Seite?** Page Purpose, Themen, Zielgruppen, bewusst nicht enthalten, Abgrenzung, grobe H1/H2-Struktur (aus Dossier F/G; `F_scope.page_purpose` + `F_scope.topics`) · 4. **Was passiert mit anderen Seiten?** Kannibalisierungsrisiko, betroffene URLs, Architecture, Companion Optimization.

Gate 1 genehmigt damit SEO-Maßnahme **und** fachlichen Scope. Der Gate-1-Kommentar ist eine verbindliche Scope-Änderung und hat in der Produktion Vorrang vor dem Dossier.

## Local Opportunities (Service × Region)

Gleiche Engine je Kombination aus `state/local.json`: Demand (GSC-Impressionen, Semrush nur aus dem Cache), aktuelles Ranking (URL + Position), Competition (nicht erhoben, keine Units), Business Fit, Cannibalization, Recommendation: **CREATE CITY PAGE** (nur bei eigenständiger lokaler Nachfrage ohne rankende Seite und mit echtem lokalem Bezug) · **USE MAIN SERVICE PAGE** (Hauptseite rankt bereits ≤ 10 oder Region ist Teil der Seite) · **OPTIMIZE EXISTING PAGE** · **MONITOR** (hoher Fit, kaum gemessene Nachfrage – 0 Volumen ≠ IGNORE) · **IGNORE**. Keine Doorway Pages.
