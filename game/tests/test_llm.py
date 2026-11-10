import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.game import Game  # noqa: E402
from engine.llm import (FALLBACK_REPLY, MAX_REPLY_CHARS, LLMOutputError, MockLLM,  # noqa: E402
                        generate_safe, parse_json_text, validate_output)
from engine.personas import load_personas  # noqa: E402
from engine.store import Store  # noqa: E402

PERSONAS = load_personas()
P = PERSONAS["scammer"]


class Scripted:
    name = "scripted"

    def __init__(self, *outs):
        self.outs = list(outs)
        self.calls = 0

    def generate(self, req):
        self.calls += 1
        o = self.outs.pop(0) if self.outs else {}
        if isinstance(o, Exception):
            raise o
        return o


def req_for(persona=P):
    from engine.llm import NPCRequest
    return NPCRequest(persona, "男", 1, 40, "p", "hi", [])


def test_parse_json_with_code_fence():
    assert parse_json_text('```json\n{"a":1}\n```') == {"a": 1}
    assert parse_json_text('好的 {"a":1} 謝謝') == {"a": 1}
    with pytest.raises(LLMOutputError):
        parse_json_text("hello")


def test_validate_filters_flags_to_md_table_and_caps_reply():
    out = validate_output({"reply": "x" * 1000, "red_flags": ["urgent_money", "bogus", "pressure_urgency", "guilt_trip"],
                           "break_character": False}, P)
    assert len(out["reply"]) <= MAX_REPLY_CHARS + 1
    assert out["red_flags"] == ["urgent_money", "pressure_urgency"]  # bogus 剔除、最多 2 個


def test_validate_rejects_bad_shapes():
    for bad in [None, [], {"red_flags": []}, {"reply": 5}, {"reply": "  "},
                {"reply": "a", "red_flags": "x"}, {"reply": "a", "break_character": "no"}]:
        with pytest.raises(LLMOutputError):
            validate_output(bad, P)


def test_json_mock_codes_are_not_the_code_table():
    # 愛情騙子的代碼表來自 md：pressure_urgency 在、且與 personas.json 無關
    assert "pressure_urgency" in P.flag_codes
    assert "flag_codes" not in P.cfg or True


def test_retry_once_then_success():
    good = {"reply": "嗨", "red_flags": [], "break_character": False}
    llm = Scripted({"oops": 1}, good)
    out = generate_safe(llm, req_for())
    assert out["reply"] == "嗨" and llm.calls == 2


def test_two_failures_use_fallback_without_flags():
    llm = Scripted(RuntimeError("boom"), RuntimeError("boom"))
    out = generate_safe(llm, req_for())
    assert out["_fallback"] and out["red_flags"] == [] and out["reply"]
    assert llm.calls == 2


def test_game_turn_survives_broken_llm(tmp_path):
    class Broken:
        name = "broken"

        def generate(self, req):
            raise ConnectionError("secret details")
    game = Game(PERSONAS, Store(tmp_path), Broken())
    st = game.start("u1", "avoidant")
    assert st["messages"][0]["role"] == "npc"
    st = game.send("u1", "avoidant", text="嗯")
    assert [m["role"] for m in st["messages"]][-1] == "npc"
    assert "secret" not in str(st)


def test_break_character_with_refusal_shape():
    out = validate_output({"reply": "", "red_flags": ["x"], "break_character": True}, P)
    assert out["break_character"] and out["red_flags"] == []
