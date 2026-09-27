"""Serve the local dashboard without a web framework or frontend build step."""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlsplit

from wyndle.lib.config import WyndleConfig, init_default_config, load_config
from wyndle.lib.dashboard import dispatch, snapshot
from wyndle.lib.state import State

ASSETS = {"/": ("index.html", "text/html"),
          "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css")}
for _asset in ("api.js", "components/tasks.js", "components/focus.js", "components/dialogs.js",
               "components/durations.js", "components/help.js"):
    ASSETS[f"/{_asset}"] = (_asset, "text/javascript")
ASSETS["/theme.css"] = ("theme.css", "text/css")
ASSETS["/components.css"] = ("components.css", "text/css")
ASSETS["/HOW_TO_USE.md"] = ("HOW_TO_USE.md", "text/markdown")
for _character in ("dalinar", "kaladin"):
    ASSETS[f"/assets/{_character}.jpg"] = (f"assets/{_character}.jpg", "image/jpeg")


class DashboardHTTPServer(ThreadingHTTPServer):
    """One owner per port, including on Python versions enabling SO_REUSEPORT."""

    allow_reuse_port = False


def make_server(cfg: WyndleConfig, state: State, port: int = 8765) -> ThreadingHTTPServer:
    """Create a loopback-only server; all reads and writes share a lock."""
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_args) -> None:
            pass

        def _send(self, code: int, body: bytes, mime: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; "
                             "script-src 'self'; style-src 'self'; "
                             "img-src 'self' data:; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, value: dict) -> None:
            self._send(code, json.dumps(value).encode())

        def _local_request(self) -> bool:
            port = self.server.server_port
            allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in allowed:
                self._json(403, {"error": "Only local dashboard requests are allowed."})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{host}" for host in allowed}:
                self._json(403, {"error": "Cross-origin requests are not allowed."})
                return False
            return True

        def do_GET(self) -> None:  # noqa: N802
            if not self._local_request():
                return
            path = urlsplit(self.path).path
            if path == "/api/help":
                from wyndle.lib.help import help_content

                self._json(200, help_content())
            elif path == "/api/status":
                try:
                    with lock:
                        self._json(200, {"app": "wyndle", "protocol": 1, **snapshot(cfg, state)})
                except (OSError, ValueError) as exc:
                    self._json(500, {"error": str(exc)})
            elif path in ASSETS:
                filename, mime = ASSETS[path]
                self._send(200, files("wyndle.web").joinpath(filename).read_bytes(), mime)
            else:
                self._json(404, {"error": "Not found."})

        def do_POST(self) -> None:  # noqa: N802
            if not self._local_request():
                return
            if self.path != "/api/action":
                self._json(404, {"error": "Not found."})
                return
            if (self.headers.get("Content-Type") != "application/json"
                    or self.headers.get("X-Wyndle-Client") != "dashboard"):
                self._json(403, {"error": "Use the Wyndle dashboard to make changes."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("Invalid request size.")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or not isinstance(payload.get("action"), str):
                    raise ValueError("Expected an action object.")
                data = payload.get("data", {})
                if not isinstance(data, dict):
                    raise ValueError("Expected action data to be an object.")
                with lock:
                    result = dispatch(cfg, state, payload["action"], data)
                self._json(200, result)
            except (ValueError, TypeError) as exc:
                self._json(400, {"error": str(exc)})
            except OSError as exc:
                self._json(500, {"error": f"Could not update your notes: {exc}"})

    return DashboardHTTPServer(("127.0.0.1", port), Handler)


def run(port: int, open_browser: bool) -> None:
    config_exists = (WyndleConfig().wyndle_dir / "config.yaml").exists()
    cfg = load_config()
    if not config_exists:
        init_default_config()
        cfg = load_config()
    state = State(cfg.state_dir)
    server = make_server(cfg, state, port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Wyndle dashboard: {url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
