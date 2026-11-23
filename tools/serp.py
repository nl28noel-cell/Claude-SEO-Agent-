#!/usr/bin/env python3
"""Echte SERP für die Research Engine: Semrush Organic Results (phrase_organic) – budget- und cachebewusst.

Ablauf je Opportunity (docs/research-strategy.md):
  1. plan   → welche Keywords brauchen eine SERP? (Primary zuerst; Secondary nur bei möglicherweise anderem Intent;
              ähnliche Keywords zusammengefasst; frischer Cache = keine Abfrage) + Kosten + Budget-Urteil
  2. Abfrage über den Semrush-Konnektor (nur bei Urteil "run"): execute_report phrase_organic, database de, display_limit 10
  3. ingest → Ergebnis in den Cache (data/serp-cache/<db>/<key>.json), Units verbuchen (config/semrush_budget.json + Log)
  4. Ranking-URLs mit tools/page_profile.py abrufen → Dossier C/D/E/I aktualisieren (SERP competitors ≠ Research competitors)

    python3 tools/serp.py plan   <client> <OPP>                          -> Plan als JSON (führt NICHTS aus)
    python3 tools/serp.py ingest <keyword> <datei.csv|json> [--units N] [--db de]   -> Cache + Budget
    python3 tools/serp.py show   <keyword> [--db de]                     -> Cache-Eintrag
    python3 tools/serp.py cost   <anzahl_keywords> [--lines 10]          -> Kostenrechnung
Dieses Skript ruft Semrush nie selbst auf.
"""
import csv, datetime as dt, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUDGET = os.path.join(ROOT, "config", "semrush_budget.json")
CACHE = os.path.join(ROOT, "data", "serp-cache")
STOP = {"mit", "per", "fuer", "der", "die", "das", "und", "von", "in", "im", "zur", "zum", "einer", "eine", "ein"}


def budget():
    return json.load(open(BUDGET, encoding="utf-8"))


def norm(kw):
    """Ähnliche Keywords auf einen Schlüssel abbilden: Kleinschreibung, Umlaute, Stoppwörter, Plural, Wortreihenfolge."""
    k = kw.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    k = unicodedata.normalize("NFKD", k).encode("ascii", "ignore").decode()
    toks = [t for t in re.split(r"[^a-z0-9]+", k) if t and t not in STOP]
    def stem(t):  # drohnen→drohne, aufnahmen→aufnahme, messungen→messung, flugs→flug
        if len(t) <= 4:
            return t
        if t.endswith("ungen"):
            return t[:-2]
        if t.endswith("en"):
            return t[:-1]
        if t.endswith("s") and not t.endswith("ss"):
            return t[:-1]
        return t
    toks = [stem(t) for t in toks]
    return " ".join(sorted(toks))


def cache_path(kw, db="de"):
    return os.path.join(CACHE, db, re.sub(r"[^a-z0-9]+", "-", norm(kw)).strip("-") + ".json")


def cached(kw, db="de", ttl_days=None):
    """Frischer Cache-Eintrag oder None."""
    p = cache_path(kw, db)
    if not os.path.exists(p):
        return None
    c = json.load(open(p, encoding="utf-8"))
    ttl = ttl_days if ttl_days is not None else budget()["serp"]["cache_ttl_days"]
    age = (dt.date.today() - dt.date.fromisoformat(c["fetched"][:10])).days
    return {**c, "age_days": age} if age <= ttl else None


def cost(n_keywords, lines=None):
    s = budget()["serp"]
    lines = s["display_limit"] if lines is None else lines
    return n_keywords * lines * s["cost_per_line"]


