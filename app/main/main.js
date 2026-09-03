const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const os = require('node:os');

const APP_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(APP_ROOT, '..');
const DEV_MODE = process.env.DUCKYPAD_CORE_DEV === '1' || !app.isPackaged;
let windowRef = null;
let sidecar = null;
let lineBuffer = '';
let nextRequestId = 1;
const pending = new Map();
const restartTimes = [];
let quitting = false;
let hidServer = null;
let hidServerPath = null;
const hidHandles = new Map();
let nextHidHandle = 1;

function rendererEvent(method, params) {
  if (!windowRef || windowRef.isDestroyed()) return;
  windowRef.webContents.send('core:event', { method, params });
}

function sidecarCommand() {
  if (DEV_MODE) {
    const python = process.platform === 'win32'
      ? path.join(REPO_ROOT, 'src', '.venv', 'Scripts', 'python.exe')
      : path.join(REPO_ROOT, 'src', '.venv', 'bin', 'python');
    return { command: python, args: [path.join(REPO_ROOT, 'src', 'core', 'sidecar.py')], cwd: path.join(REPO_ROOT, 'src') };
  }
  const executable = process.platform === 'win32' ? 'duckypad_core.exe' : 'duckypad_core';
  const resourceDir = path.join(process.resourcesPath, 'duckypad-core');
  return { command: path.join(resourceDir, executable), args: [], cwd: resourceDir };
}

function failPending(error) {
  for (const { reject, timer } of pending.values()) {
    clearTimeout(timer);
    reject(error);
  }
  pending.clear();
}

function handleMessage(line) {
  let payload;
  try { payload = JSON.parse(line); } catch {
    rendererEvent('event/log', { level: 'warn', message: `Ignoring invalid sidecar output: ${line}` });
    return;
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'id')) {
    const request = pending.get(payload.id);
    if (!request) return;
    pending.delete(payload.id);
    clearTimeout(request.timer);
    if (payload.error) request.reject(payload.error);
    else request.resolve(payload.result);
    return;
  }
  if (payload.method && payload.method.startsWith('event/')) rendererEvent(payload.method, payload.params || {});
}

// macOS routes the sidecar's raw HID calls through the .app main process over a
// Unix socket. The Input Monitoring TCC grant is keyed to the .app's main
// executable; the sidecar is a different ad-hoc binary and its own
// IOHIDDeviceOpen is denied. Performing the open (and I/O) here succeeds.
function startHidProxy() {
  if (process.platform !== 'darwin') return null;
  if (hidServer) return hidServerPath;
  const sockPath = path.join(os.tmpdir(), `duckypad-hid-${process.pid}.sock`);
  try { fs.unlinkSync(sockPath); } catch (err) { /* stale file, ignore */ }
  const server = net.createServer((socket) => {
    let buffer = '';
    socket.on('data', (chunk) => {
      buffer += chunk.toString('utf8');
      let newline;
      while ((newline = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, newline);
        buffer = buffer.slice(newline + 1);
        if (line) handleHidRequest(socket, line).catch(() => {});
      }
    });
    socket.on('close', () => {
      for (const hid of hidHandles.values()) hid.close().catch(() => {});
      hidHandles.clear();
    });
    socket.on('error', () => {});
  });
  hidServer = server;
  hidServerPath = sockPath;
  server.on('error', (err) => {
    console.error(`hid proxy: ${err && err.message || err}`);
    hidServer = null;
    hidServerPath = null;
  });
  server.listen(sockPath);
  return sockPath;
}

function stopHidProxy() {
  if (hidServer) {
    try { hidServer.close(); } catch (err) { /* ignore */ }
    hidServer = null;
  }
  for (const hid of hidHandles.values()) hid.close().catch(() => {});
  hidHandles.clear();
  if (hidServerPath) {
    try { fs.unlinkSync(hidServerPath); } catch (err) { /* ignore */ }
    hidServerPath = null;
  }
}

async function handleHidRequest(socket, line) {
  let msg;
  try { msg = JSON.parse(line); } catch (err) {
    socket.write(JSON.stringify({ error: 'bad request' }) + '\n');
    return;
  }
  const respond = (obj) => { try { socket.write(JSON.stringify(obj) + '\n'); } catch (err) { /* gone */ } };
  let nodeHid;
  try { nodeHid = require('node-hid'); } catch (err) {
    respond({ error: `node-hid unavailable: ${err && err.message || err}` });
    return;
  }
  try {
    if (msg.op === 'enumerate') {
      const devices = await nodeHid.devicesAsync();
      respond({ devices: devices.map((d) => ({
        vendor_id: d.vendorId,
        product_id: d.productId,
        usage: d.usage || 0,
        usage_page: d.usagePage || 0,
        path: Buffer.from(d.path || '', 'utf8').toString('base64'),
        serial_number: d.serialNumber || null,
        manufacturer: d.manufacturer || null,
        product: d.product || null,
      })) });
    } else if (msg.op === 'open') {
      const target = Buffer.from(msg.path || '', 'base64').toString('utf8');
      const hid = await nodeHid.HIDAsync.open(target, { nonExclusive: true });
      const handle = nextHidHandle++;
      hidHandles.set(handle, hid);
      respond({ handle });
    } else if (msg.op === 'write') {
      const hid = hidHandles.get(msg.handle);
      if (!hid) throw new Error(`unknown HID handle ${msg.handle}`);
      const bytes = await hid.write(Buffer.from(msg.data || '', 'base64'));
      respond({ result: bytes });
    } else if (msg.op === 'read') {
      const hid = hidHandles.get(msg.handle);
      if (!hid) throw new Error(`unknown HID handle ${msg.handle}`);
      const timeout = (typeof msg.timeout === 'number' && msg.timeout > 0) ? msg.timeout : 20000;
      const buf = await hid.read(timeout);
      respond({ data: buf ? buf.toString('base64') : null });
    } else if (msg.op === 'close') {
      const hid = hidHandles.get(msg.handle);
      if (hid) {
        await hid.close().catch(() => {});
        hidHandles.delete(msg.handle);
      }
      respond({ ok: true });
    } else {
      respond({ error: `unknown op ${msg.op}` });
    }
  } catch (err) {
    respond({ error: String(err && err.message || err) });
  }
}

