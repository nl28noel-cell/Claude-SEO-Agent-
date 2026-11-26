#!/usr/bin/env python3
"""OPTIMIZE nach manueller Umsetzung: Monitoring-Plan, Read-only-Verifikation, Bewertung, Wiedervorlage.

OPTIMIZE wird NICHT automatisch in WordPress umgesetzt. Noel übernimmt die Empfehlungen des Drive-Dokuments selbst in
Elementor und markiert im Artifact: implemented | partial | not_implemented (workflow/<OPP>.implementation).
Danach prüft der Agent read-only die Live-Seite (verify) und beobachtet die Entwicklung (assess) – ohne Kausalbehauptungen.

    python3 tools/implementation.py recs <OPP>                                   -> Empfehlungen aus dem freigegebenen Dossier
    python3 tools/implementation.py plan <YYYY-MM-DD>                            -> Monitoring-Checkpoints (T+14/30/60/90/180)
    python3 tools/implementation.py verify <OPP> <after_profile.json> [--before <profile.json>] [--claimed partial|implemented|not_implemented]
    python3 tools/implementation.py assess <assess_input.json>                   -> Bewertung eines Checkpoints
    python3 tools/implementation.py checkpoint <OPP> <implemented_at> <gsc_last_date> <before.csv> <after.csv> [--existing OPP-X#2,…]
        -> Checkpoint aus zwei GSC-Exporten (query,page) gleicher Länge vor/nach der Umsetzung: Bewertung + Wiedervorlage-Text + ggf. Re-Optimierung
"""
import datetime as dt, difflib, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CLIENT = "spreewald-luftaufnahmen"
CHECKPOINTS = (14, 30, 60, 90, 180)
GSC_LAG_DAYS = 3          # GSC liefert mit 2–3 Tagen Verzögerung
MIN_WINDOW_DAYS = 28      # vorher keine Aussage über Wirkung
MIN_IMPRESSIONS = 50      # je Vergleichsfenster
VERIFY = ("implemented_as_proposed", "partially_implemented", "different_implementation", "not_detected", "unable_to_verify")
VERIFY_LABEL = {"implemented_as_proposed": "Implemented as proposed", "partially_implemented": "Partially implemented",
                "different_implementation": "Different implementation", "not_detected": "Not detected", "unable_to_verify": "Unable to verify"}
OUTCOMES = {"improved": "Improved – Continue Monitoring", "no_clear_change": "No Clear Change – Reassess Later",
            "underperforming": "Underperforming – New Optimization Recommended", "negative": "Potential Negative Impact – Review Required",
            "too_early": "Too early – insufficient data"}
STOP = set("der die das und oder mit per für von zu im in am an auf aus bei ihr ihre ihren sie wir uns unser unsere ein eine einer eines den dem des ist sind wird werden so wie was als auch nicht nur noch mehr".split())


def _d(s):
    return dt.date.fromisoformat(str(s)[:10])


def _norm(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(t or ""))).strip().lower()


def _tokens(t):
    return {w for w in re.findall(r"[a-zäöüß0-9-]{3,}", _norm(t)) if w not in STOP}


def _sim(a, b):
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _hsim(cand, want, headings):
    """Überschriften-Ähnlichkeit: Zeichenfolge UND gemeinsame unterscheidende Begriffe. Begriffe, die in vielen Überschriften der
    Seite vorkommen (z. B. „Baudokumentation“, „Drohne“), zählen nicht als Beleg."""
    s = _sim(cand, want)
    if s >= 0.85:
        return s
    allh = [h for _, h in headings] + [want]
    freq = {}
    for h in allh:
        for t in _tokens(h):
            freq[t] = freq.get(t, 0) + 1
    common = {t for t, n in freq.items() if n >= 3}
    dw = _tokens(want) - common
    if not dw:
        return s
    share = len(dw & _tokens(cand)) / len(dw)
    return min(s, 0.59) if share == 0 else max(s, 0.6 + 0.25 * share) if share >= 0.34 else min(s, 0.59)


