import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server as srv  # noqa: E402
from engine.llm import MockLLM  # noqa: E402


@pytest.fixture
def api(tmp_path):
    game = srv.build_game(tmp_path, MockLLM(seed=1))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.make_handler(game))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]

    def call(path, body=None, ct="application/json", raw=None, method=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                     headers={"Content-Type": ct}, method=method)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    yield call
    httpd.shutdown()


@pytest.mark.parametrize("raw", [b"[1,2]", b'"x"', b"123", b"null", b"{bad"])
def test_non_dict_or_bad_json_is_400(api, raw):
    code, body = api("/api/start", raw=raw)
    assert code == 400 and "error" in body


def test_text_plain_rejected(api):
    code, body = api("/api/start", {"player": "abcdef1", "persona": "avoidant"}, ct="text/plain")
    assert code == 400 and "Content-Type" in body["error"]


@pytest.mark.parametrize("extra", [{"hour": "abc"}, {"hour": 99}, {"hour": [1]}, {"severity": "x"},
                                   {"text": {"a": 1}}, {"text": 5}])
def test_bad_field_types_are_400(api, extra):
    api("/api/start", {"player": "abcdef1", "persona": "avoidant"})
    body = {"player": "abcdef1", "persona": "avoidant", "text": "嗯", **extra}
    code, out = api("/api/message", body)
    assert code == 400 and "error" in out


def test_missing_fields_400_not_disconnect(api):
    assert api("/api/message", {})[0] == 400
    assert api("/api/flag", {"player": "abcdef1", "persona": "avoidant"})[0] == 400
    assert api("/api/profile")[0] == 400


def test_too_large_body_400(api):
    assert api("/api/start", raw=b'{"a":"' + b"x" * 40000 + b'"}')[0] == 400


def test_prompt_and_reveal_only_in_dev(api, monkeypatch):
    api("/api/start", {"player": "abcdef1", "persona": "avoidant"})
    monkeypatch.setenv("GAME_DEV", "1")
    assert api("/api/prompt?player=abcdef1&persona=avoidant")[0] == 200
    code, st = api("/api/start", {"player": "abcdef1", "persona": "avoidant", "reveal": True})
    assert "red_flags" in st["messages"][0]
    monkeypatch.delenv("GAME_DEV")
    assert api("/api/prompt?player=abcdef1&persona=avoidant")[0] == 404
    code, st = api("/api/start", {"player": "abcdef1", "persona": "avoidant", "reveal": True})
    assert "red_flags" not in st["messages"][0]


def test_delete_profile_both_forms(api):
    api("/api/start", {"player": "abcdef1", "persona": "avoidant"})
    assert api("/api/profile?player=abcdef1", method="DELETE") == (200, {"ok": True, "deleted": True})
    assert api("/api/profile?player=abcdef1")[1]["sessions"] == {}
    api("/api/start", {"player": "abcdef1", "persona": "avoidant"})
    assert api("/api/profile/delete", {"player": "abcdef1"})[1]["deleted"] is True
    assert api("/api/profile?player=../x", method="DELETE")[0] == 400


def test_review_mid_game_needs_finish_and_flag_locked_after(api):
    code, st = api("/api/start", {"player": "abcdef1", "persona": "avoidant"})
    mid = st["messages"][0]["id"]
    assert api("/api/review", {"player": "abcdef1", "persona": "avoidant"})[0] == 400
    code, r = api("/api/review", {"player": "abcdef1", "persona": "avoidant", "finish": True})
    assert code == 200 and "scores" in r
    assert api("/api/flag", {"player": "abcdef1", "persona": "avoidant", "msg_id": mid})[0] == 400


def test_new_fields(api):
    _, ps = api("/api/personas")
    assert all(p["color"].startswith("#") and p["description"] and p["stage_total"] == 5 for p in ps)
    _, st = api("/api/start", {"player": "abcdef1", "persona": "avoidant"})
    assert st["stage_total"] == 5 and st["flags_caught_so_far"] == 0
    _, st = api("/api/message", {"player": "abcdef1", "persona": "avoidant", "text": "好啊沒關係", "severity": 3})
    assert any(m["role"] == "coach" and m["severity"] == 3 for m in st["messages"])
    assert api("/api/resources")[1]["resources"]


