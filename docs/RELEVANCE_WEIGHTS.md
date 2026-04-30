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
| `explicit` | Was this node explicitly flagged by the game engine as relevant for this turn? |

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

## Validation

`RelevanceWeights` is a frozen Pydantic model in [npc_engine/schema/llm_config_models.py](../npc_engine/schema/llm_config_models.py). The `validate_weights_sum` model validator rejects any config where the sum deviates from 1.0 by more than 1e-6. This fires at startup so misconfigured weight files fail fast rather than producing silently biased context.