# ---------------------------------------------------------------- Monitoring-Plan
def plan(implemented_at):
    """Checkpoints ab dem TATSÄCHLICHEN Implementierungsdatum; auswertbar erst nach GSC-Verzögerung."""
    t0 = _d(implemented_at)
    return [{"label": f"T+{n}", "days": n, "due": (t0 + dt.timedelta(days=n)).isoformat(),
             "data_ready": (t0 + dt.timedelta(days=n + GSC_LAG_DAYS)).isoformat(), "status": "planned",
             "optional": n == 180} for n in CHECKPOINTS]


def due(checkpoints, today=None):
    today = _d(today or dt.date.today().isoformat())
    return [c for c in checkpoints or [] if c.get("status") == "planned" and _d(c["data_ready"]) <= today]


# ---------------------------------------------------------------- Empfehlungen aus dem freigegebenen Dossier
def recs_from_dossier(R, page_url=None):
    """Prüfbare Empfehlungen (Title, Meta, Abschnitte KEEP/EDIT/NEW, interne Links, FAQ) aus Dossier G/H/P."""
    G, H, P = R.get("G_structure") or {}, R.get("H_ia") or {}, R.get("P_diagnosis") or {}
    out = []
    title = next((x for x in P.get("sensitive_changes") or [] if x.get("element") == "Title"), None)
    if title or G.get("title_proposal"):
        out.append({"id": "title", "area": "Title", "action": "EDIT", "kind": "title", "proposed": (title or {}).get("proposed") or G.get("title_proposal"),
                    "current": (title or {}).get("current")})
    if G.get("meta_note"):
        must_not = [w for w in ("3d-modell", "jetzt buchen") if w in _norm(G["meta_note"]).replace("„", "").replace("“", "") or w.replace("-", "") in _norm(G["meta_note"])]
        out.append({"id": "meta", "area": "Meta Description", "action": "EDIT", "kind": "meta", "hint": G["meta_note"], "must_not": must_not})
    if G.get("h1_action") or G.get("h1"):
        out.append({"id": "h1", "area": "H1", "action": (G.get("h1_action") or "KEEP").split("/")[0], "kind": "heading", "heading": G.get("h1"), "tag": "h1"})
    for i, s in enumerate(G.get("sections") or []):
        a = (s.get("action") or "").split("/")[0]
        if a in ("KEEP", "EDIT", "NEW", "REMOVE", "REDUCE"):
            out.append({"id": f"s{i + 1}", "area": s.get("h2"), "action": a, "kind": "faq" if re.search(r"häufige fragen|faq", _norm(s.get("h2"))) else "heading",
                        "heading": s.get("h2"), "existing": s.get("existing"), "tag": "h2", "subheadings": s.get("h3") or []})
    target = page_url or (H.get("current") or {}).get("target", {}).get("url")
    for l in H.get("internal_links") or []:
        if l.get("type") == "add" and target and l.get("from") == target:
            out.append({"id": "link:" + l["to"], "area": f"Interner Link → {l['to']}", "action": "NEW", "kind": "link", "to": l["to"], "anchor": l.get("anchor")})
    return out


# ---------------------------------------------------------------- Read-only-Verifikation
def _links(p):
    return [x.get("href") if isinstance(x, dict) else x for x in (p or {}).get("links") or []]


