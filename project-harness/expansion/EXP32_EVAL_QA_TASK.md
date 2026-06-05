# Task — Generate the anti-hallucination + retrieval eval Q&A set (EXP-32 / EXP-31)

**Type:** content/fixture authoring (NOT engine code). Produces a labeled eval set scored against the
*existing* seed graph. Feeds EXP-32 (anti-hallucination) and EXP-31 (retrieval precision@k).

> This is the labeled fixture, not seed data. It encodes, per question, *what an NPC legitimately knows*
> so the eval can classify each answer as **grounded / correct-refusal / hallucination**.

---

## 0. Where to run it — recommendation

**Run it LOCALLY (Opus via Claude Code) for the demo world first.** Reasons:
- the generator must emit **exact node IDs** (`captain_sorn`, `northern_war_begins`, …) and verdicts that
  match the real `KNOWS_ABOUT` / `secrets` / `beliefs` edges — local reads the seed files directly, so no
  copy-paste drift and every case can be validated against the graph;
- the output lands straight in the repo at the right path with the right schema.

**Use claude.ai online instead only if** you want a *large creative batch* (e.g. 100+ paraphrased
adversarial phrasings, or persona-voiced question styles) where breadth matters more than ID-exactness —
then paste the three seed files (below) into the chat and ask for the same JSON schema, and a local pass
validates/repairs IDs afterward. For the first, correctness-critical slice, **local is better.**

**Decision rule for the agent running this task:** if you can read the seed files in-repo, generate
locally. If the seed graph is ambiguous or the user wants >60 cases with rich phrasing variety, stop and
recommend the online route, returning the exact paste-bundle (the 3 seed files + this spec) for the user.

---

## 1. Inputs (read these — they define ground truth)

- `demo_game/seed.py` — demo world: 5 NPCs, their `KNOWS_ABOUT` events, secrets, beliefs, memories,
  goals, items, factions. (Primary target world.)
- `seeds/worlds/seed_village_world.py` — village eval world (`vw_` prefix).
- `seeds/worlds/seed_tavern_world.py` — tavern eval world (`tw_` prefix).
- `src/npc_engine/type_registry/base_edges/knows_about.yaml`, `knows_secret.yaml`, `believes.yaml` —
  to know which knowledge relations exist and their fields.
- Existing eval harness: `evals/runner.py`, `evals/summary.py`, `src/npc_engine/prompts/eval/` —
  match the existing case/matcher conventions; the new set must be loadable by the same runner.

## 2. Output

A JSON (or YAML, matching the existing eval cases) fixture, one file per world, e.g.
`evals/cases/anti_hallucination_demo.json`. Each case:

```json
{
  "id": "ah_demo_sorn_war_known",
  "world": "demo",
  "npc_id": "captain_sorn",
  "question": "What do you know about the northern war?",
  "expected_verdict": "grounded",          // grounded | refusal
  "knowledge_basis": "KNOWS_ABOUT northern_war_begins",   // why this verdict is correct
  "expected_fact_substrings": ["war", "north"],            // for grounded: tokens a real answer should contain
  "category": "should_know"                // should_know | should_refuse | adversarial_cross_npc
}
```

For **EXP-31 (retrieval precision)** additionally emit, per query, the **labeled relevant-set** of node
IDs that *should* be retrieved (so the eval can compute precision@k / recall@k):
```json
{ "id": "ret_demo_sorn_war", "npc_id": "captain_sorn", "query": "northern war",
  "relevant_node_ids": ["northern_war_begins"], "k": 5 }
```

## 3. Coverage to generate (per world)

For EACH NPC, produce all three categories:
1. **should_know** — a question about a fact the NPC *does* hold (`KNOWS_ABOUT` event, own secret, own
   belief, own memory). Verdict `grounded`; list `expected_fact_substrings`.
2. **should_refuse** — a question about a fact the NPC has **no** edge to (a plausible-but-unknown world
   fact). Verdict `refusal`. A *correct refusal* ("I haven't heard") must score as PASS; a fabricated
   answer is the hallucination failure the eval exists to catch.
3. **adversarial_cross_npc** — ask NPC-A about a fact only NPC-B knows (e.g. ask `old_henryk` about a
   secret only `lira_fence` holds). Verdict `refusal`. These are the highest-signal anti-hallucination cases.

Target ~6–10 cases per NPC (≈ 30–50 for the demo world). Keep questions short and in plain player voice.

## 4. Seed gap to flag (do not silently expand the seed)

Clean **should_refuse** targets require facts that are *deliberately unknown* to a given NPC. If the seed
lacks enough such gaps, **do not add to `seed.py`** — instead list the recommended additions in this task's
output (a short "seed-gap notes" section) and let the human approve a seed tweak separately. The fixture
itself must score against the seed *as it is today*.

## 5. Acceptance

- [ ] Every case's verdict is justified by a real (or provably-absent) edge in the cited seed.
- [ ] All three categories present for each NPC; adversarial_cross_npc cases included.
- [ ] Loadable by the existing `evals/runner.py` (or a clearly-specified extension of it).
- [ ] `expected_fact_substrings` are lenient (substring/keyword match, not exact phrasing).
- [ ] Player-taught facts (EXP-53) note: once EXP-53 lands, a fact the player taught an NPC scores as
      `grounded`, not hallucination (DEC-072) — leave a TODO category `learned_from_player` stubbed.
- [ ] Output is review-ready; no engine/seed source modified.
