"""Simple, low-overhead command-line dashboard for the host backend."""

from __future__ import annotations

import sys


class TerminalUI:
    """A line-oriented admin console that works in any normal terminal."""

    def __init__(self, manager, server_info, stop_callback):
        self.manager = manager
        self.server_info = server_info
        self.stop_callback = stop_callback

    def _devices(self):
        return sorted(
            self.manager.snapshot(),
            key=lambda item: (not item.get("connected", False), item.get("id", "")),
        )

    def _show(self):
        print("\nMobileKonekt TUI")
        provider = self.server_info.get("phone_urls_provider")
        urls = provider() if provider else self.server_info.get("phone_urls")
        if urls:
            print("Phone URLs:")
            for item in urls:
                print(f"  {item['url']} ({item['interface']})")
        else:
            print(f"Phone URL: http://{self.server_info['lan_ip']}:{self.server_info['phone_http']}")
        print("-" * 72)
        devices = self._devices()
        if not devices:
            print("No connected or remembered devices.")
        for index, device in enumerate(devices, 1):
            state = "connected" if device.get("connected") else "offline"
            print(
                f"{index}. {device.get('label') or '(unnamed)'} | "
                f"player {device.get('player') or '-'} | {state} | "
                f"{device.get('remote') or device.get('id')}"
            )
        print("Commands: r refresh, z reset, n rename, a assign, d disconnect, x delete, q quit")

    def _choose(self, devices):
        if not devices:
            print("No device selected.")
            return None
        try:
            index = int(input("Device number: ")) - 1
            return devices[index] if 0 <= index < len(devices) else None
        except (EOFError, ValueError):
            return None

    def _action(self, command):
        devices = self._devices()
        if command == "r":
            return
        if command == "z":
            self.manager.reset_all()
            print("All inputs reset.")
            return
        device = self._choose(devices)
        if device is None:
            print("Invalid device.")
            return
        device_id = device["id"]
        if command == "n":
            self.manager.rename(device_id, input("New name: ").strip())
            print("Device renamed.")
        elif command == "a":
            try:
                player = int(input("Player number: "))
            except ValueError:
                print("Player must be a number.")
            else:
                print("Player assigned." if self.manager.assign(device_id, player) else "Assignment failed.")
        elif command == "d":
            print("Disconnected." if self.manager.disconnect(device_id) else "Device not found.")
        elif command == "x":
            print("Deleted." if self.manager.delete_device_data(device_id) else "Device data not found.")

    def run(self):
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print("TUI needs an interactive terminal; backend is running without the dashboard.")
            return
        while True:
            self._show()
            try:
                command = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                self.stop_callback()
                return
            if command == "q":
                self.stop_callback()
                return
            if command in {"r", "z", "n", "a", "d", "x"}:
                self._action(command)
