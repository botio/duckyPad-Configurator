# duckyPad Configurator 5.0.0 — Sidecar JSON-RPC Contract (v1)

Architecture: **Electron shell (web UI) + headless Python sidecar (all device/core logic).**
The Python core (PyHID, dsvm compiler, herdr, profile FS, update checks) is packaged as a
PyInstaller onedir app and spawned by the Electron main process. The Electron renderer is the
D3 UI (see `design/demos/direction-3-teenage-eng.html`) driven exclusively through this RPC.

## 1. Transport

- The sidecar speaks **newline-delimited JSON-RPC 2.0** (NDJSON) over **stdin (requests) / stdout (responses)**.
- One JSON object per line. No other bytes on stdout. **All logs go to stderr only.**
- Request: `{"jsonrpc":"2.0","id":<int>,"method":"<name>","params":{...}}`
- Response: `{"jsonrpc":"2.0","id":<int>,"result":{...}}` on success, or `{"jsonrpc":"2.0","id":<int>,"error":{"code":<int>,"message":"<text>","data":{...}}}` on failure.
- Push event (sidecar → main, only for async notifications, e.g. after a flash step):
  `{"jsonrpc":"2.0","method":"event/<name>","params":{...}}` — defined events in §7.
- Sidecar exit = fatal; Electron main must restart it (max 3 fast restarts, then surface an error screen).
- First request must be `hello`; main waits for it (timeout 30s dev / 60s packaged) before showing the window.

## 2. Conventions

- All paths are absolute strings. Colors are `[r,g,b]` integer arrays or `null`.
- `model` is `"dp20"` (duckyPad 2020, 15 physical keys) or `"dp24"` (duckyPad Pro, 20 keys).
- Key indices are the **canonical dp24 slots 0..MAX_KEY_COUNT-1** (shared.py: MECH 0-19, RE 20-25,
  spare GPIO 26-35, expansion 36-67). For dp20 devices the sidecar transparently applies
  `dp20_to_dp24_lookup_0idx` (keys exist only at slots {0,1,2,4,5,6,8,9,10,12,13,14,16,17,18}).
- `script` strings are UTF-8 duckyScript, no special escaping beyond JSON.
- Error codes: `-32000` no session (not connected), `-32001` device error (HID/drive),
  `-32002` user error (bad name, validation), `-32003` compile error (data carries `line`),
  `-32004` I/O or permission error, `-32005` network error. JSON-RPC standard codes for protocol faults.
- Every result object includes a `"ts"` millisecond timestamp.

## 3. Methods

### hello
`params: {}` → `{"app_version":"5.0.0","sidecar_version":"5.0.0","platform":"linux|darwin|win32","python":"3.12.x","max_profile":64,"max_keys":68}`

### device/scan
`params: {}` →
```json
{
  "devices": [
    {"id":"<serial>","model":"dp20|dp24","serial":"...","fw_version":"x.y.z",
     "fw_status":"ok|too_low|too_high|unknown","fw_supported":"a.b.c-d.e.f",
     "hid_path":"/dev/...","drive":{"label":"DP1_1234","mountpoint":"/media/.../DP1_1234"} | null}
  ],
  "hint": null | "permissions" | "sudo" | "not_found"
}
```
`hint="permissions"` = macOS IOKit issue; `"sudo"` = Linux device node unreadable;
`not_found` = no duckyPad. `devices` may be empty with `hint` set.

### device/connect
`params: {"id":"<serial>"}` — soft-reset the duckyPad into USB MSC mode, wait for the drive
to mount, build the profile list. → `session/state` result (below).
Errors: `-32001` with data `{"stage":"reset"|"mount"|"read"}`.

### device/connect_folder
`params: {"path":"<abs dir>","model":"dp20|dp24"}` — local-folder connection (backup restore /
manual). → same result.

### device/disconnect
`params: {}` → `{"ok":true}`. Closes session; subsequent session methods return `-32000`.

