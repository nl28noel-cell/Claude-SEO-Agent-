# SEO Change Log – Spreewald Luftaufnahmen

Jede relevante SEO-Maßnahme mit Datum, Ausführendem, Verifikation und Beobachtungsplan. Ziel: später nachvollziehen, welche Maßnahme welchen Effekt hatte.

| ID | Datum | URL | Maßnahme | Durch | Verifikation | Bezug |
|---|---|---|---|---|---|---|
| CL-001 | 23.11.2026 (WP modified 11:45 MEZ) | /dachinspektion-mit-drohne/ | Fehlerhaften Canonical (ohne Slash → 301) entfernt; Seite nutzt Self-Canonical | Noel | ✅ 23.11.2026 durch Claude: Canonical `https://www.spreewald-luftaufnahmen.de/dachinspektion-mit-drohne/`, HTTP 200, in page-sitemap.xml (lastmod 2026-11-23T10:45:43Z) | F-001, F-005, OPP-01 |

## Beobachtung CL-001 – Dachinspektion (Änderungsstopp bis Bewertung)

**Keine weiteren Änderungen an dieser Seite**, bis die Wirkung des Fixes bewertet ist.

Baseline vor Fix (Semrush DE, 23.11.2026): „dachinspektion mit drohne“ Pos. 45 (Vol. 110, KD 3). Keine weiteren Rankings der URL in den Top 100.

| Checkpoint | Datum | Prüfpunkte | Ergebnis |
|---|---|---|---|
| T+0 | 23.11.2026 | Sitemap ✅ · Canonical ✅ · HTTP 200 ✅ · robots index,follow ✅ | erledigt |
| T+7 | 30.11.2026 | Sitemap/Canonical erneut; Indexierung (GSC URL Inspection, sobald angebunden) | offen |
| T+14 | 07.12.2026 | + Ranking dachinspektion drohne / dachinspektion mit drohne / drohne dachinspektion / dachinspektion | offen |
| T+30 | 23.12.2026 | + GSC Impressions/Clicks/Position je Query | offen |
| T+60 | 22.01.2027 | Bewertung: Erfolgreich / Potenzial / Underperformer | offen |
| T+90 | 21.02.2027 | Entscheidung über weitere Optimierung (OPP-01 Teil 2: Keyword-Fokus) | offen |

Automatischer Check: `python3 tools/monitor_url.py <url>` (Sitemap, Canonical, Status, Robots).
