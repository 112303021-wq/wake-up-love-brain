import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import scoring  # noqa: E402

N_FLAGGED, N_CONTROL = 9, 4   # 約 1/3 無紅旗的對照訊息（後端 B 的 mock 之後也會如此）


def build_state(reply, flag, trust0=40, n_flagged=N_FLAGGED, n_control=N_CONTROL, money_every=0, text=None):
    """模擬一局。reply(i, has_flag)->'brain'|'awake'|'neutral'；flag(i, has_flag)->bool 是否按 🚩。"""
    msgs, brain, awake, trust, turns, money = [], 0, 0, trust0, 0, []
    delta = {"brain": 10, "awake": -10, "neutral": 2}
    has = [True] * n_flagged + [False] * n_control
    random.Random(7).shuffle(has)
    for i, h in enumerate(has):
        msgs.append({"role": "npc", "text": f"m{i}", "red_flags": ["x"] if h else [], "flagged": flag(i, h)})
        k = reply(i, h)
        t = text(i) if text else f"這是我第{i}次的完整回應內容"
        msgs.append({"role": "player", "kind": k, "text": t})
        turns += 1
        brain += k == "brain"
        awake += k == "awake"
        trust = max(0, min(100, trust + delta[k]))
        if money_every and k == "brain" and i % money_every == 0:
            money.append({"amount": 10000})
    return {"messages": msgs, "brain_count": brain, "awake_count": awake, "trust": trust,
            "player_turns": turns, "money_events": money}


def score(**kw):
    return scoring.compute(build_state(**kw))["awake_score"]


def smart_reply(i, h):
    return "awake" if h else "neutral"   # 對有紅旗的拒絕，對正常訊息正常回


STRATEGIES = {
    "sensible": dict(reply=smart_reply, flag=lambda i, h: h),
    "refuse_all_no_flag": dict(reply=lambda i, h: "awake", flag=lambda i, h: False),
    "refuse_all_flag_all": dict(reply=lambda i, h: "awake", flag=lambda i, h: True),
    "refuse_all_flag_correct": dict(reply=lambda i, h: "awake", flag=lambda i, h: h),
    "passive_flag_all": dict(reply=lambda i, h: "neutral", flag=lambda i, h: True),
    "passive_no_flag": dict(reply=lambda i, h: "neutral", flag=lambda i, h: False),
    "brain_no_flag": dict(reply=lambda i, h: "brain", flag=lambda i, h: False),
    "brain_flag_all": dict(reply=lambda i, h: "brain", flag=lambda i, h: True),
    "brain_money": dict(reply=lambda i, h: "brain", flag=lambda i, h: False, money_every=2),
    "half_flags": dict(reply=smart_reply, flag=lambda i, h: h and i % 2 == 0),
    "short_no_spam_flag_all": dict(reply=lambda i, h: "awake", flag=lambda i, h: True, text=lambda i: "不要"),
}


def test_sensible_strategy_is_top_and_is_warrior():
    scores = {k: score(**v) for k, v in STRATEGIES.items()}
    best = max(scores, key=scores.get)
    assert best == "sensible", scores
    assert scores["sensible"] >= 80
    assert all(v < scores["sensible"] for k, v in scores.items() if k != "sensible")


def test_single_word_refusal_spam_plus_flag_all_is_not_high():
    """Q28：每回合「不要」＋全標 🚩 不得拿高分（有對照題時必低於 60）。"""
    assert score(**STRATEGIES["short_no_spam_flag_all"]) < 60
    assert score(**STRATEGIES["refuse_all_flag_all"]) < 60


def test_blind_refuse_everything_loses_to_discernment():
    assert score(**STRATEGIES["refuse_all_flag_correct"]) < score(**STRATEGIES["sensible"]) - 8


def test_repeated_same_refusal_text_counts_once():
    rep = score(reply=smart_reply, flag=lambda i, h: h, text=lambda i: "我不要這樣做的啦")
    assert rep < score(**STRATEGIES["sensible"]) - 20


def test_money_sensitivity_q39():
    """一路 brain 並匯出大筆錢，不得與全 neutral 只差一點點；有匯款不得進火眼金睛。"""
    kw = dict(n_flagged=13, n_control=0, flag=lambda i, h: True)   # 舊 mock：每句都有紅旗
    big = {"messages": build_state(reply=lambda i, h: "brain", **kw)["messages"],
           "brain_count": 13, "awake_count": 0, "trust": 100, "player_turns": 13,
           "money_events": [{"amount": 10000}, {"amount": 50000}, {"amount": 220000}]}
    passive = build_state(reply=lambda i, h: "neutral", **kw)
    a, b = scoring.compute(big), scoring.compute(passive)
    assert b["awake_score"] - a["awake_score"] >= 25, (a["awake_score"], b["awake_score"])
    assert a["money_lost"] == 280000
    smart_paid = build_state(**STRATEGIES["sensible"])
    smart_paid["money_events"] = [{"amount": 3000}]
    assert scoring.compute(smart_paid)["awake_score"] <= scoring.MONEY_GRADE_CAP
    assert scoring.compute(smart_paid)["grade"] != "火眼金睛"


