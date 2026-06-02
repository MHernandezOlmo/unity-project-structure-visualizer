import itertools
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path

from parser import iter_assets

# Matches:  --- !u!<classID> &<fileID>  (optionally trailing "stripped")
BLOCK_RE = re.compile(
    r"^--- !u!(\d+) &(\d+)(?:\s+stripped)?[ \t]*$", re.MULTILINE
)

UNITY_CLASS_NAMES: dict[int, str] = {
    1: "GameObject",
    4: "Transform",
    20: "Camera",
    23: "MeshRenderer",
    33: "MeshFilter",
    54: "Rigidbody",
    65: "BoxCollider",
    114: "MonoBehaviour",
    136: "RectTransform",
    1001: "PrefabInstance",
}


@dataclass
class ComponentRef:
    type_name: str
    file_id: int
    script_guid: str | None = None


@dataclass
class GameObjectInfo:
    file_id: int
    name: str
    is_active: bool
    component_file_ids: list[int] = field(default_factory=list)


@dataclass
class SceneInfo:
    file_path: str
    game_objects: list[GameObjectInfo] = field(default_factory=list)
    # keyed by local file_id so callers can join GO component lists to ComponentRef
    components: dict[int, ComponentRef] = field(default_factory=dict)


def _split_blocks(text: str) -> list[tuple[int, int, str]]:
    """Return (class_id, file_id, yaml_body) for each Unity YAML block."""
    # Normalize line endings; drop %YAML / %TAG directive lines
    cleaned = "\n".join(
        line for line in text.replace("\r\n", "\n").splitlines()
        if not line.startswith("%")
    )
    headers = list(BLOCK_RE.finditer(cleaned))
    blocks: list[tuple[int, int, str]] = []
    for i, m in enumerate(headers):
        class_id = int(m.group(1))
        file_id = int(m.group(2))
        body_start = m.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(cleaned)
        yaml_body = cleaned[body_start:body_end].strip()
        blocks.append((class_id, file_id, yaml_body))
    return blocks


def _load_block(yaml_body: str) -> dict:
    try:
        result = yaml.safe_load(yaml_body)
        return result if isinstance(result, dict) else {}
    except yaml.YAMLError:
        return {}


def parse_unity_yaml(file_path: str, text: str) -> SceneInfo:
    scene = SceneInfo(file_path=file_path)

    for class_id, file_id, yaml_body in _split_blocks(text):
        data = _load_block(yaml_body)
        type_name = UNITY_CLASS_NAMES.get(class_id, f"UnityClass_{class_id}")

        if class_id == 1:  # GameObject
            go = data.get("GameObject", {})
            raw_components = go.get("m_Component") or []
            component_file_ids = [
                int(entry["component"]["fileID"])
                for entry in raw_components
                if isinstance(entry.get("component"), dict)
                and entry["component"].get("fileID") is not None
            ]
            scene.game_objects.append(GameObjectInfo(
                file_id=file_id,
                name=go.get("m_Name", ""),
                is_active=bool(go.get("m_IsActive", 1)),
                component_file_ids=component_file_ids,
            ))

        elif class_id == 114:  # MonoBehaviour
            mb = data.get("MonoBehaviour", {})
            script_ref = mb.get("m_Script") or {}
            script_guid = script_ref.get("guid") if isinstance(script_ref, dict) else None
            scene.components[file_id] = ComponentRef(
                type_name="MonoBehaviour",
                file_id=file_id,
                script_guid=script_guid or None,
            )

        else:
            scene.components[file_id] = ComponentRef(
                type_name=type_name,
                file_id=file_id,
            )

    return scene


def parse_unity_yaml_files(project_root: str) -> list[SceneInfo]:
    root = Path(project_root)
    results: list[SceneInfo] = []
    for path in sorted(itertools.chain(
        iter_assets(project_root, ".unity"),
        iter_assets(project_root, ".prefab"),
    )):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(path.relative_to(root))
        results.append(parse_unity_yaml(rel, text))
    return results
