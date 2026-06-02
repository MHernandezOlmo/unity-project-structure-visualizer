import networkx as nx

from .meta_parser import build_guid_map
from .script_parser import parse_scripts, ScriptInfo
from .scene_parser import parse_unity_yaml_files, SceneInfo


class ProjectIndex:
    """Cross-referenced index of a Unity project built from all three parsers."""

    def __init__(
        self,
        root: str,
        guid_map: dict[str, str],
        scripts: dict[str, ScriptInfo],
        scenes: dict[str, SceneInfo],
        guid_to_script: dict[str, ScriptInfo],
        graph: nx.DiGraph,
    ) -> None:
        self.root = root
        self.guid_map = guid_map        # guid -> relative asset path
        self.scripts = scripts          # rel_path -> ScriptInfo
        self.scenes = scenes            # rel_path -> SceneInfo
        self.guid_to_script = guid_to_script  # guid -> ScriptInfo (cs files only)
        self.graph = graph
        self._class_to_script: dict[str, ScriptInfo] = {
            s.class_name: s for s in scripts.values() if s.class_name
        }

    # ------------------------------------------------------------------
    # Query helpers (used by the Q&A agent in later milestones)
    # ------------------------------------------------------------------

    def script_by_class(self, class_name: str) -> ScriptInfo | None:
        """Return the ScriptInfo whose class_name matches, or None."""
        return self._class_to_script.get(class_name)

    def scripts_in_scene(self, scene_path: str) -> list[ScriptInfo]:
        """All distinct scripts attached via MonoBehaviour in a scene/prefab."""
        scene = self.scenes.get(scene_path)
        if not scene:
            return []
        seen: set[str] = set()
        result: list[ScriptInfo] = []
        for comp in scene.components.values():
            if comp.script_guid:
                info = self.guid_to_script.get(comp.script_guid)
                if info and info.file_path not in seen:
                    seen.add(info.file_path)
                    result.append(info)
        return result

    def scenes_using_script(self, class_name: str) -> list[str]:
        """Paths of scenes/prefabs that reference the named script class."""
        script = self._class_to_script.get(class_name)
        if not script:
            return []
        guids = {
            g for g, s in self.guid_to_script.items() if s.file_path == script.file_path
        }
        return [
            path for path, scene in self.scenes.items()
            if any(c.script_guid in guids for c in scene.components.values())
        ]

    def subclasses_of(self, class_name: str) -> list[ScriptInfo]:
        """Scripts that directly inherit from or implement the named type."""
        return [
            s for s in self.scripts.values()
            if s.base_class == class_name or class_name in s.interfaces
        ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _script_node_id(class_name: str, class_to_script: dict[str, ScriptInfo]) -> str:
    info = class_to_script.get(class_name)
    return f"script:{info.file_path}" if info else f"external:{class_name}"


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_index(project_root: str) -> ProjectIndex:
    guid_map = build_guid_map(project_root)
    scripts: dict[str, ScriptInfo] = {s.file_path: s for s in parse_scripts(project_root)}
    scenes: dict[str, SceneInfo] = {s.file_path: s for s in parse_unity_yaml_files(project_root)}

    # Resolve guid -> ScriptInfo using the shared guid_map
    path_to_guid: dict[str, str] = {v: k for k, v in guid_map.items()}
    guid_to_script: dict[str, ScriptInfo] = {
        path_to_guid[path]: info
        for path, info in scripts.items()
        if path in path_to_guid
    }

    class_to_script: dict[str, ScriptInfo] = {
        s.class_name: s for s in scripts.values() if s.class_name
    }

    graph: nx.DiGraph = nx.DiGraph()

    # Script nodes + inheritance / interface edges
    for path, info in scripts.items():
        node = f"script:{path}"
        is_mono = info.base_class == "MonoBehaviour"
        graph.add_node(node, type="script", path=path, class_name=info.class_name, mono=is_mono)

        if info.base_class and not is_mono:
            target = _script_node_id(info.base_class, class_to_script)
            if not graph.has_node(target):
                graph.add_node(target, type="external", class_name=info.base_class)
            graph.add_edge(node, target, type="inherits")

        for iface in info.interfaces:
            target = _script_node_id(iface, class_to_script)
            if not graph.has_node(target):
                graph.add_node(target, type="external", class_name=iface)
            graph.add_edge(node, target, type="implements")

    # Script-to-script references (new, GetComponent, typed fields — filtered to project scripts)
    for path, info in scripts.items():
        src_node = f"script:{path}"
        for ref_class in info.references:
            target_info = class_to_script.get(ref_class)
            if target_info and target_info.file_path != path:
                tgt_node = f"script:{target_info.file_path}"
                if not graph.has_edge(src_node, tgt_node):
                    graph.add_edge(src_node, tgt_node, type="references")

    # Scene / prefab nodes + "uses" edges to scripts
    for path, scene in scenes.items():
        kind = "scene" if path.replace("\\", "/").endswith(".unity") else "prefab"
        scene_node = f"{kind}:{path}"
        graph.add_node(scene_node, type=kind, path=path)

        for comp in scene.components.values():
            if comp.script_guid:
                script_info = guid_to_script.get(comp.script_guid)
                if script_info:
                    script_node = f"script:{script_info.file_path}"
                    if not graph.has_node(script_node):
                        graph.add_node(
                            script_node,
                            type="script",
                            path=script_info.file_path,
                            class_name=script_info.class_name,
                        )
                    graph.add_edge(scene_node, script_node, type="uses")

    return ProjectIndex(
        root=project_root,
        guid_map=guid_map,
        scripts=scripts,
        scenes=scenes,
        guid_to_script=guid_to_script,
        graph=graph,
    )
