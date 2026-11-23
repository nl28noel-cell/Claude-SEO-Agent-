# SEO Baseline Report & erste Opportunities – Spreewald Luftaufnahmen

Stand: 23.11.2026 · Status: **Analyse – keine Änderungen vorgenommen**
Datenbasis: Live-Crawl (17 URLs), WordPress REST API, Semrush DE (Domain, Rankings, 77 Keyword-Messwerte), Drive-Keywordrecherche 2024, Business-Profil v1.0.
**Nicht enthalten:** Google Search Console (kein Zugriff), Keyword Planner, SERP-Tiefenanalyse (siehe §6 Blocker).

---

## 1. Executive Summary

1. **Sichtbarkeit ist klein, aber fokussiert:** 23 rankende Keywords, ca. 29 organische Besuche/Monat (Semrush-Schätzung). Die Seite rankt vor allem mit **Preis- und Immobilienseiten** (Pos. 2–5) – also mit den Leistungen niedriger strategischer Priorität.
2. **Die B2B-Kernleistungen ranken praktisch nicht:** Baudokumentation (Prio 10), Dach-/Gebäudeinspektion (Prio 9) haben kaum Top-100-Rankings, obwohl messbare Nachfrage mit **sehr niedriger Keyword Difficulty (KD 0–18)** existiert.
3. **Ein technischer Fehler blockiert die Dachinspektionsseite** (falscher Canonical → nicht in Sitemap). Das ist der wichtigste Quick Win.
4. **Größte messbare B2B-Nachfrage im Umfeld:** *drohnenvermessung* (390), *drohneninspektion* (260, steigender Trend), *vermessung drohne* (210), *baudokumentation drohne* (140), *baustellendokumentation drohne* (110), *dachinspektion drohne* (110).
5. **Neue Geschäftsfelder mit Signal:** Gebäude-Thermografie per Drohne (C), Beweissicherung am Bau (A), Bestandsaufnahme Gebäude (A, steigend), 3D-Gebäudescan (B/C), „Drohnenpilot mieten“ (A).
6. **Strategische Empfehlung:** Zuerst **OPTIMIZE** der bestehenden Prio-9/10-Seiten (Technik, Keyword-Fokus, interne Verlinkung), dann **ein Vermessungs-Hub** und **Bestandsaufnahme/Beweissicherung** als einzige CREATE-Kandidaten, danach ein **kontrollierter Local-SEO-Pilot** (2 Städte) statt Stadtseiten in der Breite.

---

## 2. Baseline: Website

### 2.1 Struktur (17 öffentliche URLs)

| Bereich | URL | Index | Wörter | Interne Content-Links rein | Prio |
|---|---|---|---|---|---|
| Startseite | / | ✅ | 544 | – (Menü) | – |
| Baudokumentation | /drohnen-baudokumentation/ | ✅ | 925 | 1 | 10 |
| Gebäudeinspektion (Hub) | /drohne-dach-gebaeude-inspektion/ | ✅ | 1.086 | 1 | 9 |
| Dachinspektion | /dachinspektion-mit-drohne/ | ⚠️ Canonical-Fehler | 936 | 1 | 9 |
| Fassadeninspektion | /fassadeninspektion-mit-drohne-berlin-brandenburg/ | ✅ (neu, 02.11.26) | 1.302 | **0** | 9 |
| Dachvermessung | /drohne-dach-vermessung/ | ✅ | 1.132 | 5 | 8 |
| Fassadenaufmaß | /fassadenaufmass-drohnen-vermessung-fassade/ | ✅ | 827 | 2 | 8 |
| Immobilien | /immobilien-fotografie-drohne/ | ✅ | 1.339 | 1 | 6 |
| Firma | /drohnen-aufnahmen-firma/ | ✅ | 1.233 | 1 | 5 |
| Haus & Grundstück | /haus-grundstueck-luftbild/ | ✅ | 1.490 | 1 | 2 |
| Hochzeit | /drohne-luftaufnahmen-hochzeit/ | ✅ (nicht im Menü) | 988 | 1 | 0–1 |
| Preise | /drohnenaufnahmen-preis-kosten/ | ✅ | 904 | **0** | – |
| Kontakt | /kontakt/ | ✅ | 65 | 14 | – |
| Ads-LP Inspektion | /drohne-dach-gebaeude-inspektion-ads/ | noindex ✅ | – | – | – |
| Ads-LP Dachvermessung | /dach-vermessung-drohne-ads/ | noindex ✅ | – | – | – |
| Impressum, Datenschutz | | noindex ✅ | | | |

