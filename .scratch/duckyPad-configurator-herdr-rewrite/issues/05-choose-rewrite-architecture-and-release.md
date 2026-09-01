# 05 — 選擇重寫架構與原生發行路徑

Type: grilling
Status: resolved
Blocked by: 01, 03

## Question

在既有相容性基線及平台限制已知後，新的 Configurator 應選擇何種桌面架構、程序／插件邊界、設定儲存與遷移設計，以及 macOS/Linux 安裝、HID 權限、簽章、更新與啟動流程？

## Answer

決議如下。

- **桌面架構**：Configurator 是 PySide6 單一 Python 應用。UI 全面重寫，但 Python domain、HID、DPDS compiler 與遷移器保持直接函式邊界；herdr Bridge 仍由 herdr plugin 獨立管理，不能依附 GUI 生命週期。
- **資料邊界與遷移**：Device Format（profile、ZIP、DPDS、DSB）繼續可由 duckyPad 和既有工作流直接交換。Application State 是 Platformdirs 使用者目錄的 schema-versioned 狀態，保存 UI 偏好與 Mapping。首次遷移先建立不可變備份，顯示預覽並讓使用者確認；寫回裝置資料只輸出相容 Device Format。
- **macOS**：首版只支援 Apple Silicon。每版交付一個 ARM64 `.app` 的 notarized DMG；CI 對 bundle 內所有 executable 做 Developer ID 簽章、Hardened Runtime、timestamp、notarization/staple，並以未開發機器實測啟動與 HID。
- **Linux**：首版只支援 x86_64，交付 AppImage。首次需要 HID 時以一次性 Polkit helper 安裝／移除最小 udev rule；正常 Configurator 與 Bridge 執行永遠不得以 `sudo` 取得裝置權限。
- **更新**：app 驗證已簽章 release metadata，顯示版本與變更後等待使用者確認，再開啟官方下載。首版不自動下載、替換或 rollback 執行中的 app。

Device Format 與 Application State 術語已加入 [CONTEXT.md](../../../CONTEXT.md)。
