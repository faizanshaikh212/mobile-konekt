const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("node:child_process");
const { existsSync } = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const ADMIN_URL = "http://127.0.0.1:8090";
const DEV_FRONTEND_URL = "http://127.0.0.1:5173";
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const isDevelopment = process.argv.includes("--dev") || !app.isPackaged;
let backend;
let frontend;
let mainWindow;
let startupWindow;
let terminalMode = false;
let starting = true;
let quitting = false;

// The admin panel does not need GPU compositing. Avoid initializing the GPU
// stack on Linux, which can add startup latency and produce GLib warnings.
app.disableHardwareAcceleration();

if (process.env.ELECTRON_OZONE_PLATFORM) {
  app.commandLine.appendSwitch(
    "ozone-platform",
    process.env.ELECTRON_OZONE_PLATFORM,
  );
}

function backendCommand() {
  if (isDevelopment) {
    const localPython = path.join(__dirname, "..", ".venv", "bin", "python");
    const command =
      process.env.PYTHON || (existsSync(localPython) ? localPython : "python");
    return {
      command,
      args: ["-u", "-m", "backend"],
      cwd: path.join(__dirname, ".."),
    };
  }
  const executable = path.join(
    process.resourcesPath,
    "backend-bin",
    "MobileKonekt",
  );
  return { command: executable, args: [] };
}

function openBackendInTerminal() {
  const { command, args } = backendCommand();
  backend = spawn(command, [...args, "--tui"], {
    cwd: isDevelopment ? path.join(__dirname, "..") : process.resourcesPath,
    stdio: "inherit",
    windowsHide: true,
  });
  terminalMode = true;
  console.log("[desktop] terminal backend started");
  backend.once("error", (error) => {
    console.error("[desktop] terminal backend failed to start", error);
    dialog.showErrorBox("MobileKonekt terminal failed", error.message);
    quitting = true;
    app.quit();
  });
  backend.once("exit", (code) => {
    backend = undefined;
    if (!quitting) {
      console.log(`[desktop] terminal backend exited (${code ?? "null"})`);
      quitting = true;
      app.quit();
    }
  });
  return true;
}

function probeAdmin() {
  return new Promise((resolve) => {
    const request = http.get(`${ADMIN_URL}/api/state`, (response) => {
      response.resume();
      resolve(response.statusCode >= 200 && response.statusCode < 400);
    });
    request.setTimeout(250, () => {
      request.destroy();
      resolve(false);
    });
    request.on("error", () => resolve(false));
  });
}

