# UI 對後端的需求（尚未實作，前端目前以 placeholder 或前端暫代）

前端沒有改 server.py / engine/，以下是之後想要的欄位或 API。

1. **小測驗**：`GET /api/quiz`（題目）、`POST /api/quiz`（作答 -> 依附類型、易被騙分數）。目前首頁／選角／結算頁只有「即將推出」按鈕。
2. **成就／徽章**：`GET /api/badges?player=ID`，並在 `/api/flag`、`/api/review` 回傳 `new_badges: [{id,title,desc}]`，前端才能做解鎖動畫。
3. **暈船互助會**：需要匿名貼文／留言 API 與內容審核（含危機字詞轉介 1925），先不設計細節。
4. **教練訊息帶尺度**：目前教練泡泡標題用「目前滑桿值」顯示尺度，捲回舊訊息會不一致。希望 coach 訊息帶 `severity`（1–3）。
5. **階段總數**：前端寫死 5 階段。希望 `/api/start`、`/api/message` 回傳 `stage_total`。
6. **結算逐句覆盤**：`coach.items` 沒有 `msg_id` 與回合順序，也沒有玩家當時的回覆。希望每筆加 `msg_id`、`stage`、`player_reply`，才能做完整對話式回放。
7. **紅旗總數即時值**：希望 state 內有 `flags_caught_so_far`（不洩漏答案的計數），可在聊天中顯示「已檢舉 N 面」。
8. **角色資料**：`/api/personas` 目前沒有 `color`、`description`、`difficulty`；現在人格顏色寫在 CSS（依 id）。
9. **危機資源**：前端為了「永遠可點」把 1925/165/113 寫死在 app.js，建議新增 `GET /api/resources` 讓前後端同源。
10. **主題／尺度偏好**：目前存在 localStorage；若要跨裝置，需要 profile 欄位 `prefs`。

## 第 6 輪新增
- state 請加 `reviewed: bool`（或 `phase`）。前端現在用「自然結束後所有 NPC 訊息是否都帶 red_flags」推斷已結算；若玩家把每一則 NPC 訊息都標過旗，或 GAME_DEV 開了 reveal，會被誤判為已結算（🚩 鈕被鎖、不顯示「最後確認」）。
