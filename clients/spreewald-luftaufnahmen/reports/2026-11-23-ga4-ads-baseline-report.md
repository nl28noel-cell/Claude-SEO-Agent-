# GA4 + Google Ads – Anbindung und Baseline (23.11.2026)

Nur lesend. Keine Änderungen an GA4, GTM, Tracking, Google Ads oder der Website.

## Zugriff

| Quelle | Ergebnis |
|---|---|
| Google Ads API (v26) | Service Account funktioniert über das MCC **SemSharks (5474466547)**, Berechtigung „Nur lesen“. 4 Kundenkonten (3 aktiv, 1 gekündigt). |
| Spreewald-Ads-Konto | **1935597794 · Status CANCELED** → API liefert keine Daten (`CUSTOMER_NOT_ENABLED`). |
| Keyword Planner | `generateKeywordIdeas` / `generateKeywordHistoricalMetrics` mit Explorer-Zugang gesperrt (`DEVELOPER_TOKEN_NOT_APPROVED`). Braucht **Basic Access**. |
| GA4 | Data API + Admin API aktiv; Service Account hat bereits Lesezugriff auf **Property 321987676** („Spreewald-Luftaufnahmen – GA4“). Keine manuelle Aktion nötig. |
| GA4 ↔ Ads | Verknüpfung zum Konto 1935597794 vorhanden → Paid-Historie 06/2023–12/2024 über GA4 auswertbar. |

## GA4-Baseline (07/2022 – 11/2026)

| Jahr | Sitzungen | organisch | Anfragen (primär) | Kontakt-Klicks |
|---|---:|---:|---:|---:|
| 2022 | 273 | 111 | 0 | 0 |
| 2023 | 913 | 378 | 3 | 7 |
| 2024 | 1.854 | 260 | 12 | 156* |
| 2025 | 287 | 205 | 7 | 5 |
| 2026 | 207 | 96 | 5 | 1 |

\* 2024 überwiegend Chat-Klicks aus P-Max-Kampagnen (Qualität fraglich, teils doppelt erfasst).

Zeitraum wie GSC (21.07.2025–20.11.2026): Organic Search 168 Sitzungen, 67 % Engagement, Ø 0:56 min, 5 Anfragen + 2 Kontakt-Klicks – der mit Abstand wertvollste Kanal. Direct 115 Sitzungen, 29 % Engagement, 3 Anfragen.

## Datenqualität (wichtig für jede Interpretation)

- **F-019**: Die GA4-Summe „Key Events“ ist als Business-KPI unbrauchbar: Tag-Assistant-Testverkehr (46 Sitzungen, 66 Events), Social-Klicks und Heyflow-Interaktionen als Key Events, früher sogar `scroll`. Das Dashboard zählt nur klassifizierte Business-Conversions ohne Testverkehr.
- **F-020**: Ads-Kosten auf Kampagnenebene (über GA4) unplausibel (~96 T€, identische Monatswerte, bis 150 Klicks je Sitzung). Keyword-Ebene plausibel: **1.267 € für 208 Klicks, Ø CPC 6,09 €** (Search-Kampagnen).
- **F-021**: GA4 erfasst nur ≈ 51 % der organischen Google-Klicks laut GSC (Consent) → GA4 nur relativ nutzen.
- **F-022**: Doppelte/umbenannte Events (`click to chat` vs. `click_to_chat`, `kontaktformular_gesendet` → `kontakt_form_send`).
- Sehr kleine Fallzahlen: Anfragen je Seite sind Einzelfälle – Richtung, keine Statistik.

## Events → Business-Conversion (state/conversions.json)

| Klasse | Events |
|---|---|
| Business-Conversion (primär) | `kontakt_form_send`, `heyflow_formular_abgesendet`, historisch `kontaktformular_gesendet` |
| Kontaktabsicht (sekundär) | `tel_klick`, `email_klick`, `click_to_chat` (nicht doppelt: `click to chat`) |
| Micro / Engagement | `heyflow_interaktion`, `heyflow_erste_interaktion`, `heyflow_button_klick` |
| Keine Conversion | `fb_klick`, `ytb_klick`, `purchase`, `scroll`, `heyflow_exit` |

Empfehlung (nur nach deiner Freigabe, nicht durch den Agenten): Key Events in GA4 auf die primären + sekundären Events reduzieren und Tag-Assistant-Traffic als interner Traffic filtern.

## Zusammenführung (Search → Business)

Join-Schlüssel: **Themencluster** (gleiche Regex-Cluster für GSC-Queries, Semrush-Keywords, Ads-Keywords/Kampagnen) und **Landingpage-Pfad** (normalisiert: klein, ohne Query/abschließenden Slash). Je Cluster: Nachfrage (Semrush) → organische Sichtbarkeit (GSC) → Paid-Historie (Ads über GA4) → Landingpages (Inventar) → Engagement + Anfragen (GA4) → Business-Priorität (Profil) → regelbasierte Signale.

Beispiel aus den Daten – **Dachvermessung**: 1.970 Suchen/Monat (Semrush), organisch Ø Position 42 (schwach), 840 € Paid-Historie für 123 Klicks, passende Seite `/drohne-dach-vermessung` vorhanden, 2 Anfragen + 1 Kontakt-Klick in 16 Monaten, Priorität 8/10. Genau das Muster „Nachfrage + bezahlte Klicks + Conversions + schwache organische Sichtbarkeit + vorhandene Seite + hohe Priorität“.

## Offene Entscheidungen

1. Basic Access für das Ads Developer Token beantragen (Keyword Planner als zweite Keyword-Quelle neben Semrush).
2. Optional: GA4-Key-Events bereinigen (siehe oben) – nur mit Freigabe.
3. Falls Google Ads reaktiviert wird: echte Kampagnen-/Search-Term-/Conversion-Action-Daten automatisch über `tools/ads_client.py`.
