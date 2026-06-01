# Proposed DECISIONS.md Candidates

These are new decisions identified during the V3 roadmap audit. They have not
yet been added to `project/DECISIONS.md`. The human should review each entry,
adjust wording, and copy approved entries into `project/DECISIONS.md`.

None of these entries should be added to code or docs until the human has
reviewed and explicitly accepted them.

---

## Proposed Decision 1 — Local LLM only; no hosted fallback

**Context:** The demo targets a 12 GB VRAM machine with 64 GB system RAM.
Hosted LLM APIs (OpenAI, Anthropic, Mistral) would add network latency,
cost, and a dependency on connectivity during a live demo.

**Options considered:**
- (a) Ollama only — no fallback to hosted API
- (b) Ollama primary, hosted API as emergency fallback behind a feature flag

**Decision:** (a) — Ollama only. No hosted fallback.

**Consequences:** Demo cannot recover gracefully from a full Ollama failure;
canned responses are the only fallback tier. Eliminates cost, latency, and
connectivity risk.

**Proposed DECISIONS.md entry:**
> **[V3]** Local LLM only. No hosted-API fallback. Ollama is the sole LLM
> backend. Canned responses (`prompts/canned/`) remain the bottom degradation
> tier. Adding a hosted fallback later requires new adapter wiring and secret
> management — do not add it incidentally.

---

## Proposed Decision 2 — Demo game in `demo_game/` calling engine via HTTP

**Context:** The demo game needs to show live NPC behavior to mentors. Running
it in the same process as the engine would blur the "backend service" story
and make the FastAPI layer invisible.

**Options considered:**
- (a) `demo_game/` Python process, HTTP calls to `localhost:8000`
- (b) `demo_game/` in-process import of `src/npc_engine/`
- (c) Separate repo

**Decision:** (a) — separate folder, HTTP only.

**Consequences:** Requires the engine to be running when the demo game runs.
Adds realistic HTTP round-trip latency. Makes the API surface visible and
exercised by the demo.

**Proposed DECISIONS.md entry:**
> **[V3]** Demo game lives in `demo_game/` (same repo). It is a separate Python
> process that calls the engine exclusively via HTTP to `localhost:8000`. No
> direct imports from `src/npc_engine/`. This is load-bearing for the demo
> story: mentors should see a real client calling a real API.

---

## Proposed Decision 3 — Fine-tuning via QLoRA adapters on a shared base

**Context:** The project targets per-engine specialization (dialogue, gossip,
quest generation all want different response styles). Full fine-tunes per
engine would require separate 7–8B model weights per engine — too expensive
to store and swap on 12 GB VRAM.

**Options considered:**
- (a) QLoRA adapters on a shared base (one set of base weights, multiple adapters)
- (b) Full fine-tune per engine
- (c) System prompt engineering only, no fine-tuning

**Decision:** (a) — QLoRA adapters. Phase 3 builds the training pipeline and
trains one adapter (likely gossip mutation) as proof. Other engines follow the
same pattern.

**Consequences:** Requires LoRA merge or dynamic adapter loading at inference
time. Adapter quality depends on training data quality. Phase 3 must establish
the data pipeline as well as the training pipeline.

**Proposed DECISIONS.md entry:**
> **[V3]** Fine-tuning uses QLoRA adapters on a shared base model (Phase 1
> model swap candidate). One adapter per engine is the target architecture. Phase
> 3 builds the pipeline and ships one adapter (gossip) as proof-of-concept.
> Do not start full fine-tunes per engine.

---

## Proposed Decision 4 — LlamaAdapter removal (proposed, pending verification)

**Context:** `src/npc_engine/engines/llm/llama_adapter.py` is 14 lines — a
thin subclass of MistralAdapter with no changes. Static analysis found no
`llm_config.yaml` or test referencing it. It appears to be a legacy alias.

**Options considered:**
- (a) Remove the file; update `__init__.py` exports
- (b) Keep as dead code
- (c) Keep if any runtime config references it (needs human verification)

**Decision:** Proposed (a), but **requires human verification** that no
`llm_config.yaml` or environment variable references `LlamaAdapter` before
deletion. See `open_questions.md` Q1.

**Proposed DECISIONS.md entry (draft — do not add until verified):**
> **[V3]** LlamaAdapter removed. It was a 14-line subclass of MistralAdapter
> with no behavioral difference and no config references. Removed to reduce
> adapter surface. If a Llama-specific HTTP API variant is needed in future,
> add it as a new adapter with tests.

---

## Proposed Decision 5 — `explicit` weight: implement or remove from docs

**Context:** `docs/RELEVANCE_WEIGHTS.md` documents a 6th scoring weight
(`explicit`, a boolean game-engine relevance flag) with example value 0.10.
The `RelevanceWeights` Pydantic model has only 5 fields; `explicit` is absent
from both the model and `context_scoring.py`. This is confirmed doc/code drift.

**Options considered:**
- (a) Implement the `explicit` field: add to `RelevanceWeights`, add scoring
  logic in `context_scoring.py`, update `llm_config.yaml` defaults, update
  `RELEVANCE_WEIGHTS.md`
- (b) Remove from docs: strike the `explicit` example from `RELEVANCE_WEIGHTS.md`,
  note it as "planned but not implemented" or "removed"
- (c) Leave the drift as-is (not acceptable — causes confusion)

**Decision:** Needs human input. If explicit tagging of nodes by the game engine
is a desired feature for the demo, implement (a). If it is not needed for V3,
choose (b). See `open_questions.md` Q3.

**Proposed DECISIONS.md entry (fill in chosen option after human decision):**
> **[V3]** `explicit` relevance weight: [implemented as of Phase 1 / removed
> from docs and deferred to backlog]. Reason: ...

---

## Proposed Decision 6 — Model swap timing: default Phase 1

**Context:** Mixtral 8x7B is the current base. Phase 1 candidates are
Qwen2.5-7B-Instruct and Llama 3.1 8B Instruct. Phase 0 benchmarks current
latency to inform the decision, but the swap itself is Phase 1 work by default.
Doing the swap in Phase 0 risks destabilizing the baseline before it is recorded.

**Decision:** Model swap happens in Phase 1. If Phase 0 finds Mixtral is
unusably slow (>15s per turn cold), the human may choose to move the swap to
the end of Phase 0 after baselines are captured.

**Proposed DECISIONS.md entry:**
> **[V3]** Model swap (Mixtral 8x7B → Qwen2.5-7B-Instruct or Llama 3.1 8B
> Instruct) is Phase 1 work. Phase 0 benchmarks current latency only. The exact
> target model is decided at the start of Phase 1 based on Phase 0 latency
> findings and published benchmark quality scores.
