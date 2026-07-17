#!/usr/bin/env python3
"""Build adb-mcp release artifacts.

Produces, into ./dist, for each requested app:
  - <app>-mcp.dxt          Claude Desktop extension (MCP server bundle)
  - <app>-mcp-plugin.ccx   Adobe UXP plugin package

Currently packaged apps: photoshop, indesign.

Cross-platform (uses stdlib zipfile) so it runs identically in CI (Linux)
and locally on Windows/macOS. The proxy executable is built separately in
the release workflow via `pkg` (needs Node).

Usage:
    python scripts/build_release.py [VERSION] [APP ...]

If VERSION is omitted it is read from dxt/ps/manifest.json.
If no APP is given, all apps are built.
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"

# Shared Python modules for every MCP server bundle.
COMMON_PY_FILES = [
    "core.py",
    "logger.py",
    "socket_client.py",
    "fonts.py",
]

APPS = {
    "photoshop": {
        "dxt_dir": "ps",
        "uxp_dir": "ps",
        "server": "ps-mcp.py",
        "dxt_out": "photoshop-mcp.dxt",
        "ccx_out": "photoshop-mcp-plugin.ccx",
    },
    "indesign": {
        "dxt_dir": "id",
        "uxp_dir": "id",
        "server": "id-mcp.py",
        "dxt_out": "indesign-mcp.dxt",
        "ccx_out": "indesign-mcp-plugin.ccx",
    },
}

# Files/patterns to exclude from the .ccx plugin package.
CCX_EXCLUDE_SUFFIXES = (".OGjs", ".OGpy")
CCX_EXCLUDE_NAMES = {".DS_Store"}


def _add_file(zf: zipfile.ZipFile, src: Path, arcname: str) -> None:
    zf.write(src, arcname)
    print(f"    + {arcname}")


def build_dxt(app: str) -> Path:
    """Zip dxt/<app>/manifest.json + the MCP server .py files into a .dxt."""
    cfg = APPS[app]
    src_dir = REPO / "dxt" / cfg["dxt_dir"]
    mcp_dir = REPO / "mcp"
    out = DIST / cfg["dxt_out"]

    manifest = json.loads((src_dir / "manifest.json").read_text(encoding="utf-8"))
    print(f"Building {out.name} (manifest version {manifest['version']})...")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_file(zf, src_dir / "manifest.json", "manifest.json")
        for name in COMMON_PY_FILES + [cfg["server"]]:
            src = mcp_dir / name
            if not src.exists():
                raise FileNotFoundError(f"required MCP file missing: {src}")
            _add_file(zf, src, name)
    return out


def build_ccx(app: str) -> Path:
    """Zip the uxp/<app> plugin folder into a double-click-installable .ccx."""
    cfg = APPS[app]
    src_dir = REPO / "uxp" / cfg["uxp_dir"]
    out = DIST / cfg["ccx_out"]
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

    args = [a for a in sys.argv[1:]]
    version = None
    apps: list[str] = []
    for a in args:
        if a in APPS:
            apps.append(a)
        else:
            version = a.lstrip("v")
    if not apps:
        apps = list(APPS)
    if version is None:
        manifest = json.loads(
            (REPO / "dxt" / "ps" / "manifest.json").read_text(encoding="utf-8")
        )
        version = manifest["version"]

    print(f"=== Building adb-mcp release artifacts (v{version}): {', '.join(apps)} ===\n")
    artifacts = []
    for app in apps:
        artifacts.append(build_dxt(app))
        print()
        artifacts.append(build_ccx(app))
        print()
    print("Done. Artifacts:")
    for art in artifacts:
        print(f"  {art}  ({art.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
