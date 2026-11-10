# 質疑者 第 4 輪（Q60 起）

範圍：第 6、7 輪修復後（pytest 756 項全過，Python 3.9.6）。只讀；暫存在 `/private/tmp/claude-501/q/`（s5.py 盲測語料、s6.py 計分策略、v3.py／v6.py 授權攻擊）。未動 `saves/`。

## A. 第 3 輪 Q46–Q59 驗證狀態

| 題 | 狀態 | 本輪證據 |
|---|---|---|
| Q46 mock 無紅旗句固定、可辨識 | 部分 | 每階段每人格 8 句 clean、每 3 個 NPC 回合恰 1 句，規律仍在。但嘗試「依 flag 回饋推第三句」的策略 C 只拿 20–39 分，未成為有效刷分。見 Q67（教練色調洩漏）。 |
| Q47 最後一則不能標旗 | 已解 | 自然結束進入 `final_check`，可補標；oracle 策略各人格 84–87。 |
| Q48 safety 對新語料泛化差 | 未解 | 第三批盲測整體召回 27%、自傷 16%。見 Q60。 |
| Q49 fallback 取走真紅旗句 | 已解 | fallback 只用 clean 句（前輪驗證沿用，本輪策略 A 未再出現標對被扣）。 |
| Q50 舊存檔認領 | 已解 | 舊存檔無 token：GET/POST 皆 401；攻擊者無法搶 token；真實 `saves/` 三個舊檔未被改動。 |
| Q51 自由文字自然回覆拿不到滿分 | 已解 | 紅旗句拒絕＋正常句自然中性＋oracle 標旗：84–87（高於第 3 輪的上限 73–82）。 |
| Q52 速率限制攻擊他人／存在性 oracle | 已解 | 匿名對受害者 ID 連打 70 次全 401，受害者帶 token 仍 200；存在與不存在 ID 都回 401。 |
| Q53 配額灌爆／admin 非 ASCII 500 | 部分 | 非 ASCII header → 401，不再 500（已解）；同 IP 輪換 ID 只成功 18 個（受每 IP 每小時 20 限）。但新副作用見 Q63，admin 無節流見 Q64。 |
| Q54 safety per-session | 未解 | 自傷終局後，同玩家 `start` 另一人格立即 `ended=False`；`reset` 後可再玩。 |
| Q55 教練稱讚正常句拒絕 | 本輪未重驗 | 無獨立證據，僅見 changelog 宣稱。 |
| Q56 輸出過濾誤殺／繞過 | 本輪未重驗 | 同上。 |
| Q57 wants_leave 雙向錯誤 | 本輪未重驗 | 同上。 |
| Q58 resume confirm／mtime 保存期限 | 本輪未重驗 | 同上。 |
| Q59 教練文案殘留 | 本輪未重驗 | 同上。 |

## B. 三批 safety 語料比較

| 批次 | 句數 | 結果 |
|---|---|---|
| 第 2 輪（我） | 約 201 | 修前 48 句不符，修後 0（之後被拿去調規則，已污染） |
| 第 3 輪（我） | 約 150 | 危機召回約 20%，自傷 1/46；A 隨後針對這批調到 88% |
| 後端 A 自寫 | 159 | 未調 49%（自傷 46%）；調後 98% |
| 第 4 輪（我，全新） | 202（與 s2/s4/tests 查重，無重複） | 危機 109 句：終局 29 句 = 召回 27%；自傷 10/62 = 16%；暴力 5/14；現實詐騙 6/19；未成年 8/14；非危機 70 句誤終局 7 句 = 10% |
| 第 4 輪＋`heuristic_classifier` | 同上 | 無任何差異（召回 27%、誤終局 10% 不變） |

趨勢：每換一批新語料，召回回到 20–30%。規則對「寫過的句子」有效，對「沒寫過的」沒有泛化。A 自評的 49% 偏樂觀；`safety_limits.md` 的「大約一半到八成」與實測 27% 不符。

## C. 新問題（按嚴重度）