### device/reset
`params: {"reboot_to_msc":bool}` → `{"ok":true}`. HID SW reset (reboot to MSC mode if asked).

### session/state
`params: {}` →
```json
{
  "connected": true,
  "source": "device" | "folder",
  "model": "dp20|dp24",
  "serial": "..." , "fw_version": "...", "fw_status": "...",
  "drive": {"label":"...","mountpoint":"..."} | null,
  "root_path": "/abs/path/on/device",
  "user_header": ["line1", "..."],
  "stdlib_available": false,
  "profiles": [
    {"name":"P1","key_count":3,"bg_color":[244,241,233],"landscape":false,
     "dim_unused":true,"upper_re_halfstep":false,"lower_re_halfstep":false}
  ],
  "selected_profile": null,
  "update": {"app":0,"app_latest":null,"firmware":0,"firmware_latest":null}
}
```
When not connected: `{"connected":false}`.

### profiles/get
`params: {"name":"P1"}` →
```json
{"name":"P1","bg_color":[244,241,233],"dim_unused":true,"is_landscape":false,
 "upper_re_halfstep":false,"lower_re_halfstep":false,
 "keylist":[
   {"index":0,"name":"Key 1","name_line2":"","script":"press 'a'","script_on_release":"",
    "color":null,"allow_abort":false,"dont_repeat":false,"repeat_ms":null} | null
 ]}
```
`keylist` is the full canonical array (length = MAX_KEY_COUNT); `null` = unassigned key.

### profiles/update
`params: {"name":"P1","patch":{...}}` — partial patch of profile fields (bg_color, dim_unused,
is_landscape, halfsteps) and/or `{"patch":{"keylist":[<full array>]}}`. In-place, not yet saved.
→ session/state result.

### profiles/create
`params: {"name":"New"}` → session/state. Name rules: ≤16 chars, unique, no FS-illegal chars
(via existing `clean_input` + `MAX_PROFILE_NAME_LEN`).

### profiles/rename / profiles/duplicate / profiles/delete / profiles/move
`params: {"name":"...","new_name":"..."} / {"name":"..."} / {"name":"..."} / {"name":"...","direction":"up|down"}`
→ session/state.

### profiles/select
`params: {"name":"..." | null}` → session/state. Sets `selected_profile` (drives the UI OLED).

### profiles/save
`params: {"name":"P1" | null,"to":"device" | "backup"}` — write profile(s) (selected or all) to
the device drive (or the configured backup dir) using the existing `save_everything` path.
→ `{"ok":true,"saved":["P1"], "path":"..."}`.

### profiles/export
`params: {"names":["P1","P2"],"dir":"<abs dir>"}` — writes `duckyPad_Profile.zip`
(compatible with the duckyPad SD layout) into `dir`. → `{"ok":true,"path":"<abs zip path>"}`.

### profiles/import
`params: {"path":"<abs zip>","model":"dp20|dp24"}` — import into current root folder.
→ session/state.

### headers/get
`params: {}` → `{"user_header":["..."],"stdlib_lines":[...] | null}`

### headers/set
`params: {"user_header":["..."]}` — updates in-memory session state (persisted on `profiles/save`).
→ session/state.

### headers/fetch_stdlib
`params: {}` → `{"ok":true|false,"stdlib_lines":[...]}` (downloads stdlib like the Tk app).

