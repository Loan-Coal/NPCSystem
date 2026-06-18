# EXP-205 — Proactive dialogue act in scripted runner (demo)

**Goal / rationale:** The proactive-dialogue engine is built and wired (legacy EXP-10), but the scripted
demo — the sales artifact — never shows an NPC *initiating*. Adding an "NPC hails the player" beat makes
the highest-differentiation capability visible in a recording. Pure demo-side.

**First slice (your scope):** Add an ACT-11 beat to the scripted runner that, after a tick, fetches the
NPC's pending proactive intents and prints the NPC-initiated line. No engine/API change — consume the
existing endpoint via the existing client.

**Current state (verified):**
- `demo_game/run.py` — the scripted scenario ends at ACT 10 `RemembersYouBeat` (~line 447). There is no
  ACT-11 proactive beat. Find the `SCENES`/acts list and append one.
- `demo_game/run_scenes.py` — scene/beat classes live here (e.g. `RemembersYouBeat`). Add a new
  `ProactiveDialogueBeat` following the existing beat class pattern (same base class / `execute` shape).
- `demo_game/client.py` — the proactive endpoint is `GET /v1/dialogue/pending`; verify the existing
  `EngineClient` method name (e.g. `get_pending_intents` / `get_pending_dialogue`). Reuse it; if no
  wrapper exists, add a thin one in `client.py` (declared file).

**Files:**
- EDIT `demo_game/run_scenes.py` — new `ProactiveDialogueBeat` (advance a tick if needed, call the
  pending-intents client method, render the NPC-initiated line; graceful no-op message if none pending).
- EDIT `demo_game/run.py` — register the beat as ACT 11 in the scripted sequence.
- POSSIBLY EDIT `demo_game/client.py` — only if no pending-intents wrapper exists.
- NEW/EXTEND test: `demo_game/tests/` — `test_proactive_beat_renders_intent` (mock the client to return
  a pending intent; assert the beat renders it; empty → graceful message, no crash).

**Graph/API surface:** none new — consumes existing `GET /v1/dialogue/pending`. Demo-side only.

**Architecture fit:** pure demo-side (`demo_game/` is a REST/WS client with zero `src/npc_engine`
imports — do NOT import `src/`). No schema, no engine change.

**Test plan (RED first):** mock the client's pending-intents method to return one intent; assert the beat
output includes the NPC line; empty list → graceful "no pending" path. Watch fail, implement.
Run: `pytest demo_game/tests/ -k proactive -q`.

**Done when:** the scripted runner has an ACT-11 NPC-initiated beat that renders a pending proactive line
(or degrades gracefully); test passes; no `src/` import; the demo arc still runs.
