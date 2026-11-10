# 後端 B 第 2 輪變更紀錄（第 3 輪後 pytest 331 通過）

| Q | 狀態 | 做了什麼 / 未解原因 |
|---|---|---|
| Q5 並發 | 已解 | `Store.lock(pid)` 每玩家一把 RLock，start/send/flag/review/reset/nickname 整段 load-modify-save 都在鎖內；存檔改同目錄唯一暫存檔 + fsync + os.replace。測試：同人格 5 並發、跨人格、並發寫檔。限制：僅單一 process 有效，多 worker 需換 SQLite 或檔案鎖。 |
| Q24 損毀存檔 | 已解 | 壞 JSON 或結構不對 → 改名 `<id>.json.corrupt-時間戳-pid`，開新局，不再 500。 |
| Q10 隱私 | 部分 | 已做：ID 嚴格白名單、`DELETE /api/profile` 與 `POST /api/profile/delete`（連隔離檔一起刪）、危機原文不入庫（存遮蔽字串）。未做：首頁告知同意（前端）、保存期限、saves/ 權限與 .gitignore（非我負責檔案）、既有含真名存檔未處理。 |
| Q12 ID 無認證 | 部分 | 只統一白名單；簽發 ID、cookie、速率限制未做（需前端配合）。 |
| Q7 injection | 部分 | 歷史以 `<history>` 包住、單行化、`<>` 全形、模板單次替換（玩家的 `{stage}` 不再被二次展開）；4 種注入測試。未做：輸出端外洩偵測、user message 仍是玩家原文、結構化 messages。 |
| Q8 LLM 驗證 | 大部分已解 | `validate_output`（型別、空 reply、長度 300、紅旗限人格代碼表且 ≤2）、容忍 ```json 框、失敗重試 1 次、再失敗用無紅旗 fallback，不丟回合、不回 400、錯誤不外洩；max_tokens 4000→600；紅旗代碼表單一來源 md。未解：紅旗真值仍由模型自評（需劇本表設計）；ClaudeLLM 仍未用真 key 實測；無 timeout 設定。 |
| Q11 HTTP | 已解 | 非 dict、壞 JSON、非 application/json、body>32KB、hour/severity/欄位型別錯、缺欄位全部 400 JSON；未預期例外回 `{"error":"server error"}` 只寫 log；加 nosniff。未做 Origin/token CSRF（Content-Type 限制已擋簡單跨站表單）。 |
| Q13 開發功能 | 已解 | reveal、hour、/api/prompt 只在 `GAME_DEV=1`。 |
| Q21 補標/偷看 | 已解 | 結束或結算後 flag 回 400；局中 review 需 `finish:true`（會結束該局）。未做：重玩嘗試編號。 |
| Q23 choice_id | 已解 | 必須符合 `s{當前階段}_{有效索引}`，負索引/跨階段/非字串全拒；money 選項每局同 id 只計一次；leave 以當前階段判斷。 |
| Q6 prompt 檔 | 已解 | 啟動時一次列出所有缺失檔案並結束；紅旗表缺失、mock 紅旗不在表內也在載入時報錯。 |
| Q2/Q3 傳 kind | 部分 | game 已記錄 kind/source/reply_to_kind/kind_counts，並以相容方式傳 coach；scoring 端待後端 A 採用（見 backend_b_requests.md）。 |
| Q9 neutral/shuffle | 已解（後端） | `Persona.choices(stage, seed)` 在 shuffle 時併入 neutral，以局為種子固定排序；neutral 不計 brain/awake。 |

## UI / Prompt 需求
| 項目 | 狀態 |
|---|---|
| 4 coach severity | 已做 |
| 5 stage_total | 已做 |
| 6 逐句覆盤 msg_id/stage/player_reply | 已做（game 補欄位） |
| 7 flags_caught_so_far | 已做（另有 flags_reported） |
| 8 color/description/difficulty | 已做（預設值在 personas.py，json 可覆蓋；difficulty 暫定） |
| 9 /api/resources | 已做 |
| 10 prefs | 已做 |
| 1 小測驗 / 2 徽章 / 3 互助會 | 未做：題庫、徽章規則未定義；互助會本輪不處理 |
| Prompt 1 ai_identity 類別 | 未做：safety.py 屬後端 A；模型 reply 已存進 safety 回應的 `model_text` |
| Prompt 2 break_character 不計分 | 已確認：break 時結束局、不新增 NPC 訊息、紅旗清空 |

## 第 3 輪：整合後端 A
| 項目 | 狀態 |
|---|---|
| safety.assess / response(severity) | 已整合。ends_session=false（low）不終局，回 `notice` 並寫入帶 `safety` 的 system 訊息；Safety 物件帶 category/severity/ends_session |
| ai_identity | 已做：獨立回覆、不終局、不計分（提問存成 `meta_player`，不進計分）、不呼叫 LLM；模型 break_character 且玩家原文為 ai_identity 走同一條 |
| pause / too_painful | 終局但保留存檔，新增 `POST /api/resume` 與 state.`can_resume`；其他類別不可 resume |
| scoring.resolve_kind / money_in_text | 已用。game.classify 改為薄包裝；neutral 選項固定 neutral；自由輸入戀愛腦抽金額（事件含 source 欄位） |
| severity 預設 | send / review / server 預設改 coach.DEFAULT_SEVERITY(1) |
| API 契約 | 已寫 docs/api_contract.md |
| 整合測試 | test_game_flow.py、test_server.py 新增 8 項 |
| 已知 | safety.assess 對「我朋友說他想自殺，我不知道怎麼辦」誤判為 real_violence/high，已寫入 backend_b_requests.md 給後端 A |

## 第 4 輪
| 項目 | 狀態 |
|---|---|
| `dev` 旗標 | `GET /api/resources` 回 `dev: bool` |
| 同意紀錄 | `POST /api/consent`（version/accepted/ts 存進 profile.consent）；profile 回傳 consent；刪除資料一併刪；不強制 |
| prefs 擴充 | `mute_coach`、`feel_uncomfortable`（嚴格 bool）；靜音時不產生教練訊息仍計分；不舒服時教練尺度強制 1 |
| 前端對照 | 列在 docs/backend_b_requests.md「第 4 輪」 |
| 測試 | pytest 361 通過 |

## 第 5 輪（pytest 全過）
| 項目 | 狀態 |
|---|---|
| Q31 模型拒答 | 已解：break_character 且玩家原文無 safety 觸發 → 不終局、不顯示熱線、不帶紅旗 fallback 續局並寫 log；測試含開場拒答 |
| Q36 / Q12 token | 已解（後端）：首次建立簽發 token（只存 SHA-256），寫入／刪除／讀 profile 需 `X-Player-Token` 或 body token；ID 最短 8（GAME_MIN_ID_LEN）；總量上限 GAME_MAX_PLAYERS；每玩家速率 GAME_RATE_PER_MIN；失敗請求撤銷新 token；舊存檔可認領；token 遺失=換新 ID＋管理者 X-Admin-Token 刪除＋保存期限清理。待前端接 |
| 錯誤 code | 已解：所有錯誤回應含 code，清單在契約 |
| Q28 mock_clean_lines | 已解：MockLLM 約 1/3 回合用 clean line（種子=該局 created_at，可重現），欄位缺失容錯；`neutral_pool` 抽 1~2 個混入選項（3~4 個） |
| Q35 resume | 已解（後端）：too_painful 需 confirm、10 分鐘冷卻、每局 3 次上限，記錄 safety_events。未做：safety 狀態跨人格（切人格即可繞過，需產品/研究決定處置流程） |
| Q42 隱私 | 部分：觸發 safety 的原文一律不入庫；Store.purge_older_than 與環境變數 GAME_RETENTION_DAYS（啟動時清理）。未做：saves/ 現有三個舊檔未處理（不在我的檔案範圍，請人工刪或啟用保存期限）、.gitignore、目錄權限 |
| Q43 訊息成長 | 已解：ai_identity 每局只記 5 次、resume 3 次上限、每玩家速率限制 |
| Q45 | 部分：移除零寬／雙向字元、玩家文字冒號換小冒號避免同行偽造發言；輸出端攔截網址／長數字／錢包／紅旗代碼外洩。未做：prompt 片段相似度比對 |
| Q22 | 未做：prompt 快取結構／預設模型屬 prompt 與經費決策 |
| Q18 離開關鍵字 | 已解：`wants_leave` 排除否定、疑問與「我走了一圈」 |
| Q16/Q17/Q25/Q27 | 未做：需真 LLM key／LINE 設計／黏著度需求／環境（非我的檔案） |

## 第 6 輪（pytest 691 通過）
| Q | 狀態 | 說明 |
|---|---|---|
| Q47 補標寬限 | 已解 | 自然結束後、review 前可補標；review 後或 safety 終止才鎖；結束時不再自動公開答案。60 局驗證最佳策略 recall 100%（tests/test_round6.py） |
| Q49 fallback | 已解 | 只用該階段 mock_clean_lines，無紅旗；無 clean line 用中性句；五人格測試 |
| Q50 舊存檔 | 已解 | 預設不可讀寫認領；管理者 `/api/admin/migrate` 遷移或刪除；`GAME_ALLOW_LEGACY_CLAIM=1` 才可認領。saves/ 內 3 檔未動 |
| Q52 | 已解 | 授權先於玩家速率限制；不存在／無 token／token 錯／舊檔一律 401 同訊息；新增來源 IP 速率限制。限制：IP 取 TCP 來源，反向代理後需另處理 |
| Q53 | 已解 | 每 IP 每小時新建上限＋總量上限，單一來源無法灌滿；admin header 以 bytes 比對，非 ASCII 回 401。未做：預留名額給已知來源（以 IP 限制取代） |
| Q57 | 已解 | wants_leave 重寫並參數化測試 16 組 |
| Q56 | 大部分已解 | NFKC＋去零寬、日期時間白名單、全形網址／dot com／短網址／@handle／電話／帳號。不同意見：紅旗代碼名（如 guilt_trip）出現在 NPC 回覆仍視為洩漏而攔截；`I love u.io`、`Mr.me` 放行 |
| Q46 | 後端部分已解 | clean line 每 3 回合固定 1 回合、同局不重複、用完才回一般台詞；題材與長度仍由 Prompt 補 |
| Q48 接線 | 已解（接線） | `Game.install_safety_classifier`、`make_safety_classifier`（未實測）、GAME_SAFETY_LLM=1 啟動接線；介面缺失時安全降級；假 classifier 測試。coach 以 `last_npc_has_flags` 關鍵字相容傳入 |

## 第 7 輪（pytest 752 通過）
- 接線修正：game.py 改傳 `has_red_flag`（原誤傳 `last_npc_has_flags`，被 `_call_compat` 靜默略過，Q40/Q55 之前實際沒生效）；移除 coach 不認得的 `kind_source`。
- `_call_compat` 被略過的參數會 log 警告；測試證明 game 的呼叫點（coach.interject、scoring.compute）沒有任何被略過的參數。
- 整合測試（tests/test_coach_wiring.py）：無紅旗 NPC 句 + awake → tone=neutral（5 人格、選項與自由輸入）；有紅旗 → praise。test_game 的「awake 一律 praise」斷言放寬為 praise 或 neutral。
- safety.set_classifier：`install_safety_classifier` 呼叫的是後端 A 的 `safety.set_classifier(fn)`，簽章吻合；假 classifier 端到端：規則不觸發 → classifier 回 self_harm/high → 局終止且原文不入庫；low → 只有 notice；分類器丟例外或回傳格式不對 → 遊戲照常。
- tone 'neutral' 已寫入 api_contract.md。

## 第 8 輪
- state 新增 `reviewed:bool` 與 `phase`（playing / final_check / locked）；舊存檔缺 `reviewed` 時視為 false，phase 依 ended / safety 推斷；測試 4 項；契約已更新並列出前端配合項。

## 最後一輪（pytest 760 通過）
| Q | 狀態 | 說明 |
|---|---|---|
| Q64 | 已解 | 每 IP／每 ID＋IP 的錯誤憑證滑動視窗節流（429），admin 路由套 IP 限速與失敗節流，token 長度 16–256 驗證，admin 動作寫 log（只記 ID 雜湊），啟動時 GAME_ADMIN_TOKEN <16 字元警告 |
| Q63 | 已解 | GAME_NEW_PER_IP_HOUR 預設 200；GAME_MAX_PLAYERS 維持 2000（小組遠低於）；README 與契約說明，前端提示文案列入契約 |
| Q65 | 已解 | README 重寫（Python 3.9+、環境變數表、../personas 依賴、token／隱私、safety 限制只放連結與提醒、檢查清單） |
| Q66 | 已解 | 契約全文統一：沒有 403，所有授權失敗 401 unauthorized |
| Q70 | 部分 | 已新增 .gitignore；`.DS_Store` 與 `.pytest_cache` 刪除指令被權限系統拒絕，未刪（可手動刪，已在 .gitignore）；saves/ 未動 |
| Q69 | 已解 | 存取 log 不再記 query string |
