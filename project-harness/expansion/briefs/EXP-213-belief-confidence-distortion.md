# EXP-213 — Belief/confidence-aware distortion routing

**Goal / rationale:** Gossip distortion-type selection is currently seed-modulo (random), ignoring how
confident the receiver is. Routing distortion by receiver confidence makes the "telephone game" feel
causal (a doubtful receiver distorts differently than a credulous one). Serves BUSINESS_INTENT "gossip
that drifts believably."

**First slice (your scope):** Add an optional `receiver_confidence` input to the distortion selection so
the chosen distortion type/strength is biased by confidence (fall back to current behavior when absent).

**Current state (verified):**
- `src/npc_engine/engines/gossip/gossip_distort.py` — `gossip_distort()` has no `receiver_confidence`
  param. The distortion STRATEGY_REGISTRY is OCP-clean; do NOT edit the strategy files.
- `src/npc_engine/engines/gossip/gossip_handler.py:373` — type selection currently uses
  `seed % len(REGISTRY_KEYS)`. Pass a confidence value through and bias selection by it.
- Config: add a confidence→distortion mapping/threshold in `prompts/gossip/gossip_config.yaml` (or the
  gossip config YAML) — named, no magic numbers. Keep determinism: same (seed, confidence) → same result.

**Files:**
- EDIT `src/npc_engine/engines/gossip/gossip_distort.py` — add optional `receiver_confidence: int | None`
  kwarg; when present, bias the strategy/strength selection by it (deterministic given seed+confidence).
- EDIT `src/npc_engine/engines/gossip/gossip_handler.py` — pass the receiver's confidence into
  `gossip_distort()` (read it from the existing propagation context; if not readily available, default to
  None — do NOT add a graph call this slice).
- EDIT `src/npc_engine/prompts/gossip/gossip_config.yaml` (or the gossip config) — confidence-band keys.
- NEW/EXTEND test: `tests/unit/test_gossip_distort.py` — same seed + differing confidence → different
  (but deterministic) distortion; absent confidence → unchanged from current behavior.

**Graph/API surface:** engine-internal + config YAML. No schema, no route.

**Architecture fit:** closed-edit (gossip_distort + gossip_handler, both additive kwargs) + config YAML
add. No new node/edge. Determinism preserved (RNG seed logged per CLAUDE.md). No LLM in graph/retrieval.

**Test plan (RED first):** `test_confidence_biases_distortion_deterministically` +
`test_absent_confidence_matches_current`. Watch fail, implement. Run: `pytest tests/unit/test_gossip_distort.py -q`.

**Done when:** distortion selection is biased by receiver confidence (deterministic), back-compatible when
absent; tests pass; no schema change; strategy files untouched.
