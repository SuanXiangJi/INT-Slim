from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from app.config import settings
from app.api.v1 import api_router
from app.models import Base, engine
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="XBots Agent API", version="1.0.0",
    openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs", redoc_url="/api/v1/redoc")

app.add_middleware(CORSMiddleware, allow_origins=settings.backend_cors_origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router)

# ── Static / SPA ──────────────────────────────────────────────
_fe = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
_index = os.path.join(_fe, "index.html")

if os.path.isdir(_fe):
    # Mount static assets (JS, CSS, images under /app/assets/)
    assets_dir = os.path.join(_fe, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/app/assets", StaticFiles(directory=assets_dir), name="assets")

    # Serve individual root-level files (favicon, logo, etc.)
    for f in os.listdir(_fe):
        fp = os.path.join(_fe, f)
        if os.path.isfile(fp) and f != "index.html":
            # Use factory to avoid closure bug
            def _make_static(path: str):
                def handler():
                    return FileResponse(path)
                return handler
            app.get("/app/" + f, include_in_schema=False)(_make_static(fp))

    # SPA catch-all: serve index.html for every /app/* path
    if os.path.isfile(_index):
        @app.get("/app/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            return FileResponse(_index)

# ── Health & root ─────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/")
def root():
    return RedirectResponse(url="/app/")

# ── Shortcut redirects (closure-safe via factory) ─────────────
def _make_redirect(route_path: str):
    def handler():
        return RedirectResponse(url="/app" + route_path)
    return handler

for p in ["/chat", "/dashboard", "/courses", "/path", "/diagnosis", "/reports"]:
    app.get(p, include_in_schema=False)(_make_redirect(p))
