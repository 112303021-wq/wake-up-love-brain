"""罵醒教練（mock 版）。

原則（簡報 p.9 風險控管、會議紀錄 Q4）：
- 預設尺度是溫柔（DEFAULT_SEVERITY = 1）；毒舌、地獄要玩家主動開。
- 只批評「對方的手法」與「這個選擇」，不定義人：不用提款機、垃圾桶、蠢、笨、戀愛腦末期這類標籤。
- 每句引用對方的原話與紅旗，不拿玩家自己說的話來嘲諷。
- 低分覆盤不嘲笑，一定附下一步。
severity：1 溫柔提醒、2 毒舌、3 地獄（誇張戲劇化，但仍只針對手法）。
接上 Claude 後，可以把這裡換成另一支 coach prompt。
"""
from __future__ import annotations

from typing import Dict, List, Optional

SEVERITY_NAMES = {1: "溫柔提醒", 2: "毒舌", 3: "地獄"}
DEFAULT_SEVERITY = 1

# 每個情境、每個尺度至少 3 句；用 turn 輪替避免重複
TEMPLATES: Dict[str, Dict[int, List[str]]] = {
    # 對方這句有紅旗，玩家選了順從。可用 {npc} {quote} {flag}
    "roast_flag": {
        1: [
            "先停一下～{npc}剛剛說「{quote}」，這其實是「{flag}」。很多人聽到這種話都會心軟，你有注意到嗎？",
            "{npc}說「{quote}」，這個手法叫「{flag}」。你回得很有誠意，不過可以先想想：對方這句是在關心你，還是在把你往他要的方向帶？",
            "輕輕提醒一下：「{quote}」是「{flag}」的典型說法。不用自責，這招本來就設計得讓人很難拒絕。",
        ],
        2: [
            "停。「{quote}」——這叫{flag}，教科書級的。這個選擇有點讓步過頭了，下一句想想怎麼守住自己。",
            "{npc}這句「{quote}」就是{flag}，招數很老但很有效。你這一步被帶著走了，下一步可以拿回節奏。",
            "好，我直說：「{quote}」是{flag}，你的回應等於告訴對方這招有用。換個回法試試？",
        ],
        3: [
            "醒醒！「{quote}」是「{flag}」，紅旗插滿整面牆，而你這一步剛好踩進對方的劇本裡。這招厲害，但你可以不接。",
            "醒醒醒醒！{npc}丟出「{quote}」，標準的{flag}，這個選擇等於幫對方把戲演下去。重新想一遍，這句話你真的要接嗎？",
            "警報大響！「{quote}」＝{flag}。這個回法會讓對方的手法繼續得逞，回頭看看這句，有哪個字讓你想踩煞車？",
        ],
    },
    # 對方這句沒紅旗，玩家卻很順從
    "roast_no_flag": {
        1: [
            "對方這句看起來還算正常。不過你這步已經有點先退讓了，留意一下自己真正想要的是什麼。",
            "這句話本身沒有明顯問題，但你的回應有點急著配合對方，慢一點也沒關係。",
            "對方這句不算紅旗。只是提醒你：答應之前，先問問自己願不願意，會比較踏實。",
        ],
        2: [
            "對方還沒出什麼招，你這步就先退讓了。這個選擇可以再保留一點空間。",
            "這句沒有紅旗，但你的回應給得有點快，沒必要一開始就全盤接受。",
            "沒事的訊息不需要馬上讓步。這個選擇偏急了，下一句可以說慢一點。",
        ],
        3: [
            "人家什麼招都還沒出，你就先把門打開了。這個選擇太趕了，退一步再看看。",
            "對方沒出事，是你這步先自己讓太多。請把這個選擇收回來，重新決定。",
            "沒有紅旗也不用急著配合。這個選擇像開了自動導航，換成手動駕駛吧。",
        ],
    },
    # 轉帳。{amount}
    "money": {
        1: [
            "你剛剛「轉」了 {amount:,} 元。遊戲裡是假的，現實裡這種匯款很難追回，真遇到先打 165 問問。",
            "這一步轉出了 {amount:,} 元。這類手法的重點就是讓人在情緒裡做決定，現實中遇到可以先停下來打 165。",
            "{amount:,} 元的匯款，在現實中通常追不回來。記得：任何要你匯錢的情境，先暫停、先查證。",
        ],
        2: [
            "{amount:,} 元就這樣匯出去了，而且還沒見過面。現實中這步很難回頭，下次先查證再說。",
            "轉了 {amount:,} 元。這就是對方一路鋪陳要的結果，現實裡這種錢很難拿回來。",
            "{amount:,} 元匯出，對方的目標達成。想想看，哪一步可以更早喊停？",
        ],
        3: [
            "{amount:,} 元匯出去了！整場鋪陳就是為了這一刻，現實中這筆錢幾乎追不回來，165 的號碼現在就存起來。",
            "警報！{amount:,} 元離開帳戶。對方的手法成功了，你的錢卻回不來，下次在這一步前先打 165。",
            "{amount:,} 元，一步到位。這是詐騙流程的終點，不是你的終點，從這裡學會在更早的地方停下來。",
        ],
    },
    # 對「拒絕」的回饋：不論對方那句有沒有紅旗，形式、字數、用詞都一樣（Q67）。
    # 這句有沒有紅旗，延到結算才揭露；否則玩家可以從教練的反應反推答案。
    "praise": {
        1: [
            "收到，你選擇了拒絕。對方這句有沒有問題，結算時會一起說明，先繼續聊吧。",
            "好的，這句你選擇了守住界線。是否真有紅旗，結算時再看，先繼續。",
            "記下了，這句你選擇拒絕。答案留到結算，現在先看對方怎麼回。",
        ],
        2: [
            "收到，這句你拒絕了。是不是真有紅旗，結算再揭曉，繼續。",
            "記下，你選擇了拒絕。對錯留到結算，先看對方怎麼接。",
            "好，拒絕這步記下了。這句是不是紅旗，結算見分曉。",
        ],
        3: [
            "收到，拒絕！至於對方這句是不是真有鬼，結算時才揭曉，繼續衝。",
            "記下了，你拒絕了這句。答案先賣個關子，結算見真章。",
            "拒絕這步登記完畢。這句到底是不是紅旗，結算時攤牌。",
        ],
    },
    # 結算：漏掉的紅旗。{text} {meaning}
    "review_missed": {
        1: [
            "這場有一則「{text}」沒標到，它是{meaning}。下次看到類似的話，可以多停一秒。",
            "「{text}」是{meaning}，這次沒抓到很正常，這種話術本來就容易被忽略。",
            "回頭看「{text}」，這是{meaning}。知道它長什麼樣，下次就比較容易認出來。",
        ],
        2: [
            "「{text}」這句沒抓到，是{meaning}。重點在於它聽起來很合理，下次多問自己一句為什麼。",
            "你漏了「{text}」，它是{meaning}。這手法常常包在關心裡，才更難認。",
            "「{text}」＝{meaning}，這題被對方過關了。記住它的樣子。",
        ],
        3: [
            "「{text}」這句紅旗直接從你眼前飄過去了，它是{meaning}。對方的包裝很會，下次盯緊這類說法。",
            "「{text}」是{meaning}，這次被對方藏過去了。回頭再看一次，哪個字該警覺？",
            "「{text}」＝{meaning}，漏接一顆。下一局專抓這類話術。",
        ],
    },
    "review_money": {
        1: [
            "這場一共匯出 {amount:,} 元（遊戲幣）。現實中這通常很難追回，遇到類似狀況先打 165。",
            "遊戲中損失了 {amount:,} 元。這是練習用的，重點是記住是哪一步讓你決定匯款。",
            "共 {amount:,} 元（遊戲幣）離開了帳戶。真實世界裡，被要求匯款時先暫停、先查證。",
        ],
        2: [
            "這場匯出 {amount:,} 元（遊戲幣）。現實裡這類錢很難回來，回頭找找是哪一步讓你點頭。",
            "{amount:,} 元（遊戲幣）被對方拿走。想想看哪個時間點最適合喊停。",
            "損失 {amount:,} 元（遊戲幣）。對方的鋪陳很完整，下次在要錢之前就先踩煞車。",
        ],
        3: [
            "這場 {amount:,} 元（遊戲幣）進了對方口袋。現實裡這種錢追不回來，所以更要在要錢之前就看穿。",
            "{amount:,} 元（遊戲幣）離場。這就是詐騙的終點，從這一局找出你可以更早喊停的位置。",
            "{amount:,} 元（遊戲幣）沒了。別怪自己，檢討對方的鋪陳，下一局就在那裡煞車。",
        ],
    },
    "review_high": {
        1: ["很棒，繼續保持！", "做得很好，你對這些話術已經很有警覺了。", "表現很穩，這些判斷力在現實中很有用。"],
        2: ["還行，算你醒著。", "不錯，這局你守得住。", "這局穩，換個難一點的人格試試？"],
        3: ["嘖，這次罵不到你。", "這局對方沒討到便宜，漂亮。", "滿分表現，對手下次得換新招了。"],
    },
    "review_mid": {
        1: ["你已經認出一部分手法了，再多練幾局會更穩。", "有些地方抓得到，有些還會心軟，這都很正常。", "進步空間不少，也有不錯的基礎，看一下漏掉的那幾則吧。"],
        2: ["半對半錯。抓得到的地方不錯，漏的地方多看兩眼。", "有警覺但還不夠一致，漏掉的那幾題是關鍵。", "這局五五波，下一局把漏的那幾類記住。"],
        3: ["這局有亮點也有破口，破口那幾則就是對方得分的地方。", "對方抓到幾個縫，把那幾個縫補起來。", "別放鬆，對方有幾招你還沒完全看穿。"],
    },
    "review_low": {
        1: [
            "這局對方的招數很有效，多數人都會中。下一步：先看覆盤裡標出來的紅旗，再重玩一次。",
            "沒關係，這類手法本來就設計得讓人難以招架。下一步：挑一則漏掉的紅旗，想想怎麼回。",
            "你願意玩完並看覆盤，就已經很不容易。下一步：記住被漏掉的那幾種說法。",
        ],
        2: [
            "這局被對方牽著走了。這不代表你不行，而是對方招數成熟。下一步：重玩，專心抓前三個紅旗。",
            "分數偏低，原因主要是前面太快讓步。下一步：看覆盤，找出第一次該拒絕的地方。",
            "對方的鋪陳很完整，你被推著走。下一步：挑一個人格，重打一次並先拒絕一次。",
        ],
        3: [
            "這局對方整套劇本跑完了，這種鋪陳連老手都會中。下一步：看覆盤，找出最早能喊停的那一句，下局就從那裡開始。",
            "大敗，但資訊量很大：你現在知道對方整套流程長怎樣了。下一步：重玩，把第一個紅旗標出來。",
            "這局被對方一路帶著走，也算看完了整套詐騙流程。下一步：回看覆盤，找轉折點，下一局在那裡煞車。",
        ],
    },
}


