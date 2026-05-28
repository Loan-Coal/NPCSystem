# Eval Strategy — NPC Engine

## Goal

Validate that the system produces quality responses for **arbitrary conversations from graph context** — not just the hardcoded demo path. Every engine should be testable across multiple NPC archetypes, topics, locations, and world states.

---

## Quality Rubric Per Engine

### Dialogue Engine

| Criterion | Description | How to Measure |
|-----------|-------------|----------------|
| **Behavioral** | Same NPC voice across all topics (weather, trade, war, local gossip) | LLM judge: "Does this response match the voice descriptor?" |
| **Epistemic** | NPC only references facts in their injected context; no hallucination | Negative regex + LLM judge: "Does response mention events not in context?" |
| **Reputation-gated** | Allied NPCs warm/helpful; hostile NPCs terse/dismissive | LLM judge: "Is tone appropriate for reputation={value}?" |
| **Emotion-colored** | Emotional state subtly colors tone without dominating | LLM judge: "Does current emotion influence this response appropriately?" |

### Gossip Engine

| Criterion | Description | How to Measure |
|-----------|-------------|----------------|
| **Hedging** | Second-hand accounts use "I heard…", "supposedly…", "they say…" | `regex` matcher: `(i heard\|they say\|supposedly\|word is\|rumor has\|apparently)` |
| **Plausible distortion** | Wrong facts are believably wrong (exaggerated numbers, wrong faction, inflated severity) — not random | LLM judge: "Does this distorted account sound like how rumors spread?" |
| **Scope preservation** | Topic of original event is recognizable in distorted version | LLM judge: "Is the distorted account about the same topic as the original?" |

### Quest Engine

| Criterion | Description | How to Measure |
|-----------|-------------|----------------|
| **Archetype match** | Flavor text sounds like the quest giver's archetype | LLM judge: "Does this flavor text match a {archetype} NPC?" |
| **World-state coherence** | Quest fits current epoch (no escort quest during plague lockdown) | LLM judge: "Is this quest coherent with epoch={epoch}?" |

---

## Eval Infrastructure

### Matchers (`evals/matchers.py`)

| Kind | What it checks | Status |
|------|---------------|--------|
| `schema` | Required fields present | ✅ implemented |
| `keyword_any` | At least one keyword in response | ✅ implemented |
| `keyword_all` | All keywords in response | ✅ implemented |
| `in_set` | Field value in allowed list | ✅ implemented |
| `range` | Numeric field in [min, max] | ✅ implemented |
| `substring` | Case-insensitive substring | ✅ implemented |
| `regex` | Pattern match in response | ✅ implemented |
| `tone_judge` | LLM judges tone/voice | ❌ stubbed (ISSUE-005) |
| `negative_keyword` | Keyword must NOT appear | ❌ missing |

**Priority:** Implement `tone_judge` (R1.1) and add `negative_keyword` matcher for hallucination tests.

### Eval Case Format (`evals/cases/*.yaml`)

```yaml
id: case_001_grieving_elder
description: "Elder NPC expresses grief when asked about the fire"
requires_world: tavern_world            # which seed world to load
npc_id: elder_tomasz
player_message: "Have you heard about what happened last night?"
context_overrides:                      # optional: override graph state for this case
  reputation: neutral
expectations:
  - kind: keyword_any
    keywords: ["terrible", "awful", "loss", "tragedy"]
  - kind: tone_judge
    judge_prompt: "Does this response express genuine grief appropriate to an elder character?"
  - kind: negative_keyword             # (once implemented)
    keywords: ["haha", "excellent", "wonderful"]
```

### Negative Test Cases

Negative tests are critical — they verify the behavioral guards (Rule 2 reputation gate, Rule 5 knowledge guard) that prevent the worst failures:

