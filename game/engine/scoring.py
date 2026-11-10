"""遊戲結算：紅旗辨識（precision + recall）、被騙指數、清醒分數（簡報 p.5）。

公式是暫定版，所有權重集中在這一段，之後依使用者測試調整。

設計原則（會議紀錄 Q2、Q3）
1. 分數 = 辨識能力（紅旗 F1，亂標會被 precision 拉低，另外每次誤檢舉再扣固定分）
        + 行為（實際拒絕多少、順從多少，回「嗯」不算分）
        + 不被帶走（信任與被騙金額）。
2. 沒有互動就沒有分數：不再有「什麼都不做也白送 16 分」的基線。
3. 清醒／戀愛腦判定：選項自帶的 kind 優先（resolve_kind），沒有 kind 的自由輸入才用規則。
"""
from __future__ import annotations

import math
import re
from typing import Optional

# ---------- 權重（調整請改這裡）----------
W_DETECT = 0.45        # 紅旗辨識
W_BEHAVIOR = 0.40      # 行為：對「有紅旗」的訊息拒絕多少、順從多少
W_NOT_FOOLED = 0.15    # 100 - 被騙指數
PRECISION_POWER = 2    # 辨識分 = 100 * recall * precision**2：亂標會被 precision 重罰
FALSE_POSITIVE_PENALTY = 5      # 每次誤檢舉（對照題）額外扣的分數
FLAG_RATE_FREE = 0.7            # 標旗數 / NPC 訊息數 超過這個比例且 precision 低 → 判定亂標，再降分
OVER_REFUSE_WEIGHT = 1.0        # 對「沒有紅旗」的正常訊息也拒絕（過度警覺）：行為分扣 100*比例*權重
NORMAL_CREDIT = 0.5             # 對「沒有紅旗」的正常訊息做出得體的中性回應（非拒絕、非順從）：行為分的正向項（Q51）
MIN_AWAKE_CHARS = 4             # 自由輸入的拒絕少於這個字數（「不要」）不算清醒行為；同一句重複也只算一次
# 被騙指數（越高越被騙，0-100）
W_TRUST, W_BRAIN = 0.3, 0.7
NEUTRAL_AS_BRAIN = 0.5          # 回「嗯」算半個順從：被動不等於清醒
MONEY_PENALTY_PER_EVENT = 10
# 金額（遊戲幣）對分數的影響：log10(1 + 總額/1000) * 係數，最多扣 MONEY_SCORE_CAP 分
MONEY_SCORE_SCALE = 15
MONEY_SCORE_CAP = 45
MONEY_GRADE_CAP = 79            # 只要有匯款事件，清醒分數最高 79（不得進「火眼金睛」）
# 自由輸入抽到「轉帳意圖」但沒講金額時的預設金額（遊戲幣）
DEFAULT_FREE_TEXT_AMOUNT = 5000

GRADES = [
    (80, "火眼金睛", "紅旗一插你就看到，對方話術在你面前是透明的。"),
    (60, "警覺升級", "有警覺，但偶爾還是會心軟。"),
    (40, "觀察中", "你看到了一些紅旗，也有幾次選擇先相信對方，這很常見。"),
    (0, "新手上路", "這一局對方的招數很有效，多數人都會中。看覆盤找出轉折點，下次就能早一步停下來。"),
]


def _ratio(num: float, den: float) -> Optional[float]:
    return num / den if den else None


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _turn_stats(messages: list) -> Optional[dict]:
    """把每則玩家訊息和它前一則 NPC 訊息配對。沒有玩家訊息（舊格式）回 None。

    有效清醒 = 對「有紅旗」的 NPC 句做出的、夠長且不重複的拒絕；
    過度拒絕 = 對「沒有紅旗」的正常句也拒絕。
    """
    players = [m for m in messages if m["role"] == "player"]
    if not players:
        return None
    st = {"good": 0, "bad": 0, "over": 0, "brain": 0, "n": 0, "n_flag": 0, "padded": 0, "normal": 0, "n_clean": 0}
    last_npc, seen = None, {}
    for m in messages:
        if m["role"] == "npc":
            last_npc = m
            continue
        if m["role"] != "player":
            continue
        kind = m.get("kind")
        text = (m.get("text") or "").strip()
        padded = False
        if kind == "awake" and text:
            seen[text] = seen.get(text, 0) + 1
            if len(text) < MIN_AWAKE_CHARS or seen[text] > 1:
                kind = "neutral"
                padded = True
                st["padded"] += 1
        on_flag = bool(last_npc.get("red_flags")) if last_npc is not None else True
        st["n"] += 1
        st["n_flag"] += on_flag
        st["n_clean"] += not on_flag
        if kind == "brain":
            st["brain"] += 1
            st["bad"] += on_flag
        elif kind == "awake":
            st["good" if on_flag else "over"] += 1
        elif not on_flag and not padded:
            st["normal"] += 1
    return st