def verify(recs, after, before=None, claimed=None, research_meta=None):
    """Vergleicht Empfehlungen mit dem Live-Stand (after) und – soweit vorhanden – dem Stand vor der Umsetzung (before).
    Klassifikation je Empfehlung: implemented_as_proposed | partially_implemented | different_implementation | not_detected | unable_to_verify.
    Überschreibt nie Noels Angabe – Abweichungen werden als Hinweis ausgegeben."""
    lim = []
    if not after or after.get("error") or not after.get("headings"):
        return {"status": "failed", "results": [], "limitations": ["Live-Seite nicht lesbar: " + str((after or {}).get("error") or "keine Daten")],
                "summary": {}, "mismatch": None}
    if not before:
        lim.append("Kein verlässlicher Pre-Change-Snapshot – Änderungen gegenüber dem vorherigen Stand nur eingeschränkt nachweisbar.")
    else:
        if not before.get("sections"):
            lim.append(f"Pre-Change-Snapshot vom {str(before.get('fetched'))[:10]} enthält nur Title, Meta und Überschriften – Textänderungen innerhalb bestehender Abschnitte nicht nachweisbar.")
        if not before.get("links"):
            lim.append("Pre-Change-Snapshot ohne interne Links – Link-Empfehlungen werden nur gegen den Live-Stand geprüft.")
    if research_meta and before and research_meta.get("updated") and str(before.get("fetched", ""))[:10] > str(research_meta["updated"])[:10]:
        lim.append("Snapshot ist neuer als die Research-Version – Vergleich nur mit Vorbehalt.")
    ah = [(t, h) for t, h in after.get("headings") or []]
    bh = [(t, h) for t, h in (before or {}).get("headings") or []]
    atext = " ".join([after.get("title") or "", after.get("meta_description") or ""] + [h for _, h in ah] + [s.get("text", "") for s in after.get("sections") or []])
    res = []
    for r in recs:
        st, ev = "unable_to_verify", ""
        k = r["kind"]
        if k == "title":
            cur, prop, old = after.get("title") or "", r.get("proposed") or "", (before or {}).get("title") or r.get("current")
            if prop and _sim(cur, prop) >= 0.97:
                st, ev = "implemented_as_proposed", f"Title = „{cur}“"
            elif old and _norm(cur) == _norm(old):
                st, ev = "not_detected", "Title unverändert"
            elif old:
                st = "partially_implemented" if (_tokens(prop) - _tokens(old)) & _tokens(cur) else "different_implementation"
                ev = f"Title neu: „{cur}“ (Vorschlag: „{prop}“)"
            else:
                ev = "Kein Vorher-Title bekannt"
        elif k == "meta":
            cur, old = after.get("meta_description") or "", (before or {}).get("meta_description")
            if old is None:
                ev = "Kein Vorher-Wert bekannt"
            elif _norm(cur) == _norm(old):
                st, ev = "not_detected", "Meta Description unverändert"
            else:
                bad = [w for w in r.get("must_not") or [] if w.replace("-", "") in _norm(cur).replace("-", "")]
                st = "different_implementation" if bad else "implemented_as_proposed"
                ev = f"Neu: „{cur[:140]}“" + (f" · enthält weiterhin {', '.join(bad)}" if bad else "")
        elif k in ("heading", "faq"):
            want = r.get("heading") or ""
            parts = [x.strip() for x in re.split(r"\s+·\s+", want) if x.strip()]
            if r["action"] == "KEEP" and len(parts) > 1:  # Sammel-Label aus dem Dossier („A · B · C“) → jeden Teil prüfen
                miss = [x for x in parts if max((_hsim(h, x, ah) for _, h in ah), default=0) < 0.8]
                st, ev = ("implemented_as_proposed", "alle Teilabschnitte vorhanden") if not miss else ("not_detected", "nicht gefunden: " + ", ".join(miss) + " – bitte prüfen (Ranking Protection)")
                res.append({"id": r["id"], "area": r["area"], "action": r["action"], "status": st, "label": VERIFY_LABEL[st], "evidence": ev}); continue
            best = max(ah, key=lambda x: _hsim(x[1], want, ah), default=(None, ""))
            s = _hsim(best[1], want, ah) if best[0] else 0
            was = max((_hsim(h, want, bh) for _, h in bh), default=0) if bh else None
            if r["action"] == "KEEP":
                st, ev = ("implemented_as_proposed", "Abschnitt weiterhin vorhanden") if s >= 0.8 else ("not_detected", "KEEP-Abschnitt nicht mehr gefunden – bitte prüfen (Ranking Protection)")
            elif r["action"] in ("REMOVE", "REDUCE"):
                st, ev = ("implemented_as_proposed", "Abschnitt entfernt") if s < 0.6 else ("not_detected", "Abschnitt weiterhin vorhanden")
            elif r["action"] == "NEW":
                if s >= 0.85:
                    st, ev = "implemented_as_proposed", f"Überschrift gefunden: „{best[1]}“"
                elif s >= 0.6:
                    st, ev = "partially_implemented", f"Ähnliche Überschrift: „{best[1]}“"
                else:
                    freq = {}
                    for _, h in ah:
                        for t in _tokens(h):
                            freq[t] = freq.get(t, 0) + 1
                    dw = {t for t in _tokens(want) if freq.get(t, 0) < 3} or _tokens(want)  # nur unterscheidende Begriffe zählen
                    cover = len(dw & _tokens(atext)) / max(1, len(dw))
                    st, ev = ("different_implementation", f"Thema im Text erkennbar ({round(cover * 100)} % der Begriffe), andere Überschrift") if cover >= 0.6 else ("not_detected", "Weder Überschrift noch Thema gefunden")
                if was is not None and was >= 0.85:
                    st, ev = "unable_to_verify", f"Überschrift war schon vor der Umsetzung vorhanden: „{best[1]}“"
                if k == "faq" and st == "not_detected" and len(after.get("faq_questions") or []) > len((before or {}).get("faq_questions") or []):
                    st, ev = "partially_implemented", f"{len(after['faq_questions'])} Frage-Überschriften (vorher {len((before or {}).get('faq_questions') or [])})"
            else:  # EDIT
                if s < 0.6:
                    st, ev = "different_implementation", f"Überschrift „{want}“ nicht mehr vorhanden – Abschnitt umbenannt oder entfernt"
                elif before and before.get("sections"):
                    bt = next((x.get("text", "") for x in before["sections"] if _sim(x.get("heading"), want) >= 0.8), None)
                    at = next((x.get("text", "") for x in after.get("sections") or [] if _sim(x.get("heading"), want) >= 0.8), None)
                    if bt is not None and at is not None:
                        st, ev = ("not_detected", "Text unverändert") if _norm(bt) == _norm(at) else ("partially_implemented", "Text geändert (Inhalt bitte stichprobenartig prüfen)")
                    else:
                        ev = "Abschnittstext nicht vergleichbar"
                else:
                    ev = "Abschnitt vorhanden; Textänderung ohne Text-Snapshot nicht nachweisbar"
        elif k == "link":
            al, bl = _links(after), _links(before) if before and before.get("links") else None
            hit = any(r["to"].strip("/") and r["to"].strip("/") in (h or "") for h in al)
            if not after.get("links") and "links" not in after:
                ev = "Live-Scan ohne Linkdaten"
            elif hit:
                st, ev = ("unable_to_verify", "Link war bereits vorher vorhanden") if bl is not None and any(r["to"].strip("/") in (h or "") for h in bl) else ("implemented_as_proposed", f"Link auf {r['to']} gefunden")
            else:
                st, ev = "not_detected", f"Kein Link auf {r['to']}"
        res.append({"id": r["id"], "area": r["area"], "action": r["action"], "status": st, "label": VERIFY_LABEL[st], "evidence": ev})
    changes = [x for x in res if x["action"] != "KEEP"]
    summ = {s: sum(1 for x in changes if x["status"] == s) for s in VERIFY}
    detected = summ["implemented_as_proposed"] + summ["partially_implemented"] + summ["different_implementation"]
    keep_lost = [x["area"] for x in res if x["action"] == "KEEP" and x["status"] == "not_detected"]
    mismatch = None
    if claimed == "implemented" and summ["not_detected"]:
        mismatch = f"Du hast „vollständig umgesetzt“ markiert – {summ['not_detected']} Empfehlung(en) sind im Live-Stand nicht erkennbar. Bewusst weggelassen oder anders gelöst? Deine Angabe bleibt bestehen."
    elif claimed == "not_implemented" and detected:
        mismatch = f"Du hast „noch nicht umgesetzt“ markiert – {detected} Änderung(en) sind im Live-Stand erkennbar. Status bitte prüfen; deine Angabe bleibt bestehen."
    elif claimed in ("implemented", "partial") and not detected and changes:
        mismatch = "Im Live-Stand ist keine der empfohlenen Änderungen eindeutig erkennbar (evtl. Cache oder noch nicht gespeichert). Deine Angabe bleibt bestehen."
    if keep_lost:
        lim.append("Achtung: geschützte KEEP-Abschnitte nicht gefunden: " + ", ".join(keep_lost))
    return {"status": "complete", "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "live_fetched": after.get("fetched"), "baseline_fetched": (before or {}).get("fetched"), "results": res,
            "summary": summ, "detected": detected, "total": len(changes), "limitations": lim, "mismatch": mismatch, "claimed": claimed}


