#!/usr/bin/env python3
"""SEO-Autopilot Workflow: Gate 1 → Google-Drive-Entwurf → Review → Gate 2.

Single Source of Truth ist die Artifact-db-Collection `workflow` (ein Dokument je Opportunity).
Das Artifact schreibt Noels Entscheidungen hinein, der Agent schreibt Produktionsstatus zurück.
`state/workflow.json` ist der Git-Spiegel (vom Agenten nach jedem Lauf geschrieben).

Dokumentschema workflow/<OPP-ID>:
  opp_id, test(bool), title
  gate1:      {status: "approved", at, comment, research_version, research_state, research_override}
              Gate 1 = Strategie-Freigabe: produziert wird nur, wenn research_version der aktuellen
              Research-Version entspricht (tools/research.py strategy_ok) oder research_override=true.
  production: {status: waiting|in_progress|draft_ready|failed, version, doc_id, doc_url, doc_title,
               created_at, updated_at, qa_status, qa_notes, strategy_summary, error, history:[...]}
  review:     {status: pending|revision_requested|approved, comment, at, for_version}
  gate2:      {status: "approved", at, comment}
  trigger:    {requested_at, result}
  wordpress:  {status: not_started|queued|preparing|draft_ready|qa_failed|qa_passed|blocked|publish_queued|publishing|published|publish_failed|rolled_back,
               mode CREATE|OPTIMIZE, draft_version, documents[{role, url, wp_post_id, draft_post_id, edit_link, preview_link, original_link}],
               change_counts, publish_summary[], qa{content,seo,technical,visual,overall}, snapshots[], rollback{status,why}, baseline, published{at, change_entry}}
  gate3:      {status: approved, at, comment, for_draft_version, visual_review_confirmed}   – einzige Freigabe für Live-Schreibvorgänge (tools/wordpress.py guard)
  confirmations: [{op, post, status: confirmed, at}] – gesonderte Bestätigung für delete/slug/redirect/canonical/robots (nie automatisch)
  decision:   {status: active|on_hold|rejected, at, reason, reason_code, review_at, fingerprint, history:[{status, at, reason}]}
              Noels Opportunity-Entscheidung (APPROVE = Gate-Aktion, ON HOLD, REJECT). on_hold/rejected stoppen JEDE automatische
              Weiterverarbeitung (Produktion, WordPress, Publish; bei rejected auch Research). Vor jeder schreibenden Aktion erneut prüfen:
              `workflow.py check-active <dir> <OPP>` (Exit 0 = aktiv, 3 = gestoppt). Kein Löschen – Rücknahme über status active.
              Bricht der Runner einen Auftrag deswegen ab, setzt er production/wordpress/research_retry.status = "stopped";
              die Reaktivierung im Artifact setzt diese Aufträge auf waiting/queued zurück (Freigaben bleiben gültig).
  implementation: {status: awaiting|implemented|partial|not_implemented, implemented_at (tatsächliches Datum), confirmed_at, comment, url,
                   history:[...], baseline:{captured_at, queries[], cluster}, monitoring:{start, checkpoints[T+14…T+180]},
                   verification:{status: queued|running|complete|failed, results[], summary, limitations[], mismatch}, assessments[], reoptimization}
              NUR OPTIMIZE/MERGE: Noel setzt die Empfehlungen des Drive-Dokuments selbst in Elementor um. Kein WordPress-Draft, kein Publish
              (client.json wordpress.optimize_automation = disabled; tools/wordpress.py guard → optimize_manual_only).
  research_retry: {status: queued|running|complete|complete_with_limits|partial|failed|stopped, requested_at, started_at, finished_at,
                   components[], steps{key:{status,why}}, progress{overall,label,done,total}, done[], failed[], budget_hold[], fallback{},
                   blockers[{step,action}], saved{collection,doc,version}, attempt, history[], note}
                   – gezielter Research-Retry (kein neuer Datensatz, kein zweites Dossier). Ergebnisse je Schritt sofort in db research/<OPP>
                   (tools/research.py export-db) – unabhängig vom Git-Push. Alt: "blocked" (Alles-oder-nichts) wird nicht mehr gesetzt.

Befehle (Export vorher per ArtifactData list collection=workflow out_dir=<dir>):
  python3 tools/workflow.py queue  <dir>                   -> offene Arbeit (produce / revise) als JSON
  python3 tools/workflow.py brief  <dir> <OPP-ID> <out.md> -> Produktionsbriefing (Fakten, Freigabe-/Revisionskommentar)
  python3 tools/workflow.py render <draft.md> <out.html>   -> Entwurf (Markdown-Subset) → HTML für Google-Doc-Konvertierung
  python3 tools/workflow.py mirror <dir> [--client SLUG]   -> state/workflow.json aktualisieren
  python3 tools/workflow.py preflight <dir> [--drive-ok] [--folder-ok]  -> Preflight-Checks als JSON (Exit 0 = ok, 2 = blocked)
  python3 tools/workflow.py check-draft <draft.md> [--opp <OPP>] -> QA OPTIMIZE: Change Summary, [KEEP]/[NEW]/[EDIT]/[REMOVE] + Reason, Schutz-Queries
  python3 tools/workflow.py check-active <dir> <OPP-ID>    -> Entscheidung erneut prüfen (Exit 0 aktiv · 3 on_hold/rejected) – VOR jedem Schreibvorgang
  python3 tools/workflow.py doc-title <dir> <OPP-ID> [--companion <url>] -> deterministischer Doc-Titel (Idempotenz); --companion: 2. Dokument des Change Sets
Keine Website-, WordPress- oder URL-Aktion.
"""
import glob, html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import research  # noqa: E402
DEFAULT_CLIENT = "spreewald-luftaufnahmen"


