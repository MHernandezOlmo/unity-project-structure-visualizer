import os
import tempfile
from pathlib import Path

from parser.meta_parser import build_guid_map

SAMPLE_META = """\
fileFormatVersion: 2
guid: {guid}
MonoImporter:
  serializedVersion: 2
  defaultReferences: []
  executionOrder: 0
"""


def _write_meta(directory: Path, relative_asset: str, guid: str) -> None:
    meta_path = directory / (relative_asset + ".meta")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(SAMPLE_META.format(guid=guid), encoding="utf-8")


def test_single_meta_file():
    with tempfile.TemporaryDirectory() as tmp:
        _write_meta(Path(tmp), "Assets/Scripts/Player.cs", "a" * 32)
        result = build_guid_map(tmp)
    assert result == {"a" * 32: os.path.join("Assets", "Scripts", "Player.cs")}


def test_multiple_meta_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_meta(root, "Assets/Scripts/Player.cs", "a" * 32)
        _write_meta(root, "Assets/Scenes/Main.unity", "b" * 32)
        _write_meta(root, "Assets/Prefabs/Enemy.prefab", "c" * 32)
        result = build_guid_map(tmp)
    assert len(result) == 3
    assert result["b" * 32] == os.path.join("Assets", "Scenes", "Main.unity")


def test_missing_guid_is_skipped():
    with tempfile.TemporaryDirectory() as tmp:
        bad_meta = Path(tmp) / "Assets" / "broken.cs.meta"
        bad_meta.parent.mkdir(parents=True)
        bad_meta.write_text("fileFormatVersion: 2\n", encoding="utf-8")
        result = build_guid_map(tmp)
    assert result == {}


def test_empty_directory():
    with tempfile.TemporaryDirectory() as tmp:
        assert build_guid_map(tmp) == {}
