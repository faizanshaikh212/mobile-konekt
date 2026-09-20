"""Linux virtual gamepad creation and input translation."""

from __future__ import annotations

from threading import RLock
from time import time
from uuid import uuid4
from backend.persistence import JsonStore, LayoutStore, device_ref

from evdev import AbsInfo, InputDevice, UInput, ecodes, list_devices

MAX_PLAYERS = 8
STICK_DEADZONE = 0.06

BUTTON_CODES = {
    "A": ecodes.BTN_SOUTH,
    "B": ecodes.BTN_EAST,
    "X": ecodes.BTN_WEST,
    "Y": ecodes.BTN_NORTH,
    "LB": ecodes.BTN_TL,
    "RB": ecodes.BTN_TR,
    "LS": ecodes.BTN_THUMBL,
    "RS": ecodes.BTN_THUMBR,
    "L3": ecodes.BTN_THUMBL,
    "R3": ecodes.BTN_THUMBR,
    "SELECT": ecodes.BTN_SELECT,
    "START": ecodes.BTN_START,
    "HOME": ecodes.BTN_MODE,
    "UP": ecodes.BTN_DPAD_UP,
    "DOWN": ecodes.BTN_DPAD_DOWN,
    "LEFT": ecodes.BTN_DPAD_LEFT,
    "RIGHT": ecodes.BTN_DPAD_RIGHT,
}
HAT_AXIS = {
    "LEFT": (ecodes.ABS_HAT0X, -1),
    "RIGHT": (ecodes.ABS_HAT0X, 1),
    "UP": (ecodes.ABS_HAT0Y, -1),
    "DOWN": (ecodes.ABS_HAT0Y, 1),
}


def _stick_axis():
    return AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)


def _trigger_axis():
    return AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)


def _hat_axis():
    return AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)


class VirtualController:
    """One evdev virtual controller, with all values clamped at the boundary."""

    def __init__(self, player: int):
        capabilities = {
            ecodes.EV_KEY: sorted(set(BUTTON_CODES.values())),
            ecodes.EV_ABS: [
                (ecodes.ABS_X, _stick_axis()),
                (ecodes.ABS_Y, _stick_axis()),
                (ecodes.ABS_RX, _stick_axis()),
                (ecodes.ABS_RY, _stick_axis()),
                (ecodes.ABS_Z, _trigger_axis()),
                (ecodes.ABS_RZ, _trigger_axis()),
                (ecodes.ABS_HAT0X, _hat_axis()),
                (ecodes.ABS_HAT0Y, _hat_axis()),
            ],
        }
        self.player = player
        self.ui = UInput(
            capabilities,
            name=f"Phone Controller {player}",
            vendor=0x045E,
            product=0x028E,
            version=0x0114,
        )
        self.hat = {ecodes.ABS_HAT0X: 0, ecodes.ABS_HAT0Y: 0}
        self.hat_buttons = set()
        print(f"[+] Controller {player} created ({self.ui.device.path})")

    def button(self, name, pressed):
        code = BUTTON_CODES.get(name)
        if code is None:
            return
        self.ui.write(ecodes.EV_KEY, code, int(bool(pressed)))
        if name in HAT_AXIS:
            axis, direction = HAT_AXIS[name]
            if pressed:
                self.hat_buttons.add(name)
            else:
                self.hat_buttons.discard(name)
            value = 0
            for direction_name, (direction_axis, direction_value) in HAT_AXIS.items():
                if direction_axis == axis and direction_name in self.hat_buttons:
                    value += direction_value
            value = max(-1, min(1, value))
            if self.hat[axis] != value:
                self.hat[axis] = value
                self.ui.write(ecodes.EV_ABS, axis, value)
        self.ui.syn()

    def trigger(self, name, value):
        axis = {"LT": ecodes.ABS_Z, "RT": ecodes.ABS_RZ}.get(name)
        if axis is None:
            return
        try:
            value = max(0, min(255, int(float(value) * 255)))
        except (TypeError, ValueError, OverflowError):
            return
        self.ui.write(ecodes.EV_ABS, axis, value)
        self.ui.syn()

    def stick(self, name, x, y):
        if name not in ("LEFT", "RIGHT"):
            return
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError, OverflowError):
            return
        if not all(
            map(lambda value: value == value and abs(value) != float("inf"), (x, y))
        ):
            return
        if (x * x + y * y) ** 0.5 < STICK_DEADZONE:
            x = y = 0.0
        x, y = int(max(-1.0, min(1.0, x)) * 32767), int(max(-1.0, min(1.0, y)) * 32767)
        axes = (
            (ecodes.ABS_X, ecodes.ABS_Y)
            if name == "LEFT"
            else (ecodes.ABS_RX, ecodes.ABS_RY)
        )
        self.ui.write(ecodes.EV_ABS, axes[0], x)
        self.ui.write(ecodes.EV_ABS, axes[1], y)
        self.ui.syn()

    def reset(self):
        for code in set(BUTTON_CODES.values()):
            self.ui.write(ecodes.EV_KEY, code, 0)
        for axis in (
            ecodes.ABS_X,
            ecodes.ABS_Y,
            ecodes.ABS_RX,
            ecodes.ABS_RY,
            ecodes.ABS_Z,
            ecodes.ABS_RZ,
            ecodes.ABS_HAT0X,
            ecodes.ABS_HAT0Y,
        ):
            self.ui.write(ecodes.EV_ABS, axis, 0)
        self.hat.update({ecodes.ABS_HAT0X: 0, ecodes.ABS_HAT0Y: 0})
        self.hat_buttons.clear()
        self.ui.syn()

    def close(self):
        try:
            self.reset()
        finally:
            self.ui.close()
        print(f"[-] Controller {self.player} removed")


