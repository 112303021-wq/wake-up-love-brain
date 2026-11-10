"""玩家存檔：每位玩家一個 JSON，保存每個人格的對話與覆盤紀錄。

10/13 老師建議「之前聊的東西要存下來、切換人格後要記得」：
切到別的人格再切回來，對話會接著；教練覆盤也會讀到其他人格的成績。

並發（Q5）：每位玩家一把 RLock，呼叫端用 `with store.lock(pid):` 包住整個 load-modify-save。
寫檔（Q5）：同目錄唯一暫存檔 + fsync + os.replace，不會留下半個檔。
損毀（Q24）：讀到壞檔 → 改名為 `<id>.json.corrupt-<時間戳>` 並回傳全新存檔，不再丟 500。
隱私（Q10）：delete() 刪除該玩家所有資料（含被隔離的損毀檔）。
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import time
from pathlib import Path

log = logging.getLogger("game.store")

# 嚴格白名單：英數開頭，後面可有 _ -，最長 64。不含 . / \ 空白，因此無法路徑穿越或產生隱藏檔。
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}


def valid_player_id(player_id) -> bool:
    return (isinstance(player_id, str) and _SAFE_ID.fullmatch(player_id) is not None
            and player_id.lower() not in _RESERVED)


def _fresh(player_id: str) -> dict:
    return {"player_id": player_id, "nickname": "", "sessions": {}, "reviews": [], "prefs": {}, "consent": None, "token_hash": None}


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict = {}
        self._locks_guard = threading.Lock()

    # ---------- 鎖 ----------
    def lock(self, player_id: str) -> threading.RLock:
        """每位玩家一把鎖（可重入）。用法：with store.lock(pid): load → 修改 → save。"""
        self._path(player_id)  # 先驗證 ID
        with self._locks_guard:
            lk = self._locks.get(player_id)
            if lk is None:
                lk = self._locks[player_id] = threading.RLock()
            return lk

    # ---------- 路徑 ----------
    def _path(self, player_id: str) -> Path:
        if not valid_player_id(player_id):
            raise ValueError("invalid player id")
        path = (self.root / f"{player_id}.json").resolve()
        if path.parent != self.root.resolve():  # 雙保險
            raise ValueError("invalid player id")
        return path

    # ---------- 讀寫 ----------
    def load(self, player_id: str) -> dict:
        path = self._path(player_id)
        with self.lock(player_id):
            if not path.exists():
                return _fresh(player_id)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if (not isinstance(data, dict) or not isinstance(data.get("sessions"), dict)
                        or not isinstance(data.get("reviews", []), list)):
                    raise ValueError("unexpected structure")
            except (ValueError, OSError, UnicodeDecodeError) as e:
                self._quarantine(path, e)
                return _fresh(player_id)
            data["player_id"] = player_id
            data.setdefault("nickname", "")
            data.setdefault("reviews", [])
            data.setdefault("prefs", {})
            data.setdefault("consent", None)
            return data

    def _quarantine(self, path: Path, err: Exception) -> None:
        target = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}")
        n = 0
        while target.exists():
            n += 1
            target = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}-{n}")
        try:
            os.replace(path, target)
            log.warning("corrupt save quarantined: %s -> %s (%s)", path.name, target.name, err)
        except OSError:
            log.exception("cannot quarantine corrupt save %s", path.name)

    def save(self, profile: dict) -> None:
        pid = profile["player_id"]
        path = self._path(pid)
        payload = json.dumps(profile, ensure_ascii=False, indent=1)
        with self.lock(pid):
            fd, tmp = tempfile.mkstemp(dir=str(self.root), prefix=f".{pid}.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(payload)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise

    def count_players(self) -> int:
        return sum(1 for _ in self.root.glob("*.json"))

    def exists(self, player_id: str) -> bool:
        return self._path(player_id).exists()

    def purge_older_than(self, days: float) -> int:
        """保存期限（Q42）：刪除超過 days 天沒更新的存檔與隔離檔，回傳刪除數。"""
        cutoff = time.time() - days * 86400
        n = 0
        for p in list(self.root.glob("*.json")) + list(self.root.glob("*.json.corrupt-*")):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    n += 1
            except OSError:
                pass
        return n

    def delete(self, player_id: str) -> bool:
        """刪除該玩家所有資料（存檔與被隔離的損毀檔）。回傳是否真的刪到東西。"""
        path = self._path(player_id)
        with self.lock(player_id):
            removed = False
            for p in [path, *self.root.glob(f"{player_id}.json.corrupt-*")]:
                try:
                    p.unlink()
                    removed = True
                except FileNotFoundError:
                    pass
            return removed
