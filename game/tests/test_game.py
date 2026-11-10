import json
import re
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

GAME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GAME_DIR))

from engine import safety, scoring  # noqa: E402
from engine.game import Game, GameError, classify  # noqa: E402
from engine.llm import MockLLM  # noqa: E402
from engine.personas import load_personas, render, TEMPLATE_KEYS  # noqa: E402
from engine.store import Store  # noqa: E402

PERSONAS = load_personas()
PIDS = list(PERSONAS)


@pytest.fixture
def game(tmp_path):
    return Game(PERSONAS, Store(tmp_path), MockLLM(seed=0))


def first_choice(game, pid, kind):
    st = game.store.load("u1")["sessions"][pid]
    choices = game._choices(PERSONAS[pid], st)
    i = next(i for i, c in enumerate(choices) if c["kind"] == kind)
    return f"s{st['stage']}_{i}"


# ---------- 人格檔 ----------
def test_all_five_personas_load():
    assert set(PIDS) == {"avoidant", "dependent", "anxious", "scammer", "player"}


@pytest.mark.parametrize("pid", PIDS)
def test_persona_has_lines_choices_flags_every_stage(pid):
    p = PERSONAS[pid]
    for stage in range(1, 6):
        assert p.lines.get(stage), f"{pid} 第{stage}階段沒有台詞"
        assert {c["kind"] for c in p.choices(stage)} >= {"brain", "awake"}
        assert {c["kind"] for c in p.choices(stage)} == {"brain", "awake"}
        for code in p.cfg["mock_stage_flags"][str(stage)]:
            assert code in p.flag_codes, f"{pid} 的 mock 紅旗 {code} 不在紅旗表"


@pytest.mark.parametrize("pid", PIDS)
def test_prompt_renders_without_leftover_placeholders(pid, game):
    game.start("u1", pid)
    st = game.store.load("u1")["sessions"][pid]
    prompt = game.build_prompt(PERSONAS[pid], st)
    for key in TEMPLATE_KEYS:
        assert not re.search(r"\{\{?\s*" + key + r"\s*\}?\}", prompt), f"{pid} 殘留 {key}"
    assert "\\_" not in prompt and "“" not in prompt
    assert st["npc_name"] in prompt


def test_render_leaves_json_braces_alone():
    out = render('{"reply": "x"} {{stage}} {stage} {other}', {"stage": 3})
    assert out == '{"reply": "x"} 3 3 {other}'


# ---------- 安全檢查 ----------
@pytest.mark.parametrize("text,cat", [
    ("我真的不想活了", "self_harm"),
    ("我前男友一直跟蹤我", "real_violence"),
    ("現實中有網友叫我匯款給他", "real_scam"),
    ("他要我傳裸照", "real_scam"),
    ("我今年15歲", "minor"),
    ("我是國中生", "minor"),
])
def test_safety_triggers(text, cat):
    assert safety.check(text) == cat


@pytest.mark.parametrize("text", ["我今年25歲", "今天好累喔", "你是不是在騙我", "我不會轉帳給你"])
def test_safety_no_false_alarm(text):
    assert safety.check(text) is None


def test_safety_stops_session_and_skips_llm(game):
    game.start("u1", "player")
    n_npc = sum(m["role"] == "npc" for m in game.store.load("u1")["sessions"]["player"]["messages"])
    st = game.send("u1", "player", text="其實我現實中很想死")
    assert st["ended"] and st["safety"]["category"] == "self_harm"
    assert any(r["number"] == "1925" for r in st["safety"]["resources"])
    assert sum(m["role"] == "npc" for m in st["messages"]) == n_npc  # NPC 沒有再回話
    with pytest.raises(GameError):
        game.send("u1", "player", text="哈囉")


# ---------- 劇情流程 ----------
def test_classify():
    assert classify("好啊沒關係，我等你") == "brain"
    assert classify("我不會轉帳，這是詐騙") == "awake"
    assert classify("今天天氣不錯") == "neutral"


def test_start_creates_opening_line_and_hides_flags(game):
    st = game.start("u1", "player")
    assert st["stage"] == 1 and st["messages"][0]["role"] == "npc"
    assert "red_flags" not in st["messages"][0]  # 還沒檢舉前看不到答案
    assert len(st["choices"]) == 2


def test_stage_advances_and_leaving_ends_game(game):
    game.start("u1", "player")
    for _ in range(6):
        st = game.send("u1", "player", text="嗯嗯")
    assert st["stage"] == 3
    st = game.send("u1", "player", text="我們到此為止吧，我要封鎖你")
    assert st["stage"] == 5 and not st["ended"]
    st = game.send("u1", "player", text="不用再說了")
    st = game.send("u1", "player", text="再見")
    assert st["ended"] and st["choices"] == []
    assert st["messages"][-1]["role"] == "system"


def test_npc_does_not_repeat_lines_within_stage(game):
    game.start("u1", "avoidant")
    for _ in range(2):
        game.send("u1", "avoidant", text="嗯")
    st = game.store.load("u1")["sessions"]["avoidant"]
    stage1 = [m["text"] for m in st["messages"] if m["role"] == "npc" and m["stage"] == 1]
    assert len(stage1) == len(set(stage1))


