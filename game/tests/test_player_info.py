"""換人格後沿用玩家基本資訊（暱稱、自述年齡），NPC prompt 不必重問。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.game import Game  # noqa: E402
from engine.llm import MockLLM  # noqa: E402
from engine.personas import load_personas  # noqa: E402
from engine.store import Store  # noqa: E402

PERSONAS = load_personas()


def _game(tmp_path):
    return Game(PERSONAS, Store(tmp_path), MockLLM())


def test_first_persona_has_no_player_info_block(tmp_path):
    g = _game(tmp_path)
    g.start("u1", "scammer")
    st = g.store.load("u1")["sessions"]["scammer"]
    prompt = g.build_prompt(PERSONAS["scammer"], st)
    assert "<player_info>" not in prompt


def test_nickname_and_age_carry_to_next_persona(tmp_path):
    g = _game(tmp_path)
    g.set_nickname("u1", "小安")
    g.start("u1", "scammer")
    g.send("u1", "scammer", text="我今年25歲，在台北上班")
    other = next(p for p in PERSONAS if p != "scammer")
    g.start("u1", other)
    st = g.store.load("u1")["sessions"][other]
    prompt = g.build_prompt(PERSONAS[other], st)
    assert "<player_info>" in prompt
    assert "小安" in prompt and "25 歲" in prompt
    assert "不要再重新詢問" in prompt


def test_player_info_not_exposed_in_public_state(tmp_path):
    g = _game(tmp_path)
    g.set_nickname("u1", "小安")
    out = g.start("u1", "scammer")
    assert "player_info" not in out
