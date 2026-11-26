#!/usr/bin/env python3
"""WordPress-Produktion: Gate 2 → WordPress Draft → WordPress QA → Gate 3 → Live Update → Monitoring.

Dieses Modul ruft WordPress nie selbst auf. Der Runner liest/schreibt über den WordPress.com-Konnektor (Jetpack) und
MUSS vor JEDEM Schreibaufruf `guard` ausführen – Exit ≠ 0 = Aufruf verboten. Die Sperre liegt damit im Code
(Status der Artifact-db), nicht nur im Prompt.

    python3 tools/wordpress.py preflight <observed.json>                       -> WordPress-Preflight (Exit 2 = blocked)
    python3 tools/wordpress.py guard <op> <wf_doc.json> [--post <id>] [--fields a,b] [--status s] [--slug s] [--payload elementor.json]
                                                                               -> Schreibsperre (Exit 0 = erlaubt, 3 = verboten)
    python3 tools/wordpress.py snapshot <page_edit.json> <yoast.json> <out.json> -> Pre-change Snapshot (+ SHA-256)
    python3 tools/wordpress.py verify-snapshot <snapshot.json> [--sha <hash>]  -> vollständig & unverändert?
    python3 tools/wordpress.py firewall-check <page_edit.json|elementor.json>  -> Widgets, die die Hosting-Firewall blockiert (Exit 4 = blockiert)
    python3 tools/wordpress.py qa <change_set.json> <original_edit.json|-> <draft_edit.json> <draft_yoast.json> [--opp OPP]
                                                                               -> WordPress QA (Content · SEO · Technical · Visual)
Konfiguration: clients/<client>/client.json → "wordpress".
"""
import hashlib, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CLIENT = "spreewald-luftaufnahmen"

# Schreiboperationen und ihre Bedingungen. Alles, was hier nicht steht, ist verboten.
DRAFT_OPS = {"create_draft", "update_draft", "yoast_update_draft", "media_upload"}
LIVE_OPS = {"live_update", "publish_draft", "yoast_update_live"}
CONFIRM_OPS = {"delete", "slug_change_live", "redirect", "canonical_change", "robots_change", "settings_change", "plugin_change", "menu_change", "unpublish"}
SENSITIVE_FIELDS = {"slug": "slug_change_live", "status": "unpublish", "canonical": "canonical_change", "noindex": "robots_change",
                    "nofollow": "robots_change", "noarchive": "robots_change", "nosnippet": "robots_change", "noimageindex": "robots_change"}
STATES = ("not_started", "queued", "preparing", "draft_ready", "qa_failed", "qa_passed", "blocked", "publish_queued", "publishing", "published", "publish_failed", "rolled_back")


def cfg(client=DEFAULT_CLIENT):
    c = json.load(open(os.path.join(ROOT, "clients", client, "client.json"), encoding="utf-8"))
    return c.get("wordpress") or {}


# ---------------------------------------------------------------- Preflight
def preflight(obs, client=DEFAULT_CLIENT):
    """obs (vom Runner beobachtet): {tools: [...geladene Tool-Namen], sites: [{blog_id, site_url, platform}], role, abilities: [...]}.
    Nie auf eine andere Website ausweichen: Ziel ausschließlich per konfigurierter Blog-ID + Domain."""
    c = cfg(client)
    want_id, want_dom = str(c.get("blog_id")), (c.get("domain") or "").lower()
    tools = set(obs.get("tools") or [])
    checks = {"connector_available": any(t.startswith("mcp__WordPress_com__") for t in tools)}
    site = next((s for s in obs.get("sites") or [] if str(s.get("blog_id")) == want_id), None)
    checks["target_site"] = bool(site) and want_dom in (site.get("site_url") or "").lower()
    checks["correct_blog_id"] = bool(site)
    need_tools = {f"mcp__WordPress_com__{t}" for t in c.get("required_tools", [])}
    checks["read_write_capabilities"] = need_tools <= tools and obs.get("role") in tuple(c.get("allowed_roles", ["administrator", "editor"]))
    checks["yoast_abilities"] = set(c.get("required_abilities", [])) <= set(obs.get("abilities") or [])
    reason = None
    if not checks["connector_available"]:
        reason = "wp_connector_unavailable"
    elif not checks["correct_blog_id"] or not checks["target_site"]:
        reason = "wp_wrong_site"
    elif not checks["read_write_capabilities"]:
        reason = "wp_capabilities_missing"
    elif not checks["yoast_abilities"]:
        reason = "wp_yoast_unavailable"
    return {"ok": reason is None, "checks": checks, "block_reason": reason, "blog_id": want_id,
            "detail": {"wp_connector_unavailable": "WordPress.com-Konnektor im Lauf nicht verfügbar – kein WordPress-Schreibzugriff",
                       "wp_wrong_site": f"Zielwebsite {want_dom} (Blog-ID {want_id}) nicht erreichbar – nie auf eine andere Website ausweichen",
                       "wp_capabilities_missing": "Benötigte Lese-/Schreibrechte oder Werkzeuge fehlen",
                       "wp_yoast_unavailable": "Yoast-Fähigkeiten der Website nicht verfügbar"}.get(reason)}


