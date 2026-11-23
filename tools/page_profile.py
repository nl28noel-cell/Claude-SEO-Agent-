#!/usr/bin/env python3
"""Seitenprofil für die SERP-/Konkurrenzanalyse (Research-Stufe der Opportunity Engine).

Lädt eine öffentliche Seite (nur lesend) und extrahiert, was für die Strategie zählt:
Title, Meta Description, H1–H3-Gliederung, Wortzahl, Themen-/Trust-/Conversion-Signale.
Keine Bewertung „mehr Wörter = besser“ – die Zahlen dienen nur als Kontext.

    python3 tools/page_profile.py <url> [<url> ...] --out <dir>     -> je URL eine JSON-Datei + Konsolenübersicht
Netzwerk: der Host muss in der Umgebung freigegeben sein (sonst: Fehler im Profil, kein Abbruch).
"""
import argparse, datetime as dt, html, json, os, re, sys
from urllib.parse import urlparse

import requests

# Signale: Thema → Regex (Groß-/Kleinschreibung egal). Bewusst breit, Treffer werden gezählt.
SIGNALS = {
    "faq": r"häufig gestellte|faq|häufige fragen",
    "preis": r"\bpreis|kosten|€|euro\b|ab \d+",
    "intervall_abo": r"intervall|wöchentlich|monatlich|regelmäßig|abo\b|paket|rahmenvertrag|meilenstein",
    "zeitraffer": r"zeitraffer|timelapse|time-lapse",
    "video": r"\bvideo",
    "orthofoto": r"orthofoto|orthomosaik",
    "3d_modell": r"3d|punktwolke|photogrammetr",
    "bim_cad": r"\bbim\b|cad\b|revit|ifc",
    "portal_cloud": r"portal|cloud|online-zugang|plattform|dashboard",
    "vermessung_volumen": r"vermess|volumen|massenberechnung|aufmaß",
    "beweissicherung": r"beweissicher|nachtrag|mängel|streit",
    "marketing": r"marketing|vermarktung|investor|social media|imagefilm",
    "referenzen": r"referenz|projekt(e|beispiel)|case study|kunden(stimmen|logos)?",
    "bewertungen": r"bewertung|sterne|rezension|google-bewert|kundenstimme",
    "zertifikat_genehmigung": r"zertifi|genehmigung|lba|kenntnisnachweis|a2|eu-drohnen|betriebskategorie|spezielle kategorie",
    "versicherung": r"versicher|haftpflicht",
    "lieferzeit": r"werktag|innerhalb von \d+|lieferzeit|24 stunden|48 stunden",
    "datenschutz": r"datenschutz|dsgvo|persönlichkeitsrecht",
    "zielgruppe_bautraeger": r"bauträger|projektentwickler",
    "zielgruppe_bauunternehmen": r"bauunternehm|baufirm|generalunternehm",
    "zielgruppe_architekt": r"architekt|planer|ingenieur",
    "zielgruppe_hausverwaltung": r"hausverwalt|wohnungs|immobilienverwalt|bestandshalter",
    "zielgruppe_privat": r"bauherr|eigenheim|privat",
    "lokal_berlin": r"berlin",
    "lokal_brandenburg": r"brandenburg",
    "cta_anfrage": r"anfragen|angebot (anfordern|erhalten)|kontakt aufnehmen|jetzt (buchen|anfragen)|unverbindlich",
}


def profile(url, timeout=30):
    p = {"url": url, "domain": urlparse(url).netloc.replace("www.", ""), "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (compatible; seo-research-bot)"}, allow_redirects=True)
        p["status"] = r.status_code
        p["final_url"] = r.url
        t = r.text
    except Exception as e:
        p["error"] = str(e)[:200]
        return p
    get = lambda rx: (lambda m: html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else None)(re.search(rx, t, re.S | re.I))  # noqa: E731
    p["title"] = get(r"<title[^>]*>(.*?)</title>")
    p["meta_description"] = get(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)')
    heads = []
    for tag, inner in re.findall(r"<(h[1-3])[^>]*>(.*?)</\1>", t, re.S | re.I):
        x = html.unescape(re.sub(r"<[^>]+>", " ", inner))
        x = re.sub(r"\s+", " ", x).strip()
        if x:
            heads.append([tag.lower(), x[:160]])
    p["headings"] = heads
    p["h1"] = [h for tg, h in heads if tg == "h1"]
    body = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    body = re.sub(r"<(nav|footer|header)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    text = re.sub(r"\s+", " ", text)
    p["words"] = len(text.split())
    p["signals"] = {k: len(re.findall(v, text, re.I)) for k, v in SIGNALS.items()}
    p["faq_questions"] = [h for tg, h in heads if h.endswith("?")][:15]
    p["has_form"] = bool(re.search(r"<form", t, re.I))
    p["has_phone_link"] = bool(re.search(r'href=["\']tel:', t, re.I))
    p["schema_types"] = sorted(set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', t)))[:15]
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for u in a.urls:
        pr = profile(u)
        fn = re.sub(r"[^a-z0-9]+", "-", (pr["domain"] + urlparse(u).path).lower()).strip("-")[:90] + ".json"
        json.dump(pr, open(os.path.join(a.out, fn), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        if pr.get("error"):
            print(f"✗ {u}: {pr['error']}")
        else:
            top = sorted(((k, v) for k, v in pr["signals"].items() if v), key=lambda kv: -kv[1])[:8]
            print(f"✓ {pr['domain']} · {pr['status']} · {pr['words']} Wörter · H1: {pr['h1'][:1]} · {len(pr['headings'])} Überschriften · FAQ-Fragen {len(pr['faq_questions'])} · Form {pr['has_form']} · Signale {top}")
