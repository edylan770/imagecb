"""Resolve which static UI bundle serve-web should mount."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

_PKG_WEB = Path(__file__).resolve().parent.parent / "web"
_SHIPPED_REACT = _PKG_WEB / "frontend_dist"
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
_BUILTIN_STATIC = _PKG_WEB / "static"


class StaticUiKind(str, Enum):
    REACT = "react"
    BUILTIN = "builtin"
    NONE = "none"


def resolve_static_dir() -> tuple[Path | None, StaticUiKind]:
    """Return (directory, kind) for the best available UI bundle."""
    if _SHIPPED_REACT.is_dir() and (_SHIPPED_REACT / "index.html").is_file():
        return _SHIPPED_REACT, StaticUiKind.REACT
    if _FRONTEND_DIST.is_dir() and (_FRONTEND_DIST / "index.html").is_file():
        return _FRONTEND_DIST, StaticUiKind.REACT
    if _BUILTIN_STATIC.is_dir():
        return _BUILTIN_STATIC, StaticUiKind.BUILTIN
    return None, StaticUiKind.NONE


def _react_bundle_label(static_dir: Path) -> str:
    """Human-readable label for the mounted React bundle (ATLAS vs legacy)."""
    try:
        html = (static_dir / "index.html").read_text(encoding="utf-8")
    except OSError:
        return "React"
    if "ATLAS" in html.upper():
        return "ATLAS (React, imagecb/web/frontend_dist)"
    if static_dir == _SHIPPED_REACT:
        return "React (imagecb/web/frontend_dist)"
    return "React (frontend/dist)"


def format_serve_web_urls(*, host: str, port: int) -> list[str]:
    """Lines to print when starting serve-web."""
    static, kind = resolve_static_dir()
    base = f"http://{host}:{port}"
    lines = [f"Chat UI:   {base}/"]
    if kind == StaticUiKind.REACT and static is not None:
        lines.append(f"UI bundle: {_react_bundle_label(static)}")
        lines.append(f"Admin UI:  {base}/admin")
        return lines
    lines.append(
        "Admin UI:  not available (missing bundled React build in imagecb/web/frontend_dist)"
    )
    if kind == StaticUiKind.BUILTIN:
        lines.append(
            "  Using built-in static chat only. Ask a maintainer to ship frontend_dist or use Docker."
        )
    return lines
