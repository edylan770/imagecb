"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from imagecb.api.routes import router
from imagecb.api.static_ui import resolve_static_dir
from imagecb.admin.routes import router as admin_router
from imagecb.telemetry.schema import ensure_telemetry_schema


def create_app() -> FastAPI:
    ensure_telemetry_schema()
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
    app.include_router(admin_router)

    static, _kind = resolve_static_dir()
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