def test_brain_choice_gets_roasted_awake_gets_praise(game):
    game.start("u1", "player")
    st = game.send("u1", "player", choice_id=first_choice(game, "player", "brain"), severity=3)
    coach = [m for m in st["messages"] if m["role"] == "coach"]
    # 開場台詞可能是 mock_clean_lines（無紅旗），文案因此不固定；只驗語氣
    assert coach[-1]["tone"] == "roast" and coach[-1]["text"]
    st = game.send("u1", "player", choice_id=first_choice(game, "player", "awake"))
    # 對方上一句若沒有紅旗，教練不稱讚拒絕而回 neutral（Q40/Q55）；確定性的檢查在 test_coach_wiring.py
    assert [m for m in st["messages"] if m["role"] == "coach"][-1]["tone"] in ("praise", "neutral")


def test_scammer_money_choice_counts(game):
    game.start("u1", "scammer")
    for _ in range(6):
        game.send("u1", "scammer", text="嗯嗯")
    st = game.send("u1", "scammer", choice_id=first_choice(game, "scammer", "brain"))
    assert st["money_lost"] == 10000


def test_gender_filters_lines(game):
    st = game.start("u1", "player", gender="男")
    assert st["npc_name"] == "阿哲"
    lines = PERSONAS["player"].lines
    female_only = {l["text"] for s in lines.values() for l in s if l["gender"] == "女"}
    assert female_only  # 渣男渣女檔有女性限定台詞
    for _ in range(8):
        st = game.send("u1", "player", text="嗯")
    assert not any(m["text"] in female_only for m in st["messages"])


# ---------- 紅旗檢舉與計分 ----------
def test_flag_reports_correctness(game):
    st = game.start("u1", "player")
    r = game.flag("u1", "player", st["messages"][0]["id"])
    saved = game.store.load("u1")["sessions"]["player"]["messages"][0]
    assert r["correct"] == bool(saved["red_flags"]) and saved["flagged"]


def test_scoring_perfect_vs_fooled():
    def state(flagged, brain, awake, trust):
        msgs = [{"role": "npc", "red_flags": ["x"], "flagged": flagged},
                {"role": "npc", "red_flags": [], "flagged": False}]
        return {"messages": msgs, "brain_count": brain, "awake_count": awake,
                "trust": trust, "money_events": []}
    good = scoring.compute(state(True, 0, 5, 0))
    bad = scoring.compute(state(False, 5, 0, 100))
    assert good["recall"] == 100 and good["awake_score"] >= 80 and good["grade"] == "火眼金睛"
    assert bad["recall"] == 0 and bad["fooled_index"] == 100 and bad["grade"] == "新手上路"


def test_review_records_once_and_remembers_other_personas(game):
    game.start("u1", "avoidant")
    game.send("u1", "avoidant", text="嗯")
    game.review("u1", "avoidant", finish=True)
    game.review("u1", "avoidant")  # 重複按結算
    assert len(game.store.load("u1")["reviews"]) == 1
    game.start("u1", "player")
    r = game.review("u1", "player", finish=True)
    assert "教練記得你" in r["coach"]["comment"] and "迴避型" in r["coach"]["comment"]


# ---------- 存檔／切換人格 ----------
def test_switching_persona_keeps_history(game):
    game.start("u1", "dependent")
    game.send("u1", "dependent", text="今天好累")
    game.start("u1", "anxious")
    st = game.start("u1", "dependent")  # 切回來
    assert any(m["text"] == "今天好累" for m in st["messages"])
    assert game.profile_summary("u1")["sessions"].keys() == {"dependent", "anxious"}


def test_reset_starts_fresh(game):
    game.start("u1", "dependent")
    game.send("u1", "dependent", text="今天好累")
    game.reset("u1", "dependent")
    st = game.start("u1", "dependent")
    assert len(st["messages"]) == 1


def test_store_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        Store(tmp_path).load("../../etc/passwd")


# ---------- HTTP API ----------
def test_http_api_end_to_end(tmp_path):
    from http.server import ThreadingHTTPServer
    import server as srv

    game = srv.build_game(tmp_path, MockLLM(seed=1))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.make_handler(game))
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def call(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    try:
        import os
        os.environ["GAME_QUIET"] = "1"
        assert call("/api/personas")[1][0]["id"]
        code, st = call("/api/start", {"player": "web1", "persona": "scammer"})
        assert code == 200 and st["messages"]
        code, st = call("/api/message", {"player": "web1", "persona": "scammer", "choice_id": st["choices"][0]["id"]})
        assert code == 200 and st["messages"][-1]["role"] == "npc"
        code, r = call("/api/review", {"player": "web1", "persona": "scammer", "severity": 3, "finish": True})
        assert code == 200 and "awake_score" in r["scores"]
        assert call("/api/prompt?player=web1&persona=scammer")[1]["prompt"]
        assert call("/api/message", {"player": "web1", "persona": "nope", "text": "hi"})[0] == 400
        assert call("/api/start", {"player": "../x", "persona": "scammer"})[0] == 400
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as r:
            assert "醒醒吧" in r.read().decode()
    finally:
        httpd.shutdown()