def load_export(d):
    """Liest exportierte db-Dokumente (<dir>/workflow/<id>.json oder <dir>/<id>.json)."""
    files = glob.glob(os.path.join(d, "workflow", "*.json")) or glob.glob(os.path.join(d, "*.json"))
    docs = {}
    for f in files:
        j = json.load(open(f, encoding="utf-8"))
        data = j.get("data", j) if isinstance(j, dict) else {}
        did = j.get("id") if isinstance(j, dict) and "data" in j else os.path.splitext(os.path.basename(f))[0]
        data["_version"] = j.get("version") if isinstance(j, dict) else None
        docs[did or data.get("opp_id")] = data
    return docs


EXPECTED_BRANCH = "claude/semsharks-seo-autopilot-6j1cxc"
STALE_RUN_MIN = 45  # ein "running"-Eintrag ohne Fortschritt gilt danach als abgebrochen


def _age_min(iso):
    import datetime as dt
    try:
        t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 60
    except Exception:
        return 1e9


DECISION_STATES = ("active", "on_hold", "rejected")
IMPLEMENTATION_STATES = ("awaiting", "implemented", "partial", "not_implemented")
_DASH_CACHE = {}


def _optimize_disabled(client=DEFAULT_CLIENT):
    import wordpress
    return wordpress.cfg(client).get("optimize_automation", "disabled") != "enabled"


def mode_of(w, did=None, client=DEFAULT_CLIENT):
    """CREATE oder OPTIMIZE/MERGE: freigegebenes Change Set > WordPress-Modus > Opportunity-Typ > Test-Karte."""
    cs = ((w or {}).get("gate1") or {}).get("change_set") or {}
    if cs.get("action"):
        return "CREATE" if str(cs["action"]).startswith("CREATE") else "OPTIMIZE"
    if (w.get("wordpress") or {}).get("mode"):
        return w["wordpress"]["mode"]
    if w.get("test"):
        return (w.get("card") or {}).get("type") or "CREATE"
    try:
        if client not in _DASH_CACHE:
            _DASH_CACHE[client] = {o["id"]: o.get("type") for o in _dash(client)["opportunities"]}
        t = _DASH_CACHE[client].get(w.get("opp_id") or did)
    except Exception:
        t = None
    return "CREATE" if t == "CREATE" else "OPTIMIZE" if t else "CREATE"


def decision_status(w):
    st = ((w or {}).get("decision") or {}).get("status") or "active"
    return st if st in DECISION_STATES else "active"


def check_active(w):
    """Unmittelbar vor jeder schreibenden Aktion (Drive, WordPress, Research-Commit) erneut aufrufen – eine zwischenzeitlich
    gesetzte ON-HOLD-/REJECT-Entscheidung stoppt den laufenden Auftrag."""
    st = decision_status(w)
    d = (w or {}).get("decision") or {}
    return {"active": st == "active", "status": st, "reason": d.get("reason"), "at": d.get("at"),
            "why": None if st == "active" else f"Opportunity {'zurückgestellt (ON HOLD)' if st == 'on_hold' else 'abgelehnt (REJECTED)'} – keine Weiterverarbeitung"}


def fingerprint(opp):
    """Wesentliche Umstände zum Zeitpunkt einer Ablehnung – Grundlage für „nicht erneut vorschlagen, solange unverändert“."""
    ct = ((opp or {}).get("gsc") or {}).get("cluster_total") or {}
    return {"type": (opp or {}).get("type"), "primary_keyword": (opp or {}).get("primary_keyword"), "existing_page": (opp or {}).get("existing_page"),
            "impressions": ct.get("impressions"), "position": ct.get("position")}


def circumstances_changed(fp_then, opp):
    """True + Gründe, wenn sich die wesentlichen Umstände seit der Ablehnung geändert haben. Reaktiviert NIE automatisch –
    nur Hinweis an Noel."""
    if not fp_then:
        return {"changed": False, "why": []}
    now, why = fingerprint(opp), []
    for k in ("type", "primary_keyword", "existing_page"):
        if fp_then.get(k) != now.get(k):
            why.append(f"{k}: {fp_then.get(k)} → {now.get(k)}")
    a, b = fp_then.get("impressions"), now.get("impressions")
    if a and b is not None and abs(b - a) / a >= 0.5:
        why.append(f"Impressionen {a} → {b} (≥ 50 %)")
    pa, pb = fp_then.get("position"), now.get("position")
    if pa is not None and pb is not None and abs(pb - pa) >= 5:
        why.append(f"Position {pa} → {pb} (≥ 5)")
    return {"changed": bool(why), "why": why}