# ---------------------------------------------------------------- Bewertung (keine Kausalbehauptung)
def assess(inp):
    """inp = {implemented_at, gsc_last_date, checkpoint_days, before:{clicks, impressions, position}, after:{...},
    queries:[{query, tier, before_position, after_position, before_impressions, after_impressions}], primary_keyword}"""
    t0, last = _d(inp["implemented_at"]), _d(inp["gsc_last_date"])
    days = (last - t0).days
    b, a = inp.get("before") or {}, inp.get("after") or {}
    notes = ["Bewertung beschreibt Entwicklungen nach der Umsetzung – keine Kausalaussage; Saison, Google-Updates und Wettbewerb wirken mit."]
    if days < MIN_WINDOW_DAYS:
        return {"outcome": "too_early", "label": OUTCOMES["too_early"], "days_with_data": days,
                "notes": notes + [f"Erst {max(days, 0)} Tage GSC-Daten nach der Umsetzung (GSC-Verzögerung ~{GSC_LAG_DAYS} Tage); Mindestfenster {MIN_WINDOW_DAYS} Tage."]}
    if (b.get("impressions") or 0) < MIN_IMPRESSIONS or (a.get("impressions") or 0) < MIN_IMPRESSIONS:
        return {"outcome": "too_early", "label": OUTCOMES["too_early"], "days_with_data": days,
                "notes": notes + [f"Zu wenige Impressionen für eine belastbare Aussage (< {MIN_IMPRESSIONS} je Fenster)."]}
    rel = lambda x, y: (x - y) / y if y else None  # noqa: E731
    di, dc = rel(a.get("impressions", 0), b.get("impressions", 0)), rel(a.get("clicks", 0), b.get("clicks", 0)) if (b.get("clicks") or 0) >= 5 else None
    dp = (b.get("position") - a.get("position")) if a.get("position") and b.get("position") else 0  # positiv = besser
    lost = [q for q in inp.get("queries") or [] if q.get("tier") in ("critical", "high") and q.get("before_position") and q.get("after_position")
            and q["after_position"] - q["before_position"] >= 3]
    won = [q for q in inp.get("queries") or [] if q.get("before_position") and q.get("after_position") and q["before_position"] - q["after_position"] >= 2]
    facts = {"days_with_data": days, "impressions_change": di, "clicks_change": dc, "position_change": round(dp, 1),
             "queries_won": [q["query"] for q in won], "protected_queries_lost": [q["query"] for q in lost]}
    if lost and (di is not None and di <= -0.2) or (di is not None and di <= -0.3 and dp <= -2):
        o = "negative"
    elif dp >= 2 or (di is not None and di >= 0.25 and dp > -1) or (dc is not None and dc >= 0.25):
        o = "improved"
    elif days >= 90:
        pk = next((q for q in inp.get("queries") or [] if q.get("query") == inp.get("primary_keyword")), None)
        o = "underperforming" if not pk or (pk.get("after_position") or 99) > 10 else "no_clear_change"
    else:
        o = "no_clear_change"
    return {"outcome": o, "label": OUTCOMES[o], **facts, "notes": notes}


