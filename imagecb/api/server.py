"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from imagecb.api.routes import router

# Built-in static UI (no npm). Optional React build at frontend/dist overrides.
_STATIC_BUILTIN = Path(__file__).resolve().parent.parent / "web" / "static"
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _static_dir() -> Path | None:
    if _FRONTEND_DIST.is_dir():
        return _FRONTEND_DIST
    if _STATIC_BUILTIN.is_dir():
        return _STATIC_BUILTIN
    return None


def create_app() -> FastAPI:
    app = FastAPI(title="Imagecb", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8080",
            "http://localhost:8080",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    static = _static_dir()
    if static is not None:
        app.mount("/", StaticFiles(directory=str(static), html=True), name="static")

    return app


def launch(*, host: str = "127.0.0.1", port: int = 8080) -> None:
    import uvicorn

    uvicorn.run(
        "imagecb.api.server:create_app",
        factory=True,
        host=host,
        port=port,
        reload=False,
    )
