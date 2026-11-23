#!/usr/bin/env python3
"""Technischer URL-Check für das Monitoring (nur lesend, stdlib).

Prüft: HTTP-Status, Robots-Meta, Canonical (Self?), Aufnahme in Yoast-Sitemap (+lastmod).
Aufruf:  python3 tools/monitor_url.py https://www.example.de/seite/
"""
import re, sys, urllib.request
from urllib.parse import urlparse

UA = "Mozilla/5.0 (compatible; SEMSHARKS-Autopilot-Monitor/0.1)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.geturl(), r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, url, ""


def main(url):
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    st, final, raw = get(url)
    canon = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', raw)
    robots = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)', raw)
    _, _, idx = get(base + "/sitemap_index.xml")
    in_sm, lastmod = False, ""
    for sm in re.findall(r"<loc>([^<]+)</loc>", idx):
        _, _, x = get(sm)
        m = re.search(r"<loc>%s</loc>\s*<lastmod>([^<]+)</lastmod>" % re.escape(url), x)
        if m or f"<loc>{url}</loc>" in x:
            in_sm, lastmod = True, (m.group(1) if m else "")
    c = canon.group(1) if canon else ""
    checks = {
        "http_status": st, "final_url": final,
        "robots": robots.group(1) if robots else "(kein Meta – default index)",
        "canonical": c, "canonical_is_self": c == url,
        "in_sitemap": in_sm, "sitemap_lastmod": lastmod,
    }
    ok = st == 200 and c == url and in_sm and "noindex" not in checks["robots"]
    for k, v in checks.items():
        print(f"{k:18} {v}")
    print("RESULT            " + ("OK" if ok else "CHECK"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
