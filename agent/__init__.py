import os

import anthropic

from parser.indexer import ProjectIndex

_TOOLS = [
    {
        "name": "list_scenes",
        "description": "List all scene and prefab asset paths in the Unity project.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_scripts",
        "description": "List all C# script class names in the Unity project.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "scripts_in_scene",
        "description": (
            "Return the C# script classes attached via MonoBehaviour in a given scene or prefab."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scene_path": {
                    "type": "string",
                    "description": "Relative asset path of the scene/prefab (forward slashes accepted).",
                }
            },
            "required": ["scene_path"],
        },
    },
    {
        "name": "scenes_using_script",
        "description": "Return paths of scenes/prefabs that reference a named C# class.",
        "input_schema": {
            "type": "object",
            "properties": {
                "class_name": {"type": "string", "description": "C# class name to look up."}
            },
            "required": ["class_name"],
        },
    },
    {
        "name": "subclasses_of",
        "description": "Return script classes that directly inherit from or implement a named type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "class_name": {"type": "string", "description": "Base class or interface name."}
            },
            "required": ["class_name"],
        },
    },
    {
        "name": "script_by_class",
        "description": "Return details (base class, interfaces, serialized fields, file path) for a C# class.",
        "input_schema": {
            "type": "object",
            "properties": {
                "class_name": {"type": "string", "description": "C# class name to look up."}
            },
            "required": ["class_name"],
        },
    },
]

_SYSTEM = (
    "You are a Unity project assistant. Use the provided tools to query the project index "
    "and answer the user's question accurately. Be concise. If the question cannot be answered "
    "from the project data, say so clearly."
)


def _dispatch(name: str, tool_input: dict, index: ProjectIndex) -> str:
    if name == "list_scenes":
        return "\n".join(index.scenes.keys()) or "No scenes found."

    if name == "list_scripts":
        names = [s.class_name or s.file_path for s in index.scripts.values()]
        return ", ".join(names) if names else "No scripts found."

    if name == "scripts_in_scene":
        path = tool_input["scene_path"].replace("/", os.sep)
        scripts = index.scripts_in_scene(path)
        if not scripts:
            return "No scripts found in that scene."
        return ", ".join(s.class_name or s.file_path for s in scripts)

    if name == "scenes_using_script":
        paths = index.scenes_using_script(tool_input["class_name"])
        return "\n".join(paths) if paths else "No scenes use that script."

    if name == "subclasses_of":
        scripts = index.subclasses_of(tool_input["class_name"])
        if not scripts:
            return "No subclasses found."
        return ", ".join(s.class_name or s.file_path for s in scripts)

    if name == "script_by_class":
        info = index.script_by_class(tool_input["class_name"])
        if info is None:
            return "Script not found."
        fields = [(f["type"], f["name"]) for f in info.serialize_fields]
        return (
            f"class: {info.class_name}, "
            f"base: {info.base_class or 'none'}, "
            f"interfaces: {info.interfaces or []}, "
            f"path: {info.file_path}, "
            f"serialize_fields: {fields}"
        )

    return f"Unknown tool: {name}"


def ask(question: str, index: ProjectIndex) -> str:
    client = anthropic.Anthropic()
    messages: list = [{"role": "user", "content": question}]

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
            tools=_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = _dispatch(block.name, block.input, index)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )

        messages.append({"role": "user", "content": tool_results})

    return "I was unable to answer that question."
