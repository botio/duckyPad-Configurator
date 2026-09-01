# 01 — 盤點既有 Configurator 相容性基線

Type: task
Status: resolved
Blocked by: none

## Question

必須保留與遷移的既有使用者工作流、設定資料格式、裝置操作與錯誤復原行為各是什麼？盤點結果要能支撐後續相容性驗收範圍的決策。

## Answer

盤點完成。相容性候選涵蓋兩機型連線／離線資料夾、profile/key 編輯、DPDS 編譯、ZIP 匯入匯出、備份與差異同步、以及版本／韌體更新說明；現有 Linux `sudo` 提示必須由免權限的安裝流程取代。完整資料格式與錯誤復原邊界見[盤點資產](../inventory/01-legacy-compatibility-baseline.md)。
