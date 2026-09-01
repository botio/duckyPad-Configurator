# Wayfinder：duckyPad Configurator 與 herdr 跨平台重寫規格

## Destination

產出可實作的重寫規格與路線圖：新的 duckyPad Configurator 支援 herdr，讓可配置的一對一 agent／實體按鍵映射以 LED 動態效果顯示標準 agent 狀態，按鍵事件交由 herdr 將對應 agent 帶到前景；同時提供 macOS 與 Linux 的原生安裝、啟動與完整既有功能／設定遷移策略。

## Notes

- Domain: duckyPad 裝置整合、herdr plugin、跨平台桌面應用與設定遷移。
- 每個決策票必須先載入 `grilling` 與 `domain-modeling`；外部技術/API 事實使用 `research`。
- 此地圖預設只釐清決策與規格，不承載目的地實作。
- 已知方向：一對一可配置映射；標準狀態機搭配動態 LED；視窗焦點由 herdr 處理；macOS/Linux 原生應用入口；保留現有核心工作流並遷移設定。

## Decisions so far

<!-- Resolved child tickets are indexed here; the ticket owns its detailed resolution. -->

- [確立 herdr plugin 與 agent 控制事實](issues/02-establish-herdr-integration-facts.md)：Herdr 0.8.2 可用 pane ID、snapshot、agent-status 事件與 `agent.focus` 支援 bridge；映射和外部裝置 UI 必須自行實作。
- [評估跨平台桌面交付限制](issues/03-assess-desktop-delivery-constraints.md)：Python/PyInstaller、PySide6、Tauri sidecar 都可行；Linux udev 與 macOS 簽章／notarization 是不隨框架改變的交付門檻。

- [盤點既有 Configurator 相容性基線](issues/01-inventory-legacy-compatibility.md)：重寫的相容性候選包含兩機型、設定資料與腳本、ZIP、備份／同步及更新說明；既有 Linux `sudo` 路徑必須淘汰。

- [確立 duckyPad 實體按鍵事件通道](issues/08-establish-duckypad-key-event-channel.md)：可證實的 Pro/EVO herdr mode 只支援 15 鍵短按且取代 DPDS；OG 與 release 對應未獲證實，必須 fail closed。

- [選擇 herdr plugin 整合契約](issues/04-choose-herdr-integration-contract.md)：plugin 管理 Bridge；Pro/EVO 專用 Herdr Mode 以 workspace+pane 映射、snapshot+事件同步及不重試的 `agent.focus` 實作安全選取。

- [選擇重寫架構與原生發行路徑](issues/05-choose-rewrite-architecture-and-release.md)：PySide6 單一 Python app 保留裝置格式並另存 versioned app state；Apple Silicon notarized DMG、x86_64 AppImage + Polkit udev、確認後更新。

- [定義 agent 狀態與 LED 效果模型](issues/06-define-agent-status-led-model.md)：全域冷靜高辨識狀態機、20 FPS 合併 frame 與短暫 focus 回饋；Mapping 僅可改 agent-status 顏色。

- [原型化 agent／按鍵映射設定流程](issues/07-prototype-mapping-configuration-flow.md)：日常使用 A 的裝置畫布；Herdr Mode／workspace／capability 風險使用 C 的明確引導，原型保留在 `prototype/mapping-flow-ui`。

## Not yet specified


## Out of scope

- Configurator 自行以 macOS、X11 或 Wayland API 尋找並聚焦 herdr agent 視窗；焦點控制由 herdr 負責。
- 此地圖不直接實作重寫版、herdr plugin 或 duckyPad 韌體變更；完成規格後另行排程實作。
