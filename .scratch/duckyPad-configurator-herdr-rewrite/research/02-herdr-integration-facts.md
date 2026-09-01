# 02 — 確立 herdr plugin 與 agent 控制事實

**研究狀態：2026-09-01；未設計或實作 plugin。** 本文件鎖定官方 [`herdrdev/herdr`](https://github.com/herdrdev/herdr) 的 commit [`dbc398f`](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/Cargo.toml#L1-L12)，其 package 是 herdr **0.8.2**。較舊的已安裝版本不保證提供以下介面。

## 已確認的整合面

- **Plugin 模型**：plugin 是含 `herdr-plugin.toml` 的可執行目錄，不是 SDK。manifest 可宣告 `[[startup]]`、`[[actions]]`、`[[events]]`、`[[panes]]`、`[[link_handlers]]`；必填 `id`、`name`、`version`、`min_herdr_version`，並可限制 `linux`／`macos`／`windows`。Plugin command 可呼叫整個 Herdr CLI 或原始 local socket API。[官方 plugin 文件](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/plugins.mdx#L5-L31) [manifest 欄位](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/plugins.mdx#L78-L111)
- **可攜執行方式**：plugin runtime 提供 `HERDR_BIN_PATH`、`HERDR_SOCKET_PATH`、`HERDR_PLUGIN_CONTEXT_JSON` 等環境變數。`HERDR_BIN_PATH` 是可攜的呼叫路徑；原始 IPC 在 macOS/Linux 為 Unix socket、Windows 為 named pipe。[文件](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/plugins.mdx#L274-L287) [runtime 實作](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/src/app/api/plugins/runtime.rs#L35-L80)
- **事件**：啟用的 `[[events]]` hook 會取得 `HERDR_PLUGIN_EVENT` 與 JSON payload，僅會在宣告的 `on` 和平台相符時執行。可 hook 的事件包含 workspace/tab/pane 的 create/close/focus/move 與 `pane.agent_detected`、`pane.agent_status_changed`；高頻 `pane.output_changed`、`pane.updated`、`layout.updated`、`workspace.metadata_updated` 明確不在 hook 清單。[runtime](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/src/app/api/plugins/runtime.rs#L218-L258) [事件清單](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/src/api/schema/events.rs#L286-L355)
- **agent 身分**：agent 附屬於 pane；`pane_id` 是公開定位值。`agent.focus` 目標可用 pane ID，或唯一的 live agent name；agent-kind 標籤及 terminal ID 都不是合法 target。live name 在 agent 結束、release 或 replacement 時會清除。`AgentInfo` 可提供 `pane_id`、`workspace_id`、`tab_id`、`agent`、可選 live `name`、`agent_status`、`focused` 與 `state_change_seq`。[CLI 語意](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/cli-reference.mdx#L291-L317) [schema](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/api/herdr-api.schema.json#L6581-L6660)
- **狀態權威**：`pane.report_agent` 可回報的語意狀態只有 `idle`、`working`、`blocked`、`unknown`；`done` 是「未被看見的 idle 工作完成」衍生有效狀態，不能作為回報輸入。事件 `pane.agent_status_changed` 的 payload 必有 `pane_id`、`workspace_id`、`agent_status`，可含 `agent`、`display_agent`、`title`、`state_labels`。初始同步必須依官方 bootstrap 流程：第二條連線先訂閱、呼叫 `session.snapshot`、再套用緩衝事件。[request schema](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/api/herdr-api.schema.json#L2413-L2422) [事件 schema](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/api/herdr-api.schema.json#L6378-L6419) [socket bootstrap](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/socket-api.mdx#L91-L103)
- **焦點語意**：`agent.focus` 可接受相同 target resolver，或改用 `pane.focus` 加 pane ID。對背景 `done` 工作取得焦點，會將它標為 seen；焦點控制確實應由 Herdr 而非 Configurator 自行模擬鍵盤導航。[agent target schema](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/api/herdr-api.schema.json#L1381-L1392) [方法 schema](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/api/herdr-api.schema.json#L5394-L5408) [CLI 行為](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/cli-reference.mdx#L328-L333)
- **傳輸／相容性**：原始 IPC 是 local socket 上逐行 JSON，一行一個 request；client 應用 `ping`／`herdr status` 檢查協定並容忍未知欄位。[socket 格式](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/socket-api.mdx#L694-L730) [相容性指引](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/socket-api.mdx#L934-L940)

## 對後續決策的約束

1. **一對一映射鍵**應以 pane ID 為基礎；單獨以 agent label 映射不安全，live name 則須處理消失。這是由身分契約導出的設計推論。
2. **LED 資料流**可由 `session.snapshot` 初始化並接收 `pane.agent_status_changed`；hook 不是高頻狀態流保證，動態更新應使用 raw `events.subscribe`。這是由事件與 bootstrap 契約導出的設計推論。
3. **硬體按鍵**應要求 `agent.focus <target>` 或 raw `agent.focus`，以保留 Herdr 的焦點和 `done`→seen 語意。這是由焦點契約導出的設計推論。
4. plugin v1 沒有原生非終端 UI、managed plugin state API 或現成外部裝置映射 API；duckyPad bridge 的映射／儲存／UI 必須自行提供。

## 必須納入規格的未知數／風險

- 未找到官方一對一 HID key、duckyPad、MIDI、Stream Deck 或通用外部裝置 API。
- `pane.move` 跨 workspace 會分配新的公開 pane ID；若支援此動作，映射必須有 reconciliation policy，不能假定固定映射永久有效。[socket 文件](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/socket-api.mdx#L334-L347)
- 沒有外部相容性矩陣或 `pane.agent_status_changed` 延遲保證；發布時須以 plugin `min_herdr_version` 與 runtime protocol/version check 限制支援範圍。
- 0.7.3 只安裝在 named session 的 plugin，升至 0.8.2 後必須重新 install/link，因 plugin/enablement 已改為 per-user global。[changelog](https://github.com/herdrdev/herdr/blob/dbc398f580d1da6c336c6837a60b7e0710501d6d/docs/next/website/src/content/docs/CHANGELOG.md#L203-L209)
