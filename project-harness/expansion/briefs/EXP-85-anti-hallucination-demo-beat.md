# EXP-85 — Anti-hallucination "I don't know" demo beat

**Goal / rationale:** BUSINESS_INTENT success criterion 1 ("NPCs never assert facts they don't know")
is the #1 buyer bar and has NO dedicated beat. The scripted demo never explicitly shows an NPC
refusing to confabulate. This beat makes the anti-hallucination guard visible and provable.

**First slice (this worker's scope):** A new `AntiHallucinationBeat(Scene)` dataclass in
`run_scenes.py` that (1) asks `aldric_merchant` about the northern war
(`northern_war_begins` event — Aldric has no `KNOWS_ABOUT` edge for it; he's at `market_square`
and not in the Sorn→Mira→Henryk gossip chain), (2) prints the NPC's in-character refusal/deflection
alongside a one-line note confirming no `KNOWS_ABOUT` edge exists for that NPC.
Register the beat near the end of the scripted scene list in `run.py`. No new route — uses
`POST /v1/dialogue` and `GET /v1/graph/edges/KNOWS_ABOUT` (both already in `EngineClient`).

**Current state (verify):**
- `demo_game/run.py:98` — `SCENES: list[Scene]` is the scene list; append after the last scene.
- `demo_game/run_scenes.py` — all existing beats are `@dataclass class XxxScene(Scene)` / `@dataclass
  class XxxBeat(Scene)`. Add `AntiHallucinationBeat` following the same pattern. The `run` method
  calls `scene.run(runner)` which is the Protocol entry point.
- Existing client methods:
  - `EngineClient.start_dialogue_session` + `stream_dialogue` (WS) OR `post_dialogue` (REST) —
    use REST to keep it simple in the scripted runner.
  - `EngineClient.get_graph_edges("KNOWS_ABOUT", ...)` at `client.py:142` — use to verify absence.
- `demo_game/constants.py:NPC_IDS` — verify `aldric_merchant` is in the constants.

**Files:**
- EDIT `demo_game/run_scenes.py` — add `AntiHallucinationBeat` dataclass + `run(self, runner)` method.
  Keep the method ≤40 lines; extract helpers if needed.
- EDIT `demo_game/run.py` — append `AntiHallucinationBeat(name="beat_anti_hallucination")` to
  `SCENES` at line 98 (after the last existing beat).
- NEW `demo_game/tests/test_anti_hallucination_beat.py` — unit test with mocked client.

**Graph/API surface:** none new (reads existing routes only).

**Architecture fit:** demo-only, zero `src/` changes. New dataclass follows the existing `Scene`
OCP seam in `run_scenes.py`. `KNOWS_ABOUT` absence check is a read call, no mutations.

**Test plan (write FIRST):** `demo_game/tests/test_anti_hallucination_beat.py` — inject a mock
`EngineClient` that returns (a) an empty `get_graph_edges("KNOWS_ABOUT", "aldric_merchant", ...)`
edge list and (b) a dialogue response with a deflection text. Assert `AntiHallucinationBeat.run`
prints the NPC response and confirms "no KNOWS_ABOUT edge" (or similar). Run:
`pytest demo_game/tests/test_anti_hallucination_beat.py -q`.

**Done when:** The mocked unit test is green. Against a live seeded stack, the beat (1) calls
`/v1/dialogue` with `aldric_merchant` asking about the war, (2) prints the in-character non-answer,
(3) confirms the missing `KNOWS_ABOUT` edge. (Carry-forward: establishes the scripted pattern for
engine-vs-knowledge contrast beats; EXP-93 bribe fix lands on the same files next batch.)
