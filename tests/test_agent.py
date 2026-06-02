import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agent as agent_module
from agent import _dispatch
from main import app
from parser.indexer import build_index

# ---------------------------------------------------------------------------
# Shared fixture helpers (mirrors test_api.py)
# ---------------------------------------------------------------------------
PLAYER_GUID = "a" * 32
ENEMY_GUID = "e" * 32

PLAYER_CS = """\
using UnityEngine;
public class PlayerController : MonoBehaviour
{
    [SerializeField] private float speed;
}
"""

ENEMY_CS = """\
using UnityEngine;
public class EnemyAI : MonoBehaviour {}
"""

MAIN_UNITY = f"""\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100000
GameObject:
  m_Name: Player
  m_IsActive: 1
  m_Component:
  - component: {{fileID: 400000}}
  - component: {{fileID: 1140000}}
--- !u!4 &400000
Transform:
  m_GameObject: {{fileID: 100000}}
--- !u!114 &1140000
MonoBehaviour:
  m_GameObject: {{fileID: 100000}}
  m_Script: {{fileID: 11500000, guid: {PLAYER_GUID}, type: 3}}
"""


def _meta(guid: str) -> str:
    return f"fileFormatVersion: 2\nguid: {guid}\nMonoImporter:\n  serializedVersion: 2\n"


def _write(root: Path, rel: str, content: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.fixture
def index():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "Assets/Scripts/PlayerController.cs", PLAYER_CS)
        _write(root, "Assets/Scripts/PlayerController.cs.meta", _meta(PLAYER_GUID))
        _write(root, "Assets/Scripts/EnemyAI.cs", ENEMY_CS)
        _write(root, "Assets/Scripts/EnemyAI.cs.meta", _meta(ENEMY_GUID))
        _write(root, "Assets/Scenes/Main.unity", MAIN_UNITY)
        _write(root, "Assets/Scenes/Main.unity.meta", _meta("b" * 32))
        yield build_index(tmp)


@pytest.fixture
def client(index):
    with TestClient(app) as c:
        app.state.index = index
        yield c


# ---------------------------------------------------------------------------
# _dispatch unit tests — no Anthropic API call
# ---------------------------------------------------------------------------

def test_dispatch_list_scenes(index):
    result = _dispatch("list_scenes", {}, index)
    assert "Main.unity" in result


def test_dispatch_list_scripts(index):
    result = _dispatch("list_scripts", {}, index)
    assert "PlayerController" in result
    assert "EnemyAI" in result


def test_dispatch_scripts_in_scene(index):
    scene_path = next(iter(index.scenes.keys()))
    result = _dispatch("scripts_in_scene", {"scene_path": scene_path.replace(os.sep, "/")}, index)
    assert "PlayerController" in result


def test_dispatch_scripts_in_scene_not_found(index):
    result = _dispatch("scripts_in_scene", {"scene_path": "Assets/Scenes/Ghost.unity"}, index)
    assert "No scripts" in result


def test_dispatch_scenes_using_script(index):
    result = _dispatch("scenes_using_script", {"class_name": "PlayerController"}, index)
    assert "Main.unity" in result


def test_dispatch_scenes_using_script_not_found(index):
    result = _dispatch("scenes_using_script", {"class_name": "GhostScript"}, index)
    assert "No scenes" in result


def test_dispatch_subclasses_of(index):
    result = _dispatch("subclasses_of", {"class_name": "MonoBehaviour"}, index)
    assert "PlayerController" in result
    assert "EnemyAI" in result


def test_dispatch_subclasses_of_not_found(index):
    result = _dispatch("subclasses_of", {"class_name": "IUnknown"}, index)
    assert "No subclasses" in result


def test_dispatch_script_by_class(index):
    result = _dispatch("script_by_class", {"class_name": "PlayerController"}, index)
    assert "PlayerController" in result
    assert "MonoBehaviour" in result
    assert "speed" in result


def test_dispatch_script_by_class_not_found(index):
    result = _dispatch("script_by_class", {"class_name": "GhostScript"}, index)
    assert "not found" in result.lower()


def test_dispatch_unknown_tool(index):
    result = _dispatch("nonexistent_tool", {}, index)
    assert "Unknown tool" in result


# ---------------------------------------------------------------------------
# /agent/ask endpoint — agent.ask is patched to avoid real API calls
# ---------------------------------------------------------------------------

def test_agent_ask_returns_answer(client, monkeypatch):
    monkeypatch.setattr(agent_module, "ask", lambda q, idx: "PlayerController is used in Main.unity.")
    r = client.post("/agent/ask", json={"question": "What scripts are in Main.unity?"})
    assert r.status_code == 200
    assert r.json()["answer"] == "PlayerController is used in Main.unity."


def test_agent_ask_no_index(monkeypatch):
    monkeypatch.setattr(agent_module, "ask", lambda q, idx: "irrelevant")
    with TestClient(app) as c:
        app.state.index = None
        r = c.post("/agent/ask", json={"question": "anything"})
    assert r.status_code == 503


def test_agent_ask_missing_question(client):
    r = client.post("/agent/ask", json={})
    assert r.status_code == 422


def test_agent_ask_propagates_answer(client, monkeypatch):
    monkeypatch.setattr(agent_module, "ask", lambda q, idx: f"You asked: {q}")
    r = client.post("/agent/ask", json={"question": "hello"})
    assert r.status_code == 200
    assert r.json()["answer"] == "You asked: hello"
