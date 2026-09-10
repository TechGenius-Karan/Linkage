"""The admin's HTTP shell (planning.md 16.1, 16.3).

Presentation tier. `http.server` from the standard library, not Flask or
FastAPI: one reviewer, on one machine, over localhost. A framework here would
be a dependency earning nothing.

**Binds 127.0.0.1 by default and has no authentication.** That is the design,
not a shortcut -- the safest gate is nothing exposed. `--host` opens it to the
local network for phone review, which is a deliberate choice each time and
says so on startup.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from ..config import Config
from . import handlers

#: Every route the admin answers. Adding one is a line here plus a function in
#: `handlers`; the HTTP shell never grows.
Route = Callable[..., dict]


class AdminHandler(BaseHTTPRequestHandler):
    cfg: Config = Config()

    server_version = "linkage-admin"
    #: Suppress the default per-request stderr line -- it drowns real output.
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    # -- plumbing ---------------------------------------------------------

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        # No cache, ever. A reviewer seeing a stale queue would re-decide
        # puzzles they have already judged.
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("content-length") or 0)
        if length == 0:
            return {}
        try:
            parsed = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise handlers.BadRequest(f"body is not JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise handlers.BadRequest("body must be a JSON object")
        return parsed

    def _run(self, fn: Callable[[], dict]) -> None:
        try:
            self._send(200, fn())
        except handlers.BadRequest as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            # A local tool crashing to a blank page helps nobody; the reviewer
            # needs the reason on screen, and the traceback stays in the log.
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
            raise

    # -- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/admin/queue"):
            self._run(lambda: handlers.queue(self.cfg))
        else:
            self._send(404, {"error": f"no route for GET {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            body = self._read_json()
        except handlers.BadRequest as exc:
            self._send(400, {"error": str(exc)})
            return

        def need(key: str) -> str:
            value = body.get(key)
            if not isinstance(value, str) or not value:
                raise handlers.BadRequest(f"{key} is required")
            return value

        if path == "/api/admin/approve":
            self._run(lambda: handlers.approve(self.cfg, need("hash")))
        elif path == "/api/admin/reject":
            self._run(
                lambda: handlers.reject(
                    self.cfg, need("hash"), need("reason"), body.get("badLink")
                )
            )
        elif path == "/api/admin/undo":
            self._run(lambda: handlers.undo(self.cfg, need("hash")))
        else:
            self._send(404, {"error": f"no route for POST {self.path}"})


def make_server(cfg: Config, host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    handler = type("BoundAdminHandler", (AdminHandler,), {"cfg": cfg})
    return ThreadingHTTPServer((host, port), handler)
