#!/usr/bin/env python3
"""Keyword-Cache für Semrush-Abfragen (stdlib).

Ziel: Kein Keyword wird doppelt bezahlt. Vor jeder Semrush-Abfrage werden die
Kandidaten gegen den Cache geprüft; nur fehlende oder veraltete Keywords gehen
an die API. Auch "keine Daten"-Antworten werden gespeichert (kosten 0 Units,
müssen aber nicht erneut geprüft werden).

Cache-Datei: data/keyword-cache.csv  (eine Zeile pro keyword+database+quelle)

CLI:
  python3 tools/keyword_cache.py missing de 90 "kw1;kw2;kw3"   -> gibt nur ungecachte/alte Keywords aus
  python3 tools/keyword_cache.py import de semrush_phrase_these 2026-11-23 file.csv
  python3 tools/keyword_cache.py nodata de 2026-11-23 "kw1;kw2"
  python3 tools/keyword_cache.py stats
"""
import csv, datetime as dt, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "keyword-cache.csv")
FIELDS = ["keyword", "database", "source", "fetched", "volume", "cpc", "competition", "kd", "intent", "status"]


def norm(k):
    return " ".join(k.strip().lower().split())


def load():
    if not os.path.exists(CACHE):
        return {}
    with open(CACHE, newline="") as f:
        return {(r["keyword"], r["database"], r["source"]): r for r in csv.DictReader(f)}


def save(rows):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])


def missing(db, max_age_days, keywords, source="semrush_phrase_these"):
    c, today = load(), dt.date.today()
    out = []
    for k in keywords:
        r = c.get((norm(k), db, source))
        if not r or (today - dt.date.fromisoformat(r["fetched"])).days > max_age_days:
            out.append(norm(k))
    return sorted(set(out))


def import_semrush(db, source, fetched, path):
    c = load()
    with open(path, newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            k = norm(r["Keyword"])
            c[(k, db, source)] = {
                "keyword": k, "database": db, "source": source, "fetched": fetched,
                "volume": r.get("Search Volume", ""), "cpc": r.get("CPC", ""),
                "competition": r.get("Competition", ""),
                "kd": r.get("KD", r.get("Keyword Difficulty", r.get("Keyword Difficulty Index", ""))),
                "intent": r.get("Intent", r.get("Intents", "")), "status": "ok",
            }
    save(c)


def mark_nodata(db, fetched, keywords, source="semrush_phrase_these"):
    c = load()
    for k in keywords:
        k = norm(k)
        c[(k, db, source)] = dict.fromkeys(FIELDS, "") | {"keyword": k, "database": db, "source": source, "fetched": fetched, "status": "no_data"}
    save(c)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "missing":
        print(";".join(missing(sys.argv[2], int(sys.argv[3]), sys.argv[4].split(";"))))
    elif cmd == "import":
        import_semrush(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "nodata":
        mark_nodata(sys.argv[2], sys.argv[3], sys.argv[4].split(";"))
    elif cmd == "stats":
        c = load()
        print(f"{len(c)} Einträge, davon no_data: {sum(1 for r in c.values() if r['status']=='no_data')}")
