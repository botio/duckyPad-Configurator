# 08 — 確立 duckyPad 實體按鍵事件通道

Type: research
Status: resolved
Blocked by: none

## Question

當 duckyPad 正在使用既有 profile 時，macOS/Linux 上的常駐 Bridge 可透過哪些已支援且可發布的裝置通道收到實體按鍵按下／放開事件，並同時安全更新 LED？分別驗證 duckyPad Pro 與 OG duckyPad 的協定、權限、延遲、斷線和對既有 DPDS 腳本的干擾限制，供 herdr focus 命令與 LED 互動契約使用。

## Answer

研究完成。已驗證的 host key-event 通道只存在於未證實發布版對應的 Pro/EVO herdr mode：它取代正常 DPDS、只送 15 個主鍵短按；OG 沒有可證實的等價通道。完整協定、能力檢查與未知項見[研究資產](../research/08-duckypad-key-event-channel.md)。
