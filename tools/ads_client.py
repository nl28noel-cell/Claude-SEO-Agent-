#!/usr/bin/env python3
"""Google Ads API Client für den SEO Autopilot – AUSSCHLIESSLICH LESEND.

Authentifizierung: derselbe Service Account wie GSC (Credential-Lookup aus gsc_client.py),
Scope https://www.googleapis.com/auth/adwords. Der Service Account ist im MCC mit „Nur lesen“ hinterlegt.
Es werden nur die Endpunkte listAccessibleCustomers, googleAds:search und
KeywordPlanIdeaService (generateKeywordIdeas / generateKeywordHistoricalMetrics – reine Abfragen, ändern nichts) genutzt.
Mutate-Endpunkte sind in diesem Client bewusst nicht implementiert.

Befehle:
  python3 tools/ads_client.py check                         -> zugängliche Konten + Hierarchie unter dem MCC (nur Konsole)
  python3 tools/ads_client.py discover "<name-regex>" <out.json> -> Connectivity, MCC, Zielkonto, Fähigkeitstests (speichert keine fremden Kundennamen)
  python3 tools/ads_client.py query <cid> "<GAQL>" <out.csv> -> GAQL-Report (paginiert) als CSV
  python3 tools/ads_client.py ideas <cid> <kw1,kw2,..> <out.csv> [--url URL]  -> Keyword Planner Ideen (DE, Deutsch)
  python3 tools/ads_client.py history <cid> <kw1,kw2,..> <out.csv>             -> historische Keyword-Metriken
"""
import csv, json, os, sys

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gsc_client import load_credentials_info  # noqa: E402

API_VERSION = os.environ.get("ADS_API_VERSION", "v26")
BASE = f"https://googleads.googleapis.com/{API_VERSION}"
MCC = os.environ.get("ADS_LOGIN_CUSTOMER_ID", "5474466547")
GEO_DE, LANG_DE = "geoTargetConstants/2276", "languageConstants/1001"
_FORBIDDEN = ("mutate", ":upload", ":apply", ":remove", ":create")


def _session():
    info, source = load_credentials_info()
    print(f"[credential source: {source}]", file=sys.stderr)
    c = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/adwords"])
    c.refresh(Request())
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {c.token}", "login-customer-id": MCC})
    dev = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    if dev:
        s.headers["developer-token"] = dev
    return s


def _post(s, path, body):
    if any(f in path.lower() for f in _FORBIDDEN):
        raise SystemExit(f"Schreibender Endpunkt blockiert: {path}")
    r = s.post(BASE + path, json=body, timeout=120)
    if r.status_code != 200:
        try:
            e = r.json()["error"]; errs = [x for d in e.get("details", []) for x in d.get("errors", [])]
            msg = "; ".join(f"{list(x.get('errorCode', {}).values())}: {x.get('message')}" for x in errs) or e.get("message")
        except Exception:
            msg = r.text[:300]
        raise SystemExit(f"HTTP {r.status_code} {path}: {msg}")
    return r.json()


def search(s, cid, query):
    rows, token = [], None
    while True:
        body = {"query": query}
        if token:
            body["pageToken"] = token
        j = _post(s, f"/customers/{cid}/googleAds:search", body)
        rows += j.get("results", [])
        token = j.get("nextPageToken")
        if not token:
            return rows


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        elif isinstance(v, list):
            out[key] = json.dumps(v, ensure_ascii=False)
        else:
            out[key] = v
    return out


def write_csv(rows, out):
    flat = [flatten(r) for r in rows]
    cols = sorted({k for r in flat for k in r if not k.endswith("resourceName")})
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(flat)
    print(f"✓ {len(flat)} Zeilen → {out}")


def check():
    s = _session()
    r = s.get(BASE + "/customers:listAccessibleCustomers", timeout=60); r.raise_for_status()
    print("Direkt zugänglich:", ", ".join(x.split("/")[1] for x in r.json().get("resourceNames", [])))
    rows = search(s, MCC, "SELECT customer_client.id, customer_client.descriptive_name, customer_client.manager, customer_client.level, "
                           "customer_client.status, customer_client.currency_code, customer_client.time_zone, customer_client.test_account FROM customer_client")
    print(f"{'ID':<12} {'Lvl':<3} {'Mgr':<5} {'Status':<10} {'Cur':<4} Name")
    for x in sorted((r["customerClient"] for r in rows), key=lambda c: (int(c.get("level", 0)), c.get("descriptiveName", ""))):
        print(f"{x['id']:<12} {x.get('level', '0'):<3} {str(x.get('manager', False)):<5} {x.get('status', ''):<10} {x.get('currencyCode', ''):<4} {x.get('descriptiveName', '')}")


