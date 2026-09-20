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
import secrets
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import websockets

from backend.controller import ControllerManager
from backend.persistence import device_ref
from backend.admin import make_admin_server
from backend.tui import TerminalUI

HTTP_PORT = 8080
WEBSOCKET_PORT = 8081
ADMIN_PORT = 8090
PHONE_HTTP_PORT = int(os.getenv("MOBILEKONEKT_PHONE_HTTP_PORT", HTTP_PORT))
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


def _device_label(user_agent):
    if not isinstance(user_agent, str) or not user_agent.strip():
        return "Mobile device"
    agent = user_agent[:120]
    android = re.search(
        r"Android [^;]+;\s*(?:[a-z]{2}-[A-Z]{2};\s*)?([^;)]+)", agent
    )
    if android:
        return android.group(1).strip()[:64]
    if "iPhone" in agent:
        return "iPhone"
    if "iPad" in agent:
        return "iPad"
    return agent[:64]


def _valid_layout(layout):
    if not isinstance(layout, dict) or not layout or len(layout) > 64:
        return False
    return all(
        isinstance(point, dict)
        and isinstance(point.get("x"), (int, float))
        and isinstance(point.get("y"), (int, float))
        and math.isfinite(point["x"])
        and math.isfinite(point["y"])
        and (
            "scale" not in point
            or (
                isinstance(point["scale"], (int, float))
                and math.isfinite(point["scale"])
                and 0.5 <= point["scale"] <= 2
            )
        )
        and 0 <= point["x"] <= 100
        and 0 <= point["y"] <= 100
        for point in layout.values()
    )


def make_http_server(dist_dir=DIST_DIR, store=None, device_store=None):
    dist_dir = Path(dist_dir)

    def write_body(handler, body):
        try:
            handler.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    class WebHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            requested = self.path.split("?", 1)[0]
            if requested.startswith("/api/layouts/"):
                layout_id = requested.rsplit("/", 1)[-1]
                record = store.get_layout(layout_id) if store else None
                if record is None:
                    self.send_error(404, "Layout not found")
                    return
                body = json.dumps({"id": layout_id, "layout": record["layout"]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                write_body(self, body)
                return
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
                write_body(self, body)
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
                write_body(self, body)
                return
            self.send_error(404)

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/api/layouts" or store is None:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 16384:
                    raise ValueError
                payload = json.loads(self.rfile.read(length) or b"{}")
                layout = payload.get("layout") if isinstance(payload, dict) else None
                device_id = payload.get("device_id", "")
                label = payload.get("label", "Mobile device")
                if device_store is not None:
                    saved_device = device_store.get(device_id)
                    label = saved_device.get("label") or label
                if not _valid_layout(layout):
                    raise ValueError
                layout_id = str(secrets.randbelow(900000) + 100000)
                while store.get_layout(layout_id) is not None:
                    layout_id = str(secrets.randbelow(900000) + 100000)
                store.save_layout(
                    layout_id, layout, device_ref(device_id, store.root), label
                )
                body = json.dumps({"id": layout_id}).encode()
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                write_body(self, body)
            except (ValueError, TypeError, json.JSONDecodeError):
                self.send_error(400, "Invalid layout")

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
                device_id=token,
                remote=str(remote),
                label=_device_label(hello.get("device_name")) if hello else "Mobile device",
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
            compression=None,
            ping_interval=15,
            ping_timeout=15,
            max_size=4096,
        ):
            while stop_signal is None or not stop_signal.is_set():
                await asyncio.sleep(0.05)
    finally:
        shutdown_threads = [
            Thread(target=http_server.shutdown, daemon=True),
            Thread(target=admin_server.shutdown, daemon=True),
        ]
        for thread in shutdown_threads:
            thread.start()
        for thread in shutdown_threads:
            thread.join(timeout=1)
        http_server.server_close()
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
    http_server = make_http_server(
        store=manager.layout_store, device_store=manager.store
    )
    phone_ip = lan_address()
    admin_server = make_admin_server(
        manager,
        args.admin_bind,
        args.admin_port,
        lan_ip=phone_ip,
        phone_http_port=PHONE_HTTP_PORT,
        websocket_port=WEBSOCKET_PORT,
    )
    admin_url = (
        f"http://127.0.0.1:{args.admin_port}"
        if args.admin_bind in ("0.0.0.0", "::")
        else f"http://{args.admin_bind}:{args.admin_port}"
    )
    print("\n  Phone Controller\n  " + "-" * 34)
    print(f"  Open on your phone : http://{phone_ip}:{PHONE_HTTP_PORT}")
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
            "phone_http": PHONE_HTTP_PORT,
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
