#!/usr/bin/env python3
"""Baut die Claude-Artifact-Version des Control Centers.

Quelle der UI ist dieselbe wie lokal (dashboard/public/index.html, styles.css, app.js).
Ausgabe: dashboard/artifact/dist/
    index.html                         Seite (Titel, Styles und Script inline – Artifact-Format ohne eigenes <html>/<head>)
    data/clients.json                  Kundenliste
    data/<slug>/dashboard.json         Daten je Kunde (neben der Seite veröffentlicht, per relativer URL geladen)

Danach Security-Scan über alle Ausgabedateien: bricht ab, wenn Credentials oder Secrets enthalten sind.

    python3 tools/build_artifact.py            # Daten neu bauen + Artifact-Dateien erzeugen
    python3 tools/build_artifact.py --no-data  # nur vorhandene Daten verwenden
"""
import argparse, json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "dashboard", "public")
DIST = os.path.join(ROOT, "dashboard", "artifact", "dist")

# Muster, die niemals in ausgelieferte Dateien gehören
SECRET_PATTERNS = [
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
    (r'"private_key(_id)?"\s*:', "service-account private key field"),
    (r'"client_email"\s*:', "service-account client_email field"),
    (r"[a-z0-9-]+@[a-z0-9-]+\.iam\.gserviceaccount\.com", "service-account e-mail"),
    (r"\bya29\.[A-Za-z0-9_-]{20,}", "Google OAuth access token"),
    (r"\bAIza[0-9A-Za-z_-]{35}\b", "Google API key"),
    (r"GSC_SERVICE_ACCOUNT_JSON_B64\s*=\s*\S{20,}", "credential env value"),
    (r"(?i)semrush[^\n]{0,40}(api[_-]?key|token)\s*[=:]\s*[\"']?[A-Za-z0-9]{24,}", "Semrush key/token"),
    (r"(?i)\b(authorization|apikey)\s*[:=]\s*[\"']?(bearer\s+)?[A-Za-z0-9._-]{24,}", "auth header value"),
]


def scan(paths):
    hits = []
    for p in paths:
        txt = open(p, encoding="utf-8").read()
        for pat, label in SECRET_PATTERNS:
            for m in re.finditer(pat, txt):
                hits.append(f"{os.path.relpath(p, ROOT)}: {label} @ {m.start()}")
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-data", action="store_true", help="dashboard.json nicht neu bauen")
    a = ap.parse_args()
    if not a.no_data:
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_dashboard_data.py")], check=True)

    html = open(os.path.join(PUB, "index.html"), encoding="utf-8").read()
    body = html.split("<!--APP-START-->", 1)[1].split("<!--APP-END-->", 1)[0].strip()
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    fonts = re.search(r'<link rel="stylesheet" href="(https://fonts\.googleapis\.com/[^"]+)">', html).group(1)
    css = open(os.path.join(PUB, "styles.css"), encoding="utf-8").read()
    js = open(os.path.join(PUB, "app.js"), encoding="utf-8").read()
    if "</script" in js.lower():
        sys.exit("app.js enthält '</script' – kann nicht inline eingebettet werden")

    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(os.path.join(DIST, "data"))
    page = (f"<title>{title}</title>\n"
            f'<link rel="stylesheet" href="{fonts}">\n'
            f"<style>\n{css}</style>\n{body}\n<script>\n{js}</script>\n")
    out = [os.path.join(DIST, "index.html")]
    open(out[0], "w", encoding="utf-8").write(page)

    data_src = os.path.join(PUB, "data")
    clients = json.load(open(os.path.join(data_src, "clients.json"), encoding="utf-8"))
    shutil.copy(os.path.join(data_src, "clients.json"), os.path.join(DIST, "data", "clients.json"))
    out.append(os.path.join(DIST, "data", "clients.json"))
    files = {"data/clients.json": os.path.relpath(out[-1], ROOT)}
    for c in clients["clients"]:
        os.makedirs(os.path.join(DIST, "data", c["slug"]))
        dst = os.path.join(DIST, "data", c["slug"], "dashboard.json")
        shutil.copy(os.path.join(data_src, c["slug"], "dashboard.json"), dst)
        out.append(dst)
        files[f"data/{c['slug']}/dashboard.json"] = os.path.relpath(dst, ROOT)

    hits = scan(out)
    if hits:
        shutil.rmtree(DIST)
        sys.exit("SECURITY: Build abgebrochen, sensible Daten gefunden:\n  " + "\n  ".join(hits))
    size = sum(os.path.getsize(p) for p in out)
    print(f"✓ Artifact gebaut: {os.path.relpath(DIST, ROOT)} · {len(out)} Dateien · {size/1024:.0f} KB · Security-Scan ohne Treffer")
    print("  page:  " + os.path.relpath(out[0], ROOT) + f" ({os.path.getsize(out[0])/1024:.0f} KB)")
    print("  files: " + json.dumps(files))


if __name__ == "__main__":
    main()
