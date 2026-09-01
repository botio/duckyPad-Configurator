# 02 — 確立 herdr plugin 與 agent 控制事實

Type: research
Status: resolved
Blocked by: none

## Question

herdr 目前實際提供哪些 plugin extension points、agent 身分與生命週期事件、狀態事件、選取／聚焦命令與回應語意？找出可驗證的版本、介面與限制，讓後續 plugin 協定與 LED 狀態模型能以事實為準。

## Answer

研究完成。Herdr 0.8.2 的 plugin 是 manifest 驅動可執行檔；可用 `session.snapshot` 加 raw `pane.agent_status_changed` 同步狀態，並以 pane ID 作耐久映射、`agent.focus` 處理按鍵焦點。詳細事實、來源與風險見 [研究資產](../research/02-herdr-integration-facts.md)。
