"""載入 personas/*.md 人格提示詞，並與 data/personas.json 的遊戲設定合併。

md 檔由隊員各自撰寫，格式不完全一致（{{x}} / {x} / {{x\\_y}}、彎引號 JSON 等），
這裡統一正規化，讓遊戲端和之後的 Claude API 拿到一樣乾淨的 prompt。
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Dict, List, Optional

GAME_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = GAME_DIR / "data" / "personas.json"
DEFAULT_PROMPT_DIR = GAME_DIR.parent / "personas"

TEMPLATE_KEYS = (
    "npc_name", "npc_age", "npc_gender", "time_context",
    "stage", "trust_score", "recent_history",
)

_STAGE_HEADING = re.compile(r"^(?:\*\*階段\s*(\d)\*\*|#{2,4}\s*階段\s*(\d))\s*$")
_LINE = re.compile(r"^[-*]\s*(?:（([^）]*)）)?\s*「(.+)」\s*(?:（([^）]*)）)?\s*$")
_FLAG_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*([^|]+?)\s*\|")
_STAGE_ROW = re.compile(r"^\|\s*(\d)\s*\|\s*([^|]+?)\s*\|")

# 台詞後面的註記：哪些是「動作」要留給玩家看，哪些代表不算紅旗
_ACTION_NOTES = ("隔天消失", "已讀不回")
_NO_FLAG_NOTES = ("不必標記紅旗",)


def normalize(text: str) -> str:
    text = text.replace("\\_", "_").replace("\\~", "~").replace("\\[", "[")
    return text.replace("“", '"').replace("”", '"')


def render(template: str, values: Dict[str, object]) -> str:
    """填入 {{key}} 或 {key}；只認得 TEMPLATE_KEYS，不會誤傷 JSON 範例的大括號。"""
    def sub(m: re.Match) -> str:
        key = m.group(1) or m.group(2)
        return str(values[key]) if key in values else m.group(0)

    # 單次掃描：填進去的值（例如玩家文字裡的 {stage}）不會被再次展開（Q7）
    keys = "|".join(TEMPLATE_KEYS)
    return re.sub(r"\{\{\s*(" + keys + r")\s*\}\}|\{(" + keys + r")\}", sub, template)


def parse_lines(md: str) -> Dict[int, List[dict]]:
    """抽出「台詞參考」段落，依階段分組。"""
    lines: Dict[int, List[dict]] = {}
    in_section = False
    stage: Optional[int] = None
    for raw in md.splitlines():
        s = raw.strip()
        if s.startswith("#") and "台詞參考" in s:
            in_section = True
            continue
        if not in_section:
            continue
        if re.match(r"^#{1,2}\s", s) and "階段" not in s:
            break  # 下一個大段落
        m = _STAGE_HEADING.match(s)
        if m:
            stage = int(m.group(1) or m.group(2))
            continue
        m = _LINE.match(s)
        if m and stage:
            prefix, quote, note = m.group(1) or "", m.group(2), m.group(3) or ""
            gender = None
            narration = ""
            if prefix in ("女性角色", "男性角色"):
                gender = prefix[0]
            elif prefix:
                narration = prefix  # 例如「幾天後」
            action = note if any(a in note for a in _ACTION_NOTES) else ""
            lines.setdefault(stage, []).append({
                "text": quote,
                "gender": gender,
                "narration": narration,
                "action": action,
                "no_flag": any(n in note for n in _NO_FLAG_NOTES),
            })
    return lines


def parse_flag_codes(md: str) -> Dict[str, str]:
    codes = {}
    for raw in md.splitlines():
        m = _FLAG_ROW.match(raw.strip())
        if m:
            codes[m.group(1)] = m.group(2).strip()
    return codes


def parse_stage_names(md: str) -> Dict[int, str]:
    names = {}
    for raw in md.splitlines():
        m = _STAGE_ROW.match(raw.strip())
        if m and 1 <= int(m.group(1)) <= 5:
            names.setdefault(int(m.group(1)), m.group(2).strip())
    return names


class PersonaLoadError(RuntimeError):
    """人格設定或 prompt 檔有問題（啟動時就該擋下來）。"""


# 前端原本寫死在 CSS 的人格色；cfg 內有 color / description / difficulty 時以 cfg 為準
DEFAULT_COLORS = {"avoidant": "#3b82c4", "dependent": "#d6559a", "anxious": "#e08a1e",
                  "scammer": "#2f9e6b", "player": "#7a55d0"}
DEFAULT_DIFFICULTY = {"avoidant": 2, "dependent": 2, "anxious": 2, "scammer": 3, "player": 3}
STAGE_TOTAL = 5


class Persona:
    def __init__(self, cfg: dict, prompt_text: str):
        self.cfg = cfg
        self.id: str = cfg["id"]
        self.title: str = cfg["title"]
        self.prompt_template = prompt_text
        self.lines = parse_lines(prompt_text)
        self.stage_names = parse_stage_names(prompt_text)
        # 紅旗代碼表以 personas/*.md 為單一來源（Q8）；personas.json 的 flag_codes 不再使用
        codes = parse_flag_codes(prompt_text)
        if not codes:
            raise PersonaLoadError(f"{cfg['prompt_file']} 找不到紅旗代碼表（| `code` | 說明 | 表格）")
        self.flag_codes: Dict[str, str] = codes

    def npc_name(self, gender: str) -> str:
        return self.cfg["names"][gender]

    def choices(self, stage: int, seed: Optional[str] = None) -> List[dict]:
        """該階段的玩家選項（固定兩句）。給 seed 則以 seed 決定順序
        （同一局同一階段順序固定，choice_id 才對得上）。"""
        base = list(self.cfg["choices"].get(str(stage), []))
        if self.cfg.get("shuffle") and seed is not None:
            # 固定只給兩句（brain / awake），不再混入 neutral；seed 只決定順序
            random.Random(f"{seed}|{self.id}|{stage}").shuffle(base)
        return base

    def flag_meaning(self, code: str) -> str:
        return self.flag_codes.get(code, code)

    def public(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "tagline": self.cfg["tagline"],
            "emoji": self.cfg["emoji"],
            "names": self.cfg["names"],
            "age": self.cfg["age"],
            "default_gender": self.cfg["default_gender"],
            "stage_names": self.stage_names,
            "stage_total": STAGE_TOTAL,
            "color": self.cfg.get("color") or DEFAULT_COLORS.get(self.id, "#888888"),
            "description": self.cfg.get("description") or self.cfg["tagline"],
            "difficulty": self.cfg.get("difficulty") or DEFAULT_DIFFICULTY.get(self.id, 2),
        }


def load_personas(prompt_dir: Optional[Path] = None) -> Dict[str, Persona]:
    prompt_dir = Path(prompt_dir or DEFAULT_PROMPT_DIR)
    cfg = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    missing = [p["prompt_file"] for p in cfg["personas"]
               if not (prompt_dir / p["prompt_file"]).is_file()]
    if missing:  # Q6：啟動時一次列出所有缺失
        raise PersonaLoadError(
            f"找不到人格 prompt 檔（資料夾 {prompt_dir}）：{', '.join(missing)}。"
            f"請檢查 data/personas.json 的 prompt_file 是否與 personas/ 內實際檔名一致。")
    out: Dict[str, Persona] = {}
    for p in cfg["personas"]:
        text = normalize((prompt_dir / p["prompt_file"]).read_text(encoding="utf-8"))
        persona = Persona(p, text)
        bad = sorted({c for codes in p.get("mock_stage_flags", {}).values() for c in codes}
                     - set(persona.flag_codes))
        if bad:
            raise PersonaLoadError(f"{p['id']} 的 mock_stage_flags 用了 {p['prompt_file']} 代碼表沒有的代碼：{bad}")
        out[p["id"]] = persona
    return out
