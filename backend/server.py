"""HTTP and websocket services for MobileKonekt."""

from __future__ import annotations

import asyncio
import json
import math
import mimetypes
import socket
import sys
import argparse
import os
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import websockets

from backend.controller import ControllerManager
from backend.admin import make_admin_server
from backend.tui import TerminalUI
from backend.tui import TerminalUI

HTTP_PORT = 8080
WEBSOCKET_PORT = 8081
ADMIN_PORT = 8090
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
    if kind in ("handshake", "settings"):
        return isinstance(data.get("token"), str) and len(data["token"]) <= 128
    if kind == "button":
        return isinstance(data.get("button"), str) and isinstance(
            data.get("pressed"), bool
        )
    if kind == "trigger":
        try:
            return data.get("trigger") in ("LT", "RT") and math.isfinite(
                float(data.get("value", 0))
            )
        except (TypeError, ValueError):
            return False
    if kind == "stick":
        try:
            return data.get("stick") in ("LEFT", "RIGHT") and all(
                math.isfinite(float(data.get(key, 0))) for key in ("x", "y")
            )
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
                    body = (
                        b"MobileKonekt backend is running, but the frontend build is missing. "
                        b"Run `npm run build` to create dist/.\n"
                    )
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
                content_type = (
                    mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                )
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
    loop = asyncio.get_running_loop()
    player, controller, session_id = None, None, None
    try:
        try:
            remote = getattr(websocket, "remote_address", None)
            first = await websocket.recv()
            hello = _safe_json(first)
            token = (
                hello.get("token")
                if hello and hello.get("type") == "handshake"
                else None
            )
            player, controller, session_id = manager.claim(
                device_id=token, remote=str(remote)
            )
        except PermissionError:
            await websocket.send(
                json.dumps({"error": "Server cannot open /dev/uinput"})
            )
            return
        if controller is None:
            await websocket.send(json.dumps({"error": "All player slots are full"}))
            await websocket.close(code=1013, reason="player slots full")
            return
        manager.set_player_callback(
            session_id,
            lambda value: asyncio.run_coroutine_threadsafe(
                websocket.send(json.dumps({"type": "player_update", "player": value})),
                loop,
            ),
        )
        manager.set_connection(session_id, websocket)
        await websocket.send(
            json.dumps(
                {"type": "state", "player": player, **manager.get_settings(session_id)}
            )
        )
        manager.set_disconnect_callback(
            session_id,
            lambda: asyncio.run_coroutine_threadsafe(websocket.close(), loop),
        )
        async for message in websocket:
            data = _safe_json(message)
            if data is None or not _valid_input(data):
                continue
            kind = data["type"]
            if kind == "settings":
                manager.save_settings(
                    session_id, data.get("layout"), data.get("settings")
                )
                continue
            if kind == "handshake":
                continue
            if kind == "button":
                controller.button(data["button"], data["pressed"])
            elif kind == "trigger":
                controller.trigger(data["trigger"], data["value"])
            else:
                controller.stick(data["stick"], data["x"], data["y"])
    except (websockets.exceptions.ConnectionClosed, OSError, asyncio.CancelledError):
        pass
    finally:
        if session_id is not None:
            manager.release_session(session_id, websocket)


async def serve(http_server, admin_server, manager, websocket_port, stop_signal=None):
    http_thread = Thread(
        target=http_server.serve_forever, name="http-server", daemon=True
    )
    http_thread.start()
    admin_thread = Thread(
        target=admin_server.serve_forever, name="admin-server", daemon=True
    )
    admin_thread.start()
    try:
        async with websockets.serve(
            lambda ws, path=None: websocket_handler(ws, manager),
            "0.0.0.0",
            WEBSOCKET_PORT,
            ping_interval=15,
            ping_timeout=15,
            max_size=4096,
        ):
            while stop_signal is None or not stop_signal.is_set():
                await asyncio.sleep(0.25)
    finally:
        http_server.shutdown()
        http_server.server_close()
        admin_server.shutdown()
        admin_server.server_close()
        manager.close_all()


def main(argv=None):
    parser = argparse.ArgumentParser(description="MobileKonekt host backend")
    parser.add_argument(
        "--admin-bind", default=os.getenv("MOBILEKONEKT_ADMIN_BIND", "127.0.0.1")
    )
    parser.add_argument(
        "--admin-port",
        type=int,
        default=int(os.getenv("MOBILEKONEKT_ADMIN_PORT", ADMIN_PORT)),
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="show the server and device dashboard in the terminal",
    )
    args = parser.parse_args(argv)
    manager = ControllerManager()
    http_server = make_http_server()
    phone_ip = lan_address()
    admin_server = make_admin_server(
        manager,
        args.admin_bind,
        args.admin_port,
        lan_ip=phone_ip,
        phone_http_port=HTTP_PORT,
        websocket_port=WEBSOCKET_PORT,
    )
    admin_url = (
        f"http://127.0.0.1:{args.admin_port}"
        if args.admin_bind in ("0.0.0.0", "::")
        else f"http://{args.admin_bind}:{args.admin_port}"
    )
    print("\n  Phone Controller\n  " + "-" * 34)
    print(f"  Open on your phone : http://{phone_ip}:{HTTP_PORT}")
    print(f"  WebSocket port     : {WEBSOCKET_PORT}")
    print(f"  Admin dashboard    : {admin_url}")
    print("  Open that URL in a browser on this Linux PC to manage devices")
    print("  Ctrl+C to stop\n")
    from threading import Event

    stop_signal = Event()
    signal.signal(signal.SIGINT, lambda _signum, _frame: stop_signal.set())
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stop_signal.set())
    if args.tui:
        info = {
            "lan_ip": phone_ip,
            "phone_http": HTTP_PORT,
            "websocket": WEBSOCKET_PORT,
        }
        tui = TerminalUI(manager, info, stop_signal.set)
        tui_thread = Thread(target=tui.run, name="terminal-ui", daemon=True)
        tui_thread.start()
    try:
        asyncio.run(serve(http_server, admin_server, manager, WEBSOCKET_PORT, stop_signal))
    except KeyboardInterrupt:
        pass
    finally:
        manager.close_all()
