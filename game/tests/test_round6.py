import json
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server as srv  # noqa: E402
from engine import safety  # noqa: E402
from engine.game import Game, GameError, wants_leave  # noqa: E402
from engine.llm import LLMOutputError, MockLLM, NPCRequest, fallback_output, validate_output  # noqa: E402
from engine.personas import load_personas  # noqa: E402
from engine.store import Store  # noqa: E402

PERSONAS = load_personas()


# ---------- Q47：最後一則 NPC 訊息可補標 ----------
@pytest.mark.parametrize("pid", list(PERSONAS))
def test_last_npc_message_flaggable_in_all_60_games(pid, tmp_path):
    flaggable_last = 0
    for seed in range(1, 13):
        g = Game(PERSONAS, Store(tmp_path / f"{pid}{seed}"), MockLLM(seed))
        g.start("player01", pid)
        for _ in range(16):
            st = g.send("player01", pid, text="我不要再繼續了，再見了，我們分手")
            if st["ended"]:
                break
        sess = g.store.load("player01")["sessions"][pid]
        assert sess["ended"] and not sess.get("reviewed")
        # 答案在結算前不公開
        assert not any("red_flags" in m for m in st["messages"] if m["role"] == "npc" and not m["flagged"])
        # 最佳策略：把所有有紅旗的 NPC 訊息都標起來（含最後一則）
        for m in sess["messages"]:
            if m["role"] == "npc" and m.get("red_flags"):
                assert g.flag("player01", pid, m["id"])["correct"]
        last = [m for m in sess["messages"] if m["role"] == "npc"][-1]
        flaggable_last += bool(last.get("red_flags"))
        scores = g.review("player01", pid)["scores"]
        if scores["flags_total"]:
            assert scores["recall"] == 100 and scores["false_positives"] == 0
    # 結算後才鎖
    with pytest.raises(GameError) as e:
        g.flag("player01", pid, 1)
    assert e.value.code == "locked"


def test_safety_ended_session_flags_locked(tmp_path):
    g = Game(PERSONAS, Store(tmp_path), MockLLM(0))
    st = g.start("u1", "avoidant")
    g.send("u1", "avoidant", text="我真的不想活了")
    with pytest.raises(GameError) as e:
        g.flag("u1", "avoidant", st["messages"][0]["id"])
    assert e.value.code == "locked"


# ---------- Q49：fallback 只用 clean line ----------
class Failing:
    name = "f"

    def generate(self, req):
        raise ConnectionError("x")


def test_fallback_uses_only_clean_lines_never_flagged_lines(tmp_path):
    for pid, p in PERSONAS.items():
        g = Game(PERSONAS, Store(tmp_path / pid), Failing())
        g.start("u1", pid)
        for _ in range(4):
            g.send("u1", pid, text="今天好累")
        sess = g.store.load("u1")["sessions"][pid]
        flagged_lines = {l["text"] for ls in p.lines.values() for l in ls}
        clean = {t for v in p.cfg["mock_clean_lines"].values() for t in v}
        for m in sess["messages"]:
            if m["role"] == "npc":
                assert m["red_flags"] == [] and m.get("fallback")
                assert m["text"] in clean and m["text"] not in flagged_lines


def test_fallback_without_clean_lines_is_neutral_prompt():
    import copy
    p = copy.deepcopy(PERSONAS["avoidant"])
    p.cfg.pop("mock_clean_lines", None)
    out = fallback_output(NPCRequest(p, "男", 1, 40, "", "嗯", []))
    assert out["red_flags"] == [] and p.lines[1] and out["reply"] not in {l["text"] for l in p.lines[1]}


# ---------- Q46：clean line 配額與不重複 ----------
def test_clean_line_quota_one_per_three_and_no_repeat():
    p = PERSONAS["scammer"]
    llm = MockLLM(0)
    used, clean_turns = [], 0
    for i in range(30):
        stage = 1 + i // 6
        out = llm.generate(NPCRequest(p, "男", min(stage, 5), 40, "", "嗯", used, seed="s1"))
        used.append(out.get("_line", out["reply"]))
        clean_turns += out["red_flags"] == [] and out["_line"] in {t for v in p.cfg["mock_clean_lines"].values() for t in v}
    assert clean_turns == 10                      # 每 3 回合剛好 1 回合
    cleans = [u for u in used if u in {t for v in p.cfg["mock_clean_lines"].values() for t in v}]
    assert len(cleans) == len(set(cleans))        # 同一局不重複


