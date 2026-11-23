#!/usr/bin/env python3
"""GSC-Auswertung für den SEO Autopilot (stdlib).

Liest die Exporte aus tools/gsc_client.py (gsc_query.csv, gsc_query_page.csv,
gsc_query_date.csv, gsc_page_date.csv) und schreibt Analyse-CSVs + summary.json.

Aufruf: python3 tools/gsc_analyze.py <data_dir> <out_dir>
Die Cluster-/Orts-Regeln unten sind kundenspezifisch (Pilot Spreewald Luftaufnahmen)
und werden bei weiteren Kunden in eine Konfiguration ausgelagert.
"""
import csv, collections, json, os, re, sys

# --- Kundenspezifische Regeln (Reihenfolge = Priorität) -------------------
CLUSTERS = [
    ("brand", r"spreewald.?luft|spreewaldluft"),
    ("baudokumentation", r"baudoku|baustell|baufortschritt|bauvorhaben|baubegleit|bau\b|baustelle"),
    ("dachinspektion", r"dach.?(inspektion|kontroll|check|begutacht|prüf|schad|überprüf)|inspektion.*dach"),
    ("fassadeninspektion", r"fassad\w*.?(inspektion|prüf|schad|kontroll)|inspektion.*fassad"),
    ("dachvermessung", r"dach.?(vermess|aufmaß|aufmass|fläche|flaeche)|vermess\w*.*dach"),
    ("fassadenvermessung", r"fassad\w*.?(vermess|aufmaß|aufmass)|vermess\w*.*fassad"),
    ("vermessung_allgemein", r"vermess|aufmaß|aufmass|photogramm|3d|orthofoto|gelände|volumen"),
    ("inspektion_allgemein", r"inspekt|gebäudeprüf|gutacht|schaden|thermo|wärmebild"),
    ("bestandsaufnahme", r"bestandsaufnahme|bestandsdoku|beweissicher|dokumentation"),
    ("immobilien", r"immobilie|makler|exposé|expose|grundstück|grundstueck"),
    ("haus_privat", r"\bhaus\b|häuser|eigenheim|mein(em)? haus|vom haus|eigenen haus|garten"),
    ("hochzeit_event", r"hochzeit|event|veranstalt|feier|party|festival|konzert"),
    ("firma_imagefilm", r"firma|unternehmen|imagefilm|werbefilm|gewerbe|business"),
    ("video", r"video|film"),
    ("preis", r"preis|kost|teuer|günstig|guenstig|angebot|pauschal|tarif"),
    ("generisch_drohne", r"drohne|drohnen|luftaufnahm|luftbild|luftfoto|vogelperspektive|aus der luft|von oben|drone"),
]
PLACES = ["berlin", "brandenburg", "potsdam", "cottbus", "spreewald", "lübben", "luebben", "lübbenau", "schönefeld",
          "königs wusterhausen", "wildau", "frankfurt (oder)", "frankfurt oder", "eisenhüttenstadt", "oranienburg",
          "falkensee", "bernau", "eberswalde", "fürstenwalde", "ludwigsfelde", "zossen", "wünsdorf", "senftenberg",
          "spremberg", "guben", "forst", "lauchhammer", "finsterwalde", "luckau", "dahme", "storkow", "beeskow",
          "erkner", "strausberg", "hennigsdorf", "teltow", "kleinmachnow", "stahnsdorf", "werder", "brandenburg an der havel",
          "neuruppin", "rathenow", "prenzlau", "schwedt", "angermünde", "templin", "dresden", "leipzig", "hamburg",
          "münchen", "köln", "frankfurt", "hannover", "magdeburg", "rostock", "thüringen", "sachsen", "mecklenburg",
          "deutschland", "bundesweit", "in der nähe", "in meiner nähe", "umgebung",
          "spandau", "köpenick", "treptow", "neukölln", "marzahn", "pankow", "charlottenburg", "steglitz", "zehlendorf",
          "lichtenberg", "mitte", "kreuzberg", "friedrichshain", "prenzlauer berg", "reinickendorf", "tempelhof"]
NBO = r"thermo|wärmebild|pv|photovoltaik|solar|3d|orthofoto|volumen|halde|gelände|beweissicher|versicherung|gutacht|" \
      r"denkmal|kirche|turm|schornstein|windkraft|windrad|brücke|industrie|anlage|mieten|kaufen|kurs|schulung|führerschein|" \
      r"landwirtschaft|wald|baum|vermessungsbüro|kataster|lidar|mapping|inspektion\b"
# erwartete CTR je Position (grobe Branchenkurve, nur für relative Lücken)
EXP_CTR = {1: .28, 2: .15, 3: .10, 4: .07, 5: .05, 6: .04, 7: .03, 8: .025, 9: .02, 10: .018}


def cluster(q):
    for name, rx in CLUSTERS:
        if re.search(rx, q):
            return name
    return "sonstiges"


def places(q):
    return [p for p in PLACES if re.search(r"(^|\W)" + re.escape(p) + r"($|\W)", q)]


def exp_ctr(pos):
    return EXP_CTR.get(round(pos), 0.01 if pos <= 20 else 0.002)


def rd(path):
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        for k in ("clicks", "impressions"):
            r[k] = int(r[k])
        r["ctr"], r["position"] = float(r["ctr"]), float(r["position"])
    return rows