def compute(state: dict) -> dict:
    npc = [m for m in state["messages"] if m["role"] == "npc"]
    with_flags = [m for m in npc if m.get("red_flags")]
    caught = [m for m in with_flags if m.get("flagged")]
    false_pos = [m for m in npc if m.get("flagged") and not m.get("red_flags")]
    flagged_n = len(caught) + len(false_pos)

    recall = _ratio(len(caught), len(with_flags))
    precision = _ratio(len(caught), flagged_n)

    players = [m for m in state["messages"] if m["role"] == "player"]
    brain = state.get("brain_count") or sum(m.get("kind") == "brain" for m in players)
    awake = state.get("awake_count") or sum(m.get("kind") == "awake" for m in players)
    n_turns = max(state.get("player_turns", 0), len(players), brain + awake)
    money_events = state.get("money_events", [])
    money_total = sum(e["amount"] for e in money_events)

    ts = _turn_stats(state["messages"])
    if ts:
        # 有配對資訊：只算「對有紅旗的訊息」的拒絕／順從；回「嗯」與灌水式拒絕都不加分
        n_turns = max(n_turns, ts["n"])
        eff_brain, eff_awake = ts["brain"], ts["good"] + ts["over"]
        # 滿分 = 每個有紅旗的回合都拒絕 + 每個正常回合都得體回應（各佔 NORMAL_CREDIT）
        best = ts["n_flag"] + NORMAL_CREDIT * ts["n_clean"]
        got = ts["good"] - ts["bad"] + NORMAL_CREDIT * ts["normal"] - OVER_REFUSE_WEIGHT * NORMAL_CREDIT * ts["over"]
        behavior = 100 * got / best if best else 0.0
    else:
        eff_brain, eff_awake = brain, awake
        behavior = 100 * (awake - brain) / n_turns if n_turns else 0.0
    behavior = _clamp(behavior)
    neutral = max(0, n_turns - eff_brain - eff_awake)

    # 被騙指數：信任度 + 順從份額（回「嗯」算半個順從）+ 轉帳事件
    brain_share = (eff_brain + NEUTRAL_AS_BRAIN * neutral) / n_turns if n_turns else NEUTRAL_AS_BRAIN
    fooled = W_TRUST * state["trust"] + W_BRAIN * 100 * brain_share
    fooled += MONEY_PENALTY_PER_EVENT * len(money_events)
    fooled = int(round(_clamp(fooled)))

    # 辨識分：recall * precision^2，再扣誤檢舉與亂標
    flag_rate = flagged_n / len(npc) if npc else 0.0
    detect = 100 * (recall or 0) * (precision or 0) ** PRECISION_POWER
    spam = max(0.0, flag_rate - FLAG_RATE_FREE) / (1 - FLAG_RATE_FREE)
    detect *= 1 - spam * (1 - (precision or 0))
    detect = _clamp(detect - FALSE_POSITIVE_PENALTY * len(false_pos))

    if n_turns == 0 and not any(m.get("flagged") for m in npc):
        awake_score = 0  # 沒互動就沒分數
    else:
        awake_score = W_DETECT * detect + W_BEHAVIOR * behavior + W_NOT_FOOLED * (100 - fooled)
        if money_total:
            awake_score -= min(MONEY_SCORE_CAP, MONEY_SCORE_SCALE * math.log10(1 + money_total / 1000))
        if money_events:
            awake_score = min(awake_score, MONEY_GRADE_CAP)
        awake_score = int(round(_clamp(awake_score)))
    grade = next(g for g in GRADES if awake_score >= g[0])

    return {
        "recall": None if recall is None else round(recall * 100),
        "precision": None if precision is None else round(precision * 100),
        "flags_total": len(with_flags),
        "flags_caught": len(caught),
        "false_positives": len(false_pos),
        "flag_rate": round(flag_rate * 100),
        "fooled_index": fooled,
        "detect_score": int(round(detect)),
        "behavior_score": int(round(behavior)),
        "awake_score": awake_score,
        "grade": grade[1],
        "grade_note": grade[2],
        "brain_choices": brain,
        "awake_choices": awake,
        "over_refusals": ts["over"] if ts else 0,
        "money_lost": money_total,
    }


