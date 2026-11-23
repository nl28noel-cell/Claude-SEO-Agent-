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


class ArtifactQA(unittest.TestCase):
    """Claude-Artifact-Fassung: Format, Freshness-Metadaten, Security-Scan, Approval-Mirror."""
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_artifact.py")], check=True, capture_output=True)
        cls.dist = os.path.join(ROOT, "dashboard", "artifact", "dist")
        cls.page = open(os.path.join(cls.dist, "index.html"), encoding="utf-8").read()
        cls.d = json.load(open(os.path.join(cls.dist, "data", SLUG, "dashboard.json"), encoding="utf-8"))

    def test_page_is_artifact_body_format(self):
        self.assertTrue(self.page.startswith("<title>"))
        for tag in ("<!doctype", "<html", "<head", "<body"):
            self.assertNotIn(tag, self.page.lower()[:400])
        self.assertNotIn('src="app.js"', self.page)
        self.assertLess(len(self.page.encode()), 1_000_000)

    def test_only_allowed_external_resources(self):
        for url in re.findall(r'(?:src|href)="(https?://[^"]+)"', self.page):
            self.assertTrue(url.startswith(("https://fonts.googleapis.com/", "https://www.spreewald-luftaufnahmen.de")), url)
        self.assertNotRegex(self.page, r"fetch\(\s*[\"'`]https?://")

    def test_routes_use_plain_hash_names(self):
        self.assertNotRegex(self.page, r'href="#/')
        for reserved in ("settings", "sidebar", "customize", "upgrade", "downloads"):
            self.assertNotIn(f'href="#{reserved}"', self.page)

    def test_no_inline_event_handlers(self):
        self.assertNotRegex(self.page, r"\son(click|change|load)=")

    def test_theme_tokens_light_and_dark(self):
        self.assertIn('@media (prefers-color-scheme: dark){:root:not([data-theme="light"])', self.page)
        self.assertIn(':root[data-theme="dark"]', self.page)
        self.assertRegex(self.page, r"body\{[^}]*background:var\(--bg\)")

    def test_freshness_metadata(self):
        f = self.d["meta"]["freshness"]
        for k in ("gsc_data_through", "gsc_fetched", "semrush_last_query", "website_crawl", "state_updated"):
            self.assertRegex(f[k] or "", r"^\d{4}-\d{2}-\d{2}$", k)
        self.assertEqual(f["gsc_data_through"], self.d["gsc"]["last"])
        self.assertTrue(self.d["meta"]["built_at"].endswith("Z"))

    def test_security_scan_clean_and_detects_secrets(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import build_artifact
        files = [os.path.join(dp, f) for dp, _, fs in os.walk(self.dist) for f in fs]
        self.assertEqual(build_artifact.scan(files), [])
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as t:
            t.write('{"client_email": "a@b-1.iam.gserviceaccount.com", "private_key": "-----BEGIN PRIVATE KEY-----"}')
        try:
            self.assertGreaterEqual(len(build_artifact.scan([t.name])), 3)
        finally:
            os.unlink(t.name)

    def test_ga4_ads_funnel_sections(self):
        g, a, f = self.d["ga4"], self.d["ads"], self.d["funnel"]
        self.assertTrue(g["available"])
        self.assertGreater(g["quality"]["test_sessions_excluded"], 0)
        self.assertTrue(all(not x["test"] or "tagassistant" in x["source_medium"] for x in g["source_medium"]))
        self.assertEqual(a["discovery"]["account"]["status"], "CANCELED")
        self.assertTrue(f["clusters"] and all("signals" in c for c in f["clusters"]))
        for k in ("ga4_data_through", "ga4_fetched", "ads_checked"):
            self.assertIn(k, self.d["meta"]["freshness"])

    def test_business_classification_semantics(self):
        evs = {e["event"]: e for e in self.d["ga4"]["events"]}
        self.assertEqual(evs["tel_klick"]["level"], "lead"); self.assertEqual(evs["tel_klick"]["subtype"], "contact_action")
        self.assertEqual(evs["kontakt_form_send"]["subtype"], "form_submission")
        self.assertEqual(evs["heyflow_interaktion"]["level"], "micro")
        self.assertEqual(evs["scroll"]["level"], "engagement"); self.assertEqual(evs["fb_klick"]["level"], "outbound")
        self.assertFalse(evs["click to chat"]["counted"])
        # Key Event (GA4-Konfiguration) beeinflusst die Klassifizierung nicht
        self.assertTrue(evs["heyflow_interaktion"]["key_event_now"]); self.assertEqual(evs["heyflow_interaktion"]["level"], "micro")
        self.assertFalse(evs["kontaktformular_gesendet"]["key_event_now"]); self.assertEqual(evs["kontaktformular_gesendet"]["level"], "lead")
        for c in self.d["ga4"]["channels_window"]:
            self.assertEqual(c["leads"], c["lead_form"] + c["lead_contact"])  # Micro wird nie addiert
        f = {x["id"]: x for x in self.d["findings"]}
        self.assertNotIn("Key Events als Business-KPI unbrauchbar", f["F-019"]["description"])
        self.assertIn("Tag-Assistant", f["F-019"]["title"])

    def test_planner_account_is_planner_only(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ads_client.py"), "query", "9578550074", "SELECT customer.id FROM customer", "/dev/null"],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nur als Keyword-Planner-Zugang", r.stdout + r.stderr)

    def test_keyword_planner_intentionally_not_used(self):
        kp = self.d["sources"]["keyword_planner"]
        self.assertEqual(kp["status"], "not_used")
        f = {x["id"]: x for x in self.d["findings"]}["F-023"]
        self.assertTrue(f["status"].startswith("closed"))
        self.assertNotIn("blocked", json.dumps(self.d["sources"]["google_ads"]["capabilities"]))
        self.assertFalse(any(t["id"] == "T-206" for t in self.d["tasks"]))
        cfg = json.load(open(os.path.join(ROOT, "config", "keyword_planner.json"), encoding="utf-8"))
        self.assertFalse(cfg["enabled"])
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ads_client.py"), "history", "planner", "x", "/dev/null"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn("bewusst deaktiviert", r.stdout + r.stderr)
        self.assertNotIn("Basic Access", open(os.path.join(ROOT, "dashboard", "public", "app.js"), encoding="utf-8").read())

    def test_workflow_queue_only_explicit_approvals(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import workflow
        docs = {
            "OPP-A": {},                                                                # kein Gate 1 → nichts tun
            "OPP-B": {"gate1": {"status": "approved"}, "production": {"status": "waiting"}},
            "OPP-C": {"gate1": {"status": "approved"}, "production": {"status": "draft_ready", "version": 1}, "review": {"status": "revision_requested", "comment": "x"}},
            "OPP-D": {"gate1": {"status": "approved"}, "production": {"status": "draft_ready"}, "gate2": {"status": "approved"}},
            "OPP-E": {"gate1": {"status": "approved"}, "production": {"status": "in_progress"}},
        }
        acts = {a["doc"]: a["action"] for a in workflow.actions(docs)}
        self.assertEqual(acts, {"OPP-B": "produce", "OPP-C": "revise"})
        # alle echten Opportunities starten ohne Workflow-Eintrag (= Zur Prüfung)
        wf = json.load(open(os.path.join(CDIR, "state", "workflow.json"), encoding="utf-8"))
        self.assertFalse([x for x in wf["items"] if not x.get("test") and (x.get("gate1") or {}).get("status") == "approved"])

    def test_workflow_render_html(self):
        import tempfile
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import workflow
        with tempfile.TemporaryDirectory() as t:
            src, out = os.path.join(t, "d.md"), os.path.join(t, "d.html")
            open(src, "w", encoding="utf-8").write("# H1\n\n## H2\nText **fett** <script>x</script>\n\n- a\n- b\n\n| A | B |\n|---|---|\n| 1 | 2 |\n")
            workflow.render(src, out); h = open(out, encoding="utf-8").read()
        for frag in ("<h1>H1</h1>", "<h2>H2</h2>", "<b>fett</b>", "<li>a</li>", "<th>A</th>", "<td>2</td>", "&lt;script&gt;"):
            self.assertIn(frag, h)

    def test_no_other_mcc_clients_or_personal_data(self):
        txt = json.dumps(self.d, ensure_ascii=False)
        for bad in ("FIRO", "K&M Cover", "9578550074", "3001574868", "9195667966", "creatorEmailAddress"):
            self.assertNotIn(bad, txt)

    def test_api_clients_are_read_only(self):
        ads = open(os.path.join(ROOT, "tools", "ads_client.py"), encoding="utf-8").read()
        self.assertNotRegex(ads, r'_post\(s, f?"[^"]*:mutate')
        self.assertIn("_FORBIDDEN", ads)
        ga = open(os.path.join(ROOT, "tools", "ga4_client.py"), encoding="utf-8").read()
        for verb in ("s.patch(", "s.delete(", "s.put(", ":create", "batchCreate"):
            self.assertNotIn(verb, ga)
        self.assertIn("analytics.readonly", ga)

    def test_decision_log_mirror_only_processed(self):
        import tempfile, shutil
        appr = os.path.join(CDIR, "state", "approvals.json"); backup = open(appr, encoding="utf-8").read()
        tmp = tempfile.mkdtemp()
        try:
            base = {"schema": 1, "client": SLUG, "item_title": "T", "gate": 1, "comment": "", "decided_at": "2026-11-23T10:00:00Z", "agent_processed_at": None, "agent_note": None}
            json.dump({**base, "item_id": "A", "decision": "approve", "agent_status": "processed"}, open(os.path.join(tmp, "x--A--g1--1.json"), "w"))
            json.dump({**base, "item_id": "B", "decision": "reject", "agent_status": "pending"}, open(os.path.join(tmp, "x--B--g1--2.json"), "w"))
            json.dump({**base, "item_id": "C", "decision": "publish_now", "agent_status": "processed"}, open(os.path.join(tmp, "x--C--g1--3.json"), "w"))
            subprocess.run([sys.executable, os.path.join(ROOT, "tools", "record_decisions.py"), tmp], check=True, capture_output=True)
            log = json.load(open(appr, encoding="utf-8"))["decision_log"]
            self.assertEqual([e["item_id"] for e in log], ["A"])
        finally:
            open(appr, "w", encoding="utf-8").write(backup); shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