# ---------------------------------------------------------------- Harte Schreibsperre
def firewall_risk(tree_or_raw, client=DEFAULT_CLIENT):
    """Sandbox-Test 24.11.2026: Die Firewall (vermutlich NinjaFirewall-Plugin) beantwortet Schreibaufrufe, deren Inhalt <script> enthält, mit HTTP 403
    (atomar, nichts geschrieben). Liefert die betroffenen Widgets, BEVOR ein Schreibaufruf versucht wird."""
    pats = ((cfg(client).get("capabilities_verified") or {}).get("firewall_blocks_patterns")) or ["<script"]
    tree = json.loads(tree_or_raw) if isinstance(tree_or_raw, str) else (_tree(tree_or_raw) if isinstance(tree_or_raw, dict) else tree_or_raw or [])
    hits = []
    def walk(nodes, top):
        for n in nodes:
            s = json.dumps(n.get("settings") or {}, ensure_ascii=False).lower()
            if n.get("elType") == "widget" and any(p.lower() in s for p in pats):
                hits.append({"id": n.get("id"), "type": n.get("widgetType"), "section": top, "pattern": next(p for p in pats if p.lower() in s)})
            walk(n.get("elements") or [], top)
    for i, n in enumerate(tree):
        walk([n], i)
    return {"blocked": bool(hits), "widgets": hits, "patterns": pats,
            "why": f"{len(hits)} Widget(s) mit {', '.join(sorted({h['pattern'] for h in hits}))} – Firewall antwortet mit HTTP 403" if hits else None}


def guard(op, w, post=None, fields=None, status=None, slug=None, live_slugs=(), client=DEFAULT_CLIENT, payload=None):
    """Darf diese WordPress-Schreiboperation jetzt ausgeführt werden? w = Workflow-Dokument (Artifact-db).
    payload = zu schreibendes _elementor_data (optional) → Firewall-Vorprüfung."""
    c, wp = cfg(client), (w or {}).get("wordpress") or {}
    fields = set(fields or [])
    deny = lambda code, why: {"allowed": False, "op": op, "code": code, "why": why}  # noqa: E731
    mode = wp.get("mode") or (((w or {}).get("gate1") or {}).get("change_set") or {}).get("action")
    if mode and mode != "CREATE" and op in DRAFT_OPS | LIVE_OPS and c.get("optimize_automation", "disabled") != "enabled":
        return deny("optimize_manual_only", "OPTIMIZE wird manuell in Elementor umgesetzt – kein WordPress-Draft, kein Schreiben auf bestehende Seiten, kein Publish")
    dst = ((w or {}).get("decision") or {}).get("status") or "active"
    if dst in ("on_hold", "rejected"):
        return deny(f"decision_{dst}", "Opportunity " + ("zurückgestellt (ON HOLD)" if dst == "on_hold" else "abgelehnt (REJECTED)") + " – kein WordPress-Schreibvorgang")
    if payload is not None and op in DRAFT_OPS | LIVE_OPS:
        fr = firewall_risk(payload, client)
        if fr["blocked"]:
            return {**deny("payload_blocked_by_firewall", fr["why"] + " – nicht umgehen (keine Kodierungs-Tricks)"), "widgets": fr["widgets"]}
    if op in CONFIRM_OPS:
        conf = [x for x in (w.get("confirmations") or []) if x.get("op") == op and str(x.get("post")) == str(post) and x.get("status") == "confirmed"]
        if not conf:
            return deny("requires_explicit_confirmation", f"{op} nie automatisch – gesonderte ausdrückliche Bestätigung nötig")
        return {"allowed": True, "op": op, "code": "confirmed", "why": "ausdrücklich bestätigt"}
    if op not in DRAFT_OPS | LIVE_OPS:
        return deny("unknown_operation", "Operation nicht vorgesehen")
    if (w.get("gate2") or {}).get("status") != "approved":
        return deny("gate2_missing", "Ohne Gate 2 kein WordPress-Schreibzugriff")
    # sensible Felder sind nie Teil eines automatischen Schreibvorgangs
    bad = sorted(f for f in fields if f in SENSITIVE_FIELDS and not (op in ("create_draft",) and f in ("slug", "status")))
    if bad:
        return deny("sensitive_field", f"Felder {', '.join(bad)} nie automatisch ändern")
    registry = {str(d.get("draft_post_id")) for d in wp.get("documents") or [] if d.get("draft_post_id")}
    if op == "create_draft":
        if status not in ("draft", None):
            return deny("status_not_draft", "Neue Seiten nur mit status=draft")
        if slug and slug in set(live_slugs):
            return deny("slug_in_use", f"Slug „{slug}“ gehört einer veröffentlichten Seite")
        return {"allowed": True, "op": op, "code": "ok", "why": "Draft nach Gate 2"}
    if op in ("update_draft", "yoast_update_draft", "media_upload"):
        if op != "media_upload" and str(post) not in registry:
            return deny("not_agent_draft", "Nur vom Agenten angelegte Draft-Seiten dürfen bearbeitet werden – nie eine veröffentlichte Seite")
        if status and status != "draft":
            return deny("status_not_draft", "Draft bleibt draft")
        return {"allowed": True, "op": op, "code": "ok", "why": "Bearbeitung des eigenen Drafts"}
    # LIVE: Gate 3 + exakte Version + QA + Snapshot + Rollback
    g3 = w.get("gate3") or {}
    if g3.get("status") != "approved":
        return deny("gate3_missing", "gate3 != approved – jeder Live-Schreibvorgang gesperrt")
    if g3.get("for_draft_version") != wp.get("draft_version"):
        return deny("gate3_version_mismatch", "Gate 3 bezieht sich auf eine andere Draft-Version")
    if wp.get("qa", {}).get("overall") not in ("passed", "passed_manual_visual"):
        return deny("qa_not_passed", "WordPress QA nicht bestanden")
    if wp.get("qa", {}).get("overall") == "passed_manual_visual" and not g3.get("visual_review_confirmed"):
        return deny("visual_review_missing", "Sichtprüfung (Desktop/Tablet/Mobile) nicht bestätigt")
    em = (c.get("capabilities_verified") or {}).get("elementor") or {}
    if wp.get("mode") == "OPTIMIZE" and op in ("live_update", "yoast_update_live") and em.get("live_optimize_automation") != "VERIFIED":
        return deny("live_optimize_blocked", f"Live OPTIMIZE automation: {em.get('live_optimize_automation', 'NOT VERIFIED')} (Sandbox-Status) – kein automatisches Live-Update bestehender Seiten")
    if wp.get("mode") == "CREATE" and op == "publish_draft" and em.get("create_automation") != "VERIFIED":
        return deny("create_automation_pending", f"CREATE automation: {em.get('create_automation', 'NOT VERIFIED')} – Veröffentlichen erst nach vollständiger Sandbox-Validierung")
    if op in ("live_update", "yoast_update_live"):
        rb = wp.get("rollback") or {}
        if rb.get("status") != "available":
            return deny("rollback_unavailable", "Rollback protection unavailable – kein Live-Update")
        targets = {str(d.get("wp_post_id")) for d in wp.get("documents") or [] if d.get("wp_post_id")}
        if str(post) not in targets:
            return deny("not_in_change_set", "Seite gehört nicht zum freigegebenen Change Set")
        snaps = {str(s.get("post")) for s in wp.get("snapshots") or [] if s.get("verified")}
        if str(post) not in snaps:
            return deny("snapshot_missing", "Kein verifizierter Pre-change Snapshot für diese Seite")
    if op == "publish_draft" and str(post) not in registry:
        return deny("not_agent_draft", "Nur der freigegebene Agenten-Draft darf veröffentlicht werden")
    return {"allowed": True, "op": op, "code": "ok", "why": "Gate 3 erteilt, QA bestanden, Rollback gesichert"}


