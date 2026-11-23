# SEO Change Log

> **Generiert aus `state/changes.json`** – bitte dort ändern, nicht hier.

| ID | Datum | URL | Maßnahme | Durch | Status | Bezug |
|---|---|---|---|---|---|---|
| CL-001 | 2026-11-23 | /dachinspektion-mit-drohne/ | Fehlerhaften Canonical (ohne Slash → 301) entfernt; Seite nutzt Self-Canonical. | Noel | monitoring · Change Freeze | OPP-01, F-001, F-005 |

## CL-001 – Dachinspektion: Canonical korrigiert

- Grund: Canonical zeigte auf eine Weiterleitung; Yoast schloss die Seite deshalb aus der Sitemap aus (F-001, F-005).
- Vorher: Canonical https://www.spreewald-luftaufnahmen.de/dachinspektion-mit-drohne (301), nicht in Sitemap
- Nachher: Canonical https://www.spreewald-luftaufnahmen.de/dachinspektion-mit-drohne/ (200), in page-sitemap.xml
- Einschätzung: Too early to tell

| Checkpoint | Fällig | Status | Ergebnis |
|---|---|---|---|
| T+0 | 2026-11-23 | done | Sitemap ✓ · Canonical ✓ · HTTP 200 ✓ · index,follow ✓. GSC URL Inspection: PASS, „Submitted and indexed“, Google-Canonical = Slash-URL ✓. Gespeichertes User-Canonical noch alt und keine Sitemap-Zuordnung – Stand letzter Crawl 26.10.2026 (vor dem Fix). |
| T+7 | 2026-11-30 | pending | Neuer Crawl? User-Canonical mit Slash? Sitemap erkannt? |
| T+14 | 2026-12-07 | pending | + Rankings Dachinspektion-Varianten |
| T+30 | 2026-12-23 | pending | + GSC Impressions/Clicks/Position je Query |
| T+60 | 2027-01-22 | pending | Bewertung: Erfolgreich / Potenzial / Underperformer |
| T+90 | 2027-02-21 | pending | Entscheidung über weitere Optimierung |