def review_message(opp_name, implemented_at, assessment):
    """Text für die Wiedervorlage (Dashboard) – nur wenn die Daten es tragen."""
    if assessment.get("outcome") == "underperforming":
        return (f"Diese Seite wurde am {_d(implemented_at).strftime('%d.%m.%Y')} überarbeitet. Nach {assessment['days_with_data']} Tagen ist für die relevanten "
                "Zielkeywords noch keine klare Verbesserung erkennbar. Der Agent empfiehlt, die Suchintention und die verbleibenden Content-Gaps erneut zu prüfen.")
    if assessment.get("outcome") == "negative":
        return (f"Seit der Überarbeitung am {_d(implemented_at).strftime('%d.%m.%Y')} haben geschützte Keywords an Position verloren "
                f"({', '.join(assessment.get('protected_queries_lost') or []) or 'Gesamt-Impressionen rückläufig'}). Bitte prüfen – keine automatische Änderung.")
    return None


def reoptimization(opp, implementation, assessment, existing=()):
    """Neue OPTIMIZE-Iteration nur bei Underperforming nach ≥ 90 Tagen; nie doppelt; braucht wieder Gate 1;
    bezieht frühere Change Sets und Monitoring-Ergebnisse ein."""
    if assessment.get("outcome") != "underperforming" or (assessment.get("days_with_data") or 0) < 90:
        return None
    it = int(implementation.get("iteration") or 1) + 1
    key = f"{opp['id']}#{it}"
    if key in set(existing):
        return None
    return {"key": key, "parent": opp["id"], "iteration": it, "type": "OPTIMIZE", "status": "proposed", "needs_gate1": True,
            "previous": {"implemented_at": implementation.get("implemented_at"), "status": implementation.get("status"),
                         "verification": (implementation.get("verification") or {}).get("summary"), "assessment": assessment.get("label")},
            "instruction": "Nur Empfehlungen, die nicht bereits im vorherigen Change Set standen oder nachweislich umgesetzt sind; Suchintention und verbleibende Content-Gaps neu prüfen.",
            "message": review_message(opp.get("name"), implementation.get("implemented_at"), assessment)}


