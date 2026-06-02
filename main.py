from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Unity Visualizer")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}