def actions(docs, client=DEFAULT_CLIENT):
    """Was ist zu tun? Nur explizite Freigaben – nie aus dem bloßen Vorhandensein einer Opportunity.
    Erstproduktion zusätzlich nur mit freigegebener Strategie (Research-Stufe); sonst Eintrag `hold` (nicht bearbeiten).
    ON HOLD / REJECTED: keine Weiterverarbeitung (Eintrag `stopped`); ON HOLD erlaubt nur noch ausdrücklich angeforderte Research."""
    out = []
    for did, w in sorted(docs.items()):
        st = decision_status(w)
        rr = w.get("research_retry") or {}
        if st != "active":
            if st == "on_hold" and rr.get("status") == "queued":
                out.append({"doc": did, "action": "research", "components": rr.get("components", []), "blocked": rr.get("blocked", []),
                            "attempt": rr.get("attempt", 1), "test": bool(w.get("test")), "version": w.get("_version"), "note": "ON HOLD – nur Research, keine Produktion"})
            out.append({"doc": did, "action": "stopped", "reason": st, "test": bool(w.get("test")), "version": w.get("_version")})
            continue
        mode = mode_of(w, did, client)
        impl = w.get("implementation") or {}
        if mode != "CREATE" and not w.get("test"):
            # OPTIMIZE/MERGE: manuelle Umsetzung durch Noel. Nie WordPress (auch nicht aus alten States), nur Verifikation + Monitoring.
            wp = w.get("wordpress") or {}
            if wp.get("status") in ("queued", "preparing", "publish_queued", "publishing") and _optimize_disabled(client):
                out.append({"doc": did, "action": "wp_disabled", "reason": "optimize_manual_only", "test": False, "version": w.get("_version")})
            if (impl.get("verification") or {}).get("status") == "queued" and impl.get("status") in ("implemented", "partial", "not_implemented"):
                out.append({"doc": did, "action": "verify_implementation", "claimed": impl.get("status"), "url": impl.get("url"), "test": False, "version": w.get("_version")})
            import implementation as IMPL
            for c in IMPL.due((impl.get("monitoring") or {}).get("checkpoints")):
                out.append({"doc": did, "action": "monitor", "checkpoint": c["label"], "implemented_at": impl.get("implemented_at"), "test": False, "version": w.get("_version")})
            if (w.get("production") or {}).get("status") == "draft_ready" and (w.get("review") or {}).get("status") != "revision_requested" and _optimize_disabled(client):
                continue  # Drive-Dokument fertig = finales Produktionsartefakt; keine erneute Produktion durch alte States
        if rr.get("status") == "queued" or (rr.get("status") == "running" and _age_min(rr.get("started_at")) >= STALE_RUN_MIN):
            out.append({"doc": did, "action": "research", "components": rr.get("components", []), "blocked": rr.get("blocked", []),
                        "attempt": rr.get("attempt", 1), "test": bool(w.get("test")), "version": w.get("_version")})
        # WordPress (nach Gate 2): Draft vorbereiten bzw. – nur mit Gate 3 – veröffentlichen
        wp = w.get("wordpress") or {}
        if (w.get("gate2") or {}).get("status") == "approved" and not w.get("test") and (mode == "CREATE" or not _optimize_disabled(client)):
            if wp.get("status") == "queued" or (wp.get("status") == "preparing" and _age_min(wp.get("started_at")) >= STALE_RUN_MIN):
                out.append({"doc": did, "action": "wp_draft", "mode": wp.get("mode"), "test": False, "version": w.get("_version")})
                continue
            if wp.get("status") == "publish_queued":
                sys.path.insert(0, os.path.join(ROOT, "tools"))
                import wordpress
                g = wordpress.guard("live_update" if wp.get("mode") == "OPTIMIZE" else "publish_draft", w,
                                    post=(wp.get("documents") or [{}])[0].get("wp_post_id" if wp.get("mode") == "OPTIMIZE" else "draft_post_id"))
                out.append({"doc": did, "action": "wp_publish" if g["allowed"] else "wp_publish_blocked", "reason": g["code"], "why": g["why"],
                            "test": False, "version": w.get("_version")})
                continue
        g1 = (w.get("gate1") or {}).get("status")
        prod = w.get("production") or {}
        rev = w.get("review") or {}
        if (w.get("gate2") or {}).get("status") == "approved":
            continue
        if g1 != "approved":
            continue
        if prod.get("status") == "running" and _age_min(prod.get("started_at")) < STALE_RUN_MIN:
            continue  # läuft bereits (anderer Lauf) – nicht doppelt bearbeiten
        if prod.get("status") == "blocked":
            continue  # technisch blockiert: nur Noels „Erneut versuchen“ setzt wieder auf waiting
        if rev.get("status") == "revision_requested" and prod.get("status") in ("draft_ready", "running"):
            out.append({"doc": did, "action": "revise", "comment": rev.get("comment"), "for_version": rev.get("for_version") or prod.get("version"),
                        "test": bool(w.get("test")), "version": w.get("_version")})
        elif prod.get("status") in (None, "waiting", "failed", "running"):
            if not w.get("test"):
                ok, why = research.strategy_ok(w.get("gate1"), research.load(client, w.get("opp_id") or did))
                if not ok:
                    out.append({"doc": did, "action": "hold", "reason": why, "test": False, "version": w.get("_version")})
                    continue
            out.append({"doc": did, "action": "produce", "comment": (w.get("gate1") or {}).get("comment"), "test": bool(w.get("test")), "version": w.get("_version")})
    return out


def doc_title(w, opp=None, companion=None):
    """Deterministischer Titel → vor dem Anlegen im Zielordner suchen; existiert er, wird kein zweites Dokument erzeugt."""
    name = (opp or {}).get("name") or w.get("title") or w.get("opp_id")
    typ = (opp or {}).get("type") or (w.get("card") or {}).get("type") or "CREATE"
    v = ((w.get("production") or {}).get("version") or 0) + (1 if (w.get("review") or {}).get("status") == "revision_requested" else 0)
    if companion:  # zweites Dokument desselben Change Sets: bestehende Seite abgrenzen
        slug = companion.strip("/").split("/")[-1] or "startseite"
        base = f"{w.get('opp_id')} – Companion – {slug} – Optimierung"
        return base if v <= 1 else f"{base} v{v}"
    base = f"{w.get('opp_id')} – {name} – {'Optimierung' if typ == 'OPTIMIZE' else 'Entwurf'}"
    return base if v <= 1 else f"{base} v{v}"


def preflight(d, drive_ok=False, folder_ok=False):
    import subprocess
    def sh(*a):
        r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()
    checks, reason = {}, None
    rc, top = sh("git", "rev-parse", "--show-toplevel")
    checks["repository"] = rc == 0 and os.path.isdir(os.path.join(ROOT, "tools"))
    rc, br = sh("git", "branch", "--show-current")
    checks["correct_branch"] = br == EXPECTED_BRANCH
    rc1, _ = sh("git", "fetch", "-q", "origin", EXPECTED_BRANCH)
    rc2, behind = sh("git", "rev-list", "--count", f"HEAD..origin/{EXPECTED_BRANCH}")
    checks["up_to_date"] = rc1 == 0 and rc2 == 0 and behind == "0"
    checks["docs_workflow"] = os.path.exists(os.path.join(ROOT, "docs", "workflow.md"))
    checks["business_profile"] = os.path.exists(os.path.join(ROOT, "clients", DEFAULT_CLIENT, "business-profile.md"))
    checks["content_style_guide"] = os.path.exists(os.path.join(ROOT, "clients", DEFAULT_CLIENT, "content-style-guide.md"))
    try:
        docs = load_export(d); checks["workflow_state"] = True
    except Exception:
        docs = {}; checks["workflow_state"] = False
    checks["google_drive_write"] = bool(drive_ok)
    checks["target_folder"] = bool(folder_ok)
    order = [("workflow_state", "workflow_state_unavailable"), ("repository", "repository_unavailable"), ("correct_branch", "wrong_branch"),
             ("up_to_date", "repository_outdated"), ("docs_workflow", "runbook_missing"), ("business_profile", "business_profile_missing"),
             ("content_style_guide", "style_guide_missing"), ("google_drive_write", "drive_tool_unavailable"), ("target_folder", "drive_folder_unavailable")]
    for k, code in order:
        if not checks[k]:
            reason = code; break
    res = {"ok": reason is None, "checks": checks, "block_reason": reason, "queue": actions(docs) if docs else []}
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return res


