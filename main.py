import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router
from parser.indexer import build_index


@asynccontextmanager
async def lifespan(app: FastAPI):
    root = os.environ.get("UNITY_PROJECT_ROOT", "")
    app.state.index = build_index(root) if root else None
    yield


app = FastAPI(title="Unity Visualizer", lifespan=lifespan)

if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
