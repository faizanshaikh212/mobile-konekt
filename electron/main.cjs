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
