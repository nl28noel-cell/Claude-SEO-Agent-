#!/usr/bin/env python3
"""Website-Inventar für den SEO Autopilot (nur lesend, stdlib).

Erfasst alle öffentlichen WordPress-Seiten (REST API + Sitemap) und extrahiert
je URL: Status, Robots, Canonical, Title, Meta Description, H1–H3, Wortanzahl
des Hauptinhalts, interne Links, Bilder/Alt-Texte, Schema-Typen, FAQ-Hinweise.

Aufruf:  python3 tools/site_inventory.py https://www.example.de out_dir
Ergebnis: out_dir/inventory.json, out_dir/inventory.csv, out_dir/links.csv
"""
import csv, html, json, re, sys, urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (compatible; SEMSHARKS-Autopilot-Inventory/0.1)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.geturl(), r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, url, ""


class Page(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template"}
    CHROME = {"header", "footer", "nav"}

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.host = base, urlparse(base).netloc
        self.skip = self.chrome = 0
        self.heads, self.cur_h = [], None
        self.text, self.links, self.imgs = [], [], []
        self.in_a = None
        self.ld = []
        self.in_ld = False
        self.elementor_loc = []  # stack: header/footer Elementor templates

    def handle_starttag(self, t, a):
        a = dict(a)
        cls = a.get("class", "") or ""
        if t == "script" and a.get("type") == "application/ld+json":
            self.in_ld = True
        if t in self.SKIP:
            self.skip += 1
        chrome = t in self.CHROME or "elementor-location-header" in cls or "elementor-location-footer" in cls
        self.elementor_loc.append(chrome)
        if chrome:
            self.chrome += 1
        if t in ("h1", "h2", "h3", "h4"):
            self.cur_h = [t, ""]
        if t == "a" and a.get("href"):
            href = urljoin(self.base, a["href"].split("#")[0])
            self.in_a = [href, "", bool(self.chrome)]
        if t == "img":
            self.imgs.append({"src": a.get("src") or a.get("data-src", ""), "alt": (a.get("alt") or "").strip(), "chrome": bool(self.chrome)})

    def handle_endtag(self, t):
        if t == "script" and self.in_ld:
            self.in_ld = False
        if t in self.SKIP:
            self.skip = max(0, self.skip - 1)
        if self.elementor_loc:
            if self.elementor_loc.pop():
                self.chrome = max(0, self.chrome - 1)
        if self.cur_h and t == self.cur_h[0]:
            txt = re.sub(r"\s+", " ", self.cur_h[1]).strip()
            if txt and not self.chrome:
                self.heads.append((t, txt))
            self.cur_h = None
        if t == "a" and self.in_a:
            self.in_a[1] = re.sub(r"\s+", " ", self.in_a[1]).strip()
            self.links.append(self.in_a)
            self.in_a = None

    def handle_data(self, d):
        if self.in_ld:
            self.ld.append(d)
            return
        if self.skip:
            return
        if self.cur_h:
            self.cur_h[1] += d
        if self.in_a:
            self.in_a[1] += d
        if not self.chrome:
            self.text.append(d)


def schema_types(blobs):
    types = set()
    for b in blobs:
        try:
            data = json.loads(b)
        except Exception:
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                t = x.get("@type")
                if t:
                    types.update(t if isinstance(t, list) else [t])
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
    return sorted(types)


def meta(raw, name, attr="name"):
    m = re.search(r'<meta[^>]+%s=["\']%s["\'][^>]+content=["\']([^"\']*)' % (attr, re.escape(name)), raw, re.I)
    return html.unescape(m.group(1)).strip() if m else ""


def main(base, out):
    import os
    os.makedirs(out, exist_ok=True)
    host = urlparse(base).netloc
    urls = set()
    _, _, js = get(base.rstrip("/") + "/wp-json/wp/v2/pages?per_page=100&_fields=link,date,modified")
    rest = {}
    try:
        for p in json.loads(js):
            urls.add(p["link"]); rest[p["link"]] = p
    except Exception:
        pass
    _, _, sm = get(base.rstrip("/") + "/sitemap_index.xml")
    in_sitemap = set()
    for sub in re.findall(r"<loc>([^<]+)</loc>", sm):
        _, _, x = get(sub)
        in_sitemap.update(re.findall(r"<loc>([^<]+)</loc>", x))
    urls |= in_sitemap

    rows, edges = [], []
    for u in sorted(urls):
        st, final, raw = get(u)
        p = Page(final); p.feed(raw)
        words = len(re.sub(r"\s+", " ", " ".join(p.text)).split())
        title = re.search(r"<title>(.*?)</title>", raw, re.S)
        canon = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', raw)
        internal = [l for l in p.links if urlparse(l[0]).netloc == host]
        content_links = [l for l in internal if not l[2]]
        for l in content_links:
            edges.append({"from": u, "to": l[0], "anchor": l[1]})
        cimgs = [i for i in p.imgs if not i["chrome"]]
        rows.append({
            "url": u, "status": st, "final_url": final,
            "in_sitemap": u in in_sitemap,
            "published": rest.get(u, {}).get("date", "")[:10], "modified": rest.get(u, {}).get("modified", "")[:10],
            "robots": meta(raw, "robots"), "canonical": canon.group(1) if canon else "",
            "title": html.unescape(title.group(1)).strip() if title else "",
            "meta_description": meta(raw, "description"),
            "h1": [h[1] for h in p.heads if h[0] == "h1"],
            "h2": [h[1] for h in p.heads if h[0] == "h2"],
            "h3": [h[1] for h in p.heads if h[0] == "h3"],
            "words_main": words,
            "content_links_internal": len(content_links),
            "content_links_unique_targets": len({l[0] for l in content_links}),
            "images_content": len(cimgs),
            "images_missing_alt": sum(1 for i in cimgs if not i["alt"]),
            "schema_types": schema_types(p.ld),
            "has_faq_heading": any(re.search(r"FAQ|Fragen", h[1], re.I) for h in p.heads),
        })
    inlinks = {}
    for e in edges:
        if e["from"] != e["to"]:
            inlinks.setdefault(e["to"], set()).add(e["from"])
    for r in rows:
        r["content_inlinks_from_pages"] = len(inlinks.get(r["url"], ()))
    json.dump(rows, open(f"{out}/inventory.json", "w"), ensure_ascii=False, indent=1)
    with open(f"{out}/inventory.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (" | ".join(v) if isinstance(v, list) else v) for k, v in r.items()})
    with open(f"{out}/links.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["from", "to", "anchor"]); w.writeheader(); w.writerows(edges)
    print(f"{len(rows)} URLs, {len(edges)} interne Content-Links -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
