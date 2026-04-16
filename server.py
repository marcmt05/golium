#!/usr/bin/env python3
"""Golium — servidor HTTP para local/producción.

Uso:
  python server.py
Variables:
  PORT=8000
  HOST=0.0.0.0
"""
from __future__ import annotations

import http.server
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from storage import DB_PATH, latest_snapshot

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
ROOT = Path(__file__).resolve().parent


class GoliumHandler(http.server.SimpleHTTPRequestHandler):
    """Simple static handler with healthcheck and basic security headers."""

    server_version = "GoliumHTTP/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self._send_security_headers()
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/health", "/healthz"):
            payload = json.dumps({"status": "ok", "db": DB_PATH.name}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/api/snapshots":
            rows = [dict(r) for r in latest_snapshot()]
            payload = json.dumps({"items": rows}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/":
            self.path = "/app.html"
        super().do_GET()

    def guess_type(self, path: str) -> str:
        guessed = super().guess_type(path)
        if guessed:
            return guessed
        ext = Path(path).suffix
        return mimetypes.types_map.get(ext, "application/octet-stream")

    def log_message(self, fmt: str, *args) -> None:
        target = args[0] if args else ""
        if any(x in str(target) for x in (".html", ".json", "/health", "/app.html")):
            print(f"→ {target}")


if __name__ == "__main__":
    print(
        f"""
Golium · Servidor web
────────────────────────────────
URL:  http://localhost:{PORT}/
Health: http://localhost:{PORT}/health
Dir:  {ROOT}
────────────────────────────────
Ctrl+C para detener
"""
    )

    with http.server.ThreadingHTTPServer((HOST, PORT), GoliumHandler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")
