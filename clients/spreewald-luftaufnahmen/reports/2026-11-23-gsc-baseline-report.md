# GSC-Baseline (16 Monate) & Validierung der Priorisierung – Spreewald Luftaufnahmen

Stand: 23.11.2026 · Zeitraum: 21.07.2025–20.11.2026 (finale Daten) · Property: `https://www.spreewald-luftaufnahmen.de/` (URL-Präfix)
Rohdaten: `data/gsc-2026-11/gsc_*.csv` · Auswertung: `data/gsc-2026-11/analysis/` (erzeugt mit `tools/gsc_analyze.py`)
**Keine Websiteänderungen, keine neuen Seiten, kein Approval Gate 1.** Dachinspektion bleibt im Change Freeze (CL-001).

---

## 1. Kernaussagen

1. **Reale Performance ist klein und stabil:** 304 Klicks in 16 Monaten (~19/Monat), 93.000 Impressionen, Ø-Position ~16. Klicks schwanken 7–31/Monat ohne klaren Trend.
2. **Impressionen sind stark von der Preisseite und B2C-Themen getrieben:** Preis-Cluster 33.400 Impr. (43 % aller Query-Impressionen), Haus/Privat 11.200, Immobilien 6.800. B2B-Kernleistungen zusammen nur ~10.000.
3. **Datenqualität – Vorsicht bei Impressionen:** Viele Queries erscheinen März–Juni 2026 mit hunderten Impressionen auf Pos. 3–12, aber **0 Klicks**, und verschwinden danach vollständig (z. B. „wie teuer sind drohnenaufnahmen“ 660 → 0, „3d-modell drohne berlin“ 440 → 0, „luftaufnahmen mit drohne pauschalpreis“ 541 → 0). Muster passt zu automatisierten Abfragen (Rank-Tracker / KI-Such-Fan-out). **Hypothese, nicht beweisbar** – CTR-Bewertungen deshalb nur mit Klick-Bestätigung.
4. **Seit Juli 2026 ~50 % weniger Impressionen**, bei nahezu gleichen Klicks. Größte Verluste: Immobilien (≈1.000 → 80/Monat; „drohnenfotografie immobilien brandenburg“ Pos. 5 → 49), Baudokumentation (≈650 → 70), Dachvermessung (≈700 → 100–190), Gebäudeinspektion (≈300 → 36).
5. **Semrush unterschätzt die Sichtbarkeit:** GSC zeigt 530 Queries / 14 URLs mit Impressionen (Semrush: 23 Keywords). Baudokumentation rankt laut GSC auf Pos. 10–28 (Semrush: nicht in Top 100).
6. **Brand vs. Non-Brand:** In den Query-Daten taucht **keine** Marken-Suche auf (nur 1× „spreewald“). Die Startseite hat aber 105 Klicks bei 4.557 Impr. → Brand-Klicks liegen fast vollständig in den von Google **anonymisierten** Queries (nur 48 der 304 Klicks sind einer Query zugeordnet). Brand-Nachfrage ist damit **nicht messbar**, aber vorhanden.
7. **Desktop 70 % der Impressionen**, Mobile 29 % → typisches B2B-/Recherche-Muster. **Deutschland 93 %**; Rest irrelevant.

## 2. Seiten (16 Monate)

| Seite | Klicks | Impr. | CTR | Ø-Pos. | Trend seit Juli 2026 |
|---|---|---|---|---|---|
| /drohnenaufnahmen-preis-kosten/ | 58 | 44.075 | 0,13 % | 10,0 | Impr. −60 %, Pos. stabil 8–11 |
| / (Startseite) | 105 | 4.557 | 2,3 % | 29,9 | schwankend |
| /fassadenaufmass-drohnen-vermessung-fassade/ | 32 | 3.352 | 0,95 % | 18,6 | stabil, Pos. 13–16 |
| /haus-grundstueck-luftbild/ | 27 | 15.713 | 0,17 % | 15,4 | stabil, Pos. verbessert (9) |
| /drohne-dach-gebaeude-inspektion/ | 24 | 3.598 | 0,67 % | 27,7 | stark fallend |
| /drohne-luftaufnahmen-hochzeit/ | 21 | 4.562 | 0,46 % | 21,7 | stabil |
| /drohne-dach-vermessung/ | 18 | 5.037 | 0,36 % | 22,2 | fallend |
| /immobilien-fotografie-drohne/ | 11 | 7.508 | 0,15 % | 28,4 | **eingebrochen** |
| /drohnen-baudokumentation/ | 5 | 5.218 | 0,10 % | 26,0 | **eingebrochen** (Impr.), Pos. besser (10–14) |
| /drohnen-aufnahmen-firma/ | 2 | 2.461 | 0,08 % | 40,4 | Nov. Pos. 12 (+) |
| /fassadeninspektion-…-brandenburg/ | 2 | 83 | 2,4 % | 16,2 | neu seit 30.10. |
| /dachinspektion-mit-drohne/ | 0 | 580 | 0 % | 35,4 | seit Juni; Freeze |

