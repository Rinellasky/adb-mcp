#!/usr/bin/env python3
"""Build Photoshop MCP release artifacts (Photoshop-only fork).

Produces, into ./dist:
  - photoshop-mcp.dxt          Claude Desktop extension (MCP server bundle)
  - photoshop-mcp-plugin.ccx   Adobe Photoshop UXP plugin package

Cross-platform (uses stdlib zipfile) so it runs identically in CI (Linux)
and locally on Windows/macOS. The proxy executable is built separately in
the release workflow via `pkg` (needs Node).

Usage:
    python scripts/build_release.py [VERSION]

If VERSION is omitted it is read from dxt/ps/manifest.json.
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"

# Python modules that make up the MCP server, copied into the .dxt alongside
# the manifest. Mirrors dxt/build's ps target.
DXT_PY_FILES = [
    "core.py",
    "logger.py",
    "ps-mcp.py",
    "socket_client.py",
    "fonts.py",
]

# Files/patterns to exclude from the .ccx plugin package.
CCX_EXCLUDE_SUFFIXES = (".OGjs", ".OGpy")
CCX_EXCLUDE_NAMES = {".DS_Store"}


def _add_file(zf: zipfile.ZipFile, src: Path, arcname: str) -> None:
    zf.write(src, arcname)
    print(f"    + {arcname}")


def build_dxt(version: str) -> Path:
    """Zip dxt/ps/manifest.json + the MCP server .py files into a .dxt."""
    src_dir = REPO / "dxt" / "ps"
    mcp_dir = REPO / "mcp"
    out = DIST / "photoshop-mcp.dxt"

    manifest = json.loads((src_dir / "manifest.json").read_text(encoding="utf-8"))
    print(f"Building {out.name} (manifest version {manifest['version']})...")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_file(zf, src_dir / "manifest.json", "manifest.json")
        for name in DXT_PY_FILES:
            src = mcp_dir / name
            if not src.exists():
                raise FileNotFoundError(f"required MCP file missing: {src}")
            _add_file(zf, src, name)
    return out


def build_ccx() -> Path:
    """Zip the uxp/ps plugin folder into a double-click-installable .ccx."""
    src_dir = REPO / "uxp" / "ps"
    out = DIST / "photoshop-mcp-plugin.ccx"
    print(f"Building {out.name}...")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix in CCX_EXCLUDE_SUFFIXES or path.name in CCX_EXCLUDE_NAMES:
                continue
            arcname = path.relative_to(src_dir).as_posix()
            _add_file(zf, path, arcname)
    return out


def main() -> int:
    DIST.mkdir(exist_ok=True)

    if len(sys.argv) > 1:
        version = sys.argv[1].lstrip("v")
    else:
        manifest = json.loads(
            (REPO / "dxt" / "ps" / "manifest.json").read_text(encoding="utf-8")
        )
        version = manifest["version"]

    print(f"=== Building Photoshop MCP release artifacts (v{version}) ===\n")
    dxt = build_dxt(version)
    print()
    ccx = build_ccx()
    print()
    print("Done. Artifacts:")
    for art in (dxt, ccx):
        print(f"  {art}  ({art.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
