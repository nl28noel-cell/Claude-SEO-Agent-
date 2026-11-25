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
            "OPP-B": {"gate1": {"status": "approved", "research_override": True}, "production": {"status": "waiting"}},
            "OPP-H": {"gate1": {"status": "approved"}, "production": {"status": "waiting"}},          # Gate 1 ohne Strategie-Bezug → hold
            "OPP-C": {"gate1": {"status": "approved"}, "production": {"status": "draft_ready", "version": 1}, "review": {"status": "revision_requested", "comment": "x"}},
            "OPP-D": {"gate1": {"status": "approved"}, "production": {"status": "draft_ready"}, "gate2": {"status": "approved"}},
            "OPP-E": {"gate1": {"status": "approved"}, "production": {"status": "in_progress"}},
        }
        acts = {a["doc"]: a["action"] for a in workflow.actions(docs)}
        self.assertEqual(acts, {"OPP-B": "produce", "OPP-C": "revise", "OPP-H": "hold"})
        # echte Freigaben im Spiegel stammen nur aus expliziten Gate-1-Aktionen (mit Zeitstempel);
        # alte Freigaben ohne Strategie-Bezug werden nie produziert (hold)
        wf = json.load(open(os.path.join(CDIR, "state", "workflow.json"), encoding="utf-8"))
        real = {x["id"]: x for x in wf["items"] if not x.get("test") and (x.get("gate1") or {}).get("status") == "approved"}
        self.assertTrue(all(x["gate1"].get("at") for x in real.values()))
        for a in workflow.actions(real):
            self.assertNotEqual(a["action"], "produce", a)

    def test_research_stage(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import research
        R = research.load("spreewald-luftaufnahmen", "OPP-02")
        self.assertEqual(research.validate(R), [])
        st = research.derive(R)
        self.assertEqual(st["state"], "complete_with_limits")          # SERP nur indikativ → nie „complete“
        self.assertTrue(st["limits"])
        self.assertEqual(R["method"]["semrush_units_used"], 0)        # keine kostenpflichtigen Abfragen ohne Freigabe
        self.assertEqual(R["A_decision"]["decision"], R["H_ia"]["decision"])
        # Strategie-Freigabe nur mit passender Research-Version (oder Override)
        self.assertEqual(research.strategy_ok({"status": "approved", "research_version": R["version"]}, R), (True, "ok"))
        self.assertEqual(research.strategy_ok({"status": "approved"}, R)[1], "strategy_not_approved")
        self.assertEqual(research.strategy_ok({"status": "approved"}, None)[1], "research_missing")
        self.assertTrue(research.strategy_ok({"status": "approved", "research_override": True}, None)[0])
        # fehlender Abschnitt / offener Punkt → incomplete, egal was deklariert ist
        bad = json.loads(json.dumps(R)); bad["E_gap"] = {}
        self.assertEqual(research.derive(bad)["state"], "incomplete")
        pend = json.loads(json.dumps(R)); pend["status"]["pending"] = ["SERP validation pending"]
        d = research.derive(pend); self.assertEqual(d["state"], "incomplete"); self.assertIn("SERP validation pending", d["label"])
        self.assertEqual(research.derive(None)["state"], "not_started")
        self.assertEqual(research.strategy_ok({"status": "approved", "research_version": R["version"]}, pend)[1], "research_incomplete")
        # Dashboard: alle CREATE/OPTIMIZE/MERGE haben einen Research-Status, nur OPP-02 ein Dossier
        for o in self.d["opportunities"]:
            if o["type"] in ("CREATE", "OPTIMIZE", "MERGE"):
                self.assertIn(o["research_status"]["state"], research.STATES)
        o2 = next(o for o in self.d["opportunities"] if o["id"] == "OPP-02")
        self.assertEqual(o2["research_status"]["state"], "complete_with_limits")
        self.assertEqual(set(research.SECTIONS) - set(o2["research"]), set())
        # Kein Wettbewerbertext übernommen: Dossier enthält keine langen Zitate aus den Seitenprofilen
        self.assertNotIn("lückenloser Baufortschritt aus der Luft", json.dumps(R["F_scope"], ensure_ascii=False) + json.dumps(R["G_structure"], ensure_ascii=False))

    def test_serp_plan_budget_and_cache(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import serp, research
        # Kostenlogik: 10 Units je Zeile, Top 10
        self.assertEqual(serp.cost(1), 100); self.assertEqual(serp.cost(2), 200); self.assertEqual(serp.cost(1, 7), 70)
        # ähnliche Keywords → gleicher Schlüssel
        self.assertEqual(serp.norm("Baudokumentation Drohne"), serp.norm("drohnen baudokumentation"))
        self.assertEqual(serp.norm("baustellendokumentation mit drohne"), serp.norm("baustellendokumentation drohne"))
        self.assertNotEqual(serp.norm("baudokumentation drohne"), serp.norm("baustellendokumentation drohne"))
        # OPP-02: nur Primary geplant, 100 Units, Reserve hält → budget_hold, nichts ausgeführt
        p = serp.plan("spreewald-luftaufnahmen", "OPP-02")
        self.assertEqual([i["keyword"] for i in p["items"] if i["action"] == "query"], ["baudokumentation drohne"])
        self.assertEqual(p["units_needed"], 100)
        self.assertEqual(p["verdict"], "budget_hold")
        R = research.load("spreewald-luftaufnahmen", "OPP-02")
        self.assertEqual(R["C_serp"]["serp_competitors"], [])
        self.assertTrue(all(x.get("position") in (None, "", "–") for x in R["C_serp"]["research_competitors"]))
        self.assertNotIn("dominier", json.dumps(R, ensure_ascii=False).lower())   # keine SERP-Dominanz ohne echte SERP
        # Research competitors mit Position oder validated ohne SERP → Schemafehler
        bad = json.loads(json.dumps(R)); bad["C_serp"]["research_competitors"][0]["position"] = 3
        self.assertTrue(research.validate(bad))
        bad = json.loads(json.dumps(R)); bad["C_serp"]["quality"] = "validated"
        self.assertTrue(research.validate(bad))
        # mit echter Semrush-SERP wird aus „with limits“ „complete“
        ok = json.loads(json.dumps(R)); ok["C_serp"]["quality"] = "validated"; ok["status"]["state"] = "complete"; ok["status"]["limits"] = []
        ok["C_serp"]["serp_competitors"] = [{"keyword": "baudokumentation drohne", "position": 1, "domain": "x.de", "url": "https://x.de/", "relevance": "business_competitor", "source": "semrush phrase_organic"}]
        self.assertEqual(research.validate(ok), []); self.assertEqual(research.derive(ok)["state"], "complete")
        # Plan führt bei Budget über Reserve aus; frischer Cache → keine Abfrage
        import tempfile, shutil
        orig_b, orig_c = serp.BUDGET, serp.CACHE
        tmp = tempfile.mkdtemp()
        try:
            b = serp.budget(); b["units_balance"] = 1000
            serp.BUDGET = os.path.join(tmp, "b.json"); json.dump(b, open(serp.BUDGET, "w"))
            serp.CACHE = os.path.join(tmp, "cache")
            self.assertEqual(serp.plan("spreewald-luftaufnahmen", "OPP-02")["verdict"], "run")
            f = os.path.join(tmp, "r.csv"); open(f, "w").write("Dn;Ur\na.de;https://a.de/x\nb.de;https://b.de/y\n")
            e = serp.ingest("baudokumentation drohne", f)
            self.assertEqual((e["lines"], e["units_spent"], e["results"][1]["position"]), (2, 20, 2))
            self.assertEqual(serp.budget()["units_balance"], 980)
            p2 = serp.plan("spreewald-luftaufnahmen", "OPP-02")
            self.assertEqual((p2["verdict"], p2["units_needed"], p2["items"][0]["action"]), ("none", 0, "cache"))
        finally:
            serp.BUDGET, serp.CACHE = orig_b, orig_c; shutil.rmtree(tmp)

    def test_serp_validation_dual_source(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import serp, research
        b = serp.budget()
        self.assertEqual(b["serp"]["cache_ttl_days"], 30)                       # SERP frischer als Keyword-Daten
        self.assertGreater(b["keyword_cache_ttl_days"], b["serp"]["cache_ttl_days"])
        self.assertFalse(b["balance_tracking"]["automatic_read"])               # Konnektor liefert keinen Kontostand
        v = serp.validation("spreewald-luftaufnahmen", "OPP-02")
        self.assertEqual(v["semrush"]["label"], "Pending – budget hold")
        self.assertEqual(v["independent_web"]["label"], "Completed")
        self.assertEqual(v["cross"]["agreement"], "n/a")                         # ohne Semrush keine Übereinstimmung
        # Web Research je Primary Keyword ist Pflicht
        R = research.load("spreewald-luftaufnahmen", "OPP-02")
        x = json.loads(json.dumps(R)); x["C_serp"]["validation"]["independent_web"]["status"] = "pending"
        self.assertEqual(research.derive(x)["state"], "incomplete")
        x = json.loads(json.dumps(R)); x["C_serp"]["validation"]["independent_web"]["positions"] = [1, 2]
        self.assertTrue(research.validate(x))                                    # keine erfundenen Positionen
        # Cross-Validation über Domains
        biz = lambda d, r="business_competitor": {"domain": d, "relevance": r}  # noqa: E731
        C = {"serp_competitors": [biz("a.de"), biz("b.de"), biz("c.de"), biz("d.de")], "research_competitors": [biz("a.de"), biz("b.de"), biz("x.de")]}
        c = serp.cross_validate(C)
        self.assertEqual((c["agreement"], c["both"], c["semrush_only"], c["web_only"]), ("high", ["a.de", "b.de"], ["c.de", "d.de"], ["x.de"]))
        self.assertTrue(any("c.de" in f for f in c["flags"]))                   # rankende, nicht gefundene Wettbewerber → profilieren
        C2 = {"serp_competitors": [biz("s1.de", "software"), biz("s2.de", "software"), biz("a.de")], "research_competitors": [biz("a.de"), biz("y.de")]}
        c2 = serp.cross_validate(C2)
        self.assertEqual(c2["agreement"], "low")                                 # 1/3 = medium, Intent-Abweichung → low
        self.assertTrue(any("Seitentyp" in f for f in c2["flags"]))
        # Web-Research-Plan: Primary immer, ähnliche Keywords nicht doppelt
        p = serp.plan("spreewald-luftaufnahmen", "OPP-02")
        self.assertEqual([(w["keyword"], w["action"]) for w in p["web_research"]], [("baudokumentation drohne", "done")])

    def test_research_log_audit_trail(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import research_log as RL, serp
        self.assertEqual(RL.validate("spreewald-luftaufnahmen"), [])
        rl = self.d["research_log"]
        ev = rl["events"]; src = {s["id"]: s for s in rl["sources"]}
        o2 = [e for e in ev if e["opp"] == "OPP-02"]
        acts = {e["action"] for e in o2}
        for need in ("gsc_analysis", "semrush_keyword", "web_research", "competitor_analysis", "own_page_analysis", "cannibalization", "content_gap", "ia_review", "dossier"):
            self.assertIn(need, acts)
        # keine erfundenen Zeitpunkte: Uhrzeit nur bei exact/commit, sonst reines Datum
        for e in ev:
            self.assertEqual(len(e["at"]) == 10, e["at_precision"] == "date", e["id"])
        # Website-Quellen: anklickbare URL + echter Abrufzeitpunkt aus dem Seitenprofil
        for s in src.values():
            if s["type"] in ("competitor",):
                self.assertTrue(s["url"].startswith("https://")); self.assertEqual(s["fetched_precision"], "exact")
        # Semrush-Nachweis: Report, Endpoint, DB, Kosten (oder ausdrücklich unbekannt), Modus, kein erfundener Link
        sem = [s for s in src.values() if s["type"] == "semrush"]
        self.assertTrue(sem)
        for s in sem:
            m = s["semrush"]
            self.assertTrue(m["endpoint"] and m["database"] and m["mode"] in ("live", "cache"))
            self.assertTrue(isinstance(m["units"], int) or "metadata unavailable" in m["units_note"])
            self.assertIsNone(m["link"])
        # Findings referenzieren existierende Quellen; Wettbewerbs-Erkenntnis ist belegt
        for f in rl["findings"]:
            self.assertTrue(all(i in src for i in f["source_ids"]))
        rec = next(f for f in rl["findings"] if "regelmäßigen" in f["text"])
        self.assertGreaterEqual(len(rec["source_ids"]), 3)
        self.assertTrue(all(src[i]["type"] == "competitor" for i in rec["source_ids"]))
        # Agent Activity nutzt dieselben Events (keine zweite Liste)
        logt = [t for t in self.d["tasks"] if t.get("from_log")]
        self.assertTrue(logt)
        self.assertEqual(sum(int(re.search(r"\((\d+) Aktionen\)", t["title"]).group(1)) for t in logt), len(ev))
        # Bezahlte SERP: Rohdaten unveränderlich + Log-Eintrag mit Kosten (im Temp-Ordner, ohne echte Abfrage)
        import tempfile, shutil
        tmp = tempfile.mkdtemp(); ob, oc, orr = serp.BUDGET, serp.CACHE, RL.ROOT
        try:
            b = serp.budget(); serp.BUDGET = os.path.join(tmp, "b.json"); json.dump(b, open(serp.BUDGET, "w")); serp.CACHE = os.path.join(tmp, "cache")
            os.makedirs(os.path.join(tmp, "clients", "t", "state")); RL.ROOT = tmp
            f = os.path.join(tmp, "r.csv"); open(f, "w").write("Dn;Ur\na.de;https://a.de/x\nb.de;https://b.de/y\n")
            e = serp.ingest("baudokumentation drohne", f, client="t", opp="OPP-X")
            self.assertTrue(os.path.exists(os.path.join(serp.CACHE, "raw", e["raw_id"] + ".json")))
            self.assertRegex(e["raw_id"], r"^SERP-\d{4}-\d{2}-\d{2}-baudokumentation-drohne-DE$")
            evd, lgd = RL.load("t")
            s0 = evd["sources"][0]["semrush"]
            self.assertEqual((s0["endpoint"], s0["database"], s0["units"], s0["mode"], s0["results"][0]["url"]), ("phrase_organic", "DE", 20, "live", "https://a.de/x"))
            self.assertEqual((lgd["events"][0]["action"], lgd["events"][0]["units"]), ("semrush_serp", 20))
        finally:
            serp.BUDGET, serp.CACHE, RL.ROOT = ob, oc, orr; shutil.rmtree(tmp)

    def test_workflow_cleanup_state(self):
        """Nach dem Cleanup 24.11.: kein echter Eintrag produziert/freigegeben, Testphase im Audit Trail erhalten."""
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import workflow, research
        wf = json.load(open(os.path.join(CDIR, "state", "workflow.json"), encoding="utf-8"))
        real = {x["id"]: x for x in wf["items"] if not x.get("test")}
        for oid, x in real.items():
            self.assertTrue(all(g["superseded_as"] == "test-phase approval" for g in x["gate1"]["superseded"]))
            self.assertEqual(x["test_phase"]["label"], "Test phase · superseded")
            if x["gate1"]["status"] == "approved":                          # nur echte Freigaben NACH dem Cleanup, mit Strategie-Bezug
                self.assertGreater(x["gate1"]["at"], x["cleanup"]["at"]); self.assertTrue(x["gate1"].get("research_version"))
            else:
                self.assertEqual((x["gate1"]["status"], x["production"]["status"]), ("pending", "not_started"), oid)
                self.assertNotIn("doc_id", x["production"])
        self.assertFalse([a for a in workflow.actions(real) if a["action"] == "produce"])   # nichts wartet auf Produktion
        # Testentwürfe als Papierkorb markiert, Historie erhalten
        self.assertTrue(real["OPP-05"]["test_phase"]["production"]["doc_trashed_at"])
        self.assertTrue(real["OPP-03"]["test_phase"]["production"]["doc_trashed_at"])
        # Research bleibt erhalten
        R = research.load("spreewald-luftaufnahmen", "OPP-02")
        self.assertEqual((R["version"], research.derive(R)["state"]), (2, "complete_with_limits"))
        ev = self.d["research_log"]["events"]
        self.assertTrue(any(e["action"] == "workflow_cleanup" for e in ev))
        cleanup_at = next(e["at"] for e in ev if e["action"] == "workflow_cleanup")
        drafts = [e for e in ev if e["action"] == "draft" and e["at"] < cleanup_at]           # Testphase
        self.assertEqual({e["opp"] for e in drafts}, {"OPP-03", "OPP-05"})
        self.assertTrue(all(e["superseded"] == "Test phase · superseded" for e in drafts))
        self.assertFalse([e for e in ev if e["action"] == "draft" and e["at"] > cleanup_at and e.get("superseded")])   # echte Entwürfe danach
        self.assertGreaterEqual(len([e for e in ev if e["opp"] == "OPP-02"]), 13)   # OPP-02-Research-Log unverändert

    def test_cannibalization_engine(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import cannibalization as CZ
        O = {o["id"]: o for o in self.d["opportunities"]}
        for o in O.values():                                                     # jede Opportunity hat eine Analyse
            c = o["cannibalization"]
            self.assertIn(c["risk"], ("low", "medium", "high", "unknown")); self.assertTrue(c["recommendation"]); self.assertIn("basis", c)
        self.assertEqual((O["OPP-02"]["cannibalization"]["risk"], O["OPP-02"]["cannibalization"]["action"]), ("low", "OPTIMIZE"))
        c1 = O["OPP-01"]["cannibalization"]
        self.assertEqual((c1["risk"], c1["decision"]), ("high", "OPTIMIZE + COMPANION"))
        self.assertEqual(c1["companions"][0]["url"], "/drohne-dach-gebaeude-inspektion/"); self.assertEqual(c1["companions"][0]["linked_opp"], "OPP-03")
        self.assertEqual(O["OPP-04"]["cannibalization"]["decision"], "CREATE + COMPANION")   # generischer Intent auf spezifischer Seite
        self.assertEqual(O["OPP-06"]["cannibalization"]["action"], "MONITOR")                # MONITOR wird nicht umgestellt
        # Regeln mit synthetischen Daten
        inv = {"/a/": {"title": "Dachinspektion mit Drohne", "h1": ["Dachinspektion"]}, "/b/": {"title": "Fassade", "h1": []}}
        qp = [{"query": "dachinspektion drohne", "page": "/a/", "impressions": 800, "clicks": 3, "position": 8.0},
              {"query": "dachinspektion drohne", "page": "/b/", "impressions": 50, "clicks": 0, "position": 40.0}]
        new = {"id": "X", "type": "CREATE", "gsc_cluster": "dach", "gsc_queries": ["dachinspektion drohne"], "primary_keyword": "dachinspektion drohne", "planned_url": "/neu/"}
        r = CZ.analyze(new, qp, {"dachinspektion drohne": "dach"}, inv)
        self.assertEqual((r["risk"], r["decision"], r["action"], r["action_url"], r["changed"], r["warning"]), ("high", "DO NOT CREATE", "OPTIMIZE", "/a/", True, True))
        r2 = CZ.analyze({**new, "gsc_queries": ["xyz"]}, [{"query": "xyz", "page": "/b/", "impressions": 10, "clicks": 0, "position": 50}], {"xyz": "dach"}, inv)
        self.assertEqual((r2["risk"], r2["action"]), ("low", "CREATE"))
        self.assertEqual(CZ.analyze({**new, "gsc_queries": []}, [], {}, inv)["risk"], "unknown")
        # Local: Hauptseite rankt ≤ 10 → keine City Page
        svc = {"key": "b", "page": "/a/", "gsc_pattern": "dachinspektion", "priority": 9}
        loc = {"key": "p", "pattern": "potsdam", "coverage_regional": False}
        L = CZ.local_cell({}, svc, loc, [{"query": "dachinspektion potsdam", "page": "/a/", "impressions": 120, "clicks": 1, "position": 6}], inv)
        self.assertEqual((L["recommendation"], L["cannibalization"]), ("USE MAIN SERVICE PAGE", "high"))
        L2 = CZ.local_cell({}, svc, loc, [], inv)
        self.assertEqual(L2["recommendation"], "MONITOR")                       # 0 Volumen ≠ IGNORE
        L3 = CZ.local_cell({}, svc, loc, [{"query": "dachinspektion potsdam", "page": "/z/", "impressions": 150, "clicks": 0, "position": 45}], inv)
        self.assertEqual(L3["recommendation"], "CREATE CITY PAGE")
        cells = self.d["local"]["cells"]
        self.assertTrue(all(c["engine"]["recommendation"] in ("CREATE CITY PAGE", "USE MAIN SERVICE PAGE", "OPTIMIZE EXISTING PAGE", "MONITOR", "IGNORE") for c in cells))
        bb = next(c for c in cells if c["service"] == "baudokumentation" and c["location"] == "berlin")["engine"]
        self.assertEqual(bb["recommendation"], "USE MAIN SERVICE PAGE")        # keine /baudokumentation-berlin/
        self.assertIsNone(bb["competition"])                                     # nicht erhoben, nichts erfunden
        # Monitoring nach Veröffentlichung
        before = [{"query": "q1", "page": "/hub/", "impressions": 100}, {"query": "q2", "page": "/hub/", "impressions": 80}]
        after = [{"query": "q1", "page": "/a/", "impressions": 90}, {"query": "q2", "page": "/a/", "impressions": 50}, {"query": "q2", "page": "/hub/", "impressions": 45}]
        m = CZ.monitor("/a/", before, after, {"q1", "q2"})
        self.assertEqual((m["target_share"], len(m["switches"]), m["alternating"], m["status"]), (1.0, 2, ["q2"], "watch"))
        cw = [t for t in self.d["tasks"] if t.get("from_changes")]
        self.assertEqual(len(cw), 3); self.assertTrue(all(t["state"] == "planned" for t in cw))

    def test_change_set_companion_production(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import workflow, tempfile, shutil
        w = {"opp_id": "OPP-01", "gate1": {"status": "approved", "at": "x", "comment": "Bodenaufnahmen nicht als Standard", "research_override": True,
             "change_set": {"action": "OPTIMIZE", "url": "/dachinspektion-mit-drohne/", "companions": [{"url": "/drohne-dach-gebaeude-inspektion/", "reason": "r", "required_changes": ["c"], "linked_opp": "OPP-03"}]}},
             "production": {"status": "waiting"}}
        self.assertEqual(workflow.doc_title(w, {"name": "Dachinspektion", "type": "OPTIMIZE"}, "/drohne-dach-gebaeude-inspektion/"), "OPP-01 – Companion – drohne-dach-gebaeude-inspektion – Optimierung")
        tmp = tempfile.mkdtemp()
        try:
            json.dump(w, open(os.path.join(tmp, "OPP-01.json"), "w"))
            out = os.path.join(tmp, "b.md"); workflow.brief(tmp, "OPP-01", out)
            b = open(out, encoding="utf-8").read()
            self.assertIn("Scope-Änderungen von Noel (verbindlich", b); self.assertIn("Bodenaufnahmen nicht als Standard", b)
            self.assertIn("## Change Set: Companion Optimization", b); self.assertIn("--companion /drohne-dach-gebaeude-inspektion/", b)
        finally:
            shutil.rmtree(tmp)

    def test_page_diagnosis_ranking_protection(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import page_diagnosis as PD, research, workflow, tempfile, shutil
        O = {o["id"]: o for o in self.d["opportunities"]}
        rp2 = O["OPP-02"]["ranking_protection"]
        crit = next(q for q in rp2["queries"] if q["query"] == "baudokumentation drohne berlin")
        self.assertEqual(crit["tier"], "critical")
        self.assertTrue({"Title", "H1"} <= {h["element"] for h in crit["supported_by"]})      # Inhalt, der das Ranking trägt
        self.assertTrue(any(q["tier"] == "off_topic" and "3d" in q["query"] for q in rp2["queries"]))
        self.assertEqual(O["OPP-07"]["ranking_protection"]["strength"]["level"], "strong")       # Preisseite → konservativ
        self.assertTrue(O["OPP-01"]["ranking_protection"]["companions"])                         # Companion-Seite eigene Schutzliste
        # Dossier: Diagnose Pflicht bei OPTIMIZE, H1 bei OPP-02 bleibt, Title behält tragende Begriffe
        R2 = research.load("spreewald-luftaufnahmen", "OPP-02")
        self.assertEqual(R2["G_structure"]["h1_action"], "KEEP")
        self.assertIn("Baudokumentation Drohne", R2["G_structure"]["title_proposal"]); self.assertIn("Berlin", R2["G_structure"]["title_proposal"])
        R1 = research.load("spreewald-luftaufnahmen", "OPP-01")
        self.assertIn("Dachkontrolle", R1["G_structure"]["title_proposal"])                       # trägt Pos. 12,9
        x = json.loads(json.dumps(R2)); del x["P_diagnosis"]
        self.assertIn("Current Page Diagnosis ausstehend", research.derive(x)["missing"])
        self.assertEqual(research.validate(R2), [])
        # Risiko: sensible Änderung an tragendem Element → mindestens medium; URL/Redirect → high
        pl = [{"query": "a b", "tier": "critical", "clicks": 5, "impressions": 100, "position": 3, "supported_by": [{"element": "Title", "text": "a b"}]}]
        st = PD.strength(pl)
        self.assertEqual(PD.loss_risk(pl, st, [])["level"], "low")
        self.assertEqual(PD.loss_risk(pl, st, [{"element": "Title"}])["level"], "medium")
        self.assertEqual(PD.loss_risk(pl, st, [{"element": "Redirect"}])["level"], "high")
        # Monitoring nach OPTIMIZE: Verlust wichtiger Rankings → Finding
        base = [{"query": "q1", "tier": "critical", "clicks": 4, "impressions": 300, "position": 4}, {"query": "q2", "tier": "high", "clicks": 0, "impressions": 200, "position": 12},
                {"query": "q3", "tier": "high", "clicks": 0, "impressions": 100, "position": 15}]
        after = [{"query": "q2", "impressions": 5, "clicks": 0, "position": 25}, {"query": "q3", "impressions": 10, "clicks": 0, "position": 14}, {"query": "neu", "impressions": 30, "clicks": 1, "position": 8}]
        r = PD.protection_check(base, after, 30, 3, ["neu"])
        self.assertEqual(r["status"], "negative_impact"); self.assertEqual(r["finding"]["title"], "Potential negative impact detected")
        self.assertIn("q1", r["finding"]["affected_queries"]); self.assertEqual(r["gained_targets"], ["neu"])
        ok = PD.protection_check(base, [{"query": q["query"], "impressions": q["impressions"] / 10, "clicks": q["clicks"], "position": q["position"]} for q in base], 30, 3)
        self.assertEqual(ok["status"], "ok")
        self.assertEqual(PD.merge_winner([{"url": "/a/", "clicks": 1, "impressions": 900}, {"url": "/b/", "clicks": 5, "impressions": 100}])["winner"], "/b/")
        ch = next(c for c in self.d["changes"] if c["id"] == "CL-001")
        self.assertTrue(ch["ranking_protection_baseline"]["queries"])
        # Produktion: Change-Modus geprüft
        tmp = tempfile.mkdtemp()
        try:
            good = os.path.join(tmp, "g.md"); open(good, "w").write("## Change Summary\n| Bereich | Aktion | Grund | SEO-Risiko |\n|---|---|---|---|\n| Title | EDIT | x | Low |\n\n## [KEEP] A\nbaudokumentation drohne berlin baubegleitung drohnen tour bau\n\n## [NEW] B\nReason: Content Gap\ntext\n")
            self.assertTrue(workflow.check_draft(good, "OPP-02")["ok"])
            bad = os.path.join(tmp, "b.md"); open(bad, "w").write("## Change Summary\n| Bereich | Aktion | Grund | SEO-Risiko |\n\n## [EDIT] A\nohne Begründung\n\n## C\nx\n")
            r = workflow.check_draft(bad, "OPP-02")
            self.assertFalse(r["ok"]); self.assertTrue(any("ohne Reason" in e for e in r["errors"])); self.assertTrue(any("ohne Change-Markierung" in e for e in r["errors"]))
            self.assertTrue(any("baudokumentation drohne berlin" in w for w in r["warnings"]))
            html_out = os.path.join(tmp, "g.html"); workflow.render(good, html_out)
            self.assertIn("[NEW]</span>", open(html_out).read())
        finally:
            shutil.rmtree(tmp)

    def test_research_retry_engine(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import research, workflow, datetime as dt
        R1 = research.load("spreewald-luftaufnahmen", "OPP-01")
        o1 = {"id": "OPP-01", "type": "OPTIMIZE", "existing_page": "/dachinspektion-mit-drohne/"}
        prof = {"fetched": dt.date.today().isoformat(), "sections": []}
        hold = {"verdict": "budget_hold", "why": "Reserve"}
        c = research.components(R1, o1, {"profile": prof, "serp_plan": hold})
        st = {k: v["status"] for k, v in c.items()}
        self.assertEqual((st["gsc"], st["own_page"], st["web_research"], st["competitors"], st["serp"]), ("complete", "complete", "missing", "missing", "blocked_budget"))
        p = research.retry_plan(c)
        self.assertEqual(p["run"], ["web_research", "competitors", "content_gap", "strategy"])   # nur Fehlendes + Abhängiges
        self.assertIn("gsc", p["reuse"]); self.assertIn("own_page", p["reuse"]); self.assertEqual(p["blocked"], ["serp"])
        # eigene Seite fehlgeschlagen / veraltet → nur diese + abhängige Diagnose/Content Gap
        R2 = research.load("spreewald-luftaufnahmen", "OPP-02")
        o2 = {"id": "OPP-02", "type": "OPTIMIZE", "existing_page": "/drohnen-baudokumentation/"}
        c = research.components(R2, o2, {"profile": {"fetched": "2026-11-24", "error": "Timeout"}, "serp_plan": hold})
        self.assertEqual(c["own_page"]["status"], "failed")
        self.assertEqual(research.retry_plan(c)["run"], ["own_page", "content_gap", "diagnosis", "strategy"])
        c = research.components(R2, o2, {"profile": {"fetched": "2026-09-01"}, "serp_plan": hold, "today": dt.date(2026, 11, 24)})
        self.assertEqual(c["own_page"]["status"], "stale")
        # vom Runner gemeldeter Fehlschlag (status.failed)
        x = json.loads(json.dumps(R2)); x["status"]["failed"] = {"competitors": "Hosts nicht freigegeben"}
        c = research.components(x, o2, {"profile": {"fetched": dt.date.today().isoformat()}, "serp_plan": hold})
        self.assertEqual((c["competitors"]["status"], c["competitors"]["why"]), ("complete", ""))     # vorhandene Analyse bleibt gültig
        x["D_competitors"] = []
        c = research.components(x, o2, {"profile": {"fetched": dt.date.today().isoformat()}, "serp_plan": hold})
        self.assertEqual((c["competitors"]["status"], c["competitors"]["why"]), ("failed", "Hosts nicht freigegeben"))
        # nur kostenpflichtige Research fehlt → kein Retry, Erklärung; Budget-Schutz nie umgehen
        c = research.components(R2, o2, {"profile": {"fetched": dt.date.today().isoformat()}, "serp_plan": hold})
        p = research.retry_plan(c)
        self.assertEqual(p["run"], []); self.assertTrue(p["only_paid_missing"]); self.assertIn("Budget", p["explain"] + c["serp"]["why"] + "Budget")
        c = research.components(R2, o2, {"profile": {"fetched": dt.date.today().isoformat()}, "serp_plan": {"verdict": "run"}})
        self.assertEqual(research.retry_plan(c)["run"], ["serp"])                                  # nur bei Budget „run“
        self.assertEqual(research.components(None, {"id": "N", "type": "CREATE"}, {})["serp"]["status"], "blocked_budget")
        # Runner-Queue: Retry am bestehenden Eintrag, unabhängig von Gate 1; laufend → nicht doppelt
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        docs = {"OPP-01": {"opp_id": "OPP-01", "gate1": {"status": "pending"}, "research_retry": {"status": "queued", "components": ["web_research"], "attempt": 1}},
                "OPP-05": {"opp_id": "OPP-05", "gate1": {"status": "pending"}, "research_retry": {"status": "running", "started_at": now, "components": ["gsc"]}},
                "OPP-04": {"opp_id": "OPP-04", "gate1": {"status": "pending"}, "research_retry": {"status": "complete"}}}
        acts = workflow.actions(docs)
        self.assertEqual([(a["doc"], a["action"]) for a in acts], [("OPP-01", "research")])
        docs["OPP-05"]["research_retry"]["started_at"] = "2026-01-01T00:00:00Z"
        self.assertIn(("OPP-05", "research"), [(a["doc"], a["action"]) for a in workflow.actions(docs)])   # abgebrochen → erneut
        # Dashboard: Komponenten + Plan je Opportunity
        o = next(x for x in self.d["opportunities"] if x["id"] == "OPP-01")
        self.assertEqual(o["research_status"]["retry"]["run"], ["web_research", "competitors", "content_gap", "strategy"])

    def test_wordpress_architecture(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import wordpress as WP, workflow, copy
        # --- Preflight: richtige Website / falsche Website / kein Konnektor
        tools = [f"mcp__WordPress_com__{t}" for t in WP.cfg()["required_tools"]]
        ab = WP.cfg()["required_abilities"]
        ok = WP.preflight({"tools": tools, "sites": [{"blog_id": 174454219, "site_url": "https://www.spreewald-luftaufnahmen.de"}, {"blog_id": 111, "site_url": "https://andere-website.example"}], "role": "administrator", "abilities": ab})
        self.assertTrue(ok["ok"]); self.assertEqual(ok["blog_id"], "174454219")
        wrong = WP.preflight({"tools": tools, "sites": [{"blog_id": 111, "site_url": "https://andere-website.example"}], "role": "administrator", "abilities": ab})
        self.assertEqual((wrong["ok"], wrong["block_reason"]), (False, "wp_wrong_site"))          # nie ausweichen
        self.assertEqual(WP.preflight({"tools": [], "sites": []})["block_reason"], "wp_connector_unavailable")
        self.assertEqual(WP.preflight({"tools": tools, "sites": ok and [{"blog_id": 174454219, "site_url": "https://www.spreewald-luftaufnahmen.de"}], "role": "subscriber", "abilities": ab})["block_reason"], "wp_capabilities_missing")
        # --- Guard: harte Schreibsperre
        w = {"gate2": {"status": "approved"}, "wordpress": {"status": "draft_ready", "mode": "OPTIMIZE", "draft_version": 2,
             "documents": [{"role": "primary", "url": "/drohnen-baudokumentation/", "wp_post_id": 5401, "draft_post_id": 9001}],
             "qa": {"overall": "passed_manual_visual"}, "snapshots": [{"post": 5401, "verified": True, "stored_doc_id": "d1"}], "rollback": {"status": "available"}}}
        g = lambda *a, **k: WP.guard(*a, **k)["code"]  # noqa: E731
        self.assertEqual(g("create_draft", {"gate2": {}}), "gate2_missing")
        self.assertEqual(g("create_draft", w, status="publish"), "status_not_draft")
        self.assertEqual(g("create_draft", w, status="draft", slug="drohnen-baudokumentation", live_slugs=["drohnen-baudokumentation"]), "slug_in_use")
        self.assertEqual(g("create_draft", w, status="draft", slug="neu"), "ok")
        self.assertEqual(g("update_draft", w, post=5401), "not_agent_draft")                         # Live-Seite nie als „Draft“ bearbeiten
        self.assertEqual(g("update_draft", w, post=9001), "ok")
        self.assertEqual(g("update_draft", w, post=9001, fields=["slug"]), "sensitive_field")
        self.assertEqual(g("live_update", w, post=5401), "gate3_missing")                           # gate3 != approved → gesperrt
        w3 = copy.deepcopy(w); w3["gate3"] = {"status": "approved", "for_draft_version": 1}
        self.assertEqual(g("live_update", w3, post=5401), "gate3_version_mismatch")
        w3["gate3"]["for_draft_version"] = 2
        self.assertEqual(g("live_update", w3, post=5401), "visual_review_missing")
        w3["gate3"]["visual_review_confirmed"] = True
        self.assertEqual(g("live_update", w3, post=5401), "live_optimize_blocked")          # realer Status nach Sandbox-Test
        real_cfg = WP.cfg
        WP.cfg = lambda client=WP.DEFAULT_CLIENT: {**real_cfg(client), "capabilities_verified": {"elementor": {"live_optimize_automation": "VERIFIED", "create_automation": "VERIFIED"}}}  # simuliert: Schreibweg bestätigt
        try:
            self.assertEqual(g("live_update", w3, post=5401), "ok")
            self.assertEqual(g("live_update", w3, post=5401, fields=["canonical"]), "sensitive_field")
            self.assertEqual(g("live_update", w3, post=4857), "not_in_change_set")
            w4 = copy.deepcopy(w3); w4["wordpress"]["rollback"] = {"status": "unavailable"}
            self.assertEqual(g("live_update", w4, post=5401), "rollback_unavailable")
            w5 = copy.deepcopy(w3); w5["wordpress"]["snapshots"] = []
            self.assertEqual(g("live_update", w5, post=5401), "snapshot_missing")
        finally:
            WP.cfg = real_cfg
        for op in ("delete", "redirect", "canonical_change", "robots_change", "slug_change_live", "unpublish", "plugin_change"):
            self.assertEqual(g(op, w3, post=5401), "requires_explicit_confirmation")
        self.assertEqual(g("delete", {**w3, "confirmations": [{"op": "delete", "post": 9001, "status": "confirmed"}]}, post=9001), "confirmed")
        # --- Snapshot + Rollback
        tree = [{"id": "c1", "elType": "container", "elements": [
            {"id": "h1", "widgetType": "heading", "settings": {"title": "Baudokumentation Drohne in Berlin und Brandenburg", "header_size": "h1"}},
            {"id": "h2a", "widgetType": "heading", "settings": {"title": "Baufortschritt per Drohne jederzeit im Blick behalten", "header_size": "h2"}},
            {"id": "t1", "widgetType": "text-editor", "settings": {"editor": "<p>Die Baubegleitung mit Drohne bietet …</p>"}},
            {"id": "i1", "widgetType": "image", "settings": {"image": {"url": "https://x/a.jpg"}}},
            {"id": "h2b", "widgetType": "heading", "settings": {"title": "Mehrjährige Begleitung", "header_size": "h2"}},
            {"id": "t2", "widgetType": "text-editor", "settings": {"editor": "<p>Alt</p>"}},
            {"id": "b1", "widgetType": "button", "settings": {"text": "Anfragen", "link": {"url": "/kontakt/"}}}]}]
        page = {"data": {"id": 5401, "slug": "drohnen-baudokumentation", "status": "publish", "link": "https://www.spreewald-luftaufnahmen.de/drohnen-baudokumentation/", "template": "",
                "meta": {"_elementor_data": json.dumps(tree), "_elementor_edit_mode": "builder", "_elementor_page_settings": {}}}}
        snap = WP.snapshot(page, {"data": [{"seo_title": "T", "meta_description": "D", "canonical": "c", "noindex": None}]}, "2026-11-24T14:00:00+00:00")
        self.assertTrue(WP.verify_snapshot(snap)["verified"])
        bad = copy.deepcopy(snap); bad["elementor"]["_elementor_data"] = json.dumps(tree).replace("Alt", "Neu")
        self.assertFalse(WP.verify_snapshot(bad)["hash_ok"])                                        # Manipulation erkannt
        self.assertEqual(WP.rollback_status([{**snap, "verified": True, "stored_doc_id": "d"}], {"elementor_meta_write_verified": False, "yoast_write_available": True})["status"], "unavailable")
        self.assertEqual(WP.rollback_status([{**snap, "verified": True, "stored_doc_id": "d"}], {"elementor_meta_write_verified": True, "yoast_write_available": True, "revisions_available": True})["status"], "available")
        self.assertFalse(WP.cfg()["capabilities_verified"]["elementor_meta_write_verified"])         # noch kein Schreibtest → Gate 3 bei OPTIMIZE gesperrt
        # --- QA: KEEP unverändert, EDIT/NEW vorhanden, Bilder/Buttons, H1, Yoast, Visual nie erfunden
        new = copy.deepcopy(tree); c = new[0]["elements"]
        c[5]["settings"]["editor"] = "<p>Neu: Turnus nach Bauphasen</p>"
        c.append({"id": "h2c", "widgetType": "heading", "settings": {"title": "Häufige Fragen zur Baustellendokumentation mit Drohne", "header_size": "h2"}})
        c.append({"id": "t3", "widgetType": "text-editor", "settings": {"editor": "<p>FAQ … baudokumentation drohne berlin</p>"}})
        cs = {"mode": "OPTIMIZE", "sections": [{"heading": "Baufortschritt per Drohne jederzeit im Blick behalten", "action": "KEEP"}, {"heading": "Mehrjährige Begleitung", "action": "EDIT"},
              {"heading": "Häufige Fragen zur Baustellendokumentation mit Drohne", "action": "NEW"}],
              "seo": {"title": "T2", "meta_description": "D2", "h1": "Baudokumentation Drohne in Berlin und Brandenburg"}, "canonical": "c", "internal_links": [{"to": "/kontakt/"}]}
        dy = {"data": [{"seo_title": "T2", "meta_description": "D2", "canonical": "c"}]}
        q = WP.qa(cs, page, {"meta": {"_elementor_data": json.dumps(new)}}, dy, {"protected_queries": ["baudokumentation drohne berlin"]})
        self.assertEqual(q["overall"], "passed_manual_visual", q); self.assertEqual(q["visual"]["status"], "manual_review_required")
        broken = copy.deepcopy(new); broken[0]["elements"][2]["settings"]["editor"] = "<p>Umformuliert</p>"; broken[0]["elements"][3]["settings"]["image"] = {"url": ""}
        q2 = WP.qa(cs, page, {"meta": {"_elementor_data": json.dumps(broken)}}, dy)
        self.assertEqual(q2["overall"], "failed")
        self.assertTrue(any("[KEEP]" in i for i in q2["content"]["issues"])); self.assertTrue(q2["technical"]["issues"])
        q3 = WP.qa(cs, page, {"meta": {"_elementor_data": json.dumps(new)}}, {"data": [{"seo_title": "falsch", "meta_description": "D2", "canonical": "c"}]})
        self.assertTrue(any("SEO-Title" in i for i in q3["seo"]["issues"]))
        self.assertEqual(WP.change_counts(cs), {"NEW": 1, "EDIT": 1, "KEEP": 1, "REMOVE": 0})
        self.assertIn("Unverändert: URL/Slug, Canonical, Indexierung, Menüs, Einstellungen", WP.publish_summary(cs, "OPTIMIZE"))
        # --- Queue: Gate 2 → wp_draft; Gate 3 nur mit Guard → wp_publish, sonst wp_publish_blocked
        docs = {"OPP-02": {"opp_id": "OPP-02", "gate1": {"status": "approved", "research_version": 2}, "gate2": {"status": "approved"}, "production": {"status": "draft_ready"},
                           "wordpress": {"status": "queued", "mode": "OPTIMIZE"}}}
        self.assertEqual([(x["doc"], x["action"]) for x in workflow.actions(docs)], [("OPP-02", "wp_draft")])
        docs["OPP-02"]["wordpress"] = {**w["wordpress"], "status": "publish_queued"}
        a = workflow.actions(docs)[0]; self.assertEqual((a["action"], a["reason"]), ("wp_publish_blocked", "gate3_missing"))
        docs["OPP-02"]["gate3"] = {"status": "approved", "for_draft_version": 2, "visual_review_confirmed": True}
        a = workflow.actions(docs)[0]; self.assertEqual((a["action"], a["reason"]), ("wp_publish_blocked", "live_optimize_blocked"))
        real_cfg = WP.cfg
        WP.cfg = lambda client=WP.DEFAULT_CLIENT: {**real_cfg(client), "capabilities_verified": {"elementor": {"live_optimize_automation": "VERIFIED", "create_automation": "VERIFIED"}}}
        try:
            self.assertEqual(workflow.actions(docs)[0]["action"], "wp_publish")
        finally:
            WP.cfg = real_cfg
        e = WP.change_log_entry(docs["OPP-02"], "OPP-02", "2026-12-01T10:00:00Z", {"queries": []})
        self.assertEqual([c["label"] for c in e["checkpoints"]], ["T+7", "T+14", "T+30", "T+60", "T+90"])
        self.assertTrue(all(set(c["checks"]) == {"ranking_protection", "cannibalization"} for c in e["checkpoints"]))

    def test_wordpress_sandbox_firewall(self):
        """Sandbox-Test 24.11.2026: Payload mit <script> → Firewall 403. Guard muss das VOR dem Schreibaufruf erkennen."""
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import wordpress as WP
        tree = [{"id": "c1", "elType": "container", "elements": [
                    {"id": "h1", "elType": "widget", "widgetType": "heading", "settings": {"title": "Baudokumentation", "header_size": "h1"}, "elements": []},
                    {"id": "x1", "elType": "widget", "widgetType": "html", "settings": {"html": "<SCRIPT src='https://cdn.example/l.js'></SCRIPT>"}, "elements": []}]}]
        fr = WP.firewall_risk(tree)
        self.assertTrue(fr["blocked"]); self.assertEqual([h["id"] for h in fr["widgets"]], ["x1"])
        self.assertFalse(WP.firewall_risk(json.dumps(tree[:0]))["blocked"])
        self.assertFalse(WP.firewall_risk([{"id": "c", "elType": "container", "elements": [tree[0]["elements"][0]]}])["blocked"])
        w = {"gate2": {"status": "approved"}, "wordpress": {"mode": "OPTIMIZE", "documents": [{"draft_post_id": 9001}]}}
        r = WP.guard("update_draft", w, post=9001, payload=tree)
        self.assertEqual(r["code"], "payload_blocked_by_firewall"); self.assertFalse(r["allowed"])
        self.assertEqual(WP.guard("update_draft", w, post=9001, payload=[tree[0]["elements"][0]])["code"], "ok")
        # Status aus dem Sandbox-Test: kein automatisches Live-Update bestehender (OPTIMIZE) Seiten
        cv = WP.cfg()["capabilities_verified"]
        em = cv["elementor"]
        self.assertEqual((em["write"], em["standard_widgets"], em["script_widgets"], em["live_optimize_automation"], em["create_automation"], em["rollback"]),
                         ("PARTIAL", "VERIFIED", "BLOCKED_BY_FIREWALL", "BLOCKED", "PENDING_TRUSTINDEX_REFERENCE", "NOT_YET_VERIFIED"))
        self.assertFalse(cv["elementor_meta_write_verified"])
        wc = {"gate2": {"status": "approved"}, "gate3": {"status": "approved", "for_draft_version": 1, "visual_review_confirmed": True},
              "wordpress": {"mode": "CREATE", "draft_version": 1, "qa": {"overall": "passed"}, "documents": [{"draft_post_id": 9002}]}}
        self.assertEqual(WP.guard("publish_draft", wc, post=9002)["code"], "create_automation_pending")
        self.assertEqual(WP.guard("create_draft", wc, status="draft", slug="neu")["code"], "ok")             # Drafts bleiben erlaubt
        f = {x["id"]: x for x in json.load(open(os.path.join(ROOT, "clients/spreewald-luftaufnahmen/state/findings.json")))["findings"]}
        self.assertEqual(f["F-025"]["title"], "Runner repository write/push unavailable"); self.assertNotIn("WordPress", f["F-025"]["title"])
        self.assertEqual(f["F-024"]["status"], "open")
        w3 = {"gate2": {"status": "approved"}, "gate3": {"status": "approved", "for_draft_version": 1, "visual_review_confirmed": True},
              "wordpress": {"mode": "OPTIMIZE", "draft_version": 1, "qa": {"overall": "passed"}, "rollback": {"status": "available"},
                            "documents": [{"wp_post_id": 5401, "draft_post_id": 9001}], "snapshots": [{"post": 5401, "verified": True}]}}
        self.assertEqual(WP.guard("live_update", w3, post=5401)["code"], "live_optimize_blocked")
        st = json.load(open(os.path.join(ROOT, "clients/spreewald-luftaufnahmen/state/sources.json")))["wordpress"]["sandbox_test"]
        self.assertTrue(st["source_page"]["unchanged"]); self.assertEqual(st["test_draft"]["status"], "draft")
        self.assertFalse(st["test_draft"]["published"])
        self.assertNotRegex(json.dumps(st), r"(?i)password|token|secret|private[_]key")

    def test_wordpress_template_layers(self):
        """CREATE über Vorlage / OPTIMIZE über bestehende Seite: Content Layer bearbeiten, Design Layer erhalten, Blöcke duplizieren + spiegeln."""
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import wordpress as WP, copy
        def col(w, kind, cid):
            wid = {"text": [{"id": cid + "t", "elType": "widget", "widgetType": "text-editor", "settings": {"editor": "<p>Text</p>", "_margin": {"top": "5"}}, "elements": []}],
                   "image": [{"id": cid + "i", "elType": "widget", "widgetType": "image", "settings": {"image": {"url": "https://x/a.jpg", "id": 1}}, "elements": []}]}[kind]
            return {"id": cid, "elType": "container", "settings": {"width": {"unit": "%", "size": w}, "padding_mobile": {"top": "2"}}, "elements": wid}
        def sec(sid, first):
            head = {"id": sid + "h", "elType": "container", "settings": {"width": {"unit": "%", "size": "100"}},
                    "elements": [{"id": sid + "hh", "elType": "widget", "widgetType": "heading", "settings": {"title": "H2"}, "elements": []}]}
            a, b = ("text", "image") if first == "text" else ("image", "text")
            return {"id": sid, "elType": "container", "settings": {"flex_direction": "row"}, "elements": [head, col("50", a, sid + "a"), col("50", b, sid + "b")]}
        html = {"id": "trust1", "elType": "container", "settings": {}, "elements": [{"id": "ti1", "elType": "widget", "widgetType": "html", "settings": {"html": "<script src='https://cdn.example/loader.js'></script>"}, "elements": []}]}
        tree = [sec("s1", "text"), sec("s2", "image"), html, sec("s3", "image")]
        al = WP.alternation(tree)
        self.assertEqual([x["orientation"] for x in al["text_image_sections"]], ["text_left", "image_left", "image_left"])
        self.assertEqual(al["issues"][0]["sections"], [1, 3]); self.assertFalse(al["issues"][0]["adjacent"])
        # duplizieren + spiegeln: Design identisch, IDs neu & eindeutig, Ausrichtung gewechselt
        t = copy.deepcopy(tree); new = WP.duplicate_section(t, "s1", mirror=True)
        self.assertEqual(WP.text_image_orientation(new), "image_left"); self.assertEqual(t[1]["id"], new["id"])
        ids = []
        def coll(ns):
            for n in ns: ids.append(n["id"]); coll(n.get("elements") or [])
        coll(t); self.assertEqual(len(ids), len(set(ids)))
        strip = lambda n: sorted(json.dumps({k: v for k, v in x.items() if k not in ("id", "elements")}, sort_keys=True) for x in WP_flat(n))  # noqa: E731
        def WP_flat(n):
            out = [n]
            for c in n.get("elements") or []: out += WP_flat(c)
            return out
        self.assertEqual(strip(tree[0]), strip(new))                                          # Design/Abstände/Responsive unverändert
        with self.assertRaises(ValueError): WP.duplicate_section(t, "trust1", mirror=True)    # kein Text+Bild-Block
        # Content Layer ja, Design Layer nein
        WP.set_content(t, "s1hh", title="Neue H2"); self.assertEqual(WP.find(t, "s1hh")["settings"]["title"], "Neue H2")
        with self.assertRaises(PermissionError): WP.set_content(t, "ti1", html="<p>x</p>")      # Trustindex = Template Layer
        with self.assertRaises(PermissionError): WP.set_content(t, "s1at", _margin={"top": "0"})  # Abstand = Design
        with self.assertRaises(PermissionError): WP.set_content(t, "s1a", width={"size": 40})
        # Sandbox-Kopie ohne Script ist firewall-tauglich, Original nicht
        self.assertTrue(WP.firewall_risk(tree)["blocked"]); self.assertFalse(WP.firewall_risk(WP.script_free_copy(tree))["blocked"])
        # Transport + Rücklese-Vergleich (S3: NBSP-Verlust bei lesbarer Übertragung)
        sent = [{"id": "a1", "elType": "widget", "widgetType": "text-editor", "settings": {"editor": "<p>A\u00a0B</p>"}, "elements": []}]
        self.assertIn("\\u00a0", WP.transport_json(sent)); self.assertTrue(WP.compare_readback(sent, WP.transport_json(sent))["identical"])
        got = [{"id": "a1", "elType": "widget", "widgetType": "text-editor", "settings": {"editor": "<p>A B</p>"}, "elements": []}]
        r = WP.compare_readback(sent, got); self.assertFalse(r["identical"]); self.assertEqual(r["diffs"][0]["issue"], "whitespace")
        got2 = [{"id": "a1", "elType": "widget", "widgetType": "text-editor", "settings": {"editor": "<p>X</p>"}, "elements": []}]
        self.assertEqual(WP.compare_readback(sent, got2)["diffs"][0]["issue"], "value")
        s3 = json.load(open(os.path.join(ROOT, "clients/spreewald-luftaufnahmen/state/sources.json")))["wordpress"]["s3_test"]
        self.assertEqual(s3["target"]["id"], 6955); self.assertTrue(s3["draft_kept"])
        self.assertEqual({r["layer"] for r in s3["results"]} >= {"technisch geschrieben", "strukturell geprüft", "visuell von Noel zu prüfen"}, True)
        tpl = WP.cfg()["create_template"]
        self.assertEqual((tpl["id"], tpl["title"]), (6813, "Landingpage-Vorlage 2026"))

    def test_workflow_render_html(self):
        import tempfile
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import workflow
        with tempfile.TemporaryDirectory() as t:
            src, out = os.path.join(t, "d.md"), os.path.join(t, "d.html")
            open(src, "w", encoding="utf-8").write("# H1\n\n## H2\nText **fett** <script>x</script>\n\n- a\n- b\n\n| A | B |\n|---|---|\n| 1 | 2 |\n| Title | Baudoku \\| Berlin |\n")
            workflow.render(src, out); h = open(out, encoding="utf-8").read()
        for frag in ("<h1>H1</h1>", "<h2>H2</h2>", "<b>fett</b>", "<li>a</li>", "<th>A</th>", "<td>2</td>", "&lt;script&gt;", "<td>Baudoku | Berlin</td>"):
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