class ControllerManager:
    def __init__(self, max_players: int = MAX_PLAYERS, store=None):
        self.max_players = max_players
        self.controllers = {}
        self.devices = {}
        self.store = store or JsonStore()
        self.layout_store = LayoutStore(root=self.store.root)
        self.layout_store.sync_device_labels(
            self.store.snapshot(), root=self.store.root
        )
        for layout_id, layout in self.store.legacy_layouts.items():
            if isinstance(layout, dict) and "layout" not in layout:
                self.layout_store.save_layout(
                    layout_id, layout, "", "Mobile device"
                )
        self._lock = RLock()
        self.physical_players = self.store.get_physical_players()

    @staticmethod
    def _physical_identity(device):
        info = device.info
        return "|".join(
            (
                device.name or "Physical controller",
                device.phys or "",
                str(info.vendor),
                str(info.product),
                str(info.version),
            )
        )

    def physical_snapshot(self):
        devices = []
        for path in list_devices():
            try:
                device = InputDevice(path)
                if (device.name or "").startswith("Phone Controller "):
                    device.close()
                    continue
                capabilities = device.capabilities()
                keys = set(capabilities.get(ecodes.EV_KEY, []))
                axes = capabilities.get(ecodes.EV_ABS, [])
                if not axes and not (
                    ecodes.BTN_GAMEPAD in keys or ecodes.BTN_JOYSTICK in keys
                ):
                    device.close()
                    continue
                identity = self._physical_identity(device)
                player = self.physical_players.get(identity)
                devices.append(
                    {
                        "id": f"physical:{path}",
                        "label": device.name or "Physical controller",
                        "player": player,
                        "connected": True,
                        "physical": True,
                        "remote": "",
                        "path": path,
                        "identity": identity,
                    }
                )
                device.close()
            except OSError:
                continue
        active = {item["id"] for item in devices}
        return devices

    def _assigned_players(self):
        with self._lock:
            mobile = {
                item.get("player")
                for item in self.devices.values()
                if item.get("player") is not None
            }
            mobile.update(
                item.get("player")
                for item in self.store.snapshot().values()
                if isinstance(item, dict) and item.get("player") is not None
            )
        physical = {
            item.get("player")
            for item in self.physical_snapshot()
            if item.get("player") is not None
        }
        return mobile | physical

    def claim(self, device_id=None, remote="unknown", label="Mobile device"):
        old_controller = None
        with self._lock:
            session_id = device_id or uuid4().hex
            previous = self.devices.get(session_id)
            if previous:
                previous["connected"] = False
                old_controller = self.controllers.pop(previous["player"], None)
                self.devices.pop(session_id, None)
                if previous.get("disconnect"):
                    previous["disconnect"]()
        if old_controller:
            old_controller.close()
        with self._lock:
            saved = self.store.get(session_id)
            preferred = saved.get("player")
            player = (
                preferred
                if isinstance(preferred, int)
                and 1 <= preferred <= self.max_players
                and preferred not in self.controllers
                and preferred not in self._assigned_players()
                else None
            )
            if player is None:
                player = next(
                    (
                        p
                        for p in range(1, self.max_players + 1)
                        if p not in self.controllers
                        and p not in self._assigned_players()
                    ),
                    None,
                )
            if player is not None:
                controller = VirtualController(player)
                self.controllers[player] = controller
                self.devices[session_id] = {
                    "id": session_id,
                    "player": player,
                    "label": saved.get("label") or label,
                    "remote": remote,
                    "connected_at": time(),
                    "disconnect": None,
                    "connected": True,
                    "layout": saved.get("layout"),
                    "settings": saved.get("settings"),
                    "websocket": None,
                }
                self.store.update(
                    session_id,
                    player=player,
                    label=self.devices[session_id]["label"],
                )
                return player, controller, session_id
        return None, None, None

    def set_disconnect_callback(self, session_id, callback):
        with self._lock:
            if session_id in self.devices:
                self.devices[session_id]["disconnect"] = callback

    def set_connection(self, session_id, connection):
        with self._lock:
            if session_id in self.devices:
                self.devices[session_id]["websocket"] = connection

    def set_connected(self, session_id, connected):
        with self._lock:
            if session_id in self.devices:
                self.devices[session_id]["connected"] = connected

    def get_settings(self, session_id):
        with self._lock:
            device = self.devices.get(session_id, {})
            return {"layout": device.get("layout"), "settings": device.get("settings")}

    def save_settings(self, session_id, layout=None, settings=None):
        with self._lock:
            device = self.devices.get(session_id)
            if not device:
                return False
            if layout is not None and (
                not isinstance(layout, dict) or len(layout) > 64
            ):
                return False
            if settings is not None and (
                not isinstance(settings, dict) or len(settings) > 32
            ):
                return False
            if layout is not None:
                device["layout"] = layout
            if settings is not None:
                device["settings"] = settings
            values = {
                "layout": device.get("layout"),
                "settings": device.get("settings"),
            }
        self.store.update(session_id, **values)
        return True

    def snapshot(self):
        with self._lock:
            active = {d["id"] for d in self.devices.values()}
            public_keys = {
                "id",
                "player",
                "label",
                "remote",
                "connected_at",
                "connected",
                "layout",
                "settings",
            }
            result = [
                {key: value for key, value in device.items() if key in public_keys}
                for device in self.devices.values()
            ]
            for token, saved in self.store.snapshot().items():
                if token not in active:
                    result.append(
                        {
                            "id": token,
                            "player": saved.get("player"),
                            "label": saved.get("label", ""),
                            "remote": "",
                            "connected_at": 0,
                            "connected": False,
                        }
                    )
            return result + self.physical_snapshot()

    def rename(self, session_id, label):
        with self._lock:
            device = self.devices.get(session_id)
            if device is None:
                if not self.store.get(session_id):
                    return False
                self.store.update(session_id, label=label)
                self.layout_store.update_device(device_ref(session_id, self.store.root), label)
                return True
            device["label"] = label
            self.store.update(session_id, label=label)
            self.layout_store.update_device(device_ref(session_id, self.store.root), label)
            return True

    def delete_device_data(self, session_id):
        """Disconnect and forget all persisted preferences for a device."""
        with self._lock:
            device = self.devices.get(session_id)
            callback = device.get("disconnect") if device else None
            player = device.get("player") if device else None
            if device:
                device["connected"] = False
                device["disconnect"] = None
        if callback:
            callback()
        if player is not None:
            self.release(player, keep_device=False)
        self.layout_store.delete_device(device_ref(session_id, self.store.root))
        return self.store.delete(session_id) or device is not None

    def assign(self, session_id, player):
        if player < 1 or player > self.max_players:
            return False
        physical = self.physical_snapshot()
        assigned = self._assigned_players()
        if session_id.startswith("physical:"):
            path = session_id.removeprefix("physical:")
            if not any(item["id"] == session_id for item in physical):
                return False
            current = next(item for item in physical if item["id"] == session_id)
            if player in assigned and current.get("player") != player:
                return False
            identity = current["identity"]
            self.physical_players[identity] = player
            self.store.set_physical_player(identity, player)
            return True
        with self._lock:
            device = self.devices.get(session_id)
            if device is None:
                if not self.store.get(session_id):
                    return False
                if any(item.get("player") == player for item in physical):
                    return False
                self.store.update(session_id, player=player)
                return True
            old_player = device["player"]
            if any(item.get("player") == player for item in physical):
                return False
            other = next(
                (
                    item
                    for item in self.devices.values()
                    if item["player"] == player and item["id"] != session_id
                ),
                None,
            )
            controller = self.controllers.pop(old_player)
            if other is not None:
                other_controller = self.controllers.pop(player)
                other_controller.player = old_player
                self.controllers[old_player] = other_controller
                other["player"] = old_player
                self.store.update(other["id"], player=old_player)
            controller.player = player
            self.controllers[player] = controller
            device["player"] = player
            self.store.update(session_id, player=player)
            callbacks = [
                (player, device.get("player_update")),
                (old_player, other.get("player_update") if other else None),
            ]
            for new_player, callback in callbacks:
                if callback:
                    callback(new_player)
            return True

    def disconnect(self, session_id):
        with self._lock:
            device = self.devices.get(session_id)
            callback = device.get("disconnect") if device else None
            player = device.get("player") if device else None
            if device:
                device["connected"] = False
                device["disconnect"] = None
        if not device:
            return False
        if callback:
            callback()
        if player is not None:
            self.release(player, keep_device=True)
        return True

    def release_session(self, session_id, connection=None):
        with self._lock:
            device = self.devices.get(session_id)
            if (
                device
                and connection is not None
                and device.get("websocket") is not connection
            ):
                return
            player = device.get("player") if device else None
        if player is not None:
            with self._lock:
                if session_id in self.devices:
                    self.devices[session_id]["connected"] = False
                    self.devices[session_id]["disconnect"] = None
            self.release(player, keep_device=True)

    def set_player_callback(self, session_id, callback):
        with self._lock:
            if session_id in self.devices:
                self.devices[session_id]["player_update"] = callback

    def reset_all(self):
        with self._lock:
            controllers = list(self.controllers.values())
        for controller in controllers:
            controller.reset()

    def release(self, player, keep_device=False):
        with self._lock:
            controller = self.controllers.pop(player, None)
            session_id = next(
                (
                    key
                    for key, value in self.devices.items()
                    if value["player"] == player
                ),
                None,
            )
            if session_id and not keep_device:
                self.devices.pop(session_id, None)
        if controller:
            controller.close()

    def close_all(self):
        with self._lock:
            players = list(self.controllers)
        for player in players:
            self.release(player)
