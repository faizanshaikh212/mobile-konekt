const { app, BrowserWindow, dialog } = require("electron");
const { spawn, spawnSync } = require("node:child_process");
const { existsSync } = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const ADMIN_URL = "http://127.0.0.1:8090";
const isDevelopment = process.argv.includes("--dev") || !app.isPackaged;
const externalBackend = process.argv.includes("--external-backend");
let backend;
let mainWindow;

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
  const cwd = isDevelopment ? path.join(__dirname, "..") : process.resourcesPath;
  const commandLine = [backend.command, ...backend.args]
    .map((part) => `'${String(part).replaceAll("'", "'\\''")}'`)
    .join(" ");
  const shellArgs = ["-c", `exec ${commandLine}`];
  const terminals = [
    ["x-terminal-emulator", ["-e", "sh", ...shellArgs]],
    ["gnome-terminal", ["--", "sh", ...shellArgs]],
    ["konsole", ["-e", "sh", ...shellArgs]],
    ["xfce4-terminal", ["--command", `sh ${shellArgs.map((arg) => `'${arg.replaceAll("'", "'\\''")}'`).join(" ")}`]],
    ["kitty", ["sh", ...shellArgs]],
    ["alacritty", ["-e", "sh", ...shellArgs]],
  ];
  return { cwd, terminals };
}

function openBackendInTerminal() {
  const { cwd, terminals } = terminalCommand();
  for (const [command, args] of terminals) {
    const installed = spawnSync("which", [command], { stdio: "ignore" });
    if (installed.status !== 0) continue;
    try {
      const terminal = spawn(command, args, {
        cwd,
        detached: true,
        stdio: "ignore",
        windowsHide: true,
      });
      terminal.unref();
      return true;
    } catch {}
  }
  return false;
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
  backend.once("error", (error) => {
    dialog.showErrorBox("MobileKonekt backend failed", error.message);
    app.quit();
  });
}

async function waitForAdmin() {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const ready = await new Promise((resolve) => {
      const request = http.get(ADMIN_URL, (response) => {
        response.resume();
        resolve(response.statusCode >= 200 && response.statusCode < 400);
      });
      request.setTimeout(500, () => {
        request.destroy();
        resolve(false);
      });
      request.on("error", () => resolve(false));
    });
    if (ready) return;
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
          "No supported terminal emulator was found. Install x-terminal-emulator, gnome-terminal, Konsole, xfce4-terminal, kitty, or Alacritty.",
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
app.on("before-quit", () => {
  mainWindow = null;
  if (backend && !backend.killed) {
    backend.kill("SIGINT");
    backend = undefined;
  }
});
