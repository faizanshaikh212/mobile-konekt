#!/usr/bin/env python3

import asyncio
import json
import os
import signal
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import websockets
from evdev import UInput, ecodes, AbsInfo


# ============================================================
# SETTINGS
# ============================================================

HTTP_PORT = 8080
WEBSOCKET_PORT = 8081

MAX_PLAYERS = 8


# ============================================================
# PHONE CONTROLLER HTML
# ============================================================

HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport"
      content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">

<title>Phone Controller</title>

<style>

* {
    box-sizing: border-box;
    user-select: none;
    -webkit-user-select: none;
    touch-action: none;
}

html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #111;
    color: white;
    font-family: sans-serif;
}

#top {
    height: 45px;
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 18px;
    background: #181818;
}

#controller {
    position: relative;
    width: 100vw;
    height: calc(100vh - 45px);
}

button {
    position: absolute;
    border: none;
    border-radius: 50%;
    background: #333;
    color: white;
    font-weight: bold;
    font-size: 18px;
}

button:active,
button.pressed {
    background: #777;
    transform: scale(0.94);
}


/* ----------------------------------------------------------
   FACE BUTTONS
---------------------------------------------------------- */

#A {
    width: 70px;
    height: 70px;
    right: 12%;
    top: 43%;
}

#B {
    width: 70px;
    height: 70px;
    right: 5%;
    top: 32%;
}

#X {
    width: 70px;
    height: 70px;
    right: 19%;
    top: 32%;
}

#Y {
    width: 70px;
    height: 70px;
    right: 12%;
    top: 21%;
}


/* ----------------------------------------------------------
   D-PAD
---------------------------------------------------------- */

.dpad {
    position: absolute;
    left: 5%;
    top: 25%;
    width: 150px;
    height: 150px;
}

.dpad button {
    width: 55px;
    height: 55px;
    border-radius: 10px;
}

#UP {
    left: 48px;
    top: 0;
}

#DOWN {
    left: 48px;
    bottom: 0;
}

#LEFT {
    left: 0;
    top: 48px;
}

#RIGHT {
    right: 0;
    top: 48px;
}


/* ----------------------------------------------------------
   SHOULDER BUTTONS
---------------------------------------------------------- */

.shoulder {
    position: absolute;
    top: 4%;
    width: 90px;
    height: 45px;
    border-radius: 12px;
}

#LB {
    left: 5%;
}

#RB {
    right: 5%;
}

.trigger {
    position: absolute;
    top: 4%;
    width: 70px;
    height: 45px;
    border-radius: 12px;
}

#LT {
    left: 27%;
}

#RT {
    right: 27%;
}


/* ----------------------------------------------------------
   START / SELECT
---------------------------------------------------------- */

.small {
    width: 70px;
    height: 40px;
    border-radius: 12px;
    top: 12%;
}

#SELECT {
    left: 39%;
}

#START {
    right: 39%;
}


/* ----------------------------------------------------------
   JOYSTICKS
---------------------------------------------------------- */

.stick {
    position: absolute;
    width: 130px;
    height: 130px;
    border-radius: 50%;
    background: #222;
    border: 3px solid #444;
}

.knob {
    position: absolute;
    width: 65px;
    height: 65px;
    left: 32px;
    top: 32px;
    border-radius: 50%;
    background: #555;
}

#leftStick {
    left: 5%;
    bottom: 7%;
}

#rightStick {
    right: 5%;
    bottom: 7%;
}

</style>
</head>

<body>

<div id="top">
    <span id="status">Connecting...</span>
</div>

