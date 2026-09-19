"""Linux virtual gamepad creation and input translation."""

from __future__ import annotations

from threading import Lock

from evdev import AbsInfo, UInput, ecodes

MAX_PLAYERS = 8
STICK_DEADZONE = 0.06

BUTTON_CODES = {
    "A": ecodes.BTN_SOUTH, "B": ecodes.BTN_EAST, "X": ecodes.BTN_WEST,
    "Y": ecodes.BTN_NORTH, "LB": ecodes.BTN_TL, "RB": ecodes.BTN_TR,
    "LS": ecodes.BTN_THUMBL, "RS": ecodes.BTN_THUMBR,
    "L3": ecodes.BTN_THUMBL, "R3": ecodes.BTN_THUMBR,
    "SELECT": ecodes.BTN_SELECT, "START": ecodes.BTN_START,
    "HOME": ecodes.BTN_MODE, "UP": ecodes.BTN_DPAD_UP,
    "DOWN": ecodes.BTN_DPAD_DOWN, "LEFT": ecodes.BTN_DPAD_LEFT,
    "RIGHT": ecodes.BTN_DPAD_RIGHT,
}
HAT_AXIS = {
    "LEFT": (ecodes.ABS_HAT0X, -1), "RIGHT": (ecodes.ABS_HAT0X, 1),
    "UP": (ecodes.ABS_HAT0Y, -1), "DOWN": (ecodes.ABS_HAT0Y, 1),
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
                (ecodes.ABS_X, _stick_axis()), (ecodes.ABS_Y, _stick_axis()),
                (ecodes.ABS_RX, _stick_axis()), (ecodes.ABS_RY, _stick_axis()),
                (ecodes.ABS_Z, _trigger_axis()), (ecodes.ABS_RZ, _trigger_axis()),
                (ecodes.ABS_HAT0X, _hat_axis()), (ecodes.ABS_HAT0Y, _hat_axis()),
            ],
        }
        self.player = player
        self.ui = UInput(capabilities, name=f"Phone Controller {player}",
                         vendor=0x045E, product=0x028E, version=0x0114)
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
        if not all(map(lambda value: value == value and abs(value) != float("inf"), (x, y))):
            return
        if (x * x + y * y) ** 0.5 < STICK_DEADZONE:
            x = y = 0.0
        x, y = int(max(-1.0, min(1.0, x)) * 32767), int(max(-1.0, min(1.0, y)) * 32767)
        axes = (ecodes.ABS_X, ecodes.ABS_Y) if name == "LEFT" else (ecodes.ABS_RX, ecodes.ABS_RY)
        self.ui.write(ecodes.EV_ABS, axes[0], x)
        self.ui.write(ecodes.EV_ABS, axes[1], y)
        self.ui.syn()

    def reset(self):
        for code in set(BUTTON_CODES.values()):
            self.ui.write(ecodes.EV_KEY, code, 0)
        for axis in (ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_RX, ecodes.ABS_RY,
                     ecodes.ABS_Z, ecodes.ABS_RZ, ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
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
    def __init__(self, max_players: int = MAX_PLAYERS):
        self.max_players = max_players
        self.controllers = {}
        self._lock = Lock()

    def claim(self):
        with self._lock:
            for player in range(1, self.max_players + 1):
                if player not in self.controllers:
                    controller = VirtualController(player)
                    self.controllers[player] = controller
                    return player, controller
        return None, None

    def release(self, player):
        with self._lock:
            controller = self.controllers.pop(player, None)
        if controller:
            controller.close()

    def close_all(self):
        with self._lock:
            players = list(self.controllers)
        for player in players:
            self.release(player)
