# MobileKonekt

MobileKonekt turns phones on the local network into Linux virtual gamepads.

## Run on the host

Build the frontend and Install the frontend and Python dependencies. Arch Linux marks its system
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
python mobile-konekt.py
```

Open the printed HTTP address on a phone. The backend serves `dist/` on port
8080 and accepts the existing JSON websocket protocol on port 8081. It creates
one evdev controller per connected phone, and resets/releases controllers when
clients disconnect or the server shuts down. If `dist/index.html` is absent,
the HTTP endpoint returns a useful build instruction instead of failing.

The Linux user running the backend needs permission to create `/dev/uinput`.
Use an appropriate udev rule or run the backend with the permissions required
by your distribution.

## Frontend development

Start both the Vite frontend and Python backend together:

```sh
npm run dev
```

Activate the Python environment first so the combined command can find the
backend dependencies:

```sh
source .venv/bin/activate
npm run dev
```

The development frontend is available on port 5173. Open
`http://<your-linux-lan-ip>:5173` on the phone. The Vite page connects to the
Python WebSocket backend on port 8081 automatically. If you only want one
process, use `npm run dev:web` or `npm run backend`.

For the phone-ready production flow, always run `npm run build` first so the
backend can serve the generated `dist/` directory.

To create a native Linux executable bundle:

```sh
python3 -m pip install -r requirements.txt
npm run build
```

The bundle is written to `release/MobileKonekt/`. Build it on the target
directory. MobileKonekt targets Linux and uses `evdev` plus `/dev/uinput` to
create virtual gamepads. The user running the packaged executable must have
permission to access `/dev/uinput`.

## Project layout

- `src/` — React 19 + TypeScript controller interface and touch/pointer input
- `backend/controller.py` — evdev virtual gamepad and player-slot management
- `backend/server.py` — HTTP static-file server and WebSocket protocol
- `mobile-konekt.py` — small executable backend entrypoint
