# 三方向呈現記錄（duckyPad Configurator UI 重設計）

- 用戶原話：「原本的UI 我不太滿意 用 [huashu-design] 設計一下」（2026-09-02，未給風格參考 → 走 Fallback 三方向硬門；用戶未明說跳過）
- 假設（用戶未答問，依 best judgment 補齊，待其反饋修正）：
  - 範圍 = 整個主視窗重設計（含 herdr 主角功能），深色／淺色由方向自決
  - 產物 = 三版單檔 HTML 高保真 mockup，選定後再落回 Tkinter 實現
  - **初稿事實修正**：使用者確認主要裝置是 duckyPad **3 columns × 5 rows（3×5，15 onboard keys）**，不是 Pro 4×5（20 keys）；D1／D2 為探索存檔，已選 D3 依此重畫。
  - 視覺母題（三版初稿是 4×5；D3 實作的真實契約是 **3 columns × 5 rows 實體 key grid**），herdr agent board = 主角 zone

## 三版初稿
| # | 邏輯 | 風格錨點 | 檔案 | 截圖 |
|---|------|----------|------|------|
| 1 | 🎲 秒數輪盤（50s → 11） | Warm Editorial（Anthropic/Claude 暖紙出版系） | `demos/direction-1-warm-editorial.html` | `shots/direction-1.webp` |
| 2 | 🏆 現實參照 | Ableton Live 專業 DAW 暗色工作站 | `demos/direction-2-pro-daw.html` | `shots/direction-2.webp` |
| 3 | 🧠 最佳設計師 | Teenage Engineering（OP-1/PO-33 工業玩味極簡） | `demos/direction-3-teenage-eng.html` | `shots/direction-3.webp` |

## 用戶選擇
- 用戶原話：「D3」（2026-09-02）。
- 已選方向：**Teenage Engineering 的硬體面板語彙**——暖白硬體灰、黑色絲網印刷式標籤、唯一橙色控制 accent、**3 columns × 5 rows 厚鍵帽與 RGB 光縫**、右側常駐 herdr LED 儀表。
- 後續實作約束：不是逐像素移植 HTML；以 Tkinter 可達的深度實現 D3 的資訊架構、**3 columns × 5 rows** 鍵帽狀態 grid、左右區域與色彩／排印層級。`design/d3-implementation-spec.md` 是實作 source of truth。