def _dash(client):
    """dashboard.json ist nicht in Git (generiert). Im Cold Start fehlt es → automatisch aus den Rohdaten bauen."""
    p = os.path.join(ROOT, "dashboard", "public", "data", client, "dashboard.json")
    if not os.path.exists(p):
        import subprocess
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_dashboard_data.py")], check=True, capture_output=True)
    return json.load(open(p, encoding="utf-8"))


def brief(d, opp_id, out, client=DEFAULT_CLIENT):
    docs = load_export(d)
    w = docs.get(opp_id) or {}
    if (w.get("gate1") or {}).get("status") != "approved":
        sys.exit(f"{opp_id}: keine Gate-1-Freigabe – Produktion verweigert.")
    dash = _dash(client)
    o = next((x for x in dash["opportunities"] if x["id"] == opp_id), None)
    if not o and not w.get("test"):
        sys.exit(f"{opp_id} nicht in den Opportunities.")
    R = None
    if not w.get("test"):
        R = research.load(client, opp_id)
        ok, why = research.strategy_ok(w.get("gate1"), R)
        if not ok and (w.get("review") or {}).get("status") != "revision_requested":
            sys.exit(f"{opp_id}: Strategie nicht freigegeben ({why}) – Produktion verweigert.")
    if not o:  # TEST-Eintrag: Karte aus dem db-Dokument
        o = {"id": opp_id, "name": w.get("title", opp_id), "type": (w.get("card") or {}).get("type", "CREATE"), "primary_keyword": (w.get("card") or {}).get("primary_keyword", "test"),
             "gsc": {"queries": [], "cluster": None}, "semrush": {"keywords": []}, "existing_page": None, "why": "Technischer Test", "recommendation": "Technischer Test", "reasoning": [], "risks": [], "findings_detail": []}
    f = next((c for c in dash.get("funnel", {}).get("clusters", []) if c["cluster"] == o.get("gsc_cluster")), None)
    L = [f"# Produktionsbriefing {opp_id} – {o['name']}", ""]
    if w.get("test"):
        L += ["**TEST-Opportunity – nur technischer Workflow-Test, kein echter Content.**", ""]
    g1 = w.get("gate1") or {}
    L += ["## Freigabe", f"- Gate 1: approved am {g1.get('at')}",
          f"- **Kommentar / Scope-Änderungen von Noel (verbindlich, Vorrang vor Dossier F/G):** {g1.get('comment') or '–'}"]
    cs = g1.get("change_set") or {}
    if cs:
        L += [f"- Freigegebene Maßnahme: {cs.get('action')} {cs.get('url') or ''}"]
        cz = g1.get("cannibalization") or {}
        if cz:
            L += [f"- Kannibalisierung bei Freigabe: {cz.get('risk')} · Engine: {cz.get('engine_decision')} · Entscheidung Noel: {cz.get('choice')}"]
        if cs.get("companions"):
            L += ["", "## Change Set: Companion Optimization (je Seite ein eigenes Drive-Dokument, gemeinsam reviewen)"]
            for c in cs["companions"]:
                L += [f"- Seite {c['url']}{' (verknüpft mit ' + c['linked_opp'] + ')' if c.get('linked_opp') else ''}: {c.get('reason')}",
                      f"  - Titel: `python3 tools/workflow.py doc-title <dir> {opp_id} --companion {c['url']}`"] + [f"  - {x}" for x in c.get("required_changes", [])]
    rev = w.get("review") or {}
    if rev.get("status") == "revision_requested":
        L += [f"- **Änderungswunsch (Version {rev.get('for_version')}):** {rev.get('comment')}"]
    L += ["", "## Opportunity",
          f"- Typ: {o['type']} · Priorität: {o.get('priority')} · Confidence: {o.get('confidence')} · Business Fit: {o.get('business_fit')}/10",
          f"- Primary Keyword: {o.get('primary_keyword')} · Cluster: {o.get('gsc_cluster')}",
          f"- Bestehende URL: {o.get('existing_page') or '–'} · Geplante URL: {o.get('planned_url') or '–'}",
          f"- Warum: {o.get('why')}", f"- Empfehlung: {o.get('recommendation')}"]
    L += ["- Reasoning:"] + [f"  - {r}" for r in o.get("reasoning", [])]
    L += ["- Risiken:"] + [f"  - {r}" for r in o.get("risks", [])]
    L += ["", "## Evidenz GSC (16 Monate)"] + [
        f"- {q['query']}: {q.get('impressions', 0)} Impr., {q.get('clicks', 0)} Klicks, Pos. {q.get('position')}" for q in o.get("gsc", {}).get("queries", []) if not q.get("missing")]
    L += ["", "## Evidenz Semrush (DE)"] + [
        f"- {k['keyword']}: Vol. {k.get('volume')}, KD {k.get('kd')}, CPC {k.get('cpc')}" for k in o.get("semrush", {}).get("keywords", []) if k.get("status") == "ok"]
    if f:
        e = f["engagement"]
        L += ["", "## Search → Business (GA4/Ads)", f"- Sitzungen {e['sessions']} · engagiert {e['engaged']} · Funnel Intent {e['micro_sessions']} Sitz. · Leads {e['leads']} ({e['lead_form']} Form, {e['lead_contact']} Kontakt)",
              f"- Paid-Historie: {f['paid']['keyword_cost']} € / {f['paid']['keyword_clicks']} Klicks"] + [f"- Signal: {s['text']}" for s in f["signals"]]
    if R:
        L += _research_brief(R, (w.get("gate1") or {}))
    if o.get("type") in ("OPTIMIZE", "MERGE") or (R or {}).get("P_diagnosis"):
        L += _optimize_brief(R or {}, o)
    L += ["", "## Findings"] + [f"- {x['id']} {x['title']} ({x['status']})" for x in o.get("findings_detail", [])]
    L += ["", "## Verbindliche Regeln",
          "- clients/spreewald-luftaufnahmen/business-profile.md (insb. §8 belegte Vorteile, §10 Niemals erfinden)",
          "- clients/spreewald-luftaufnahmen/content-style-guide.md (Hausformat, Tonalität, Nicht übernehmen)",
          "- Paketinhalt: interner Block, SEO Title, Meta Description, H1, Struktur H2/H3, Volltexte, CTAs, FAQ, interne Links, Bildhinweise, Schema, Redirect-/Canonical-Hinweis (nur Empfehlung); bei OPTIMIZE: bleibt/ändert/ergänzt/warum",
          "- Keine Website-, WordPress-, URL- oder Redirect-Änderung. Nichts veröffentlichen."]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"✓ Briefing → {out}")