<div id="controller">

    <!-- SHOULDERS -->

    <button id="LB" class="shoulder">L1</button>
    <button id="RB" class="shoulder">R1</button>

    <button id="LT" class="trigger">L2</button>
    <button id="RT" class="trigger">R2</button>


    <!-- D-PAD -->

    <div class="dpad">

        <button id="UP">▲</button>
        <button id="DOWN">▼</button>
        <button id="LEFT">◀</button>
        <button id="RIGHT">▶</button>

    </div>


    <!-- FACE BUTTONS -->

    <button id="Y">Y</button>
    <button id="X">X</button>
    <button id="B">B</button>
    <button id="A">A</button>


    <!-- SELECT / START -->

    <button id="SELECT" class="small">SELECT</button>
    <button id="START" class="small">START</button>


    <!-- STICKS -->

    <div id="leftStick" class="stick">
        <div class="knob"></div>
    </div>

    <div id="rightStick" class="stick">
        <div class="knob"></div>
    </div>

</div>


<script>

let ws;

function connect() {

    ws = new WebSocket(
        "ws://" + location.hostname + ":8081"
    );

    ws.onopen = () => {
        document.getElementById("status").innerText =
            "Connected";
    };

    ws.onclose = () => {
        document.getElementById("status").innerText =
            "Disconnected - refreshing...";
        setTimeout(connect, 2000);
    };

    ws.onmessage = (event) => {

        try {

            const data = JSON.parse(event.data);

            if (data.player) {

                document.getElementById("status").innerText =
                    "Player " + data.player;

            }

        } catch(e) {}

    };
}


function send(data) {

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
    }

}


/* ----------------------------------------------------------
   BUTTONS
---------------------------------------------------------- */

function button(id, name) {

    const element = document.getElementById(id);

    element.addEventListener("pointerdown", (e) => {

        e.preventDefault();

        element.classList.add("pressed");

        send({
            type: "button",
            button: name,
            pressed: true
        });

    });

    element.addEventListener("pointerup", (e) => {

        e.preventDefault();

        element.classList.remove("pressed");

        send({
            type: "button",
            button: name,
            pressed: false
        });

    });

    element.addEventListener("pointercancel", () => {

        element.classList.remove("pressed");

        send({
            type: "button",
            button: name,
            pressed: false
        });

    });

}


button("A", "A");
button("B", "B");
button("X", "X");
button("Y", "Y");

button("UP", "UP");
button("DOWN", "DOWN");
button("LEFT", "LEFT");
button("RIGHT", "RIGHT");

button("LB", "LB");
button("RB", "RB");

button("SELECT", "SELECT");
button("START", "START");


/* ----------------------------------------------------------
   ANALOG TRIGGERS
---------------------------------------------------------- */

function trigger(id, name) {

    const element = document.getElementById(id);

    function update(e) {

        const rect = element.getBoundingClientRect();

        let value =
            1 -
            ((e.clientY - rect.top) / rect.height);

        value = Math.max(0, Math.min(1, value));

        send({
            type: "trigger",
            trigger: name,
            value: value
        });

    }

    element.addEventListener("pointerdown", update);

    element.addEventListener("pointermove", (e) => {

        if (e.buttons) {
            update(e);
        }

    });

    element.addEventListener("pointerup", () => {

        send({
            type: "trigger",
            trigger: name,
            value: 0
        });

    });

}

trigger("LT", "LT");
trigger("RT", "RT");


/* ----------------------------------------------------------
   ANALOG STICKS
---------------------------------------------------------- */

function stick(id, name) {

    const base = document.getElementById(id);
    const knob = base.querySelector(".knob");

    let active = false;

    function update(e) {

        const rect = base.getBoundingClientRect();

        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        let dx = e.clientX - centerX;
        let dy = e.clientY - centerY;

        const max =
            rect.width / 2 - 32;

        const distance =
            Math.sqrt(dx * dx + dy * dy);

        if (distance > max) {

            dx *= max / distance;
            dy *= max / distance;

        }

        knob.style.transform =
            "translate(" + dx + "px," + dy + "px)";

        send({
            type: "stick",
            stick: name,
            x: Math.max(-1, Math.min(1, dx / max)),
            y: Math.max(-1, Math.min(1, dy / max))
        });

    }

    base.addEventListener("pointerdown", (e) => {

        active = true;
        base.setPointerCapture(e.pointerId);

        update(e);

    });

    base.addEventListener("pointermove", (e) => {

        if (active) {
            update(e);
        }

    });

    base.addEventListener("pointerup", () => {

        active = false;

        knob.style.transform =
            "translate(0px,0px)";

        send({
            type: "stick",
            stick: name,
            x: 0,
            y: 0
        });

    });

}

