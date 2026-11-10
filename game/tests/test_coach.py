import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import coach, scoring  # noqa: E402
from engine.personas import load_personas  # noqa: E402

PERSONAS = load_personas()
PERSONA = PERSONAS["scammer"]
BANNED = ["提款機", "情緒垃圾桶", "垃圾桶", "戀愛腦末期", "蠢", "笨", "白痴", "智障", "活該", "怪你", "你就是", "跪了", "陪練", "捐給詐騙集團"]
NPC = {"text": "我現在有個投資機會，今天一定要決定", "red_flags": [PERSONA.cfg["mock_stage_flags"]["3"][0]]}


def all_template_strings():
    for scenario, by_sev in coach.TEMPLATES.items():
        for sev, options in by_sev.items():
            for t in options:
                yield scenario, sev, t


def test_default_severity_is_gentle():
    assert coach.DEFAULT_SEVERITY == 1
    tip = coach.interject(PERSONA, "小美", NPC, "好啊", "brain", severity=None, turn=1)
    gentle = coach.interject(PERSONA, "小美", NPC, "好啊", "brain", severity=1, turn=1)
    assert tip == gentle
    assert coach.interject(PERSONA, "小美", NPC, "好啊", "brain", severity=99, turn=1) == gentle


@pytest.mark.parametrize("scenario", list(coach.TEMPLATES))
@pytest.mark.parametrize("sev", [1, 2, 3])
def test_at_least_three_distinct_lines(scenario, sev):
    options = coach.TEMPLATES[scenario][sev]
    assert len(options) >= 3 and len(set(options)) == len(options)


def test_no_personal_insults_in_any_template():
    for scenario, sev, t in all_template_strings():
        for w in BANNED:
            assert w not in t, (scenario, sev, t, w)


def test_templates_format_without_error():
    for scenario, sev, t in all_template_strings():
        t.format(npc="小美", quote="q", flag="f", amount=1000, text="t", meaning="m")


@pytest.mark.parametrize("sev", [1, 2, 3])
def test_interject_varies_with_turn_and_never_echoes_player(sev):
    texts = {coach.interject(PERSONA, "小美", NPC, "獨特的玩家原文XYZ", "brain", sev, 0, t)["text"] for t in range(3)}
    assert len(texts) == 3
    assert all("XYZ" not in t for t in texts)
    praises = {coach.interject(PERSONA, "小美", NPC, "x", "awake", sev, 0, t)["text"] for t in range(3)}
    assert len(praises) == 3


def test_interject_no_flag_money_and_neutral():
    tip = coach.interject(PERSONA, "小美", {"text": "晚安", "red_flags": []}, "好", "brain", 2, 0, 0)
    assert tip["tone"] == "roast"
    tip = coach.interject(PERSONA, "小美", NPC, "好", "brain", 2, 12000, 0)
    assert "12,000" in tip["text"]
    assert coach.interject(PERSONA, "小美", NPC, "嗯", "neutral", 2) is None


def _state(missed=True):
    flags = ["x"] if missed else []
    return {"messages": [{"role": "npc", "text": "快匯款給我", "red_flags": [PERSONA.cfg["mock_stage_flags"]["3"][0]],
                          "flagged": not missed}]}


def _scores(score, grade=None, money=0, fp=0):
    g = next(x for x in scoring.GRADES if score >= x[0])
    return {"awake_score": score, "grade": grade or g[1], "grade_note": g[2], "money_lost": money, "false_positives": fp}


@pytest.mark.parametrize("sev", [1, 2, 3])
@pytest.mark.parametrize("score", [10, 30, 50, 70, 90])
def test_review_clean_of_insults_and_always_returns_comment(sev, score):
    r = coach.review(PERSONA, "小美", _state(), _scores(score, money=5000, fp=1), sev, [])
    assert r["severity"] == sev and r["items"][0]["status"] == "missed"
    for w in BANNED:
        assert w not in r["comment"], (sev, score, w)


@pytest.mark.parametrize("sev", [1, 2, 3])
def test_low_score_review_has_next_step_and_no_mocking(sev):
    r = coach.review(PERSONA, "小美", _state(), _scores(10), sev, [])
    assert "下一步" in r["comment"]
    assert "戀愛腦末期" not in r["comment"]


def test_review_remembers_other_persona():
    past = [{"persona_id": "avoidant", "persona_title": "迴避型", "awake_score": 55}]
    r = coach.review(PERSONA, "小美", _state(), _scores(50), 1, past)
    assert "教練記得你" in r["comment"] and "迴避型" in r["comment"]


def test_review_variants_differ_by_seed():
    seen = set()
    for extra in range(6):
        st = _state()
        st["messages"] += [{"role": "player", "text": "x"}] * extra
        seen.add(coach.review(PERSONA, "小美", st, _scores(10), 3, [])["comment"])
    assert len(seen) >= 3


OLD_GRADES = ["清醒戰士", "半醒狀態", "暈船中", "戀愛腦末期", "戀愛腦"]


def test_grade_names_are_neutral_and_not_in_coach_text():
    assert [g[1] for g in scoring.GRADES] == ["火眼金睛", "警覺升級", "觀察中", "新手上路"]
    assert [g[0] for g in scoring.GRADES] == [80, 60, 40, 0]
    for _, _, t in all_template_strings():
        assert not any(o in t for o in OLD_GRADES), t
    for score in (10, 50, 70, 90):
        r = coach.review(PERSONA, "小美", _state(), _scores(score), 3, [])
        assert not any(o in r["comment"] for o in OLD_GRADES)
        assert r["comment"].startswith("【" + next(g[1] for g in scoring.GRADES if score >= g[0]) + "】")


def test_refusal_feedback_does_not_depend_on_red_flag():
    """Q67：教練對拒絕的回饋與對方有無紅旗無關，答案延到結算。"""
    clean = {"text": "我今天要加班", "red_flags": []}
    for sev in (1, 2, 3):
        for turn in range(6):
            outs = {coach.interject(PERSONA, "小美", last, "我不要這樣", "awake", sev, 0, turn, has_red_flag=h)["text"]
                    for last, h in ((clean, False), (NPC, True), (NPC, None), (clean, None))}
            assert len(outs) == 1, (sev, turn, outs)
            tip = coach.interject(PERSONA, "小美", clean, "x", "awake", sev, 0, turn, has_red_flag=False)
            assert tip["tone"] in ("praise", "neutral")
            assert "沒有紅旗" not in tip["text"] and "不是每句" not in tip["text"]


def test_refusal_lines_vary_with_turn():
    texts = {coach.interject(PERSONA, "小美", NPC, "x", "awake", 1, 0, t)["text"] for t in range(3)}
    assert len(texts) == 3
