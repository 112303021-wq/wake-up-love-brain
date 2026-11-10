import os

# 既有測試會呼叫 /api/prompt 等開發功能；預設開啟。要測「正式模式」的測試自行 monkeypatch.delenv。
os.environ.setdefault("GAME_DEV", "1")
os.environ.setdefault("GAME_QUIET", "1")

# 舊的測試不帶 token、用短 ID；要測正式行為的測試自行 monkeypatch.setenv 成預設值（見 test_auth.py）
os.environ.setdefault("GAME_REQUIRE_TOKEN", "0")
os.environ.setdefault("GAME_MIN_ID_LEN", "1")
os.environ.setdefault("GAME_RATE_PER_MIN", "0")
os.environ.setdefault("GAME_AUTH_FAIL_PER_IP", "0")   # 既有測試會連續送很多錯誤憑證；節流測試自行設定
os.environ.setdefault("GAME_AUTH_FAIL_PER_ID", "0")
os.environ.setdefault("GAME_NEW_PER_IP_HOUR", "100000")