def plan(client, opp):
    """Abfrageplan aus dem Dossier (B_demand). Secondary nur mit serp_check=true (möglicherweise anderer Intent)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import research
    R = research.load(client, opp) or {}
    b, s = budget(), budget()["serp"]
    kws = (R.get("B_demand") or {}).get("keywords") or []
    cand = [k for k in kws if k.get("role") == "primary"] + [k for k in kws if k.get("role") != "primary" and k.get("serp_check")]
    seen, items = {}, []
    for k in cand:
        key = norm(k["keyword"])
        if key in seen:
            items.append({"keyword": k["keyword"], "action": "skip_similar", "same_as": seen[key], "units": 0})
            continue
        seen[key] = k["keyword"]
        c = cached(k["keyword"], s["database"])
        if c:
            items.append({"keyword": k["keyword"], "action": "cache", "fetched": c["fetched"], "age_days": c["age_days"], "units": 0})
        else:
            items.append({"keyword": k["keyword"], "action": "query", "role": k.get("role"), "reason": k.get("serp_check_reason") or ("Primary Keyword" if k.get("role") == "primary" else "anderer Intent möglich"), "units": cost(1)})
    skipped = [k["keyword"] for k in kws if k not in cand and k.get("role") != "do_not_target"]
    need = sum(i["units"] for i in items)
    after = b["units_balance"] - need
    if need == 0:
        verdict, why = "none", "Alle benötigten SERPs im frischen Cache"
    elif need > b.get("max_units_per_opportunity", need):
        verdict, why = "budget_hold", f"{need} Units > Limit je Opportunity ({b['max_units_per_opportunity']})"
    elif after < b["reserve_units"]:
        verdict, why = "budget_hold", f"Kontostand {b['units_balance']} − {need} = {after} < Reserve {b['reserve_units']}"
    elif not b.get("auto_use"):
        verdict, why = "approval_required", "Automatische Nutzung ausgeschaltet"
    else:
        verdict, why = "run", f"Budget reicht: {b['units_balance']} − {need} = {after} ≥ Reserve {b['reserve_units']}"
    return {"opp": opp, "report": s["report"], "database": s["database"], "display_limit": s["display_limit"],
            "items": items, "not_queried": skipped, "units_needed": need, "units_balance": b["units_balance"],
            "balance_checked_at": b.get("balance_checked_at"), "reserve_units": b["reserve_units"], "verdict": verdict, "why": why,
            "call": {"tool": "Semrush execute_report", "report": s["report"],
                     "params": {"phrase": "<keyword>", "database": s["database"], "display_limit": s["display_limit"]},
                     "check_first": "get_report_schema('phrase_organic') → price prüfen (kostenlos)"}}


def _rows(path):
    t = open(path, encoding="utf-8").read().strip()
    if t.startswith("[") or t.startswith("{"):
        j = json.loads(t)
        rows = j.get("rows") or j.get("data") or j if isinstance(j, dict) else j
    else:
        rows = list(csv.DictReader(t.splitlines(), delimiter=";" if ";" in t.splitlines()[0] else ","))
    out = []
    for i, r in enumerate(rows, 1):
        g = lambda *ks: next((r[k] for k in ks if k in r and r[k] not in (None, "")), None)  # noqa: E731
        out.append({"position": int(g("Po", "Position", "position") or i), "domain": g("Dn", "Domain", "domain"),
                    "url": g("Ur", "Url", "URL", "url"), "serp_features": g("Fk", "SERP Features", "Fp")})
    return out


def ingest(kw, path, units=None, db="de"):
    res = _rows(path)
    b = budget()
    spent = units if units is not None else len(res) * b["serp"]["cost_per_line"]
    entry = {"keyword": kw, "key": norm(kw), "database": db, "fetched": dt.date.today().isoformat(), "source": "semrush " + b["serp"]["report"],
             "lines": len(res), "units_spent": spent, "results": res}
    os.makedirs(os.path.join(CACHE, db), exist_ok=True)
    json.dump(entry, open(cache_path(kw, db), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    b["units_balance"] = b["units_balance"] - spent
    b["balance_checked_at"] = dt.date.today().isoformat()
    b["balance_source"] = "berechnet nach Abfrage (tools/serp.py ingest)"
    json.dump(b, open(BUDGET, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log = os.path.join(CACHE, "usage-log.csv")
    new = not os.path.exists(log)
    with open(log, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "report", "database", "keyword", "lines", "units"])
        w.writerow([entry["fetched"], b["serp"]["report"], db, kw, len(res), spent])
    print(f"✓ {kw}: {len(res)} Ergebnisse gecacht · {spent} Units verbucht · Kontostand {b['units_balance']}")
    return entry


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    db = a[a.index("--db") + 1] if "--db" in a else "de"
    if a[0] == "plan":
        print(json.dumps(plan(a[1], a[2]), ensure_ascii=False, indent=2))
    elif a[0] == "ingest":
        ingest(a[1], a[2], int(a[a.index("--units") + 1]) if "--units" in a else None, db)
    elif a[0] == "show":
        print(json.dumps(cached(a[1], db, ttl_days=10**6), ensure_ascii=False, indent=2))
    elif a[0] == "cost":
        n = int(a[1]); lines = int(a[a.index("--lines") + 1]) if "--lines" in a else None
        print(f"{n} Keyword(s) × {lines or budget()['serp']['display_limit']} Zeilen × {budget()['serp']['cost_per_line']} Units = {cost(n, lines)} Units")
    else:
        sys.exit(__doc__)
