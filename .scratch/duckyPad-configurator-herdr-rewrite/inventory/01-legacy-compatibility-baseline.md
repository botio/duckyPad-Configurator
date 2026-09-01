# 盤點既有 Configurator 相容性基線

**範圍：** 目前工作樹中可由程式碼證實的 GUI 工作流、設定資料與裝置操作。這是後續「選擇重寫架構與原生發行路徑」決定相容性承諾的事實輸入，**不是**已承諾的全部驗收範圍。

## 建議視為核心相容性候選的工作流

| 工作流 | 現有行為 | 重寫規格必須決定的相容性面 |
|---|---|---|
| 裝置連線與離線資料夾 | 掃描多台 duckyPad、讓使用者選擇；duckyPad Pro 走 MSC 磁碟路徑，OG duckyPad 透過 HID 匯出 SD 資料。裝置未找到或權限不足時，可退回手選本機資料夾。載入舊 OG 資料夾時會轉換鍵位排序。 | 新版是否保證兩種機型、實體裝置與離線備份資料夾皆可開啟；缺少權限／找不到裝置時必須有非破壞性的回復路徑。 |
| Profile 管理 | 載入目錄中的 profile 順序、顯示並可新增、刪除、複製、重新命名、重排。 | 現有 profile 順序與名稱是否完整保留；刪除／覆寫的確認與復原策略。 |
| Key 編輯 | 每個鍵有兩行名稱、按下／放開腳本、RGB、不可重複與可中止旗標；profile 有背景色、按下色、未用鍵變暗、橫向及兩種 half-step 旋轉設定。 | 新 UI 必須保留的欄位、哪些原始欄位只需匯入、以及 agent LED overlay 與既有 profile/key 色彩的優先序。 |
| Script 編譯與儲存 | 儲存前編譯所有按下／放開腳本成 DSB；編譯錯誤或超過大小限制時，顯示 profile/key 定位的錯誤並停止儲存。成功後寫出來源 `.txt`、binary `.dsb`、`config.txt`、`profile_info.txt` 與可選 `user_header.txt`。 | 必須保留「無法編譯不可寫入」的安全門檻；DPDS/DSB 是否保留既有 compiler 與檔案布局，或設計版本化遷移器。 |
| 匯入／匯出 | 單一 `duckyPad_Profile.zip` 可匯入為 profile；可選多個 profile 匯出成可分享 ZIP。 | 舊 ZIP 與設定目錄要能匯入；輸出格式是否需繼續與舊版互通。 |
| 儲存至裝置與備份 | 每次儲存先建立本機備份，再依檔案差異同步。MSC 裝置完成後 eject/reset；HID 路徑完成後 reset 並刷新 dump。使用者可從備份目錄自行複製回 SD 卡復原。 | 備份必須在裝置寫入前建立；寫入失敗、拔線與重連時的復原、同步與 eject/reset 可觀測狀態。 |
| 韌體／應用程式維護 | 程式含 app 與 firmware update status 檢查；韌體更新 UI 依機型導向官方更新說明，而不是在 app 內直接刷寫。 | 重寫版是否繼續檢查版本、支援哪些機型與如何交付更新說明；不得誤把目前行為描述成 app 內刷寫。 |

## 已確認的設定格式

- Root 有 `profile_info.txt`，以排序號碼加名稱記錄 profile 順序；可選 `user_header.txt`。
- 每個 profile 目錄有 `config.txt`、每鍵 `key<N>.txt`、可選 `key<N>-release.txt`，及其 `.dsb` binary。
- `config.txt` 表示 profile 與鍵的色彩、名稱、旗標、方向與 key index；目前讀取端會容錯列印例外後略過，不能假設格式驗證是嚴格或具交易性。

## 裝置／錯誤復原約束

- 現有連線 UI 對 macOS 權限不足顯示說明，對 Linux 明示 `sudo` 並提供改選資料夾；這是目前行為，不符合地圖已決定的免 `sudo` 原生交付目標。新版必須以 udev/安裝流程取代，而非保留此提示。
- 現有儲存流程的例外會顯示訊息，但不保證檔案或裝置同步具原子性。重寫規格應明定中斷寫入後的資料完整性與可復原界線。

## 程式碼依據

- [資料夾載入與兩機型轉換](../../../src/duckypad_config.py#L402-L438)
- [連線、MSC/HID 路徑與回退](../../../src/duckypad_config.py#L544-L598)
- [儲存前編譯與輸出檔案](../../../src/duckypad_config.py#L886-L1022)
- [儲存、備份、同步、eject/reset](../../../src/duckypad_config.py#L1029-L1060)
- [Profile ZIP 匯入](../../../src/duckypad_config.py#L1919-L1938)；[匯出](../../../src/duckypad_config.py#L1959-L1996)
- [設定格式讀取](../../../src/duck_objs.py#L52-L97)
- [HID 差異同步](../../../src/hid_op.py#L141-L154)
- [韌體更新說明連結](../../../src/duckypad_config.py#L361-L365)
