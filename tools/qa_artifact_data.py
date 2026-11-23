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
check("tasks", [t["id"] for t in st("agent_tasks")["tasks"]] == [t["id"] for t in d["tasks"]])
check("no 'running' task state", all(t["state"] != "running" for t in d["tasks"]))

# Security
txt = json.dumps(d)
for pat in [r"private_key", r"client_email", r"iam\.gserviceaccount\.com", r"BEGIN [A-Z ]*PRIVATE KEY", r"service_account", r"data_dir"]:
    check(f"no '{pat}' in data", not re.search(pat, txt))

print("PASS", len(ok)); print("FAIL", len(bad)); [print("  ✗", b) for b in bad]
sys.exit(1 if bad else 0)
