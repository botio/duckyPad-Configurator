# 03 — 評估跨平台桌面交付限制

Type: research
Status: resolved
Blocked by: none

## Question

哪些桌面技術與發行方案能在 macOS 與 Linux 提供原生應用程式入口、可靠 HID 存取、簽章／權限處理、更新與可維護的打包流程？比較可驗證的技術限制與現有 Python/HID 資產的遷移成本，供重寫架構決策使用。

## Answer

研究完成。Python + PyInstaller、PySide6 與 Tauri sidecar 都可符合不同取捨；無論選型，Linux udev 權限與 macOS 所有 bundled executable 的簽章／notarization 都是發行規格。詳細比較、來源與待實測項目見 [研究資產](../research/03-desktop-delivery-constraints.md)。
