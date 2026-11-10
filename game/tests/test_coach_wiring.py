import inspect
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import coach, safety, scoring  # noqa: E402
from engine import game as game_mod  # noqa: E402
from engine.game import Game, _call_compat  # noqa: E402
from engine.llm import MockLLM  # noqa: E402
from engine.personas import load_personas  # noqa: E402
from engine.store import Store  # noqa: E402

PERSONAS = load_personas()


class Scripted:
    """每次回傳指定的 NPC 句子與紅旗。"""
    name = "scripted"

    def __init__(self, flags):
        self.flags = flags

    def generate(self, req):
        return {"reply": "你今天過得好嗎", "red_flags": list(self.flags), "break_character": False}


def _awake_choice(g, pid):
    st = g.store.load("u1")["sessions"][pid]
    opts = g._choices(PERSONAS[pid], st)
    return f"s{st['stage']}_{next(i for i, c in enumerate(opts) if c['kind'] == 'awake')}"


@pytest.mark.parametrize("pid", list(PERSONAS))
def test_awake_after_clean_npc_line_is_neutral_not_praise(tmp_path, pid):
    g = Game(PERSONAS, Store(tmp_path), Scripted([]))
    g.start("u1", pid)
    st = g.send("u1", pid, choice_id=_awake_choice(g, pid))
    tips = [m for m in st["messages"] if m["role"] == "coach"]
    assert tips and tips[-1]["tone"] == "neutral" and tips[-1]["text"]


@pytest.mark.parametrize("pid", list(PERSONAS))
def test_awake_after_flagged_npc_line_is_praise(tmp_path, pid):
    code = sorted(PERSONAS[pid].flag_codes)[0]
    g = Game(PERSONAS, Store(tmp_path), Scripted([code]))
    g.start("u1", pid)
    st = g.send("u1", pid, choice_id=_awake_choice(g, pid))
    # 對外 tone 不得洩漏紅旗有無（Q67）：praise 在序列化時統一成 neutral；存檔內部仍記 praise
    assert [m for m in st["messages"] if m["role"] == "coach"][-1]["tone"] == "neutral"
    stored = g.store.load("u1")["sessions"][pid]["messages"]
    assert [m for m in stored if m["role"] == "coach"][-1]["tone"] == "praise"


def test_free_text_refusal_after_clean_line_is_neutral(tmp_path):
    g = Game(PERSONAS, Store(tmp_path), Scripted([]))
    g.start("u1", "scammer")
    st = g.send("u1", "scammer", text="我不要，這是詐騙")
    assert [m for m in st["messages"] if m["role"] == "coach"][-1]["tone"] == "neutral"


# ---------- _call_compat 不再靜默 ----------
def test_call_compat_warns_once_on_dropped_keyword(caplog):
    def f(a, b=1):
        return a + b
    game_mod._WARNED_DROPPED.clear()
    with caplog.at_level(logging.WARNING, logger="game"):
        assert _call_compat(f, 1, b=2, nope=3) == 3
        _call_compat(f, 1, nope=3)
    msgs = [r for r in caplog.records if "nope" in r.getMessage()]
    assert len(msgs) == 1


def test_all_compat_call_sites_match_real_signatures(tmp_path):
    """game.py 傳給 coach.interject / scoring.compute 的關鍵字必須全部被接受（避免靜默略過）。"""
    src = inspect.getsource(game_mod.Game)
    assert "has_red_flag=" in src and "last_npc_has_flags" not in src and "kind_source" not in src
    assert "has_red_flag" in inspect.signature(coach.interject).parameters
    # 實際跑一遍並確認沒有任何警告
    game_mod._WARNED_DROPPED.clear()
    g = Game(PERSONAS, Store(tmp_path), MockLLM(0))
    g.start("u1", "scammer")
    g.send("u1", "scammer", text="不要")
    g.review("u1", "scammer", finish=True)
    assert game_mod._WARNED_DROPPED == set()


# ---------- safety.set_classifier 端到端 ----------
@pytest.fixture
def reset_classifier():
    yield
    safety.set_classifier(None)


def test_install_calls_real_set_classifier_with_matching_signature(reset_classifier):
    assert "fn" in inspect.signature(safety.set_classifier).parameters
    fake = lambda text: None  # noqa: E731
    assert Game.install_safety_classifier(fake) is True
    assert safety.get_classifier() is fake


def test_fake_classifier_end_to_end_ends_session(tmp_path, reset_classifier):
    text = "今天天氣很好"  # 規則完全不會觸發
    assert safety.assess(text) is None
    calls = []

    def fake(t):
        calls.append(t)
        return {"category": "self_harm", "severity": "high"}
    assert Game.install_safety_classifier(fake)
    g = Game(PERSONAS, Store(tmp_path), MockLLM(0))
    g.start("u1", "avoidant")
    st = g.send("u1", "avoidant", text=text)
    assert calls == [text]
    assert st["ended"] and st["safety"]["category"] == "self_harm" and st["safety"]["ends_session"]
    blob = str(g.store.load("u1"))
    assert text not in blob  # 觸發 safety 的原文不入庫


def test_classifier_error_or_garbage_does_not_break_game(tmp_path, reset_classifier):
    def boom(t):
        raise RuntimeError("down")
    Game.install_safety_classifier(boom)
    g = Game(PERSONAS, Store(tmp_path), MockLLM(0))
    g.start("u1", "avoidant")
    assert not g.send("u1", "avoidant", text="今天天氣很好")["ended"]
    Game.install_safety_classifier(lambda t: {"category": "nope", "severity": "high"})
    assert not g.send("u1", "avoidant", text="哈囉")["ended"]


def test_classifier_low_severity_gives_notice_not_end(tmp_path, reset_classifier):
    Game.install_safety_classifier(lambda t: {"category": "self_harm", "severity": "low"})
    g = Game(PERSONAS, Store(tmp_path), MockLLM(0))
    g.start("u1", "avoidant")
    st = g.send("u1", "avoidant", text="今天天氣很好")
    assert not st["ended"] and st["notice"]["severity"] == "low"
