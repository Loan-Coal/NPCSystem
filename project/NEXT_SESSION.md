# Next Session Instructions

## Phase 3 — World Depth. Feature 3.7 next.

Run tests before touching any code:

```bash
pytest tests/ -q
```

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 3.6 as DONE (committed), add Feature 3.7 as IN_PROGRESS with today's date.
2. `project/STATUS.md` — update Phase 3 row to reflect 3.1–3.6 ✅, 3.7 IN_PROGRESS.

---

## Feature 3.7 — Secrets

Read `project/ROADMAP.md` lines 563–585 first (the authoritative spec).

Only start after `pytest tests/ -q` is green.

**Context:** Secrets are discrete graph entities that NPCs know. They propagate
via gossip differently from events — lower base probability, higher distortion.
Secrets should appear in NPC context so they can inform dialogue.

### Architecture decisions (read before coding)

- **Node**: `Secret` with fields `id`, `content`, `severity` (int, 0–100),
  `created_at` (str, game-time JSON).
- **Edge**: `(:Character)-[:KNOWS_SECRET]->(:Secret)`.
  No additional edge fields needed.
- Schema YAML files:
  - `type_registry/base_nodes/secret.yaml`
  - `type_registry/base_edges/knows_secret.yaml`
- `graph/secret_queries.py` — Cypher strings for create, get by character.
- `graph/secret_service.py` (≤150 lines) — `create_secret`, `get_secrets_for_character`.
- `retrieval/context_builder.py` — include known secrets in Tier A (priority 84,
  just below owned items at 86). Fetch top-3 secrets ordered by severity desc.
- Admin route `api/routes/secrets.py` — `POST /v1/admin/secrets/{character_id}`,
  `GET /v1/admin/secrets/{character_id}`. Wire into `main.py` at admin_prefix.
- **Gossip propagation**: In `engines/gossip/knowledge_propagator.py`, add a
  separate propagation path for secrets: lower `base_probability` (0.2 vs
  default), higher distortion chance (50%). Keep the change additive — do not
  rewrite the existing propagation logic.

### Steps

1. **Schema YAMLs**:
   - `type_registry/base_nodes/secret.yaml` — `id`, `content`, `severity` (int, range [0,100]),
     `created_at` (str).
   - `type_registry/base_edges/knows_secret.yaml` — `src_type: character`,
     `dst_type: secret`, no extra fields.

2. **`graph/secret_queries.py`** — Cypher strings + `get_secrets_for_character`
   read accessor (returns top-k ordered by severity desc).

3. **`graph/secret_service.py`** (≤150 lines):
   - `create_secret(session, *, character_id, content, severity, game_time) -> str`
   - `get_secrets_for_character_svc(session, *, character_id, k=3) -> list[dict]`

4. **`retrieval/context_builder.py`** — after owned_items, fetch secrets for
   the NPC and include as Tier A at priority 84.

5. **`api/routes/secrets.py`** — two endpoints: create, list.
   Wire into `main.py` following the goals/items route pattern.

6. **`engines/gossip/knowledge_propagator.py`** — add a `propagate_secret`
   helper function that reuses the existing propagation infrastructure but
   applies secret-specific parameters (lower probability, higher distortion).
   Wire it in to the gossip tick so secrets have a chance to propagate.

7. **Unit tests** `tests/unit/test_secret_service.py`:
   - Happy path: create secret → returns UUID.
   - Get secrets: returns list for character ordered by severity.
   - No-secrets case: returns empty list.
   - Get secret with k limit: respects k param.

8. **E2E scenario** `e2e/scenarios/scenario_secrets.py`:
   - Seed a character.
   - Create a secret for that character.
   - Fetch secrets, assert one returned with correct severity.
   - Cleanup.

### Definition of done (3.7)
- Schema YAMLs exist in `type_registry/base_nodes/` and `type_registry/base_edges/`.
- `graph/secret_service.py` passes all unit tests.
- `retrieval/context_builder.py` includes secrets in Tier A.
- Admin routes exist and are wired.
- Gossip propagator has a distinct secret propagation path.
- E2E scenario passes.
- Pre-merge checklist from `CLAUDE.md` satisfied.
- Commit: `feat: secret nodes (Phase 3.7)`

---

## After 3.7 is committed — update this file for Feature 3.8

When Feature 3.7 is committed and `pytest tests/ -q` is green, rewrite this
file to target Feature 3.8 — Promises and debts.

Read `project/ROADMAP.md` lines 589+ before writing 3.8 instructions.

---

## Open issues to be aware of (do NOT fix during Phase 3.7 unless explicitly blocking)

- **ISSUE-013**: `how_long_ago` has no defined bucket for 7–27 days (P3)
- **ISSUE-005**: `adjust_reputation_for_event` not wired into event engine (P3)
- **ISSUE-006**: pre-existing `Character.faction` string field not migrated (P3)
- **ISSUE-004**: `edge_updater.py` no-any-return mypy warning (P3)
- **ISSUE-011**: `.env` uses Docker DNS (`bolt://neo4j:7687`) — fails outside Docker (P3)

If any of these blocks Phase 3.7, log a new ISSUES.md entry describing the
blocking scenario and get approval before fixing.
