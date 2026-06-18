# EXP-83 — Integrator hello-world quickstart

**Goal / rationale:** The smallest sales/onboarding artifact that proves the one-deployment integration pitch
(BUSINESS_INTENT success-criterion "integrator hello-world in minutes"). A standalone script a studio runs
against a fresh stack that seeds a tiny world, sends one dialogue turn, and prints the NPC's grounded reply —
using nothing but `httpx` (no `EngineClient`, no `src/` imports), proving the API is consumable cold.

**First slice (this worker's scope):** A single self-contained `demo_game/quickstart.py` (httpx-only) + a
`make hello` target. It (1) checks `/health`, (2) seeds one location + one NPC + one event the NPC `KNOWS_ABOUT`
(via the public `/v1/graph/*` + `/v1/admin/*` routes), (3) POSTs one `/v1/dialogue` turn, (4) prints the reply and
a one-line "grounded: the NPC answered from known context" note. Idempotent; safe to re-run.

**Current state (verify):**
- Auth: `Authorization: Bearer <API_KEY>` (see `demo_game/client.py:53`); key from env/`.env.demo` (`NPC_API_KEY`).
- Live route shapes to mirror (already correct in `demo_game/client.py`): `POST /v1/graph/nodes/{type}`,
  `POST /v1/graph/edges/{type}`, `POST /v1/admin/...` for inner-life, `POST /v1/dialogue` with body
  `{player_id, npc_id, player_message, location_id, session_id, explicit_node_ids}`.
- Dialogue is slow on the cold model (~30-40s first token) — set the httpx timeout to **120s** for the dialogue
  call (mirror `config.py` `NPC_DIALOGUE_TIMEOUT_S=120`), short timeout for the rest.
- **Do NOT import `demo_game.client` or anything from `src/`** — the whole point is a from-scratch httpx consumer.

**Files (all NEW → near-zero conflict):**
- NEW `demo_game/quickstart.py` — the standalone script (httpx only; ~1 small file, keep <300 lines; module +
  function docstrings).
- EDIT `Makefile` — add `hello` target (`$(PYTHON) -m demo_game.quickstart`). **Conflict note:** EXP-31 also edits
  `Makefile`; sequence the two Makefile edits or add both target lines at fan-in.
- NEW `demo_game/tests/test_quickstart.py` — unit test with a mocked httpx client (no live stack): assert the
  script issues the seed calls then the dialogue call to the right paths and prints the reply.

**Graph/API surface:** consumes existing routes only; adds none.

**Architecture fit:** demo-layer only, zero `src/` change, zero schema. Pure standalone client (this is also the
SEV-02 "demo is a standalone consumer" property, reaffirmed).

**Test plan (write FIRST):** `demo_game/tests/test_quickstart.py` — inject a mock httpx client; assert the call
sequence (health → seed nodes/edges → `/v1/dialogue`) hits the correct paths/bodies and that the printed output
contains the mocked NPC reply. Run: `pytest demo_game/tests/test_quickstart.py -q`.

**Done when:** the mocked unit test is green, and against a live fresh stack `make hello` seeds, sends one turn,
and prints a grounded NPC reply. Keep it short enough to paste into a README quickstart.
