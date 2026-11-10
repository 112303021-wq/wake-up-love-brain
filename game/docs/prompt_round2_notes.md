# Prompt 第 2 輪：給後端 B 的格式說明（backend_b_requests.md 尚未存在，故寫在這裡）

## 1. recent_history 分隔格式（Q7）
五份 prompt 都已寫明：`{{recent_history}}` 會被替換成

```
<history>
玩家：...
角色名：...
</history>
```

- 請由後端在替換時加上 `<history>` 與 `</history>`（prompt 內 `{{recent_history}}` 本身不含標籤，避免重複包）。
- 每行格式維持「角色：內容」。
- 請跳脫玩家文字中的 `<history>`、`</history>`（例如替換成全形 `＜history＞`），並把換行壓成單行或縮排，避免偽造段落。prompt 已說明假標籤仍視為玩家文字，但後端跳脫是第一道防線。
- 若日後改成結構化 messages，這段規則仍適用，只需把標籤保留在 user 區內容。

## 2. 選項資料（Q9）
- `choices` 欄位與 kind 不變（仍恰好 brain/awake 各一，現有測試 `== {"brain","awake"}` 與 `len==2` 照過）。順序已預先打散。
- 新增欄位 `neutral_choices`（每人格每階段 1 個，kind=`neutral`，另有 `note`）與 persona 層級 `shuffle: true`。
- engine 目前不讀 `neutral_choices`。建議 `Persona.choices(stage)` 在 `shuffle` 為真時合併 `choices + neutral_choices` 後以玩家／局為種子的亂數排序；`TRUST_DELTA` 已有 neutral。合併後測試 `test_persona_has_lines_choices_flags_every_stage` 與 `len(st["choices"]) == 2` 需同步改（我沒有動 tests）。
- 計分：neutral 不應計入 brain/awake 次數；若玩家對 neutral 訊息按紅旗，應算誤檢舉（對照 Q2/Q3）。
