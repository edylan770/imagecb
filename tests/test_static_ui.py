"""Static UI resolution for serve-web."""

from __future__ import annotations

from pathlib import Path

from imagecb.api.static_ui import StaticUiKind, resolve_static_dir


def test_resolve_static_prefers_shipped_frontend_dist():
    static, kind = resolve_static_dir()
    shipped = Path(__file__).resolve().parents[1] / "imagecb" / "web" / "frontend_dist"
    assert shipped.is_dir()
    assert kind == StaticUiKind.REACT
    assert static == shipped
