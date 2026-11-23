#!/usr/bin/env python3
"""Data- & Security-QA für das Dashboard (stdlib unittest).

    python3 -m unittest tests/test_dashboard.py -v
"""
import csv, datetime as dt, json, os, re, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = "spreewald-luftaufnahmen"
CDIR = os.path.join(ROOT, "clients", SLUG)
GDIR = os.path.join(CDIR, "data", "gsc-2026-11")
OUT = os.path.join(ROOT, "dashboard", "public", "data", SLUG, "dashboard.json")


def rows(name):
    return list(csv.DictReader(open(os.path.join(GDIR, name), encoding="utf-8")))


class DataQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_dashboard_data.py"), "--today", "2026-11-23"], check=True, capture_output=True)
        cls.d = json.load(open(OUT, encoding="utf-8"))

    def test_daily_totals_match_source(self):
        src = rows("gsc_date.csv")
        self.assertEqual(len(self.d["gsc"]["daily"]), len(src))
        self.assertEqual(sum(r["clicks"] for r in self.d["gsc"]["daily"]), sum(int(r["clicks"]) for r in src))
        self.assertEqual(sum(r["impressions"] for r in self.d["gsc"]["daily"]), sum(int(r["impressions"]) for r in src))

    def test_28d_kpi_window(self):
        src = sorted(rows("gsc_date.csv"), key=lambda r: r["date"])
        cur, prev = src[-28:], src[-56:-28]
        last = dt.date.fromisoformat(src[-1]["date"])
        self.assertEqual(cur[0]["date"], (last - dt.timedelta(days=27)).isoformat(), "28 consecutive days expected (no gaps)")
        c = sum(int(r["clicks"]) for r in cur); i = sum(int(r["impressions"]) for r in cur)
        d = self.d["gsc"]["daily"][-28:]
        self.assertEqual(c, sum(r["clicks"] for r in d)); self.assertEqual(i, sum(r["impressions"] for r in d))
        self.assertTrue(len(prev) == 28)

    def test_queries_pages_no_double_count(self):
        q = rows("gsc_query.csv")
        self.assertEqual(len(self.d["gsc"]["queries"]), len(q))
        self.assertEqual(len({x["query"] for x in self.d["gsc"]["queries"]}), len(q), "duplicate queries")
        self.assertEqual(sum(x["impressions"] for x in self.d["gsc"]["queries"]), sum(int(r["impressions"]) for r in q))
        seg = self.d["gsc"]["segment_totals"]
        self.assertEqual(sum(v["queries"] for v in seg.values()), len(q), "every query in exactly one segment")
        self.assertEqual(sum(v["impressions"] for v in seg.values()), sum(int(r["impressions"]) for r in q))

    def test_change_windows_are_90_days_and_disjoint(self):
        w = self.d["gsc"]["compare_window"]
        a0, a1 = map(dt.date.fromisoformat, w["current"]); b0, b1 = map(dt.date.fromisoformat, w["previous"])
        self.assertEqual((a1 - a0).days, 89); self.assertEqual((b1 - b0).days, 89); self.assertEqual((a0 - b1).days, 1)

    def test_query_change_matches_query_date(self):
        w = self.d["gsc"]["compare_window"]
        qd = rows("gsc_query_date.csv")
        target = "baudokumentation drohne"
        cur = sum(int(r["impressions"]) for r in qd if r["query"] == target and w["current"][0] <= r["date"] <= w["current"][1])
        x = next(q for q in self.d["gsc"]["queries"] if q["query"] == target)
        self.assertEqual(x["imp_90d"], cur)

    def test_opportunities_and_findings_from_state(self):
        st = json.load(open(os.path.join(CDIR, "state", "opportunities.json"), encoding="utf-8"))["opportunities"]
        self.assertEqual({o["id"] for o in self.d["opportunities"]}, {o["id"] for o in st})
        for o in self.d["opportunities"]:
            s = next(x for x in st if x["id"] == o["id"])
            self.assertEqual((o["type"], o["status"], o["priority"]), (s["type"], s["status"], s["priority"]))
        f = json.load(open(os.path.join(CDIR, "state", "findings.json"), encoding="utf-8"))["findings"]
        self.assertEqual(self.d["health"]["open_findings"], sum(1 for x in f if x["status"] == "open"))

    def test_opportunity_gsc_values_match_source(self):
        q = {r["query"]: r for r in rows("gsc_query.csv")}
        o = next(o for o in self.d["opportunities"] if o["id"] == "OPP-02")
        for g in o["gsc"]["queries"]:
            if not g.get("missing"):
                self.assertEqual(g["impressions"], int(q[g["query"]]["impressions"]))

    def test_semrush_values_from_cache(self):
        cache = {r["keyword"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "keyword-cache.csv"), encoding="utf-8")) if r["source"] == "semrush_phrase_these"}
        o = next(o for o in self.d["opportunities"] if o["id"] == "OPP-04")
        k = next(k for k in o["semrush"]["keywords"] if k["keyword"] == "drohnenvermessung")
        self.assertEqual(k["volume"], int(cache["drohnenvermessung"]["volume"]))

    def test_no_fake_running_state(self):
        self.assertFalse(any(t["state"] == "running" for t in self.d["tasks"]))

    def test_unmeasured_is_not_zero(self):
        for c in self.d["local"]["cells"]:
            if c["semrush"]["status"] != "ok":
                self.assertNotIn("volume", c["semrush"])
            self.assertIsNone(c["competition"])


class SecurityQA(unittest.TestCase):
    PATTERNS = [r"BEGIN PRIVATE KEY", r'"private_key"', r'"private_key_id"', r"service_account\"", r"semrtkn-", r"client_secret"]

    def test_public_dir_has_no_secrets(self):
        for dp, _, files in os.walk(os.path.join(ROOT, "dashboard", "public")):
            for fn in files:
                with open(os.path.join(dp, fn), encoding="utf-8", errors="ignore") as fh:
                    txt = fh.read()
                for p in self.PATTERNS:
                    self.assertIsNone(re.search(p, txt), f"{p} in {fn}")

    def test_git_tracked_files_have_no_secrets(self):
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        for fn in files:
            if fn.startswith("tests/"):
                continue
            with open(os.path.join(ROOT, fn), encoding="utf-8", errors="ignore") as fh:
                txt = fh.read()
            for p in self.PATTERNS[:3]:
                self.assertIsNone(re.search(p, txt), f"{p} in {fn}")
            self.assertFalse(re.search(r"(^|/)\.env($|\.)", fn), f".env tracked: {fn}")

    def test_build_does_not_read_credentials(self):
        src = open(os.path.join(ROOT, "tools", "build_dashboard_data.py"), encoding="utf-8").read()
        for p in ["GSC_SERVICE_ACCOUNT", ".config/semsharks", "gsc_client"]:
            self.assertNotIn(p, src)

    def test_gitignore_blocks_credentials(self):
        for fn in ["x-service-account.json", "claude-seo-agent-515611-28570fccb156.json", ".env", "secrets/a.json"]:
            r = subprocess.run(["git", "check-ignore", "-q", fn], cwd=ROOT)
            self.assertEqual(r.returncode, 0, f"not ignored: {fn}")


if __name__ == "__main__":
    unittest.main()
