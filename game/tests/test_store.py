import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.game import Game  # noqa: E402
from engine.llm import MockLLM  # noqa: E402
from engine.personas import load_personas  # noqa: E402
from engine.store import Store, valid_player_id  # noqa: E402

PERSONAS = load_personas()


@pytest.mark.parametrize("bad", ["../x", "a/b", "a\\b", "", ".hidden", "a.b", "a" * 65, "con", "NUL",
                                 "x y", "é", None, 5, "a\x00b", "..", "/etc/passwd"])
def test_invalid_ids_rejected(tmp_path, bad):
    assert not valid_player_id(bad)
    with pytest.raises(ValueError):
        Store(tmp_path).load(bad)


def test_valid_ids():
    for ok in ["u1", "abc-DEF_123", "a" * 64]:
        assert valid_player_id(ok)


def test_atomic_save_leaves_no_temp_files(tmp_path):
    st = Store(tmp_path)
    prof = st.load("u1")
    st.save(prof)
    assert [p.name for p in tmp_path.iterdir()] == ["u1.json"]


def test_corrupt_save_quarantined_and_fresh(tmp_path):
    (tmp_path / "u1.json").write_text("{not json", encoding="utf-8")
    st = Store(tmp_path)
    prof = st.load("u1")
    assert prof["sessions"] == {}
    names = [p.name for p in tmp_path.iterdir()]
    assert any(n.startswith("u1.json.corrupt-") for n in names) and "u1.json" not in names
    game = Game(PERSONAS, st, MockLLM(seed=0))
    assert game.start("u1", "avoidant")["messages"]  # 不再 500


def test_wrong_structure_also_quarantined(tmp_path):
    (tmp_path / "u1.json").write_text("[1,2]", encoding="utf-8")
    assert Store(tmp_path).load("u1")["sessions"] == {}
    assert any(".corrupt-" in p.name for p in tmp_path.iterdir())


def test_delete_removes_everything(tmp_path):
    st = Store(tmp_path)
    game = Game(PERSONAS, st, MockLLM(seed=0))
    game.start("u1", "avoidant")
    (tmp_path / "u1.json.corrupt-old").write_text("x")
    assert game.delete_profile("u1")["deleted"] is True
    assert list(tmp_path.iterdir()) == []
    assert game.delete_profile("u1")["deleted"] is False
    assert game.profile_summary("u1")["sessions"] == {}


class SlowLLM(MockLLM):
    def generate(self, req):
        time.sleep(0.05)
        return super().generate(req)


def test_concurrent_sends_same_player_same_persona(tmp_path):
    game = Game(PERSONAS, Store(tmp_path), SlowLLM(seed=0))
    game.start("u1", "avoidant")
    errs = []

    def go():
        try:
            game.send("u1", "avoidant", text="嗯")
        except Exception as e:  # noqa: BLE001
            errs.append(e)
    ts = [threading.Thread(target=go) for _ in range(5)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    sess = game.store.load("u1")["sessions"]["avoidant"]
    assert not errs or all("ended" in str(e) for e in errs)
    ids = [m["id"] for m in sess["messages"]]
    assert len(ids) == len(set(ids))
    done = 5 - len(errs)
    assert sess["player_turns"] == done


def test_concurrent_different_personas_no_lost_update(tmp_path):
    game = Game(PERSONAS, Store(tmp_path), SlowLLM(seed=0))
    game.start("u1", "avoidant")
    game.start("u1", "anxious")
    ts = [threading.Thread(target=game.send, args=("u1", p), kwargs={"text": "嗯"})
          for p in ("avoidant", "anxious")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    s = game.store.load("u1")["sessions"]
    assert s["avoidant"]["player_turns"] == 1 and s["anxious"]["player_turns"] == 1


def test_concurrent_save_file_always_valid_json(tmp_path):
    st = Store(tmp_path)
    prof = st.load("u1")
    prof["blob"] = "x" * 50000

    def go():
        for _ in range(30):
            st.save(prof)
    ts = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in ts]
    for _ in range(50):
        json.loads((tmp_path / "u1.json").read_text(encoding="utf-8")) if (tmp_path / "u1.json").exists() else None
    [t.join() for t in ts]
    assert json.loads((tmp_path / "u1.json").read_text(encoding="utf-8"))["blob"]
