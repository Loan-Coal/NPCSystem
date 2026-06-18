# EXP-219 — Personality-modulated emotion model (2nd EmotionModelProtocol impl)

**Goal / rationale:** Emotion is currently one fixed VAD model — every NPC reacts identically. A
trait-modulated model makes NPCs feel distinct (a timid NPC fears more, a bold one less). The
`EmotionModelProtocol` OCP seam already exists, so this is a clean new-file add. Serves BUSINESS_INTENT
"NPCs with distinct emotional state."

**First slice (your scope):** A new `TraitModulatedEmotionModel` implementing `EmotionModelProtocol`,
which takes the base VAD delta and scales it by personality traits. New-file-only — do NOT edit the
existing `VadEmotionModel` or the composition root this slice (wiring is slice 2).

**Current state (verified):**
- `src/npc_engine/engines/emotion/` — `EmotionModelProtocol` exists and `VadEmotionModel` implements it
  (read both to learn the protocol method signatures + the delta shape). Model your new class on
  `VadEmotionModel`'s interface exactly (LSP — same behavior contract, no surprising exceptions).
- Trait data: a trait reader exists in `graph/` (e.g. `get_traits_svc`/`trait_reader`). For a pure new
  model, accept the traits (or a trait-derived modulation factor) as a constructor/param input — do NOT
  call the graph from inside the model (keep it pure; the caller supplies traits). Keep DI-friendly.

**Files:**
- NEW `src/npc_engine/engines/emotion/trait_modulated_model.py` — `TraitModulatedEmotionModel`
  implementing `EmotionModelProtocol`; scales the VAD delta by named trait-weight constants
  (UPPER_SNAKE; no magic numbers). Module docstring with `Does NOT:` + `Dependencies injected:`.
- NEW test: `tests/unit/test_trait_modulated_model.py` — assert a high-fear-trait NPC gets a larger
  fear delta than baseline, and that with neutral traits it matches the base model (LSP parity).

**Graph/API surface:** engine-internal. No schema, no route.

**Architecture fit:** pure new-file-add via the `EmotionModelProtocol` OCP seam (do NOT edit the existing
model or protocol). Layer = engines. No schema.

**Test plan (RED first):** `test_high_fear_trait_amplifies_fear_delta` + `test_neutral_traits_match_base`.
Watch fail (class missing), implement. Run: `pytest tests/unit/test_trait_modulated_model.py -q`.

**Done when:** a second `EmotionModelProtocol` impl modulates VAD deltas by traits; tests pass; existing
model/protocol untouched; docstrings present; functions ≤40 lines.