def _research_brief(R, g1):
    """Freigegebene Strategie (A–J) als verbindliche Vorgabe für den Entwurf."""
    A, F, G, H = R.get("A_decision", {}), R.get("F_scope", {}), R.get("G_structure", {}), R.get("H_ia", {})
    ko = H.get("keyword_ownership", {})
    L = ["", f"## Freigegebene Strategie (Research v{R.get('version')}{' · OVERRIDE ohne vollständige Research' if g1.get('research_override') else ''})",
         f"- Entscheidung: {A.get('decision')} · Ziel-URL: {A.get('target_url') or '–'}", f"- Zusammenfassung: {A.get('summary')}",
         f"- Kernbotschaft: {F.get('core_message')}", f"- Search Intent: {F.get('search_intent')}", f"- Zielgruppe: {', '.join(F.get('audience', []))}",
         f"- Conversion-Ziel: {F.get('conversion_goal')}", "- Fachliche Fragen (müssen beantwortet werden):"]
    for q in F.get("key_questions", []):
        L += [f"  - {q}"] if isinstance(q, str) else [f"  - {q.get('group')}:"] + [f"    - {x}" for x in q.get("questions", [])]
    L += ["- Notwendige Leistungsinformationen (nur belegt):"] + [f"  - {x}" if isinstance(x, str) else f"  - {x['text']} (Beleg: {x.get('evidence', '–')})" for x in F.get("service_info", [])]
    if F.get("delimitation"):
        L += ["- Abgrenzung:"] + [f"  - {x['service']}: {x['question']} · {x['timing']} · {x['output']} → {x['page']}" for x in F["delimitation"]]
    L += ["- Trust/Proof (nur diese, alle belegt):"] + [f"  - {x}" for x in F.get("trust_proof", [])]
    L += ["- Bewusst NICHT auf dieser Seite:"] + [f"  - {x['topic']} → {x['goes_to']}" for x in F.get("not_on_page", [])]
    L += ["", "### Struktur (Grobgliederung, im Entwurf ausformulieren)", f"- Title-Vorschlag: {G.get('title_proposal') or '–'} · Meta: {G.get('meta_note') or '–'}", f"- H1: {G.get('h1')}"]
    for x in G.get("sections", []):
        L += [f"- H2: {x['h2']} – {x['purpose']}"] + [f"  - H3: {h}" for h in x.get("h3", [])]
    if H.get("consolidation"):
        L += ["", "### Architektur", f"- Konsolidierung: {H['consolidation'].get('decision')}",
              f"- Parent (empfohlen): {((H.get('recommended') or {}).get('parent') or {}).get('url')} · Ziel-URL bleibt: {((H.get('recommended') or {}).get('target') or {}).get('url')}"]
    L += ["", "### Keyword Ownership", f"- Diese Seite: {', '.join(ko.get('owns', []))}"] + [f"- NICHT targeten: {x['keyword']} ({x['reason']} → {x['owner']})" for x in ko.get("do_not_target", [])]
    L += ["- Interne Links (Empfehlung):"] + [f"  - {x['from']} → {x['to']} „{x['anchor']}“ ({x['type']})" for x in H.get("internal_links", [])]
    L += ["", "### Offene Punkte / Risiken (nicht erfinden, im Zweifel weglassen)"] + [f"- [{x['type']}] {x['item']} → {x['mitigation']}" for x in R.get("J_risks", [])]
    return L


MARK_STYLE = {"KEEP": "#e6f4ea;color:#137333", "NEW": "#e8f0fe;color:#1a56c4", "EDIT": "#fef7e0;color:#9a6700", "REMOVE": "#fce8e6;color:#b3261e", "REDUCE": "#fce8e6;color:#b3261e"}
MARK_COLOR = {"KEEP": "#137333", "NEW": "#1a56c4", "EDIT": "#9a6700", "REMOVE": "#b3261e", "REDUCE": "#b3261e"}
# Darstellung der Blöcke im Google Doc: Label (klein, fett, Versalien) + Inhalt. Keine großen Hintergrundflächen.
BLOCK_STYLE = {
    "why": ("Warum diese Änderung?", "color:#5f6368;font-size:9pt;font-weight:bold", "color:#5f6368;font-style:italic"),
    "old": ("BISHERIGER WEBSITE-TEXT", "color:#80868b;font-size:8pt;font-weight:bold;letter-spacing:1px", "color:#80868b"),
    "new": ("NEUER WEBSITE-TEXT – ZUM ÜBERNEHMEN", "color:#1a56c4;font-size:8pt;font-weight:bold;letter-spacing:1px", "color:#202124"),
    "diff": ("ÄNDERUNG IM DETAIL (ALT → NEU)", "color:#5f6368;font-size:8pt;font-weight:bold;letter-spacing:1px", "color:#202124"),
    "position": ("POSITION AUF DER SEITE", "color:#5f6368;font-size:8pt;font-weight:bold;letter-spacing:1px", "color:#5f6368;font-style:italic"),
    "layout": ("BILD / LAYOUT", "color:#5f6368;font-size:8pt;font-weight:bold;letter-spacing:1px", "color:#5f6368;font-style:italic"),
    "risk": ("SEO-/RANKING-RISIKO", "color:#b3261e;font-size:8pt;font-weight:bold;letter-spacing:1px", "color:#5f6368;font-style:italic"),
}