| Case | What it tests |
|------|--------------|
| `case_hostile_refuses_help` | Hostile reputation → NPC does NOT offer help |
| `case_no_hallucinate_war` | NPC without KNOWS_ABOUT(war) does NOT mention war |
| `case_no_hallucinate_barracks` | Tavern NPC does NOT describe barracks layout |
| `case_gossip_hedges_001` | Distorted rumor (knowledge_state=rumor) MUST use hedging language |
| `case_no_invent_names` | NPC does NOT invent character names not in context |

---

## Eval Worlds (`seeds/world/`)

Each eval world is a standalone seed script that wipes the graph and populates it via API. Worlds are reusable — they can be loaded for evals, demos, or manual testing.

### `seed_tavern_world.py`
- **NPCs:** innkeeper (warm/observant), wanderer (guarded/traveller), merchant (gossipy/trade-focused)
- **Events:** local theft, market fire, travelling performer — deliberately NOT the war scenario
- **Gossip:** 2-hop distortion chain (wanderer sees theft → tells innkeeper with distortion)
- **Locations:** tavern, market square, back alley
- **Epoch:** age_of_peace (no active war)

### `seed_village_world.py`
- **NPCs:** healer, village elder, farmer, guard, fence
- **Events:** crop blight, bandit raid on northern road, missing child, secret romance
- **Gossip:** 2-hop chain (guard witnesses raid → tells healer with distortion)
- **Locations:** village square, farm, chapel
- **Epoch:** famine (active_conditions: [drought, crop_failure])

### `seed_kingdom_world.py` *(post-hackathon)*
- **NPCs:** noble, spy, herald, blacksmith, cleric
- **Events:** succession dispute, trade embargo, assassination attempt, treaty signed
- **Locations:** palace, forge, docks
- **Epoch:** political crisis

### World Runner

```bash
# Seed a world and run its eval cases
python seeds/world/run_eval_world.py --world tavern_world

# Manually seed only (for interactive testing)
python seeds/world/seed_tavern_world.py

# Run evals against currently loaded world
python evals/runner.py --cases evals/cases/tavern/
```

---

## NPC Voice Strategy

**Principle:** Voice is a graph property, not a prompt constant. The dialogue prompt is NPC-agnostic.

- `voice_descriptor` is stored on the Character node in Neo4j
- `get_character_with_relations()` returns it as part of character context
- `prompt_builder.py` reads it from the serialized context — no YAML lookup
- Seed scripts set `voice_descriptor` when creating Character nodes
- `npc_voices.yaml` is deprecated (historical reference only)

**Voice descriptor format** (concise, 1–2 sentences):

```
"Warm, pragmatic innkeeper. Hears everything but speaks carefully about politics."
"Clipped military diction. Names facts directly. References duty and chain of command."
"Rambling elder. Mixes current rumour with decades-old memory. Often wrong about specifics."
"Precise and gentle. Speaks of the body and spirit. Avoids conflict."
```

---

## Running the Full Eval Suite

```bash
# Run all eval cases (requires server running + graph seeded)
make eval-full

# Run only the LLM judge evals (demo path)
make eval-llm-demo

# Run evals for a specific world
python seeds/world/seed_tavern_world.py && python evals/runner.py --cases evals/cases/tavern/

# Generate markdown report
python evals/runner.py --cases evals/cases/ --report evals/reports/$(date +%Y-%m-%d).md
```

---

## Iterative Improvement Loop

1. **Seed a world** → `python seeds/world/seed_tavern_world.py`
2. **Run evals** → identify failing cases
3. **Diagnose**: is the failure in the prompt (Rule missing/weak) or in the context (wrong data surfaced)?
4. **Fix prompt** → update `system_v1.yaml` (increment PROMPT_VERSION)
5. **Re-run evals** → verify improvement, check for regressions
6. **Document** in `docs/PROMPT_DESIGN.md` migration log

For prompt A/B comparison (R2.3): `python evals/runner.py --prompt-variant evals/variants/v3_gossip_hedge.yaml`
