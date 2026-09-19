#!/usr/bin/env python3
"""
Phone Controller - turn Android/iOS phones into virtual gamepads on Linux.

Open http://<this-machine-ip>:8080 on a phone (same Wi-Fi), rotate to
landscape, and a new virtual Xbox-style pad appears on this machine.
"""

import asyncio
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import websockets
from evdev import UInput, ecodes, AbsInfo


# ============================================================
# SETTINGS
# ============================================================

HTTP_PORT = 8080
WEBSOCKET_PORT = 8081

MAX_PLAYERS = 8

# How far a stick must move before it counts (0..1)
STICK_DEADZONE = 0.06


# ============================================================
# PHONE CONTROLLER PAGE
# ============================================================

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#101317">
<title>Phone Controller</title>
<style>
:root {
  --bg:      #101317;
  --cap:     #252a32;
  --cap-lip: #0c0e12;
  --ink:     #e8ebf0;
  --dim:     #78828f;
  --live:    #5bd6a8;
  --lost:    #e0685f;

  --a: #62c67d;
  --b: #e0685f;
  --x: #5c9de8;
  --y: #e2b65a;

  /* one number drives the whole pad; it can never grow past the screen */
  --unit: clamp(34px, min(15vh, 9vw), 72px);
  --gap: clamp(4px, 1.4vh, 14px);
}

* { box-sizing: border-box; margin: 0; padding: 0;
    -webkit-user-select: none; user-select: none;
    -webkit-tap-highlight-color: transparent;
    touch-action: none; }

html, body {
  height: 100%;
  overflow: hidden;
  overscroll-behavior: none;
  background: var(--bg);
  color: var(--ink);
  font: 600 15px/1.2 ui-rounded, "SF Pro Rounded", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-variant-numeric: tabular-nums;
}

body::before {
  content: "";
  position: fixed; inset: 0;
  background: radial-gradient(120% 90% at 50% -20%, #1b212a 0%, var(--bg) 62%);
  z-index: -1;
}

/* ----------------------------------------------------------
   BOARD: a 3 x 3 grid, so nothing can ever sit on top of
   anything else no matter how small the screen is
---------------------------------------------------------- */

#board {
  position: fixed;
  inset: 0;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: var(--gap) clamp(8px, 3vw, 28px);
  padding:
    calc(6px + env(safe-area-inset-top))
    calc(10px + env(safe-area-inset-right))
    calc(6px + env(safe-area-inset-bottom))
    calc(10px + env(safe-area-inset-left));
}

.cell { display: flex; align-items: center; gap: clamp(6px, 1.4vw, 12px); }

#topLeft   { grid-area: 1 / 1; justify-self: start; }
#topMid    { grid-area: 1 / 2; justify-self: center; }
#topRight  { grid-area: 1 / 3; justify-self: end; }
#midLeft   { grid-area: 2 / 1; justify-self: start; align-self: center; }
#midMid    { grid-area: 2 / 2; justify-self: center; align-self: center; }
#midRight  { grid-area: 2 / 3; justify-self: end; align-self: center; }
#lowLeft   { grid-area: 3 / 1; justify-self: start; align-self: end; }
#lowRight  { grid-area: 3 / 3; justify-self: end; align-self: end; }

/* ---------- status ---------- */

#bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px 4px 11px;
  border-radius: 999px;
  background: rgba(23,27,33,.92);
  box-shadow: 0 1px 0 rgba(255,255,255,.05) inset;
}
#dot { width: 8px; height: 8px; border-radius: 50%; background: var(--dim); transition: background .2s; }
#bar.live #dot { background: var(--live); }
#bar.lost #dot { background: var(--lost); }
#label { font-size: 12px; font-weight: 500; color: var(--dim); white-space: nowrap; }
#bar.live #label { color: var(--ink); }

