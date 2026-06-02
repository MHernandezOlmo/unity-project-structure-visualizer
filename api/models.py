from pydantic import BaseModel


class SceneSummary(BaseModel):
    path: str
    kind: str
    game_object_count: int


class ComponentInfo(BaseModel):
    type_name: str
    script_class: str | None = None


class GameObjectDetail(BaseModel):
    name: str
    is_active: bool
    components: list[ComponentInfo]


class SceneDetail(BaseModel):
    path: str
    kind: str
    game_objects: list[GameObjectDetail]
    script_classes: list[str]


class ScriptSummary(BaseModel):
    path: str
    class_name: str | None
    base_class: str | None
    interfaces: list[str]


class ScriptDetail(BaseModel):
    path: str
    class_name: str | None
    base_class: str | None
    interfaces: list[str]
    usings: list[str]
    serialize_fields: list[dict]
    used_in_scenes: list[str]


class GraphNode(BaseModel):
    id: str
    type: str
    label: str


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


class LoadRequest(BaseModel):
    path: str


class LoadResponse(BaseModel):
    status: str
    scene_count: int
    script_count: int