def test_larger_amount_scores_lower():
    base = build_state(**STRATEGIES["sensible"])
    small = dict(base, money_events=[{"amount": 1000}])
    large = dict(base, money_events=[{"amount": 300000}])
    assert scoring.compute(large)["awake_score"] < scoring.compute(small)["awake_score"]


def test_mock_without_control_messages_still_gated_by_behavior():
    """舊 mock（每句都有紅旗）：全標 🚩 抓不出來，但「不要」灌水與全嗯不能拿高分。"""
    kw = dict(n_flagged=13, n_control=0, flag=lambda i, h: True)
    assert score(reply=lambda i, h: "awake", text=lambda i: "不要", **kw) < 60
    assert score(reply=lambda i, h: "neutral", **kw) < 60
    assert score(reply=lambda i, h: "brain", **kw) <= 45
    good = score(reply=lambda i, h: "awake", **kw)
    assert good >= 80


def test_all_hum_plus_flag_everything_is_not_high_score():
    s = scoring.compute(build_state(**STRATEGIES["passive_flag_all"]))
    assert s["awake_score"] < 60 and s["grade"] != "火眼金睛"
    assert s["precision"] < 100  # 對照題讓亂標暴露


def test_all_no_with_no_flags_is_not_top():
    s = score(**STRATEGIES["refuse_all_no_flag"])
    assert s < score(**STRATEGIES["sensible"]) - 20


def test_all_brain_scores_lowest_tier():
    assert score(**STRATEGIES["brain_flag_all"]) < 60
    assert score(**STRATEGIES["brain_no_flag"]) < 40
    assert score(**STRATEGIES["brain_money"]) < 40


def test_control_false_positive_is_penalised():
    base = scoring.compute(build_state(**STRATEGIES["sensible"]))
    one_fp = STRATEGIES["sensible"].copy()
    first_control = {}

    def flag(i, h, _seen=first_control):
        if h:
            return True
        if not _seen:
            _seen[i] = True
            return True
        return False
    one_fp["flag"] = flag
    worse = scoring.compute(build_state(**one_fp))
    assert worse["false_positives"] == 1
    assert worse["precision"] < 100
    assert base["awake_score"] - worse["awake_score"] >= 5


def test_flag_spam_loses_to_selective_flagging_across_seeds():
    for seed in range(20):
        rng = random.Random(seed)
        spam = score(reply=lambda i, h: "awake", flag=lambda i, h: True)
        smart = score(reply=lambda i, h: "awake", flag=lambda i, h: h)
        assert smart > spam, seed


def test_random_strategies_never_beat_sensible():
    best = score(**STRATEGIES["sensible"])
    for seed in range(200):
        rng = random.Random(seed)
        reps = [rng.choice(["brain", "awake", "neutral"]) for _ in range(N_FLAGGED + N_CONTROL)]
        flags = [rng.random() < rng.random() for _ in range(N_FLAGGED + N_CONTROL)]
        s = score(reply=lambda i, h: reps[i], flag=lambda i, h: flags[i])
        assert s < best, (seed, s)


def test_random_average_is_mediocre():
    vals = []
    for seed in range(200):
        rng = random.Random(seed)
        reps = [rng.choice(["brain", "awake", "neutral"]) for _ in range(13)]
        flags = [rng.random() < 0.5 for _ in range(13)]
        vals.append(score(reply=lambda i, h: reps[i], flag=lambda i, h: flags[i]))
    assert sum(vals) / len(vals) < 50


def test_no_interaction_gives_zero():
    s = scoring.compute({"messages": [{"role": "npc", "red_flags": ["x"], "flagged": False}],
                         "brain_count": 0, "awake_count": 0, "trust": 40, "money_events": []})
    assert s["awake_score"] == 0


def test_money_events_reduce_score_and_are_summed():
    clean = build_state(**STRATEGIES["sensible"])
    paid = dict(clean, money_events=[{"amount": 10000}, {"amount": 5000}])
    a, b = scoring.compute(clean), scoring.compute(paid)
    assert b["money_lost"] == 15000 and b["awake_score"] < a["awake_score"]