# ---------- Q50 / Q52 / Q53 ----------
@pytest.fixture
def secure(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_REQUIRE_TOKEN", "1")
    monkeypatch.setenv("GAME_MIN_ID_LEN", "8")
    monkeypatch.setenv("GAME_RATE_PER_MIN", "60")
    monkeypatch.setenv("GAME_RATE_PER_IP_MIN", "100000")
    monkeypatch.setenv("GAME_NEW_PER_IP_HOUR", "100000")
    srv._rate.clear()
    game = srv.build_game(tmp_path, MockLLM(seed=1))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.make_handler(game))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]

    def call(path, body=None, token=None, method=None, headers=None):
        h = {"Content-Type": "application/json", **(headers or {})}
        if token:
            h["X-Player-Token"] = token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    call.tmp, call.game = tmp_path, game
    yield call
    httpd.shutdown()
    srv._rate.clear()


def _legacy(secure, pid="legacy0001"):
    (secure.tmp / f"{pid}.json").write_text(json.dumps(
        {"player_id": pid, "nickname": "舊玩家", "sessions": {}, "reviews": []}), encoding="utf-8")
    return pid


def test_legacy_profile_cannot_be_read_written_or_claimed(secure):
    pid = _legacy(secure)
    assert secure(f"/api/profile?player={pid}")[0] == 401
    assert secure("/api/nickname", {"player": pid, "nickname": "hacker"})[0] == 401
    assert secure("/api/start", {"player": pid, "persona": "avoidant"})[0] == 401
    assert secure(f"/api/profile?player={pid}", method="DELETE")[0] == 401
    saved = json.loads((secure.tmp / f"{pid}.json").read_text(encoding="utf-8"))
    assert saved["nickname"] == "舊玩家" and "token_hash" not in saved


def test_legacy_claim_only_with_env(secure, monkeypatch):
    pid = _legacy(secure)
    monkeypatch.setenv("GAME_ALLOW_LEGACY_CLAIM", "1")
    c, r = secure("/api/start", {"player": pid, "persona": "avoidant"})
    assert c == 200 and r["token"]


def test_admin_migrate_and_delete(secure, monkeypatch):
    pid = _legacy(secure)
    assert secure("/api/admin/migrate", {"player": pid})[0] == 401          # 未設管理者 token
    monkeypatch.setenv("GAME_ADMIN_TOKEN", "adm1n-secret")
    assert secure("/api/admin/migrate", {"player": pid}, headers={"X-Admin-Token": "bad"})[0] == 401
    c, r = secure("/api/admin/migrate", {"player": pid}, headers={"X-Admin-Token": "adm1n-secret"})
    assert c == 200 and r["token"]
    assert secure(f"/api/profile?player={pid}", token=r["token"])[1]["nickname"] == "舊玩家"
    assert secure("/api/admin/migrate", {"player": pid}, headers={"X-Admin-Token": "adm1n-secret"})[0] == 400
    assert secure(f"/api/profile?player={pid}", method="DELETE",
                  headers={"X-Admin-Token": "adm1n-secret"})[1]["deleted"] is True


def test_non_ascii_admin_header_is_not_500(secure, monkeypatch):
    monkeypatch.setenv("GAME_ADMIN_TOKEN", "adm1n-secret")
    pid = _legacy(secure)
    # http.client 以 latin-1 送 header，這裡用 latin-1 範圍的非 ASCII 字元
    c, r = secure(f"/api/profile?player={pid}", method="DELETE", headers={"X-Admin-Token": "密碼".encode("utf-8").decode("latin-1")})
    assert c == 401
    c, r = secure("/api/admin/migrate", {"player": pid}, headers={"X-Admin-Token": "é"})
    assert c == 401


def test_nonexistent_and_wrong_token_look_identical(secure):
    tok = secure("/api/start", {"player": "victim-001", "persona": "avoidant"})[1]["token"]
    a = secure("/api/profile?player=victim-001", token="wrong")
    b = secure("/api/profile?player=nobody-001", token="wrong")
    c = secure("/api/profile?player=nobody-001")
    assert a == b == c and a[0] == 401
    assert secure("/api/message", {"player": "victim-001", "persona": "avoidant", "text": "嗯"}, token="x") == \
        secure("/api/message", {"player": "nobody-001", "persona": "avoidant", "text": "嗯"}, token="x")
    assert secure("/api/profile?player=victim-001", token=tok)[0] == 200


