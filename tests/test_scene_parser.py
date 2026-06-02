import os
import tempfile
from pathlib import Path

from parser.scene_parser import (
    ComponentRef,
    GameObjectInfo,
    SceneInfo,
    parse_unity_yaml,
    parse_unity_yaml_files,
)

# ---------------------------------------------------------------------------
# Minimal Unity YAML fixtures
# ---------------------------------------------------------------------------

SIMPLE_SCENE = """\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100000
GameObject:
  m_ObjectHideFlags: 0
  m_Name: Player
  m_IsActive: 1
  m_Component:
  - component: {fileID: 400000}
  - component: {fileID: 1140000}
--- !u!4 &400000
Transform:
  m_ObjectHideFlags: 0
  m_GameObject: {fileID: 100000}
--- !u!114 &1140000
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_GameObject: {fileID: 100000}
  m_Script: {fileID: 11500000, guid: abcdef1234567890abcdef1234567890, type: 3}
"""

INACTIVE_GO_SCENE = """\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &200000
GameObject:
  m_Name: HiddenObject
  m_IsActive: 0
  m_Component: []
"""

MULTI_GO_SCENE = """\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100000
GameObject:
  m_Name: Alpha
  m_IsActive: 1
  m_Component:
  - component: {fileID: 400000}
--- !u!4 &400000
Transform:
  m_GameObject: {fileID: 100000}
--- !u!1 &100001
GameObject:
  m_Name: Beta
  m_IsActive: 1
  m_Component:
  - component: {fileID: 400001}
  - component: {fileID: 1140001}
--- !u!4 &400001
Transform:
  m_GameObject: {fileID: 100001}
--- !u!114 &1140001
MonoBehaviour:
  m_GameObject: {fileID: 100001}
  m_Script: {fileID: 11500000, guid: deadbeefdeadbeefdeadbeefdeadbeef, type: 3}
"""

NO_GUID_MONOBEHAVIOUR = """\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100000
GameObject:
  m_Name: Foo
  m_IsActive: 1
  m_Component:
  - component: {fileID: 1140000}
--- !u!114 &1140000
MonoBehaviour:
  m_GameObject: {fileID: 100000}
  m_Script: {fileID: 0}
"""

UNKNOWN_COMPONENT_SCENE = """\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100000
GameObject:
  m_Name: Rigidbody
  m_IsActive: 1
  m_Component:
  - component: {fileID: 540000}
--- !u!54 &540000
Rigidbody:
  m_Mass: 1
"""

STRIPPED_BLOCK_SCENE = """\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100000
GameObject:
  m_Name: Root
  m_IsActive: 1
  m_Component: []
--- !u!4 &400000 stripped
Transform:
  m_GameObject: {fileID: 100000}
"""

EMPTY_FILE = """\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
"""


# ---------------------------------------------------------------------------
# Tests for parse_unity_yaml
# ---------------------------------------------------------------------------


def test_single_game_object_name_and_active():
    info = parse_unity_yaml("Main.unity", SIMPLE_SCENE)
    assert len(info.game_objects) == 1
    go = info.game_objects[0]
    assert go.name == "Player"
    assert go.is_active is True


def test_game_object_component_file_ids():
    info = parse_unity_yaml("Main.unity", SIMPLE_SCENE)
    go = info.game_objects[0]
    assert 400000 in go.component_file_ids
    assert 1140000 in go.component_file_ids


def test_transform_component_registered():
    info = parse_unity_yaml("Main.unity", SIMPLE_SCENE)
    assert 400000 in info.components
    assert info.components[400000].type_name == "Transform"
    assert info.components[400000].script_guid is None


def test_monobehaviour_script_guid():
    info = parse_unity_yaml("Main.unity", SIMPLE_SCENE)
    assert 1140000 in info.components
    ref = info.components[1140000]
    assert ref.type_name == "MonoBehaviour"
    assert ref.script_guid == "abcdef1234567890abcdef1234567890"


def test_inactive_game_object():
    info = parse_unity_yaml("Inactive.unity", INACTIVE_GO_SCENE)
    assert len(info.game_objects) == 1
    assert info.game_objects[0].is_active is False
    assert info.game_objects[0].name == "HiddenObject"


def test_multiple_game_objects():
    info = parse_unity_yaml("Multi.unity", MULTI_GO_SCENE)
    names = {go.name for go in info.game_objects}
    assert names == {"Alpha", "Beta"}


def test_multi_scene_component_map():
    info = parse_unity_yaml("Multi.unity", MULTI_GO_SCENE)
    assert info.components[1140001].script_guid == "deadbeefdeadbeefdeadbeefdeadbeef"


def test_monobehaviour_no_guid():
    info = parse_unity_yaml("NoGuid.unity", NO_GUID_MONOBEHAVIOUR)
    ref = info.components[1140000]
    assert ref.type_name == "MonoBehaviour"
    assert ref.script_guid is None


def test_unknown_component_type_name():
    info = parse_unity_yaml("Physics.unity", UNKNOWN_COMPONENT_SCENE)
    assert 540000 in info.components
    assert info.components[540000].type_name == "Rigidbody"


def test_stripped_block_is_parsed():
    info = parse_unity_yaml("Stripped.unity", STRIPPED_BLOCK_SCENE)
    # The stripped Transform block should still register as a component
    assert 400000 in info.components
    assert info.components[400000].type_name == "Transform"


def test_empty_file_returns_empty_scene():
    info = parse_unity_yaml("Empty.unity", EMPTY_FILE)
    assert info.game_objects == []
    assert info.components == {}


def test_file_path_stored():
    info = parse_unity_yaml("Assets/Scenes/Main.unity", SIMPLE_SCENE)
    assert info.file_path == "Assets/Scenes/Main.unity"


# ---------------------------------------------------------------------------
# Tests for parse_unity_yaml_files (filesystem walk)
# ---------------------------------------------------------------------------


def _write_asset(root: Path, rel_path: str, content: str) -> None:
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_discovers_unity_and_prefab_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_asset(root, "Assets/Scenes/Main.unity", SIMPLE_SCENE)
        _write_asset(root, "Assets/Prefabs/Player.prefab", SIMPLE_SCENE)
        results = parse_unity_yaml_files(tmp)
    assert len(results) == 2
    paths = {r.file_path for r in results}
    assert any("Main.unity" in p for p in paths)
    assert any("Player.prefab" in p for p in paths)


def test_ignores_non_yaml_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_asset(root, "Assets/Scenes/Main.unity", SIMPLE_SCENE)
        _write_asset(root, "Assets/Scripts/Player.cs", "public class Player {}")
        results = parse_unity_yaml_files(tmp)
    assert len(results) == 1


def test_empty_directory():
    with tempfile.TemporaryDirectory() as tmp:
        assert parse_unity_yaml_files(tmp) == []