## 3. Cluster (Query-Ebene)

| Cluster | Queries | Klicks | Impr. | Ø-Pos. | Hauptseiten |
|---|---|---|---|---|---|
| Preis/Kosten | 76 | 32 | 33.441 | 9,0 | Preise |
| Haus/Privat | 36 | 3 | 11.228 | 15,0 | Haus & Grundstück |
| Immobilien | 48 | 3 | 6.825 | 20,8 | Immobilien |
| Generisch Drohne | 162 | 2 | 6.656 | 36,3 | Startseite, Firma |
| **Vermessung allgemein** (inkl. 3D-Modell) | 35 | 1 | 3.530 | 16,1 | Dachvermessung, **Baudoku**, Fassadenaufmaß |
| **Baudokumentation** | 27 | 0 | 3.291 | 29,9 | Baudoku |
| Video | 11 | 1 | 3.048 | 11,2 | Preise |
| Hochzeit/Event | 28 | 1 | 2.988 | 21,9 | Hochzeit |
| **Dachvermessung** | 23 | 2 | 1.303 | 42,1 | Dachvermessung |
| **Dachinspektion** | 23 | 2 | 1.195 | 44,4 | **Gebäudeinspektion (813)** > Dachinspektion (382) |
| Firma/Imagefilm | 15 | 0 | 1.052 | 31,4 | Firma |
| **Fassadenvermessung** | 7 | 1 | 987 | 16,6 | Fassadenaufmaß |
| Inspektion allgemein | 9 | 0 | 593 | 36,2 | Gebäudeinspektion |
| **Fassadeninspektion** | 4 | 0 | 494 | 39,0 | **Fassadenaufmaß (448)** |
| Bestandsaufnahme/Dokumentation | 3 | 0 | 409 | 24,2 | Fassadenaufmaß, Baudoku |

## 4. Quick Wins & Positionen 4–20 (B2B-relevant)

| Query | Impr. | Pos. | Seite | Einordnung |
|---|---|---|---|---|
| drohnenvermessung berlin | 1.062 | 10,1 | Dachvermessung (5 URLs konkurrieren) | **Vermessungs-Hub-Signal** |
| anbieter vermessung drohne berlin | 472 | 10,6 | Dachvermessung | dto. |
| drohnenvermessung brandenburg | 110 | 4,2 | Dachvermessung | dto. |
| vermessung drohne brandenburg | 84 | 2,5 | Dachvermessung | dto. |
| 3d-modell drohne berlin (+4 Varianten) | ~1.100 | 12–16 | **Baudoku**/Dachvermessung | 3D-Nachfrage landet auf falscher Seite |
| baudokumentation drohne berlin | 84 | **2,3** | Baudoku | lokales Top-Ranking |
| baubegleitung mit drohne | 233 | 12,6 | Baudoku | Baudoku-Vokabular |
| fassadenvermessung drohne / berlin | 90 / 99 | 5,7 / 10,1 | Fassadenaufmaß | gut positioniert |
| fassadenaufmaß | 328 | 18,5 | Fassadenaufmaß | Top-10-Chance |
| fassaden dokumentation drohne | 249 | 16,7 | Fassadenaufmaß | Bestandsaufnahme-Signal |
| dachvermessung mit drohne berlin | 103 | 10,3 | Dachvermessung | |
| dachinspektion per drohne berlin | 110 | 17,3 | Dachinspektion | Freeze |

Seiten mit niedriger Priorität und guten Positionen (Immobilien, Haus, Preis) siehe `analysis/quickwins_pos4-20.csv`.

