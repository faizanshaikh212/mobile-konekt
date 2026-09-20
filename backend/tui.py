"""Small stdlib-only terminal dashboard for the host backend."""

from __future__ import annotations

import os
import select
import sys
import termios
import time
import tty


class TerminalUI:
    """A low-overhead, keyboard-driven view over a ControllerManager."""

    def __init__(self, manager, server_info, stop_callback):
        self.manager = manager
        self.server_info = server_info
        self.stop_callback = stop_callback
        self.selected = 0
        self.message = "Ready"
        self._old_terminal = None

    @property
    def interactive(self):
        return sys.stdin.isatty() and sys.stdout.isatty()

    def _write(self, text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def render(self):
        devices = sorted(self.manager.snapshot(), key=lambda item: (not item.get("connected", False), item.get("id", "")))
        if devices:
            self.selected = min(self.selected, len(devices) - 1)
        else:
            self.selected = 0
        lines = [
            "\x1b[2J\x1b[H",
            "MobileKonekt terminal dashboard  (q quit, r refresh, arrows/j/k select)",
            f"Phone: http://{self.server_info['lan_ip']}:{self.server_info['phone_http']}  "
            f"WebSocket: {self.server_info['websocket']}",
            "Commands: z reset inputs | n rename | a assign player | d disconnect | x delete saved data",
            "-" * 96,
        ]
        if not devices:
            lines.append("  No devices connected or remembered.")
        for index, device in enumerate(devices):
            marker = ">" if index == self.selected else " "
            state = "connected" if device.get("connected") else "offline"
            label = device.get("label") or "(unnamed)"
            remote = device.get("remote") or "-"
            lines.append(
                f"{marker} {index + 1:>2}. P{device.get('player') or '-':<2} "
                f"{state:<9} {label[:24]:<24} {remote[:38]:<38} {device.get('id', '')}"
            )
        lines.extend(["-" * 96, self.message])
        self._write("\n".join(lines) + "\n")
        return devices

    def _selected(self):
        devices = sorted(self.manager.snapshot(), key=lambda item: (not item.get("connected", False), item.get("id", "")))
        return devices[self.selected] if devices and self.selected < len(devices) else None

    def _prompt(self, prompt):
        self._restore_terminal()
        try:
            return input(f"\n{prompt}: ")
        finally:
            self._set_raw_terminal()

    def _action(self, command):
        device = self._selected()
        if command == "r":
            self.message = "Refreshed"
        elif command == "z":
            self.manager.reset_all()
            self.message = "All inputs reset"
        elif command in ("n", "a") and not device:
            self.message = "Select a device first"
        elif command == "n":
            label = self._prompt("New name").strip()
            self.message = "Renamed" if self.manager.rename(device["id"], label) else "Device not found"
        elif command == "a":
            try:
                player = int(self._prompt("Player number"))
            except ValueError:
                self.message = "Player must be an integer"
            else:
                self.message = "Player assigned" if self.manager.assign(device["id"], player) else "Assignment failed"
        elif command == "d":
            self.message = "Select a device first" if not device else (
                "Disconnected" if self.manager.disconnect(device["id"]) else "Device not found"
            )
        elif command == "x":
            self.message = "Select a device first" if not device else (
                "Saved data deleted" if self.manager.delete_device_data(device["id"]) else "No saved data"
            )

    def _set_raw_terminal(self):
        if self._old_terminal is None:
            self._old_terminal = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

    def _restore_terminal(self):
        if self._old_terminal is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_terminal)
            self._old_terminal = None

    def run(self):
        if not self.interactive:
            self._write("Terminal dashboard requires an interactive TTY; running backend without it.\n")
            return
        try:
            self._set_raw_terminal()
            while True:
                self.render()
                ready, _, _ = select.select([sys.stdin], [], [], 1.0)
                if not ready:
                    continue
                key = os.read(sys.stdin.fileno(), 8).decode(errors="ignore")
                if key in ("q", "\x03"):
                    self.stop_callback()
                    return
                if key in ("\x1b[A", "k"):
                    self.selected = max(0, self.selected - 1)
                elif key in ("\x1b[B", "j"):
                    self.selected += 1
                elif key in ("r", "z", "n", "a", "d", "x"):
                    self._action(key)
                elif key.isdigit() and key != "0":
                    self.selected = int(key) - 1
        finally:
            self._restore_terminal()
            self._write("\n")