# ---------------------------------------------------------------- Snapshot & Rollback
def snapshot(page_edit, yoast, taken_at):
    """Pre-change Snapshot einer Live-Seite: Elementor-Daten, Content, Yoast, Seiteneinstellungen, Zeitstempel."""
    d = page_edit.get("data", page_edit)
    m = d.get("meta") or {}
    y = (yoast.get("data") if isinstance(yoast, dict) else yoast) or []
    y = y[0] if isinstance(y, list) and y else y
    snap = {"post": d.get("id"), "slug": d.get("slug"), "status": d.get("status"), "link": d.get("link"), "template": d.get("template"),
            "modified": d.get("modified"), "title": (d.get("title") or {}).get("raw") if isinstance(d.get("title"), dict) else d.get("title"),
            "content_raw": (d.get("content") or {}).get("raw") if isinstance(d.get("content"), dict) else d.get("content"),
            "elementor": {k: m.get(k) for k in ("_elementor_data", "_elementor_page_settings", "_elementor_edit_mode", "_elementor_template_type", "_elementor_conditions") if k in m},
            "yoast": {k: y.get(k) for k in ("seo_title", "meta_description", "focus_keyphrase", "canonical", "noindex", "nofollow", "schema_page_type", "open_graph_title", "open_graph_description")} if isinstance(y, dict) else None,
            "taken_at": taken_at}
    snap["sha256"] = hashlib.sha256(json.dumps(snap, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return snap


def verify_snapshot(snap, sha=None):
    """Vollständig (alle Rollback-relevanten Teile vorhanden, Elementor-JSON lesbar) und unverändert (Hash)?"""
    missing = [k for k in ("post", "slug", "status", "taken_at") if not snap.get(k)]
    el = snap.get("elementor") or {}
    try:
        tree = json.loads(el["_elementor_data"]) if isinstance(el.get("_elementor_data"), str) else el.get("_elementor_data")
        if not isinstance(tree, list) or not tree:
            missing.append("_elementor_data")
    except Exception:
        missing.append("_elementor_data (nicht lesbar)")
    if el.get("_elementor_edit_mode") != "builder":
        missing.append("_elementor_edit_mode")
    if not snap.get("yoast"):
        missing.append("yoast")
    body = {k: v for k, v in snap.items() if k != "sha256"}
    actual = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    ok_hash = actual == (sha or snap.get("sha256"))
    return {"verified": not missing and ok_hash, "missing": missing, "hash_ok": ok_hash, "sha256": actual}


def rollback_status(snapshots, capabilities):
    """Rollback geschützt, wenn: jede Ziel-Seite einen verifizierten Snapshot hat, der Snapshot dauerhaft gespeichert ist (Drive)
    und der Schreibweg für _elementor_data + Yoast nachweislich funktioniert (Schreibtest). WP-Revisionen sind zweite Linie."""
    why = []
    if not snapshots:
        why.append("kein Pre-change Snapshot")
    if any(not s.get("verified") for s in snapshots or []):
        why.append("Snapshot nicht verifiziert")
    if any(not s.get("stored_doc_id") for s in snapshots or []):
        why.append("Snapshot nicht dauerhaft gespeichert (Drive)")
    if not capabilities.get("elementor_meta_write_verified"):
        why.append("Schreiben von _elementor_data nicht durch Schreibtest bestätigt")
    if not capabilities.get("yoast_write_available"):
        why.append("Yoast-Schreibweg nicht verfügbar")
    return {"status": "available" if not why else "unavailable", "why": why,
            "secondary": "WordPress-Revisionen (wpcom-manage-revisions)" if capabilities.get("revisions_available") else None}


# ---------------------------------------------------------------- Elementor-Analyse & QA
def _tree(x):
    d = x.get("data", x) if isinstance(x, dict) else {}
    raw = ((d.get("meta") or {}).get("_elementor_data")) if "meta" in d else d.get("_elementor_data")
    return json.loads(raw) if isinstance(raw, str) else (raw or [])


def _strip(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()


def widgets(tree):
    """Flache Liste der Widgets in Reihenfolge: (id, type, text, extras)."""
    out = []
    def walk(nodes):
        for n in nodes:
            wt = n.get("widgetType")
            s = n.get("settings") or {}
            if wt:
                text = _strip(s.get("title") or s.get("editor") or s.get("text") or s.get("description_text") or "")
                out.append({"id": n.get("id"), "type": wt, "tag": s.get("header_size"), "text": text,
                            "link": (s.get("link") or {}).get("url") if isinstance(s.get("link"), dict) else None,
                            "image": (s.get("image") or {}).get("url") if isinstance(s.get("image"), dict) else None,
                            "images": [i.get("url") for i in s.get("carousel") or [] if isinstance(i, dict)]})
            walk(n.get("elements") or [])
    walk(tree)
    return out


def sections(ws):
    """Abschnitte = Überschrift (H1–H3) + folgende Widgets bis zur nächsten Überschrift."""
    secs, cur = [], {"heading": "(Anfang)", "tag": None, "widgets": []}
    for w in ws:
        if w["type"] == "heading" and (w.get("tag") in (None, "h1", "h2", "h3")):
            secs.append(cur); cur = {"heading": w["text"], "tag": w.get("tag") or "h2", "widgets": [w]}
        else:
            cur["widgets"].append(w)
    secs.append(cur)
    return [s for s in secs if s["widgets"]]


def _norm(t):
    return re.sub(r"[^a-z0-9äöüß ]+", "", (t or "").lower()).strip()


def qa(change_set, original, draft, draft_yoast, plan=None):
    """WordPress QA gegen das freigegebene Change Set. change_set = {mode, primary_keyword, sections: [{heading, action, existing}], seo: {title, meta_description, h1, focus_keyphrase},
    internal_links: [{to, anchor}], canonical, companions: [...] }. Visuelle Prüfung wird nie erfunden."""
    res = {"content": {"status": "passed", "issues": []}, "seo": {"status": "passed", "issues": []}, "technical": {"status": "passed", "issues": []},
           "visual": {"status": "manual_review_required", "note": "Keine visuelle Prüfung technisch möglich (Vorschau nur eingeloggt) – Desktop/Tablet/Mobile manuell prüfen"}}
    fail = lambda part, msg: (res[part]["issues"].append(msg), res[part].__setitem__("status", "failed"))  # noqa: E731
    dw = widgets(_tree(draft)) if draft else []
    if not dw:
        fail("technical", "Draft ohne Elementor-Struktur (_elementor_data leer oder nicht lesbar)")
    ds = {_norm(s["heading"]): s for s in sections(dw)}
    cs = {_norm(x.get("existing") if x.get("existing") not in (None, "gleich") else x["heading"]): x for x in change_set.get("sections", [])}
    if original:
        ow = widgets(_tree(original))
        for s in sections(ow):
            key = _norm(s["heading"])
            plan_s = cs.get(key)
            act = (plan_s or {}).get("action", "KEEP")
            target = ds.get(_norm(plan_s["heading"])) if plan_s else ds.get(key)
            if act == "REMOVE" or act == "REDUCE":
                continue
            if not target:
                fail("content", f"Abschnitt fehlt im Draft: „{s['heading']}“ ({act})")
                continue
            if act == "KEEP":
                otext = [w["text"] for w in s["widgets"]]
                ttext = [w["text"] for w in target["widgets"]]
                if otext != ttext:
                    fail("content", f"[KEEP] „{s['heading']}“ wurde verändert – unbeabsichtigte Textänderung")
                oimg = [w.get("image") for w in s["widgets"] if w.get("image")] + [i for w in s["widgets"] for i in w.get("images") or []]
                timg = [w.get("image") for w in target["widgets"] if w.get("image")] + [i for w in target["widgets"] for i in w.get("images") or []]
                if oimg != timg:
                    fail("technical", f"[KEEP] „{s['heading']}“: Bilder geändert/fehlen")
        removed = [x["heading"] for x in change_set.get("sections", []) if x.get("action") == "REMOVE" and _norm(x["heading"]) in ds]
        for h in removed:
            fail("content", f"[REMOVE] „{h}“ ist noch im Draft")
    for x in change_set.get("sections", []):
        if x.get("action") in ("NEW", "EDIT") and _norm(x["heading"]) not in ds:
            fail("content", f"[{x['action']}] „{x['heading']}“ fehlt im Draft")
    # Technisch: Bilder, Buttons/Links, Überschriften
    for w in dw:
        if w["type"] == "image" and not w.get("image"):
            fail("technical", f"Bild-Widget ohne Bild ({w['id']})")
        if w["type"] in ("button", "call-to-action") and w.get("link") in (None, "", "#"):
            fail("technical", f"Button ohne Ziel: „{w['text'][:40]}“")
    h1 = [w for w in dw if w["type"] == "heading" and w.get("tag") == "h1"]
    if len(h1) != 1:
        fail("seo", f"{len(h1)} H1 im Draft (erwartet 1)")
    seo = change_set.get("seo") or {}
    if seo.get("h1") and h1 and _norm(h1[0]["text"]) != _norm(seo["h1"]):
        fail("seo", f"H1 weicht ab: „{h1[0]['text']}“ ≠ „{seo['h1']}“")
    y = (draft_yoast.get("data") if isinstance(draft_yoast, dict) and "data" in draft_yoast else draft_yoast) or {}
    y = y[0] if isinstance(y, list) and y else y
    if seo.get("title") and (y.get("seo_title") or "") != seo["title"]:
        fail("seo", "SEO-Title entspricht nicht dem freigegebenen Change Set")
    if seo.get("meta_description") and (y.get("meta_description") or "") != seo["meta_description"]:
        fail("seo", "Meta Description entspricht nicht dem freigegebenen Change Set")
    if change_set.get("mode") == "OPTIMIZE" and change_set.get("canonical") and y.get("canonical") not in (None, "", change_set["canonical"]):
        fail("seo", "Canonical abweichend – Canonical wird nie automatisch geändert")
    links = [w.get("link") for w in dw if w.get("link")]
    alltext = " ".join(w["text"] for w in dw)
    for l in change_set.get("internal_links") or []:
        if not any(l["to"].strip("/") in (x or "") for x in links) and l["to"].strip("/") not in json.dumps(_tree(draft)):
            fail("seo", f"Interner Link fehlt: {l['to']}")
    for q in (plan or {}).get("protected_queries", []):
        if not all(t in alltext.lower() for t in q.lower().split() if t not in ("mit", "per", "drohne", "drohnen")):
            fail("seo", f"Schutz-Query nicht mehr abgedeckt: „{q}“")
    # Focus Keyphrase: über Konnektor nicht schreibbar (Yoast-Ability ohne Feld; REST-Meta _yoast_wpseo_focuskw wird verworfen,
    # Test 25.11.2026 an Draft 6955) → nie stillschweigend weglassen, sondern als manuelle Aktion mit konkretem Keyword ausweisen.
    res["manual_actions"] = []
    kp = seo.get("focus_keyphrase") or change_set.get("primary_keyword")
    if kp:
        if (y.get("focus_keyphrase") or "").strip().lower() == kp.strip().lower():
            res["manual_actions"].append({"field": "Yoast Focus Keyphrase", "value": kp, "status": "done", "note": "in Yoast eingetragen"})
        else:
            res["manual_actions"].append({"field": "Yoast Focus Keyphrase", "value": kp, "status": "manual_action_required",
                                          "note": "Manual action required – im WordPress-Editor (Yoast-Box) eintragen; über die Schnittstelle nicht schreibbar"})
    else:
        fail("seo", "Primäre Keyphrase fehlt im Change Set (seo.focus_keyphrase bzw. primary_keyword)")
    overall = "passed_manual_visual" if all(res[p]["status"] == "passed" for p in ("content", "seo", "technical")) else "failed"
    res["overall"] = overall
    return res


def change_counts(change_set):
    c = {"NEW": 0, "EDIT": 0, "KEEP": 0, "REMOVE": 0}
    for x in change_set.get("sections", []):
        a = {"REDUCE": "REMOVE", "KEEP/EDIT": "EDIT"}.get(x.get("action"), x.get("action"))
        if a in c:
            c[a] += 1
    for x in change_set.get("meta_changes", []):
        a = x.get("action")
        if a in c:
            c[a] += 1
    return c


def publish_summary(change_set, mode):
    """Was wird beim Publish tatsächlich verändert? (kompakt, für Gate 3)"""
    out = []
    if mode == "CREATE":
        out.append(f"Neue Seite wird öffentlich unter {change_set.get('slug') or '(geplanter Slug)'}")
    for x in change_set.get("meta_changes", []):
        out.append(f"{x['area']}: „{x.get('current', '–')}“ → „{x.get('proposed')}“")
    for x in change_set.get("sections", []):
        if x.get("action") in ("NEW", "EDIT", "REMOVE", "REDUCE"):
            out.append(f"{x['action']}: {x['heading']}")
    out.append("Unverändert: URL/Slug, Canonical, Indexierung, Menüs, Einstellungen" if mode == "OPTIMIZE" else "Indexierbar nach Veröffentlichung (Yoast-Standard)")
    return out


def change_log_entry(w, opp, published_at, baseline):
    """Change-Log-Eintrag nach Publish inkl. Monitoring T+7…T+90 (Ranking Protection + Kannibalisierung)."""
    import datetime as dt
    d = dt.date.fromisoformat(published_at[:10])
    wp = w.get("wordpress") or {}
    return {"id": f"CL-WP-{opp}-{published_at[:10]}", "date": published_at[:10], "url": wp.get("documents", [{}])[0].get("url"), "title": f"{opp}: WordPress-Veröffentlichung ({wp.get('mode')})",
            "action": "; ".join(wp.get("publish_summary") or []), "by": "Workflow-Runner nach Gate 3", "status": "monitoring", "related_opportunity": opp,
            "ranking_protection_baseline": baseline, "cannibalization_watch": {"target": wp.get("documents", [{}])[0].get("url")},
            "checkpoints": [{"label": f"T+{n}", "due": (d + dt.timedelta(days=n)).isoformat(), "status": "planned", "checks": ["ranking_protection", "cannibalization"]} for n in (7, 14, 30, 60, 90)]}


# ---------------------------------------------------------------- Content Layer vs. Design/Template Layer (CREATE über Vorlage, OPTIMIZE über bestehende Seite)
# Der Agent ändert nur CONTENT_KEYS (Texte, Überschriften-Text, Bild-Zuordnung, Link-Ziele). Alles andere (Container, Abstände,
# Responsive-Werte, Farben, Typografie, Trustindex/HTML, Formulare/Heyflow, Karussells) gehört zum Design/Template Layer und bleibt.
CONTENT_KEYS = {"heading": {"title", "header_size"}, "text-editor": {"editor"}, "button": {"text", "link"}, "image": {"image", "link"},
                "icon-list": {"icon_list"}, "icon-box": {"title_text", "description_text"}, "testimonial": {"testimonial_content", "testimonial_name"}}
DESIGN_WIDGETS = {"html", "form", "image-carousel", "call-to-action", "divider", "template", "shortcode", "star-rating", "video"}


def _S(n):
    s = n.get("settings")
    return s if isinstance(s, dict) else {}


def find(tree, eid):
    for n in tree:
        if n.get("id") == eid:
            return n
        r = find(n.get("elements") or [], eid)
        if r:
            return r
    return None


def layer_of(node):
    wt = node.get("widgetType")
    if not wt:
        return "design"
    return "content" if wt in CONTENT_KEYS else "design"


def set_content(tree, eid, **values):
    """Content-Layer-Änderung an genau einem Widget. Design-Schlüssel werden abgewiesen."""
    n = find(tree, eid)
    if not n:
        raise KeyError(f"Widget {eid} nicht gefunden")
    wt = n.get("widgetType")
    allowed = CONTENT_KEYS.get(wt)
    if not allowed:
        raise PermissionError(f"{eid} ({wt or n.get('elType')}) gehört zum Design/Template Layer – nicht bearbeiten")
    bad = set(values) - allowed
    if bad:
        raise PermissionError(f"Schlüssel {sorted(bad)} gehören zum Design Layer von {wt}")
    if not isinstance(n.get("settings"), dict):
        n["settings"] = {}
    n["settings"].update(values)
    return n


def _ids(tree):
    out = set()
    for n in tree:
        out.add(n.get("id")); out |= _ids(n.get("elements") or [])
    return out


def _new_ids(node, taken, seed):
    import copy
    node = copy.deepcopy(node)
    def walk(n):
        i = 0
        while True:
            cand = hashlib.sha1(f"{seed}:{n.get('id')}:{i}".encode()).hexdigest()[:8]
            if cand not in taken:
                break
            i += 1
        taken.add(cand); n["id"] = cand
        for c in n.get("elements") or []:
            walk(c)
    walk(node)
    return node


def text_image_orientation(section):
    """'text_left' | 'image_left' | None für einen Text+Bild-Abschnitt (row-Container mit Bild-Spalte und Text-Spalte)."""
    cols = [c for c in section.get("elements") or [] if c.get("elType") == "container"]
    def kinds(n):
        k = set()
        for c in n.get("elements") or []:
            if c.get("widgetType"):
                k.add(c["widgetType"])
            k |= kinds(c)
        return k
    order = []
    for c in cols:
        k = kinds(c)
        if "image" in k and "text-editor" not in k:
            order.append("image")
        elif "text-editor" in k and "image" not in k:
            order.append("text")
    if order[:1] and set(order) == {"image", "text"}:
        return "text_left" if order.index("text") < order.index("image") else "image_left"
    return None


def alternation(tree):
    """Layoutregel: aufeinanderfolgende Text+Bild-Abschnitte alternieren. Liefert Reihenfolge + Verstöße."""
    seq = [(i, n.get("id"), text_image_orientation(n)) for i, n in enumerate(tree)]
    ti = [x for x in seq if x[2]]
    issues = []
    for a, b in zip(ti, ti[1:]):
        if a[2] == b[2]:
            issues.append({"sections": [a[0], b[0]], "orientation": a[2], "adjacent": b[0] == a[0] + 1,
                           "between": [i for i, _, o in seq if a[0] < i < b[0]]})
    return {"text_image_sections": [{"index": i, "id": e, "orientation": o} for i, e, o in ti], "issues": issues, "ok": not issues}


def duplicate_section(tree, section_id, mirror=False, after_id=None, seed="dup"):
    """Text+Bild-Block duplizieren (Design, Abstände, Responsive, Styling bleiben), neue eindeutige Elementor-IDs,
    optional gespiegelt (Text- und Bild-Spalte tauschen). Gibt die neue Sektion zurück; tree wird verändert."""
    idx = next(i for i, n in enumerate(tree) if n.get("id") == section_id)
    new = _new_ids(tree[idx], _ids(tree), seed)
    if mirror:
        if not text_image_orientation(new):
            raise ValueError(f"{section_id} ist kein Text+Bild-Abschnitt – Spiegeln nicht möglich")
        # die zwei Spalten (≠ 100 % Breite) tauschen; eine Überschrift-Zeile mit 100 % Breite bleibt oben
        side = [i for i, c in enumerate(new.get("elements") or []) if c.get("elType") == "container"
                and str((_S(c).get("width") or {}).get("size")) not in ("100", "100.0")]
        if len(side) == 2:
            a, b = side
            new["elements"][a], new["elements"][b] = new["elements"][b], new["elements"][a]
    pos = idx + 1 if after_id is None else next(i for i, n in enumerate(tree) if n.get("id") == after_id) + 1
    tree.insert(pos, new)
    return new


def script_free_copy(tree, placeholder="[Trustindex – Template-Layer, wird über Vorlage gerendert]"):
    """Für Sandbox-Tests: Script-HTML-Widgets durch eine markierte Überschrift ersetzen (Design/Template Layer, nicht Content)."""
    import copy
    t = copy.deepcopy(tree)
    def walk(nodes):
        for i, n in enumerate(nodes):
            if n.get("widgetType") == "html" and "<script" in str(_S(n).get("html", "")).lower():
                nodes[i] = {"id": n["id"], "elType": "widget", "widgetType": "heading", "elements": [],
                            "settings": {"title": placeholder, "header_size": "p", "align": "center"}}
            else:
                walk(n.get("elements") or [])
    walk(t)
    return t


def transport_json(tree):
    """Payload für den Konnektor: kompaktes JSON mit \\uXXXX-Escaping. S3 (25.11.2026): unsichtbare Zeichen (z. B. geschütztes
    Leerzeichen U+00A0) gingen bei lesbarer Ausgabe verloren – mit ASCII-Escaping bleiben sie sichtbar und exakt."""
    return json.dumps(tree, separators=(",", ":"), ensure_ascii=True)


def compare_readback(sent, got):
    """Nach jedem Schreibvorgang: gesendeten Baum mit dem zurückgelesenen vergleichen (pro Element, Settings + Typ + Reihenfolge)."""
    sent = json.loads(sent) if isinstance(sent, str) else sent
    got = json.loads(got) if isinstance(got, str) else got
    def flat(ns, out, order):
        for n in ns:
            out[n.get("id")] = n; order.append(n.get("id")); flat(n.get("elements") or [], out, order)
        return out, order
    a, oa = flat(sent, {}, []); b, ob = flat(got, {}, [])
    diffs = []
    for i in oa:
        if i not in b:
            diffs.append({"id": i, "issue": "fehlt"}); continue
        if a[i].get("widgetType") != b[i].get("widgetType") or a[i].get("elType") != b[i].get("elType"):
            diffs.append({"id": i, "issue": "Typ"})
        sa, sb = _S(a[i]), _S(b[i])
        for k in sorted(set(sa) | set(sb)):
            if sa.get(k) != sb.get(k):
                kind = "whitespace" if isinstance(sa.get(k), str) and isinstance(sb.get(k), str) and \
                    re.sub(r"\s", " ", sa[k]) == re.sub(r"\s", " ", sb[k]) else "value"
                diffs.append({"id": i, "key": k, "issue": kind})
    extra = [i for i in ob if i not in a]
    return {"identical": not diffs and not extra and oa == ob, "elements": len(oa), "diffs": diffs, "extra": extra, "order_ok": oa == ob}


TRUSTINDEX_RE = re.compile(r"cdn\.trustindex\.io/loader\.js\?([0-9a-f]+)")


def trustindex_ids(tree):
    """Trustindex-Widget-IDs (loader.js?<id>) aller HTML-Widgets → {Elementor-Widget-ID: Trustindex-ID}."""
    out = {}
    def walk(ns):
        for n in ns:
            if n.get("widgetType") == "html":
                m = TRUSTINDEX_RE.search(str(_S(n).get("html", "")))
                if m:
                    out[n["id"]] = m.group(1)
            walk(n.get("elements") or [])
    walk(tree)
    return out


def trustindex_reference_copy(tree, template_ids):
    """Kopie eines Elementor-Baums, in der jedes Trustindex-HTML-Widget durch das Elementor-Pro-Widget „Template“ ersetzt ist,
    das auf das zentrale Trustindex-Template verweist. template_ids = {Trustindex-ID: Elementor-Template-ID}.
    Element-ID und Position bleiben gleich, alle übrigen Elemente byte-gleich; Ergebnis enthält kein <script> mehr."""
    import copy
    t = copy.deepcopy(tree)
    missing = []
    def walk(ns):
        for i, n in enumerate(ns):
            if n.get("widgetType") == "html":
                m = TRUSTINDEX_RE.search(str(_S(n).get("html", "")))
                if m:
                    tid = template_ids.get(m.group(1))
                    if not tid:
                        missing.append(m.group(1)); continue
                    extra = {k: v for k, v in _S(n).items() if k != "html"}  # evtl. Abstände/Responsive des Widgets übernehmen
                    ns[i] = {"id": n["id"], "elType": "widget", "widgetType": "template", "elements": [], "settings": {"template_id": str(tid), **extra}}
                    continue
            walk(n.get("elements") or [])
    walk(t)
    if missing:
        raise KeyError(f"Kein zentrales Template für Trustindex-ID(s) {sorted(set(missing))}")
    return t


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    opt = lambda k: a[a.index(k) + 1] if k in a else None  # noqa: E731
    if a[0] == "preflight":
        r = preflight(json.load(open(a[1], encoding="utf-8"))); print(json.dumps(r, ensure_ascii=False, indent=2)); sys.exit(0 if r["ok"] else 2)
    elif a[0] == "guard":
        w = json.load(open(a[2], encoding="utf-8")); w = w.get("data", w)
        r = guard(a[1], w, opt("--post"), (opt("--fields") or "").split(",") if opt("--fields") else [], opt("--status"), opt("--slug"),
                  (opt("--live-slugs") or "").split(","), payload=json.load(open(opt("--payload"), encoding="utf-8")) if opt("--payload") else None)
        print(json.dumps(r, ensure_ascii=False)); sys.exit(0 if r["allowed"] else 3)
    elif a[0] == "snapshot":
        import datetime as dt
        s = snapshot(json.load(open(a[1], encoding="utf-8")), json.load(open(a[2], encoding="utf-8")), dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        json.dump(s, open(a[3], "w", encoding="utf-8"), ensure_ascii=False); print(json.dumps({**verify_snapshot(s), "out": a[3]}))
    elif a[0] == "verify-snapshot":
        r = verify_snapshot(json.load(open(a[1], encoding="utf-8")), opt("--sha")); print(json.dumps(r)); sys.exit(0 if r["verified"] else 1)
    elif a[0] == "firewall-check":
        r = firewall_risk(json.load(open(a[1], encoding="utf-8"))); print(json.dumps(r, ensure_ascii=False, indent=2)); sys.exit(4 if r["blocked"] else 0)
    elif a[0] == "qa":
        orig = None if a[2] == "-" else json.load(open(a[2], encoding="utf-8"))
        r = qa(json.load(open(a[1], encoding="utf-8")), orig, json.load(open(a[3], encoding="utf-8")), json.load(open(a[4], encoding="utf-8")))
        print(json.dumps(r, ensure_ascii=False, indent=2)); sys.exit(0 if r["overall"] != "failed" else 1)
    else:
        sys.exit(__doc__)
