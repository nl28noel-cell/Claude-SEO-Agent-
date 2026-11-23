"""GA4-, Google-Ads- und Funnel-Abschnitte für dashboard.json (wird von build_dashboard_data.py aufgerufen).

Pipeline: API → Rohdaten (clients/<slug>/data/ga4-*/, ads-*/) → hier Normalisierung/Analyse → Dashboard-Datenschicht.
Liest keine Credentials. Schreibt keine Account-Namen anderer MCC-Kunden.

Funnel-Modell (je Themencluster und je Landingpage):
  Search Demand (Semrush) → Organic Visibility (GSC) / Paid Visibility (Ads-Historie über GA4)
  → Click → Landing Page (Website-Inventar) → Engagement (GA4) → Conversion (GA4, klassifiziert) → Business Value (Profil-Priorität)
"""
import csv, datetime as dt, glob, json, os, re
from collections import defaultdict, Counter


def _csv(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _latest(cdir, prefix):
    ds = sorted(glob.glob(os.path.join(cdir, "data", prefix + "-*")))
    return ds[-1] if ds else None


def norm_path(p):
    """GSC-Pfad und GA4-landingPage auf dieselbe Form bringen: klein, ohne Query, ohne Slash am Ende (außer /)."""
    if p is None:
        return None
    p = p.split("?")[0].split("#")[0].strip().lower()
    if not p or p == "(not set)":
        return None
    if not p.startswith("/"):
        p = "/" + p
    return p if p == "/" else p.rstrip("/")


def _iso(d):  # 20241117 -> 2024-11-17
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 and d.isdigit() else d


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def build(cdir, cfg, gsc_daily, gsc_range, queries, pages, classify_cluster, inventory, cache_rows, opps):
    warnings = []
    gdir = _latest(cdir, "ga4")
    adir = _latest(cdir, "ads")
    conv_cfg = json.load(open(os.path.join(cdir, "state", "conversions.json"), encoding="utf-8")) if os.path.exists(os.path.join(cdir, "state", "conversions.json")) else {"events": [], "exclude_sources": []}
    cls = {e["event"]: e for e in conv_cfg.get("events", [])}
    excl = set(conv_cfg.get("exclude_sources", []))
    count_as = {"primary", "secondary"}
    # Doppelte Varianten (z. B. "click to chat") werden nicht zusätzlich gezählt
    no_count = {e["event"] for e in conv_cfg.get("events", []) if "Doppel" in (e.get("recommendation") or "")}
    g_from, g_to = gsc_range

    ga4 = {"available": bool(gdir)}
    if gdir:
        admin = json.load(open(os.path.join(gdir, "ga4_admin.json"), encoding="utf-8")) if os.path.exists(os.path.join(gdir, "ga4_admin.json")) else {}
        summary = json.load(open(os.path.join(gdir, "ga4_fetch_summary.json"), encoding="utf-8")) if os.path.exists(os.path.join(gdir, "ga4_fetch_summary.json")) else {}
        key_events = [k["eventName"] for k in admin.get("keyEvents", {}).get("keyEvents", [])]

        # Tageswerte (Sitzungen/Nutzer/Engagement) + organische Sitzungen + Conversions je Tag
        daily = {}
        for r in _csv(os.path.join(gdir, "ga4_date.csv")):
            d = _iso(r["date"])
            daily[d] = {"date": d, "sessions": int(r["sessions"]), "users": int(r["totalUsers"]), "engaged": int(r["engagedSessions"]),
                        "eng_time": round(_f(r["userEngagementDuration"])), "organic": 0, "conv_primary": 0, "conv_secondary": 0}
        landing_rows = _csv(os.path.join(gdir, "ga4_landing_date.csv"))
        test_sessions = 0
        for r in landing_rows:
            d = _iso(r["date"])
            if r["sessionSource"] in excl:
                test_sessions += int(r["sessions"]); continue
            if r["sessionDefaultChannelGroup"] == "Organic Search" and d in daily:
                daily[d]["organic"] += int(r["sessions"])
        conv_rows = [r for r in _csv(os.path.join(gdir, "ga4_conv_date.csv")) if r["sessionSource"] not in excl]
        test_conv = sum(int(r["eventCount"]) for r in _csv(os.path.join(gdir, "ga4_conv_date.csv")) if r["sessionSource"] in excl)
        for r in conv_rows:
            c = cls.get(r["eventName"], {}).get("class")
            d = _iso(r["date"])
            if c in count_as and r["eventName"] not in no_count and d in daily:
                daily[d]["conv_" + c] += int(r["eventCount"])
        daily_l = sorted(daily.values(), key=lambda x: x["date"])

        # Kanäle: 16-Monats-Fenster (wie GSC) und gesamt
        def channel_table(a, b):
            t = defaultdict(lambda: Counter())
            for r in landing_rows:
                d = _iso(r["date"])
                if r["sessionSource"] in excl or not (a <= d <= b):
                    continue
                x = t[r["sessionDefaultChannelGroup"]]
                x["sessions"] += int(r["sessions"]); x["engaged"] += int(r["engagedSessions"]); x["eng_time"] += _f(r["userEngagementDuration"])
            for r in conv_rows:
                d = _iso(r["date"]); c = cls.get(r["eventName"], {}).get("class")
                if a <= d <= b and c in count_as and r["eventName"] not in no_count:
                    t[r["sessionDefaultChannelGroup"]]["conv_" + c] += int(r["eventCount"])
            out = [{"channel": k, "sessions": v["sessions"], "engaged": v["engaged"], "eng_rate": (v["engaged"] / v["sessions"]) if v["sessions"] else None,
                    "avg_eng_time": (v["eng_time"] / v["sessions"]) if v["sessions"] else None,
                    "conv_primary": v["conv_primary"], "conv_secondary": v["conv_secondary"]} for k, v in t.items()]
            return sorted(out, key=lambda x: -x["sessions"])

        first = daily_l[0]["date"] if daily_l else None
        last = daily_l[-1]["date"] if daily_l else None

        # Monatsreihe je Kanal
        ch_month = defaultdict(Counter)
        for r in landing_rows:
            if r["sessionSource"] in excl:
                continue
            ch_month[_iso(r["date"])[:7]][r["sessionDefaultChannelGroup"]] += int(r["sessions"])

        # Landingpages im GSC-Fenster
        lp = defaultdict(Counter)
        for r in landing_rows:
            d = _iso(r["date"]); p = norm_path(r["landingPage"])
            if r["sessionSource"] in excl or not p or not (g_from <= d <= g_to):
                continue
            x = lp[p]; s = int(r["sessions"])
            x["sessions"] += s; x["engaged"] += int(r["engagedSessions"]); x["eng_time"] += _f(r["userEngagementDuration"])
            if r["sessionDefaultChannelGroup"] == "Organic Search":
                x["organic"] += s; x["organic_engaged"] += int(r["engagedSessions"])
            elif r["sessionDefaultChannelGroup"] in ("Paid Search", "Cross-network", "Paid Other"):
                x["paid"] += s
        for r in conv_rows:
            d = _iso(r["date"]); p = norm_path(r["landingPage"]); c = cls.get(r["eventName"], {}).get("class")
            if p and g_from <= d <= g_to and c in count_as and r["eventName"] not in no_count:
                lp[p]["conv_" + c] += int(r["eventCount"])
                if r["sessionDefaultChannelGroup"] == "Organic Search":
                    lp[p]["organic_conv"] += int(r["eventCount"])

        # Event-Inventar
        ev = defaultdict(lambda: {"total": 0, "window": 0, "first": None, "last": None, "key_hist": 0})
        for r in _csv(os.path.join(gdir, "ga4_events_month.csv")):
            e = ev[r["eventName"]]; m = r["yearMonth"][:4] + "-" + r["yearMonth"][4:]
            n = int(r["eventCount"]); e["total"] += n; e["key_hist"] += round(_f(r["keyEvents"]))
            if g_from[:7] <= m <= g_to[:7]:
                e["window"] += n
            e["first"] = min(e["first"] or m, m); e["last"] = max(e["last"] or m, m)
        tests = Counter()
        for r in _csv(os.path.join(gdir, "ga4_conv_date.csv")):
            if r["sessionSource"] in excl:
                tests[r["eventName"]] += int(r["eventCount"])
        events = []
        for name, e in ev.items():
            c = cls.get(name)
            if not c and e["total"] < 1:
                continue
            events.append({"event": name, "total": e["total"], "window": e["window"], "first": e["first"], "last": e["last"],
                           "key_event_now": name in key_events, "key_events_hist": e["key_hist"], "test_events": tests.get(name, 0),
                           "class": c["class"] if c else "auto", "label": c["label"] if c else None,
                           "reason": c["reason"] if c else "Automatisch erfasstes GA4-Event (keine Business-Conversion).",
                           "recommendation": c["recommendation"] if c else None})
        order = {"primary": 0, "secondary": 1, "micro": 2, "none": 3, "auto": 4}
        events.sort(key=lambda x: (order.get(x["class"], 9), -x["total"]))

        sm = sorted(_csv(os.path.join(gdir, "ga4_source_medium.csv")), key=lambda r: -int(r["sessions"]))
        dev = defaultdict(Counter)
        for r in _csv(os.path.join(gdir, "ga4_device_channel.csv")):
            x = dev[r["deviceCategory"]]; x["sessions"] += int(r["sessions"]); x["engaged"] += int(r["engagedSessions"])
            if r["sessionDefaultChannelGroup"] == "Organic Search":
                x["organic"] += int(r["sessions"])
        reg = Counter()
        for r in _csv(os.path.join(gdir, "ga4_region.csv")):
            reg[r["region"]] += int(r["sessions"])
        ga4.update({
            "property": {"id": admin.get("property", {}).get("name", "").split("/")[-1], "name": admin.get("property", {}).get("displayName"),
                         "time_zone": admin.get("property", {}).get("timeZone"), "created": (admin.get("property", {}).get("createTime") or "")[:10],
                         "retention": admin.get("dataRetentionSettings", {}).get("eventDataRetention"),
                         "streams": [s.get("webStreamData", {}).get("defaultUri") for s in admin.get("dataStreams", {}).get("dataStreams", [])],
                         "ads_links": [l.get("customerId") for l in admin.get("googleAdsLinks", {}).get("googleAdsLinks", [])]},
            "first": first, "last": last, "fetch_range": [summary.get("start"), summary.get("end")],
            "quality": {"thresholding": any(v.get("subject_to_thresholding") for v in summary.get("datasets", {}).values()),
                        "sampling": any(v.get("sampling") for v in summary.get("datasets", {}).values()),
                        "test_sessions_excluded": test_sessions, "test_conversion_events_excluded": test_conv,
                        "capture_ratio": None},
            "key_events": key_events,
            "daily": daily_l,
            "channel_month": [{"month": m, **dict(v)} for m, v in sorted(ch_month.items())],
            "channels_window": channel_table(g_from, g_to),
            "channels_all": channel_table("0000", "9999"),
            "landing": [{"page": p, **{k: (round(v) if isinstance(v, float) else v) for k, v in x.items()},
                         "eng_rate": (x["engaged"] / x["sessions"]) if x["sessions"] else None,
                         "avg_eng_time": (x["eng_time"] / x["sessions"]) if x["sessions"] else None} for p, x in sorted(lp.items(), key=lambda kv: -kv[1]["sessions"])],
            "events": events,
            "source_medium": [{"source_medium": r["sessionSourceMedium"], "channel": r["sessionDefaultChannelGroup"], "sessions": int(r["sessions"]),
                               "engaged": int(r["engagedSessions"]), "test": any(x in r["sessionSourceMedium"] for x in excl)} for r in sm[:25]],
            "devices": sorted([{"device": k, **dict(v)} for k, v in dev.items()], key=lambda x: -x["sessions"]),
            "regions": [{"region": k, "sessions": v} for k, v in reg.most_common(12)],
        })
        # Erfassungsquote: GA4 google/organic vs. GSC-Klicks im selben Zeitraum
        gsc_clicks = sum(r["clicks"] for r in gsc_daily if g_from <= r["date"] <= g_to)
        ga_org = sum(int(r["sessions"]) for r in landing_rows if r["sessionSource"] == "google" and r["sessionDefaultChannelGroup"] == "Organic Search" and g_from <= _iso(r["date"]) <= g_to)
        ga4["quality"]["capture_ratio"] = round(ga_org / gsc_clicks, 3) if gsc_clicks else None
        ga4["quality"]["capture_basis"] = {"gsc_clicks": gsc_clicks, "ga4_google_organic_sessions": ga_org, "range": [g_from, g_to]}
    else:
        warnings.append("Keine GA4-Daten gefunden.")

    # ---------------------------------------------------------------- Google Ads
    ads = {"available": False}
    disc = json.load(open(os.path.join(adir, "ads_discovery.json"), encoding="utf-8")) if adir and os.path.exists(os.path.join(adir, "ads_discovery.json")) else None
    if disc:
        ads.update({"discovery": {k: disc.get(k) for k in ("checked_at", "api_version", "access_level", "tests", "mcc", "client_accounts", "account")}})
    if gdir:
        hist = [r for r in _csv(os.path.join(gdir, "ga4_ads_month.csv")) if r["sessionGoogleAdsCampaignName"] != "(not set)"]
        seen = defaultdict(list)
        for r in hist:
            seen[(r["advertiserAdImpressions"], r["advertiserAdClicks"], r["advertiserAdCost"][:8])].append(r["yearMonth"])
        months = []
        for r in hist:
            imp, clk, cost, ses = int(_f(r["advertiserAdImpressions"])), int(_f(r["advertiserAdClicks"])), _f(r["advertiserAdCost"]), int(r["sessions"])
            flags = []
            if imp and len(seen[(r["advertiserAdImpressions"], r["advertiserAdClicks"], r["advertiserAdCost"][:8])]) > 1:
                flags.append("Identische Werte in mehreren Monaten")
            if clk and ses and clk / ses > 10:
                flags.append(f"Klicks/Sitzungen = {clk / ses:.0f}")
            months.append({"month": r["yearMonth"][:4] + "-" + r["yearMonth"][4:], "campaign": r["sessionGoogleAdsCampaignName"], "impressions": imp,
                           "clicks": clk, "cost": round(cost, 2), "sessions": ses, "cluster": classify_cluster(r["sessionGoogleAdsCampaignName"]), "flags": flags})
        months.sort(key=lambda x: (x["month"], x["campaign"]))
        kws = []
        for r in _csv(os.path.join(gdir, "ga4_ads_keyword.csv")):
            if r["sessionGoogleAdsKeyword"] in ("(not set)", ""):
                continue
            clk, cost = int(_f(r["advertiserAdClicks"])), _f(r["advertiserAdCost"])
            kws.append({"keyword": r["sessionGoogleAdsKeyword"], "clicks": clk, "cost": round(cost, 2), "cpc": round(cost / clk, 2) if clk else None,
                        "sessions": int(r["sessions"]), "engaged": int(r["engagedSessions"]), "key_events": int(_f(r["keyEvents"])),
                        "cluster": classify_cluster(r["sessionGoogleAdsKeyword"])})
        sq = [{"query": r["sessionGoogleAdsQuery"], "sessions": int(r["sessions"]), "engaged": int(r["engagedSessions"]),
               "cluster": classify_cluster(r["sessionGoogleAdsQuery"])} for r in _csv(os.path.join(gdir, "ga4_ads_query.csv")) if r["sessionGoogleAdsQuery"] not in ("(not set)", "")]
        alp = defaultdict(Counter)
        for r in _csv(os.path.join(gdir, "ga4_ads_landing.csv")):
            if r["sessionGoogleAdsCampaignName"] == "(not set)":
                continue
            p = norm_path(r["landingPage"]) or "(not set)"
            alp[p]["sessions"] += int(r["sessions"]); alp[p]["engaged"] += int(r["engagedSessions"])
        ads.update({"available": bool(hist), "source": "GA4 ↔ Google-Ads-Verknüpfung (historisch)",
                    "history_months": months, "keywords": sorted(kws, key=lambda x: -x["cost"]), "search_queries": sorted(sq, key=lambda x: -x["sessions"]),
                    "landing": [{"page": p, **dict(v)} for p, v in sorted(alp.items(), key=lambda kv: -kv[1]["sessions"])],
                    "range": [months[0]["month"], months[-1]["month"]] if months else None,
                    "totals": {"campaign_level_cost": round(sum(m["cost"] for m in months), 2), "campaign_level_clicks": sum(m["clicks"] for m in months),
                               "keyword_level_cost": round(sum(k["cost"] for k in kws), 2), "keyword_level_clicks": sum(k["clicks"] for k in kws),
                               "paid_sessions": sum(m["sessions"] for m in months), "flagged_rows": sum(1 for m in months if m["flags"])}})

    # ---------------------------------------------------------------- Funnel je Cluster
    prio = cfg.get("service_priorities", {})
    sem = defaultdict(list)
    for r in cache_rows:
        if r.get("status") == "ok" and r.get("database", "de") == "de":
            sem[classify_cluster(r["keyword"])].append(r)
    gq = defaultdict(list)
    for q in queries:
        gq[q["cluster"]].append(q)
    lp_index = {x["page"]: x for x in ga4.get("landing", [])}
    inv_paths = {norm_path(k) for k in inventory}
    clusters = [c for c in list(prio) + ["preis", "generisch_drohne"] if c in gq or c in sem]
    funnel = []
    for c in clusters:
        qs = gq.get(c, []); imp = sum(q["impressions"] for q in qs); clk = sum(q["clicks"] for q in qs)
        pos = sum(q["position"] * q["impressions"] for q in qs) / imp if imp else None
        page_imp = Counter()
        for q in qs:
            if q["page"]:
                page_imp[norm_path(q["page"])] += q["impressions"]
        main_pages = [p for p, _ in page_imp.most_common(3)]
        g = [lp_index.get(p, {}) for p in main_pages]
        kw = [k for k in ads.get("keywords", []) if k["cluster"] == c]
        camp = [m for m in ads.get("history_months", []) if m["cluster"] == c]
        sk = sorted(sem.get(c, []), key=lambda r: -int(_f(r["volume"])))
        f = {"cluster": c, "priority": prio.get(c),
             "demand": {"semrush_volume": sum(int(_f(r["volume"])) for r in sk), "keywords": len(sk),
                        "top": [{"keyword": r["keyword"], "volume": int(_f(r["volume"])), "kd": _f(r["kd"]), "cpc": _f(r["cpc"])} for r in sk[:3]],
                        "avg_cpc": round(sum(_f(r["cpc"]) for r in sk) / len(sk), 2) if sk else None},
             "organic": {"queries": len(qs), "impressions": imp, "clicks": clk, "ctr": clk / imp if imp else None, "position": round(pos, 1) if pos else None},
             "paid": {"keyword_clicks": sum(k["clicks"] for k in kw), "keyword_cost": round(sum(k["cost"] for k in kw), 2),
                      "keywords": [k["keyword"] for k in kw], "campaigns": sorted({m["campaign"] for m in camp}),
                      "campaign_sessions": sum(m["sessions"] for m in camp)},
             "pages": [{"page": p, "exists": p in inv_paths, "organic_sessions": x.get("organic", 0), "sessions": x.get("sessions", 0),
                        "eng_rate": x.get("eng_rate"), "conv_primary": x.get("conv_primary", 0), "conv_secondary": x.get("conv_secondary", 0)}
                       for p, x in zip(main_pages, g)],
             "opportunities": [o["id"] for o in opps if o.get("gsc_cluster") == c]}
        f["engagement"] = {"sessions": sum(p["sessions"] for p in f["pages"]), "organic_sessions": sum(p["organic_sessions"] for p in f["pages"]),
                           "conv_primary": sum(p["conv_primary"] for p in f["pages"]), "conv_secondary": sum(p["conv_secondary"] for p in f["pages"])}
        f["signals"] = funnel_signals(f)
        funnel.append(f)

    # ---------------------------------------------------------------- Landingpage-Join
    gsc_pages = {norm_path(p["page"]): p for p in pages}
    all_pages = set(gsc_pages) | set(lp_index) | {x["page"] for x in ads.get("landing", []) if x["page"] != "(not set)"}
    paid_lp = {x["page"]: x for x in ads.get("landing", [])}
    joined = []
    for p in all_pages:
        if not p:
            continue
        gp, ga, pa = gsc_pages.get(p, {}), lp_index.get(p, {}), paid_lp.get(p, {})
        joined.append({"page": p, "in_inventory": p in inv_paths, "title": gp.get("title"),
                       "gsc_clicks": gp.get("clicks", 0), "gsc_impressions": gp.get("impressions", 0), "gsc_position": gp.get("position"),
                       "ga4_sessions": ga.get("sessions", 0), "ga4_organic": ga.get("organic", 0), "eng_rate": ga.get("eng_rate"), "avg_eng_time": ga.get("avg_eng_time"),
                       "conv_primary": ga.get("conv_primary", 0), "conv_secondary": ga.get("conv_secondary", 0), "paid_sessions_hist": pa.get("sessions", 0)})
    joined.sort(key=lambda x: -(x["gsc_impressions"] + 50 * x["ga4_sessions"]))
    return ga4, ads, {"clusters": funnel, "pages": joined, "window": [g_from, g_to]}, warnings


def funnel_signals(f):
    """Regelbasierte, nachvollziehbare Aussagen – keine Bewertung ohne Datenbasis."""
    s = []
    d, o, p, e = f["demand"], f["organic"], f["paid"], f["engagement"]
    if d["semrush_volume"]:
        s.append(("demand", f"Nachfrage: {d['semrush_volume']:,} Suchen/Monat über {d['keywords']} gemessene Keywords".replace(",", ".")))
    if p["keyword_cost"] or p["campaigns"]:
        txt = f"Paid-Historie: {p['keyword_cost']:,.0f} € für {p['keyword_clicks']} Keyword-Klicks".replace(",", ".") if p["keyword_cost"] else "Paid-Historie: Kampagne(n) " + ", ".join(p["campaigns"][:2])
        s.append(("paid", txt + " (2023–24, über GA4)"))
    if d.get("avg_cpc"):
        s.append(("value", f"Marktwert je Klick (Semrush Ø CPC): {d['avg_cpc']:.2f} €".replace(".", ",")))
    if o["position"] is not None:
        if o["position"] > 10:
            s.append(("weak", f"Organisch schwach: Ø Position {o['position']:.1f}".replace(".", ",")))
        elif o["position"] <= 5:
            s.append(("strong", f"Organisch stark: Ø Position {o['position']:.1f}".replace(".", ",")))
    elif d["semrush_volume"]:
        s.append(("weak", "Organisch keine Sichtbarkeit (keine GSC-Queries)"))
    if f["pages"]:
        ex = [x["page"] for x in f["pages"] if x["exists"]]
        if ex:
            s.append(("page", "Passende Seite vorhanden: " + ex[0]))
    if e["conv_primary"] or e["conv_secondary"]:
        s.append(("conv", f"{e['conv_primary']} Anfragen + {e['conv_secondary']} Kontakt-Klicks über diese Seiten (16 Monate, GA4)"))
    elif e["sessions"]:
        s.append(("noconv", f"{e['sessions']} GA4-Sitzungen, keine Anfrage gemessen (16 Monate)"))
    if (f["priority"] or 0) >= 8:
        s.append(("prio", f"Hohe Business-Priorität ({f['priority']}/10)"))
    return [{"kind": k, "text": t} for k, t in s]
