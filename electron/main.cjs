const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("node:child_process");
const { existsSync } = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const ADMIN_URL = "http://127.0.0.1:8090";
const isDevelopment = process.argv.includes("--dev") || !app.isPackaged;
const externalBackend = process.argv.includes("--external-backend");
let backend;
let mainWindow;
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

function terminalCommand() {
  const backend = backendCommand();
  backend.args = [...backend.args, "--tui"];
  const cwd = isDevelopment ? path.join(__dirname, "..") : process.resourcesPath;
  return { cwd, backend };
}

function openBackendInTerminal() {
  const { cwd, backend } = terminalCommand();

  spawn(backend.command, backend.args, {
    cwd,
    stdio: "inherit",
    windowsHide: true,
  });
  return true;
}

async function chooseStartupMode() {
  const result = await dialog.showMessageBox({
    type: "question",
    title: "Start MobileKonekt",
    message: "How would you like to run MobileKonekt?",
    detail:
      "The Electron admin panel is convenient, while terminal mode uses less memory and keeps the backend in a terminal window.",
    buttons: ["Open Electron admin panel", "Run backend in terminal"],
    defaultId: 0,
    cancelId: 0,
    noLink: true,
  });
  return result.response === 1 ? "terminal" : "electron";
}

function startBackend() {
  const { command, args } = backendCommand();
  if (!isDevelopment && !existsSync(command)) {
    throw new Error(`Bundled backend not found: ${command}`);
  }
  backend = spawn(command, args, {
    cwd: isDevelopment ? path.join(__dirname, "..") : process.resourcesPath,
    stdio: "inherit",
    windowsHide: true,
  });
  backend.once("exit", (code, signal) => {
    console.log(`[desktop] backend exited (${code ?? "null"}${signal ? `, ${signal}` : ""})`);
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
  console.log(`[desktop] loading admin panel at ${ADMIN_URL}`);
  await waitForAdmin();
  mainWindow = new BrowserWindow({
    show: false,
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
      app.quit();
      return;
    }
    if (!externalBackend) startBackend();
    await createWindow();
    console.log("[desktop] desktop window created");
  } catch (error) {
    console.error("[desktop] startup failed", error);
    dialog.showErrorBox("MobileKonekt could not start", error.message);
    app.quit();
  }
});

app.on("window-all-closed", () => app.quit());
app.on("before-quit", (event) => {
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
});
