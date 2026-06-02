# Unity Visualizer — CLAUDE.md

## What this project is
A Unity project visualizer with an agentic Q&A layer. Given a Unity project root it parses
meta files, C# scripts, and scene/prefab YAML, builds a cross-referenced index and dependency
graph, exposes it via a FastAPI REST API, and renders it in an interactive Cytoscape.js UI.

## Running
```
cd unity-visualizer
uvicorn main:app --reload        # serves on http://localhost:8000
```
Open `http://localhost:8000` — a welcome screen asks for the Unity project folder path.
No env vars required. Optionally set `UNITY_PROJECT_ROOT` to skip the welcome screen.
`ANTHROPIC_API_KEY` is only needed for the agent chat panel.

## Testing
```
cd unity-visualizer
python -m pytest -v
```
All 99 tests must stay green. No mocks — tests use real temp-dir fixtures.
Exception: `agent.ask` is patched in endpoint tests (Anthropic API is an external service).

## Project layout
```
unity-visualizer/
  parser/
    __init__.py         # iter_assets(root, suffix) — walks Assets/ pruning EXCLUDED_DIRS
    meta_parser.py      # build_guid_map(root) → {guid: rel_path}
    script_parser.py    # parse_scripts(root) → [ScriptInfo]
    scene_parser.py     # parse_unity_yaml_files(root) → [SceneInfo]
    indexer.py          # build_index(root) → ProjectIndex  ← central hub
  api/
    deps.py             # get_index FastAPI dependency (503 if no index)
    models.py           # Pydantic request/response models
    routes.py           # all API routes (see endpoints below)
  agent/
    __init__.py         # ask(question, index) → str  — Anthropic tool-use agentic loop
  static/
    index.html          # Cytoscape.js graph UI (self-contained, no build step)
  tests/
    test_meta_parser.py
    test_script_parser.py
    test_scene_parser.py
    test_indexer.py
    test_api.py
    test_agent.py
  main.py               # FastAPI app entry point
  requirements.txt
```

## API endpoints
| Method | Path | Notes |
|--------|------|-------|
| POST | `/project/load` | `{path}` → indexes project, stores in app.state.index |
| GET | `/scenes` | list all scenes/prefabs |
| GET | `/scenes/{path}` | scene detail with GameObjects + script classes |
| GET | `/scripts` | list all scripts |
| GET | `/scripts/{class_name}` | script detail with inheritance + used_in_scenes |
| GET | `/graph/dependencies` | full node/edge graph for Cytoscape |
| POST | `/agent/ask` | `{question}` → `{answer}` via agentic loop |
| GET | `/health` | `{"status": "ok"}` |

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
| 9 | Project loader — welcome screen + `POST /project/load`, no env var required |
| 10 | Asset filtering — scan restricted to `Assets/`; EXCLUDED_DIRS prunes plugins |
| 11 | MonoBehaviour visual distinction — no hub node; scripts inheriting MB get `mono=True` flag, rendered amber in frontend |
| 12 | Script-to-script dependency detection — `new X()`, `GetComponent<X>`, typed fields → `"references"` edges (purple) |
| 13 | Auto-sized script nodes — ellipse nodes use `width/height: label` + padding so long class names always fit |

## Key design decisions
- **Asset scanning**: only `Assets/` is walked; `EXCLUDED_DIRS` in `parser/__init__.py` prunes
  Unity built-ins (`Plugins`, `TextMesh Pro`, `Standard Assets`, etc.) and common third-party
  packages (DOTween, Photon, Cinemachine, FMOD, Spine, …). Add folder names there to extend.
- **Paths**: stored with OS separators internally; API routes accept `/`-separated paths and
  normalize with `path.replace("/", os.sep)`
- **Graph node IDs**: `"scene:Assets\Scenes\Main.unity"`, `"script:..."`, `"external:ClassName"`
  — prefix encodes type
- **Index lifecycle**: built on demand via `POST /project/load`; stored in `app.state.index`;
  all data routes return 503 if index is None; re-loading replaces it atomically
- **Unity YAML parsing**: split on `--- !u!<classID> &<fileID>` regex; strip `%YAML`/`%TAG`
  lines; `yaml.safe_load` each block body independently; `stripped` suffix handled
- **Agent model**: `claude-haiku-4-5-20251001` with ephemeral prompt caching on system prompt;
  6 tools wrapping ProjectIndex query methods
- **MonoBehaviour handling**: scripts whose `base_class == "MonoBehaviour"` are tagged `mono=True`
  on the graph node instead of creating an `external:MonoBehaviour` hub node. The `GraphNode`
  Pydantic model carries `mono: bool`; the frontend uses a `node[?mono]` Cytoscape selector.
- **Script references**: `ScriptInfo.references` is populated by three regex patterns
  (`NEW_RE`, `UNITY_GENERIC_RE`, `FIELD_TYPE_RE`) in `script_parser.py`. The indexer filters
  those to known project scripts and creates `"references"` edges; non-project types are silently
  ignored to avoid noise from Unity/system types.
- **No mocks in tests**: all parser/indexer/API tests build real temp-dir fixtures;
  `agent.ask` is the only thing patched (external API boundary)

## Next milestone candidates
- **Health report** — `GET /health/report`: broken GUID refs, unused scripts, scripts in no scene
- **Richer graph** — extend parsers to surface material/texture/audio GUID refs as new node types
- **Streaming agent** — `GET /agent/ask/stream` SSE endpoint for token-by-token chat responses

## Dependencies (requirements.txt)
```
fastapi, uvicorn, pyyaml, networkx, anthropic, python-dotenv, pytest
```
`httpx` must be installed for FastAPI TestClient (it is, transitively).

## Repository
https://github.com/MHernandezOlmo/unity-project-structure-visualizer
