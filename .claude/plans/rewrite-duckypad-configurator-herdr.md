# Feature: 重寫 duckyPad Configurator 並整合 herdr

本計畫以 Wayfinder 已鎖定的決策為準，不重開架構選擇。開始實作前，必須先取得有版本與 checksum 的 Herdr-capable Pro/EVO firmware release URL；目前只驗證到本機 sibling firmware source，沒有可交付的 release 對應。

## Feature Description

以 PySide6 重寫單體 Python Configurator，保留 duckyPad Device Format 與既有 profile/ZIP/DPDS/DSB 工作流，並新增版本化 Application State。Configurator 引導安裝 `duckypad-herdr` plugin bundle；plugin startup hook 啟動無 UI 的 Bridge。Bridge 訂閱 Herdr agent 狀態、管理 capability-checked Pro/EVO Herdr Mode 的 15-slot LED frame，並將短按轉為一次、不重試的 `agent.focus`。

## User Story

身為 duckyPad 使用者，我想在 macOS Apple Silicon 或 Linux x86_64 上以原生 GUI 管理既有設定，並把支援的 Pro/EVO 實體鍵映射到 Herdr agent，讓 LED 顯示狀態且短按聚焦正確 agent，如此不必以 `sudo` 啟動或手動維護 IPC。

## Problem Statement

現有 `src/duckypad_config.py` 是 Tkinter 與 module-global state 的單檔 GUI；裝置、檔案、編譯、UI、更新檢查無清楚邊界。它沒有測試基線，Linux 連線路徑要求 `sudo`，macOS 是 one-file PyInstaller ZIP。Herdr 的 plugin 與 custom-HID Herdr Mode 需要常駐 Bridge、嚴格 capability gate、workspace-scoped mapping 與安全的同步／失連行為。

## Solution Statement

建立新的 package-first PySide6 application；以 pure domain/service layer 保留並測試 Device Format 與 DPDS compiler；以 Application State 保存 UI 與 Herdr mapping。Bridge 作為與 GUI 分離的 packaged executable，由 versioned Herdr plugin bundle 啟動。新 GUI 的日常畫面使用 Device Canvas；初次 Herdr Mode 啟用、workspace 切換和 capability recovery 使用顯式 wizard。完成硬體、遷移、release gates 後移除 Tkinter 與舊打包入口。

## Out of Scope / Non-Goals

- 不在 Configurator 內刷寫 firmware；app 僅驗證並引導到外部、已簽署的 firmware release。
- 不支援 OG duckyPad 的 Herdr Mode、實體 key event 或 LED overlay。
- 不支援 Herdr Mode 與正常 DPDS key handling 共存；模式切換明確且可回到 Profile Mode。
- 不實作 macOS Intel、Linux ARM64、Windows、in-app self-updater、rollback。
- 不由 Configurator 直接管理 macOS/X11/Wayland 視窗；焦點一律使用 Herdr `agent.focus`。

## Feature Metadata

**Feature Type**: New Capability + full GUI Refactor  
**Estimated Complexity**: High  
**Primary Systems Affected**: PySide6 GUI、Device Format、HID、Herdr Bridge/plugin、packaging/release  
**Dependencies**: Python 3.12+（在 foundation 固定）、PySide6、pytest、pytest-qt、hidapi、platformdirs、Herdr >= 0.8.2、capability-checked Pro/EVO firmware release

## Related Work

**Implements**: `.scratch/duckyPad-configurator-herdr-rewrite/map.md`  
**Architecture decisions**: 所有 resolved ticket 位於 `.scratch/duckyPad-configurator-herdr-rewrite/issues/`  
**Domain vocabulary**: `CONTEXT.md`  
**Prototype source**: branch `prototype/mapping-flow-ui` at `ae95b12`

## CONTEXT REFERENCES

### Relevant Codebase Files — must read before implementing