def _optimize_brief(R, o):
    """OPTIMIZE/MERGE: bestehende Rankings schützen, minimal notwendige Veränderung, Change-Modus im Dokument."""
    P, rp = R.get("P_diagnosis") or {}, o.get("ranking_protection") or {}
    L = ["", "## Bestehende Seite: Preserve what works → fix what is weak → add what is missing",
         f"- Prinzip: {P.get('principle') or (rp.get('strength') or {}).get('mode') or 'Nicht neu schreiben, nur gezielt verbessern.'}",
         "- **Nicht neu schreiben, nur weil man es besser schreiben könnte.** Bestehende Abschnitte, die Schutz-Queries tragen, bleiben inhaltlich erhalten."]
    for k, lab in (("keep", "KEEP"), ("improve", "IMPROVE"), ("add", "ADD"), ("remove", "REMOVE/REDUCE")):
        if P.get(k):
            L += [f"- {lab}:"] + [f"  - {x['item']} – {x.get('reason', '')}" for x in P[k]]
    if P.get("sensitive_changes"):
        L += ["- SEO-sensible Änderungen (nur diese, genau so):"] + [f"  - {x['element']}: „{x['current']}“ → „{x['proposed']}“ ({x['reason']}; Risiko {x['ranking_risk']})" for x in P["sensitive_changes"]]
    if P.get("not_changed"):
        L += [f"- Nicht ändern: {', '.join(P['not_changed'])}. URL/Canonical/Redirect nie umsetzen, nur empfehlen."]
    prot = [x for x in rp.get("queries", []) if x["tier"] in ("critical", "high", "watch")]
    if prot:
        L += ["", "### Ranking Protection List (diese Queries müssen im Text abgedeckt bleiben)"] + \
             [f"- [{x['tier']}] {x['query']} – Pos. {x['position']}, {x.get('impressions')} Impr.; getragen von: {', '.join(h['element'] + ' „' + (h.get('text') or '')[:50] + '“' for h in x.get('supported_by', [])) or '–'}" for x in prot]
    L += ["", "### Change-Modus im Dokument (Pflicht) – Agent-Notizen und Website-Text NIE vermischen",
          "- Dokument beginnt mit `## Change Summary` als Tabelle: Bereich | Aktion | Grund | SEO-Risiko (Vorlage: Dossier P_diagnosis.change_summary).",
          "- Jeder Abschnitt: Überschrift `## [EDIT] H2: <Überschrift>` (bzw. [NEW]/[KEEP]/[REMOVE], H3 analog). Danach NUR Blöcke:",
          "  - `:::why` … `:::` – Warum diese Änderung? (Agent-Notiz, 1–3 Sätze; wird kursiv/grau dargestellt)",
          "  - `:::old` … `:::` – BISHERIGER WEBSITE-TEXT (wörtlich von der Live-Seite)",
          "  - `:::new` … `:::` – NEUER WEBSITE-TEXT – ZUM ÜBERNEHMEN (vollständig ausformuliert, direkt verwendbar, keine Hinweise darin)",
          "  - `:::diff` … `:::` – bei kleinen Formulierungsänderungen: Zeilen `Alt: …` und `Neu: …` (wird als Wort-Diff gerendert)",
          "  - `:::position` … `:::` – nur [NEW]: genaue Position auf der bestehenden Seite (nach/vor welchem Abschnitt)",
          "  - `:::layout` … `:::` – optional: Bild-/Layout-Empfehlung (z. B. „Text links, Bild rechts – bestehenden Block duplizieren“)",
          "  - `:::risk` … `:::` – nur [REMOVE]: SEO-/Ranking-Risiko",
          "- Pflicht je Aktion: [EDIT] why + old + new (diff zusätzlich bei kleinen Änderungen) · [NEW] why + position + new · [KEEP] nur why (kein Volltext abdrucken) · [REMOVE] old + why + risk (nur Vorschlag).",
          "- Kein Text außerhalb der Blöcke innerhalb eines markierten Abschnitts. Interne Anweisungen gehören nur in why/position/layout/risk.",
          "- Vor dem Anlegen prüfen: `python3 tools/workflow.py check-draft <draft.md> --opp <OPP>` (Exit 0 nötig); dann `render` → HTML für Google Docs."]
    return L


BLOCKS = ("why", "old", "new", "diff", "position", "layout", "risk")
REQUIRED = {"EDIT": ("why", "old", "new"), "NEW": ("why", "position", "new"), "KEEP": ("why",), "REMOVE": ("old", "why", "risk"), "REDUCE": ("old", "why", "new")}


def _blocks(txt):
    """:::name … ::: → {name: [Inhalt, …]} und Rest außerhalb von Blöcken."""
    found, rest, cur, buf = {}, [], None, []
    for ln in txt.splitlines():
        m = re.match(r"^:::\s*(\w+)\s*$", ln.strip())
        if cur is None and m and m.group(1) in BLOCKS:
            cur, buf = m.group(1), []
        elif cur is not None and ln.strip() == ":::":
            found.setdefault(cur, []).append("\n".join(buf).strip()); cur = None
        elif cur is not None:
            buf.append(ln)
        else:
            rest.append(ln)
    return found, "\n".join(rest).strip(), cur