Fehlend gemessen am Business-Profil: **Bestandsaufnahme (Prio 8)**, **Industrie/Projektdokumentation (Prio 8)**, **Vermessungs-Übersicht** (Prio 8, nur Dach/Fassade einzeln).

### 2.2 Technische & On-Page-Befunde

| ID | Befund | Wirkung | Empfehlung |
|---|---|---|---|
| F-001 / **F-005** | **Ursache gefunden:** Dachinspektion hat Canonical `…/dachinspektion-mit-drohne` (ohne Slash). Diese URL leitet per 301 auf die Slash-Version um → Canonical zeigt auf Weiterleitung, Yoast schließt Seiten mit abweichendem Canonical aus der Sitemap aus. | Google bekommt widersprüchliche Signale; Seite rankt nur Pos. 45 für „dachinspektion mit drohne“. | Canonical in Yoast leeren (Self-Canonical). **Quick Win, sehr geringer Aufwand.** |
| F-006 | Interne Content-Verlinkung sehr dünn: Fassadeninspektion und Preise erhalten **0** kontextuelle Links; Hubs verlinken kaum auf Unterseiten. Navigation trägt fast alles. | Schwache thematische Signale für Prio-9/10-Cluster. | Cluster-Verlinkung Inspektion ↔ Dach/Fassade ↔ Vermessung ↔ Baudoku. |
| F-007 | Schema: nur Yoast-Standard (Organization/WebPage). **Kein LocalBusiness/ProfessionalService, kein Service-Schema.** FAQPage nur auf Preisseite; Fassadeninspektion hat FAQ ohne Schema. | Verschenkte lokale/SERP-Signale. | LocalBusiness + Service + FAQPage ergänzen. |
| F-008 | Ca. 45–65 % der Content-Bilder ohne Alt-Text (z. B. Fassadeninspektion 13 von 20). | Bild-SEO, Barrierefreiheit. | Alt-Texte nachpflegen. |
| F-009 | Titles/Descriptions durchgängig vorhanden und in Länge ok; viele H2 sind Template-Blöcke („Unkompliziert zur perfekten Lösung!“, „Kundenstimmen“). | Wenig themenspezifische Überschriften-Signale. | Bei OPTIMIZE themenspezifische H2 einsetzen. |
| F-010 | Leichte **Kannibalisierung „drohnenvermessung berlin“**: Dachvermessung (Pos. 7) und Gebäudeinspektion (Pos. 59); „anbieter vermessung drohne berlin“ ebenso (8 / 87). | Kein Hub für generische Vermessungs-Suchen. | Vermessungs-Hub prüfen (s. §4). |
| F-011 | Dachvermessung behauptet „Bis zu 99,4 % Genauigkeit“ (vermutlich Partnerangabe Airteam). | Content-Regel: Zahl muss belegt sein. | Quelle bestätigen oder entschärfen. |
| F-003 | Öffnungszeiten widersprüchlich (Kontakt vs. Footer). | NAP-Konsistenz. | Mit GBP abgleichen. |

---

## 3. Baseline: Rankings (Semrush DE, 23.11.2026)

Domain: Semrush Rank 2.087.761 · 23 Keywords · ~29 Besuche/Monat · Traffic-Wert ~8 €.

### 3.1 Rankings je URL