function startSidecar() {
  const { command, args, cwd } = sidecarCommand();
  if (!fs.existsSync(command)) throw new Error(`Python core is missing: ${command}`);
  const hidSock = startHidProxy();
  const env = { ...process.env };
  if (hidSock) env.DUCKYPAD_HID_SOCK = hidSock;
  sidecar = spawn(command, args, { cwd, stdio: ['pipe', 'pipe', 'pipe'], env, windowsHide: true });
  lineBuffer = '';
  sidecar.stdout.setEncoding('utf8');
  sidecar.stdout.on('data', (chunk) => {
    lineBuffer += chunk;
    let newline;
    while ((newline = lineBuffer.indexOf('\n')) !== -1) {
      const line = lineBuffer.slice(0, newline).trim();
      lineBuffer = lineBuffer.slice(newline + 1);
      if (line) handleMessage(line);
    }
  });
  sidecar.stderr.setEncoding('utf8');
  sidecar.stderr.on('data', (chunk) => {
    for (const message of chunk.split(/\r?\n/)) if (message) rendererEvent('event/log', { level: 'info', message });
  });
  sidecar.on('error', (error) => handleSidecarExit(error.message));
  sidecar.on('exit', (code, signal) => {
    if (!quitting) handleSidecarExit(`sidecar exited (${code ?? signal ?? 'unknown'})`);
  });
}

function handleSidecarExit(reason) {
  failPending({ code: -32006, message: reason, data: {} });
  sidecar = null;
  const now = Date.now();
  restartTimes.push(now);
  while (restartTimes[0] < now - 10000) restartTimes.shift();
  if (restartTimes.length >= 3) {
    rendererEvent('event/sidecar-dead', { reason });
    return;
  }
  setTimeout(async () => {
    try {
      startSidecar();
      await request('hello', {}, 30000);
      rendererEvent('event/sidecar-restored', {});
    } catch (error) {
      handleSidecarExit(error.message || 'sidecar restart failed');
    }
  }, 500);
}

function request(method, params = {}, timeout = null) {
  if (!sidecar || !sidecar.stdin.writable) return Promise.reject({ code: -32006, message: 'Python core is not running', data: {} });
  const id = nextRequestId++;
  const ms = timeout || ((method === 'device/connect' || method === 'herdr/flash') ? 60000 : 30000);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject({ code: -32006, message: `${method} timed out`, data: {} });
    }, ms);
    pending.set(id, { resolve, reject, timer });
    sidecar.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', id, method, params })}\n`);
  });
}

function createMenu() {
  const edit = [
    { role: 'undo' }, { role: 'redo' }, { type: 'separator' },
    { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(process.platform === 'darwin' ? [{ label: app.name, submenu: [{ role: 'about' }, { type: 'separator' }, { role: 'quit' }] }] : []),
    { label: 'Edit', submenu: edit },
    { label: 'View', submenu: [{ role: 'reload' }, { role: 'toggleDevTools' }] },
  ]));
}

async function boot() {
  createMenu();
  windowRef = new BrowserWindow({
    width: 1450,
    height: 850,
    minWidth: 1100,
    minHeight: 700,
    resizable: false,
    show: false,
    title: 'duckyPad Configurator',
    backgroundColor: '#E8E4DA',
    icon: path.join(APP_ROOT, 'resources', 'icon_512.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  try {
    startSidecar();
    await request('hello', {}, app.isPackaged ? 60000 : 30000);
    await windowRef.loadFile(path.join(APP_ROOT, 'renderer', 'index.html'));
  } catch (error) {
    await windowRef.loadFile(path.join(APP_ROOT, 'renderer', 'error.html'), { query: { message: error.message || String(error) } });
  }
  windowRef.show();
}

ipcMain.handle('core:call', (_event, { method, params }) => request(method, params || {}));
ipcMain.handle('core:pickExportDir', async () => {
  const result = await dialog.showOpenDialog(windowRef, { properties: ['openDirectory', 'createDirectory'] });
  return result.canceled ? null : result.filePaths[0];
});
ipcMain.handle('core:pickImportFile', async () => {
  const result = await dialog.showOpenDialog(windowRef, { properties: ['openFile'], filters: [{ name: 'duckyPad profile', extensions: ['zip'] }] });
  return result.canceled ? null : result.filePaths[0];
});
ipcMain.handle('core:pickFolder', async () => {
  const result = await dialog.showOpenDialog(windowRef, { properties: ['openDirectory'] });
  return result.canceled ? null : result.filePaths[0];
});
ipcMain.handle('core:openPath', (_event, target) => shell.openPath(target));
ipcMain.handle('core:openExternal', (_event, target) => {
  const url = new URL(target);
  if (!['https:', 'http:'].includes(url.protocol)) throw new Error('Only http(s) links are allowed');
  return shell.openExternal(url.toString());
});

app.whenReady().then(boot);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) boot(); });
app.on('before-quit', () => {
  quitting = true;
  stopHidProxy();
  if (!sidecar || sidecar.killed) return;
  sidecar.kill('SIGTERM');
  setTimeout(() => { if (sidecar && !sidecar.killed) sidecar.kill('SIGKILL'); }, 5000).unref();
});
