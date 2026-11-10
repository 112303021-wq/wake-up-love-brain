# Prompt 對後端的需求（未改 engine/）

1. 真誠詢問「是不是 AI」時模型會回 `break_character=true`。safety.py 的 `model` 類別訊息是「我們先暫停一下遊戲」，語氣偏通用；建議新增 `ai_identity` 類別或讓 `model_text`（模型的 reply）顯示在安全畫面。若不想採此政策，請告知，我會把 AI 身分句改回「不承認 AI」。
2. `break_character=true` 時 prompt 要求 `red_flags=[]`。確認 game.py 在此情況不計分、不顯示紅旗（目前看 game.py:114 會先處理 break_character，應無問題）。
3. `ClaudeLLM.generate` 用 `reply_schema` 的 enum 限制 red_flags 為 `persona.flag_codes`。愛情騙子現在 md 內有代碼表，personas.json 的 `flag_codes` 已重複，可擇一保留；md 多了 `pressure_urgency`。
4. 渣男渣女移除 `body_criticism` 後，若有其他地方（結算頁文案）引用該代碼請一併移除。
5. safety.py 規則尚無「玩家要求暫停／退出／停止」的關鍵字（只有「太痛苦」）。prompt 已要求模型對此回報 break_character；建議關鍵字層加「暫停|不玩了|退出|停止遊戲」之類，並避免誤判「停止聯絡」等劇情用語。
6. 若要用 `time_context`：愛情騙子與焦慮型 prompt 目前不特別使用，無需處理。
