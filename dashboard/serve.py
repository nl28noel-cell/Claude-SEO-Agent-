#!/usr/bin/env python3
"""Startet das SEO Autopilot Dashboard lokal.

    python3 dashboard/serve.py            # baut die Daten neu und startet http://127.0.0.1:8765
    python3 dashboard/serve.py --no-build # nur Server
    python3 dashboard/serve.py --port 9000

Ausgeliefert wird ausschließlich dashboard/public/ (keine Repo-Dateien, keine Credentials).
"""
import argparse, functools, http.server, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PUBLIC = os.path.join(HERE, "public")


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, fmt, *args):  # ruhiges Log, keine Query-Strings
        sys.stderr.write("%s %s\n" % (self.command, self.path.split("?")[0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args()
    if not a.no_build:
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_dashboard_data.py")], check=True)
    srv = http.server.ThreadingHTTPServer((a.host, a.port), functools.partial(Handler, directory=PUBLIC))
    print(f"SEO Autopilot Dashboard: http://{a.host}:{a.port}/  (Strg+C zum Beenden)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