| URL | Keyword | Pos. | Vol. | KD |
|---|---|---|---|---|
| Preise | drohnenaufnahmen angebot | 2 | 70 | 10 |
| | drohnenaufnahmen kosten | 3 | 110 | 2 |
| | drohnenaufnahmen preise | 5 | 170 | 5 |
| | kosten drohnenaufnahmen | 5 | 70 | 2 |
| | drohnenfotografie kosten | 24 | 90 | 3 |
| Immobilien | drohnenfotografie immobilien brandenburg | 2 | 70 | 1 |
| | drohnenfotos immobilien | 3 | 70 | 1 |
| | drohnendienstleistungen immobilien berlin | 4 | 140 | 5 |
| Dachvermessung | drohnenvermessung berlin | 7 | 110 | 5 |
| | anbieter vermessung drohne berlin | 8 | 110 | 4 |
| | 3d-modell immobilien drohne berlin | 28 | 70 | 0 |
| Haus & Grundstück | luftaufnahmen von ihrem haus | 8 | 90 | 6 |
| Baudokumentation | baustellendokumentation drohne thüringen | 14 | 90 | 1 |
| Startseite | luftaufnahmen bau | 39 | 90 | 2 |
| Gebäudeinspektion | drohnenservice berlin | 44 | 110 | 8 |
| | drohnendienstleistungen berlin | 63 | 140 | 6 |
| | drohnendienstleister berlin | 69 | 170 | 28 |
| Dachinspektion | dachinspektion mit drohne | 45 | 110 | 3 |
| Fassadeninspektion | – (zu neu) | | | |

### 3.2 Striking Distance (Pos. 4–20)

| Keyword | Pos. | URL | Hebel |
|---|---|---|---|
| drohnendienstleistungen immobilien berlin | 4 | Immobilien | Title/H1-Feinschliff (Prio 6) |
| drohnenaufnahmen preise / kosten drohnenaufnahmen | 5 | Preise | CTR/Snippet; FAQ ist da |
| drohnenvermessung berlin | 7 | Dachvermessung | **Prio 8** – Hub-Entscheidung, s. OPP-04 |
| anbieter vermessung drohne berlin | 8 | Dachvermessung | wie oben |
| luftaufnahmen von ihrem haus | 8 | Haus | Prio 2 – nicht aktiv ausbauen |
| baustellendokumentation drohne thüringen | 14 | Baudoku | Signal: Google traut der Seite überregionale Baudoku zu |

**Hinweis:** „Hohe Impressionen bei schwacher CTR“ und echte Query-Daten lassen sich erst mit Search Console bewerten (§6).

---

## 4. Opportunities (Phase 1 – datenbasiert, noch ohne SERP-Tiefenanalyse)

Faktoren je Opportunity offen gelegt; noch **keine Gewichtungsformel**. Nachfrage = Semrush DE Monatsvolumen (Summe Kern-Keywords). KD = Semrush Keyword Difficulty (0–100). Business Fit = Prio laut Profil.

### OPP-01 · Dachinspektion – technischer Fix + Keyword-Fokus → **OPTIMIZE**
- Nachfrage: dachinspektion drohne 110 · dachinspektion 320 (gemischter Intent, u. a. Dachdecker) · dachcheck 140 · dach inspektion 40
- KD 0–17 · CPC bis 2,87 € · Business Fit 9
- Ist: Pos. 45; Canonical-Fehler; nicht in Sitemap
- Begründung: Niedrigster Aufwand, höchster Hebel; Seite inhaltlich bereits solide (936 Wörter).
- Erwartung: Nach Fix realistisch Top 10–20 für „dachinspektion drohne“ binnen 1–3 Monaten (geringe KD). *Annahme, kein Versprechen.*

### OPP-02 · Baudokumentation (Prio 10) → **OPTIMIZE**
- Nachfrage: baudokumentation drohne 140 · baustellendokumentation drohne 110 · drohne baustelle 70 · baufortschrittsdokumentation 20
- KD 0–15 · CPC 1,59–2,30 € · Business Fit 10 · Wiederkehrender Auftragscharakter (Retainer-Modell belegt)
- Ist: keine Top-100-Platzierung für die Kern-Keywords (nur „…thüringen“ Pos. 14)
- Begründung: Höchste Prio + messbare Nachfrage + sehr niedrige Difficulty = beste Chance im ganzen Profil. Seite (925 Wörter) muss stärker auf „Baustellendokumentation/Baufortschritt mit Drohne“, Intervalle, Bauträger/Bauunternehmen, Ergebnisformate ausgerichtet werden.
- Abgrenzung: „baudokumentation“ (720) / „baustellendokumentation“ (880, CPC 8,37 €) sind überwiegend Software-/Ratgeber-Intent → als Supporting-Content prüfen, nicht als Primary Keyword.