### Hohe Impressionen, schwache CTR
- **Preisseite:** 173 Queries, 38.600 Impr., Pos. ~7–10, **33 Klicks statt ~1.000 erwartet** (Branchen-CTR-Kurve). 26 Queries mit ≥300 Impr. in den Top 10 haben 0 Klicks (18.600 Impr.).
- Einschränkung: Ein Teil dieser Impressionen ist vermutlich nicht menschlich (Kernaussage 3). Selbst bei 50 % Abschlag bleibt eine deutliche Lücke → Snippet (Title/Description/Preisangaben/Review-Sterne) ist ein günstiger Test.

## 5. Kannibalisierung (Auswahl, 37 Fälle insgesamt)

| Query-Gruppe | Konkurrierende Seiten | Bewertung |
|---|---|---|
| **Dachinspektion** (mit/per/drohne …) | Gebäudeinspektion (Pos. 37–80) vs. Dachinspektion (Pos. 26–46) | Echt. Hub zieht Dach-Queries; nach Freeze Rollen klären (Hub verlinkt mit Dach-Anker, Hub-Fokus auf Gebäude/Fassade allgemein). |
| **Fassadeninspektion** | Fassadenaufmaß (448 Impr.) vs. neue Fassadeninspektion | Erwartbar (Seite neu). Beobachten, ob die neue Seite übernimmt. |
| **Drohnenvermessung / Anbieter Vermessung Berlin** | Dachvermessung, Fassadenaufmaß, Gebäudeinspektion, Baudoku | Kein Hub vorhanden → bestätigt OPP-04. |
| **3D-Modell Berlin** | Baudoku vs. Dachvermessung | Thema hat keine Heimat. |
| Haus/Preis-Fragen | Haus vs. Preise vs. Immobilien | Niedrige Prio, ignorieren. |
| „drohnenaufnahmen brandenburg/berlin“ | Startseite, Firma, Hochzeit, Immobilien | Generisch; Startseite sollte Ziel sein (niedrige Prio). |

## 6. Lokale Suchanfragen

- **Berlin** dominiert (41 Queries), **Brandenburg** 12. Leistungs×Berlin-Kombinationen mit Impressionen: Vermessung, 3D-Modell, Dachinspektion, Dachvermessung, Fassadenvermessung, Baudoku, Immobilien.
- **Potsdam (7 Impr.), Cottbus (11), Neuruppin (24)**: nur generische „drohnenaufnahmen <ort>“, Pos. 43–57. Die Website adressiert diese Orte nicht – **kein Gegenbeweis, aber auch keine Bestätigung**.
- **Überregional** tauchen Leistungs-Queries auf: „dachinspektion sachsen“ (58, Pos. 17,7), „baustellendokumentation drohne thüringen“ (87), Dachinspektion Bonn/Köln/Lemgo, Inspektion München → Google ordnet die Inspektions-/Baudoku-Seiten auch ohne Ortsbezug zu; B2B-Nachfrage ist leistungs- statt ortsgetrieben.

## 7. Signale für neue Services (NBO)

| Signal | GSC | Bewertung |
|---|---|---|
| **3D-Modell / 3D-Dachvermessung** | ~1.300 Impr., Pos. 12–16 (teils Tracker-verdächtig), 0 Klicks | **Bestätigt NBO-03** als Thema mit Sichtbarkeit; Leistungsumfang mit Airteam (3D-Modell ist Teil Dach/Fassade) klären. |
| Fassaden-/Gebäudedokumentation | 249–409 Impr. | stützt Bestandsaufnahme (OPP-05), schwach |
| Solaranlage („preis für drohnenbilder von solaranlage“) | 16 | sehr schwach |
| Wärmebild | 1 | kein GSC-Signal (Website deckt Thema nicht ab) – Semrush-Signal (NBO-01) bleibt maßgeblich |
| Kurse/Führerschein/Kaufen | 1–3 | D – uninteressant |

## 8. Validierung der bisherigen Opportunities

