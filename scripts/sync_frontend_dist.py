#!/usr/bin/env python3
"""Copy frontend/dist into imagecb/web/frontend_dist for serve-web (maintainers/CI)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "dist"
DST = ROOT / "imagecb" / "web" / "frontend_dist"


def main() -> int:
    if not (SRC / "index.html").is_file():
        print("Run 'npm run build' in frontend/ first.", file=sys.stderr)
        return 1
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    print(f"Synced {SRC} -> {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
