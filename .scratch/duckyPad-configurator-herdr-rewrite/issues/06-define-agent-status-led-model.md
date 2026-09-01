# 06 — 定義 agent 狀態與 LED 效果模型

Type: grilling
Status: resolved
Blocked by: 04

## Question

在整合契約已定後，標準 agent 狀態機、狀態優先序、RGB 色彩、動態效果、更新頻率、暫時覆寫、裝置斷線與未知狀態的降級規則應是什麼？哪些屬於全域預設，哪些可按映射覆寫？

## Answer

決議如下。

- **全域狀態預設**：`working` 為 `#3B82F6` 藍色 2.4 秒慢呼吸；`blocked` 為 `#F59E0B` 琥珀雙脈衝；`idle` 為 `#06B6D4` 青色恆亮；`done` 為 `#22C55E` 綠色一次確認脈衝後低亮恆亮；`unknown` 為 `#6B7280` 灰色低亮。這些狀態都以 Herdr 的有效狀態為準。
- **診斷與失連**：HID 已斷線沒有可顯示的裝置輸出；Configurator/Bridge 只記錄診斷。HID 仍連線但 Herdr 同步失去可信度時，以 `#8B5CF6` 紫灰慢閃表示。失效 Mapping 與未驗證 Capability 都熄滅，不能模擬可用狀態。
- **暫時回饋與優先序**：`agent.focus` response 成功後白色 150ms 脈衝，失敗後 `#EF4444` 紅色 300ms 脈衝，然後立即回到有效狀態。優先序為：無裝置無輸出 > Capability／失效 Mapping 熄滅 > Herdr 同步失連 > 暫時回饋 > agent 狀態。
- **覆寫**：Mapping 僅可覆寫 `working`、`blocked`、`idle`、`done`、`unknown` 的 RGB；狀態集合、優先序、效果節奏、安全／診斷色與回饋色都是全域固定。
- **更新預算**：狀態改變併入下一個 frame；動畫最多 20 FPS（50ms），未改變 frame 不送，且只有一個序列化 HID write。無 queue、無 output retry；write 失敗轉入裝置斷線流程。

術語已記錄於 [CONTEXT.md](../../../CONTEXT.md)。
