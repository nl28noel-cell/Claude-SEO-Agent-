#!/usr/bin/env python3
"""Data-QA: vergleicht die (veröffentlichte) dashboard.json stichprobenartig mit den Rohquellen.

    python3 tools/qa_artifact_data.py <pfad/zur/dashboard.json> [client-slug]

Prüft GSC-KPIs (gesamt, letzte 28 Tage, Vorperiode), Query-Evidence der Opportunities, Semrush-Werte,
Findings, Change Log und Security (keine Credential-Felder)."""
import csv, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = sys.argv[1]; slug = sys.argv[2] if len(sys.argv) > 2 else "spreewald-luftaufnahmen"
d = json.load(open(path, encoding="utf-8"))
cdir = os.path.join(ROOT, "clients", slug)
gdir = os.path.join(cdir, "data", "gsc-2026-11")
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))
ok, bad = [], []
def check(name, cond, info=""): (ok if cond else bad).append(name + (f" — {info}" if info else ""))

# GSC Tageswerte
raw = rd(os.path.join(gdir, "gsc_date.csv"))
check("GSC days", len(raw) == len(d["gsc"]["daily"]), f"{len(raw)} vs {len(d['gsc']['daily'])}")
for key in ("clicks", "impressions"):
    r = sum(int(x[key]) for x in raw); s = sum(x[key] for x in d["gsc"]["daily"])
    check(f"GSC total {key}", r == s, f"raw {r} vs dashboard {s}")
    r28 = sum(int(x[key]) for x in raw[-28:]); s28 = sum(x[key] for x in d["gsc"]["daily"][-28:])
    check(f"GSC 28D {key}", r28 == s28, f"raw {r28} vs dashboard {s28}")
    rp = sum(int(x[key]) for x in raw[-56:-28]); sp = sum(x[key] for x in d["gsc"]["daily"][-56:-28])
    check(f"GSC prev-28D {key}", rp == sp, f"raw {rp} vs dashboard {sp}")
check("GSC last date", raw[-1]["date"] == d["gsc"]["last"] == d["meta"]["freshness"]["gsc_data_through"], raw[-1]["date"])

# Query-Evidence der Opportunities (16 Monate)
q = {x["query"]: x for x in rd(os.path.join(gdir, "gsc_query.csv"))}
n = 0
for o in d["opportunities"]:
    for e in o["gsc"]["queries"]:
        if e.get("missing"):
            check(f"{o['id']} '{e['query']}' missing also in raw", e["query"] not in q); continue
        r = q.get(e["query"]); n += 1
        check(f"{o['id']} '{e['query']}' clicks/impr", r and int(r["clicks"]) == e["clicks"] and int(r["impressions"]) == e["impressions"],
              f"raw {r and (r['clicks'], r['impressions'])} vs {(e['clicks'], e['impressions'])}")
check("opportunity GSC evidence rows compared", n > 0, str(n))

# Semrush
cache = {x["keyword"]: x for x in rd(os.path.join(ROOT, "data", "keyword-cache.csv"))}
m = 0
for o in d["opportunities"]:
    for k in o["semrush"]["keywords"]:
        if k["status"] == "ok":
            c = cache.get(k["keyword"]); m += 1
            check(f"{o['id']} semrush '{k['keyword']}'", c and int(c["volume"]) == k["volume"] and float(c["kd"]) == float(k["kd"]), f"{c and (c['volume'], c['kd'])} vs {(k['volume'], k['kd'])}")
check("semrush values compared", m > 0, str(m))

# State: Opportunities, Findings, Changes, Tasks
st = lambda n: json.load(open(os.path.join(cdir, "state", n + ".json"), encoding="utf-8"))
so = {o["id"]: o for o in st("opportunities")["opportunities"]}
check("opportunity ids", set(so) == {o["id"] for o in d["opportunities"]})
for o in d["opportunities"]:
    s = so[o["id"]]
    check(f"{o['id']} type/priority/status/fit", (s["type"], s["priority"], s["status"], s["business_fit"]) == (o["type"], o["priority"], o["status"], o["business_fit"]))
sf = {f["id"]: f for f in st("findings")["findings"]}
check("findings ids", set(sf) == {f["id"] for f in d["findings"]}, f"{len(sf)} findings")
for f in d["findings"]:
    check(f"{f['id']} severity/status/title", (sf[f["id"]]["severity"], sf[f["id"]]["status"], sf[f["id"]]["title"]) == (f["severity"], f["status"], f["title"]))
check("open findings KPI", d["health"]["open_findings"] == sum(1 for f in sf.values() if f["status"] == "open"), str(d["health"]["open_findings"]))
sc = {c["id"]: c for c in st("changes")["changes"]}
for c in d["changes"]:
    s = sc[c["id"]]
    check(f"{c['id']} checkpoints", [(x["label"], x["due"], x["status"]) for x in s["checkpoints"]] == [(x["label"], x["due"], x["status"]) for x in c["checkpoints"]])
    check(f"{c['id']} date/url/freeze", (s["date"], s["url"], s.get("freeze")) == (c["date"], c["url"], c.get("freeze")))
check("tasks", [t["id"] for t in st("agent_tasks")["tasks"]] == [t["id"] for t in d["tasks"] if not t.get("from_log") and not t.get("from_changes")])
# Research Log: Agent Activity „Completed“ aus denselben Events, keine Doppelpflege
rl = d.get("research_log", {})
check("research log: events + sources present", len(rl.get("events", [])) > 0 and len(rl.get("sources", [])) > 0)
check("research log: activity groups cover all events", sum(int(t["title"].split("(")[-1].split()[0]) for t in d["tasks"] if t.get("from_log")) == len(rl.get("events", [])))
check("research log: no credentials in sources", not re.search(r"private[_]key|client[_]email", json.dumps(rl)))
check("research log: semrush sources carry endpoint/units/mode", all(s["semrush"].get("endpoint") and "units" in s["semrush"] and s["semrush"].get("mode") for s in rl.get("sources", []) if s["type"] == "semrush"))
check("no 'running' task state", all(t["state"] != "running" for t in d["tasks"]))