### OPP-03 · Gebäudeinspektion-Hub auf „Drohneninspektion“ → **OPTIMIZE**
- Nachfrage: drohneninspektion 260 (**Trend: letzte 4 Monate auf Jahreshoch**) · inspektion drohne 50 · gebäudeinspektion drohne 50 · gebäudeinspektion 40
- KD 0–18 · CPC 1,24–2,40 € · Business Fit 9
- Ist: Hub rankt nur für generische „drohnenservice/dienstleister berlin“ (Pos. 44–69)
- Begründung: Wachsendes Suchmuster; Hub sollte Primary „Drohneninspektion“ besetzen und Dach/Fassade/Vermessung/Bestandsaufnahme sauber verlinken.

### OPP-04 · Vermessungs-Hub „Drohnenvermessung“ → **Entscheidung: CREATE vs. OPTIMIZE**
- Nachfrage: drohnenvermessung 390 · vermessung drohne 210 · photogrammetrie drohne 90 · aufmaß drohne 20 · dachaufmaß 30 · fassadenaufmaß 20
- KD 0–9 · CPC bis 4,18 € · Business Fit 8 (Partnerleistung Airteam)
- Ist: Dachvermessung rankt Pos. 7–8 für „drohnenvermessung berlin“ – Google nutzt eine *Dach*-Seite für eine *generische* Vermessungs-Suche (+ Kannibalisierung durch Gebäudeinspektion).
- Optionen: (a) **CREATE** Hub „Drohnenvermessung Berlin & Brandenburg“ als Parent von Dach/Fassade; (b) **OPTIMIZE** Dachvermessung breiter → verwässert den Dach-Fokus.
- Empfehlung: (a), weil kein bestehendes Dokument das generische Thema sinnvoll bedient. **Offene Frage:** Welche Vermessungsleistungen deckt Airteam real ab (nur Dach/Fassade oder auch Gelände/Volumen)?

### OPP-05 · Bestandsaufnahme Gebäude / Beweissicherung am Bau → **CREATE (Kandidat)**
- Nachfrage: bestandsaufnahme gebäude 50 (Trend steigend) · bestandsdokumentation 50 · beweissicherung bau 90 (CPC 1,88 €, Comp 0,66) · gebäudebestandsaufnahme 20 · bestandsaufnahme immobilie 20
- Business Fit 8 (Bestandsaufnahme) · Zielkunden 1–3 (Verwaltungen, Bauträger, Bauunternehmen)
- Keine bestehende URL bedient das Thema (nur ein geplanter interner Link im Inspektions-Text).
- Begründung: Verbindet Inspektion + Baudoku zu einem B2B-Produkt mit klarem Anlass (vor Baubeginn, vor Sanierung, Bestandsportfolio). **Beweissicherung** siehe auch NBO-02.

### OPP-06 · Fassadeninspektion → **MONITOR**
- Nachfrage klein (fassadeninspektion 40, Trend steigend; fassadenprüfung 30; fassadenschäden 30), Seite seit 02.11.2026 live, noch nicht in Semrush.
- Maßnahme: nur interne Verlinkung (0 eingehende Content-Links) + FAQ-Schema; Ranking nach 30/60 Tagen bewerten.

### OPP-07 · Preise & Immobilien → **IGNORE (bewusst)**
- Rankt bereits Pos. 2–5; Prio 6 bzw. Conversion-Seite. Keine Ressourcen, außer CTR-Check mit GSC.

### OPP-08 · Private/Hochzeit/Events → **IGNORE**
- Profil-Prio 0–2. Bestehende Seiten bleiben, keine Investition.

---

## 5. NEW BUSINESS OPPORTUNITIES (Suchsignale – Entscheidung bei Noel)

