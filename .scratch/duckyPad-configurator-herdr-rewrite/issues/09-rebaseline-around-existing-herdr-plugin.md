# 09 — 收斂目的地：圍繞既有 herdr plugin 管理

Type: grilling
Status: resolved
Blocked by: 02, 04, 05, 06, 08

## Question

使用者確認採用 duckyPad repo 現有的 Rust `ducky-pad-bridge` plugin（`herdr plugin link` + user service），並將目的地收斂為「讓 Configurator 能管理此 plugin + v3.1.0-herdr 韌體」，不再全面重寫 Configurator GUI。此票取代 05/06/07 的重寫範圍。

## Answer

決議如下。

- **Bridge**：採用 repo 內 `herdr-ducky-pad/` 的 Rust daemon（`ducky-pad-bridge`）。它由 `install.sh` 建為 user service（Linux systemd / macOS launchd），並註冊 herdr plugin；不由 herdr one-shot startup hook 監督（該 hook 必須退出，不能監督長駐 daemon）。
- **韌體**：可取得的 herdr-capable 韌體是 repo 內的 `firmware/duckypad_v3.1.0-herdr.dfu`（`fc32dad0` 之後的 release；SHA-256 `b1ea7431…18da96`，commit `e6738101`），官方 3.0.4 **不含** herdr mode。
- **Configurator 新職責**（在現有 `src/duckypad_config.py` 上擴充，不換 GUI 框架）：
  1. **環境診斷**：偵測 `herdr`、`cargo`、`dfu-util`、Rust toolchain 與 plugin 狀態。
  2. **Rust plugin 安裝器**：包裝 `herdr-ducky-pad/install.sh`（build + `herdr plugin link` + user service），提供進度、log、idempotent 重跑、失敗診斷。
  3. **LED/映射設定**：以可移植設定檔（JSON）讓 Bridge 可選地讀取 per-status RGB 與 slot 指派；缺省維持 Bridge 內建 locked palette，未配置時行為不變。
  4. **韌體閃寫引導**：對 EVO 裝置提供 `dfu-util --device 0483:df11 -a 0 -D …duckypad_v3.1.0-herdr.dfu` 的 guided flash（DFU 模式 + 可回復），並能回刷官方 `duckypad_v3.0.4.dfu`。
- **LED 色票**：Bridge 現行 locked palette（blocked=紅、working=綠、done=藍、unknown=琥珀、idle=dim gray）為預設；Configurator 只可覆寫 RGB，不改變 sticky slot 分配語意（pane_id 身分、list order 填 slot）。
- **重寫降級**：原 05/06/07 的 PySide6 全面重寫、20 FPS 動畫、PyInstaller DMG/AppImage 與自寫 Python Bridge 不再屬於本次範圍；改以「擴充既有 Tkinter Configurator + 管理既有 Rust plugin」達成 herdr 支援。

術語更新見 [CONTEXT.md](../../../CONTEXT.md)。