def test_scores_stay_in_range():
    for v in STRATEGIES.values():
        r = scoring.compute(build_state(**v))
        assert 0 <= r["awake_score"] <= 100 and 0 <= r["fooled_index"] <= 100


def test_weights_sum_to_one():
    assert abs(scoring.W_DETECT + scoring.W_BEHAVIOR + scoring.W_NOT_FOOLED - 1) < 1e-9


# ---------- kind 與規則 ----------
def test_resolve_kind_prefers_given_kind():
    assert scoring.resolve_kind("awake", "對不起我愛你好啊") == "awake"
    assert scoring.resolve_kind("brain", "我不要轉") == "brain"
    assert scoring.resolve_kind(None, "我不要轉") == "awake"
    assert scoring.resolve_kind("neutral", "我轉你") == "brain"  # neutral 不是有效 kind，走規則
    assert scoring.resolve_kind("", "嗯") == "neutral"


@pytest.mark.parametrize("text,expected", [
    ("對不起我不能", "awake"),
    ("對不起，我不能借你錢", "awake"),
    ("不好意思我不要轉你好啊", "awake"),
    ("我先不轉", "awake"),
    ("我不能轉給你", "awake"),
    ("好啊 我才不信你是詐騙", "awake"),
    ("我不會轉帳，這是詐騙", "awake"),
    ("我轉你", "brain"),
    ("我轉你3萬", "brain"),
    ("好啊沒關係，我等你", "brain"),
    ("對不起是我的錯", "brain"),
    ("他是詐騙嗎", "neutral"),
    ("我不是詐騙", "neutral"),
    ("今天天氣不錯", "neutral"),
    ("嗯", "neutral"),
    ("", "neutral"),
])
def test_classify_text(text, expected):
    assert scoring.classify_text(text) == expected, text


@pytest.mark.parametrize("text,amount", [
    ("我轉你", scoring.DEFAULT_FREE_TEXT_AMOUNT),
    ("我轉你3萬", 30000),
    ("我轉你三萬", 30000),
    ("轉給你30,000元", 30000),
    ("我借你五千", 5000),
    ("我匯給你1萬2", 10000),
    ("我不轉3萬", 0),
    ("我不能轉給你", 0),
    ("對不起我不能", 0),
    ("今天花了3萬買東西", 0),
    ("嗯", 0),
])
def test_money_in_text(text, amount):
    assert scoring.money_in_text(text) == amount, text


# ---------- 第 6 輪：入戲轉帳、禮貌自然回覆（Q48、Q51）----------
@pytest.mark.parametrize("text", ["我剛剛匯了五萬到你的帳戶", "我已經買了點數拍序號給你", "我轉你五萬，不要客氣"])
def test_in_game_transfer_counts_as_money_event(text):
    assert scoring.classify_text(text) == "brain"
    assert scoring.money_in_text(text) > 0


@pytest.mark.parametrize("text", [
    "謝謝你，我也覺得跟你聊天很開心", "好呀，那我們週末再約，慢慢認識", "嗯嗯我了解，我們先這樣安排", "好啊，那就這樣",
])
def test_polite_natural_replies_are_not_brain(text):
    assert scoring.classify_text(text) == "neutral", text


def test_normal_reply_to_clean_message_earns_behavior_credit():
    base = dict(reply=lambda i, h: "awake" if h else "neutral", flag=lambda i, h: h)
    cold = dict(reply=lambda i, h: "awake" if h else "brain", flag=lambda i, h: h)
    a = scoring.compute(build_state(**base))
    # 對正常訊息得體回應 >= 對正常訊息順從（brain 不拿正常回應的加分）
    b = scoring.compute(build_state(**cold))
    assert a["behavior_score"] >= b["behavior_score"]
    assert a["behavior_score"] == 100


# ---------- Q67：教練回饋不能當標旗答案 ----------
def test_always_refuse_and_flag_only_praised_is_far_below_baseline():
    from engine import coach
    from engine.personas import load_personas
    persona = load_personas()["scammer"]
    praised = set()
    ref = build_state(reply=lambda i, h: "awake", flag=lambda i, h: False)
    npc = [m for m in ref["messages"] if m["role"] == "npc"]
    for i, m in enumerate(npc):
        tip = coach.interject(persona, "小美", m, "我不接受這樣的要求", "awake", 1, 0, i,
                              has_red_flag=bool(m["red_flags"]))
        if tip and "沒有紅旗" not in tip["text"]:   # 玩家看得到的是文字；前端須把 praise/neutral 渲染得一樣
            praised.add(i)
    exploit = score(reply=lambda i, h: "awake", flag=lambda i, h: i in praised)
    baseline = score(**STRATEGIES["sensible"])
    assert exploit <= baseline - 15, (exploit, baseline)
