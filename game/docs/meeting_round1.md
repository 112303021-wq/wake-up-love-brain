# 第 1 次會議紀錄（2026-11-08）

出席：協調者、使用者研究員、UI 設計師、Prompt 工程師、質疑者
輸入：questions_round1.md（27 題：高 9、中 15、低 3）、research/*、ui_backend_requests.md、prompt_backend_requests.md

## 決議

| 議題 | 對應 Q | 決議 | 負責 |
|---|---|---|---|
| Q6 引擎起不來 | Q6 | 已解決：焦慮型檔名已改，personas.json 已同步，pytest 37 過。新增啟動驗證（prompt 檔缺失時明確報錯）| 後端 B |
| 安全關鍵字漏判與誤判 | Q1, Q14 | 擴充自殺自傷、暴力、匯款、未成年、暫停退出、AI 身分類別；正規化空白與全半形；第三人稱與虛構語境降級為提醒而不終局；測試改為大量樣本 | 後端 A |
| 計分可刷 | Q2, Q3 | 清醒/戀愛腦改用選項的 kind 欄位，自由輸入才用規則；紅旗辨識加入「誤檢舉」懲罰（precision 要有對照題）；以多種策略的刷分腳本做回歸測試 | 後端 A（計分）+ 後端 B（game.py 傳 kind） |
| 並發寫入 | Q5 | 每位玩家一把鎖，包住整個 load-modify-save，存檔改原子寫入 | 後端 B |
| 教練罵人 | Q4 | 預設溫柔；毒舌與地獄需玩家主動開；只批評手法與選擇，不貶低人；低分結算不嘲笑；教練文案全面改寫 | 後端 A（coach.py）+ 前端（預設值） |
| prompt injection | Q7 | recent_history 以明確分隔與跳脫包起來，標示為不可信資料；玩家原文不得偽裝成系統段落 | 後端 B + Prompt 工程師 |
| LLM 輸出驗證 | Q8 | 解析失敗重試一次，仍失敗用安全 fallback，不丟回合；紅旗代碼限制在該人格代碼表 | 後端 B |
| 教育成效與洩題 | Q9 | 選項洩題：隨機排序、清醒選項去掉「詐騙」「165」等提示詞；加入正常訊息對照題；前後測納入研究計畫 | Prompt 工程師（選項）+ 研究員（前後測） |
| 伺服器輸入驗證 | Q11 | 錯誤 body 與參數一律回 400 JSON；只接受 application/json | 後端 B |
| 開發功能外露 | Q13, Q21, Q23 | reveal 與 /api/prompt 只在 GAME_DEV=1 開啟；局中禁止 review；結算後禁止補標；choice_id 必須屬於目前階段 | 後端 B |
| 存檔損毀與隱私 | Q10, Q24 | 損毀存檔隔離改名並重新開始；暱稱與對話保存告知寫入首頁；提供刪除我的資料 | 後端 B + 前端 |
| AI 身分政策 | 待定 | 暫時沿用統一版（真誠詢問就如實說明）。**待使用者確認** | 使用者 |
| 愛情騙子紅旗代碼雙來源 | prompt_backend_requests | md 為單一來源，personas.json 不再維護 | 後端 B |

## 不處理（本輪）

- LINE Bot 實作、暈船互助會社群、真 LLM 實測。
- 小測驗只定義題目，不實作。

## 第 2 輪分工與檔案所有權

- 後端 A：engine/safety.py、engine/scoring.py、engine/coach.py、tests 中對應檔
- 後端 B：server.py、engine/store.py、engine/llm.py、engine/game.py、engine/personas.py
- Prompt 工程師：personas/*.md、data/personas.json
- 研究員：docs/research/*
- 前端：第 3 輪等後端契約穩定後，套用 ui_backend_requests.md
