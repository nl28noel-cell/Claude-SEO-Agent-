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
| C · Live SERP | Quelle + Qualität (`validated`/`indicative`/`missing`), Intent-Urteil, Ergebnisse mit Seitentyp und Einordnung (Wettbewerber, Plattform, Software, Ratgeber, Verzeichnis, Partner) | source, quality, intent_verdict, results |
| D · Competitor Insights | Je relevantem Business-Wettbewerber: H1/Positionierung, Themen, Zielgruppe, FAQ, Trust/Proof, lokaler Fokus, Conversion, Takeaway | ≥ 1 Eintrag |
| E · Content Gap | Competitors cover · We already cover · We are missing · Opportunity to outperform | alle vier |
| F · Recommended Page Scope | Kernbotschaft, Intent, Zielgruppe, Key Questions, Leistungsinfos, Trust/Proof, Conversion-Ziel, **bewusst nicht auf dieser Seite** (mit Zielseite) | alle |
| G · Proposed Structure | Title-Vorschlag, H1, H2/H3 mit Zweck, Herleitung – keine ausformulierten Texte | h1, sections |
| H · Information Architecture | Parent, Target, Children, Siblings, Keyword Ownership + Do-not-target, interne Links, Kannibalisierung (mit GSC-Evidenz), Entscheidung | alle |
| I · How We Can Win | Hebel aus belegten Business-Assets | ≥ 1 |
| J · Risks / Unknowns | Risiken und offene Fragen mit Umgang | ≥ 1 |

Regeln: Wettbewerbertexte werden analysiert, nie übernommen. Wortzahlen sind Kontext, kein Ziel. Vorteile nur aus dem Business-Profil (§8), nichts erfinden (§10).

## Research-Status (`tools/research.py derive`)

| Status | Bedeutung | Gate 1 |
|---|---|---|
| `complete` | Alle Abschnitte gefüllt, SERP validiert | normal |
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

## Kostenbewusste Reihenfolge

1. **Cache** (Semrush-Keyword-Cache, frühere Dossiers, Drive-Notizen)
2. **Google Search Console** (Queries, Query×Seite → Kannibalisierung, 90-Tage-Trend)
3. **Bestehende Website** (Live-Abruf, Inventar, interne Links)
4. **Vorhandene Semrush-Daten**
5. **Web-/SERP-Recherche**: Websuche + `python3 tools/page_profile.py <urls> --out clients/<c>/data/research/<OPP>/pages` (Hosts müssen im Netzwerk der Umgebung erlaubt sein)
6. **Semrush kostenpflichtig** nur, wenn entscheidungsrelevant **und** von Noel freigegeben (`method.semrush_approved_by`). Aktuell ~250 Units geschützt.

Eine fehlende Semrush-SERP heißt nicht „keine Wettbewerbsanalyse“: Die Websuche liefert keine Google.de-Positionen, aber die Anbieter- und Seitentyp-Landschaft. Das wird als `quality: indicative` gekennzeichnet. Ist die Validierung für die Entscheidung nötig, kommt sie in `status.pending` → Status `incomplete` → kein stiller Entwurf.

## Befehle

```
python3 tools/research.py status   <client>            # Status aller Opportunities
python3 tools/research.py validate <client> [OPP ...]  # Schema prüfen (Exit 1 bei Fehlern)
python3 tools/research.py skeleton <client> <OPP>      # leeres Dossier anlegen
python3 tools/page_profile.py <url ...> --out <dir>    # Seitenprofile für C/D/E
```

Im Artifact: Opportunity-Detail zeigt Status, A–J und „Gate 1 – Strategie freigeben“; Workflow-Karten zeigen den Research-Status.
