import os
import tempfile
from pathlib import Path

from parser.indexer import build_index, ProjectIndex

# ---------------------------------------------------------------------------
# Fixture GUIDs
# ---------------------------------------------------------------------------
PLAYER_GUID = "a" * 32
ENEMY_GUID = "e" * 32
SCENE_GUID = "b" * 32

# ---------------------------------------------------------------------------
# Asset content
# ---------------------------------------------------------------------------
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
  - component: {{fileID: 1140000}}
--- !u!114 &1140000
MonoBehaviour:
  m_GameObject: {{fileID: 100000}}
  m_Script: {{fileID: 11500000, guid: {PLAYER_GUID}, type: 3}}
"""

MULTI_SCRIPT_UNITY = f"""\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100000
GameObject:
  m_Name: Player
  m_IsActive: 1
  m_Component:
  - component: {{fileID: 1140000}}
--- !u!114 &1140000
MonoBehaviour:
  m_GameObject: {{fileID: 100000}}
  m_Script: {{fileID: 11500000, guid: {PLAYER_GUID}, type: 3}}
--- !u!1 &200000
GameObject:
  m_Name: Enemy
  m_IsActive: 1
  m_Component:
  - component: {{fileID: 1140001}}
--- !u!114 &1140001
MonoBehaviour:
  m_GameObject: {{fileID: 200000}}
  m_Script: {{fileID: 11500000, guid: {ENEMY_GUID}, type: 3}}
"""

UNKNOWN_GUID_UNITY = f"""\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100000
GameObject:
  m_Name: Mystery
  m_IsActive: 1
  m_Component:
  - component: {{fileID: 1140000}}
--- !u!114 &1140000
MonoBehaviour:
  m_GameObject: {{fileID: 100000}}
  m_Script: {{fileID: 11500000, guid: {'f' * 32}, type: 3}}
