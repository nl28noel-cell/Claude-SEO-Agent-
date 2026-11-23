# SEO Issues & Opportunities – Spreewald Luftaufnahmen

Laufende Liste. **Status OPEN = erkannt, nichts verändert.** Änderungen an der Website nur nach Freigabe.

| ID | Datum | Typ | Befund | Status |
|---|---|---|---|---|
| F-001 | 22.11.2026 | Technik/Indexierung | /dachinspektion-mit-drohne/ fehlte in der Yoast-Sitemap. Ursache F-005. **Verifiziert 23.11.2026: jetzt in page-sitemap.xml (lastmod 2026-11-23T10:45:43Z)** | RESOLVED – MONITOR |
| F-002 | 22.11.2026 | Struktur | /drohne-luftaufnahmen-hochzeit/ steht in der Sitemap, ist aber nicht im Hauptmenü verlinkt (Prio 0–1, kein Handlungsdruck) | OPEN |
| F-003 | 22.11.2026 | Konsistenz/NAP | GBP (maßgeblich): Mo–Fr 09–17, Sa/So geschlossen. /kontakt/ stimmt überein. **Footer (alle Seiten) zeigt abweichend „Mo.–Fr.: 08:00–18:00 Uhr“** (verifiziert 23.11.2026) → Footer anpassen (nach Freigabe) | OPEN |
| F-004 | 22.11.2026 | Konsistenz/Preis | Preis-FAQ „ab ca. 230–250 €“ vs. Pakete ab 349 €. **Kein automatischer Fehler** – kontextbezogen prüfen (unterschiedliche Leistungen/Einstiegspreise) | OPEN – prüfen |
| F-005 | 23.11.2026 | Technik/Canonical | Dachinspektion: Canonical zeigte auf `…/dachinspektion-mit-drohne` (ohne Slash, 301). **Von Noel behoben; verifiziert 23.11.2026: Canonical = Self (mit Slash), HTTP 200, Schema-@id korrekt.** Siehe CL-001 | RESOLVED – MONITOR |
| F-006 | 23.11.2026 | Interne Verlinkung | Kontextuelle Links sehr dünn; Fassadeninspektion und Preise 0 eingehende Content-Links | OPEN |
| F-007 | 23.11.2026 | Schema | Nur Yoast-Standard; kein LocalBusiness/Service; FAQ-Schema fehlt auf Fassadeninspektion | OPEN |
| F-008 | 23.11.2026 | Bilder | ca. 45–65 % der Content-Bilder ohne Alt-Text | OPEN |
| F-009 | 23.11.2026 | On-Page | Viele H2 sind generische Template-Blöcke | OPEN |
| F-010 | 23.11.2026 | Kannibalisierung | „drohnenvermessung berlin“ / „anbieter vermessung drohne berlin“: Dachvermessung (7/8) + Gebäudeinspektion (59/87) | OPEN |
| F-011 | 23.11.2026 | Content-Claim | „Bis zu 99,4 % Genauigkeit“ (Dachvermessung) – Quelle bestätigen | OPEN – prüfen |
| F-012 | 23.11.2026 | Performance | Seitenübergreifender Impressionsrückgang ab Juli 2026 (≈ −50 %), Klicks stabil; stark: Immobilien, Baudoku, Dachvermessung, Gebäudeinspektion | OPEN – Analyse |
| F-013 | 23.11.2026 | Kannibalisierung | Dachinspektion-Queries landen überwiegend auf /drohne-dach-gebaeude-inspektion/ (813 vs. 382 Impr.) | OPEN – nach Freeze |
| F-014 | 23.11.2026 | Kannibalisierung | Fassadeninspektion-Queries landen auf /fassadenaufmass-…/ (448 Impr.); neue Seite im Aufbau | MONITOR |
| F-015 | 23.11.2026 | Content-Lücke | 3D-Modell-Queries (~1.300 Impr.) ohne passende Zielseite (Baudoku/Dachvermessung) | OPEN |
| F-016 | 23.11.2026 | CTR | Preisseite CTR 0,13 % bei Pos. ~10 (38.600 Impr., 33 statt ~1.000 erwarteten Klicks) | OPEN |
| F-017 | 23.11.2026 | Technik | /kontakt/?rwg_token=… (GBP-Reservierungslink) in GSC sichtbar – unkritisch | MONITOR |
| F-018 | 23.11.2026 | Datenqualität | Verdacht auf nicht-menschliche Impressionen (Frühjahr 2026: hohe Impr., 0 Klicks, danach 0) | HINWEIS |