| ID | Feld | Suchmuster & Nachfrage (DE/Monat) | Klasse | Einschätzung |
|---|---|---|---|---|
| **NBO-01** | **Gebäude-Thermografie per Drohne** | thermografie drohne 140 (KD 3, Comp 1,0) · thermografie gebäude 140 · pv thermografie 70 · wärmebildkamera haus 170 (eher Kauf-/DIY-Intent) | **C** (Wärmebildsensor + Fachkunde nötig) | Starkes Fit zu Hausverwaltung/Wohnungswirtschaft und Dach/Fassade; saisonal (Heizperiode); sehr niedrige KD. Höchstes NBO-Potenzial. |
| **NBO-02** | **Beweissicherung vor/während Bauvorhaben** | beweissicherung bau 90 (CPC 1,88 €) · beweissicherungsverfahren 880 (überwiegend juristisch) | **A** (Foto-/Videodokumentation) | Klassischer B2B-Anlass für Bauunternehmen/Bauträger (Nachbarbebauung vor Baubeginn); passt zu Baudoku-Retainern. Content muss juristisch sauber abgrenzen (kein Gutachten). |
| **NBO-03** | **3D-Gebäudescan / 3D-Modell** | 3d scan gebäude 70 (CPC 2,93 €, Comp 1,0) · photogrammetrie drohne 90 · 3d modell gebäude 20 | **B** (Airteam) / **C** | Rankt bereits Pos. 28 („3d-modell immobilien drohne berlin“). Hoher kommerzieller Wettbewerb = Zahlungsbereitschaft. |
| **NBO-04** | **Drohnenpilot mieten / buchen (B2B-Dienstleistung)** | drohne mieten 720 (meist Gerätemiete) · drohnenpilot mieten 70 · drohnenpilot 720 (gemischt, viel Berufs-Info) | **A** | Suchmuster „Pilot + Drohne als Dienstleistung“ für Film/Agenturen/Projekte. Nur bedingt B2B-hochpreisig – prüfen. |
| **NBO-05** | **Industrie-/Anlageninspektion** | industrie inspektion drohne 50 (Trend stark steigend) · industriedrohne 30 · brückeninspektion drohne 20 | **A/C** je Objekt | Profil-Prio 8 ohne Seite. Kleines, aber wachsendes Signal; Auftragswerte potenziell hoch. |
| NBO-06 | Dachflächen-Ermittlung (Ratgeber → Vermessung) | dachfläche berechnen **1.900** (Info-Intent, KD 10) | **A/B** | Kein Lead-Keyword, aber großer Zubringer für PV-/Sanierungsplaner zu Dachvermessung. Supporting-Content-Kandidat. |
| NBO-07 | Orthofotos / Geländevermessung / Volumen | orthofoto 590 (Geoportal-Intent) · orthofoto drohne 20 · geländevermessung 20 · Volumen/Halden: nicht messbar | **C** | Messbare Nachfrage gering; B2B-Wert (Bau/Erdbau) hoch, aber Wettbewerb durch Vermessungsbüros. Beobachten. |
| NBO-08 | PV-Inspektion | pv anlage inspektion 20 · photovoltaik inspektion drohne 10 · solaranlage prüfen 20 | C | Sehr wenig messbare Nachfrage; nur in Kombination mit NBO-01 sinnvoll. |
| NBO-09 | Landwirtschaft | landwirtschaft drohne 110 | D | Spritz-/Agrardrohnen – strategisch uninteressant. |

Nicht messbar (Volumen 0/keine Daten): Schadensdokumentation Versicherung, Denkmal-Dokumentation, Hausverwaltung/Wohnungswirtschaft + Drohne, Windkraft-, Schornsteininspektion, Volumen/Halden. → **Kein IGNORE**, sondern über SERPs/GSC/Vertrieb validieren.

---

## 6. Local Opportunity Matrix – Version 0 (Struktur & Priorisierung)

Lokale B2B-Kombinationen liefern in Semrush typischerweise **kein messbares Volumen**; gemäß Profil ist das kein IGNORE-Grund. Stadtgrößen = gerundete Einwohnerzahlen (Allgemeinwissen, vor Nutzung zu verifizieren). Nachfrage/Wettbewerb je Zelle werden erst mit GSC + SERP-Check befüllt.