def wr(path, rows, fields):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(src, out):
    os.makedirs(out, exist_ok=True)
    q = rd(f"{src}/gsc_query.csv")
    qp = rd(f"{src}/gsc_query_page.csv")
    qd = rd(f"{src}/gsc_query_date.csv")
    host = "https://www.spreewald-luftaufnahmen.de"

    # Query-Tabelle anreichern
    for r in q:
        r["cluster"] = cluster(r["query"])
        r["places"] = "|".join(places(r["query"]))
        r["nbo_signal"] = bool(re.search(NBO, r["query"]))
        r["pos_bucket"] = "1-3" if r["position"] <= 3.5 else "4-10" if r["position"] <= 10.5 else "11-20" if r["position"] <= 20.5 else "21-50" if r["position"] <= 50.5 else ">50"
        r["exp_clicks"] = round(r["impressions"] * exp_ctr(r["position"]), 1)
        r["ctr_gap_clicks"] = round(r["exp_clicks"] - r["clicks"], 1)
    pages_by_q = collections.defaultdict(list)
    for r in qp:
        r["page"] = r["page"].replace(host, "") or "/"
        pages_by_q[r["query"]].append(r)
    for r in q:
        ps = sorted(pages_by_q.get(r["query"], []), key=lambda x: -x["impressions"])
        r["top_page"] = ps[0]["page"] if ps else ""
        r["n_pages"] = len(ps)
    fields = ["query", "cluster", "places", "nbo_signal", "clicks", "impressions", "ctr", "position", "pos_bucket",
              "exp_clicks", "ctr_gap_clicks", "top_page", "n_pages"]
    wr(f"{out}/queries_enriched.csv", sorted(q, key=lambda r: -r["impressions"]), fields)

    # Cluster-Summen
    cs = collections.defaultdict(lambda: {"queries": 0, "clicks": 0, "impressions": 0, "wpos": 0.0, "pages": collections.Counter()})
    for r in q:
        c = cs[r["cluster"]]
        c["queries"] += 1; c["clicks"] += r["clicks"]; c["impressions"] += r["impressions"]; c["wpos"] += r["position"] * r["impressions"]
        if r["top_page"]:
            c["pages"][r["top_page"]] += r["impressions"]
    crow = [{"cluster": k, "queries": v["queries"], "clicks": v["clicks"], "impressions": v["impressions"],
             "avg_pos": round(v["wpos"] / v["impressions"], 1) if v["impressions"] else "",
             "main_pages": " | ".join(f"{p} ({i})" for p, i in v["pages"].most_common(3))} for k, v in cs.items()]
    wr(f"{out}/clusters.csv", sorted(crow, key=lambda r: -r["impressions"]), list(crow[0].keys()))

    # Quick Wins: Pos 4-20 mit Impressionen, sortiert nach Klick-Potenzial
    qw = [r for r in q if 3.5 < r["position"] <= 20.5 and r["impressions"] >= 50]
    wr(f"{out}/quickwins_pos4-20.csv", sorted(qw, key=lambda r: -r["ctr_gap_clicks"]), fields)

    # Kannibalisierung: Query mit >=2 Seiten, zweite Seite >=20% der Impressionen der ersten
    cann = []
    for query, ps in pages_by_q.items():
        ps = sorted(ps, key=lambda x: -x["impressions"])
        if len(ps) >= 2 and ps[0]["impressions"] >= 30 and ps[1]["impressions"] >= 0.2 * ps[0]["impressions"]:
            cann.append({"query": query, "cluster": cluster(query),
                         "pages": " | ".join(f"{p['page']} (imp {p['impressions']}, pos {p['position']:.1f})" for p in ps[:4]),
                         "total_imp": sum(p["impressions"] for p in ps)})
    wr(f"{out}/cannibalization.csv", sorted(cann, key=lambda r: -r["total_imp"]), ["query", "cluster", "total_imp", "pages"])

    # Lokale Queries
    loc = [r for r in q if r["places"]]
    wr(f"{out}/local_queries.csv", sorted(loc, key=lambda r: -r["impressions"]), fields)

    # NBO-Signale
    nbo = [r for r in q if r["nbo_signal"]]
    wr(f"{out}/nbo_signals.csv", sorted(nbo, key=lambda r: -r["impressions"]), fields)

    # Zeitliche Entwicklung je Cluster (monatlich, aus query×date)
    mon = collections.defaultdict(lambda: collections.Counter())
    for r in qd:
        m = r["date"][:7]
        c = cluster(r["query"])
        mon[c][m + "_imp"] += r["impressions"]
        mon[c][m + "_clk"] += r["clicks"]
    months = sorted({k[:7] for v in mon.values() for k in v})
    trow = []
    for c, v in mon.items():
        row = {"cluster": c}
        for m in months:
            row[m] = v[m + "_imp"]
        trow.append(row)
    wr(f"{out}/cluster_trend_monthly_impressions.csv", sorted(trow, key=lambda r: -sum(r[m] for m in months)), ["cluster"] + months)

    summary = {
        "queries": len(q), "query_clicks": sum(r["clicks"] for r in q), "query_impressions": sum(r["impressions"] for r in q),
        "quickwins": len(qw), "cannibalization_cases": len(cann), "local_queries": len(loc), "nbo_queries": len(nbo),
        "places_seen": collections.Counter(p for r in loc for p in r["places"].split("|")).most_common(),
    }
    json.dump(summary, open(f"{out}/summary.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