# Security
txt = json.dumps(d)
for pat in [r"private[_]key", r"client[_]email", r"iam\.gserviceaccount\.com", r"BEGIN [A-Z ]*PRIVATE KEY", r"service_account", r"data_dir"]:
    check(f"no '{pat}' in data", not re.search(pat, txt))

# GA4 gegen Rohdaten
ga = os.path.join(cdir, "data", "ga4-2026-11")
if d.get("ga4", {}).get("available"):
    rawd = rd(os.path.join(ga, "ga4_date.csv"))
    for k_raw, k in (("sessions", "sessions"), ("totalUsers", "users"), ("engagedSessions", "engaged")):
        r = sum(int(x[k_raw]) for x in rawd); s_ = sum(x[k] for x in d["ga4"]["daily"])
        check(f"GA4 total {k}", r == s_, f"raw {r} vs dashboard {s_}")
    lo, hi = d["funnel"]["window"]
    iso = lambda x: f"{x[:4]}-{x[4:6]}-{x[6:]}"
    ld = rd(os.path.join(ga, "ga4_landing_date.csv"))
    org = sum(int(x["sessions"]) for x in ld if x["sessionSource"] != "tagassistant.google.com" and x["sessionDefaultChannelGroup"] == "Organic Search" and lo <= iso(x["date"]) <= hi)
    dash = next((c["sessions"] for c in d["ga4"]["channels_window"] if c["channel"] == "Organic Search"), None)
    check("GA4 organic sessions (window, ohne Test)", org == dash, f"raw {org} vs dashboard {dash}")
    conv = json.load(open(os.path.join(cdir, "state", "conversions.json"), encoding="utf-8"))
    ev = {e["event"]: e for e in conv["events"]}
    counted = lambda n, lvl, sub=None: n in ev and not ev[n].get("duplicate_of") and ev[n]["level"] == lvl and (sub is None or ev[n].get("subtype") == sub)  # noqa: E731
    cv = rd(os.path.join(ga, "ga4_conv_date.csv"))
    win = [x for x in cv if x["sessionSource"] != "tagassistant.google.com" and lo <= iso(x["date"]) <= hi]
    for sub, key in (("form_submission", "lead_form"), ("contact_action", "lead_contact")):
        r_ = sum(int(x["eventCount"]) for x in win if counted(x["eventName"], "lead", sub))
        d_ = sum(c[key] for c in d["ga4"]["channels_window"])
        check(f"GA4 {key} (window, ohne Test, ohne Duplikat)", r_ == d_, f"raw {r_} vs dashboard {d_}")
    rm = sum(int(x["sessions"]) for x in win if counted(x["eventName"], "micro"))
    dm = sum(c["micro_sessions"] for c in d["ga4"]["channels_window"])
    check("GA4 funnel-intent sessions (window)", rm == dm, f"raw {rm} vs dashboard {dm}")
    dup = sum(int(x["eventCount"]) for x in win if x["eventName"] == "click to chat")
    check("Duplikat 'click to chat' nicht in Leads", all(not e["counted"] for e in d["ga4"]["events"] if e["event"] == "click to chat"), str(dup))
    check("Heyflow-Interaktion nie als Lead", all(e["level"] == "micro" for e in d["ga4"]["events"] if e["event"].startswith("heyflow_") and e["event"] != "heyflow_formular_abgesendet"))
    tests = sum(int(x["eventCount"]) for x in cv if x["sessionSource"] == "tagassistant.google.com")
    check("GA4 test events excluded count", tests == d["ga4"]["quality"]["test_conversion_events_excluded"], str(tests))
    kw = rd(os.path.join(ga, "ga4_ads_keyword.csv"))
    rc = round(sum(float(x["advertiserAdCost"]) for x in kw if x["sessionGoogleAdsKeyword"] not in ("(not set)", "")), 2)
    check("Ads keyword-level cost", abs(rc - d["ads"]["totals"]["keyword_level_cost"]) < 0.05, f"raw {rc} vs {d['ads']['totals']['keyword_level_cost']}")
    disc = json.load(open(os.path.join(cdir, "data", "ads-2026-11", "ads_discovery.json"), encoding="utf-8"))
    check("Ads account status", d["ads"]["discovery"]["account"]["status"] == disc["account"]["status"] == "CANCELED")
    # Funnel: Cluster-Impressionen = Summe der Queries des Clusters
    for f in d["funnel"]["clusters"][:6]:
        s2 = sum(q["impressions"] for q in d["gsc"]["queries"] if q["cluster"] == f["cluster"])
        check(f"funnel {f['cluster']} GSC impressions", s2 == f["organic"]["impressions"], f"{s2} vs {f['organic']['impressions']}")
    # Datenschutz: keine anderen MCC-Kunden, keine Ersteller-E-Mail
    for bad_txt in ("FIRO", "K&M Cover", "9578550074", "3001574868", "9195667966", "creatorEmailAddress", "@gmx.de", "planning_customer_id"):
        check(f"no '{bad_txt}' in data", bad_txt not in txt)

print("PASS", len(ok)); print("FAIL", len(bad)); [print("  ✗", b) for b in bad]
sys.exit(1 if bad else 0)
