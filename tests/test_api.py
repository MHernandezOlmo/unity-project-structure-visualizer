import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from parser.indexer import build_index

# ---------------------------------------------------------------------------
# Fixture helpers (same content as test_indexer.py)
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
def client():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "Assets/Scripts/PlayerController.cs", PLAYER_CS)
        _write(root, "Assets/Scripts/PlayerController.cs.meta", _meta(PLAYER_GUID))
        _write(root, "Assets/Scenes/Main.unity", MAIN_UNITY)
        _write(root, "Assets/Scenes/Main.unity.meta", _meta("b" * 32))

        idx = build_index(tmp)
        with TestClient(app) as c:
            app.state.index = idx
            yield c


@pytest.fixture
def no_index_client():
    with TestClient(app) as c:
        app.state.index = None
        yield c


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /scenes
# ---------------------------------------------------------------------------

def test_list_scenes(client):
    r = client.get("/scenes")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert "Main.unity" in data[0]["path"]
    assert data[0]["kind"] == "scene"
    assert data[0]["game_object_count"] == 1


def test_list_scenes_no_index(no_index_client):
    r = no_index_client.get("/scenes")
    assert r.status_code == 503


def test_get_scene(client):
    scenes = client.get("/scenes").json()
    raw_path = scenes[0]["path"]
    url_path = raw_path.replace("\\", "/")

    r = client.get(f"/scenes/{url_path}")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "scene"
    assert len(body["game_objects"]) == 1

    go = body["game_objects"][0]
    assert go["name"] == "Player"
    assert go["is_active"] is True

    type_names = [c["type_name"] for c in go["components"]]
    assert "Transform" in type_names
    assert "MonoBehaviour" in type_names

    mono = next(c for c in go["components"] if c["type_name"] == "MonoBehaviour")
    assert mono["script_class"] == "PlayerController"


def test_get_scene_script_classes(client):
    scenes = client.get("/scenes").json()
    url_path = scenes[0]["path"].replace("\\", "/")

    r = client.get(f"/scenes/{url_path}")
    assert "PlayerController" in r.json()["script_classes"]


def test_get_scene_not_found(client):
    r = client.get("/scenes/Assets/Scenes/Ghost.unity")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /scripts
# ---------------------------------------------------------------------------

def test_list_scripts(client):
    r = client.get("/scripts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["class_name"] == "PlayerController"
    assert data[0]["base_class"] == "MonoBehaviour"
    assert data[0]["interfaces"] == []


def test_list_scripts_no_index(no_index_client):
    r = no_index_client.get("/scripts")
    assert r.status_code == 503


def test_get_script(client):
    r = client.get("/scripts/PlayerController")
    assert r.status_code == 200
    body = r.json()
    assert body["class_name"] == "PlayerController"
    assert body["base_class"] == "MonoBehaviour"
    assert "UnityEngine" in body["usings"]
    assert any(f["name"] == "speed" for f in body["serialize_fields"])


def test_get_script_used_in_scenes(client):
    r = client.get("/scripts/PlayerController")
    assert r.status_code == 200
    scenes = r.json()["used_in_scenes"]
    assert len(scenes) == 1
    assert "Main.unity" in scenes[0]


def test_get_script_not_found(client):
    r = client.get("/scripts/GhostScript")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /graph/dependencies
# ---------------------------------------------------------------------------

def test_graph_returns_nodes_and_edges(client):
    r = client.get("/graph/dependencies")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body
    assert "edges" in body


def test_graph_node_types(client):
    body = client.get("/graph/dependencies").json()
    types = {n["type"] for n in body["nodes"]}
    assert "scene" in types
    assert "script" in types


def test_graph_scene_node_label(client):
    body = client.get("/graph/dependencies").json()
    scene_node = next(n for n in body["nodes"] if n["type"] == "scene")
    assert scene_node["label"] == "Main.unity"


def test_graph_script_node_label(client):
    body = client.get("/graph/dependencies").json()
    script_node = next(n for n in body["nodes"] if n["type"] == "script")
    assert script_node["label"] == "PlayerController"


def test_graph_uses_edge(client):
    body = client.get("/graph/dependencies").json()
    uses = [e for e in body["edges"] if e["type"] == "uses"]
    assert len(uses) == 1


def test_graph_monobehaviour_tagged_not_edged(client):
    body = client.get("/graph/dependencies").json()
    # No inherits edge to MonoBehaviour; it's represented as a node flag instead
    inherits = [e for e in body["edges"] if e["type"] == "inherits"]
    assert len(inherits) == 0
    player_node = next(n for n in body["nodes"] if n["label"] == "PlayerController")
    assert player_node["mono"] is True


def test_graph_no_index(no_index_client):
    r = no_index_client.get("/graph/dependencies")
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# /project/load
# ---------------------------------------------------------------------------

def test_load_project_success(no_index_client):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "Assets/Scripts/PlayerController.cs", PLAYER_CS)
        _write(root, "Assets/Scripts/PlayerController.cs.meta", _meta(PLAYER_GUID))
        _write(root, "Assets/Scenes/Main.unity", MAIN_UNITY)
        _write(root, "Assets/Scenes/Main.unity.meta", _meta("b" * 32))

        r = no_index_client.post("/project/load", json={"path": tmp})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["scene_count"] == 1
        assert body["script_count"] == 1


def test_load_project_updates_index(no_index_client):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "Assets/Scripts/PlayerController.cs", PLAYER_CS)
        _write(root, "Assets/Scripts/PlayerController.cs.meta", _meta(PLAYER_GUID))
        _write(root, "Assets/Scenes/Main.unity", MAIN_UNITY)
        _write(root, "Assets/Scenes/Main.unity.meta", _meta("b" * 32))

        no_index_client.post("/project/load", json={"path": tmp})
        r = no_index_client.get("/scenes")
        assert r.status_code == 200
        assert len(r.json()) == 1


def test_load_project_bad_path(no_index_client):
    r = no_index_client.post("/project/load", json={"path": "/nonexistent/path/xyz"})
    assert r.status_code == 400
    assert "not found" in r.json()["detail"].lower()


def test_load_project_missing_path_field(no_index_client):
    r = no_index_client.post("/project/load", json={})
    assert r.status_code == 422
