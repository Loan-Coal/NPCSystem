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
        # Mirrors [tool.setuptools.package-data] in pyproject.toml. Both lists are
        # pinned together by tests/unit/scripts/test_packaging_spec.py, which reds when
        # a declared runtime asset is not bundled here (R5.3, CR-L12-02).
        (str(SRC_ROOT / "npc_engine" / "prompts"), "npc_engine/prompts"),
        (str(SRC_ROOT / "npc_engine" / "config"), "npc_engine/config"),
        (str(SRC_ROOT / "npc_engine" / "data"), "npc_engine/data"),
        (str(SRC_ROOT / "npc_engine" / "observability"), "npc_engine/observability"),
        (str(SRC_ROOT / "npc_engine" / "type_registry" / "base_nodes"), "npc_engine/type_registry/base_nodes"),
        (str(SRC_ROOT / "npc_engine" / "type_registry" / "base_edges"), "npc_engine/type_registry/base_edges"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "chapter"), "npc_engine/engines/chapter"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "contracts"), "npc_engine/engines/contracts"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "dialogue"), "npc_engine/engines/dialogue"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "economy"), "npc_engine/engines/economy"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "events"), "npc_engine/engines/events"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "faction_politics"), "npc_engine/engines/faction_politics"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "gossip"), "npc_engine/engines/gossip"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "memory_consolidation"), "npc_engine/engines/memory_consolidation"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "proactive_dialogue"), "npc_engine/engines/proactive_dialogue"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "quest_generation"), "npc_engine/engines/quest_generation"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "reputation"), "npc_engine/engines/reputation"),
        (str(SRC_ROOT / "npc_engine" / "engines" / "story_pacing"), "npc_engine/engines/story_pacing"),
        # GAME_SCHEMA_PATH defaults to the bare relative "game_schema.yaml" (config.py),
        # so this one lands at the bundle root, not under npc_engine/.
        (str(SRC_ROOT / "npc_engine" / "game_schema.yaml"), "."),
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