# =====================================================================
# 清醒／戀愛腦判定（Q3、Q32）
# =====================================================================
_NEG = "不沒別未無勿"
_CLAUSE_SPLIT = re.compile(r"[，,。.！!？?；;、~～…\s]+")

# 拒絕／守界線
_AWAKE_RULES = re.compile("|".join([
    r"不(要|行|能|可以|可能|會|想|用|肯|借|給|轉|匯|買|投資|答應|去|信|相信|上當|被騙|再)",
    r"沒辦法", r"辦不到", r"拒絕", r"才不(信|會|要|想)", r"先不", r"免了",
    r"界線", r"我需要", r"我決定", r"我想要穩定", r"檢舉", r"165", r"報警", r"封鎖",
    r"證據", r"視訊", r"見面再說", r"見面談", r"保重", r"各自的生活", r"晚點回", r"我的感受", r"不是想太多",
    r"這是詐騙", r"像詐騙", r"是詐騙吧", r"你是詐騙", r"是詐騙[!！。]",
    r"為什麼要(問|借|匯|轉)",
]))
# 弱順從詞：禮貌用語，遇到拒絕就失效（修「對不起我不能」）
_WEAK_BRAIN = re.compile(r"沒關係|都可以|不介意|算了|沒差|隨便你|我不會怪你|你開心就好|我可以等")
# 情感上的強順從
_EMO_BRAIN = re.compile("|".join([
    r"我馬上", r"秒回", r"都聽你", r"我等你", r"我愛你", r"我去辦", r"不會離開", r"永遠",
    r"寶貝", r"是我想太多", r"我的錯", r"是我不好", r"我會改",
]))
# 轉帳／給錢意圖（要在同一子句且未被否定才算）
_MONEY_INTENT = re.compile("|".join([
    r"我(先|再|馬上|現在|立刻|明天|今天|等一下|就|會|願意)?(轉|匯)(?!頭|學|身|眼|職|換|移|貼|載|念|行|運|彎|角|過來給我)",
    r"(轉|匯)(給你|你)", r"借(你|給你)", r"(給|付)你錢", r"付給你", r"把(錢|存款|積蓄|薪水)(都|全部|全)?(給|轉|匯|借)",
    r"(存款|積蓄|薪水|錢)(都|全部|全)(給|轉|匯|借)", r"全部(都)?(給|轉|匯)你", r"(領錢|提款|ATM)", r"代墊",
    r"幫你(付|墊|出)", r"(?<=不會不)(轉|匯|給|借)", r"(?<=不是不)(轉|匯|給|借)", r"(轉帳|匯款)(給|過去)", r"(轉帳|匯款|匯|轉)過去", r"買了?(點數|遊戲點數|禮物卡|序號)", r"拍.{0,3}序號", r"已(經)?(匯款|轉帳|匯|轉)", r"(轉|匯)了(\d|[一二兩三四五六七八九十百千萬])",
]))
_ASKED_OF_ME = "要叫讓請逼教"   # 「你要我轉」「他叫我匯」是對方的要求，不是玩家的意圖
_QUESTION_END = re.compile(r"[嗎吧呢?？]$")


def _clauses(text: str) -> list:
    return [c for c in _CLAUSE_SPLIT.split(text or "") if c]


def _neg_parity(clause: str, start: int) -> int:
    """match 前 3 個字內的否定字數（偶數＝沒被否定或雙重否定）。"""
    head = re.sub(r"對不起|不好意思|不要緊|不客氣", "", clause[:start])
    return sum(c in _NEG for c in head[-3:])


def _affirmative(pattern: "re.Pattern", clause: str) -> Optional["re.Match"]:
    for m in pattern.finditer(clause):
        if _neg_parity(clause, m.start()) % 2:
            continue
        if m.start() > 0 and clause[m.start() - 1] in _ASKED_OF_ME and clause[m.start()] == "我":
            continue
        if m.start() > 1 and clause[m.start() - 2] in _ASKED_OF_ME and clause[m.start() - 1] == "我":
            continue
        return m
    return None