"""


def _meta(guid: str) -> str:
    return f"fileFormatVersion: 2\nguid: {guid}\nMonoImporter:\n  serializedVersion: 2\n"


def _write(root: Path, rel: str, content: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _build_fixture(
    root: Path,
    *,
    player: bool = True,
    enemy: bool = False,
    scene_content: str = MAIN_UNITY,
    scene_name: str = "Main.unity",
) -> None:
    if player:
        _write(root, "Assets/Scripts/PlayerController.cs", PLAYER_CS)
        _write(root, "Assets/Scripts/PlayerController.cs.meta", _meta(PLAYER_GUID))
    if enemy:
        _write(root, "Assets/Scripts/EnemyAI.cs", ENEMY_CS)
        _write(root, "Assets/Scripts/EnemyAI.cs.meta", _meta(ENEMY_GUID))
    _write(root, f"Assets/Scenes/{scene_name}", scene_content)
    _write(root, f"Assets/Scenes/{scene_name}.meta", _meta(SCENE_GUID))


# ---------------------------------------------------------------------------
# build_index: basic population
# ---------------------------------------------------------------------------

def test_scripts_indexed():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    assert any("PlayerController.cs" in p for p in idx.scripts)


def test_scenes_indexed():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    assert any("Main.unity" in p for p in idx.scenes)


def test_guid_to_script_resolved():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    assert PLAYER_GUID in idx.guid_to_script
    assert idx.guid_to_script[PLAYER_GUID].class_name == "PlayerController"


def test_unknown_guid_not_in_guid_to_script():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    assert "f" * 32 not in idx.guid_to_script


def test_empty_project():
    with tempfile.TemporaryDirectory() as tmp:
        idx = build_index(tmp)
    assert idx.scripts == {}
    assert idx.scenes == {}
    assert idx.guid_to_script == {}
    assert len(idx.graph.nodes) == 0


# ---------------------------------------------------------------------------
# Query: script_by_class
# ---------------------------------------------------------------------------

def test_script_by_class_found():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    info = idx.script_by_class("PlayerController")
    assert info is not None
    assert info.class_name == "PlayerController"


def test_script_by_class_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    assert idx.script_by_class("NonExistent") is None


# ---------------------------------------------------------------------------
# Query: scripts_in_scene
# ---------------------------------------------------------------------------

def test_scripts_in_scene():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    scene_path = next(p for p in idx.scenes if "Main.unity" in p)
    scripts = idx.scripts_in_scene(scene_path)
    assert len(scripts) == 1
    assert scripts[0].class_name == "PlayerController"


def test_scripts_in_scene_multiple():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp), enemy=True, scene_content=MULTI_SCRIPT_UNITY)
        idx = build_index(tmp)
    scene_path = next(p for p in idx.scenes if "Main.unity" in p)
    names = {s.class_name for s in idx.scripts_in_scene(scene_path)}
    assert names == {"PlayerController", "EnemyAI"}


def test_scripts_in_scene_unknown_guid_excluded():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp), scene_content=UNKNOWN_GUID_UNITY)
        idx = build_index(tmp)
    scene_path = next(p for p in idx.scenes if "Main.unity" in p)
    assert idx.scripts_in_scene(scene_path) == []


def test_scripts_in_scene_bad_path_returns_empty():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    assert idx.scripts_in_scene("does/not/exist.unity") == []


# ---------------------------------------------------------------------------
# Query: scenes_using_script
# ---------------------------------------------------------------------------

def test_scenes_using_script():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    paths = idx.scenes_using_script("PlayerController")
    assert len(paths) == 1
    assert "Main.unity" in paths[0]


def test_scenes_using_script_not_referenced():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp), enemy=True)
        idx = build_index(tmp)
    # EnemyAI is indexed but not used in MAIN_UNITY
    assert idx.scenes_using_script("EnemyAI") == []


def test_scenes_using_script_unknown_class():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    assert idx.scenes_using_script("GhostClass") == []


# ---------------------------------------------------------------------------
# Query: subclasses_of
# ---------------------------------------------------------------------------

def test_subclasses_of_monobehaviour():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp), enemy=True)
        idx = build_index(tmp)
    names = {s.class_name for s in idx.subclasses_of("MonoBehaviour")}
    assert "PlayerController" in names
    assert "EnemyAI" in names


def test_subclasses_of_no_matches():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    assert idx.subclasses_of("IUnknownInterface") == []


# ---------------------------------------------------------------------------
# Graph structure
# ---------------------------------------------------------------------------

def test_graph_has_scene_node():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    scene_nodes = [n for n in idx.graph.nodes if n.startswith("scene:")]
    assert len(scene_nodes) == 1


def test_graph_has_script_node():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    script_nodes = [n for n in idx.graph.nodes if n.startswith("script:")]
    assert len(script_nodes) == 1


def test_graph_uses_edge_scene_to_script():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    uses_edges = [
        (u, v) for u, v, d in idx.graph.edges(data=True) if d.get("type") == "uses"
    ]
    assert len(uses_edges) == 1
    u, v = uses_edges[0]
    assert u.startswith("scene:")
    assert v.startswith("script:")


def test_graph_monobehaviour_tagged_not_edged():
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp))
        idx = build_index(tmp)
    # No external:MonoBehaviour node and no inherits edge pointing to it
    assert "external:MonoBehaviour" not in idx.graph.nodes
    inherits_edges = [
        (u, v) for u, v, d in idx.graph.edges(data=True) if d.get("type") == "inherits"
    ]
    assert len(inherits_edges) == 0
    # Scripts inheriting MonoBehaviour are tagged mono=True on the node
    class_to_data = {
        d["class_name"]: d
        for _, d in idx.graph.nodes(data=True)
        if d.get("type") == "script"
    }
    assert class_to_data["PlayerController"].get("mono") is True


def test_graph_no_duplicate_uses_edges():
    # Two GOs in a scene referencing the same script should produce one edge
    same_script_twice = f"""\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100000
GameObject:
  m_Name: PlayerA
  m_IsActive: 1
  m_Component:
  - component: {{fileID: 1140000}}
--- !u!114 &1140000
MonoBehaviour:
  m_GameObject: {{fileID: 100000}}
  m_Script: {{fileID: 11500000, guid: {PLAYER_GUID}, type: 3}}
--- !u!1 &200000
GameObject:
  m_Name: PlayerB
  m_IsActive: 1
  m_Component:
  - component: {{fileID: 1140001}}
--- !u!114 &1140001
MonoBehaviour:
  m_GameObject: {{fileID: 200000}}
  m_Script: {{fileID: 11500000, guid: {PLAYER_GUID}, type: 3}}
"""
    with tempfile.TemporaryDirectory() as tmp:
        _build_fixture(Path(tmp), scene_content=same_script_twice)
        idx = build_index(tmp)
    uses_edges = [
        (u, v) for u, v, d in idx.graph.edges(data=True) if d.get("type") == "uses"
    ]
    assert len(uses_edges) == 1
