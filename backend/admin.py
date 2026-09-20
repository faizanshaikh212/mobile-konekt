"""Local-only administration HTTP service."""

from __future__ import annotations

import json
import mimetypes
import platform
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ASSET_DIR = Path(__file__).with_name("admin_assets")


def _json_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 8192:
        raise ValueError("request too large")
    data = json.loads(handler.rfile.read(length) or b"{}")
    if not isinstance(data, dict):
        raise ValueError("JSON object required")
    return data


def make_admin_server(
    manager,
    bind="127.0.0.1",
    port=8090,
    lan_ip="127.0.0.1",
    phone_http_port=8080,
    websocket_port=8081,
):
    class AdminHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def respond(self, status, payload, content_type="application/json"):
            body = (
                payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # Browsers can cancel an asset request while a window is
                # closing or navigating; there is nothing left to send.
                return

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/state":
                self.respond(
                    200,
                    {
                        "devices": manager.snapshot(),
                        "server": {
                            "platform": platform.platform(),
                            "hostname": socket.gethostname(),
                            "admin": f"{bind}:{port}",
                            "lan_ip": lan_ip,
                            "phone_http": phone_http_port,
                            "phone_websocket": websocket_port,
                            "phone_url": f"http://{lan_ip}:{phone_http_port}",
                            "physical_controllers": True,
                        },
                    },
                )
                return
            relative = (
                "index.html" if path in ("/", "/index.html") else path.lstrip("/")
            )
            target = (ASSET_DIR / relative).resolve()
            if target.is_file() and ASSET_DIR.resolve() in target.parents:
                content_type = (
                    mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                )
                if content_type.startswith("text/"):
                    content_type += "; charset=utf-8"
                self.respond(200, target.read_bytes(), content_type)
                return
            self.respond(404, {"error": "not found"})

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            try:
                data = _json_body(self)
                session_id = data.get("id")
                if path == "/api/rename":
                    label = data.get("label")
                    if (
                        not isinstance(session_id, str)
                        or not isinstance(label, str)
                        or len(label) > 64
                    ):
                        raise ValueError("id and label are required")
                    ok = manager.rename(session_id, label.strip())
                elif path == "/api/assign":
                    player = data.get("player")
                    if (
                        not isinstance(session_id, str)
                        or isinstance(player, bool)
                        or not isinstance(player, int)
                    ):
                        raise ValueError("id and integer player are required")
                    ok = manager.assign(session_id, player)
                elif path == "/api/disconnect":
                    if not isinstance(session_id, str):
                        raise ValueError("id is required")
                    ok = manager.disconnect(session_id)
                elif path == "/api/reset":
                    manager.reset_all()
                    ok = True
                elif path == "/api/delete":
                    if not isinstance(session_id, str):
                        raise ValueError("id is required")
                    ok = manager.delete_device_data(session_id)
                else:
                    self.respond(404, {"error": "not found"})
                    return
                self.respond(200 if ok else 404, {"ok": ok})
            except (ValueError, json.JSONDecodeError, TypeError):
                self.respond(400, {"error": "invalid request"})

        def log_message(self, *_args):
            return

    return ThreadingHTTPServer((bind, port), AdminHandler)