def discover(name_match, out):
    """Connectivity + Discovery + Fähigkeits-Test. Speichert nur MCC, das Zielkonto und die ANZAHL weiterer Konten
    (Namen/IDs anderer Kunden werden bewusst nicht in Kundendaten geschrieben)."""
    import datetime as dt, re
    s = _session()
    res = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
           "api_version": API_VERSION, "access_level": "Explorer (laut Nutzer; API-Antworten bestätigen Explorer-Grenzen)", "tests": {}}
    r = s.get(BASE + "/customers:listAccessibleCustomers", timeout=60)
    res["tests"]["list_accessible_customers"] = "ok" if r.ok else f"HTTP {r.status_code}"
    rows = search(s, MCC, "SELECT customer_client.id, customer_client.descriptive_name, customer_client.manager, customer_client.level, "
                           "customer_client.status, customer_client.currency_code, customer_client.time_zone FROM customer_client")
    cc = [x["customerClient"] for x in rows]
    mcc = next(c for c in cc if c["id"] == MCC)
    res["mcc"] = {"id": MCC, "name": mcc.get("descriptiveName"), "status": mcc.get("status"), "permission": "Read only (Service Account)"}
    others = [c for c in cc if c["id"] != MCC]
    res["client_accounts"] = {"total": len(others), "by_status": {st: sum(1 for c in others if c.get("status") == st) for st in sorted({c.get("status") for c in others})}}
    tgt = next((c for c in others if re.search(name_match, c.get("descriptiveName", ""), re.I)), None)
    res["account"] = ({"id": tgt["id"], "name": tgt.get("descriptiveName"), "status": tgt.get("status"), "currency": tgt.get("currencyCode"),
                       "time_zone": tgt.get("timeZone")} if tgt else None)
    res["tests"]["gaql_mcc"] = "ok"
    if tgt:
        try:
            search(s, tgt["id"], "SELECT customer.id FROM customer"); res["tests"]["gaql_account"] = "ok"
        except SystemExit as e:
            res["tests"]["gaql_account"] = str(e).split(": ", 2)[-1]
    probe = next((c["id"] for c in others if c.get("status") == "ENABLED" and not c.get("manager")), None)
    for meth, body in (("generateKeywordIdeas", {"language": LANG_DE, "geoTargetConstants": [GEO_DE], "keywordSeed": {"keywords": ["drohne"]}}),
                       ("generateKeywordHistoricalMetrics", {"language": LANG_DE, "geoTargetConstants": [GEO_DE], "keywords": ["drohne"]})):
        try:
            _post(s, f"/customers/{probe}:{meth}", body); res["tests"][meth] = "ok"
        except SystemExit as e:
            res["tests"][meth] = str(e).split(": ", 2)[-1]
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))


def ideas(cid, kws, out, url=None):
    s = _session()
    body = {"language": LANG_DE, "geoTargetConstants": [GEO_DE], "keywordPlanNetwork": "GOOGLE_SEARCH", "includeAdultKeywords": False}
    if kws and url:
        body["keywordAndUrlSeed"] = {"keywords": kws, "url": url}
    elif url:
        body["urlSeed"] = {"url": url}
    else:
        body["keywordSeed"] = {"keywords": kws}
    rows, token = [], None
    while True:
        if token:
            body["pageToken"] = token
        j = _post(s, f"/customers/{cid}:generateKeywordIdeas", body)
        rows += j.get("results", []); token = j.get("nextPageToken")
        if not token or len(rows) >= 2000:
            break
    out_rows = [{"keyword": r.get("text"), "avg_monthly_searches": r.get("keywordIdeaMetrics", {}).get("avgMonthlySearches"),
                 "competition": r.get("keywordIdeaMetrics", {}).get("competition"),
                 "competition_index": r.get("keywordIdeaMetrics", {}).get("competitionIndex"),
                 "low_top_bid_eur": _micros(r.get("keywordIdeaMetrics", {}).get("lowTopOfPageBidMicros")),
                 "high_top_bid_eur": _micros(r.get("keywordIdeaMetrics", {}).get("highTopOfPageBidMicros")),
                 "monthly": json.dumps([[m.get("year"), m.get("month"), m.get("monthlySearches")] for m in r.get("keywordIdeaMetrics", {}).get("monthlySearchVolumes", [])])}
                for r in rows]
    _write_plain(out_rows, out)


def history(cid, kws, out):
    s = _session()
    j = _post(s, f"/customers/{cid}:generateKeywordHistoricalMetrics",
              {"keywords": kws, "language": LANG_DE, "geoTargetConstants": [GEO_DE], "keywordPlanNetwork": "GOOGLE_SEARCH"})
    rows = [{"keyword": r.get("text"), "close_variants": "|".join(r.get("closeVariants", [])),
             "avg_monthly_searches": r.get("keywordMetrics", {}).get("avgMonthlySearches"),
             "competition": r.get("keywordMetrics", {}).get("competition"),
             "low_top_bid_eur": _micros(r.get("keywordMetrics", {}).get("lowTopOfPageBidMicros")),
             "high_top_bid_eur": _micros(r.get("keywordMetrics", {}).get("highTopOfPageBidMicros")),
             "monthly": json.dumps([[m.get("year"), m.get("month"), m.get("monthlySearches")] for m in r.get("keywordMetrics", {}).get("monthlySearchVolumes", [])])}
            for r in j.get("results", [])]
    _write_plain(rows, out)


def _micros(v):
    return round(int(v) / 1e6, 2) if v not in (None, "") else None


def _write_plain(rows, out):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"✓ {len(rows)} Zeilen → {out}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "check":
        check()
    elif a[0] == "discover":
        discover(a[1], a[2])
    elif a[0] == "query":
        write_csv(search(_session(), a[1], a[2]), a[3])
    elif a[0] in ("ideas", "history"):
        url = a[a.index("--url") + 1] if "--url" in a else None
        kws = [k.strip() for k in a[2].split(",") if k.strip()]
        (ideas(a[1], kws, a[3], url) if a[0] == "ideas" else history(a[1], kws, a[3]))
    else:
        sys.exit(__doc__)