def _pick(scenario: str, severity: int, seed: int) -> str:
    options = TEMPLATES[scenario][severity]
    return options[seed % len(options)]


def _norm_severity(severity) -> int:
    return severity if severity in SEVERITY_NAMES else DEFAULT_SEVERITY


def _short(text: str, n: int = 24) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= n else text[:n] + "…"


def interject(persona, npc_name: str, last_npc: Optional[dict], player_text: str,
              kind: str, severity: int, money: int = 0, turn: int = 0,
              has_red_flag: Optional[bool] = None) -> Optional[dict]:
    """玩家每回合之後，教練要不要插話。回傳 None 代表不插話。

    不再引用玩家自己的原話。拒絕的回饋文字與對方有無紅旗無關（答案延到結算）；has_red_flag=False 只讓 tone 變 neutral（前端須同樣渲染）（避免嘲諷式複誦），只引用對方的話與紅旗。
    """
    severity = _norm_severity(severity)
    if kind == "awake":
        # 文字刻意不隨 has_red_flag 變化（Q67）。tone 仍依它回 praise/neutral 以相容既有契約與測試，
        # 前端必須把兩種 tone 渲染成完全一樣（同圖示、同顏色），否則 tone 本身就是答案。
        if has_red_flag is False:
            return {"tone": "neutral", "text": _pick("praise", severity, turn)}
        return {"tone": "praise", "text": _pick("praise", severity, turn)}
    if kind != "brain":
        return None
    flags = (last_npc or {}).get("red_flags") or []
    if flags:
        text = _pick("roast_flag", severity, turn).format(
            npc=npc_name, quote=_short(last_npc["text"]), flag=persona.flag_meaning(flags[0]))
    else:
        text = _pick("roast_no_flag", severity, turn)
    if money:
        text += "\n" + _pick("money", severity, turn).format(amount=money)
    return {"tone": "roast", "text": text}