def assess_from_rows(before_rows, after_rows, page, protected, implemented_at, gsc_last, primary_keyword):
    """GSC-Zeilen (query, page, clicks, impressions, position) zweier gleich langer Fenster → assess()-Eingabe für die Zielseite."""
    def agg(rows):
        rows = [r for r in rows if (r.get("page") or "").rstrip("/").endswith(page.rstrip("/"))]
        c = sum(float(r["clicks"]) for r in rows); i = sum(float(r["impressions"]) for r in rows)
        pw = sum(float(r["position"]) * float(r["impressions"]) for r in rows)
        q = {r["query"]: r for r in rows}
        return {"clicks": c, "impressions": i, "position": round(pw / i, 2) if i else None}, q
    b, bq = agg(before_rows); a, aq = agg(after_rows)
    tiers = {x["query"]: x.get("tier") for x in protected or []}
    qs = []
    for k in sorted(set(bq) | set(aq) | set(tiers)):
        qs.append({"query": k, "tier": tiers.get(k), "before_position": float(bq[k]["position"]) if k in bq else None, "after_position": float(aq[k]["position"]) if k in aq else None,
                   "before_impressions": float(bq[k]["impressions"]) if k in bq else 0, "after_impressions": float(aq[k]["impressions"]) if k in aq else 0})
    return {"implemented_at": implemented_at, "gsc_last_date": gsc_last, "before": b, "after": a, "queries": qs, "primary_keyword": primary_keyword}


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "plan":
        print(json.dumps(plan(a[1]), indent=2))
    elif a[0] == "recs":
        sys.path.insert(0, os.path.join(ROOT, "tools")); import research  # noqa: E401
        print(json.dumps(recs_from_dossier(research.load(DEFAULT_CLIENT, a[1])), ensure_ascii=False, indent=2))
    elif a[0] == "verify":
        sys.path.insert(0, os.path.join(ROOT, "tools")); import research  # noqa: E401
        R = research.load(DEFAULT_CLIENT, a[1])
        opt = lambda k: a[a.index(k) + 1] if k in a else None  # noqa: E731
        before = json.load(open(opt("--before"), encoding="utf-8")) if opt("--before") else None
        r = verify(recs_from_dossier(R), json.load(open(a[2], encoding="utf-8")), before, opt("--claimed"), {"updated": R.get("updated"), "version": R.get("version")})
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif a[0] == "checkpoint":
        import csv
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        d = json.load(open(os.path.join(ROOT, "dashboard", "public", "data", DEFAULT_CLIENT, "dashboard.json"), encoding="utf-8"))
        o = next(x for x in d["opportunities"] if x["id"] == a[1])
        rows = lambda f: list(csv.DictReader(open(f, encoding="utf-8")))  # noqa: E731
        inp = assess_from_rows(rows(a[4]), rows(a[5]), o.get("existing_page") or "", (o.get("ranking_protection") or {}).get("queries"), a[2], a[3], o.get("primary_keyword"))
        r = assess(inp)
        ex = (a[a.index("--existing") + 1].split(",") if "--existing" in a else [])
        print(json.dumps({"result": {**r, "message": review_message(o.get("name"), a[2], r)}, "reoptimization": reoptimization(o, {"implemented_at": a[2]}, r, ex)}, ensure_ascii=False, indent=2))
    elif a[0] == "assess":
        print(json.dumps(assess(json.load(open(a[1], encoding="utf-8"))), ensure_ascii=False, indent=2))
    else:
        sys.exit(__doc__)