stick("leftStick", "LEFT");
stick("rightStick", "RIGHT");


connect();

</script>

</body>
</html>
"""


# ============================================================
# VIRTUAL CONTROLLER
# ============================================================

class VirtualController:

    def __init__(self, player):

        self.player = player

        capabilities = {

            ecodes.EV_KEY: [

                ecodes.BTN_SOUTH,   # A
                ecodes.BTN_EAST,    # B
                ecodes.BTN_WEST,    # X
                ecodes.BTN_NORTH,   # Y

                ecodes.BTN_TL,      # LB
                ecodes.BTN_TR,      # RB

                ecodes.BTN_SELECT,
                ecodes.BTN_START,

                ecodes.BTN_DPAD_UP,
                ecodes.BTN_DPAD_DOWN,
                ecodes.BTN_DPAD_LEFT,
                ecodes.BTN_DPAD_RIGHT,
            ],

            ecodes.EV_ABS: [

                (
                    ecodes.ABS_X,
                    AbsInfo(
                        0,
                        -32768,
                        32767,
                        0,
                        0,
                        0
                    )
                ),

                (
                    ecodes.ABS_Y,
                    AbsInfo(
                        0,
                        -32768,
                        32767,
                        0,
                        0,
                        0
                    )
                ),

                (
                    ecodes.ABS_RX,
                    AbsInfo(
                        0,
                        -32768,
                        32767,
                        0,
                        0,
                        0
                    )
                ),

                (
                    ecodes.ABS_RY,
                    AbsInfo(
                        0,
                        -32768,
                        32767,
                        0,
                        0,
                        0
                    )
                ),

                (
                    ecodes.ABS_Z,
                    AbsInfo(
                        0,
                        0,
                        255,
                        0,
                        0,
                        0
                    )
                ),

                (
                    ecodes.ABS_RZ,
                    AbsInfo(
                        0,
                        0,
                        255,
                        0,
                        0,
                        0
                    )
                ),

                (
                    ecodes.ABS_HAT0X,
                    AbsInfo(
                        0,
                        -1,
                        1,
                        0,
                        0,
                        0
                    )
                ),

                (
                    ecodes.ABS_HAT0Y,
                    AbsInfo(
                        0,
                        -1,
                        1,
                        0,
                        0,
                        0
                    )
                ),
            ]
        }

        self.ui = UInput(
            capabilities,
            name=f"Phone Controller {player}",
            vendor=0x045E,
            product=0x028E,
            version=0x0114
        )

        self.values = {
            "hat_x": 0,
            "hat_y": 0
        }

        self.button_codes = {

            "A": ecodes.BTN_SOUTH,
            "B": ecodes.BTN_EAST,
            "X": ecodes.BTN_WEST,
            "Y": ecodes.BTN_NORTH,

            "LB": ecodes.BTN_TL,
            "RB": ecodes.BTN_TR,

            "SELECT": ecodes.BTN_SELECT,
            "START": ecodes.BTN_START,

            "UP": ecodes.BTN_DPAD_UP,
            "DOWN": ecodes.BTN_DPAD_DOWN,
            "LEFT": ecodes.BTN_DPAD_LEFT,
            "RIGHT": ecodes.BTN_DPAD_RIGHT
        }

        print(
            f"[+] Created Controller {player}"
        )


    def button(self, name, pressed):

        code = self.button_codes.get(name)

        if code is None:
            return

        self.ui.write(
            ecodes.EV_KEY,
            code,
            1 if pressed else 0
        )

        self.ui.syn()


    def trigger(self, name, value):

        value = max(
            0,
            min(255, int(value * 255))
        )

        if name == "LT":

            self.ui.write(
                ecodes.EV_ABS,
                ecodes.ABS_Z,
                value
            )

        elif name == "RT":

            self.ui.write(
                ecodes.EV_ABS,
                ecodes.ABS_RZ,
                value
            )

        self.ui.syn()


    def stick(self, name, x, y):

        x = max(-1, min(1, float(x)))
        y = max(-1, min(1, float(y)))

        x = int(x * 32767)
        y = int(y * 32767)

        if name == "LEFT":

            self.ui.write(
                ecodes.EV_ABS,
                ecodes.ABS_X,
                x
            )

            self.ui.write(
                ecodes.EV_ABS,
                ecodes.ABS_Y,
                y
            )

        elif name == "RIGHT":

            self.ui.write(
                ecodes.EV_ABS,
                ecodes.ABS_RX,
                x
            )

            self.ui.write(
                ecodes.EV_ABS,
                ecodes.ABS_RY,
                y
            )

        self.ui.syn()


    def close(self):

        self.ui.close()

        print(
            f"[-] Removed Controller {self.player}"
        )


# ============================================================
# CONTROLLER MANAGEMENT
# ============================================================

controllers = {}
connections = {}

next_player = 1


def get_controller():

    global next_player

    for player in range(1, MAX_PLAYERS + 1):

        if player not in controllers:

            controller = VirtualController(player)

            controllers[player] = controller

            return player, controller

    return None, None


def release_controller(player):

    if player in controllers:

        controllers[player].close()

        del controllers[player]


# ============================================================
# WEBSOCKET SERVER
# ============================================================

async def websocket_handler(websocket):

    player, controller = get_controller()

    if controller is None:

        await websocket.send(
            json.dumps({
                "error": "No controller slots available"
            })
        )

        await websocket.close()

        return

    connections[websocket] = player

    print(
        f"[+] Phone connected -> Player {player}"
    )

    await websocket.send(
        json.dumps({
            "player": player
        })
    )

    try:

        async for message in websocket:

            try:

                data = json.loads(message)

            except json.JSONDecodeError:

                continue

            msg_type = data.get("type")

            if msg_type == "button":

                controller.button(
                    data.get("button"),
                    data.get("pressed", False)
                )

            elif msg_type == "trigger":

                controller.trigger(
                    data.get("trigger"),
                    data.get("value", 0)
                )

            elif msg_type == "stick":

                controller.stick(
                    data.get("stick"),
                    data.get("x", 0),
                    data.get("y", 0)
                )

    except websockets.exceptions.ConnectionClosed:
        pass

    finally:

        print(
            f"[-] Phone disconnected -> Player {player}"
        )

        release_controller(player)

        connections.pop(websocket, None)


# ============================================================
# HTTP SERVER
# ============================================================

class WebHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/":

            data = HTML.encode("utf-8")

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )

            self.send_header(
                "Content-Length",
                str(len(data))
            )

            self.end_headers()

            self.wfile.write(data)

        else:

            self.send_response(404)
            self.end_headers()


    def log_message(self, format, *args):

        return


def start_http():

    server = HTTPServer(
        ("0.0.0.0", HTTP_PORT),
        WebHandler
    )

    print(
        f"[HTTP] http://0.0.0.0:{HTTP_PORT}"
    )

    server.serve_forever()


# ============================================================
# MAIN
# ============================================================

async def main():

    print()
    print("==============================")
    print(" Phone Controller Server")
    print("==============================")
    print()

    print(
        f"HTTP server : {HTTP_PORT}"
    )

    print(
        f"WebSocket   : {WEBSOCKET_PORT}"
    )

    print()
    print(
        "Waiting for Android phones..."
    )
    print()

    Thread(
        target=start_http,
        daemon=True
    ).start()

    async with websockets.serve(
        websocket_handler,
        "0.0.0.0",
        WEBSOCKET_PORT
    ):

        await asyncio.Future()


def cleanup():

    print()
    print("Cleaning up controllers...")

    for player in list(controllers.keys()):

        release_controller(player)


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        pass

    finally:

        cleanup()
