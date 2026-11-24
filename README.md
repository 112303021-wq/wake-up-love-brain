# 醒醒吧！戀愛腦

辨識依附／詐騙型態紅旗的教育文字 RPG。玩家與不同類型的 NPC 互動，練習在對話中看出紅旗，結束後由教練覆盤，並可用情境小測驗與成就持續練習。

## 功能

- **角色互動**：五種角色（迴避型、依賴型、焦慮型、愛情騙子、玩咖），逐回合對話。
- **覆盤與教練回饋**：結束後顯示清醒分數與紅旗標示。
- **情境小測驗**：從 22 題題庫抽 10 題，選答案與把握程度，確認後看解析。
- **我的成就**：19 枚徽章，進度由後端判定與保存。

## 快速啟動

需要 Python 3.9 以上；預設 mock 模式只用標準函式庫，不需安裝套件。

```bash
cd game
python3 server.py        # 打開 http://localhost:8000
```

執行測試（需先 `pip install -r game/requirements.txt`，Python 3.10+）：

```bash
cd game
python3 -m pytest -q tests
```

## 文件

詳細說明（環境變數、Claude 模式、資料與隱私、部署限制）請見 [`game/README.md`](game/README.md)；API 說明見 [`game/docs/api_contract.md`](game/docs/api_contract.md)。

## 目錄

- `game/`：伺服器、遊戲引擎、前端、題庫與測試
- `personas/`：角色設定