### Q60【高】safety 對全新語料召回只有 27%，自傷 16%；文件寫「一半到八成」
- 證據：`s5.py -v`。漏判類型：隱晦黑話、台語、中英混用、長句脈絡的自傷幾乎全漏。`docs/safety_limits.md` 第 8 行「大約一半到八成，不保證」。
- 重要：使用者測試必然有玩家打出規則沒寫的說法，系統會照常讓 NPC 回話。文件高估會讓小組放鬆人工監看。
- 另：`heuristic_classifier` 預設關閉，`server.py` 只在 claude 模式接線（約第 340 行）。mock 模式的使用者測試只靠規則。且它在本批 202 句上沒有增益。
- 建議：後端 A 把 safety_limits 改成實測數字（約 27%，自傷 16%）；研究／組長把「安全網」改為流程（全程有人在場、測試前說明）而非程式。

### Q61【高】誤終局 10%，且常是日常或入戲語句
- 證據：誤終局 7 句：「這蛋糕甜到要死」「活動超好玩，我笑到要死」「我想消失三天去山上露營」「我決定不再喝酒了，真的好痛苦戒酒」「我剛刷卡幫你付了保證金」（入戲）「我弟被網友騙了三萬，我在陪他處理」「我在寫論文，主題是青少年自殺防治」。
- 重要：會把玩家鎖進 🆘 並結束整局；大學生測試的語氣誇飾很常見，會直接破壞測試體驗，並讓玩家覺得系統「不懂人話」。與 Q60 一起看：漏的多、錯殺的也多，兩邊都不準。
- 建議：後端 A 對 hyperbole（要死／死了）、陪伴他人（我弟／朋友）、研究主題加反例；遊戲內「入戲」轉帳語句不應走 real_scam 終局。

### Q62【中】前端仍自行推斷 phase，與 api_contract 第 8 輪補充衝突
- 證據：`static/app.js` 355–360 行 `phaseOf()` 用「所有 NPC 訊息都帶 red_flags」推斷已結算；`api_contract.md` 179 行寫明「前端不要再用此推斷」，並新增 `phase`／`reviewed`。後端回應（v3 輸出）已含 `phase`、`reviewed`。
- 推論（未在瀏覽器實測）：自然結束後玩家把每則 NPC 訊息都標了旗，`phaseOf` 會判成 `done`，不顯示「最後確認」卡片，按鈕變成不經確認的「看結算」。GAME_DEV reveal 亦可能干擾。
- 建議：前端改用 `st.phase`。

### Q63【中】每 IP 每小時只能建 20 個新玩家：教室／同一 Wi-Fi／反向代理後會卡人
- 證據：`server.py` 約 242–256 行 `GAME_NEW_PER_IP_HOUR` 預設 20，每 IP 每分鐘 300。用 `client_address[0]`，不看 X-Forwarded-For。小組若在同一區網或經 ngrok／反向代理，所有人共用 IP。
- 重要：第 21 位受測者會看到 `quota_exceeded`「目前無法建立新玩家」，而且他看到的是前端文案，不知道怎麼辦。
- 建議：README／測試手冊寫明要調高 `GAME_NEW_PER_IP_HOUR`；前端對 quota_exceeded 提示聯絡主持人。

### Q64【中】admin migrate／刪除端點沒有節流與長度要求
- 證據：`v6.py`：對 `/api/admin/migrate` 連續 500 個錯誤 token 全回 401，無延遲、無鎖定（該路由在 `_guarded` 之外，不受 IP 限速）。`GAME_ADMIN_TOKEN` 沒有最小長度檢查。admin header 用 `DELETE /api/profile` 可刪任何人的存檔，且沒有稽核 log。
- 好的部分：未設環境變數時一律拒絕；比對用 `compare_digest`；非 ASCII 不 500；已有 token 的存檔不能被重複遷移；token 沒進 log、回應與存檔明文，`token_hash` 不外洩。
- 建議：admin 路由也套 IP 限速；啟動時若 token 少於 16 字元就警告；admin 動作寫 log（不含 token）。

### Q65【中】README 過期且與實況不符
- 證據：README 最後修改 Oct 15；寫「需要 Python 3.10 以上」，但 3.9.6 下 756 項測試全過，伺服器可啟動（`from __future__ import annotations` 已加，僅 `engine/__init__.py` 沒有但不需要）。沒有提到 token 授權、`GAME_DEV`、`GAME_ADMIN_TOKEN`、`GAME_NEW_PER_IP_HOUR`、`GAME_RETENTION_DAYS`、safety 限制、同意書。
- 另：遊戲依賴上層 `../personas/*.md`（`engine/personas.py` 第 16 行），單獨複製 `game/` 資料夾會直接報錯，README 沒說。
- 建議：後端 B 更新 README；改為「Python 3.9+」；列環境變數表與目錄依賴。

