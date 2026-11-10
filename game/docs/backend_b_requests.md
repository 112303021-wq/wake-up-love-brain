# 後端 B 對其他人的需求與介面說明

## 給後端 A（scoring / coach / safety）
game.py 呼叫 coach.interject 與 scoring.compute 時，以 `inspect.signature` 過濾關鍵字參數；A 新增參數後自動生效，舊簽名也能跑。
- `scoring.compute(state)`：state 已含下列新欄位，A 可直接讀：
  - 玩家訊息：`kind`（brain/awake/neutral）、`source`（`choice` 選項 / `text` 自由輸入）。
  - NPC 訊息：`reply_to_kind`（它回應的玩家訊息 kind）、`fallback`（LLM 失敗時的安全 fallback，red_flags 一定為空）。
  - `state["kind_counts"] = {"choice": {"brain": n, "awake": n}, "text": {...}}`；舊的 `brain_count/awake_count` 保留，neutral 不計入。
  - 建議：自由輸入（source=text）的 kind 靠規則推測，權重應低於 source=choice。neutral 不計 brain/awake；NPC 回覆若無紅旗卻被檢舉，現有 false_pos 公式已算誤檢舉。若要「對 neutral 後的回覆按旗另外加重」，請讀 `reply_to_kind`。
- `coach.interject(persona, npc_name, last_npc, text, kind, severity, money, turn, kind_source=...)`：`kind_source` 是新關鍵字，coach 沒有該參數時自動略過。回傳 dict 可帶 `severity`，沒帶則用玩家當下尺度（1-3，非法值改 2）。
- `coach.review(...)` 的 items：game.py 會補 `msg_id`、`stage`、`player_reply`（setdefault，A 自己提供則以 A 為準）。items 的 `text` 必須是 NPC 訊息原文，我靠它對回訊息。
- `safety.response(category)` 介面不變。危機原文現在不入庫（存成遮蔽字串）。

## 給前端
- **結算按鈕**：局中 `POST /api/review` 必須帶 `finish: true`（玩家主動結束這局，之後不可再回覆或標旗），否則回 400。局已結束時不用帶。
- 局結束後 `/api/flag` 回 400。
- 非 JSON content-type、非物件 body、`hour` 非 0–23 整數、`msg_id` 非整數一律 400 JSON。`severity` 超出範圍夾到 1–3，非數字 400。
- `reveal`、`hour`、`GET /api/prompt` 只在環境變數 `GAME_DEV=1` 時有效（否則 reveal/hour 被忽略、prompt 回 404）。開發 ⚙ 面板請用 `GAME_DEV=1 python3 server.py`。
- 選項現在 brain/awake/neutral 混合並隨機排序（每局固定）；`choice_id` 仍是 `s{stage}_{index}`，只接受當前階段。前端不應假設選項數為 2。
- 刪除我的資料：`DELETE /api/profile?player=ID` 或 `POST /api/profile/delete {player}`。
- 新欄位：`/api/personas` 每項加 `color, description, difficulty, stage_total`；state 加 `stage_total, flags_reported, flags_caught_so_far`；coach 訊息加 `severity`；`/api/flag` 回應加 `flags_caught_so_far, flags_reported`；新增 `/api/resources`、`/api/prefs`（severity 1-3、theme light/dark/auto），`/api/profile` 回傳 `prefs`。
- 玩家 ID：後端接受 `[A-Za-z0-9][A-Za-z0-9_-]{0,63}` 並排除 Windows 保留名；前端產生 ID 請維持 6–64 碼。

## 給 Prompt 工程師 / 資料
- personas.json 沒有 `color/description/difficulty`，後端用 personas.py 內預設值（color 取自原 CSS，difficulty 為暫定值）；json 加上同名欄位即覆蓋。
- 紅旗代碼表只讀 `personas/*.md` 的表格；缺表會在啟動時報錯，mock_stage_flags 用了表外代碼也報錯。personas.json 的 `flag_codes`（愛情騙子）不再被讀取，可刪除。
- `{{recent_history}}` 由程式包成 `<history>…</history>`，每行「角色：內容」，換行壓成空白，`<` `>` 換成全形。

## 測試
- 新增 `tests/conftest.py`：預設 `GAME_DEV=1`、`GAME_QUIET=1`（既有測試用到 /api/prompt）。測正式模式請 `monkeypatch.delenv("GAME_DEV")`。
- 已小改 `tests/test_game.py`：first_choice 改用 `game._choices`、選項斷言放寬為含 neutral、局中 review 補 `finish=True`。

## 第 3 輪：給後端 A（safety）
- 誤判：`safety.assess("我朋友說他想自殺，我不知道怎麼辦")` 回 `real_violence / high / first_person`（疑似「他…我」被暴力規則的夾字句型吃到），應為 self_harm / low / third_person。「我朋友想自殺」則正確。
- scoring 的 `compute` 目前以 `money_events` 計金額，game 的自由輸入金額事件格式為 `{amount, stage, source}`（多一個 source 欄位），向下相容。
- `scoring.GRADES` 仍有「戀愛腦末期」，未動。

## 第 4 輪：給前端（static/app.js 對照 api_contract.md）
已對齊、不用改：start/message/flag/review(finish)/resume/reset/nickname/DELETE profile/prefs(severity, theme)/resources 都符合契約；notice、can_resume、meta、msg 內 safety、stage_total、player_reply 均已處理。

不一致或建議：
1. `detectDev()`（app.js:90）仍用 `/api/prompt?player=probe&persona=probe` 的 404 猜 dev。改用 `GET /api/resources` 回的 `dev`（loadConfig 已在呼叫它，順便設 `S.dev = !!r.dev`）。
2. 同意狀態只存 `lb_consent`（app.js:535-538）。請在勾選時 `POST /api/consent {player, version, accepted}`，並在進入頁用 `/api/profile` 回傳的 `consent` 還原；刪除資料後 consent 也已清空。後端不強制，閘門在前端。
3. 「靜音教練」（`S.muted`，app.js:602）只改前端。請 `savePrefs({mute_coach: S.muted})`；載入時從 `prof.prefs.mute_coach` 還原（app.js:200 的 prefsApplied 區塊目前只還原 severity / theme）。注意靜音時後端不會產生教練訊息，前端不用再過濾；若玩家取消靜音，之前被靜音的回合不會補出教練訊息。
4. 「我不舒服」（app.js:608）請同時 `savePrefs({severity:1, feel_uncomfortable:true})`；要取消時送 `feel_uncomfortable:false`。後端在 true 時會把教練尺度強制為 1。
5. 錯誤判斷靠訊息字串：`/ended|locked/`（app.js:392）。目前後端訊息是 `session ended; flags are locked`，可用，但屬脆弱契約；若要穩定請告知，後端可加 `code` 欄位（例如 `{"error":..., "code":"session_ended"}`）。
6. 前端在 `detectDev` 前會對不存在的 persona 打 /api/prompt；GAME_DEV 下回 400（不是 404），已不影響判斷，但改用 resources.dev 後可移除。
7. `role:"player"` 且 `meta:true`（問 AI 身分）的訊息沒有 `kind`，若有依 kind 上色的程式請容許 undefined。
8. 正式模式下 `hour`、`reveal` 會被後端忽略（不報錯），前端 devOpts 已只在 S.dev 時送，沒有問題。