| Stadt/Region | Einw. ca. | Entf. Schönefeld | Zielkundendichte (Bau/Verwaltung/Gewerbe) | Baudoku (10) | Gebäude-/Dachinspektion (9) | Vermessung (8) | Empfehlung |
|---|---|---|---|---|---|---|---|
| **Berlin** | 3,8 Mio. | 0–40 km | sehr hoch | bestehende Seiten (BB-Fokus) | bestehende Seiten | Pos. 7 vorhanden | **OPTIMIZE** bestehende Seiten auf Berlin, keine Stadtseite nötig |
| **Potsdam** | 185 Tsd. | ~45 km | hoch (Bauträger, Bestand, Denkmal) | Kandidat | Kandidat | – | **Pilot-Stadtseite** (nach SERP-Check) |
| **Cottbus** | 98 Tsd. | ~110 km | mittel–hoch (Strukturwandel, Großprojekte Lausitz) | Kandidat | Kandidat | – | **Pilot-Stadtseite** (nach SERP-Check) |
| Brandenburg a. d. H. | 73 Tsd. | ~80 km | mittel | später | später | – | Warteliste |
| Frankfurt (Oder) / Eisenhüttenstadt | 57 / 24 Tsd. | ~90–110 km | mittel; **belegtes Projekt Eisenhüttenstadt** (09/2026) | – | Kandidat | – | Warteliste (Referenz vorhanden) |
| Königs Wusterhausen / Wildau / BER-Umfeld | 38 Tsd. + Gewerbe | ~15–25 km | hoch (Gewerbe, Logistik, Flughafen) | Kandidat | Kandidat | – | Prüfen als **Region „Dahme-Spreewald/BER“** |
| Oranienburg, Falkensee, Bernau, Eberswalde | 40–48 Tsd. | 40–70 km | mittel (Speckgürtel-Wohnungsbau) | später | später | – | Warteliste |
| Lübben/Lübbenau (Spreewald) | 14 / 16 Tsd. | ~70 km | niedrig | – | – | – | Markenbezug, keine eigene B2B-Seite |
| Dresden / Leipzig | >500 Tsd. | 160–190 km | hoch | nur bei Projektlage | – | – | außerhalb Kernmarkt, beobachten |

**Empfohlenes Vorgehen (keine Doorway-Fabrik):**
1. Berlin über bestehende Seiten stärken (OPTIMIZE).
2. **Pilot: maximal 2 Städte × 1–2 Leistungen** (z. B. Potsdam & Cottbus × Baudokumentation/Gebäudeinspektion), jeweils mit echtem lokalem Bezug.
3. Nach 60–90 Tagen GSC-Impressionen/Anfragen auswerten → erst dann weitere Städte.

---

## 7. Blocker & benötigte Zugänge

| # | Blocker | Auswirkung | Lösung |
|---|---|---|---|
| B-1 | **Semrush API Units fast aufgebraucht** (Start 1.250, jetzt **250**). Verbrauch heute: 1.000 Units (Domain, Rankings, 77 Keyword-Messwerte). | Keine breite Discovery (Related/Questions 40 Units/Zeile), keine Wettbewerber-/SERP-Analyse. | Units aufladen bzw. Plan prüfen; Budget pro Lauf festlegen (Empfehlung für nächsten Schritt: ca. 3.000–5.000 Units). |
| B-2 | **Kein Search-Console-Zugriff** in dieser Umgebung. | Keine echten Queries/Impressionen/CTR, keine Kannibalisierung auf Query-Ebene, Local-Signale fehlen. | Pilot-Lösung: GSC-Leistungsbericht (Suchanfragen + Seiten, 16 Monate) als Export in Drive ablegen → ich importiere. |
| B-3 | Google Business Profile nicht angebunden. | Öffnungszeiten (maßgeblich) und GBP-Anfragen unbekannt. | Zeiten kurz nennen oder GBP-Export bereitstellen. |
| B-4 | SERP-Tiefenanalyse noch offen. | Wettbewerb lokal/B2B nicht bewertet. | Nach B-1: `phrase_organic` nur für ernsthafte Kandidaten (OPP-01 bis 05, Pilotstädte). |

---

## 8. Vorgeschlagene nächste Schritte (zur Freigabe)

1. **Entscheidung Units-Budget (B-1)** und **GSC-Export (B-2)**.
2. Mit GSC: Query-/URL-Mapping, Kannibalisierung, CTR-Quick-Wins nachziehen.
3. SERP- & Wettbewerbsanalyse nur für OPP-01–05, NBO-01/02 und die 2 Pilotstädte.
4. Daraus das **erste Approval-Gate-1-Paket** (vollständige Empfehlungskarten).

*Keine Content-Produktion und keine Website-Änderungen bis zur Freigabe.*
