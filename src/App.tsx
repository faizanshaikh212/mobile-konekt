import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import { Dpad, GameButton, Stick, Trigger } from "./components/Controls";
import { LayoutControl } from "./components/LayoutControl";
import { useLayout } from "./hooks/useLayout";
import { PRESETS } from "./presets";
import type { Connection, Layout } from "./types/controller";
import { APP_CONFIG } from "./config/appConfig";
import { getStored, makeDeviceToken, setStored } from "./lib/browserStorage";

function App() {
  const socket = useRef<WebSocket | null>(null);
  const connectRef = useRef<() => void>(() => {});
  const reconnectTimer = useRef<number | undefined>(undefined);
  const mounted = useRef(false);
  const held = useRef(new Set<string>());
  const wakeLock = useRef<WakeLockSentinel | null>(null);
  const [connection, setConnection] = useState<Connection>("connecting");
  const [player, setPlayer] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [haptics, setHaptics] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [pressed, setPressed] = useState<Set<string>>(new Set());
  const [triggerValues, setTriggerValues] = useState({ LT: 0, RT: 0 });
  const [layoutId, setLayoutId] = useState("");
  const [layoutCode, setLayoutCode] = useState("");
  const [layoutMessage, setLayoutMessage] = useState("");
  const deviceToken = useRef<string>(
    getStored("mobilekonekt-device-token") || makeDeviceToken(),
  );
  const vibrate = useCallback(
    (duration = 8) => {
      if (haptics && navigator.vibrate) navigator.vibrate(duration);
    },
    [haptics],
  );
  const send = useCallback((message: Record<string, unknown>) => {
    if (socket.current?.readyState === WebSocket.OPEN)
      socket.current.send(JSON.stringify(message));
  }, []);
  const {
    layout,
    editing,
    startEditing,
    save,
    reset,
    applyPreset,
    move,
    applyRemote,
    applyLayout,
  } = useLayout((value) =>
    send({
      type: "settings",
      token: deviceToken.current,
      layout: value,
      settings: { haptics },
    }),
  );
  const shareLayout = async () => {
    try {
      const response = await fetch("/api/layouts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          layout,
          device_id: deviceToken.current,
          label: navigator.userAgent.slice(0, 120),
        }),
      });
      if (!response.ok) throw new Error("Unable to publish layout");
      const data = (await response.json()) as { id?: string };
      if (!data.id) throw new Error("The server returned no layout number");
      setLayoutId(data.id);
      setLayoutMessage("Layout number ready to share.");
      await navigator.clipboard?.writeText(data.id).catch(() => {});
    } catch {
      setLayoutMessage("Connect to the host before sharing a layout.");
    }
  };
  const loadSharedLayout = async () => {
    const id = layoutCode.trim();
    if (!/^\d{6}$/.test(id)) {
      setLayoutMessage("Enter a six-digit layout number.");
      return;
    }
    try {
      const response = await fetch(`/api/layouts/${id}`);
      if (!response.ok) throw new Error("Layout not found");
      const data = (await response.json()) as { layout?: Layout };
      if (!data.layout) throw new Error("Invalid layout");
      applyLayout(data.layout);
      setLayoutId(id);
      setLayoutMessage("Shared layout loaded.");
    } catch {
      setLayoutMessage("That layout number was not found on this host.");
    }
  };
  useEffect(() => {
    setStored("mobilekonekt-device-token", deviceToken.current);
  }, []);
  const setButton = useCallback(
    (name: string, down: boolean) => {
      if (held.current.has(name) === down) return;
      if (down) held.current.add(name);
      else held.current.delete(name);
      setPressed(new Set(held.current));
      send({ type: "button", button: name, pressed: down });
      if (down) vibrate();
    },
    [send, vibrate],
  );
  const connect = useCallback(() => {
    if (!mounted.current) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.hostname}:8081`);
    socket.current = ws;
    setConnection("connecting");
    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          type: "handshake",
          token: deviceToken.current,
          device_name: navigator.userAgent.slice(0, 120),
        }),
      );
      setConnection("connected");
      setError("");
      reconnectTimer.current = undefined;
      if ("wakeLock" in navigator)
        navigator.wakeLock
          ?.request("screen")
          .then((lock) => {
            wakeLock.current = lock;
          })
          .catch(() => {});
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as {
          player?: number;
          error?: string;
          layout?: Record<string, { x: number; y: number }>;
          settings?: { haptics?: boolean };
          type?: string;
        };
        if (
          data.type === "state" ||
          data.type === "player_update" ||
          typeof data.player === "number"
        ) {
          if (typeof data.player === "number") setPlayer(data.player);
        }
        if (data.layout)
          applyRemote(data.layout as Parameters<typeof applyRemote>[0]);
        if (data.settings?.haptics !== undefined)
          setHaptics(data.settings.haptics);
        if (data.error) {
          setError(data.error);
          setConnection("error");
        }
      } catch {
        /* Ignore malformed server messages. */
      }
    };
    ws.onclose = () => {
      if (!mounted.current || socket.current !== ws) return;
      setConnection("reconnecting");
      setPlayer(null);
      if (!reconnectTimer.current)
        reconnectTimer.current = window.setTimeout(
          () => connectRef.current(),
          900,
        );
    };
    ws.onerror = () => ws.close();
  }, [applyRemote]);
  useEffect(() => {
    mounted.current = true;
    connectRef.current = connect;
    const initial = window.setTimeout(connect, 0);
    return () => {
      window.clearTimeout(initial);
      if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
      reconnectTimer.current = undefined;
      const activeSocket = socket.current;
      socket.current = null;
      activeSocket?.close();
      wakeLock.current?.release().catch(() => {});
    };
  }, [connect]);
  useEffect(() => {
    const resetInputs = () => {
      held.current.forEach((name) =>
        send({ type: "button", button: name, pressed: false }),
      );
      held.current.clear();
      setPressed(new Set());
      send({ type: "trigger", trigger: "LT", value: 0 });
      send({ type: "trigger", trigger: "RT", value: 0 });
      send({ type: "stick", stick: "LEFT", x: 0, y: 0 });
      send({ type: "stick", stick: "RIGHT", x: 0, y: 0 });
      setTriggerValues({ LT: 0, RT: 0 });
    };
    const wake = () => {
      if (document.visibilityState === "visible" && "wakeLock" in navigator)
        navigator.wakeLock
          ?.request("screen")
          .then((lock) => {
            wakeLock.current = lock;
          })
          .catch(() => {});
    };
    window.addEventListener("blur", resetInputs);
    document.addEventListener("visibilitychange", wake);
    return () => {
      window.removeEventListener("blur", resetInputs);
      document.removeEventListener("visibilitychange", wake);
    };
  }, [send]);
  const toggleFullscreen = async () => {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen?.();
    setFullscreen(Boolean(document.fullscreenElement));
  };
  const trigger = (name: "LT" | "RT", value: number) => {
    setTriggerValues((current) => ({ ...current, [name]: value }));
    send({ type: "trigger", trigger: name, value });
  };
  const stick = (name: "LEFT" | "RIGHT", x: number, y: number) =>
    send({ type: "stick", stick: name, x, y });

  return (
    <main
      className={`controller ${editing ? "layout-editing" : ""}`}
      aria-label={`${APP_CONFIG.name} gamepad`}
    >
      <header className="topbar">
        <div className="brand">
          <img className="brand-mark" src={APP_CONFIG.logoPath} alt="" />
          <span>{APP_CONFIG.name}</span>
        </div>
        <div className={`connection ${connection}`} role="status">
          <span className="status-dot" />
          {error ||
            (connection === "connected"
              ? APP_CONFIG.status.connected(player)
              : connection === "reconnecting"
                ? APP_CONFIG.status.reconnecting
                : APP_CONFIG.status.connecting)}
        </div>
      </header>
      <div className="control-area">
        <div className="toolbar">
          <button
            className={`tool-button ${haptics ? "active" : ""}`}
            aria-pressed={haptics}
            onClick={() => setHaptics((value) => !value)}
          >
            <span aria-hidden="true">⌁</span>
            <span className="tool-label">{APP_CONFIG.toolbar.haptics}</span>
          </button>
          <button
            className="tool-button"
            aria-pressed={fullscreen}
            onClick={() => void toggleFullscreen()}
          >
            <span aria-hidden="true">{fullscreen ? "⤢" : "⛶"}</span>
            <span className="tool-label">{APP_CONFIG.toolbar.fullscreen}</span>
          </button>
          {editing ? (
            <>
              <select
                className="preset-select"
                aria-label={APP_CONFIG.toolbar.preset}
                defaultValue=""
                onChange={(event) => applyPreset(event.target.value)}
              >
                <option value="" disabled>
                  {APP_CONFIG.toolbar.preset}…
                </option>
                {PRESETS.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {
                      APP_CONFIG.presets[
                        preset.id as keyof typeof APP_CONFIG.presets
                      ].label
                    }
                  </option>
                ))}
              </select>
              <button className="tool-button" onClick={reset}>
                {APP_CONFIG.toolbar.reset}
              </button>
              <button className="tool-button save-button" onClick={save}>
                {APP_CONFIG.toolbar.save}
              </button>
              <button className="tool-button" onClick={() => void shareLayout()}>
                Share layout
              </button>
            </>
          ) : (
            <button className="tool-button edit-button" onClick={startEditing}>
              {APP_CONFIG.toolbar.edit}
            </button>
          )}
        </div>
        {editing && <p className="editing-hint">{APP_CONFIG.editing.hint}</p>}
        <div className="layout-sharing">
          {layoutId && (
            <button
              className="layout-id"
              title="Copy layout number"
              onClick={() => void navigator.clipboard?.writeText(layoutId)}
            >
              Layout #{layoutId}
            </button>
          )}
          <input
            value={layoutCode}
            inputMode="numeric"
            maxLength={6}
            placeholder="Enter layout #"
            aria-label="Shared layout number"
            onChange={(event) => setLayoutCode(event.target.value.replace(/\D/g, ""))}
          />
          <button className="tool-button" onClick={() => void loadSharedLayout()}>
            Load
          </button>
          {layoutMessage && <span>{layoutMessage}</span>}
        </div>
      </div>
      <section className="deck">
        <div className="center-brand" aria-hidden="true">
          <strong>{APP_CONFIG.centerLabel}</strong>
          <span>
            {APP_CONFIG.tagline} · {APP_CONFIG.centerHint}
          </span>
        </div>
        {(
          [
            [
              "lt",
              <Trigger
                name="LT"
                value={triggerValues.LT}
                onValue={(value) => trigger("LT", value)}
              />,
            ],
            [
              "lb",
              <GameButton
                name="LB"
                label={APP_CONFIG.controls.lb}
                pressed={pressed.has("LB")}
                onChange={setButton}
              />,
            ],
            ["dpad", <Dpad onChange={setButton} pressed={pressed} />],
            [
              "left-stick",
              <Stick
                name="LEFT"
                label={APP_CONFIG.controls.leftStick}
                onMove={(x, y) => stick("LEFT", x, y)}
              />,
            ],
            [
              "ls",
              <GameButton
                name="LS"
                label={APP_CONFIG.controls.ls}
                pressed={pressed.has("LS")}
                onChange={setButton}
              />,
            ],
            [
              "select",
              <GameButton
                name="SELECT"
                label={APP_CONFIG.controls.select}
                pressed={pressed.has("SELECT")}
                onChange={setButton}
              />,
            ],
            [
              "start",
              <GameButton
                name="START"
                label={APP_CONFIG.controls.start}
                pressed={pressed.has("START")}
                onChange={setButton}
              />,
            ],
            [
              "rb",
              <GameButton
                name="RB"
                label={APP_CONFIG.controls.rb}
                pressed={pressed.has("RB")}
                onChange={setButton}
              />,
            ],
            [
              "rt",
              <Trigger
                name="RT"
                value={triggerValues.RT}
                onValue={(value) => trigger("RT", value)}
              />,
            ],
            [
              "y",
              <GameButton
                name="Y"
                label={APP_CONFIG.controls.y}
                pressed={pressed.has("Y")}
                onChange={setButton}
              />,
            ],
            [
              "x",
              <GameButton
                name="X"
                label={APP_CONFIG.controls.x}
                pressed={pressed.has("X")}
                onChange={setButton}
              />,
            ],
            [
              "b",
              <GameButton
                name="B"
                label={APP_CONFIG.controls.b}
                pressed={pressed.has("B")}
                onChange={setButton}
              />,
            ],
            [
              "a",
              <GameButton
                name="A"
                label={APP_CONFIG.controls.a}
                pressed={pressed.has("A")}
                onChange={setButton}
              />,
            ],
            [
              "rs",
              <GameButton
                name="RS"
                label={APP_CONFIG.controls.rs}
                pressed={pressed.has("RS")}
                onChange={setButton}
              />,
            ],
            [
              "right-stick",
              <Stick
                name="RIGHT"
                label={APP_CONFIG.controls.rightStick}
                onMove={(x, y) => stick("RIGHT", x, y)}
              />,
            ],
          ] as const
        ).map(([id, control]) => (
          <LayoutControl
            key={id}
            id={id}
            point={layout[id]}
            editing={editing}
            onMove={move}
            className={`control-${id}`}
          >
            {control}
          </LayoutControl>
        ))}
      </section>
      <div className="rotate-hint">
        <span aria-hidden="true">↻</span> {APP_CONFIG.rotateHint}
      </div>
    </main>
  );
}

export default App;
