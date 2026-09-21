# MobileKonekt

MobileKonekt turns phones into Linux virtual gamepads. The **host backend only
runs on Linux** because it creates an evdev `/dev/uinput` controller. Windows
and macOS are not supported host platforms. Android and iPhone/iPad devices
can be used as the controller client from their browser.

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

## Using a phone over USB

USB does not require a special MobileKonekt protocol: use USB tethering so the
phone and Linux host share a network interface. MobileKonekt lists every
usable IPv4 address in the admin dashboard and terminal, including interfaces
such as `usb0`, `enx...`, `rndis...`, or `wwan...`. Open the URL labelled with
that interface on the phone. The WebSocket automatically uses the same host
and ports, so this path avoids unreliable Wi-Fi.

The admin dashboard rechecks interfaces every time it refreshes (every three
seconds), so USB tethering can be enabled after MobileKonekt has already
started. Click **Refresh**, then open the newly listed USB URL on the phone.

### Android USB tethering (recommended)

1. Connect the Android phone with a USB data cable.
2. On the phone, enable **Settings → Network & internet → Hotspot & tethering
   → USB tethering**. The exact names vary by Android vendor.
3. On Linux, wait for NetworkManager to create the USB interface and start
   MobileKonekt. Find the URL marked with the new interface in the admin
   dashboard (`http://127.0.0.1:8090`) or terminal.
4. Open that URL in Chrome/Firefox on the phone. Keep USB tethering enabled
   while playing.

For a USB-only Android connection without tethering, enable **USB debugging**
and install `adb`, then run:

```sh
adb devices                 # approve the phone's debugging prompt
adb reverse tcp:8080 tcp:8080
adb reverse tcp:8081 tcp:8081
```

Open `http://127.0.0.1:8080` on the phone. `adb reverse` forwards the phone's
localhost ports to the Linux host and must be repeated after reconnecting the
phone. This method needs Android USB debugging; it does not apply to iPhone.

### iPhone/iPad USB connection

On iOS/iPadOS, enable **Personal Hotspot → Allow Others to Join**, connect the
device by USB, and trust the Linux computer if prompted. The Linux host must
have an iPhone USB networking driver/interface available (commonly provided
by `usbmuxd`/`libimobiledevice` packages on the distribution). Open the URL
shown for that USB interface. If the interface is not created, use Wi-Fi
hotspot instead; MobileKonekt cannot create the missing Linux networking
driver.

### Linux firewall and permissions

Allow the phone ports on the USB interface, not on every interface:

```sh
sudo ufw allow in on <usb-interface> to any port 8080 proto tcp
sudo ufw allow in on <usb-interface> to any port 8081 proto tcp
```

For firewalld:

```sh
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --add-port=8081/tcp --permanent
sudo firewall-cmd --reload
```

The backend also needs `/dev/uinput`. Common setup commands are:

```sh
# Arch/CachyOS/Manjaro
sudo modprobe uinput
sudo usermod -aG input "$USER"

# Debian/Ubuntu/Linux Mint
sudo modprobe uinput
sudo usermod -aG input "$USER"
```

Log out and back in after changing group membership. If your distribution
does not grant the `input` group access to `/dev/uinput`, add a udev rule
matching your distribution's policy, reload udev, and verify with
`ls -l /dev/uinput`. Do not run the whole desktop as root just to bypass this
permission.

## Frontend development

Start the Python backend and open the native Electron admin window:

```sh
npm run dev
```

`npm run dev` starts Vite with HMR alongside the Python backend and native
Electron admin panel. In Electron mode, the phone controller is served live
from Vite on port 5173, while the Python WebSocket remains on port 8081.
Frontend changes are reflected without rebuilding. The backend's port 8080
still serves the built frontend for production-style/manual backend runs.

```sh
npm run dev:web
```

Use `npm run dev:web` when you specifically want only the Vite browser/HMR
frontend on port 5173. The backend-only command is `npm run backend`. The phone-ready
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
stored in readable `state.json` and `layouts.json` files; device tokens are
encrypted/opaque while labels, settings, and full layout coordinates remain
inspectable. Development runs use `.dev-data/` at the project root;
packaged executables use a writable `userdata/` directory beside the executable.
These directories are intentionally ignored by Git. Phones generate a token in
`localStorage`, so refreshing or reconnecting restores the same device and its
preferred player. Layout changes are synchronized to the host when connected,
with local storage remaining the offline fallback. While editing a controller,
use **Share layout** to publish the current layout and receive a six-digit
layout number. Share that number with another phone on the same host, where it
can be entered and loaded from the layout-sharing controls.
The editor also supports square-cell **64×, 32×, 16×, and 8× grids** (or no
grid); dragging snaps controls to the selected grid. Use the resize handle on
an editing control to scale it, and saved/shared layouts preserve those sizes.
The admin panel also detects connected physical evdev gamepads (for example an
EvoFox pad) and lists them beside phones. Detection requires gamepad button
capabilities and rejects pointer/direct-input devices, so laptop trackpads,
touchscreens, mice, keyboards, and many 2.4 GHz receiver interfaces are not
shown as physical controllers. Physical pads can be assigned an unused player
number; the app leaves their native input handling untouched.

## Project layout

- `src/` — React 19 + TypeScript controller interface and touch/pointer input
- `backend/controller.py` — evdev virtual gamepad and player-slot management
- `backend/server.py` — HTTP static-file server and WebSocket protocol
- `backend/admin.py` and `backend/admin_assets/` — localhost-only host dashboard
- `backend/__main__.py` — executable backend module entrypoint

The virtual controller implementation uses Linux `evdev`/`uinput`; creating
controllers is therefore limited to Linux hosts with `/dev/uinput` permission.
This is why Windows and macOS are not supported as hosts, regardless of
whether the phone is connected by Wi-Fi or USB.


`npx electron-builder --linux tar.gz --publish never`