def review(persona, npc_name: str, state: dict, scores: dict, severity: int,
           past: List[dict]) -> dict:
    """結算覆盤：逐則列出紅旗（抓到／漏掉／誤判），加上教練總評。"""
    severity = _norm_severity(severity)
    items = []
    for m in state["messages"]:
        if m["role"] != "npc":
            continue
        flags = m.get("red_flags") or []
        if not flags and not m.get("flagged"):
            continue
        status = "caught" if flags and m.get("flagged") else ("missed" if flags else "false_positive")
        items.append({
            "text": m["text"],
            "status": status,
            "flags": [{"code": f, "meaning": persona.flag_meaning(f)} for f in flags],
        })

    seed = len(state["messages"]) + scores["awake_score"]
    s = scores["awake_score"]
    grade = scores["grade"]
    lines = [f"【{grade}】{scores['grade_note']}"]
    missed = [i for i in items if i["status"] == "missed"]
    if missed:
        top = missed[0]
        lines.append(_pick("review_missed", severity, seed).format(
            text=_short(top["text"]), meaning=top["flags"][0]["meaning"]))
    if scores.get("false_positives"):
        lines.append(f"另外有 {scores['false_positives']} 則其實是正常訊息被你標成紅旗。保持警覺很好，但不是每句話都有問題，分辨出來也是能力。")
    if scores["money_lost"]:
        lines.append(_pick("review_money", severity, seed).format(amount=scores["money_lost"]))
    if s >= 80:
        lines.append(_pick("review_high", severity, seed))
    elif s < 40:
        lines.append(_pick("review_low", severity, seed))
    else:
        lines.append(_pick("review_mid", severity, seed))

    prev = [p for p in past if p.get("persona_id") != persona.id]
    if prev:
        p = prev[-1]
        lines.append(f"（教練記得你：上次跟「{p['persona_title']}」玩，清醒分數 {p['awake_score']}。）")

    return {
        "severity": severity,
        "severity_name": SEVERITY_NAMES[severity],
        "comment": "\n".join(lines),
        "items": items,
    }