async function chooseStartupMode() {
  console.log("[desktop] showing startup mode chooser");
  startupWindow = new BrowserWindow({
    width: 520,
    height: 250,
    resizable: false,
    maximizable: false,
    minimizable: false,
    title: "Start MobileKonekt",
    alwaysOnTop: true,
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  await startupWindow.loadURL(
    `data:text/html;charset=utf-8,${encodeURIComponent(`
      <html><body style="font:16px sans-serif;padding:24px;background:#111827;color:#f9fafb">
        <h2>Start MobileKonekt</h2>
        <p>Choose how to run the host application.</p>
        <button onclick="location.href='mobilekonekt:electron'" style="padding:10px;margin-right:8px">Open Electron admin panel</button>
        <button onclick="location.href='mobilekonekt:terminal'" style="padding:10px">Run in terminal</button>
      </body></html>
    `)}`,
  );
  return new Promise((resolve) => {
    const select = (event, url) => {
      if (!url.startsWith("mobilekonekt:")) return;
      event.preventDefault();
      const mode = url.endsWith("terminal") ? "terminal" : "electron";
      console.log(`[desktop] startup mode selected: ${mode}`);
      if (mode === "terminal") terminalMode = true;
      startupWindow.removeAllListeners("closed");
      startupWindow.close();
      startupWindow = undefined;
      resolve(mode);
    };
    startupWindow.webContents.on("will-navigate", select);
    startupWindow.on("closed", () => {
      if (startupWindow) {
        startupWindow = undefined;
        resolve("electron");
      }
    });
    startupWindow.show();
    startupWindow.focus();
  });
}

function startFrontend() {
  if (!isDevelopment) return;
  frontend = spawn(npmCommand, ["run", "dev:web"], {
    cwd: path.join(__dirname, ".."),
    env: process.env,
    stdio: "inherit",
    windowsHide: true,
  });
  frontend.once("error", (error) => {
    dialog.showErrorBox("MobileKonekt frontend failed", error.message);
    app.quit();
  });
  frontend.once("exit", (code, signal) => {
    frontend = undefined;
    if (!quitting && (code || signal)) {
      dialog.showErrorBox(
        "MobileKonekt frontend stopped",
        `The Vite development server exited (${code ?? signal}).`,
      );
      app.quit();
    }
  });
}

async function waitForFrontend() {
  if (!isDevelopment) return;
  const startedAt = Date.now();
  const deadline = startedAt + 15000;
  while (Date.now() < deadline) {
    const ready = await new Promise((resolve) => {
      const request = http.get(DEV_FRONTEND_URL, (response) => {
        response.resume();
        resolve(response.statusCode >= 200 && response.statusCode < 400);
      });
      request.setTimeout(250, () => {
        request.destroy();
        resolve(false);
      });
      request.on("error", () => resolve(false));
    });
    if (ready) {
      console.log(`[desktop] Vite frontend ready after ${Date.now() - startedAt}ms`);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("The Vite development server did not start on port 5173.");
}

function startBackend() {
  const { command, args } = backendCommand();
  if (!isDevelopment && !existsSync(command)) {
    throw new Error(`Bundled backend not found: ${command}`);
  }
  backend = spawn(command, args, {
    cwd: isDevelopment ? path.join(__dirname, "..") : process.resourcesPath,
    env: {
      ...process.env,
      ...(isDevelopment ? { MOBILEKONEKT_PHONE_HTTP_PORT: "5173" } : {}),
    },
    stdio: "inherit",
    windowsHide: true,
  });
  backend.once("exit", (code, signal) => {
    console.log(`[desktop] backend exited (${code ?? "null"}${signal ? `, ${signal}` : ""})`);
    if (code && !quitting) {
      dialog.showErrorBox(
        "MobileKonekt backend stopped",
        `The backend exited with code ${code}. Check the terminal output for details.`,
      );
    }

    backend = undefined;
  });
  backend.once("error", (error) => {
    dialog.showErrorBox("MobileKonekt backend failed", error.message);
    app.quit();
  });
}

async function waitForAdmin() {
  const startedAt = Date.now();
  const deadline = startedAt + 15000;
  while (Date.now() < deadline) {
    const ready = await new Promise((resolve) => {
      const request = http.get(ADMIN_URL, (response) => {
        response.resume();
        resolve(response.statusCode >= 200 && response.statusCode < 400);
      });
      request.setTimeout(200, () => {
        request.destroy();
        resolve(false);
      });
      request.on("error", () => resolve(false));
    });
    if (ready) {
      console.log(`[desktop] admin server ready after ${Date.now() - startedAt}ms`);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("The local admin server did not start on port 8090.");
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    show: true,
    width: 1200,
    height: 820,
    minWidth: 900,
    minHeight: 620,
    title: "MobileKonekt",
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.once("ready-to-show", () => {
    console.log("[desktop] admin window ready; showing window");
    mainWindow.show();
    mainWindow.focus();
  });
  mainWindow.webContents.on("did-fail-load", (_event, code, description) => {
    console.error(
      `[desktop] admin panel failed to load (${code}): ${description}`,
    );
  });
  console.log(`[desktop] waiting for admin server at ${ADMIN_URL}`);
  await waitForAdmin();
  console.log(`[desktop] loading admin panel at ${ADMIN_URL}`);
  await mainWindow.loadURL(ADMIN_URL);
  console.log("[desktop] admin panel loaded");
  mainWindow.show();
  mainWindow.focus();
}

app.whenReady().then(async () => {
  try {
    console.log("[desktop] Electron is ready");
    const mode = await chooseStartupMode();
    if (mode === "terminal") {
      if (!openBackendInTerminal()) {
        throw new Error(
          "No supported terminal emulator was found. Install xdg-terminal-exec, x-terminal-emulator, GNOME Terminal, Konsole, xfce4-terminal, or xterm.",
        );
      }
      starting = false;
      return;
    }
    startFrontend();
    await waitForFrontend();
    if (await probeAdmin()) {
      console.log("[desktop] existing backend detected; reusing it");
    } else {
      startBackend();
    }
    // Create the native window before waiting for Python. This gives users
    // immediate visual feedback even if backend startup is slow or fails.
    await createWindow();
    starting = false;
    console.log("[desktop] desktop window created");
  } catch (error) {
    console.error("[desktop] startup failed", error);
    dialog.showErrorBox("MobileKonekt could not start", error.message);
    app.quit();
  }
});

app.on("window-all-closed", () => {
  if (!starting && !terminalMode) app.quit();
});
app.on("before-quit", (event) => {
  if (terminalMode && !quitting) {
    event.preventDefault();
    return;
  }
  mainWindow = null;
  if (backend && !backend.killed && !quitting) {
    event.preventDefault();
    quitting = true;
    // SIGTERM is handled by the backend and releases its listening sockets
    // immediately, avoiding a stale server when switching startup modes.
    const child = backend;
    child.once("exit", () => app.exit(0));
    backend.kill("SIGTERM");
    backend = undefined;
    setTimeout(() => app.exit(0), 2000).unref();
  }
  if (frontend && !frontend.killed) {
    frontend.kill("SIGTERM");
  }
});