def _money_clause(text: str) -> Optional[str]:
    """回傳含有未被否定的轉帳意圖的子句；拒絕詞只在「同一子句」才會讓轉帳意圖失效。"""
    for c in _clauses(text):
        if _affirmative(_MONEY_INTENT, c):
            # 同子句出現拒絕且不是被前面否定字吃掉的情況（例如「不轉」已在 _affirmative 排除）
            return c
    return None


def has_money_intent(text: str) -> bool:
    return _money_clause(text) is not None


def classify_text(text: str) -> str:
    """規則版判定（只給自由輸入用）。回傳 brain / awake / neutral。

    - 有轉帳意圖（我轉你、把錢都給你、已匯款…）→ brain，即使別的子句有「不要客氣」
    - 拒絕詞只在與轉帳「同一子句」且為否定時才抵銷（我不轉、我不能轉給你）
    - 雙重否定（我不會不轉）算轉帳
    - 禮貌詞（對不起、好啊）不抵銷拒絕；純提問不算表態
    - 拒絕與情感性順從並存 → neutral
    """
    t = re.sub(r"\s+", "", text or "")
    if not t:
        return "neutral"
    if has_money_intent(t):
        return "brain"
    awake = bool(_AWAKE_RULES.search(t))
    if awake and _QUESTION_END.search(t) and not re.search(r"不|沒|拒|才不|165|檢舉|封鎖|報警", t):
        awake = False
    emo = any(_affirmative(_EMO_BRAIN, c) for c in _clauses(text))
    if awake and emo:
        return "neutral"
    if awake:
        return "awake"
    weak = any(_affirmative(_WEAK_BRAIN, c) for c in _clauses(text))
    if emo or weak:   # 替對方找理由、無條件讓步（沒關係、都可以、你開心就好）
        return "brain"
    # 只有禮貌／附和（好啊、嗯嗯我了解、謝謝你）不構成順從：回 neutral，由配對邏輯依對方有無紅旗給中性評價（Q51）
    return "neutral"


def resolve_kind(kind: Optional[str], text: str = "") -> str:
    """選項帶了 kind（brain/awake）就用它；沒有（自由輸入）才用規則。"""
    if kind in ("brain", "awake"):
        return kind
    return classify_text(text)


_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_UNITS = {"十": 10, "百": 100, "千": 1000}
_AMOUNT = re.compile(r"(\d[\d,]*(?:\.\d+)?|[零〇一二兩三四五六七八九十百千]+)\s*(萬|万|千|百|k|K)?\s*(?:塊|元|圓|台幣|NT)?")


def _cn_number(s: str) -> Optional[int]:
    if not s or not all(c in _DIGITS or c in _UNITS for c in s):
        return None
    total, cur = 0, 0
    for c in s:
        if c in _DIGITS:
            cur = _DIGITS[c]
        else:
            total += (cur or 1) * _UNITS[c]
            cur = 0
    return total + cur


def _amount_in(t: str) -> Optional[int]:
    for m in _AMOUNT.finditer(t):
        raw, unit = m.group(1), m.group(2)
        if not unit and not re.search(r"塊|元|圓|台幣", m.group(0)) and len(raw.replace(",", "")) < 3:
            continue  # 單獨的小數字不當金額（「我轉3次」）
        base = float(raw.replace(",", "")) if raw[0].isdigit() else _cn_number(raw)
        if base is None:
            continue
        mult = {"萬": 10000, "万": 10000, "千": 1000, "百": 100, "k": 1000, "K": 1000}.get(unit or "", 1)
        value = int(base * mult)
        if value > 0:
            return value
    return None


def money_in_text(text: str) -> int:
    """從自由輸入抽出玩家「要轉出去的金額」。與 kind 無關：有轉帳意圖就抽。

    沒有轉帳意圖，或轉帳被同子句否定 → 0。有意圖但沒講金額 → DEFAULT_FREE_TEXT_AMOUNT。
    """
    clause = _money_clause(text)
    if clause is None:
        return 0
    amount = _amount_in(clause)
    if amount is None:
        # 金額可能在別的子句（「我轉你，三萬」）：只在含金額的子句找，不管拒絕詞
        amount = _amount_in(re.sub(r"\s+", "", text))
    return amount or DEFAULT_FREE_TEXT_AMOUNT
