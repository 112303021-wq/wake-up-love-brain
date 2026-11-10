# 後端 A 對後端 B（game.py 等）的需求

後端 A 只改了 safety.py / scoring.py / coach.py，全部向下相容，現有 game.py 不改也能跑（pytest 全過）。
以下是要發揮完整效果時，game.py 需要配合的地方。

## 1. safety：改用 assess()，才有降級與 ai_identity

目前 game.py 用 `safety.check(text)`，它只會對「需要終局」的類別回傳（self_harm、real_violence、real_scam、minor、too_painful、pause），
第三人稱／小說／誇飾（severity=low）與 ai_identity 都回 None，所以玩家不會被誤終局，但也看不到溫和提醒與 AI 身分回覆。

建議流程：

```python
hit = safety.assess(text)           # None 或 {category, severity, ends_session, context}
if hit:
    resp = safety.response(hit["category"], severity=hit["severity"])
    if hit["ends_session"]:         # severity high / medium
        state["ended"] = True
        state["safety"] = resp
        save; return
    # severity low 或 info：不終局。把 resp 放進本回合回傳（例如 state["notice"] = resp，
    # 或加一則 role=system 訊息），然後繼續正常流程。
    #   low  -> 溫和提醒＋資源，玩家可繼續玩
    #   info -> ai_identity：如實說明是 AI，不計分，不當危機
```

- `safety.respond(text)` 是 assess + response 的捷徑。
- 回傳 dict 新增 `severity`（high/medium/low/info）與 `ends_session`；舊欄位不變。
- 模型回 break_character 時：`safety.response("model", out.get("reply", ""))`（severity=medium，仍終局）。
  若模型是回應「是不是 AI」，建議 game.py 判斷用 `safety.assess(player_text)` 是 ai_identity 時改走 `response("ai_identity")` 且不終局。
- 新類別：`pause`（玩家要求暫停／退出／停止）、`ai_identity`。前端要處理這兩個 category 的文案與是否顯示資源（ai_identity 的 resources 是空陣列）。
- Q14 的「觸發後保留進度、可回到遊戲」需要 game.py 支援（例如 pause 後允許 resume）；safety 這邊只提供 `ends_session` 旗標。

## 2. scoring：自由輸入用 resolve_kind 與 money_in_text

game.py 目前自己有 `classify()` 和 `_AWAKE/_BRAIN` regex（Q3 的來源）。請改成：

```python
kind = scoring.resolve_kind(chosen_kind, text)     # 有 kind 用 kind，沒有才用規則
if not choice_id:                                  # 自由輸入也抽金額
    money = scoring.money_in_text(text) if kind == "brain" else 0
```

- `resolve_kind` 只回 brain / awake / neutral。選項的 kind 一律優先。
- `money_in_text("我轉你3萬")` = 30000；有轉帳意圖沒講金額回 `DEFAULT_FREE_TEXT_AMOUNT`（5000）；「我不轉3萬」回 0。
- `scoring.compute(state)` 現在會讀 `state["player_turns"]`（已有）；沒有也會從 player 訊息推算。
- 計分輸出新增 `detect_score`、`behavior_score`，舊欄位保留。
- 對照題：計分已會因誤檢舉扣分，但 mock 台詞幾乎每句都有紅旗（Q9、Q2），需要 Prompt 工程師補「無紅旗」對照台詞，precision 才有鑑別力。
- 等級名稱「戀愛腦末期」仍保留，因為 tests/test_game.py 斷言它。教練對外已改顯示「這局對方很會」。
  若要改名，請同步改 scoring.GRADES 與 test_game.py 的 `grade == "戀愛腦末期"`。

## 3. coach：預設尺度與參數

- coach 預設尺度是 1（溫柔），`severity` 傳 None 或不合法值都會變 1。
- game.py 的 `send(... severity=2 ...)` 與 `review(... severity ...)` 預設值還是 2，請改成 1（`coach.DEFAULT_SEVERITY`），否則預設仍是毒舌。
- `coach.interject` 簽名不變；不再把玩家原話嵌進教練句子。
- 前端（Q4）：地獄尺度需要二次確認與說明；`static/app.js` 預設值 `lb_sev` 要改 1。

## 第 6 輪：給後端 B 的接線需求

### 1. 第二道分類器（Q48，預設關閉）
```python
from engine import safety
safety.set_classifier(fn)    # fn(text) -> None 或 {"category": <safety 類別>, "severity": "high|medium|low|info"}
safety.set_classifier(None)  # 關閉（預設）
```
- 只有規則層「沒觸發」或「只有 low」時才呼叫 fn；fn 例外或格式錯誤一律當作沒事，不會中斷遊戲。
- `assess()` 的回傳 `context == "classifier"` 代表來自分類器。
- 建議在 server 啟動時：`if os.environ.get("GAME_SAFETY_LLM") == "1": safety.set_classifier(你的_llm_分類函式)`。
  函式要自己處理逾時與隱私（送出前提示使用者同意）。本機免費選項：`safety.set_classifier(safety.heuristic_classifier)`，
  它只在「第一人稱 + 多個絕望線索」時回 self_harm/low（只提醒不終局），不是完整偵測。

### 2. 入戲轉帳（Q48）
- `safety.assess("我剛剛匯了五萬到你的帳戶")` 現在是 None（含「你」的轉帳敘述視為對 NPC 說話）。
- `scoring.classify_text` 同句為 brain、`scoring.money_in_text` 為 50000，game.py 既有流程就會記成 money_event。
  請確認 game.py 對 `kind=="brain"` 且 `money_in_text(text)>0` 的自由輸入一律記 money_event（不論有沒有 choice_id）。

### 3. Q51：自然回覆與 neutral
- `classify_text` 對「謝謝你，我也覺得跟你聊天很開心」「嗯嗯我了解，我們先這樣安排」回 neutral（不再是 brain）。
  「沒關係、都可以、你開心就好」這類無條件讓步仍是 brain。
- scoring 的行為分新增正向項：對「沒有紅旗」的 NPC 訊息做中性回應，算 `NORMAL_CREDIT=0.5` 個回合的得分。
  需要 state["messages"] 內 player 訊息帶 `kind`（現有）、npc 訊息帶 `red_flags`（現有）。

### 4. Q40/Q55：教練要知道對方這句有沒有紅旗
`coach.interject(..., turn=0, has_red_flag=None)` 新增關鍵字參數：
- `has_red_flag=False`：玩家拒絕（kind=="awake"）時不稱讚，回 `{"tone": "neutral", "text": ...}`。
- `True` 或 `None`（預設）：維持舊行為（稱讚），所以不傳也相容。
- 建議 game.py：`has_red_flag=bool(last_npc and last_npc.get("red_flags"))`。注意 tone 多了 `"neutral"`，前端要能顯示。
  這會讓 test_game 內「awake 一律得到 praise」的斷言在 mock 遇到無紅旗句時不成立，請 B 調整該測試或固定種子。

## 第 7 輪：Q67 前端／後端 B 需求
- 教練對拒絕的回饋文字已不隨「對方有無紅旗」變化；但 `tone` 仍是 `praise`（對方有紅旗或未告知）或 `neutral`（`has_red_flag=False`）。
  請前端把兩者渲染成完全一樣，或由 game.py 序列化時把 `neutral` 一律改成 `praise`（會影響 tests/test_coach_wiring.py 的 neutral 斷言，需同步改）。
  否則玩家可以用 tone 反推答案，Q67 的洩題就沒有真正解決。