- `CONTEXT.md` (all lines) — Bridge、Herdr Mode、Profile Mode、Mapping、Device Format、Application State 的不可變語意。
- `.scratch/duckyPad-configurator-herdr-rewrite/issues/04-choose-herdr-integration-contract.md` (lines 11-22) — Bridge、mapping、focus、失連合約。
- `.scratch/duckyPad-configurator-herdr-rewrite/issues/05-choose-rewrite-architecture-and-release.md` (lines 11-21) — PySide6、平台與更新交付決策。
- `.scratch/duckyPad-configurator-herdr-rewrite/issues/06-define-agent-status-led-model.md` (lines 11-21) — LED precedence、palette、20 FPS frame budget。
- `.scratch/duckyPad-configurator-herdr-rewrite/issues/07-prototype-mapping-configuration-flow.md` (lines 11-19) — Device Canvas + activation wizard UX。
- `src/duck_objs.py:52-97` — legacy `config.txt` read semantics；port to parser tests before UI。
- `src/duckypad_config.py:402-438` — source-folder load、機型分支、OG key-order conversion。
- `src/duckypad_config.py:544-598` — current Pro MSC / OG HID connection flow與現有 fallback。
- `src/duckypad_config.py:886-1022` — compile-before-save invariant與 Device Format output。
- `src/duckypad_config.py:1029-1060` — backup-before-sync、eject/reset behavior。
- `src/duckypad_config.py:1919-1996` — profile ZIP import/export behavior。
- `src/hid_common.py:62-108`、`src/hid_op.py:141-154`、`src/my_compare.py:113-166` — scan、RTC、diff sync、HID file sync。
- `src/dsvm_make_bytecode.py:437-570`、`src/dsvm_preprocessor.py:632-641` — compiler seam；不要重寫 bytecode format。
- `src/check_update.py:17-66` — current app/firmware version checks；替換為 user-confirmed release flow。
- `.scratch/duckyPad-configurator-herdr-rewrite/research/02-herdr-integration-facts.md` — Herdr 0.8.2 socket/plugin identity and bootstrap evidence。
- `.scratch/duckyPad-configurator-herdr-rewrite/research/03-desktop-delivery-constraints.md` — signing, udev, PySide6 deployment facts。
- `.scratch/duckyPad-configurator-herdr-rewrite/research/08-duckypad-key-event-channel.md` — Pro/EVO custom-HID command/event constraints。

### New Files to Create

- `pyproject.toml` — project metadata, runtime/test tooling, PySide6 deployment configuration.
- `src/duckypad_configurator/__main__.py` — GUI entry point.
- `src/duckypad_configurator/domain/{device_format,application_state,mapping,status}.py` — pure models, validation, state precedence.
- `src/duckypad_configurator/services/{legacy_profiles,compiler,device_sync,app_state,plugin_install}.py` — reusable application operations.
- `src/duckypad_configurator/herdr/{client,plugin_bundle,bridge}.py` — NDJSON socket client, bundle materialization, bridge runtime.
- `src/duckypad_configurator/ui/{main_window,device_canvas,slot_inspector,herdr_wizard}.py` — PySide6 UI.
- `packaging/linux/{install-udev-rule,duckypad-configurator.rules,org.duckypad.Configurator.policy}` — least-privilege Polkit/udev installation assets.
- `packaging/macos/{entitlements.plist,sign-and-notarize.sh}` — Apple Silicon signing/notarization pipeline.
- `tests/{unit,integration,ui,fixtures}/...` — pytest, fake HID, fake Herdr NDJSON server, pytest-qt tests.
- `.github/workflows/{test,release-macos,release-linux}.yml` — CI and release gates.

### Relevant Documentation

