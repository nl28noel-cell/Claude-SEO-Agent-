# GA4 + Google Ads – Anbindung und Baseline (23.11.2026)

Nur lesend. Keine Änderungen an GA4, GTM, Tracking, Google Ads oder der Website.

## Zugriff

| Quelle | Ergebnis |
|---|---|
| Google Ads API (v26) | Service Account funktioniert über das MCC **SemSharks (5474466547)**, Berechtigung „Nur lesen“. 4 Kundenkonten (3 aktiv, 1 gekündigt). |
| Spreewald-Ads-Konto | **1935597794 · Status CANCELED** – bewusst gekündigt, wird nicht reaktiviert. API liefert dafür keine Daten (`CUSTOMER_NOT_ENABLED`); Paid-Historie über GA4. |
| Keyword Planner | KeywordPlanIdeaService mit der Zugriffsstufe **Explorer** des Cloud-Projekts gesperrt. Benötigt **Basic Access** – seit dem Developer-Token-Sunset (09.09.2026) beantragt in der **Google Cloud Console → Google Ads API Overview**, Voraussetzung **Brand Verification**. Planning Customer künftig ein aktives MCC-Konto (nur Planner-Zugang). |
| GA4 | Data API + Admin API aktiv; Service Account hat bereits Lesezugriff auf **Property 321987676** („Spreewald-Luftaufnahmen – GA4“). Keine manuelle Aktion nötig. |
| GA4 ↔ Ads | Verknüpfung zum Konto 1935597794 vorhanden → Paid-Historie 06/2023–12/2024 über GA4 auswertbar. |

## GA4-Baseline (07/2022 – 11/2026)

Zeitraum wie GSC (21.07.2025–20.11.2026), ohne Testverkehr:

| Kanal | Sitzungen | Engagement | Funnel Intent (Sitzungen) | Leads: Form | Leads: Contact |
|---|---:|---:|---:|---:|---:|
| Organic Search | 168 | 67 % | 30 | 5 | 2 |
| Direct | 115 | 29 % | 3 | 3 | 0 |

Organic Search ist der wertvollste Kanal. Exakte Werte je Kanal, Landingpage und Zeitraum im Artifact (Analytics, Search → Business).

## Datenqualität (technische Befunde)

- **F-019 Tag-Assistant-Testverkehr**: 46 Sitzungen / 66 Funnel-Events aus Tag-Tests – im Dashboard ausgeschlossen.
- **F-020**: Ads-Kosten auf Kampagnenebene (über GA4) unplausibel; Keyword-Ebene plausibel (1.267 € / 208 Klicks, Ø CPC 6,09 €).
- **F-021**: GA4 erfasst ≈ 51 % der organischen Google-Klicks (Consent) → nur relativ nutzen.
- **F-022**: `click to chat` ist ein technisches Duplikat von `click_to_chat` (141 von 141 Auslösungen parallel) → nicht doppelt gezählt.
- Die bewusst gewählte GA4-Key-Event-Konfiguration ist **kein** Datenqualitätsproblem und wird nicht bewertet.

## Business-Klassifizierung (state/conversions.json, Definition Noel)

GA4 Key Event und SEO-Autopilot-Klassifizierung sind getrennt. GA4 wird nicht verändert.

| Ebene | Events | Verwendung |
|---|---|---|
| A · Lead / Contact – Form Submission | `kontakt_form_send`, `heyflow_formular_abgesendet`, hist. `kontaktformular_gesendet` | Leads |
| A · Lead / Contact – Direct Contact Action | `tel_klick`, `email_klick`, `click_to_chat` | Leads (Kontakt technisch nicht bestätigt) |
| B · Micro Conversion / Funnel Intent | `heyflow_interaktion`, `heyflow_erste_interaktion`, `heyflow_button_klick`, `heyflow_exit` | sichtbar, als Sitzungen gezählt, nie zu Leads addiert |
| C · Engagement | `scroll`, `video_*`, `user_engagement` | keine Conversion |
| D · Outbound / sonstige | `fb_klick`, `ytb_klick`, `click` | separat, nicht für Priorisierung |

Funnel: Search Demand → Visibility → Clicks → Sessions → Engaged Sessions → Funnel Intent → Leads / Contacts (Form | Direct Contact).

## Zusammenführung (Search → Business)

Join-Schlüssel: **Themencluster** (gleiche Regex-Cluster für GSC-Queries, Semrush-Keywords, Ads-Keywords/Kampagnen) und **Landingpage-Pfad** (normalisiert: klein, ohne Query/abschließenden Slash). Je Cluster: Nachfrage (Semrush) → organische Sichtbarkeit (GSC) → Paid-Historie (Ads über GA4) → Landingpages (Inventar) → Engagement + Anfragen (GA4) → Business-Priorität (Profil) → regelbasierte Signale.

Beispiel aus den Daten – **Dachvermessung**: 1.970 Suchen/Monat (Semrush), organisch Ø Position 42 (schwach), 840 € Paid-Historie für 123 Klicks, passende Seite `/drohne-dach-vermessung` vorhanden, 3 Leads (2 Formulare + 1 direkter Kontakt) und Funnel Intent in ≈ 4 Sitzungen in 16 Monaten, Priorität 8/10. Genau das Muster „Nachfrage + bezahlte Klicks + Conversions + schwache organische Sichtbarkeit + vorhandene Seite + hohe Priorität“.

## Offene Entscheidungen

1. Brand Verification + Basic Access für das Cloud-Projekt beantragen (Keyword Planner). Danach testet der Agent den Planner über das aktive Planning-Customer-Konto und vergleicht die Genauigkeit mit einem Konto ohne Spend.