| ID | Bisher | GSC-Befund | Neu |
|---|---|---|---|
| OPP-01 Dachinspektion | OPTIMIZE (Fix) | Fix greift erst nach Re-Crawl (letzter Crawl 26.10.). **Neu: Kannibalisierung durch Gebäudeinspektion-Hub.** | **OPTIMIZE bestätigt – Freeze bis Bewertung**; danach Hub-Rolle klären |
| OPP-02 Baudokumentation | OPTIMIZE | **Stärker bestätigt:** baudokumentation drohne 1.144 Impr. Pos. 28; baustellendokumentation drohne 704 Pos. 25; baubegleitung 233 Pos. 13; Berlin Pos. 2. Aber Impressionen −90 % seit Juni → Ursache prüfen (Seite am 16.07.2026 geändert). | **OPTIMIZE – höchste Priorität**, zuerst Ursachenanalyse |
| OPP-03 Gebäudeinspektion-Hub „Drohneninspektion“ | OPTIMIZE | „drohneninspektion“ in GSC praktisch nicht sichtbar (2 Impr.); Hub rankt für „gebäudeinspektion drohne“ (495, Pos. 33) und zieht Dach-Queries. | **OPTIMIZE angepasst:** Primärfokus Gebäudeinspektion + Hub-Logik, Dach-Queries an Dach-Seite abgeben |
| OPP-04 Vermessungs-Hub | CREATE vs. OPTIMIZE offen | drohnenvermessung berlin 1.062 Impr. Pos. 10 über 5 URLs; 3D-Queries ohne Heimat. | **CREATE wahrscheinlicher** – finale Entscheidung nach SERP-Check |
| OPP-05 Bestandsaufnahme/Beweissicherung | CREATE-Kandidat | Schwache Signale (Fassaden-/Gebäudedokumentation). | **Kandidat, niedrige Konfidenz** – SERP-Check nötig |
| OPP-06 Fassadeninspektion | MONITOR | Kannibalisierung mit Fassadenaufmaß (erwartet). | **MONITOR bestätigt** |
| OPP-07 Preise/Immobilien | IGNORE | Preisseite: massive CTR-Lücke; Immobilien: Rankingverlust. | **Preise → OPTIMIZE (nur Snippet-Test, geringer Aufwand)**; Immobilien → **MONITOR** |
| OPP-08 Privat/Hochzeit/Events | IGNORE | Viel Impressionen, kaum Klicks, Prio 0–2. | **IGNORE bestätigt** |
| NBO-03 3D-Modell | B/C | ~1.300 Impr. | **aufgewertet** |
| Local-Pilot Potsdam/Cottbus | Pilot nach SERP-Check | Keine GSC-Nachfrage (Orte nicht adressiert); Berlin bestätigt; überregionale Leistungs-Nachfrage sichtbar. | **Unverändert Hypothese**; Berlin über bestehende Seiten zuerst |
| **NEU** OPP-09 Fassadenvermessung/-aufmaß | – | Pos. 5–18, stabilste B2B-Seite, 32 Klicks | **OPTIMIZE (leicht)** – bereits beste B2B-Seite |
| **NEU** F-012 Impressionsrückgang Juli 2026 | – | seitenübergreifend, Klicks stabil | **Analyse** (Core Update? Tracker-Wegfall? Seitenänderungen 16.07.) |

## 9. Neue Findings

- **F-012** Seitenübergreifender Impressionsrückgang ab Juli 2026 (−50 %), Klicks stabil – Ursache offen.
- **F-013** Dach-Queries landen überwiegend auf dem Gebäudeinspektion-Hub (Kannibalisierung).
- **F-014** Fassadeninspektion-Queries landen auf Fassadenaufmaß (neue Seite noch im Aufbau).
- **F-015** 3D-Modell-Queries ohne passende Zielseite (Baudoku/Dachvermessung).
- **F-016** Preisseite: CTR 0,13 % bei Pos. ~10 (38.600 Impr.).
- **F-017** URL `/kontakt/?rwg_token=…` (Google-Reservierungslink aus GBP) erscheint in GSC – unkritisch, beobachten.
- **F-018** Verdacht auf nicht-menschliche Impressionen (Frühjahr 2026) – Auswertungen mit Klick-Bestätigung gewichten.

## 10. Empfohlene nächste Schritte (zur Freigabe, ohne Änderungen)

1. **Ursachenanalyse F-012/OPP-02:** WordPress-Revision der Baudoku-Seite vom 16.07.2026 vs. vorher, Google-Updates im Zeitraum, Query-Verluste je Seite.
2. **SERP-/Wettbewerbs-Check (Semrush-Connector, cache-first)** für: drohnenvermessung (Hub-Entscheidung), baudokumentation drohne, baustellendokumentation drohne, gebäudeinspektion drohne, 3d-modell drohne, fassadenaufmaß, bestandsaufnahme gebäude. Geschätzt ~700–1.000 Units → **erst nach Unit-Reset bzw. Freigabe**.
3. Danach: gezielte Discovery für die bestätigten Cluster → Approval-Gate-1-Paket.
