#!/usr/bin/env bash
# TEMPORARY: delete by end of task REORG-PR6. Reason: per-domain driver for the
# graph/ folder reorg (move modules into a domain sub-package + rewrite imports +
# fix baseline paths + write facade __init__). Not part of the shipped tree.
set -euo pipefail

DOMAIN="$1"; PURPOSE="$2"; shift 2
MODULES=("$@")

GRAPH=src/npc_engine/graph
DOMAIN_DIR="$GRAPH/$DOMAIN"
mkdir -p "$DOMAIN_DIR"

# 1. git mv each module into the domain dir
for m in "${MODULES[@]}"; do
  git mv "$GRAPH/$m.py" "$DOMAIN_DIR/$m.py"
done

# 2. build alternation of module names for the rewrite
ALT=$(IFS='|'; echo "${MODULES[*]}")

# 3. rewrite imports repo-wide (two forms), only over files that reference them
mapfile -t FILES < <(grep -rlE "npc_engine\.graph\.($ALT)\b|from npc_engine\.graph import ($ALT)\b" \
  --include=*.py src tests demo_game evals matchers summary runner conftest.py 2>/dev/null || true)
if [ "${#FILES[@]}" -gt 0 ]; then
  perl -i -pe "s/\bfrom npc_engine\.graph import ($ALT)\b/from npc_engine.graph.$DOMAIN import \$1/g;
               s/\bnpc_engine\.graph\.($ALT)\b/npc_engine.graph.$DOMAIN.\$1/g" "${FILES[@]}"
fi

# 4. fix baseline path prefixes for moved modules
for m in "${MODULES[@]}"; do
  perl -i -pe "s{src/npc_engine/graph/$m\.py}{src/npc_engine/graph/$DOMAIN/$m.py}g" scripts/rules_baseline.txt
done

# 5. facade __init__.py (docstring satisfies docstring_audit; submodules import by full path)
SURFACE=$(IFS=', '; echo "${MODULES[*]}")
cat > "$DOMAIN_DIR/__init__.py" <<EOF
"""
Package: graph.$DOMAIN
Layer: graph
Purpose: $PURPOSE
Public surface: submodules — $SURFACE.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
EOF
git add "$DOMAIN_DIR/__init__.py" scripts/rules_baseline.txt

echo "moved $DOMAIN: ${#MODULES[@]} modules; rewrote ${#FILES[@]} files"
