# Unity Visualizer — CLAUDE.md

## What this project is
A Unity project visualizer with an agentic Q&A layer. Given a Unity project root it parses
meta files, C# scripts, and scene/prefab YAML, builds a cross-referenced index and dependency
graph, exposes it via a FastAPI REST API, and renders it in an interactive Cytoscape.js UI.

## Running
```
set UNITY_PROJECT_ROOT=C:\path\to\MyUnityProject
uvicorn main:app --reload        # serves on http://localhost:8000
```
`/` redirects to the graph UI at `/static/index.html`.

## Testing
```
cd unity-visualizer
python -m pytest -v
```
All 70 tests must stay green. No mocks — tests use real temp-dir fixtures.

## Project layout
```
unity-visualizer/
  parser/
    meta_parser.py      # build_guid_map(root) → {guid: rel_path}
    script_parser.py    # parse_scripts(root) → [ScriptInfo]
    scene_parser.py     # parse_unity_yaml_files(root) → [SceneInfo]
    indexer.py          # build_index(root) → ProjectIndex  ← central hub
  api/
    deps.py             # get_index FastAPI dependency (503 if no index)
    models.py           # Pydantic response models
    routes.py           # /scenes, /scenes/{path}, /scripts, /scripts/{class}, /graph/dependencies
  agent/                # Milestone 8 — Q&A agent (not yet built)
  static/
    index.html          # Cytoscape.js graph UI (self-contained, no build step)
  tests/
    test_meta_parser.py
    test_script_parser.py
    test_scene_parser.py
    test_indexer.py
    test_api.py
  main.py               # FastAPI app with lifespan (builds index on startup)
  requirements.txt
```

## Milestones completed
| # | What |
|---|------|
| 1 | FastAPI scaffold + health endpoint |
| 2 | Meta parser — GUID → asset path map |
| 3 | C# script parser — class, base, interfaces, SerializeFields |
| 4 | Scene/prefab YAML parser — GameObjects, components, MonoBehaviour GUID refs |
| 5 | Index / aggregation layer — cross-references all parsers, networkx graph |
| 6 | REST API — `/scenes`, `/scripts`, `/graph/dependencies` + Pydantic models |
| 7 | Frontend — Cytoscape.js graph, sidebar, click-to-detail panel |
| 8 | Q&A agent — Anthropic SDK tool-use loop, `POST /agent/ask`, chat panel in frontend |

## Next milestone
TBD

## Key design decisions
- **Paths**: stored with OS separators internally; API routes accept `/`-separated paths and normalize with `path.replace("/", os.sep)`
- **Graph node IDs**: `"scene:Assets\Scenes\Main.unity"`, `"script:..."`, `"external:ClassName"` — prefix encodes type
- **Index startup**: built once in FastAPI lifespan from `UNITY_PROJECT_ROOT` env var; stored in `app.state.index`; returns 503 if not set
- **Unity YAML parsing**: split on `--- !u!<classID> &<fileID>` regex; strip `%YAML`/`%TAG` lines; `yaml.safe_load` each block body independently; `stripped` suffix handled
- **No mocks in tests**: all parser and API tests build real temp-dir fixtures

## Dependencies (requirements.txt)
```
fastapi, uvicorn, pyyaml, networkx, anthropic, python-dotenv, pytest
```
`httpx` must be installed for FastAPI TestClient (it is, transitively).
