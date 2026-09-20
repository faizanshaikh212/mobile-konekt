# MobileKonekt

MobileKonekt turns phones on the local network into Linux virtual gamepads.

## Run on the host

Build the frontend and install the frontend and Python dependencies. Arch Linux marks its system
Python as externally managed, so use a virtual environment:

```sh
source .venv/bin/activate
python -m pip install -r requirements.txt
npm run dev
```

```sh
npm install
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm run build
python -m backend
```

Open the printed HTTP address on a phone. The backend serves `dist/` on port
8080 and accepts the existing JSON websocket protocol on port 8081. It creates
one evdev controller per connected phone, and resets/releases controllers when
clients disconnect or the server shuts down. If `dist/index.html` is absent,
the HTTP endpoint returns a useful build instruction instead of failing.

The host-only administration dashboard is served separately at
`http://127.0.0.1:8090`. It tracks connected phones, labels and assigns player
slots, disconnects devices, resets inputs, and displays the LAN URL that phones
should open. It is never exposed through the phone HTTP/WebSocket services.
Override the safe localhost defaults with
`MOBILEKONEKT_ADMIN_BIND` and `MOBILEKONEKT_ADMIN_PORT`, or
`python -m backend --admin-bind 127.0.0.1 --admin-port 8090`.
Do not open port 8090 in UFW; only open 8080/8081 as needed for phone clients.
For example, allow the phone services only on your LAN interface:

```sh
sudo ufw allow in on <lan-interface> to any port 8080 proto tcp
sudo ufw allow in on <lan-interface> to any port 8081 proto tcp
# No ufw rule is needed for 8090: it is bound to localhost.
```

The Linux user running the backend needs permission to create `/dev/uinput`.
Use an appropriate udev rule or run the backend with the permissions required
by your distribution.

## Frontend development

Start the Python backend and open the native Electron admin window:

```sh
npm run dev
```

`npm run dev` is the recommended production-like development flow. It
automatically prefers `.venv/bin/python` and shows a startup chooser: open the
Electron admin panel or run the backend in a terminal. Electron mode starts the
backend, waits for the admin service, and opens the desktop window. The phone
controller is served from the current `dist/` build, so run `npm run build:web`
after frontend changes.

```sh
npm run dev:web
```

Use `npm run dev:web` when you specifically want the Vite browser/HMR frontend
on port 5173. The backend-only command is `npm run backend`. The phone-ready
production flow serves the built frontend on port 8080 and connects to the
Python WebSocket backend on port 8081.

The terminal also prints an `Admin dashboard` URL. Open that URL in a browser
on the Linux PC to manage connected phones. The admin panel is part of the
Python backend and is not shown to phone users.

For the phone-ready production flow, always run `npm run build:backend` first so
the backend can serve the generated `dist/` directory. To use the native Linux
desktop shell during development, run `npm run dev:desktop`; it starts the
Python backend and opens the host dashboard in Electron.

Choosing terminal mode starts a lightweight keyboard-driven TUI instead of
Electron. It keeps the phone URL and connected-device list visible while using
`r` to refresh, `z` to reset inputs, `n` to rename, `a` to assign a player,
`d` to disconnect, and `x` to delete saved device data. Use the arrow keys or
`j`/`k` to select a device and `q` to stop the backend.

To create a native Linux executable bundle:

```sh
python3 -m pip install -r requirements.txt
npm run build
```

This creates both `dist/MobileKonekt-*.AppImage` and
`dist/mobilekonekt_*_amd64.deb`, in addition to the PyInstaller backend under
`release/MobileKonekt/`.
The AppImage is portable; install the `.deb` on Debian/Ubuntu-based systems.
Build on the target Linux architecture. MobileKonekt targets Linux and uses `evdev` plus `/dev/uinput` to
create virtual gamepads. The user running the packaged executable must have
permission to access `/dev/uinput`.

The packaged desktop app is the complete host application. On startup it asks
whether to open the admin panel in Electron or run the backend in a terminal.
Terminal mode uses less memory and is useful when the dashboard is not needed;
Electron mode starts the bundled Python backend and opens the admin panel in a
native window. Connected phones still use their browser to open the phone URL
shown in the admin panel or terminal.

Device identity, labels, player assignments, and per-device layout/settings are
stored as JSON. Development runs use `.dev-data/` at the project root; packaged
executables use a writable `userdata/` directory beside the executable. These
directories are intentionally ignored by Git. Phones generate a token in
`localStorage`, so refreshing or reconnecting restores the same device and its
preferred player. Layout changes are synchronized to the host when connected,
with local storage remaining the offline fallback. While editing a controller,
use **Share layout** to publish the current layout and receive a six-digit
layout number. Share that number with another phone on the same host, where it
can be entered and loaded from the layout-sharing controls.

## Project layout

- `src/` — React 19 + TypeScript controller interface and touch/pointer input
- `backend/controller.py` — evdev virtual gamepad and player-slot management
- `backend/server.py` — HTTP static-file server and WebSocket protocol
- `backend/admin.py` and `backend/admin_assets/` — localhost-only host dashboard
- `backend/__main__.py` — executable backend module entrypoint

The virtual controller implementation uses Linux `evdev`/`uinput`; creating
controllers is therefore limited to Linux hosts with `/dev/uinput` permission.


`npx electron-builder --linux tar.gz --publish never`