- [Herdr plugin documentation](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/plugins.mdx) — manifest, startup hook, environment contract.
- [Herdr socket API](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/socket-api.mdx) — NDJSON, subscription + snapshot bootstrap, protocol compatibility.
- [Qt for Python deployment](https://doc.qt.io/qtforpython-6.10/deployment/deployment-pyside6-deploy.html) — `pyside6-deploy`, macOS `.app`, Linux binary output.
- [HIDAPI README](https://github.com/libusb/hidapi#about) — Linux unprivileged HID access requires a udev rule.
- [systemd udev(7)](https://www.freedesktop.org/software/systemd/man/latest/udev.html) — device rule and permission model.
- [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) — Developer ID, Hardened Runtime, timestamp, nested executables, staple.

### Patterns to Follow

- Preserve the legacy **compile-before-save** gate from `compile_all_scripts()` / `save_everything()`; no Device Format writes after a compiler failure.
- Preserve **backup-before-device-sync** from `save_click()`; failure recovery must never overwrite the sole recovery copy.
- Replace all module-global Tk state with explicit `ApplicationState` / service dependencies; do not port Tk callbacks or globals into PySide6.
- Treat every HID write and socket request as a boundary: serialise writes, preserve the agreed no-output-retry policy, and surface diagnosable connection state.

## IMPLEMENTATION PLAN

### Phase 1: Package foundation and test harness

**Tasks:**

1. **CREATE `pyproject.toml` and package layout**
   - Define Python version, PySide6, hidapi, platformdirs, pytest, pytest-qt dependencies and console entry points for GUI and Bridge.
   - Move no legacy behavior yet; establish `src/duckypad_configurator` import boundary.
   - **GOTCHA**: Bridge must be a separate executable entry point; it must not import or start Qt.
   - **VALIDATE**: `python -m compileall src/duckypad_configurator`.

2. **CREATE pytest fixtures and fakes**
   - Add fake HID transport and fake Herdr NDJSON server with controlled snapshots, events, disconnects, delayed responses and malformed messages.
   - Add pytest-qt application fixture; prohibit real HID and real socket access in unit/UI tests.
   - **VALIDATE**: `python -m pytest tests -q`.

### Phase 2: Port Device Format and migration domain

**Depends on:** Phase 1.

3. **CREATE pure Device Format parser/writer**
   - Port `config.txt`, `profile_info.txt`, user header, key text/release text and DSB file handling out of `duck_objs.py` / `duckypad_config.py` into typed models.
   - Preserve OG order conversion, profile order, key colors, flags, orientation and absent-file semantics.
   - **GOTCHA**: parser errors must be reportable; do not retain the old catch-all-and-pass behavior as the only outcome.
   - **VALIDATE**: fixture round trips against representative legacy folders and ZIPs.

4. **CREATE compiler and synchronisation adapters**
   - Wrap existing DSVM compiler and diff-sync code behind services; write Device Format only after every press/release script compiles and is below the existing size limit.
   - Create immutable timestamped backup before sync, then retain MSC eject/reset and OG HID refresh behavior for Profile Mode.
   - **VALIDATE**: fake-device sync tests prove compile failure produces no device write and sync failure leaves backup intact.

5. **CREATE Application State schema and migrator**
   - Store UI preferences and Mapping records separately through Platformdirs with `schema_version` and atomic replace.
   - On first open, snapshot legacy source data, show migration preview, then persist Application State only after user confirmation.
   - **VALIDATE**: migration, malformed-state, downgrade/reopen, and atomic-write interruption tests.

### Phase 3: PySide6 Profile Mode application

**Depends on:** Phase 2.

6. **CREATE PySide6 application shell and device selection**
   - Implement a main window, device/backup-folder chooser, reconnect diagnostics, profile list, key editor, import/export and backup view.
   - Use Device Format services, not direct filesystem/HID calls in widgets.
   - **GOTCHA**: preserve manual local-folder fallback but remove all `sudo`-run application prompts.
   - **VALIDATE**: pytest-qt flow opens legacy backup, selects profile/key, edits in memory, and reports device permission failure without crashing.

7. **CREATE Device Canvas and Slot Inspector**
   - Implement the selected A information architecture: workspace agent list, 15-slot visual pad, selected-slot inspector, unmapped-agent visibility and invalid-mapping warning.
   - The user may override only agent-status RGB; hide edits for global effects, safety colors and precedence.
   - **VALIDATE**: pytest-qt tests assert a moved pane invalidates its slot and no UI action silently remaps it.

### Phase 4: Herdr plugin bundle and Bridge

**Depends on:** Phases 1 and 5. Requires a real signed firmware release URL before release work.

8. **CREATE versioned plugin bundle and guided installer**
   - Materialize a `duckypad-herdr` manifest plus Bridge executable reference in a user-owned location.
   - GUI "Connect Herdr" action detects Herdr >= 0.8.2, invokes documented install/link/enable flow only after confirmation, and reports exact remediation when Herdr/version/plugin setup is unavailable.
   - **GOTCHA**: do not write unmanaged plugin state or assume a Unix socket path; use Herdr-provided executable/context contract.
   - **VALIDATE**: fake CLI integration tests cover install, update, incompatible version and idempotent re-run.

9. **CREATE Herdr NDJSON client and Bridge state machine**
   - Subscribe, snapshot, then apply buffered `pane.agent_status_changed` events; map by `{workspace_id, pane_id}` only.
   - On `pane.move`, invalidate mapping. On socket/HID loss, remove trusted runtime state; on reconnect preflight capability, enable mode, resubscribe/reconcile and issue one full RGB frame.
   - For mapped short press, serialise one `agent.focus`, wait for response/focus event, render temporary feedback; no persisted queue or automatic retry.
   - **VALIDATE**: fake-server tests cover snapshot races, move, reconnect, focus success/failure and unknown fields.

10. **CREATE Pro/EVO custom-HID capability gate and LED renderer**
    - Verify the externally released firmware's documented version/checksum/capability before enabling Herdr Mode.
    - Implement command 34 full RGB output, command 36 mode on/off, and `[0x04,0xF0,0x00,slot]` input only for slots 1–15.
    - Resolve LED Presentation precedence and send deduplicated, serialised frames at most 20 FPS. Do not claim acknowledgement, release/hold events, DPDS coexistence, OG compatibility or delivery guarantees.
    - **VALIDATE**: byte-level fake-HID tests for commands/events, frame coalescing, precedence, no-output-retry, and capability failure.

### Phase 5: Herdr Mode activation UX

**Depends on:** Phase 4.

11. **CREATE activation wizard from prototype C**
    - Step 1: choose a capability-verified Pro/EVO device; Step 2: choose one Herdr workspace; Step 3: explicitly accept replacement of Profile Mode key behavior.
    - Unsupported device, unavailable firmware capability, missing Herdr, and disconnected states are terminal diagnostics, not partially enabled modes.
    - Stopping Herdr Mode sends best-effort mode-off, clears Bridge display ownership and returns to Profile Mode.
    - **VALIDATE**: pytest-qt wizard tests and fake-HID assertions for accept/cancel/capability-loss paths.

### Phase 6: Packaging, permissions, updates and release gates

**Depends on:** Phases 1–5.

12. **CREATE Apple Silicon macOS pipeline**
    - Produce an ARM64 PySide6 `.app` / DMG. Sign every nested executable with Developer ID + Hardened Runtime + timestamp; notarize, staple and retain notarization logs.
    - Build and smoke test on Apple Silicon with real HID; no Intel artifact.
    - **VALIDATE**: CI signing/notarization gate plus clean-machine launch/HID checklist.

13. **CREATE Linux x86_64 AppImage and Polkit udev flow**
    - Package desktop entry and AppImage. Install/remove only the narrowly matched duckyPad udev rule through a one-time Polkit helper; normal GUI/Bridge processes never use `sudo`.
    - Verify install, reconnect, rule removal and permission-denied diagnostics on clean supported Linux environments.
    - **VALIDATE**: packaging smoke plus physical HID checklist.

14. **CREATE user-confirmed update flow**
    - Fetch and verify signed release metadata, display installed/available version and changelog, then open the official download only after confirmation.
    - Do not self-download, replace the current app, or implement rollback.
    - **VALIDATE**: metadata signature/version tests and UI confirmation/cancel tests.

### Phase 7: Cutover and documentation

**Depends on:** Phases 2–6.

15. **REMOVE Tkinter/legacy entry points after parity**
    - Remove `src/duckypad_config.py`, old Tk-only helpers and PyInstaller scripts only after their behavior has a replacement and migration fixtures pass.
    - Update `README.md` with Apple Silicon DMG, Linux AppImage + udev permission flow, Profile Mode / Herdr Mode distinction, external firmware prerequisite and fallback behavior.
    - **GOTCHA**: no hidden compatibility shim; Device Format is the supported compatibility surface.
    - **VALIDATE**: full test suite, package builds, Profile Mode real-device smoke, Herdr Mode real Pro/EVO smoke, and migration from archived legacy fixtures.

## TESTING STRATEGY

### Unit tests

- Device Format parsing/writing, profile order, import/export, compiler gate, Application State migration, Mapping validation and LED precedence.
- Herdr protocol framing, unknown fields, snapshot/event race, focus response, invalidation and reconnect.
- Custom-HID packet shape, command 34/36, 15-slot bounds, frame deduplication and 20 FPS limiter.

### Integration tests

- Fake HID + fake Herdr server drive Bridge from snapshot through status update, press, focus outcome, disconnect and reconnect.
- PySide6 flow: legacy folder → migration preview → Profile Mode edit/save → activation wizard → mapping canvas.
- Plugin installer: no Herdr, old Herdr, update existing bundle, and idempotent rerun.

### Release smoke tests

- Apple Silicon: notarized DMG on a non-development machine; app starts, sees HID, writes Profile Mode config and checks Bridge diagnostics.
- Linux x86_64: AppImage, one-time Polkit udev install, unprivileged HID open/reconnect, udev removal, and permission-denied recovery.
- Pro/EVO: exact signed firmware release passes preflight; Herdr Mode press / LED / focus works. OG and unknown firmware remain disabled.

## VALIDATION COMMANDS

- `python -m compileall src/duckypad_configurator`
- `python -m pytest tests/unit -q`
- `python -m pytest tests/integration -q`
- `python -m pytest tests/ui -q`
- `python -m pytest tests -q`
- `pyside6-deploy src/duckypad_configurator/__main__.py` on each target platform build runner.
- macOS and Linux release smoke checklists described above; these are required real-device gates, not substitutable by unit tests.

## ACCEPTANCE CRITERIA

- [ ] Legacy Device Format profile folders and ZIPs open, edit, export and write back without format loss; compiler failure writes nothing to device.
- [ ] Profile Mode preserves backup-before-sync and recovery behavior for Pro and OG.
- [ ] Application State migration is previewed, confirmed, versioned and recoverable from backup.
- [ ] Configurator guides Herdr plugin install/update and reports missing/incompatible Herdr without partial setup.
- [ ] Only preflight-verified Pro/EVO firmware may enable Herdr Mode; unsupported hardware/firmware fails closed.
- [ ] Mapping is workspace+pane scoped; pane move invalidates, never auto-rebinds.
- [ ] Bridge implements snapshot+event reconciliation, 20 FPS frame budget, agreed LED precedence and one-shot focus delivery.
- [ ] Apple Silicon DMG is signed/notarized; Linux x86_64 AppImage uses one-time Polkit udev setup and never needs `sudo` to run.
- [ ] pytest, pytest-qt and all physical release smoke gates pass.

## OPEN QUESTIONS / ASSUMPTIONS

- **Blocking external dependency**: the official, versioned, signed/checksummed Pro/EVO Herdr-capable firmware release URL and its capability/version contract are not yet supplied. Do not begin Phase 4 release work without it.
- **Assumed**: Herdr 0.8.2 is the initial minimum supported version because its researched plugin/socket surface is the only verified version. Re-evaluate only with backward-compatibility evidence.
- **Assumed**: direct-download DMG and AppImage are hosted as official release assets; release metadata signature format and signing-key custody must be specified before Phase 6.
- **Assumed**: `pytest-qt` is acceptable for the new PySide6 UI test harness; no existing tests constrain this choice.

## Confidence

**7/10.** The code and protocol boundaries are mapped and product decisions are closed. Confidence is limited by the missing official firmware release contract, absence of existing automated tests, and the need for real Apple Silicon/Linux/Pro-EVO release smoke environments.
