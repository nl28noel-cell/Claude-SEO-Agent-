#!/usr/bin/env python3
"""Google Analytics 4 Client für den SEO Autopilot – AUSSCHLIESSLICH LESEND.

Authentifizierung: derselbe Service Account wie GSC/Ads (Credential-Lookup aus gsc_client.py),
Scope analytics.readonly. Genutzt werden nur Data API runReport/getMetadata und lesende Admin-API-Listen.
Keine Änderungen an Property, Events, Key Events, Links oder Tracking.

Befehle:
  python3 tools/ga4_client.py check                     -> Accounts/Properties, auf die der Service Account Zugriff hat
  python3 tools/ga4_client.py admin <property_id> <out.json>   -> Konfiguration (Streams, Key Events, Ads-Links, Retention) lesen
  python3 tools/ga4_client.py report <property_id> <start> <end> <dims> <metrics> <out.csv> [--events e1,e2]
  python3 tools/ga4_client.py baseline <property_id> <start> <end> <outdir>   -> Standard-Baseline-Datensätze (siehe BASELINE)
"""
import csv, json, os, sys

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gsc_client import load_credentials_info  # noqa: E402

DATA = "https://analyticsdata.googleapis.com/v1beta"
ADMIN = "https://analyticsadmin.googleapis.com/v1beta"
import re
CONV_PATTERN = re.compile(r"form|kontakt|contact|tel|phone|anruf|mail|chat|heyflow|lead|anfrage|generate_lead|purchase", re.I)

# name, dimensions, metrics, optional event filter ("key" = nur Key Events laut Admin-API)
BASELINE = [
    ("date", "date", "sessions,totalUsers,newUsers,engagedSessions,userEngagementDuration,eventCount,keyEvents,screenPageViews", None),
    ("date_channel", "date,sessionDefaultChannelGroup", "sessions,engagedSessions,userEngagementDuration,keyEvents", None),
    ("landing_channel", "landingPage,sessionDefaultChannelGroup", "sessions,totalUsers,engagedSessions,userEngagementDuration,keyEvents,screenPageViews", None),
    ("source_medium", "sessionSourceMedium,sessionDefaultChannelGroup", "sessions,totalUsers,engagedSessions,keyEvents", None),
    ("device_channel", "deviceCategory,sessionDefaultChannelGroup", "sessions,totalUsers,engagedSessions,userEngagementDuration,keyEvents", None),
    ("region", "region,city", "sessions,totalUsers,keyEvents", None),
    ("events_month", "yearMonth,eventName", "eventCount,totalUsers,keyEvents", None),
    ("keyevents_landing", "eventName,landingPage,sessionDefaultChannelGroup,yearMonth", "eventCount,keyEvents", "key"),
    ("keyevents_page", "eventName,pagePath", "eventCount", "key"),
    ("landing_date", "date,landingPage,sessionDefaultChannelGroup,sessionSource", "sessions,engagedSessions,userEngagementDuration,keyEvents", None),
    ("conv_date", "date,eventName,landingPage,sessionDefaultChannelGroup,sessionSource", "eventCount,keyEvents", "conv"),
    ("ads_month", "yearMonth,sessionGoogleAdsCampaignName", "advertiserAdImpressions,advertiserAdClicks,advertiserAdCost,sessions,keyEvents", None),
    ("ads_keyword", "sessionGoogleAdsKeyword", "advertiserAdClicks,advertiserAdCost,sessions,engagedSessions,keyEvents", None),
    ("ads_query", "sessionGoogleAdsQuery", "sessions,engagedSessions,keyEvents", None),
    ("ads_landing", "landingPage,sessionGoogleAdsCampaignName", "sessions,engagedSessions,userEngagementDuration,keyEvents", None),
]


def _session(scope="https://www.googleapis.com/auth/analytics.readonly"):
    info, source = load_credentials_info()
    print(f"[credential source: {source}]", file=sys.stderr)
    c = service_account.Credentials.from_service_account_info(info, scopes=[scope]); c.refresh(Request())
    s = requests.Session(); s.headers["Authorization"] = f"Bearer {c.token}"
    return s


def _get(s, url):
    r = s.get(url, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f"HTTP {r.status_code} {url}: {r.text[:300]}")
    return r.json()