### script/check
`params: {"script":"...","on_release":0|1}` — compiles via dsvm exactly like the Tk
`check_syntax` (uses current session's model, user header, stdlib).
→ `{"ok":true,"dsb":"<base64>"}` or error `-32003` with `data:{"line":<int>,"message":"<text>"}`.

### herdr/status
`params: {}` → herdr status dict (env probe, plugin installed?, config, dfu verified) —
serialized from `herdr.py::herdr_status()` / `show_diagnostics()`:
```json
{"env":{"os":"...","arch":"...","dfu_tool":true,"dfu_tool_path":"...","can_install_plugin":true},
 "plugin":{"installed":false,"version":null,"service_ok":null},
 "config":{"led":"...","key":"..."},
 "dfu":{"verified":null}}
```

### herdr/install
`params: {}` → `{"ok":true,"log":"<multi-line>"}`. Installs/updates the herdr plugin
(subprocess, non-interactive; if it would block, return `-32004` with data `{"needs":"<what>"}`).

### herdr/uninstall
`params: {}` → `{"ok":true,"log":"..."}`

### herdr/flash
`params: {"image":"herdr"|"stock"}` — flash the duckyPad DFU image for herdr (or back to stock),
non-interactive: enter DFU if needed (device must be connected or in DFU), run the flash command,
report progress via `event/herdr/flash` (params `{"phase":"enter|write|verify|done","detail":"..."}`),
then resolve. Errors: `-32001`.

### update/check
`params: {}` → `{"app":0|1|2,"app_latest":"x.y.z"|null,"firmware":0|1|2,"firmware_latest":"x.y.z"|null}`
(compares against the release repo configured in §6).

## 4. Sidecar lifecycle & binary location

- Packaged: `<resources>/duckypad-core/duckypad_core` (Linux/macOS) or
  `duckypad_core.exe` (Windows). Electron main spawns it with empty env additions
  (inherits `DISPLAY` etc.) and cwd = its own directory.
- Dev mode (`electron .` / `--dev`): sidecar = `<repo>/src/.venv/bin/python <repo>/src/core/sidecar.py`
  (Windows: `python.exe`), selected when env `DUCKYPAD_CORE_DEV=1`.
- Sidecar must be import-safe headless: **no tkinter import anywhere in the import chain**
  (`src/core/service.py` must not import `duckypad_config`).

## 5. Renderer integration (Electron)

- `preload.js` exposes `window.core`:
  - `call(method, params) → Promise<result>` (rejects with `{code,message,data}`)
  - `on(eventName, cb) → unsubscribe` for `event/*` pushes
  - `pickExportDir() → Promise<string|null>`, `pickImportFile() → Promise<string|null>`
    (native dialogs), `openPath(path)`, `openExternal(url)`
- UI states (no fake data — production shows only real sidecar data):
  1. **Boot**: splash until `hello`.
  2. **No device**: dashboard shows "Connect" (sidecar `device/scan` → pick device) and
     "Open backup folder" (native dir picker → `device/connect_folder` + model question).
  3. **Connected**: live D3 layout (key grid, OLED, switches, profiles rail, script editor,
     herdr panel, updates panel, resources bar). Empty key = blank cap.
- Script editor: textarea; debounced `script/check` (400ms) after input; show
  `Code seems OK…` / red error line indicator.
- Key grid: dp20 → 3 cols × 5 rows (slots {0,1,2,4,5,6,8,9,10,12,13,14,16,17,18});
  dp24 → 4 cols × 5 rows. Keycap shows up to 2 name lines; click = `profiles/get` + select;
  OLED shows `P<n>` + name; −/+ = `profiles/select(next|prev)` with wrap.

## 6. Config / release identity

- App id: `com.dekunukem.duckypad-configurator`. App name: `duckyPad Configurator`. Version: `5.0.0`.
- The update check targets the **botio/duckyPad-Configurator** releases (this fork), not the
  upstream duckyPad org repo. Firmware check URLs stay as today.
- Windows: `NSIS`; macOS: DMG (arm64 + x64, ad-hoc signed when no cert, notarization via CI
  secrets when present); Linux: **AppImage (x64)** — must run on Fedora/Arch/Ubuntu
  (sidecar bundles libhidapi; AppImage runtime provides the rest).

## 7. Events (sidecar → renderer)

- `event/session/lost` `{"reason":"unmount|hid_gone"}` — device unplugged mid-session.
- `event/herdr/flash` `{"phase":"enter|write|verify|done|error","detail":"..."}`
- `event/log` `{"level":"info|warn|error","message":"..."}` — sidecar stderr, line-buffered
  (main forwards; renderer shows in an optional debug strip).
