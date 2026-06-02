import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from parser.indexer import ProjectIndex, build_index
from .deps import get_index
import agent as _agent

from .models import (
    AskRequest,
    AskResponse,
    ComponentInfo,
    LoadRequest,
    LoadResponse,
    GameObjectDetail,
    GraphData,
    GraphEdge,
    GraphNode,
    SceneDetail,
    SceneSummary,
    ScriptDetail,
    ScriptSummary,
)

router = APIRouter()


def _kind(path: str) -> str:
    return "scene" if path.replace("\\", "/").endswith(".unity") else "prefab"


def _graph_label(node_id: str, graph) -> str:
    data = graph.nodes[node_id]
    node_type = data.get("type", "")
    if node_type in ("script", "external"):
        return data.get("class_name") or node_id.split(":", 1)[-1]
    path = data.get("path", "")
    return Path(path).name if path else node_id.split(":", 1)[-1]


# ---------------------------------------------------------------------------
# Scenes / prefabs
# ---------------------------------------------------------------------------

@router.get("/scenes", response_model=list[SceneSummary])
def list_scenes(index: ProjectIndex = Depends(get_index)):
    return [
        SceneSummary(
            path=path,
            kind=_kind(path),
            game_object_count=len(scene.game_objects),
        )
        for path, scene in sorted(index.scenes.items())
    ]


@router.get("/scenes/{path:path}", response_model=SceneDetail)
def get_scene(path: str, index: ProjectIndex = Depends(get_index)):
    normalized = path.replace("/", os.sep)
    scene = index.scenes.get(normalized)
    if scene is None:
        raise HTTPException(404, detail=f"Scene not found: {path}")

    game_objects = []
    for go in scene.game_objects:
        comps = []
        for fid in go.component_file_ids:
            comp = scene.components.get(fid)
            if comp:
                script_class = None
                if comp.script_guid:
                    info = index.guid_to_script.get(comp.script_guid)
                    script_class = info.class_name if info else None
                comps.append(ComponentInfo(type_name=comp.type_name, script_class=script_class))
        game_objects.append(
            GameObjectDetail(name=go.name, is_active=go.is_active, components=comps)
        )

    script_classes = [
        s.class_name for s in index.scripts_in_scene(normalized) if s.class_name
    ]

    return SceneDetail(
        path=path,
        kind=_kind(normalized),
        game_objects=game_objects,
        script_classes=script_classes,
    )


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------

@router.get("/scripts", response_model=list[ScriptSummary])
def list_scripts(index: ProjectIndex = Depends(get_index)):
    return [
        ScriptSummary(
            path=info.file_path,
            class_name=info.class_name,
            base_class=info.base_class,
            interfaces=info.interfaces,
        )
        for info in sorted(index.scripts.values(), key=lambda s: s.file_path)
    ]


@router.get("/scripts/{class_name}", response_model=ScriptDetail)
def get_script(class_name: str, index: ProjectIndex = Depends(get_index)):
    info = index.script_by_class(class_name)
    if info is None:
        raise HTTPException(404, detail=f"Script not found: {class_name}")

    return ScriptDetail(
        path=info.file_path,
        class_name=info.class_name,
        base_class=info.base_class,
        interfaces=info.interfaces,
        usings=info.usings,
        serialize_fields=info.serialize_fields,
        used_in_scenes=index.scenes_using_script(class_name),
    )


# ---------------------------------------------------------------------------
# Project loader
# ---------------------------------------------------------------------------

@router.post("/project/load", response_model=LoadResponse)
def load_project(req: LoadRequest, request: Request):
    path = req.path.strip()
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Directory not found: {path}")
    try:
        index = build_index(path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to index project: {exc}")
    request.app.state.index = index
    return LoadResponse(
        status="ok",
        scene_count=len(index.scenes),
        script_count=len(index.scripts),
    )


# ---------------------------------------------------------------------------
# Agent Q&A
# ---------------------------------------------------------------------------

@router.post("/agent/ask", response_model=AskResponse)
def agent_ask(req: AskRequest, index: ProjectIndex = Depends(get_index)):
    answer = _agent.ask(req.question, index)
    return AskResponse(answer=answer)


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------

@router.get("/graph/dependencies", response_model=GraphData)
def get_graph(index: ProjectIndex = Depends(get_index)):
    g = index.graph
    nodes = [
        GraphNode(
            id=n,
            type=g.nodes[n].get("type", "unknown"),
            label=_graph_label(n, g),
            mono=g.nodes[n].get("mono", False),
        )
        for n in g.nodes
    ]
    edges = [
        GraphEdge(source=u, target=v, type=d.get("type", ""))
        for u, v, d in g.edges(data=True)
    ]
    return GraphData(nodes=nodes, edges=edges)
