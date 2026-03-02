from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from routers import sources,sync
import os

app = FastAPI(title="MLIB Downloader")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(sources.router)
app.include_router(sync.router)


# ── Serve the UI ──────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="ui"), name="static")

@app.get("/")
def serve_ui():
    return FileResponse("ui/index.html")