def check_draft(path, opp=None, client=DEFAULT_CLIENT):
    """QA für OPTIMIZE-Entwürfe: Change Summary, Markierung je Abschnitt, Pflichtblöcke je Aktion (why/old/new/position/risk),
    strikte Trennung Agent-Notiz ↔ Website-Text, Schutz-Queries noch abgedeckt. Altes Format (Reason:) → Fehler mit Hinweis."""
    t = open(path, encoding="utf-8").read()
    errs, warns = [], []
    if not re.search(r"^##\s+Change Summary", t, re.M):
        errs.append("Change Summary fehlt (## Change Summary)")
    elif not re.search(r"\|\s*Bereich\s*\|\s*Aktion\s*\|\s*Grund\s*\|\s*SEO-Risiko", t):
        errs.append("Change Summary ohne Tabelle Bereich | Aktion | Grund | SEO-Risiko")
    body = re.split(r"^##\s+Change Summary.*?$", t, flags=re.M)[-1]
    secs = re.split(r"^(#{2,3}\s+.*)$", body, flags=re.M)
    for i in range(1, len(secs), 2):
        head, txt = secs[i], secs[i + 1] if i + 1 < len(secs) else ""
        if re.match(r"^##\s+(Interner Block|SEO|Meta|Schema|Bildhinweise|Interne Links|Redirect)", head, re.I):
            continue
        m = re.search(r"\[(KEEP|NEW|EDIT|REMOVE|REDUCE)\]", head)
        if not m:
            if re.search(r"\[(KEEP|NEW|EDIT|REMOVE|REDUCE)\]", txt[:300]) or txt.strip():
                errs.append(f"Abschnitt ohne Change-Markierung in der Überschrift: {head.strip()[:60]}")
            continue
        act, name = m.group(1), head.strip()[:60]
        bl, rest, open_ = _blocks(txt)
        if open_:
            errs.append(f"Block :::{open_} nicht geschlossen: {name}")
        if re.search(r"^(Reason|Grund):", txt, re.M) and not bl:
            errs.append(f"Altes Format (Reason:) – bitte in :::why/:::old/:::new-Blöcke überführen: {name}"); continue
        for need in REQUIRED[act]:
            if not any(x.strip() for x in bl.get(need, [])):
                errs.append(f"[{act}] ohne :::{need}: {name}")
        if act == "KEEP" and bl.get("new"):
            warns.append(f"[KEEP] mit :::new – unveränderte Abschnitte nicht neu abdrucken: {name}")
        if rest:
            errs.append(f"Text außerhalb der Blöcke (Website-Text und Agent-Notiz trennen): {name}")
        for n in bl.get("new", []):
            if re.search(r"(?im)^(reason|grund|hinweis|agent|todo|anmerkung)\s*:", n) or ":::" in n:
                errs.append(f"Interne Notiz im neuen Website-Text: {name}")
        for d in bl.get("diff", []):
            if not (re.search(r"(?m)^Alt:", d) and re.search(r"(?m)^Neu:", d)):
                errs.append(f":::diff braucht Zeilen „Alt:“ und „Neu:“: {name}")
    if opp:
        d = _dash(client)
        o = next((x for x in d["opportunities"] if x["id"] == opp), {})
        low = t.lower()
        for q in (o.get("ranking_protection") or {}).get("queries", []):
            if q["tier"] in ("critical", "high") and not all(tok in low for tok in re.split(r"\s+", q["query"].lower()) if tok not in ("mit", "per", "drohne", "drohnen")):
                warns.append(f"Schutz-Query nicht mehr vollständig im Text: „{q['query']}“")
    return {"ok": not errs and not warns, "errors": errs, "warnings": warns}


def _inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\[(KEEP|NEW|EDIT|REMOVE|REDUCE)\]", lambda m: f'<span style="color:{MARK_COLOR[m.group(1)]};font-weight:bold">[{m.group(1)}]</span>', t)
    t = re.sub(r"^(Reason|Grund):", r'<i style="color:#5f6368">\1:</i>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def word_diff(old, new):
    """Wort-Diff für kleine Formulierungsänderungen: entfernt = rot durchgestrichen, neu = grün fett (ohne Hintergrund)."""
    import difflib
    a, b = old.split(), new.split()
    o_out, n_out = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        A, B = html.escape(" ".join(a[i1:i2])), html.escape(" ".join(b[j1:j2]))
        if op == "equal":
            o_out.append(A); n_out.append(B)
        else:
            if A:
                o_out.append(f'<span style="color:#b3261e;text-decoration:line-through">{A}</span>')
            if B:
                n_out.append(f'<span style="color:#137333;font-weight:bold">{B}</span>')
    return " ".join(o_out), " ".join(n_out)


def _md(lines, style=""):
    """Markdown-Subset → HTML (Überschriften, Absätze, Listen, Tabellen, Fett/Kursiv, Links, Trennlinie, Zitat); style = Absatzstil."""
    H, i, st = [], 0, f' style="{style}"' if style else ""
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            n = len(m.group(1)); H.append(f"<h{n}>{_inline(m.group(2))}</h{n}>"); i += 1; continue
        if ln.strip() == "---":
            H.append("<hr>"); i += 1; continue
        if ln.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                # Zellen an nicht-maskierten "|" trennen; "\|" bleibt als Zeichen erhalten (z. B. im SEO-Title)
                raw = lines[i].strip()
                raw = raw[1:] if raw.startswith("|") else raw
                raw = raw[:-1] if raw.endswith("|") and not raw.endswith("\\|") else raw
                cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", raw)]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            H.append('<table border="1" cellpadding="6">')
            for r, cells in enumerate(rows):
                tag = "th" if r == 0 else "td"
                H.append("<tr>" + "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells) + "</tr>")
            H.append("</table>"); continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", ln):
            ordered = bool(re.match(r"^\s*\d+\.", ln)); tag = "ol" if ordered else "ul"
            H.append(f"<{tag}>")
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                H.append(f"<li{st}>" + _inline(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i])) + "</li>"); i += 1
            H.append(f"</{tag}>"); continue
        if ln.startswith(">"):
            H.append("<blockquote>" + _inline(ln.lstrip("> ")) + "</blockquote>"); i += 1; continue
        para = [ln]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|\||\s*([-*]|\d+\.)\s|>|---)", lines[i]):
            para.append(lines[i].rstrip()); i += 1
        H.append(f"<p{st}>" + _inline(" ".join(para)) + "</p>")
    return H


