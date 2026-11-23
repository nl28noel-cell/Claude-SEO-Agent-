#!/usr/bin/env python3
"""Google Search Console Client für den SEO Autopilot (nur lesend).

Authentifizierung: Service Account, Scope webmasters.readonly.
Credential: Umgebungsvariable GSC_SERVICE_ACCOUNT_JSON_B64 (Base64 der JSON-Schlüsseldatei),
eingetragen ausschließlich in den Umgebungseinstellungen – nie im Repo oder Chat.

Abhängigkeiten: pip install google-auth requests

Befehle:
  python3 tools/gsc_client.py check
      -> zeigt Service-Account-E-Mail (ohne Schlüssel) und alle Properties, auf die er Zugriff hat
  python3 tools/gsc_client.py query <siteUrl> <start> <end> <dims> <out.csv>
      -> Search Analytics, dims kommagetrennt (query,page,country,device,date,searchAppearance)
         paginiert automatisch (25.000 Zeilen je Request)
  python3 tools/gsc_client.py inspect <siteUrl> <url>
      -> URL Inspection (Indexierungsstatus, Canonical laut Google, letzter Crawl)

siteUrl: Domain-Property als "sc-domain:example.de", URL-Property als "https://www.example.de/".
"""
import base64, csv, json, os, sys
from urllib.parse import quote

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
API = "https://searchconsole.googleapis.com"


DEFAULT_FILE = os.path.expanduser("~/.config/semsharks/gsc-service-account.json")


def load_credentials_info():
    """Reihenfolge: 1) Umgebungsvariable GSC_SERVICE_ACCOUNT_JSON_B64 (persistent, bevorzugt)
    2) Datei aus GSC_SERVICE_ACCOUNT_FILE  3) ~/.config/semsharks/gsc-service-account.json
    (außerhalb des Repos, chmod 600). Der Schlüsselinhalt wird nie ausgegeben."""
    raw = os.environ.get("GSC_SERVICE_ACCOUNT_JSON_B64")
    if raw:
        return json.loads(base64.b64decode(raw)), "env:GSC_SERVICE_ACCOUNT_JSON_B64"
    path = os.environ.get("GSC_SERVICE_ACCOUNT_FILE", DEFAULT_FILE)
    if os.path.exists(path):
        return json.load(open(path)), f"file:{path}"
    sys.exit("Kein GSC-Credential gefunden (GSC_SERVICE_ACCOUNT_JSON_B64 oder Datei außerhalb des Repos).")


def session():
    info, source = load_credentials_info()
    print(f"[credential source: {source}]", file=sys.stderr)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    creds.refresh(Request())
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {creds.token}"
    return s, info.get("client_email", "?")


def check():
    s, email = session()
    print("Service Account:", email)
    r = s.get(f"{API}/webmasters/v3/sites", timeout=60)
    r.raise_for_status()
    for e in r.json().get("siteEntry", []):
        print(f"  {e['siteUrl']:50} {e['permissionLevel']}")


def query(site, start, end, dims, out):
    s, _ = session()
    dims = [d for d in dims.split(",") if d]
    rows, start_row = [], 0
    while True:
        body = {"startDate": start, "endDate": end, "dimensions": dims,
                "rowLimit": 25000, "startRow": start_row, "dataState": "final"}
        r = s.post(f"{API}/webmasters/v3/sites/{quote(site, safe='')}/searchAnalytics/query", json=body, timeout=120)
        r.raise_for_status()
        batch = r.json().get("rows", [])
        rows += batch
        if len(batch) < 25000:
            break
        start_row += 25000
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(dims + ["clicks", "impressions", "ctr", "position"])
        for x in rows:
            w.writerow(x.get("keys", []) + [x["clicks"], x["impressions"], round(x["ctr"], 4), round(x["position"], 2)])
    print(f"{len(rows)} Zeilen -> {out}")


def inspect(site, url):
    s, _ = session()
    r = s.post(f"{API}/v1/urlInspection/index:inspect", json={"inspectionUrl": url, "siteUrl": site}, timeout=60)
    r.raise_for_status()
    res = r.json().get("inspectionResult", {}).get("indexStatusResult", {})
    for k in ("verdict", "coverageState", "indexingState", "robotsTxtState", "pageFetchState",
              "googleCanonical", "userCanonical", "lastCrawlTime", "sitemap"):
        print(f"{k:16} {res.get(k)}")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    {"check": check, "query": query, "inspect": inspect}[cmd](*args)
