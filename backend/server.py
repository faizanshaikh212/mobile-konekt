"""HTTP and websocket services for MobileKonekt."""

from __future__ import annotations

import asyncio
import json
import math
import mimetypes
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import websockets

from .controller import ControllerManager

HTTP_PORT = 8080
WEBSOCKET_PORT = 8081
if getattr(sys, "frozen", False):
    DIST_DIR = Path(getattr(sys, "_MEIPASS", Path.cwd())) / "dist"
else:
    DIST_DIR = Path(__file__).resolve().parent.parent / "dist"


def _safe_json(message):
    try:
        data = json.loads(message)
    except (TypeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _valid_input(data):
    kind = data.get("type")
    if kind == "button":
        return isinstance(data.get("button"), str) and isinstance(data.get("pressed"), bool)
    if kind == "trigger":
        try:
            return data.get("trigger") in ("LT", "RT") and math.isfinite(float(data.get("value", 0)))
        except (TypeError, ValueError):
            return False
    if kind == "stick":
        try:
            return data.get("stick") in ("LEFT", "RIGHT") and all(
                math.isfinite(float(data.get(key, 0))) for key in ("x", "y"))
        except (TypeError, ValueError):
            return False
    return False


def make_http_server(dist_dir=DIST_DIR):
    dist_dir = Path(dist_dir)

    class WebHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            requested = self.path.split("?", 1)[0]
            if requested in ("/", "/index.html"):
                target = dist_dir / "index.html"
                if target.is_file():
                    body, content_type = target.read_bytes(), "text/html; charset=utf-8"
                else:
                    body = (b"MobileKonekt backend is running, but the frontend build is missing. "
                            b"Run `npm run build` to create dist/.\n")
                    content_type = "text/plain; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            relative = requested.lstrip("/")
            target = (dist_dir / relative).resolve()
            if target.is_file() and dist_dir.resolve() in target.parents:
                body = target.read_bytes()
                content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                if content_type.startswith("text/"):
                    content_type += "; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def log_message(self, *_args):
            return

    return ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), WebHandler)


def lan_address():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


async def websocket_handler(websocket, manager):
    player, controller = None, None
    try:
        try:
            player, controller = manager.claim()
        except PermissionError:
            await websocket.send(json.dumps({"error": "Server cannot open /dev/uinput"}))
            return
        if controller is None:
            await websocket.send(json.dumps({"error": "All player slots are full"}))
            await websocket.close(code=1013, reason="player slots full")
            return
        await websocket.send(json.dumps({"player": player}))
        async for message in websocket:
            data = _safe_json(message)
            if data is None or not _valid_input(data):
                continue
            kind = data["type"]
            if kind == "button":
                controller.button(data["button"], data["pressed"])
            elif kind == "trigger":
                controller.trigger(data["trigger"], data["value"])
            else:
                controller.stick(data["stick"], data["x"], data["y"])
    except (websockets.exceptions.ConnectionClosed, OSError, asyncio.CancelledError):
        pass
    finally:
        if player is not None:
            manager.release(player)


async def serve(http_server, manager):
    http_thread = Thread(target=http_server.serve_forever, name="http-server", daemon=True)
    http_thread.start()
    stop = asyncio.Event()
    try:
        async with websockets.serve(
            lambda ws, path=None: websocket_handler(ws, manager),
            "0.0.0.0", WEBSOCKET_PORT, ping_interval=15, ping_timeout=15, max_size=4096
        ):
            await stop.wait()
    finally:
        http_server.shutdown()
        http_server.server_close()
        manager.close_all()


def main():
    manager = ControllerManager()
    http_server = make_http_server()
    print("\n  Phone Controller\n  " + "-" * 34)
    print(f"  Open on your phone : http://{lan_address()}:{HTTP_PORT}")
    print(f"  WebSocket port     : {WEBSOCKET_PORT}")
    print("  Ctrl+C to stop\n")
    try:
        asyncio.run(serve(http_server, manager))
    except KeyboardInterrupt:
        pass
    finally:
        manager.close_all()