.chip {
  border: 0; border-radius: 999px;
  background: #222831; color: var(--dim);
  font: inherit; font-size: 11px; font-weight: 600;
  padding: 5px 9px;
}
.chip[aria-pressed="true"] { background: #2e3742; color: var(--ink); }

/* ---------- key caps ---------- */

.cap {
  display: grid;
  place-items: center;
  border: 0;
  color: var(--ink);
  background: linear-gradient(#2b313a, var(--cap));
  box-shadow: 0 4px 0 var(--cap-lip), 0 6px 10px rgba(0,0,0,.45);
  font: inherit;
  transition: transform .04s, box-shadow .04s, background .04s;
}
.cap.on {
  transform: translateY(4px);
  background: #323945;
  box-shadow: 0 0 0 2px var(--tint, #4b5462), 0 0 14px -2px var(--tint, transparent);
}

/* ---------- bumpers and triggers ---------- */

.bumper, .trigger {
  width: calc(var(--unit) * 1.5);
  height: calc(var(--unit) * .62);
  border-radius: 14px;
  font-size: calc(var(--unit) * .24);
  color: var(--dim);
}
.bumper.on { color: var(--ink); }

.trigger {
  position: relative;
  overflow: hidden;
  background: #1d222a;
  box-shadow: 0 4px 0 var(--cap-lip), 0 6px 10px rgba(0,0,0,.45);
  display: grid;
  place-items: center;
}
.trigger .fill {
  position: absolute; inset: auto 0 0 0;
  height: 0%;
  background: linear-gradient(#3c6f89, #2f5568);
  transition: height .05s linear;
}
.trigger .tag { position: relative; font-weight: 700; }
.trigger.on .tag { color: var(--ink); }

/* ---------- d-pad: one touch zone, eight directions ---------- */

#dpad {
  position: relative;
  width: calc(var(--unit) * 2.35);
  height: calc(var(--unit) * 2.35);
}
#dpad .arm {
  position: absolute;
  display: grid; place-items: center;
  background: linear-gradient(#2b313a, var(--cap));
  box-shadow: 0 4px 0 var(--cap-lip), 0 6px 10px rgba(0,0,0,.45);
  color: var(--dim);
  font-size: calc(var(--unit) * .24);
  transition: background .05s, color .05s;
}
#dpad .arm.on { background: #3a4451; color: var(--ink); }
#dpad .hub   { position: absolute; left: 33%; top: 33%; width: 34%; height: 34%;
               background: #20252d; border-radius: 6px; }
#dpad .up    { left: 34%; top: 0;    width: 32%; height: 37%; border-radius: 12px 12px 4px 4px; }
#dpad .down  { left: 34%; bottom: 0; width: 32%; height: 37%; border-radius: 4px 4px 12px 12px; }
#dpad .left  { top: 34%; left: 0;    width: 37%; height: 32%; border-radius: 12px 4px 4px 12px; }
#dpad .right { top: 34%; right: 0;   width: 37%; height: 32%; border-radius: 4px 12px 12px 4px; }

/* ---------- face buttons ---------- */

#face {
  position: relative;
  --s: calc(var(--unit) * .88);
  width: calc(var(--unit) * 2.5);
  height: calc(var(--unit) * 2.5);
}
#face .cap {
  position: absolute;
  width: var(--s);
  height: var(--s);
  border-radius: 50%;
  font-weight: 700;
  font-size: calc(var(--s) * .42);
}
#Y { top: 0;    left: calc(50% - var(--s) / 2); color: var(--y); --tint: var(--y); }
#A { bottom: 0; left: calc(50% - var(--s) / 2); color: var(--a); --tint: var(--a); }
#X { left: 0;   top: calc(50% - var(--s) / 2);  color: var(--x); --tint: var(--x); }
#B { right: 0;  top: calc(50% - var(--s) / 2);  color: var(--b); --tint: var(--b); }

/* ---------- sticks ---------- */

.zone {
  position: relative;
  width: calc(var(--unit) * 2.35);
  height: calc(var(--unit) * 2.35);
}
.base {
  position: absolute;
  left: 50%; top: 50%;
  width: calc(var(--unit) * 1.75);
  height: calc(var(--unit) * 1.75);
  margin: calc(var(--unit) * -0.875);
  border-radius: 50%;
  background: #14181e;
  box-shadow: inset 0 3px 8px rgba(0,0,0,.7), 0 0 0 1px #262c35;
}
.knob {
  position: absolute;
  left: 50%; top: 50%;
  width: 56%; height: 56%;
  margin: -28%;
  border-radius: 50%;
  background: linear-gradient(#333b46, #232932);
  box-shadow: 0 3px 0 var(--cap-lip), 0 5px 12px rgba(0,0,0,.5);
}
.zone.held .base { box-shadow: inset 0 3px 8px rgba(0,0,0,.7), 0 0 0 2px #3a4553; }

/* ---------- small keys: LS, RS, Select, Start ---------- */

.mini {
  width: calc(var(--unit) * 1.05);
  height: calc(var(--unit) * .5);
  border-radius: 12px;
  font-size: calc(var(--unit) * .21);
  font-weight: 700;
  color: var(--dim);
}
.mini.on { color: var(--ink); }

#midMid { flex-direction: column; gap: var(--gap); }

/* ---------- rotate notice ---------- */

#notice {
  position: fixed; inset: 0;
  display: none;
  place-items: center;
  text-align: center;
  padding: 24px;
  background: var(--bg);
  z-index: 20;
}
#notice p { color: var(--dim); max-width: 34ch; line-height: 1.5; font-weight: 500; }
#notice strong { display: block; color: var(--ink); font-size: 20px; margin-bottom: 8px; }

@media (orientation: portrait) {
  #notice { display: grid; }
}

/* very short screens: drop the bottom row tighter and shrink the caps a touch */
@media (max-height: 340px) {
  :root { --unit: clamp(30px, 13.5vh, 46px); }
}
</style>
</head>
<body>

<div id="board">

  <div class="cell" id="topLeft">
    <div class="trigger" id="LT"><span class="fill"></span><span class="tag">L2</span></div>
    <button class="cap bumper" id="LB">L1</button>
  </div>

  <div class="cell" id="topMid">
    <div id="bar">
      <span id="dot"></span>
      <span id="label">Connecting</span>
      <button class="chip" id="haptics" aria-pressed="true">Buzz</button>
      <button class="chip" id="full">Full screen</button>
    </div>
  </div>

  <div class="cell" id="topRight">
    <button class="cap bumper" id="RB">R1</button>
    <div class="trigger" id="RT"><span class="fill"></span><span class="tag">R2</span></div>
  </div>

  <div class="cell" id="midLeft">
    <div id="dpad">
      <span class="hub"></span>
      <span class="arm up">&#9650;</span>
      <span class="arm down">&#9660;</span>
      <span class="arm left">&#9664;</span>
      <span class="arm right">&#9654;</span>
    </div>
  </div>

  <div class="cell" id="midMid">
    <button class="cap mini" id="SELECT">Select</button>
    <button class="cap mini" id="START">Start</button>
  </div>

  <div class="cell" id="midRight">
    <div id="face">
      <button class="cap" id="Y">Y</button>
      <button class="cap" id="X">X</button>
      <button class="cap" id="B">B</button>
      <button class="cap" id="A">A</button>
    </div>
  </div>

  <div class="cell" id="lowLeft">
    <div class="zone" id="zoneL">
      <div class="base"><div class="knob"></div></div>
    </div>
    <button class="cap mini" id="LS">LS</button>
  </div>

  <div class="cell" id="lowRight">
    <button class="cap mini" id="RS">RS</button>
    <div class="zone" id="zoneR">
      <div class="base"><div class="knob"></div></div>
    </div>
  </div>

</div>

<div id="notice">
  <p><strong>Turn your phone sideways</strong>
  The pad needs landscape to fit. Rotate and it starts straight away.</p>
</div>

<script>
"use strict";

/* ---------------- connection ---------------- */

var ws = null, retry = 0, wake = null;
var bar = document.getElementById("bar");
var label = document.getElementById("label");

function connect() {
  ws = new WebSocket("ws://" + location.hostname + ":8081");

  ws.onopen = function () {
    retry = 0;
    bar.className = "live";
    label.textContent = "Connected";
    keepAwake();
  };

  ws.onmessage = function (e) {
    var d = {};
    try { d = JSON.parse(e.data); } catch (err) { return; }
    if (d.player) label.textContent = "Player " + d.player;
    if (d.error) { bar.className = "lost"; label.textContent = d.error; }
  };

  ws.onclose = function () {
    bar.className = "lost";
    label.textContent = "Reconnecting";
    retry = Math.min(retry + 1, 6);
    setTimeout(connect, 300 * retry);
  };

  ws.onerror = function () { try { ws.close(); } catch (err) {} };
}

function send(msg) {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify(msg));
}

async function keepAwake() {
  try {
    if ("wakeLock" in navigator && !wake) wake = await navigator.wakeLock.request("screen");
  } catch (err) {}
}
document.addEventListener("visibilitychange", function () {
  if (document.visibilityState === "visible") { wake = null; keepAwake(); }
});

/* ---------------- options ---------------- */

var buzz = true;
var buzzBtn = document.getElementById("haptics");

buzzBtn.addEventListener("click", function () {
  buzz = !buzz;
  buzzBtn.setAttribute("aria-pressed", buzz ? "true" : "false");
});

document.getElementById("full").addEventListener("click", function () {
  if (document.fullscreenElement) document.exitFullscreen();
  else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
});

function tick(ms) { if (buzz && navigator.vibrate) navigator.vibrate(ms); }

document.addEventListener("contextmenu", function (e) { e.preventDefault(); });
document.addEventListener("dblclick", function (e) { e.preventDefault(); });
document.addEventListener("gesturestart", function (e) { e.preventDefault(); });

/* ---------------- buttons ---------------- */

var held = {};

function setButton(name, down) {
  if (!!held[name] === !!down) return;
  held[name] = down;
  send({ type: "button", button: name, pressed: down });
  if (down) tick(8);
}

function wireButton(id, name) {
  var el = document.getElementById(id);

  el.addEventListener("pointerdown", function (e) {
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    el.classList.add("on");
    setButton(name, true);
  });

  function up(e) {
    el.classList.remove("on");
    setButton(name, false);
    if (e && el.hasPointerCapture && el.hasPointerCapture(e.pointerId)) {
      el.releasePointerCapture(e.pointerId);
    }
  }

  el.addEventListener("pointerup", up);
  el.addEventListener("pointercancel", up);
  el.addEventListener("lostpointercapture", up);
}

["A", "B", "X", "Y", "LB", "RB", "LS", "RS", "SELECT", "START"].forEach(function (id) {
  wireButton(id, id);
});

/* ---------------- d-pad: eight directions from one touch ---------------- */

(function () {
  var pad = document.getElementById("dpad");
  var arms = {
    UP: pad.querySelector(".up"),
    DOWN: pad.querySelector(".down"),
    LEFT: pad.querySelector(".left"),
    RIGHT: pad.querySelector(".right")
  };
  var pointer = null;

  function apply(dirs) {
    Object.keys(arms).forEach(function (d) {
      var on = dirs.indexOf(d) !== -1;
      arms[d].classList.toggle("on", on);
      setButton(d, on);
    });
  }

  function read(e) {
    var r = pad.getBoundingClientRect();
    var dx = e.clientX - (r.left + r.width / 2);
    var dy = e.clientY - (r.top + r.height / 2);
    var dist = Math.hypot(dx, dy);
    if (dist < r.width * 0.14) return apply([]);

    var deg = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
    var sector = Math.round(deg / 45) % 8;
    apply([
      ["RIGHT"], ["RIGHT", "DOWN"], ["DOWN"], ["DOWN", "LEFT"],
      ["LEFT"], ["LEFT", "UP"], ["UP"], ["UP", "RIGHT"]
    ][sector]);
  }

  pad.addEventListener("pointerdown", function (e) {
    e.preventDefault();
    pointer = e.pointerId;
    pad.setPointerCapture(e.pointerId);
    read(e);
    tick(8);
  });

  pad.addEventListener("pointermove", function (e) {
    if (e.pointerId === pointer) read(e);
  });

  function release(e) {
    if (e.pointerId !== pointer) return;
    pointer = null;
    apply([]);
  }

  pad.addEventListener("pointerup", release);
  pad.addEventListener("pointercancel", release);
  pad.addEventListener("lostpointercapture", release);
})();

/* ---------------- triggers: press for full, slide up to ease off ---------------- */

function wireTrigger(id, name) {
  var el = document.getElementById(id);
  var fill = el.querySelector(".fill");
  var pointer = null, startY = 0, last = -1;
  var travel = 70;

  function level(v) {
    v = Math.max(0, Math.min(1, v));
    if (Math.abs(v - last) < 0.02 && v !== 0 && v !== 1) return;
    last = v;
    fill.style.height = (v * 100) + "%";
    send({ type: "trigger", trigger: name, value: v });
  }

  el.addEventListener("pointerdown", function (e) {
    e.preventDefault();
    pointer = e.pointerId;
    startY = e.clientY;
    el.setPointerCapture(e.pointerId);
    el.classList.add("on");
    level(1);
    tick(8);
  });

  el.addEventListener("pointermove", function (e) {
    if (e.pointerId !== pointer) return;
    level(1 - (startY - e.clientY) / travel);
  });

  function release(e) {
    if (e.pointerId !== pointer) return;
    pointer = null;
    el.classList.remove("on");
    level(0);
  }

  el.addEventListener("pointerup", release);
  el.addEventListener("pointercancel", release);
  el.addEventListener("lostpointercapture", release);
}

wireTrigger("LT", "LT");
wireTrigger("RT", "RT");

/* ---------------- sticks: floating, multi-touch, frame-paced ---------------- */

function wireStick(zoneId, name) {
  var zone = document.getElementById(zoneId);
  var base = zone.querySelector(".base");
  var knob = zone.querySelector(".knob");
  var pointer = null, originX = 0, originY = 0;
  var radius = 0, queued = null, sent = { x: 0, y: 0 };

  function flush() {
    queued = null;
    if (Math.abs(sent.x - pending.x) < 0.01 && Math.abs(sent.y - pending.y) < 0.01) return;
    sent = { x: pending.x, y: pending.y };
    send({ type: "stick", stick: name, x: sent.x, y: sent.y });
  }

  var pending = { x: 0, y: 0 };

  function move(e) {
    var dx = e.clientX - originX;
    var dy = e.clientY - originY;
    var dist = Math.hypot(dx, dy);
    if (dist > radius) { dx *= radius / dist; dy *= radius / dist; }

    knob.style.transform = "translate(" + dx + "px," + dy + "px)";
    pending.x = dx / radius;
    pending.y = dy / radius;
    if (!queued) queued = requestAnimationFrame(flush);
  }

  zone.addEventListener("pointerdown", function (e) {
    e.preventDefault();
    pointer = e.pointerId;
    zone.setPointerCapture(e.pointerId);

    var zr = zone.getBoundingClientRect();
    var size = base.offsetWidth;
    radius = size * 0.38;

    // the base follows the thumb, clamped inside the zone
    var x = Math.min(Math.max(e.clientX - zr.left, size / 2), zr.width - size / 2);
    var y = Math.min(Math.max(e.clientY - zr.top, size / 2), zr.height - size / 2);
    base.style.left = x + "px";
    base.style.top = y + "px";

    originX = zr.left + x;
    originY = zr.top + y;
    zone.classList.add("held");
    move(e);
  });

  zone.addEventListener("pointermove", function (e) {
    if (e.pointerId === pointer) move(e);
  });

  function release(e) {
    if (e.pointerId !== pointer) return;
    pointer = null;
    zone.classList.remove("held");
    knob.style.transform = "translate(0px,0px)";
    base.style.left = "50%";
    base.style.top = "50%";
    pending.x = 0; pending.y = 0;
    sent = { x: 1, y: 1 };
    flush();
  }

  zone.addEventListener("pointerup", release);
  zone.addEventListener("pointercancel", release);
  zone.addEventListener("lostpointercapture", release);
}

wireStick("zoneL", "LEFT");
wireStick("zoneR", "RIGHT");

/* release everything if the page is backgrounded mid-press */
window.addEventListener("blur", function () {
  Object.keys(held).forEach(function (n) { setButton(n, false); });
  document.querySelectorAll(".on").forEach(function (el) { el.classList.remove("on"); });
});

connect();
</script>
</body>
</html>
"""


# ============================================================
# VIRTUAL CONTROLLER
# ============================================================

BUTTON_CODES = {
    "A": ecodes.BTN_SOUTH,
    "B": ecodes.BTN_EAST,
    "X": ecodes.BTN_WEST,
    "Y": ecodes.BTN_NORTH,
    "LB": ecodes.BTN_TL,
    "RB": ecodes.BTN_TR,
    "LS": ecodes.BTN_THUMBL,   # left stick click (a.k.a. L3)
    "RS": ecodes.BTN_THUMBR,   # right stick click (a.k.a. R3)
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


def stick_axis():
    return AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)


def trigger_axis():
    return AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)


def hat_axis():
    return AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)


class VirtualController:
    def __init__(self, player):
        self.player = player

        capabilities = {
            ecodes.EV_KEY: sorted(set(BUTTON_CODES.values())),
            ecodes.EV_ABS: [
                (ecodes.ABS_X, stick_axis()),
                (ecodes.ABS_Y, stick_axis()),
                (ecodes.ABS_RX, stick_axis()),
                (ecodes.ABS_RY, stick_axis()),
                (ecodes.ABS_Z, trigger_axis()),
                (ecodes.ABS_RZ, trigger_axis()),
                (ecodes.ABS_HAT0X, hat_axis()),
                (ecodes.ABS_HAT0Y, hat_axis()),
            ],
        }

        # Xbox 360 ids so SDL, Steam and Proton pick up the right button map
        self.ui = UInput(
            capabilities,
            name=f"Phone Controller {player}",
            vendor=0x045E,
            product=0x028E,
            version=0x0114,
        )

        self.hat = {ecodes.ABS_HAT0X: 0, ecodes.ABS_HAT0Y: 0}
        print(f"[+] Controller {player} created ({self.ui.device.path})")

    # ---- input ----

    def button(self, name, pressed):
        code = BUTTON_CODES.get(name)
        if code is None:
            return

        self.ui.write(ecodes.EV_KEY, code, 1 if pressed else 0)

        # Mirror the d-pad onto the hat axes; some games only read one or the other.
        if name in HAT_AXIS:
            axis, direction = HAT_AXIS[name]
            value = direction if pressed else 0
            if not pressed and self.hat[axis] != direction:
                value = self.hat[axis]
            if self.hat[axis] != value:
                self.hat[axis] = value
                self.ui.write(ecodes.EV_ABS, axis, value)

        self.ui.syn()

    def trigger(self, name, value):
        try:
            value = int(float(value) * 255)
        except (TypeError, ValueError):
            return

        value = max(0, min(255, value))
        axis = ecodes.ABS_Z if name == "LT" else ecodes.ABS_RZ if name == "RT" else None
        if axis is None:
            return

        self.ui.write(ecodes.EV_ABS, axis, value)
        self.ui.syn()

    def stick(self, name, x, y):
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            return

        if (x * x + y * y) ** 0.5 < STICK_DEADZONE:
            x = y = 0.0

        x = int(max(-1.0, min(1.0, x)) * 32767)
        y = int(max(-1.0, min(1.0, y)) * 32767)

        if name == "LEFT":
            self.ui.write(ecodes.EV_ABS, ecodes.ABS_X, x)
            self.ui.write(ecodes.EV_ABS, ecodes.ABS_Y, y)
        elif name == "RIGHT":
            self.ui.write(ecodes.EV_ABS, ecodes.ABS_RX, x)
            self.ui.write(ecodes.EV_ABS, ecodes.ABS_RY, y)
        else:
            return

        self.ui.syn()

    def reset(self):
        """Centre everything, so a dropped phone never leaves a key stuck down."""
        for code in set(BUTTON_CODES.values()):
            self.ui.write(ecodes.EV_KEY, code, 0)
        for axis in (ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_RX, ecodes.ABS_RY,
                     ecodes.ABS_Z, ecodes.ABS_RZ, ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
            self.ui.write(ecodes.EV_ABS, axis, 0)
        self.ui.syn()

    def close(self):
        try:
            self.reset()
        finally:
            self.ui.close()
        print(f"[-] Controller {self.player} removed")


# ============================================================
# SLOT MANAGEMENT
# ============================================================

controllers = {}


def claim_slot():
    for player in range(1, MAX_PLAYERS + 1):
        if player not in controllers:
            controllers[player] = VirtualController(player)
            return player, controllers[player]
    return None, None


def release_slot(player):
    controller = controllers.pop(player, None)
    if controller:
        controller.close()


# ============================================================
# WEBSOCKET SERVER
# ============================================================

async def websocket_handler(websocket, path=None):
    try:
        player, controller = claim_slot()
    except PermissionError:
        await websocket.send(json.dumps({"error": "Server cannot open /dev/uinput"}))
        print("[!] Permission denied on /dev/uinput - run with sudo or add a udev rule")
        return

    if controller is None:
        await websocket.send(json.dumps({"error": "All player slots are full"}))
        await websocket.close()
        return

    print(f"[+] Phone connected -> Player {player}")
    await websocket.send(json.dumps({"player": player}))

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            kind = data.get("type")

            if kind == "button":
                controller.button(data.get("button"), bool(data.get("pressed")))
            elif kind == "trigger":
                controller.trigger(data.get("trigger"), data.get("value", 0))
            elif kind == "stick":
                controller.stick(data.get("stick"), data.get("x", 0), data.get("y", 0))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        print(f"[-] Phone disconnected -> Player {player}")
        release_slot(player)


# ============================================================
# HTTP SERVER
# ============================================================

PAGE = HTML.encode("utf-8")


class WebHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(PAGE)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(PAGE)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, fmt, *args):
        return


def start_http():
    ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), WebHandler).serve_forever()


def lan_address():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


# ============================================================
# MAIN
# ============================================================

async def main():
    address = lan_address()

    print("\n  Phone Controller")
    print("  " + "-" * 34)
    print(f"  Open on your phone : http://{address}:{HTTP_PORT}")
    print(f"  WebSocket port     : {WEBSOCKET_PORT}")
    print(f"  Player slots       : {MAX_PLAYERS}")
    print("  Ctrl+C to stop\n")

    Thread(target=start_http, daemon=True).start()

    async with websockets.serve(
        websocket_handler,
        "0.0.0.0",
        WEBSOCKET_PORT,
        ping_interval=15,
        ping_timeout=15,
        max_size=4096,
    ):
        await asyncio.Future()


def cleanup():
    for player in list(controllers):
        release_slot(player)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()