### Q66【低】文件互相矛盾
- `api_contract.md` 錯誤 code 表仍列 `unauthorized`＝缺 token、`forbidden` 403＝token 不符；同檔 134 行寫「不再有 403 forbidden」。
- 「前端需配合的變更」第 1 點仍寫「收到 401/403」。
- `safety_limits.md` 的 49–80% 與實測不符（見 Q60）。

### Q67【中】教練色調洩漏：永遠拒絕＋事後只標被稱讚的句子也能拿 60–67 分
- 證據：`s6.py` 策略 B（每回合選拒絕，事後只標教練稱讚過的 NPC 句）五個人格 60–67；基準 oracle 84–87。差距只有約 18–25 分，且 B 完全不需要辨識紅旗。
- 其他策略（皆未超過基準）：D 全程自然中性＋oracle 標旗 60；E 全程中性、最後確認全標 16；F 反向（紅旗順從、正常拒絕）10–51；G 隨機一半拒絕 64–69；H 順從但不匯款 45–52；I 反覆 pause/resume 後 oracle 84–88（resume 沒有加分）；C 區塊配額推論 20–39。最高分仍是合理策略（紅旗拒絕＋正常句自然回覆＋準確標旗）。
- 重要：玩家看教練對自己這一句的反應，就能反推 NPC 那句是不是紅旗，變成「標旗」這一步的答案提示。
- 建議：教練對「拒絕」的回應不依 NPC 句是否紅旗而變色，或把標旗與教練回饋的時間點拆開。

### Q68【中】使用者測試只驗證 UI 與流程，不驗證 LLM 行為
- ClaudeLLM 路徑仍沒有任何測試或實跑（README 只寫「之後接」）。mock 的 clean 句每階段 8 句，玩三輪就會重複。若小組以 mock 結果推論「玩家學到什麼」，效度有限。
- 建議：研究端先寫清楚這輪測試的目的是可用性，不是學習成效。

### Q69【低】存取 log 含玩家 ID
- `GET /api/profile?player=<id>` 的 URL 會出現在 http.server 預設 log。token 本身不在 log（已確認），但 ID 是半個憑證，log 若被分享要遮蔽。

### Q70【低】檔案殘留
- `game/.DS_Store`（Oct 15）、`game/.pytest_cache`，沒有 `.gitignore`、沒有 `requirements.txt`（可不需要，但 README 要說明）。`saves/` 仍有 3 個 Oct 15/20 的舊存檔（`phnf3me8rsf.json` 等），是你之前的測試資料，交給小組前應先搬走或清空。目錄沒有 `.tmp`／備份檔殘留。

### Q71【低】前端其他檢查（正面）
- `static/app.js` 沒有任何 `innerHTML`／`outerHTML`／`insertAdjacentHTML`／`document.write`，暱稱與訊息皆以 `textContent`／`createTextNode` 渲染，未見 XSS。
- localStorage 讀、寫、移除都包 try/catch（30、31、104 行）。
- 錯誤處理以 `code` 判斷（`unauthorized`、`ended`、`locked`、`cooldown`、`resume_limit`、`not_finished`），與契約一致，但 `forbidden` 不在前端處理（後端也不再回傳）。

## D. 回報摘要

前 5 大問題：Q60（safety 27%、文件高估）、Q61（誤終局 10%，日常誇飾也鎖局）、Q63（每 IP 20 個新玩家的上限會卡住同網段的測試）、Q62（前端仍用舊推斷，與契約衝突）、Q67（教練色調洩漏標旗答案）。

未解題：Q48、Q54（未解）；Q46、Q53（部分）；Q55–Q59（本輪未重驗，共 5 題）；新題 Q60–Q71 共 12 題。

可否交付使用者測試：可以，但限定條件。授權、舊存檔、速率限制、XSS、Python 版本、啟動流程都過關，計分最高分仍是合理策略。條件：全程有人在場、事前說明遊戲不是心理支持、🆘 資源常駐、已取得知情同意、測試用 mock 並把目的定為可用性；測試前調高 `GAME_NEW_PER_IP_HOUR`、清空 `saves/` 舊檔、更新 README。不可交付給無人監看的公開使用，因為 safety 對新語料召回只有約 27%。