def test_server_error_hides_internals(api, monkeypatch):
    import engine.game as g
    monkeypatch.setattr(g.Game, "profile_summary", lambda self, p: 1 / 0)
    code, out = api("/api/profile?player=abcdef1")
    assert code == 500 and out == {"error": "server error", "code": "server_error"}


def test_http_notice_resume_and_default_severity(api):
    api("/api/start", {"player": "abcdef1", "persona": "avoidant"})
    code, st = api("/api/message", {"player": "abcdef1", "persona": "avoidant", "text": "好啊沒關係"})
    assert all(m["severity"] == 1 for m in st["messages"] if m["role"] == "coach")
    code, st = api("/api/message", {"player": "abcdef1", "persona": "avoidant", "text": "小說裡的角色想自殺"})
    assert code == 200 and st["notice"]["ends_session"] is False and not st["ended"]
    code, st = api("/api/message", {"player": "abcdef1", "persona": "avoidant", "text": "我要暫停"})
    assert st["ended"] and st["can_resume"] and st["safety"]["category"] == "pause"
    assert api("/api/message", {"player": "abcdef1", "persona": "avoidant", "text": "嗯"})[0] == 400
    code, st = api("/api/resume", {"player": "abcdef1", "persona": "avoidant"})
    assert code == 200 and not st["ended"]
    assert api("/api/resume", {"player": "abcdef1", "persona": "avoidant"})[0] == 400


def test_resources_reports_dev_flag(api, monkeypatch):
    monkeypatch.setenv("GAME_DEV", "1")
    assert api("/api/resources")[1]["dev"] is True
    monkeypatch.delenv("GAME_DEV")
    assert api("/api/resources")[1]["dev"] is False


def test_consent_recorded_in_profile_and_deleted(api):
    code, r = api("/api/consent", {"player": "abcdef1", "version": "v1.0"})
    assert code == 200 and r["consent"]["version"] == "v1.0" and r["consent"]["accepted"] is True
    assert api("/api/profile?player=abcdef1")[1]["consent"]["version"] == "v1.0"
    assert api("/api/profile?player=nobody1")[1]["consent"] is None
    for bad in [{"version": ""}, {"version": 3}, {"version": "a b"}, {"version": "v1", "accepted": "yes"}, {}]:
        assert api("/api/consent", {"player": "abcdef1", **bad})[0] == 400
    api("/api/profile?player=abcdef1", method="DELETE")
    assert api("/api/profile?player=abcdef1")[1]["consent"] is None
    # 未同意也能玩（只記錄不強制）
    assert api("/api/start", {"player": "abcdef2", "persona": "avoidant"})[0] == 200


def test_prefs_mute_and_uncomfortable(api):
    pl = {"player": "abcdef1", "persona": "avoidant"}
    api("/api/start", pl)
    assert api("/api/prefs", {"player": "abcdef1", "prefs": {"mute_coach": 1}})[0] == 400
    assert api("/api/prefs", {"player": "abcdef1", "prefs": {"severity": True}})[0] == 400
    code, r = api("/api/prefs", {"player": "abcdef1", "prefs": {"mute_coach": True, "feel_uncomfortable": False}})
    assert r["prefs"] == {"mute_coach": True, "feel_uncomfortable": False}
    assert api("/api/profile?player=abcdef1")[1]["prefs"]["mute_coach"] is True
    code, st = api("/api/message", {**pl, "text": "好啊沒關係，我等你"})
    assert not [m for m in st["messages"] if m["role"] == "coach"]
    # 仍計分
    code, r = api("/api/review", {**pl, "finish": True})
    assert r["scores"]["brain_choices"] == 1


def test_feel_uncomfortable_forces_gentle_coach(api):
    pl = {"player": "abcdef1", "persona": "avoidant"}
    api("/api/start", pl)
    api("/api/prefs", {"player": "abcdef1", "prefs": {"feel_uncomfortable": True}})
    code, st = api("/api/message", {**pl, "text": "好啊沒關係，我等你", "severity": 3})
    assert all(m["severity"] == 1 for m in st["messages"] if m["role"] == "coach")
