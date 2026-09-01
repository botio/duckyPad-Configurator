# 07 — 原型化 agent／按鍵映射設定流程

Type: prototype
Status: resolved
Blocked by: 01, 04, 05, 06

## Question

以低保真原型讓使用者決定重寫版的裝置選取、agent 清單、實體按鍵映射、色彩／效果設定、衝突提示、未映射 agent 與失連狀態的操作流程；原型要形成可驗收的資訊架構與互動模型，不實作產品。

## Answer

使用者選擇混搭 A 與 C。

- **日常設定**採 A 的三欄裝置畫布：左欄是目前 workspace 的 agent 與映射狀態，中欄是 15-slot duckyPad 視覺畫布，右欄是所選 slot 的 Agent Target、目前 LED、RGB 覆寫及失效警告。未映射 agent 始終留在左欄；未映射／失效 slot 不假裝有可用動作。
- **Herdr Mode 啟用、切換 workspace、capability 恢復**採 C 的引導流程：先選擇驗證過 capability 的 Pro/EVO 裝置，再選 workspace，最後以明確確認頁告知 Herdr Mode 會取代 Profile Mode 的 DPDS key handling。OG、未驗證 firmware 或不支援 capability 不能進入映射畫布。
- **失連與跨 workspace**在全域裝置狀態與 slot inspector 顯示；`pane.move` 後立即把 Mapping 顯示為失效，而不是自動跟隨 agent name。

三個變體的 primary source 已捕捉於 throwaway branch `prototype/mapping-flow-ui` 的 commit `ae95b12`；主分支只保留本決議。
