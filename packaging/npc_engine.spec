# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the NPC Engine packaged server (SHIP-04).
#
# Build with:  pyinstaller packaging/npc_engine.spec
#              (run from the repo root; pyinstaller must be installed)
#
# Output:  dist/npc_engine/npc_engine_server[.exe]
#
# The packaged binary:
#   1. Runs scripts/launcher.py as the entry point.
#   2. Bundles all npc_engine source plus YAML data files.
#   3. The Unity game process spawns this binary on startup and kills it on exit.
#
# uvicorn hidden imports: uvicorn uses importlib at runtime to load protocol
# handlers; PyInstaller cannot see these imports statically, so they are listed
# explicitly below.

from pathlib import Path

REPO_ROOT = Path(SPECPATH)
SRC_ROOT = REPO_ROOT / "src"

a = Analysis(
    [str(REPO_ROOT / "scripts" / "launcher.py")],
    pathex=[str(SRC_ROOT)],
    binaries=[],
    datas=[
        (str(REPO_ROOT / "src" / "npc_engine" / "prompts"), "npc_engine/prompts"),
        (str(REPO_ROOT / "config"), "config"),
        (str(REPO_ROOT / "game_schema.yaml"), "."),
    ],
    hiddenimports=[
        # uvicorn runtime imports (not statically discoverable)
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # npc_engine sub-packages (importlib.import_module paths)
        "npc_engine.main",
        "npc_engine.api",
        "npc_engine.engines",
        "npc_engine.services",
        "npc_engine.graph",
        "npc_engine.retrieval",
        "npc_engine.config",
        "npc_engine.setup",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="npc_engine_server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="npc_engine_server",
)
