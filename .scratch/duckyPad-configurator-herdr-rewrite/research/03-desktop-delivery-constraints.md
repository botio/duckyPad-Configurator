# 03 — 評估跨平台桌面交付限制

**研究狀態：2026-09-01；未選定技術棧。** 已用 agent-reach 的 web backend 及官方一手文件查核。現有程式是 Tkinter GUI，`src/requirements.txt` 已宣告 `hidapi` 與 `pyinstaller`，而現有 macOS 打包腳本採 PyInstaller `--onefile`；因此以下「保留 Python」不是抽象假設，而是可延續既有執行路徑。[本機來源：GUI](../../../src/duckypad_config.py) [本機來源：依賴](../../../src/requirements.txt) [本機來源：macOS 打包](../../../src/_build_mac_pyinstaller.py)

## 共同且不可迴避的交付限制

| 面向 | 已驗證事實／規格影響 |
|---|---|
| HID 重用 | HIDAPI 明確支援 Windows、Linux、macOS；Linux 可用 `hidraw` 或 libusb backend，macOS backend 是 `IOHidManager`。它也明示：未授權 Linux 使用者要用 HIDAPI 存取 HID 裝置，應隨應用提供 udev rule。[HIDAPI README](https://github.com/libusb/hidapi#about) |
| Linux 權限 | systemd-udevd 會管理 device-node 權限；udev rule 可依裝置屬性比對，並以 `OWNER`、`GROUP`、`MODE` 指定 device-node 權限。規格必須包含以 duckyPad 的實測 VID/PID（及必要時 interface/subsystem）產生的 rule、安裝位置與移除流程；不能把 `sudo` 當正常 GUI 啟動模式。[systemd udev(7)](https://www.freedesktop.org/software/systemd/man/latest/udev.html) |
| macOS 直接下載 | Apple 對直接分發的 Developer-ID 軟體要求所有可執行檔有效簽章、Developer ID certificate、Hardened Runtime、secure timestamp；notary service 通過後產生可 staple 的 ticket，Gatekeeper 可使用它。這同時適用主程式和任何打包進 app bundle 的 Python/HID 原生二進位檔。[Apple：Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) |
| 架構／CI | PyInstaller 產物與執行它的 OS、Python 版本、32/64 位元綁定，故 macOS ARM64、macOS x86_64 與目標 Linux architectures 都需要相對應 build/test lane，不能由一台 Linux 建出全部可交付產物。[PyInstaller operating mode](https://pyinstaller.org/en/stable/operating-mode.html) |

## 可比較的交付選項

| 選項 | Python/HID 與既有工作流 | macOS / Linux 交付 | 更新 | 遷移成本與主要新增風險 |
|---|---|---|---|---|
| **A. 保留 Python GUI（既有 Tkinter 或改 Python GUI），以 PyInstaller 打包** | 可直接保留 `hid_op.py`/`hidapi` 與大多數 Python 領域邏輯；PyInstaller 會收集 interpreter 與依賴，使用者無須安裝 Python。它識別 TkInter；動態 import/路徑操作則需要 spec、hidden import 或 hook 明確納入。[PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html) | 每個 target 原生建置 bundle；可選 one-folder 或 one-file。one-file 啟動會解壓至臨時 `_MEI_*` 目錄，較慢；Linux `/tmp` 若 `noexec`，one-file 不相容（可設 runtime tmpdir），所以硬體工具的交付驗證應涵蓋此情境。macOS 仍須將 bundle 中所有 executables 正確簽章、notarize、staple。[PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html) [Apple](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) | PyInstaller 官方「What it does」文件只描述 bundle 建置／分發，未提供內建 updater 契約；需另行決定 signed feed、下載／替換、rollback 與 macOS re-sign/notarize 發布步驟。這是**需補設計**，不是宣稱不存在任何第三方 updater。 | **最低 UI/核心遷移**（可保留 Python GUI 與 HID 層）；但要補齊 release engineering、原生依賴收集、macOS universal/雙架構、sudo-free udev 安裝與自訂更新器。現有 macOS 腳本以 `sudo` 啟動且是 one-file zip，與目標「原生入口」及正常使用者權限相衝，需淘汰而非沿用。 |
| **B. Python GUI + Qt for Python 的 `pyside6-deploy`（若 UI 重寫到 PySide6）** | HID Python 模組可仍留在同一 Python process；但 Tkinter views/event wiring 要移植到 PySide6，故核心硬體層可重用、UI 不可直接重用。Qt 官方的 `pyside6-deploy` 是 Nuitka wrapper，產生 Linux `.bin`、macOS `.app`；`onefile` 是預設，也可選 `standalone`。[Qt for Python 6.10](https://doc.qt.io/qtforpython-6.10/deployment/deployment-pyside6-deploy.html) | 直接得到 macOS `.app` 與 Linux binary，但仍要自行處理 Apple Developer-ID signing/notarization 和 Linux udev rule／發行包。工具本身另要求 Linux `readelf`、macOS 12+ `dyld_info` 作高效率依賴打包；`macos.permissions` 會映射至 app `Info.plist` UsageDescription。[Qt](https://doc.qt.io/qtforpython-6.10/deployment/deployment-pyside6-deploy.html) | 文件定義 deploy tool，不定義 in-app update protocol；仍須自選更新層與簽章發行流程。 | **中等到高**：HID/domain Python 可保留，UI 全面改寫；換來 `.app` 形式的原生 Qt GUI。需對現有 Tk 操作（檔案、色彩、對話框、長 HID 操作）做 parity 驗收。 |
| **C. Web shell：Tauri 2 + web UI + 打包的 Python HID sidecar** | Tauri 可 bundle 任意語言 executable，官方特別列 Python CLI/API server（可用 PyInstaller）為 sidecar 用例；因此可把既有 Python HID/設定/遷移邏輯變成受限 IPC service，前端與其通訊，而不是把 HID 重寫為 JS/Rust。每個 target/architecture 都必須提供 `name-$TARGET_TRIPLE` 的 sidecar；sidecar spawn 另需要明確 Tauri shell capability。[Tauri sidecar](https://v2.tauri.app/develop/sidecar/) | Tauri CLI 可生成 platform bundles；官方列 Linux Debian、Snap、AppImage、Flatpak、RPM、AUR 等分發形式，macOS 可直接下載 DMG 或 App Store。直接下載的 macOS app 仍需 code signing 與 notarization。[Tauri distribute](https://v2.tauri.app/distribute/) 針對 HID，sidecar 仍是同一套 HIDAPI/Linux udev/macOS signing 問題；Tauri 不會替 sidecar 消除它。 | 官方 updater 支援 macOS、Linux、Windows，可取 dynamic server 或 static JSON；production 要 TLS，更新 artifact 必須有不可停用的簽章驗證，且私鑰遺失後不能再給既有使用者發更新。它會為 Linux 產生 AppImage + `.sig`，macOS 產生 `.app.tar.gz` + `.sig`。[Tauri updater](https://v2.tauri.app/plugin/updater/) | **高**：保留 Python HID 需界定 versioned IPC、sidecar lifecycle/error/reconnect、JSON serialization、security capability 與 Python bundle 每架構產物；UI 則從 Tkinter 完整重寫為 web stack。好處是 updater 是已定義的產品能力，而非另造；代價是 Rust/Tauri、JS/TS 與 Python 三段 release chain。 |

## 對規格的可操作結論（非選型）

1. 將「HID access」列為與 GUI 框架無關的 release acceptance criterion：在每個支援 Linux distribution 的乾淨帳號，安裝後**不以 sudo 啟動 app**即可 enumerate、read/write duckyPad；並驗證拔插後裝置重連。這源自 HIDAPI 對 udev 的明確要求及 udev 的 permission ownership model。[HIDAPI](https://github.com/libusb/hidapi#about) [udev](https://www.freedesktop.org/software/systemd/man/latest/udev.html)
2. 將 macOS release acceptance criterion 寫成：每個 nested executable（Python interpreter、hidapi/native wheels、Tauri sidecar 若採用）簽名後，Developer-ID + Hardened Runtime + timestamp，送 notarytool、檢查 notary log、staple，並在未開發機器 Gatekeeper 啟動與實機 HID 存取。Apple 要求的保護是「all executables」，不是只有外層 `.app`。[Apple](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
3. 不論選 A/B/C，將設定遷移做成可獨立測試的 Python domain/import layer；C 只是以 IPC 呼叫它，A/B 直接呼叫它。如此可避免將舊設定格式、HID protocol 和 UI/framework migration 綁成一次不可診斷的切換。

## 尚待實測／決策的技術未知數

- duckyPad 實際 VID/PID、interface、hidraw path 與所需 read/write modes；據此確認最小 udev match/rule，並在 Debian/Ubuntu、Fedora、Arch 與無 systemd 環境界定支援邊界。
- macOS Intel 與 Apple Silicon 的 HIDAPI Python wheel／PyInstaller bundle 是否都能通過 Hardened Runtime/notarization，及是否要 universal2 或雙下載；不可由上述一般文件推斷。
- 目前 Python `hidapi` package 的確切版本、native backend 選擇與打包後實際動態庫，及它是否只在 `hidraw` 下運作；應從 lockfile/實機 bundle 和裝置測試確認。
- 既有 `check_update.py` 的 protocol、host、信任模型和使用者資料位置；這決定 A/B 是保留、改造或遷移。Tauri updater 若採 C，需先決定 signing-key custody、HTTPS endpoint、channel/rollback 與舊版升級路徑。
- 是否需要 sandbox/App Store。此票只驗證 direct-distribution 路徑；App Store entitlement／hardware access 的合規性不能從 direct-download notarization 規則外推。
- herdr plugin 的桌面端進程／IPC 邊界尚未由「確立 herdr plugin 與 agent 控制事實」定義；它會決定 Configurator 是否必須常駐、如何收到 agent status、以及 sidecar/GUI 的 lifetime 與 auto-update restart 順序。

## Sources

- [HIDAPI README](https://github.com/libusb/hidapi#about)
- [systemd udev(7)](https://www.freedesktop.org/software/systemd/man/latest/udev.html)
- [Apple: Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
- [PyInstaller operating mode](https://pyinstaller.org/en/stable/operating-mode.html)
- [Qt for Python 6.10 deployment](https://doc.qt.io/qtforpython-6.10/deployment/deployment-pyside6-deploy.html)
- [Tauri v2 sidecar](https://v2.tauri.app/develop/sidecar/)
- [Tauri v2 distribution](https://v2.tauri.app/distribute/)
- [Tauri v2 updater](https://v2.tauri.app/plugin/updater/)
