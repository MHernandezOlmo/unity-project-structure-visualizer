from fastapi import HTTPException, Request

from parser.indexer import ProjectIndex


def get_index(request: Request) -> ProjectIndex:
    idx = getattr(request.app.state, "index", None)
    if idx is None:
        raise HTTPException(503, detail="Index not available: set UNITY_PROJECT_ROOT")
    return idx
