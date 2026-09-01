# 08 — 確立 duckyPad 實體按鍵事件通道

**證據範圍：** 本研究僅以本機 sibling checkout `/home/botio/Projects/duckyPad` 的 `firmware/evo` 與舊 OG 韌體原始碼確認。沒有證實這些 `HERDR_*` 擴充已隨官方 release 發布或具穩定版本對應。

## 結論

可直接驗證的唯一 host-visible 實體按鍵通道是 **duckyPad Pro/EVO 在 herdr mode 下的 custom-HID IN event**。它只傳送 15 個主鍵的短按，不是 press/release stream；啟用後會在正常 DPDS profile 處理之前 early return。因此 Herdr mode **取代**正常巨集，不是旁路觀察。

OG 只證實傳送 macro keyboard HID output，未證實可把實體 key slot 回報給 host，也未證實 host-controlled per-key RGB frame。OG 不可納入此 integration contract。

## Pro/EVO 已驗證的協定

### Key event

```text
IN report, 64 bytes:
[0] = 0x04        custom HID device-to-host usage
[1] = 0xF0        HERDR_IN_KEY_EVENT
[2] = 0x00        OK
[3] = slot         1..15
[4..63] = 0
```

`process_keyevent()` 在 `herdr_mode` 啟用時，僅對 `swid < 15` 的 `SW_EVENT_SHORT_PRESS` 傳送上述 event，然後 return。它不傳 release、long press、hold、`+/-` 鍵；也不執行 `keyN.dsb` 或 `keyN-release.dsb`。

### Bridge 輸出

```text
OUT [0]=0x05 [1]=0 [2]=34 [3..47]=15 × RGB   SET_RGB_FRAME
OUT [0]=0x05 [1]=0 [2]=35 [3]=len [4..]      SET_OLED_TEXT
OUT [0]=0x05 [1]=0 [2]=36 [3]=0|1            SET_HERDR_MODE
```

RGB frame 寫入 15 個 NeoPixels；OLED 文字最多 56 bytes。commands 34–36 直接 return，沒有 ACK 或已證實 flow-control，因此 Bridge 必須自行 serialise/限流，不能承諾無遺失或固定延遲。

## 契約限制

1. capability 僅能命名為本產品的 `duckypad-pro-herdr-keypress-v1`；必須 preflight 驗證支援 command 34–36 與 event `0xF0` 的 firmware，無法驗證時 fail closed。
2. 啟用 mode 前必須告知使用者：正常 DPDS profile key behavior 交給 Bridge，不與 herdr mode 共存。
3. Bridge 僅處理有效 `[0x04, 0xF0, 0x00, slot]` 且 `slot ∈ 1..15` 的短按；不得依賴 release。
4. disconnect 後應清除本地狀態；reopen 後重新 preflight、enable mode，並重送完整 RGB frame。這是 host 安全政策，不是 device protocol 的 replay 保證。
5. 明確不支援：OG、release/hold、`+/-`、DPDS coexistence、保證的 event latency/delivery、未驗證 release firmware 自動啟用。

## 已知未知數

- Linux udev、macOS entitlement、Windows ACL/driver 仍需以實機驗證。
- custom-HID event 沒有來源可證實的 queue/backpressure、delivery、latency 或 reconnect 保障。
- 目前 source 沒有確認任何官方 Pro release 包含 herdr mode。

## 程式碼依據

- `/home/botio/Projects/duckyPad/firmware/evo/Src/hid_task.c:101-155`：15-key RGB frame、OLED、event buffer。
- `/home/botio/Projects/duckyPad/firmware/evo/Src/hid_task.c:233-265`：commands 34–36、無 ACK 的 early return。
- `/home/botio/Projects/duckyPad/firmware/evo/Src/keypress_task.c:248-287`：herdr mode 短按送 event 後 return；正常 DPDS 分支在其後。
- `/home/botio/Projects/duckyPad/firmware/evo/Inc/hid_task.h:25-44`：commands 與 event constants。
- `/home/botio/Projects/duckyPad/resources/old_v1/firmware/Src/keyboard.c:145-255`：OG macro keyboard HID output。
- `/home/botio/Projects/duckyPad/resources/old_v1/firmware/Src/buttons.c:1-126`：OG 實體按鍵只在內部 GPIO path 處理。
