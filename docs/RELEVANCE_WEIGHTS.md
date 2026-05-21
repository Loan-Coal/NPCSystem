# Relevance Weights

Context items (Characters, Events, Locations) compete for a fixed token budget each dialogue turn. Each candidate node receives a score in `[0, 1]` and the highest-scoring items fill the budget first.

## Components

| Weight field | What it measures |
|---|---|
| `recency` | How recently was this node last updated? Nodes touched in the last few ticks score higher. |
| `severity` | How significant was the associated event? Events with high `severity` (0–100) score higher. |
| `proximity` | Is the node nearby in the graph? Nodes within `max_proximity_hops` hops of the NPC score higher. |
| `relation` | How strong is the NPC's RELATES_TO edge to this node? Higher `trust`/`affection` increases score. |
| `quest` | Is this node directly involved in an active quest for the player? Quest-linked nodes score higher. |
| `explicit` | Was this node explicitly pinned by the game engine for this turn? Set via `explicit_node_ids` in `POST /v1/dialogue`. Pinned nodes score 1.0; all others score 0.0. Primarily used for Tier A graph nodes (Events, Memories, Characters) whose IDs the game engine knows are scene-critical. |

## Scoring formula

```
score(node) = recency   * norm(recency_value)
            + severity  * norm(severity_value)
            + proximity * norm(proximity_value)
            + relation  * norm(relation_value)
            + quest     * norm(quest_flag)
            + explicit  * norm(explicit_flag)
```

where `norm(x)` maps the raw value to `[0, 1]` for that component, and all weights satisfy:

```
recency + severity + proximity + relation + quest + explicit == 1.0  (± 1e-6)
```

Tie-break order: `score DESC`, `node_type ASC`, `node_id ASC`.

## Worked examples

### Recency-heavy (hot gossip scenario)

```yaml
recency:   0.50
severity:  0.10
proximity: 0.10
relation:  0.10
quest:     0.10
explicit:  0.10
```

Use when the game is in a fast-moving phase and recent events should dominate. A freshly created Event node will outrank an older, strongly-related Character node even with modest severity.

### Relation-heavy (trusted companion scenario)

```yaml
recency:   0.10
severity:  0.10
proximity: 0.10
relation:  0.50
quest:     0.10
explicit:  0.10
```

Use for intimate NPCs (e.g. a loyal companion) where the conversation should surface relationship history. A high-trust Character with an old interaction scores above a recent low-relation event.

### Balanced default

```yaml
recency:   0.20
severity:  0.20
proximity: 0.15
relation:  0.20
quest:     0.15
explicit:  0.10
```

The default shipped in `config/llm_config.yaml`. Roughly equal weight to recency and relation, slightly lower weight to quest and explicit to avoid quest nodes crowding out ambient context.

## A/B testing relevance profiles

Run two NPC Engine instances with different `llm_config.yaml` files pointing at the same Neo4j instance. Route a subset of sessions to each instance. Use the eval harness (`make eval`) to compare Layer 1 and Layer 2 metrics between the two profiles. Active weights are logged at startup:

```
INFO: Active relevance weights: recency=0.20 severity=0.20 ...
```

## Using explicit_node_ids

The game engine pins nodes by passing `explicit_node_ids` in the `POST /v1/dialogue` request body:

```json
{
  "player_id": "player_1",
  "npc_id": "guard_npc",
  "player_message": "What happened at the market?",
  "explicit_node_ids": ["event_market_fire", "character:blacksmith_npc"]
}
```

Node IDs match the identifier component of a context item key — the part after the first `:` in keys like `"character:blacksmith_npc"` or `"event:market_fire"`. When `explicit_node_ids` is omitted or empty the score is 0.0 for all nodes, and the `explicit` weight has no effect regardless of its configured value.

Tier B RAG chunks are technically addressable by their row ID (e.g., `"rag:42"` → node_id `"42"`), but are better left to vector similarity — Tier A graph node IDs are stable and meaningful to the game engine.

## Validation

`RelevanceWeights` is a frozen Pydantic model in [npc_engine/schema/llm_config_models.py](../npc_engine/schema/llm_config_models.py). The `validate_weights_sum` model validator rejects any config where the sum deviates from 1.0 by more than 1e-6. This fires at startup so misconfigured weight files fail fast rather than producing silently biased context.

The `explicit` field defaults to `0.0`, so existing weight profiles that do not declare it remain valid (their five declared fields already sum to 1.0).