def test_unauthenticated_flood_does_not_rate_limit_the_victim(secure, monkeypatch):
    monkeypatch.setenv("GAME_RATE_PER_MIN", "5")
    tok = secure("/api/start", {"player": "victim-002", "persona": "avoidant"})[1]["token"]
    for _ in range(30):
        assert secure("/api/nickname", {"player": "victim-002", "nickname": "x"})[0] == 401
    assert secure("/api/nickname", {"player": "victim-002", "nickname": "ok"}, token=tok)[0] == 200


def test_ip_rate_limit_stops_id_rotation(secure, monkeypatch):
    monkeypatch.setenv("GAME_RATE_PER_IP_MIN", "10")
    codes = [secure("/api/start", {"player": f"rotate-{i:04d}", "persona": "avoidant"})[0] for i in range(14)]
    assert codes[:10] == [200] * 10 and set(codes[10:]) == {429}


def test_new_players_per_ip_limit_and_total_cap_not_exhausted_by_one_ip(secure, monkeypatch):
    monkeypatch.setenv("GAME_NEW_PER_IP_HOUR", "3")
    monkeypatch.setenv("GAME_MAX_PLAYERS", "100")
    codes = [secure("/api/start", {"player": f"flood-{i:04d}", "persona": "avoidant"}) for i in range(6)]
    assert [c for c, _ in codes[:3]] == [200] * 3
    assert all(c == 429 and r["code"] == "quota_exceeded" for c, r in codes[3:])
    assert len(list(secure.tmp.glob("flood-*.json"))) == 3     # 被拒的不留檔
    assert secure.game.store.count_players() < 100              # 單一來源灌不滿總量


# ---------- Q57 ----------
@pytest.mark.parametrize("text,expected", [
    ("分手吧，才怪", False), ("我朋友剛分手", False), ("我們分手的話你會怎樣", False),
    ("我前任跟我分手過", False), ("不要封鎖我", False), ("我不想分手", False),
    ("你是不是想分手", False), ("我走了一圈回來", False), ("他們昨天分手了", False),
    ("我要走了", True), ("我走啦", True), ("拜拜我先走", True), ("別再聯絡了", True),
    ("我們分手吧", True), ("到此為止，我要封鎖你", True), ("我走了，再見", True),
])
def test_wants_leave_round6(text, expected):
    assert wants_leave(text) is expected


# ---------- Q56 ----------
@pytest.mark.parametrize("text", [
    "生日 1990-01-01 12:30:45 剛好", "訂單編號 20241108123456", "我們認識 3.14159265358 天",
    "1萬2000塊 一共 12000000000 元", "I love u.io", "這是 Mr.me", "我去 7-11 買 100000 0000 的點數",
    "下午 3:30 見", "2024/11/08 見面", "我今年 28 歲，身高 175",
])
def test_output_filter_allows_dates_and_numbers(text):
    validate_output({"reply": text, "red_flags": [], "break_character": False}, PERSONAS["scammer"])


@pytest.mark.parametrize("text", [
    "加我 ｅｘａｍｐｌｅ．ｃｏｍ", "example dot com", "0912​345​678打給我", "零九一二三四五六七八",
    "我的LINE @kevin888", "k e v i n . m e", "點這裡 hxxp://a.b", "我帳號 8 1 2 0 0 0 1 2 3 4 5 6",
    "bit.ly/abc", "t.me/kevin_invest", "wa.me/886912345678", "http://x.y", "請匯到帳號 1234567890123",
    "0912-345-678", "ｗｗｗ．ｓｈｏｐ．ｃｏｍ",
])
def test_output_filter_blocks_obfuscated_contacts(text):
    with pytest.raises(LLMOutputError):
        validate_output({"reply": text, "red_flags": [], "break_character": False}, PERSONAS["scammer"])


# ---------- Q48 接線 ----------
def test_install_safety_classifier_with_fake(monkeypatch):
    seen = {}
    monkeypatch.setattr(safety, "set_classifier", lambda fn: seen.setdefault("fn", fn), raising=False)
    fake = lambda text: None  # noqa: E731
    assert Game.install_safety_classifier(fake) is True and seen["fn"] is fake


def test_install_safety_classifier_missing_interface(monkeypatch):
    monkeypatch.delattr(safety, "set_classifier", raising=False)
    assert Game.install_safety_classifier(lambda t: None) is False


def test_coach_receives_flag_info_when_supported(tmp_path, monkeypatch):
    from engine import coach
    got = {}
    real = coach.interject

    def spy(persona, npc_name, last_npc, text, kind, severity, money=0, turn=0, has_red_flag=None):
        got["flag"] = has_red_flag
        return real(persona, npc_name, last_npc, text, kind, severity, money, turn, has_red_flag)
    monkeypatch.setattr(coach, "interject", spy)
    g = Game(PERSONAS, Store(tmp_path), MockLLM(0))
    g.start("u1", "scammer")
    g.send("u1", "scammer", text="不要")
    assert isinstance(got["flag"], bool)


