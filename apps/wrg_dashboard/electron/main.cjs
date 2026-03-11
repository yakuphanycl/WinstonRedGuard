const { app, BrowserWindow } = require("electron");
const path = require("node:path");

function createWindow() {
  const preloadPath = path.join(__dirname, "preload.cjs");
  const isDev = Boolean(process.env.ELECTRON_START_URL);
  const distIndexPath = path.join(__dirname, "..", "dist", "index.html");
  const win = new BrowserWindow({
    width: 1360,
    height: 880,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    title: "WRG Control Center v0.1",
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  win.once("ready-to-show", () => {
    win.show();
  });

  win.webContents.on("did-finish-load", () => {
    console.log("[desktop] did-finish-load");
  });

  win.webContents.on("did-fail-load", (_event, code, description, url, isMainFrame) => {
    console.error(
      `[desktop] did-fail-load code=${code} description=${description} url=${url} mainFrame=${isMainFrame}`
    );
  });

  win.webContents.on("render-process-gone", (_event, details) => {
    console.error(`[desktop] render-process-gone reason=${details.reason} exitCode=${details.exitCode}`);
  });

  if (isDev) {
    win.loadURL(process.env.ELECTRON_START_URL);
  } else {
    console.log(`[desktop] loading production index: ${distIndexPath}`);
    console.log(`[desktop] preload path: ${preloadPath}`);
    win.loadFile(distIndexPath);
  }
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