def render(src, out):
    """Entwurf → HTML für die Google-Doc-Konvertierung. Change-Blöcke (:::why/old/new/diff/position/layout/risk) werden als echte
    Formatierung erzeugt: Agent-Notizen kursiv/grau, bisheriger Text grau, neuer Text hervorgehoben mit eindeutigem Label,
    Wort-Diff bei kleinen Änderungen, Leerraum zwischen markierten Abschnitten. Keine Markdown-Symbole im Dokument."""
    lines = open(src, encoding="utf-8").read().splitlines()
    H, buf, i, first_mark, act = ['<html><head><meta charset="utf-8"></head><body>'], [], 0, True, None
    def flush():
        H.extend(_md(buf)); buf.clear()
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^:::\s*(\w+)\s*$", ln.strip())
        if m and m.group(1) in BLOCK_STYLE:
            flush()
            name, body = m.group(1), []
            i += 1
            while i < len(lines) and lines[i].strip() != ":::":
                body.append(lines[i]); i += 1
            i += 1
            label, lst, cst = BLOCK_STYLE[name]
            if name == "why":
                label = {"KEEP": "Warum bleibt der Abschnitt?", "REMOVE": "Warum entfernen?"}.get(act, label)
            H.append(f'<p style="margin-top:10pt;margin-bottom:2pt"><span style="{lst}">{label}</span></p>')
            if name == "diff":
                txt = "\n".join(body)
                o = re.search(r"(?m)^Alt:\s*(.*)$", txt); n = re.search(r"(?m)^Neu:\s*(.*)$", txt)
                if o and n:
                    a, b = word_diff(o.group(1), n.group(1))
                    H.append(f'<p><span style="color:#5f6368;font-weight:bold">Alt: </span><span style="color:#5f6368">{a}</span></p>')
                    H.append(f'<p><span style="color:#5f6368;font-weight:bold">Neu: </span>{b}</p>')
                else:
                    H.extend(_md(body, cst))
            else:
                H.extend(_md(body, cst))
            continue
        mk = re.match(r"^#{2,3}\s+.*\[(KEEP|NEW|EDIT|REMOVE|REDUCE)\]", ln)
        if mk:
            flush(); act = mk.group(1)
            if not first_mark:
                H.append("<p>&nbsp;</p><hr>")  # deutlicher Abstand zwischen Abschnitten
            first_mark = False
        buf.append(ln); i += 1
    flush()
    H.append("</body></html>")
    open(out, "w", encoding="utf-8").write("\n".join(H))
    print(f"✓ HTML → {out} ({os.path.getsize(out)} Bytes)")


def mirror(d, client=DEFAULT_CLIENT):
    docs = load_export(d)
    # Veröffentlichte WordPress-Änderungen ins Change Log übernehmen (Monitoring T+7…T+90), idempotent
    chp = os.path.join(ROOT, "clients", client, "state", "changes.json")
    if os.path.exists(chp):
        ch = json.load(open(chp, encoding="utf-8")); ids = {x["id"] for x in ch.get("changes", [])}; added = 0
        for did, w in docs.items():
            e = ((w.get("wordpress") or {}).get("published") or {}).get("change_entry")
            if e and e.get("id") not in ids:
                ch["changes"].append(e); ids.add(e["id"]); added += 1
        if added:
            json.dump(ch, open(chp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"✓ {added} WordPress-Veröffentlichung(en) ins Change Log übernommen")
    items = []
    for did, w in sorted(docs.items()):
        w = {k: v for k, v in w.items() if not k.startswith("_")}
        items.append({"id": did, **w})
    p = os.path.join(ROOT, "clients", client, "state", "workflow.json")
    import datetime as dt
    json.dump({"_doc": "Git-Spiegel der Artifact-db-Collection 'workflow' (SSOT ist die db). Vom Agenten nach jedem Workflow-Lauf geschrieben.",
               "updated": dt.date.today().isoformat(), "items": items}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(p, "a").write("\n")
    print(f"✓ {len(items)} Workflow-Einträge → {p}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "queue":
        print(json.dumps(actions(load_export(a[1])), ensure_ascii=False, indent=2))
    elif a[0] == "brief":
        brief(a[1], a[2], a[3])
    elif a[0] == "render":
        render(a[1], a[2])
    elif a[0] == "preflight":
        r = preflight(a[1], "--drive-ok" in a, "--folder-ok" in a); sys.exit(0 if r["ok"] else 2)
    elif a[0] == "doc-title":
        docs = load_export(a[1]); w = docs[a[2]]
        try:
            o = next((x for x in _dash(DEFAULT_CLIENT)["opportunities"] if x["id"] == a[2]), None)
        except Exception:
            o = None
        print(doc_title(w, o, a[a.index("--companion") + 1] if "--companion" in a else None))
    elif a[0] == "check-active":
        docs = load_export(a[1]); r = check_active(docs.get(a[2]) or {})
        print(json.dumps(r, ensure_ascii=False)); sys.exit(0 if r["active"] else 3)
    elif a[0] == "check-draft":
        r = check_draft(a[1], a[a.index("--opp") + 1] if "--opp" in a else None)
        print(json.dumps(r, ensure_ascii=False, indent=2)); sys.exit(0 if r["ok"] else 1)
    elif a[0] == "mirror":
        mirror(a[1], a[a.index("--client") + 1] if "--client" in a else DEFAULT_CLIENT)
    else:
        sys.exit(__doc__)
