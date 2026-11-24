#!/usr/bin/env python3
"""Einmalige Übernahme der OPP-02-Recherche (23.11.2026) in Research Log + Evidence Store.

Nur belegte Metadaten:
- Seitenabrufe: Zeitstempel aus den Seitenprofilen (exakt)
- Dossier-/Engine-Schritte: Zeitpunkt des Git-Commits, der das Ergebnis enthält (at_precision=commit)
- GSC/GA4/Semrush-Keyword-Abrufe und Websuchen: nur Datum bekannt (at_precision=date), Uhrzeit nicht protokolliert
- Semrush-Keyword-Abfrage: Unit-Verbrauch wurde damals nicht protokolliert → units=None, "metadata unavailable"
Idempotent: bricht ab, wenn bereits OPP-02-Events existieren.
"""
import csv, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import research_log as RL  # noqa: E402

C, OPP = "spreewald-luftaufnahmen", "OPP-02"
NA = RL.NA


def commit_time(msg_prefix):
    out = subprocess.run(["git", "-C", ROOT, "log", "--format=%aI|%s"], capture_output=True, text=True).stdout.splitlines()
    for line in out:
        t, s = line.split("|", 1)
        if s.startswith(msg_prefix):
            return t.replace("+00:00", "Z")
    return None


def main():
    ev, lg = RL.load(C)
    if any(e.get("opp") == OPP for e in lg["events"]):
        sys.exit("OPP-02 bereits migriert")
    pages = os.path.join(ROOT, "clients", C, "data", "research", OPP, "pages")
    RL.save(C, ev, lg)
    RL.add_profiles(C, OPP, pages)
    ev, lg = RL.load(C)
    prof = {s["domain"]: s for s in ev["sources"] if s["type"] in ("competitor", "website")}
    own = prof["spreewald-luftaufnahmen.de"]
    comps = [s for s in ev["sources"] if s["type"] == "competitor"]
    ok_comps = [s for s in comps if s.get("status") == 200]

    t_v1 = commit_time("Opportunity Engine: Research-/Strategy-Stufe")
    t_v2 = commit_time("Research Engine: Semrush Organic Results")
    t_v2b = commit_time("Research Engine: SERP Validation")

    # ---- Quellen: GSC, GA4, Semrush, Website-Inventar, Websuchen
    prop = "https://www.spreewald-luftaufnahmen.de/ (URL-Präfix)"
    g_q = RL.add_source(ev, {"type": "gsc", "key": "gsc-query-baudoku", "opp_ids": [OPP], "title": "GSC · Queries Cluster Baudokumentation",
                             "fetched": "2026-11-23", "fetched_precision": "date", "url": None,
                             "meta": {"property": prop, "period": "2025-07-21 – 2026-11-20", "dimensions": "query", "filter": "Cluster „baudokumentation“ (27 Queries)",
                                      "raw_path": f"clients/{C}/data/gsc-2026-11/gsc_query.csv"}})
    g_qp = RL.add_source(ev, {"type": "gsc", "key": "gsc-query-page-baudoku", "opp_ids": [OPP], "title": "GSC · Query × Page",
                              "fetched": "2026-11-23", "fetched_precision": "date", "url": None,
                              "meta": {"property": prop, "period": "2025-07-21 – 2026-11-20", "dimensions": "query + page", "filter": "Cluster-Queries · /drohnen-baudokumentation/",
                                       "raw_path": f"clients/{C}/data/gsc-2026-11/gsc_query_page.csv"}})
    g_qd = RL.add_source(ev, {"type": "gsc", "key": "gsc-query-date-baudoku", "opp_ids": [OPP], "title": "GSC · Query × Datum (90-Tage-Vergleich)",
                              "fetched": "2026-11-23", "fetched_precision": "date", "url": None,
                              "meta": {"property": prop, "period": "2025-07-21 – 2026-11-20 (Vergleich letzte 90 vs. vorherige 90 Tage)", "dimensions": "query + date",
                                       "filter": "Cluster „baudokumentation“", "raw_path": f"clients/{C}/data/gsc-2026-11/gsc_query_date.csv"}})
    ga = RL.add_source(ev, {"type": "ga4", "key": "ga4-landing-baudoku", "opp_ids": [OPP], "title": "GA4 · Landingpages + Conversions",
                            "fetched": "2026-11-23", "fetched_precision": "date", "url": None,
                            "meta": {"property": "321987676", "period": "2025-07-21 – 2026-11-20", "dimensions": "landingPage + sessionDefaultChannelGroup; eventName (Lead-Taxonomie A–D)",
                                     "filter": "Landingpages des Clusters (/drohnen-baudokumentation/)", "raw_path": f"clients/{C}/data/ga4-2026-11/"}})
    kws = [r for r in csv.DictReader(open(os.path.join(ROOT, "data", "keyword-cache.csv"), encoding="utf-8"))
           if r["keyword"] in ("baudokumentation drohne", "baustellendokumentation drohne", "drohne baustelle", "baufortschrittsdokumentation", "baudokumentation", "baustellendokumentation")]
    sm = RL.add_source(ev, {"type": "semrush", "key": "semrush-phrase_these-baudoku-2026-11-23", "opp_ids": [OPP], "title": f"Semrush Batch Keyword Overview · {len(kws)} Keywords · DE",
                            "fetched": kws[0]["fetched"], "fetched_precision": "date", "url": None,
                            "semrush": {"report": "Batch Keyword Overview", "endpoint": "phrase_these", "keyword": ", ".join(r["keyword"] for r in kws), "database": "DE",
                                        "results_count": len(kws), "units": None, "units_note": f"{NA} – Verbrauch wurde bei dieser Abfrage nicht protokolliert",
                                        "mode": "cache", "mode_note": "Damals live abgefragt; heute aus dem Keyword-Cache gelesen (0 Units)",
                                        "raw_path": "data/keyword-cache.csv",
                                        "results": [{"keyword": r["keyword"], "volume": int(r["volume"]), "kd": float(r["kd"]), "cpc": float(r["cpc"])} for r in kws],
                                        "link": None, "link_note": "Der Semrush-Konnektor liefert keine Report-URL."}})
    inv = RL.add_source(ev, {"type": "website", "key": "inventory-2026-11-22", "opp_ids": [OPP], "title": "Website-Inventar + interne Links (17 URLs)",
                             "fetched": "2026-11-22", "fetched_precision": "date", "url": "https://www.spreewald-luftaufnahmen.de/drohnen-baudokumentation/",
                             "meta": {"raw_path": f"clients/{C}/data/baseline-2026-11/links.csv", "note": "Interne Links auf die Seite: nur Startseite"}})
    ws = []
    for q, note in (("baudokumentation drohne (Standard-Suche)", "Wortlaut der Suchanfrage nicht protokolliert; Ergebnis überwiegend Fachartikel/PDFs"),
                    ("baudokumentation drohne (Extended-Suche)", "Wortlaut nicht protokolliert; Ergebnis: Anbieter-Landingpages"),
                    ("Domain-gefilterte Suche (Software/Wettbewerber 2024)", "Wortlaut nicht protokolliert; Ergebnis: airclip, capmo, airteam, schicker-allmedia"),
                    ("baustellendokumentation drohne berlin anbieter", "Wortlaut protokolliert; Ergebnis überwiegend Plattformen/Technik, keine neuen Wettbewerber"),
                    ("baufortschritt drohne dokumentieren dienstleister brandenburg", "Wortlaut protokolliert; Ergebnis überwiegend Fachartikel")):
        ws.append(RL.add_source(ev, {"type": "web_search", "key": "ws-" + q, "opp_ids": [OPP], "title": f"WebSearch · {q}", "fetched": "2026-11-23", "fetched_precision": "date",
                                     "url": None, "meta": {"tool": "Claude WebSearch (US-Index, keine Google.de-SERP, keine Positionen)", "note": note}}))

    # ---- Findings (mit Belegen)
    rec = [s["id"] for s in ok_comps if json.load(open(os.path.join(ROOT, s["raw_path"]), encoding="utf-8"))["signals"]["intervall_abo"] >= 3]
    faq = [s["id"] for s in ok_comps if "FAQPage" in (s["meta"].get("schema_types") or [])]
    f_rec = RL.add_finding(ev, OPP, "D", "Mehrere Research competitors stellen Baudokumentation als regelmäßigen/laufenden Prozess dar (Intervalle, laufende Begleitung).", rec)
    f_meth = RL.add_finding(ev, OPP, "D", "Nur einzelne Seiten erklären, wie Aufnahmen über die Bauzeit vergleichbar werden (Wiederholbarkeit, einmalig vs. laufend, Lieferformate).",
                            [prof["techpic.de"]["id"], prof["bondar-sky-images.de"]["id"]])
    f_faq = RL.add_finding(ev, OPP, "E", "FAQ mit FAQPage-Schema bei mehreren Research competitors; unsere Seite hat keine FAQ.", faq + [own["id"]])
    f_own = RL.add_finding(ev, OPP, "E", "Eigene Seite: „Baustellendokumentation“ nur im Title und einmal im Text, keine FAQ, kein sichtbarer Ablauf, keine Angaben zu Übergabe/Lieferzeit; Meta Description verspricht „3D-Modellierung“.", [own["id"]])
    f_kw = RL.add_finding(ev, OPP, "B", "Kern-Keywords mit messbarer Nachfrage und sehr niedriger KD: baudokumentation drohne 140 (KD 5), baustellendokumentation drohne 110 (KD 0); Varianten ohne „Drohne“ 720/880 mit Software-Muster.", [sm])
    f_pos = RL.add_finding(ev, OPP, "B", "Schwache Positionen: Cluster Ø 30, 0 Klicks; „baustellendokumentation drohne“ 24,9 (90 Tage 14,5); Berlin-Variante Pos. 2,3.", [g_q, g_qd])
    f_can = RL.add_finding(ev, OPP, "H", "Keine Kannibalisierung: 3.289 von 3.291 Cluster-Impressionen auf /drohnen-baudokumentation/.", [g_qp])
    f_ga = RL.add_finding(ev, OPP, "B", "GA4: Cluster mit 2 Sitzungen und 1 Lead (Kontaktaktion) im Zeitraum – Richtung, keine Statistik.", [ga])
    f_link = RL.add_finding(ev, OPP, "H", "Einziger interner Link auf die Seite kommt von der Startseite.", [inv])

    # ---- Events (chronologisch)
    E = lambda **k: RL.add_event(lg, {"opp": OPP, **k})  # noqa: E731
    E(at="2026-11-23", at_precision="date", action="gsc_analysis", title="GSC-Auswertung Cluster Baudokumentation",
      summary="27 Cluster-Queries über 16 Monate ausgewertet, inkl. 90-Tage-Vergleich und Analyse des Sichtbarkeitsrückgangs.",
      found="3.291 Impressionen, 0 Klicks, Ø Pos. 30; Rückgang ab 18.05.2026 überwiegend themenfremde Queries; echter Verlust: „baustellendokumentation drohne“.",
      source_ids=[g_q, g_qd], finding_ids=[f_pos])
    E(at="2026-11-23", at_precision="date", action="semrush_keyword", title="Semrush Keyword Research",
      summary="Suchvolumen, KD und CPC für 6 Keywords des Clusters (DE).", found="140 / 110 / 70 / 20 / 720 / 880 Suchen pro Monat",
      source_ids=[sm], finding_ids=[f_kw], units=None, units_note=f"{NA} (nicht protokolliert)")
    E(at="2026-11-23", at_precision="date", action="ga4_analysis", title="GA4 Search → Business",
      summary="Sitzungen, Funnel Intent und Leads der Cluster-Landingpage.", found="2 Sitzungen · 1 Lead (Kontakt)", source_ids=[ga], finding_ids=[f_ga])
    E(at="2026-11-23", at_precision="date", action="web_research", title="Independent Web Research",
      summary="Eigenständige Websuche für „baudokumentation drohne“ und zwei regionale Varianten (5 Suchen, Standard/Extended/Domainfilter). Keine Google.de-SERP, keine Positionen.",
      found=f"13 Domains gefunden, davon {len(comps)} Anbieterseiten zur Analyse ausgewählt.", source_ids=ws)
    E(at=own["fetched"], at_precision="exact", action="own_page_analysis", title="Eigene Seite analysiert",
      summary="/drohnen-baudokumentation/ live abgerufen und mit Inventar/internen Links abgeglichen.",
      found="„Baustellendokumentation“ nur im Title, keine FAQ, kein Ablauf, keine Übergabe-/Lieferangaben; nur 1 interner Link (Startseite).",
      source_ids=[own["id"], inv], finding_ids=[f_own, f_link], links=[{"label": "Eigene Seite öffnen", "url": own["url"]}])
    last = max(s["fetched"] for s in comps)
    E(at=last, at_precision="exact", action="competitor_analysis", title="Wettbewerberseiten analysiert",
      summary=f"{len(comps)} Anbieterseiten abgerufen und profiliert (Gliederung, Themen, Zielgruppen, Trust, Conversion).",
      found=f"{len(ok_comps)} Seiten erfolgreich analysiert, {len(comps) - len(ok_comps)} nicht abrufbar (dronext.de, SSL-Fehler).",
      insight="Mehrere Anbieter positionieren die Leistung als regelmäßige Baufortschrittsdokumentation; nur einzelne erklären, wie Aufnahmen vergleichbar werden.",
      source_ids=[s["id"] for s in comps], finding_ids=[f_rec, f_meth, f_faq])
    E(at=t_v1, at_precision="commit", action="cannibalization", title="Kannibalisierung geprüft",
      summary="Query × Page für alle Cluster-Queries geprüft.", found="Risiko gering – nur eine URL erhält Impressionen.", source_ids=[g_qp], finding_ids=[f_can])
    E(at=t_v1, at_precision="commit", action="content_gap", title="Content Gap erstellt",
      summary="Wettbewerberthemen gegen eigene Seite und belegte Business-Assets gestellt.", found="Fehlend: Methode, FAQ, Ablauf, Übergabe, Abgrenzung, Begriff „Baustellendokumentation“.",
      source_ids=[own["id"]] + [s["id"] for s in ok_comps], finding_ids=[f_own, f_faq])
    E(at=t_v1, at_precision="commit", action="ia_review", title="Information Architecture geprüft",
      summary="Parent/Siblings/Keyword Ownership, interne Links.", found="OPTIMIZE bestehende URL; keine Child Pages; interne Links ergänzen.", source_ids=[inv, g_qp], finding_ids=[f_link, f_can])
    E(at=t_v1, at_precision="commit", action="dossier", title="Research Dossier v1 erstellt",
      summary="Dossier A–J; Entscheidung OPTIMIZE; Status Research complete · with limits.", found="Status Opportunity: Strategy ready for Gate 1")
    E(at=t_v2, at_precision="commit", action="semrush_serp", title="Semrush SERP Research – nicht ausgeführt",
      summary="Organic Results für „baudokumentation drohne“ geplant (DE, Top 10, 100 Units).", found="Budget hold: Kontostand 250 = Reserve 250 → keine Abfrage, 0 Units", units=0)
    E(at=t_v2, at_precision="commit", action="reassessment", title="Research Dossier v2 – Strategie geschärft",
      summary="SERP-Aussagen an Datenlage angepasst; Scope, Struktur, How We Can Win auf strukturierte, wiederholbare Baufortschrittsdokumentation; IA Current/Recommended.",
      found="Entscheidung bleibt OPTIMIZE")
    E(at=t_v2b, at_precision="commit", action="dossier", title="Research Dossier v2 aktualisiert",
      summary="SERP Validation (Semrush pending, Independent Web Research completed); Übergabe- und Intervallformulierung nach Antwort Noel.",
      found="Status: Research complete · with limits")
    RL.save(C, ev, lg)
    print(f"✓ {len(ev['sources'])} Quellen · {len(ev['findings'])} Findings · {len(lg['events'])} Events")


if __name__ == "__main__":
    main()