# ---------- 最後一輪：Q64 錯誤憑證節流 ----------
def test_failed_auth_throttled_per_id_and_ip(secure, monkeypatch):
    monkeypatch.setenv("GAME_AUTH_FAIL_PER_ID", "5")
    monkeypatch.setenv("GAME_AUTH_FAIL_PER_IP", "8")
    tok = secure("/api/start", {"player": "target-0001", "persona": "avoidant"})[1]["token"]
    codes = [secure("/api/nickname", {"player": "target-0001", "nickname": "x"}, token="a" * 32)[0]
             for _ in range(8)]
    assert codes[:5] == [401] * 5 and set(codes[5:]) == {429}
    # 被節流期間連正確 token 也先擋（避免用來暴力猜測）
    assert secure("/api/nickname", {"player": "target-0001", "nickname": "x"}, token=tok)[0] == 429
    # 其他 ID 仍受每 IP 上限
    c = [secure("/api/message", {"player": f"other-{i:04d}", "persona": "avoidant", "text": "嗯"}, token="b" * 32)[0]
         for i in range(10)]
    assert 429 in c


def test_short_or_long_tokens_never_authorize(secure):
    tok = secure("/api/start", {"player": "target-0002", "persona": "avoidant"})[1]["token"]
    assert secure("/api/nickname", {"player": "target-0002", "nickname": "x"}, token=tok[:8])[0] == 401
    assert secure("/api/nickname", {"player": "target-0002", "nickname": "x"}, token=tok + "z" * 300)[0] == 401
    assert secure("/api/nickname", {"player": "target-0002", "nickname": "x"}, token=tok)[0] == 200


def test_admin_migrate_throttled(secure, monkeypatch):
    monkeypatch.setenv("GAME_ADMIN_TOKEN", "x" * 24)
    monkeypatch.setenv("GAME_AUTH_FAIL_PER_IP", "5")
    codes = [secure("/api/admin/migrate", {"player": "legacy0001"}, headers={"X-Admin-Token": "bad"})[0]
             for _ in range(8)]
    assert codes[:5] == [401] * 5 and set(codes[5:]) == {429}


def test_admin_actions_are_logged_without_token(secure, monkeypatch, caplog):
    import logging
    monkeypatch.setenv("GAME_ADMIN_TOKEN", "adm1n-secret-0123456789")
    pid = _legacy(secure)
    with caplog.at_level(logging.WARNING, logger="game.server"):
        secure("/api/admin/migrate", {"player": pid}, headers={"X-Admin-Token": "adm1n-secret-0123456789"})
    assert "ADMIN migrate" in caplog.text and "adm1n-secret" not in caplog.text and pid not in caplog.text


# ---------- 接話：NPC 要回應玩家剛說的話 ----------
def test_mock_replies_acknowledge_player_text_and_keep_flags():
    p = PERSONAS["scammer"]
    llm = MockLLM(0)
    base = llm.generate(NPCRequest(p, "男", 1, 40, "", "", [], seed="b"))      # 開場：不接話
    assert base["reply"] == base["_line"] or base["reply"].endswith(base["_line"])
    q = MockLLM(0).generate(NPCRequest(p, "男", 1, 40, "", "你今天在做什麼？", [], seed="b"))
    r = MockLLM(0).generate(NPCRequest(p, "男", 1, 40, "", "我不想聊這個", [], seed="b"))
    assert q["reply"] != r["reply"]                                              # 不同意圖接不同話
    assert q["reply"].endswith(q["_line"]) and q["reply"] != q["_line"]          # 接話在台詞之前
    assert q["red_flags"] == MockLLM(0).generate(NPCRequest(p, "男", 1, 40, "", "", [], seed="b"))["red_flags"]


def test_prompt_tells_model_to_answer_latest_player_message(tmp_path):
    from engine.game import Game
    from engine.store import Store
    g = Game(PERSONAS, Store(tmp_path), MockLLM(0))
    g.start("u1", "scammer")
    st = g.store.load("u1")["sessions"]["scammer"]
    assert "<reply_rule>" in g.build_prompt(PERSONAS["scammer"], st, skip_last_player=True)
    assert "<reply_rule>" not in g.build_prompt(PERSONAS["scammer"], st)