def check():
    s = _session()
    for a in _get(s, ADMIN + "/accountSummaries").get("accountSummaries", []):
        print(f"Account {a['account']} · {a.get('displayName')}")
        for p in a.get("propertySummaries", []):
            print(f"   {p['property']} · {p.get('displayName')} · {p.get('propertyType')}")


def admin(pid, out):
    s = _session(); P = f"{ADMIN}/properties/{pid}"
    res = {"property": _get(s, P)}
    for ep in ("dataStreams", "keyEvents", "googleAdsLinks", "customDimensions", "customMetrics", "dataRetentionSettings"):
        try:
            res[ep] = _get(s, f"{P}/{ep}")
        except SystemExit as e:
            res[ep] = {"error": str(e)[:200]}
    for x in res.get("googleAdsLinks", {}).get("googleAdsLinks", []):
        x.pop("creatorEmailAddress", None)  # keine personenbezogenen Daten speichern
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✓ Admin-Konfiguration → {out}")
    return res


def report(s, pid, start, end, dims, metrics, events=None):
    body = {"dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": d} for d in dims], "metrics": [{"name": m} for m in metrics],
            "limit": 100000, "returnPropertyQuota": True, "keepEmptyRows": False}
    if events:
        body["dimensionFilter"] = {"filter": {"fieldName": "eventName", "inListFilter": {"values": events}}}
    rows, offset, meta = [], 0, {}
    while True:
        body["offset"] = offset
        r = s.post(f"{DATA}/properties/{pid}:runReport", json=body, timeout=120)
        if r.status_code != 200:
            raise SystemExit(f"HTTP {r.status_code} runReport {dims}: {r.text[:400]}")
        j = r.json()
        for x in j.get("rows", []):
            rows.append([v["value"] for v in x.get("dimensionValues", [])] + [v["value"] for v in x.get("metricValues", [])])
        meta = {"rowCount": j.get("rowCount", 0), "metadata": j.get("metadata", {}), "quota": j.get("propertyQuota", {})}
        offset += 100000
        if offset >= j.get("rowCount", 0):
            return rows, meta


def write(rows, cols, out):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(rows)


def baseline(pid, start, end, outdir):
    s = _session()
    cfg = admin(pid, os.path.join(outdir, "ga4_admin.json"))
    key_events = [k["eventName"] for k in cfg.get("keyEvents", {}).get("keyEvents", [])]
    # Conversion-Kandidaten: aktuelle Key Events + alle Events, die nach Kontakt/Formular/Telefon/Mail/Chat aussehen
    all_events = [r[0] for r in report(s, pid, start, end, ["eventName"], ["eventCount"])[0]]
    conv_candidates = sorted(set(key_events) | {e for e in all_events if CONV_PATTERN.search(e)})
    summary = {"property": pid, "conversion_candidates": conv_candidates, "start": start, "end": end, "key_events": key_events, "datasets": {}}
    for name, dims, mets, ev in BASELINE:
        d, m = dims.split(","), mets.split(",")
        evf = key_events if ev == "key" else conv_candidates if ev == "conv" else None
        rows, meta = report(s, pid, start, end, d, m, evf)
        write(rows, d + m, os.path.join(outdir, f"ga4_{name}.csv"))
        md = meta["metadata"]
        summary["datasets"][name] = {"rows": len(rows), "subject_to_thresholding": md.get("subjectToThresholding", False),
                                     "data_loss_other_row": md.get("dataLossFromOtherRow", False),
                                     "sampling": bool(md.get("samplingMetadatas"))}
        q = meta["quota"].get("tokensPerDay", {})
        print(f"✓ ga4_{name}.csv · {len(rows)} Zeilen · thresholding={md.get('subjectToThresholding', False)} · tokens/day left={q.get('remaining')}")
    json.dump(summary, open(os.path.join(outdir, "ga4_fetch_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "check":
        check()
    elif a[0] == "admin":
        admin(a[1], a[2])
    elif a[0] == "report":
        ev = a[a.index("--events") + 1].split(",") if "--events" in a else None
        d, m = a[4].split(","), a[5].split(",")
        rows, meta = report(_session(), a[1], a[2], a[3], d, m, ev); write(rows, d + m, a[6]); print(f"✓ {len(rows)} Zeilen → {a[6]}", meta["metadata"])
    elif a[0] == "baseline":
        baseline(a[1], a[2], a[3], a[4])
    else:
        sys.exit(__doc__)
