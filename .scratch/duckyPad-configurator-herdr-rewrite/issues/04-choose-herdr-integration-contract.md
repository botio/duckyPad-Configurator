# 04 — 選擇 herdr plugin 整合契約

Type: grilling
Status: resolved
Blocked by: 02, 08

## Question

根據 herdr 已驗證的延伸點，plugin 與 Configurator／duckyPad 之間應採用何種事件與命令契約：agent 識別、註冊、狀態更新、LED 回寫、按鍵選取、焦點請求、確認、重試、失連及多工作區隔離各由誰負責？

## Answer

決議如下。

- **生命週期與責任**：herdr plugin 的 startup hook 啟動並管理無 UI 的 Bridge；Configurator 只編輯與觀測設定。Herdr 是 agent 狀態與焦點的權威；Bridge 管理 HID、裝置 capability、映射載入及事件轉送。
- **設定權威**：Configurator 原子寫入 schema-versioned 使用者設定檔；Bridge 驗證後 watch/reload，無效檔案保留最後可用設定並輸出診斷。
- **硬體邊界**：只在 preflight 驗證通過本產品 `duckypad-pro-herdr-keypress-v1` capability 的 Pro/EVO 裝置上啟用 Herdr Mode。此模式只支援 15 主鍵短按和全 RGB frame，並取代 Profile Mode 的 DPDS key handling；關閉後才回到舊 profile/DPDS。OG 與未確認 firmware 一律 fail closed。
- **映射**：一個 slot 對一個 `{workspace_id, pane_id}` Agent Target。`pane.move` 跨 workspace 後立即使映射失效；不可用 agent name 自動重綁或靜默改指向。
- **狀態與失連**：Bridge 以訂閱、`session.snapshot`、再套用緩衝事件完成初始化與重連 reconciliation。Herdr 或 HID 失連時清除可信 runtime state 並降級，重連後重新 preflight、啟用 mode、同步與重送完整 LED frame。
- **按鍵焦點**：有效且已映射的短按只發一個序列化 raw `agent.focus`，等待 response 並以 Herdr focus event 確認。不自動重試或持久化 focus 命令；未映射／失效 slot 不送命令，失敗只記錄診斷，下一次按鍵才可重試。

術語已記錄於 [CONTEXT.md](../../../CONTEXT.md)；硬體通道的證據與明確不支援範圍見[研究資產](../research/08-duckypad-key-event-channel.md)。
