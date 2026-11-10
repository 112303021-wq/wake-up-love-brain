"""NPC 回覆產生器。

- MockLLM：不花錢、不連網。從人格 md 的「台詞參考」依階段抽台詞，紅旗用 personas.json 的
  mock_stage_flags 近似標記。用來測 UI 與遊戲流程。
- ClaudeLLM：經費下來後用。需要 Python 3.10+ 與 `pip install anthropic`，並設定
  ANTHROPIC_API_KEY。以環境變數 GAME_LLM=claude 啟用。

兩者介面一樣：generate(req) -> {"reply", "red_flags", "break_character"}
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import unicodedata
from typing import Dict, List

log = logging.getLogger("game.llm")

MAX_REPLY_CHARS = 300   # Q8：NPC 一則訊息的長度上限
MAX_FLAGS = 2
FALLBACK_REPLY = "（訊息好像沒有送出去……）你可以再說一次嗎？"


class LLMOutputError(ValueError):
    """模型輸出無法使用（不是 JSON、缺欄位、型別錯誤、空 reply）。"""


def parse_json_text(text: str) -> dict:
    """容忍 ```json 程式碼框與前後多餘文字。"""
    text = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except ValueError:
        a, b = text.find("{"), text.rfind("}")
        if a < 0 or b <= a:
            raise LLMOutputError("not json")
        try:
            data = json.loads(text[a:b + 1])
        except ValueError:
            raise LLMOutputError("not json")
    return data


_SHORTENERS = r"(?:bit\.ly|t\.me|wa\.me|line\.me|lin\.ee|reurl\.cc|ppt\.cc|tinyurl\.com|goo\.gl|is\.gd)"
_DOMAIN = re.compile(
    r"\b[a-z0-9-]{2,}\.(?:com|net|org|tw|cn|app|xyz|info|top|vip|link|shop)\b"
    r"|\b[a-z0-9-]{3,}\.(?:io|me|co|cc|ly|gl|ee)\b")
_URL_SCHEME = re.compile(r"(?:h(?:tt|xx|tx)ps?|ftp)\s*:\s*/\s*/|\bwww\.", re.I)
_SPACED_LETTERS = re.compile(r"(?:(?:\b[A-Za-z0-9]\b|\.)[ ]){4,}\b[A-Za-z0-9]\b")
_HANDLE = re.compile(r"(?<![A-Za-z0-9])@[A-Za-z0-9_.]{3,}")
_WALLET = re.compile(r"\b0x[0-9a-fA-F]{20,}\b|\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b")
_DATE = re.compile(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|\d{1,2}:\d{2}(?::\d{2})?")
_PHONE = re.compile(r"(?<!\d)(?:\+?886[ -]?)?0?9\d{2}[ -]?\d{3}[ -]?\d{3}(?!\d)|(?<!\d)0\d{1,2}[ -]?\d{7,8}(?!\d)")
_ACCOUNT = re.compile(
    r"(?:帳號|帳戶|戶頭|銀行|郵局|匯款|匯到|轉到|轉入|卡號|電話|手機|line|LINE|微信|wechat)\D{0,8}(\d[\d \-]{7,})")
_CN_PHONE = re.compile(r"[零〇一二三四五六七八九]{9,}")
_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]")


def _check_output_safe(reply: str, persona) -> None:
    """輸出端攔截（Q45、Q56）：真實網址／帳號／電話／錢包地址，或洩漏紅旗代碼（prompt 片段）。

    先做 NFKC 與去零寬；日期時間與一般數字不誤殺。"""
    t = _ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", reply))
    t = re.sub(r"\s*(?:dot|點)\s*(?=(?:com|net|org|tw|io|me|co|cc|ly)\b)", ".", t, flags=re.I)
    low = t.lower()
    texts = [low]
    for m in _SPACED_LETTERS.finditer(low):  # k e v i n . m e
        texts.append(re.sub(r"[ ]", "", m.group(0)))
    undated = _DATE.sub(" ", t)
    bad = (
        _URL_SCHEME.search(low) or re.search(_SHORTENERS, low)
        or any(_DOMAIN.search(x) for x in texts)
        or _HANDLE.search(t) or _WALLET.search(t)
        or _PHONE.search(undated) or _ACCOUNT.search(undated) or _CN_PHONE.search(t)
    )
    if bad:
        raise LLMOutputError("reply contains url/account-like content")
    if any(code in low for code in persona.flag_codes):
        raise LLMOutputError("reply leaks flag codes")


def validate_output(out, persona) -> Dict:
    """檢查並正規化 LLM 輸出。紅旗只留該人格代碼表（來自 personas/*.md）內的代碼。"""
    if not isinstance(out, dict):
        raise LLMOutputError("output is not an object")
    brk = out.get("break_character", False)
    if not isinstance(brk, bool):
        raise LLMOutputError("break_character not bool")
    reply = out.get("reply")
    if not isinstance(reply, str):
        raise LLMOutputError("reply missing or not str")
    reply = reply.strip()
    if not reply and not brk:
        raise LLMOutputError("empty reply")
    if len(reply) > MAX_REPLY_CHARS:
        reply = reply[:MAX_REPLY_CHARS].rstrip() + "…"
    if not brk:
        _check_output_safe(reply, persona)
    raw = out.get("red_flags", [])
    if not isinstance(raw, list):
        raise LLMOutputError("red_flags not list")
    flags: List[str] = []
    for f in raw:
        if isinstance(f, str) and f in persona.flag_codes and f not in flags:
            flags.append(f)
        else:
            log.warning("dropped red flag %r for persona %s", f, persona.id)
    clean = {"reply": reply, "red_flags": [] if brk else flags[:MAX_FLAGS], "break_character": brk}
    if "_line" in out:
        clean["_line"] = out["_line"]
    return clean


def generate_safe(llm, req) -> Dict:
    """呼叫 LLM；輸出或連線失敗時重試一次，仍失敗回安全 fallback，絕不丟例外（Q8）。"""
    for attempt in (1, 2):
        try:
            return validate_output(llm.generate(req), req.persona)
        except Exception as e:  # noqa: BLE001 - 連線、解析、驗證錯誤一律走重試
            log.warning("LLM attempt %d failed: %s: %s", attempt, type(e).__name__, e)
    return fallback_output(req)


def clean_pool(persona, stage: int, gender: str) -> List[str]:
    """personas.json 的 mock_clean_lines[stage]（字串或 {text, gender}）；欄位不存在回空。"""
    raw = (persona.cfg.get("mock_clean_lines") or {}).get(str(stage)) or []
    out = []
    for item in raw:
        text, g = (item, None) if isinstance(item, str) else (item.get("text"), item.get("gender"))
        if text and g in (None, gender):
            out.append(text)
    return out


def fallback_output(req) -> Dict:
    """安全 fallback（Q49）：只用該階段「無紅旗」的 clean line，絕不取帶紅旗的台詞；
    沒有 clean line 就用中性提示句。一律 red_flags=[]。"""
    pool = clean_pool(req.persona, req.stage, req.gender)
    fresh = [t for t in pool if t not in req.used_lines]
    choices = fresh or pool
    text = choices[len(req.used_lines) % len(choices)] if choices else FALLBACK_REPLY
    return {"reply": text[:MAX_REPLY_CHARS], "red_flags": [], "break_character": False,
            "_fallback": True, "_line": text}


class NPCRequest:
    def __init__(self, persona, gender: str, stage: int, trust: int,
                 system_prompt: str, player_text: str, used_lines: List[str], seed=None):
        self.persona = persona
        self.gender = gender
        self.stage = stage
        self.trust = trust
        self.system_prompt = system_prompt
        self.player_text = player_text
        self.used_lines = used_lines
        self.seed = seed  # 每局種子（Mock 用它決定哪些回合出正常台詞，可重現）


# Mock 的「接話」：mock 只會抽固定台詞，無法真的理解玩家；這裡用關鍵字判斷玩家這句的意圖，
# 先回一句中性的接話（無紅旗、不含網址帳號），再接原本的台詞，讓對話不至於上文不接下文。
# 真正根據上下文回答要靠 Claude 模式。
_BRIDGES = [
    ("leave", r"掰掰|拜拜|再見|我要走|先這樣|晚安|要睡了|去睡|下線", ["好吧，那你先去忙。", "嗯，晚安。"]),
    ("refuse", r"不要|不想|不行|不用|不可以|拒絕|算了|沒空|沒辦法|不方便|不好意思|不能", ["好啦，我聽到你說的了。", "嗯，我知道你的意思。"]),
    ("thanks", r"謝謝|感謝|多謝", ["不客氣啦。", "你這麼說我會不好意思。"]),
    ("greet", r"^(?:嗨|哈囉|哈嘍|你好|hi|hello|hey|在嗎|早安|午安|安安)", ["嗨，你來了。", "欸，你終於回我了。"]),
    ("sad", r"難過|傷心|心情不好|很累|好累|壓力|煩死|崩潰|焦慮|睡不著|不開心|委屈", ["怎麼了？聽起來你今天不太好。", "我有聽到，你先慢慢說。"]),
    ("angry", r"生氣|火大|很煩|討厭|幹嘛|夠了|別再|你很奇怪|你好奇怪|不爽", ["欸，你是不是生氣了？", "好啦，你先別氣。"]),
    ("affection", r"喜歡你|愛你|想你|想見你|開心|好喔|好啊|可以啊|好呀|好的", ["嗯，我也是這樣想。", "聽你這樣說我就安心了。"]),
    ("question", r"[?？]|嗎|什麼|為什麼|為何|怎麼|誰|哪裡|哪個|幾點|多少|是不是", ["你問這個喔，我想一下。", "這個問題問得好。"]),
]
_BRIDGE_DEFAULT = ["嗯嗯，我有在聽。", "我知道，你說的我都有看。"]


def mock_bridge(req) -> str:
    """依玩家這句話的意圖，挑一句中性接話；沒有玩家文字（開場）回空字串。可重現（以種子與回合決定）。"""
    t = (req.player_text or "").strip()
    if not t:
        return ""
    low = t.lower()
    options = _BRIDGE_DEFAULT
    for _name, pat, opts in _BRIDGES:
        if re.search(pat, low):
            options = opts
            break
    return random.Random(f"{req.seed}|{req.persona.id}|bridge|{len(req.used_lines)}").choice(options)


def _with_bridge(out: Dict, req) -> Dict:
    b = mock_bridge(req)
    if b:
        out["reply"] = (b + out["reply"])[:MAX_REPLY_CHARS]
    return out


class MockLLM:
    name = "mock"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    CLEAN_BLOCK = 3  # Q46：每 3 回合固定 1 回合出無紅旗正常台詞（位置由每局種子決定），不是機率

    @classmethod
    def _clean_line(cls, req: "NPCRequest"):
        turn = len(req.used_lines)
        block = turn // cls.CLEAN_BLOCK
        slot = random.Random(f"{req.seed}|{req.persona.id}|slot|{block}").randrange(cls.CLEAN_BLOCK)
        if turn % cls.CLEAN_BLOCK != slot:
            return None
        fresh = [t for t in clean_pool(req.persona, req.stage, req.gender) if t not in req.used_lines]
        if not fresh:  # 該階段的 clean line 用完才回到一般台詞
            return None
        text = random.Random(f"{req.seed}|{req.persona.id}|pick|{turn}").choice(fresh)
        return {"reply": text, "red_flags": [], "break_character": False, "_line": text}

    def generate(self, req: NPCRequest) -> Dict:
        clean = self._clean_line(req)
        if clean is not None:
            return _with_bridge(clean, req)
        pool = [l for l in req.persona.lines.get(req.stage, [])
                if l["gender"] in (None, req.gender)]
        fresh = [l for l in pool if l["text"] not in req.used_lines]
        line = self.rng.choice(fresh or pool)

        text = line["text"]
        if line["narration"]:
            text = f"（{line['narration']}）{text}"
        if line["action"]:
            text = f"{text}（{line['action']}）"

        flags: List[str] = []
        if not line["no_flag"]:
            options = req.persona.cfg["mock_stage_flags"].get(str(req.stage), [])
            if options:
                flags = [options[pool.index(line) % len(options)]]
        return _with_bridge({"reply": text, "red_flags": flags, "break_character": False,
                             "_line": line["text"]}, req)


def reply_schema(flag_codes: List[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "red_flags": {"type": "array", "items": {"type": "string", "enum": flag_codes}},
            "break_character": {"type": "boolean"},
        },
        "required": ["reply", "red_flags", "break_character"],
        "additionalProperties": False,
    }


class ClaudeLLM:
    """尚未實測（目前沒有 API key）。結構依 Anthropic Python SDK 文件撰寫。"""
    name = "claude"

    def __init__(self, model: str = ""):
        import anthropic  # 延遲匯入：mock 模式不需要安裝

        self.anthropic = anthropic
        self.client = anthropic.Anthropic()  # 從 ANTHROPIC_API_KEY 讀金鑰
        self.model = model or os.environ.get("GAME_CLAUDE_MODEL", "claude-opus-5-5")

    def generate(self, req: NPCRequest) -> Dict:
        opening = "（玩家剛打開聊天室，請你主動傳第一則訊息）"
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=600,
            # 被安全分類器拒答時，伺服器自動改用其他模型重跑
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=req.system_prompt,
            messages=[{"role": "user", "content": req.player_text or opening}],
            output_config={
                "effort": "low",  # 短句聊天不需要深度推理
                "format": {"type": "json_schema",
                           "schema": reply_schema(sorted(req.persona.flag_codes))},
            },
        )
        if response.stop_reason == "refusal":
            return {"reply": "", "red_flags": [], "break_character": True}
        text = next((b.text for b in response.content if b.type == "text"), "")
        return parse_json_text(text)  # 驗證與紅旗過濾交給 validate_output（generate_safe 內）


def make_safety_classifier(llm):
    """GAME_SAFETY_LLM=1 時用的第二道 safety 分類器（Q48）。**尚未用真 API 實測。**
    回傳 classifier(text) -> {"category","severity","ends_session","context"} 或 None；失敗一律回 None
    （不影響規則式 safety）。目前只有 ClaudeLLM 支援。"""
    client = getattr(llm, "client", None)
    if client is None:
        return None
    categories = ["self_harm", "real_violence", "real_scam", "minor", "too_painful"]

    def classify(text: str):
        try:
            resp = client.messages.create(
                model=getattr(llm, "model", ""), max_tokens=100,
                system=("你是安全分類器。判斷玩家這句話是否表達『玩家本人現實中』的危機："
                        + "、".join(categories) + "。遊戲內對 NPC 的角色扮演不算。"
                        "只輸出 JSON：{\"category\": 類別或null, \"severity\": \"high\"|\"medium\"|\"low\"}"),
                messages=[{"role": "user", "content": text[:300]}])
            data = parse_json_text("".join(b.text for b in resp.content if b.type == "text"))
            cat, sev = data.get("category"), data.get("severity")
            if cat in categories and sev in ("high", "medium", "low"):
                return {"category": cat, "severity": sev, "ends_session": sev in ("high", "medium"),
                        "context": "llm"}
        except Exception as e:  # noqa: BLE001
            log.warning("safety classifier failed: %s", e)
        return None
    return classify


def get_llm():
    if os.environ.get("GAME_LLM", "mock").lower() == "claude":
        return ClaudeLLM()
    return MockLLM()
