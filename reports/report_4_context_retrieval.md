# Report 4: Context Retrieval Improvements

> **Scope:** General review of the retrieval pipeline — relevance quality, completeness, token efficiency, latency.
> **Date:** 2026-05-13

---

## Section 1: Current Pipeline Audit

### 1.1 Tier Model Analysis

`context_builder.build_serialized_context` assembles four tiers in order:

**Tier 0 — World & emotion** (lines 137–140, always included, never compressed)
- `world` — full `WorldState` JSON (~150–250 tokens with 2 standings + 1 condition)
- `emotion` — only `{"current_mood": "<label>"}`. Arousal and valence are computed in `dialogue_handler.py:139–158` but never propagated into Tier 0.
- **Gap**: Tier 0 has no enforced token cap in the active code path. `TIER0_MAX_TOKENS = 380` exists only in the legacy `token_budget_enforcer.py` which is unused. In the active `context_budget_enforcer.enforce_context_budget`, Tier 0 is never validated.

**Tier A — Character facts** (lines 141–232 + session turns, never compressed)
Fetches these queries serially: `get_character_with_relations`, `get_events_for_npc` (limit=5), `get_npc_location_id`, `get_location_context`, `get_reputation_context_for_npc`, `get_memories_for_character` (k=3), `get_beliefs_for_character` (k=3), `get_goals_for_character` (k=3), `get_items_for_character` (no limit), `get_secrets_for_character` (k=3), `get_debts_for_character` (k=5). Budget: `tier_a: 4000` tokens. If Tier A exceeds 4000 tokens, the request fails with `ContextBudgetError`.

**Tier B — RAG primary half** (lines 234–254)
Vector index search on `player_message`, top-K=5 results. The first `max(1, len//2)` = 2 of 5 results go to Tier B. Budget: `tier_b: 3000`. Compressed at 85% of budget.

**Tier C — RAG secondary half**
Remaining 3 of 5 vector results. Budget: `tier_c: 2000`. Most aggressively dropped in the final pass.

**Final pass** (`context_builder.py:304–344`): iteratively drops Tier C then Tier B items until `serialized_size <= PROMPT_TOKEN_BUDGET = 800`.

**Tier model issues:**
1. Tier 0 is uncapped in the active enforcer — a large `WorldState` silently consumes all available space.
2. Tier A is a single bucket with no internal priority. There is no graceful Tier A trimming — it either fits or the request fails.
3. No middle tier exists for "graph facts relevant to the current query" (e.g., beliefs that mention entities from the player message). Currently graph facts are either always included (Tier A) or only surfaced via the character-hash vector (Tier B/C).
4. Several graph domains are missing from all tiers entirely (see below).

**Missing from any tier:**
- Player character beliefs/goals/secrets — the player is represented only via the `RELATES_TO` edge and reputation standing.
- Player's active quest state — dialogue is completely blind to quest progress.
- Nearby NPC beliefs/goals/relations — `nearby_npcs` in Tier A dumps full property dicts but no mind-layer facts.
- Faction relations between NPCs (MEMBER_OF + STANDS_WITH for NPCs in the scene).
- Schedule/routine context — the NPC's expected activity for `time_of_day` is never read.
- Recent trade/economy history — `pricing_queries.py` exists but nothing in `context_builder.py` reads it.

---

### 1.2 Tier A Completeness

| Fact | NPC only? | Player? | Nearby NPCs? | Limit | Order |
|---|---|---|---|---|---|
| Profile | NPC only | No | Yes (full props, no filter) | 1 | n/a |
| Relations | NPC outgoing only | No | No | All RELATES_TO | n/a |
| Memories | NPC only | No | No | k=3 | `vividness DESC` |
| Beliefs | NPC only | No | No | k=3 | `confidence DESC` |
| Goals | NPC only, `status='active'` | No | No | k=3 | `urgency DESC` |
| Items | NPC only | No | No | **no limit** | undefined |
| Secrets | NPC only | No | No | k=3 | `severity DESC` |
| Debts | NPC only | No | No | k=5 | `due_by ASC` |
| Reputation | NPC factions × player | Yes | No | Threshold filter (≥20) | descending standing |
| Events | NPC KNOWS_ABOUT only | No | No | k=5 | `occurred_at DESC` |
| Location | NPC current | n/a | n/a | 1 | n/a |
| Nearby NPCs | At NPC's location | Excluded | n/a | All | n/a |
| Session turns | n/a | Joint | No | DIALOGUE_SESSION_TURNS=10 | chronological |

**Key gaps:**
- Beliefs/goals/secrets are ordered by intrinsic priority (confidence/urgency/severity), not by relevance to the current player message. Top-3 most intense beliefs may have nothing to do with what was asked.
- Items have no limit — an NPC with 50 items dumps all 50 into Tier A. A token-cost outlier and a relevance hole simultaneously.
- Nearby NPCs emit full property dicts (via `collect(properties(c))` in `CYPHER_GET_LOCATION_CONTEXT`). A market scene with 6 NPCs may emit ~600 tokens of NPC properties the model rarely uses.
- Memory recency is ranked by `vividness` only, not by `last_recalled_at` or `created_at_game_time`.

---

### 1.3 Relevance Scoring Gaps

`context_relevance_engine.py:37–66` computes a weighted sum of 6 signals (weights from `config/llm_config.yaml:10–16`):

| Dimension | Weight | Implementation | Issues |
|---|---|---|---|
| recency | 0.25 | Linear decay from 1.0 at age 0 to 0.0 at 72h, using `datetime.now(UTC)` (`context_scoring.py:70–83`) | Hard-coded 72h half-life is **wall-clock**, but most timestamps are **game time** (e.g., `Memory.created_at_game_time`). Ancient game events score as "very recent" because their DB row was created minutes ago. |
| severity | 0.20 | Reads `payload["severity"]` / 100 | Only Event, Secret have `severity`. `Memory.emotional_charge` is in the payload but NOT mapped. Beliefs (`confidence`), Goals (`urgency`), Items have no severity — they always score 0.0 and lose to any event regardless of importance. |
| proximity | 0.20 | Infers hops from key prefix (`context_scoring.py:106–118`) — RAG items get `max_proximity_hops + 1` | RAG items receive `proximity_score = 0.0` by construction — the proximity dimension cannot help rank Tier C items at all. |
| relation | 0.20 | Uses `vector_scores[key]` for Tier B; `priority/100` otherwise | Conflates graph-relation strength with vector cosine similarity. The actual `RELATES_TO.trust/affinity/respect` between the NPC and event participants is never consulted. |
| quest | 0.10 | Returns 1.0 if substring `"quest"` is in the key (`context_scoring.py:99–103`) | String-match only. No quest node is fetched in `subgraph_retriever`, so this dimension fires almost never. |
| explicit | 0.05 | Returns 1.0 for Tier A, 0.0 otherwise | Redundant with the tier separation itself — Tier A items are never dropped, so this weight has no ranking effect within any tier. |

**Critical consequence**: because most non-event Tier A items return 0 for severity, 0 for recency (items/beliefs have no timestamp), and 0 for quest, the typical item scores ~0.05 (explicit only). Ranking within Tier A is dominated by ties and falls back to `(node_type, node_id, key)` alphabetical order (`context_relevance_engine.py:93–100`). In practice, belief/goal/item ordering inside Tier A is effectively **alphabetical, not relevance-weighted**.

**Graph signals available but unused:**
- `RELATES_TO.trust/affinity/respect` between the NPC and event participants
- `Memory.emotional_charge` (in payload, not mapped to severity)
- `Goal.urgency` and `Belief.confidence` (both 0–100, mappable to severity)
- Player's faction standings (Tier A item, not a scoring signal)
- NPC arousal/valence (computed in EmotionUpdater, not propagated into Tier 0 or scoring)
- World epoch (could weight epoch-tagged events higher)
- `KNOWS_ABOUT.knowledge_state` ('knows' vs 'rumored' vs 'distorted') — never used to penalize uncertain knowledge

---

### 1.4 Vector Search Analysis

**What's indexed** (`embedding_reconciler.py:20–57`):
- Character: `name + archetype + biography + current_mood`
- Event: `summary + event_type + location_id`
- Location: `name + descriptor + region + location_tag`

Beliefs, Goals, Memories, Secrets, Items, Factions, Quests are **not indexed**.

**The embedding itself** (`embedding_index.py:13–23`): a 16-dimensional character-bucket hash that sums `ord(char) % 101` into buckets, normalized by length. **This is not a semantic embedding.** Despite `Settings.EMBEDDING_MODEL = "all-MiniLM-L6-v2"` existing in `config.py:69`, no sentence-transformer is loaded anywhere — that config string is dead. Dot-product similarity is dominated by character-frequency overlap; semantically related but lexically different strings ("smith" vs. "blacksmith", "the war" vs. "conflict") rank low.

**Query** (`context_builder.py:238`): raw `player_message` embedded — no expansion, no NPC-specific reformulation.

**RAG_TOP_K=5 in practice**: 5 nodes total from Character + Event + Location, with no per-type quota. A query that hash-overlaps location names returns 5 locations and zero events.

**No reranking**: vector results pass through scoring where `proximity_score = 0`, and are serialized. No cross-encoder rerank.

**Cold-start**: `EmbeddingReconciler` reconciles every `EMBEDDING_RECONCILE_INTERVAL_SECONDS = 300` seconds. First 5 minutes after startup: empty index, Tier B/C produce no results. Index is in-memory only (`InMemoryVectorStore`) — Qdrant backend raises `NotImplementedError`. Restart clears everything.

**No NPC knowledge filter**: vector search retrieves from the global corpus. An NPC in a remote region can surface events from anywhere — there is no `KNOWS_ABOUT` filter on retrieval.

---

### 1.5 Compression Analysis

`context_compression.py:_compress_text` (lines 114–121):

```python
target_chars = max(32, target_tokens * 4)
clipped = text[: max(1, target_chars - len(COMPRESSION_SUFFIX) - 12)]
return f"{clipped}{COMPRESSION_SUFFIX}#{digest}"
```

**This is pure left-truncation**, not summarization. Most likely outcome: trailing JSON braces are removed, producing invalid JSON. The LLM sees `{"summary":"…","participants":["a","b...[compressed]#abcd1234` and must learn to parse around it.

Compression triggers at `compression_trigger_ratio = 0.85` (85% of tier budget). All items in the tier are compressed to the same `per_item_target = budget / len(items)` regardless of intrinsic importance. Lower-priority items are dropped, but content within items is truncated rather than field-selectively reduced.

**Tier A is never compressed** — if it overruns `PROMPT_TOKEN_BUDGET`, the request fails with `ContextBudgetError(tier="total_prompt")`.

---

### 1.6 Token Budget Calibration

`PROMPT_TOKEN_BUDGET = 800` (`config.py:74`). Token estimator: `(len(text) + 3) // 4` chars/token (`context_utils.py:18–28`).

**Estimated Tier 0 + Tier A for a typical NPC** (3 beliefs, 2 goals, 3 items, 2 secrets, 3 memories, 3 debts, 5 events, 2 nearby NPCs, 10 session turns):

| Item | ~tokens |
|---|---:|
| World state (2 standings, 1 condition) | 70 |
| Emotion (`current_mood`) | 7 |
| Session turns (10 × ~80 chars) | 200 |
| Character profile (biography ~200 chars) | 150 |
| Player relation edge | 30 |
| Location context | 50 |
| Nearby NPCs (2 × full props) | 125 |
| 5 events × ~200 chars | 250 |
| 3 beliefs | 75 |
| 2 goals | 63 |
| 3 items | 113 |
| 2 secrets | 63 |
| 3 memories | 100 |
| 3 debts | 75 |
| Reputation | 25 |
| **Tier 0 + A total** | **~1400** |

**Tier 0 + Tier A already consume ~1.75× the 800-token final budget** before any Tier B/C is added. In practice, Tier B and Tier C are almost always dropped in the final pass. The dialogue model rarely sees vector-retrieved facts. The 4000-token Tier A budget is meaningless — the binding constraint is the 800-token final budget.

**Interaction with model context**: Mixtral-8x7B has a 32K window. System prompt (~256 tokens) + 800-token prompt budget + 512 output = ~1568 tokens. The model has another 30K of unused headroom. **The 800-token cap is artificially conservative** and forces aggressive lossy truncation of naturally-growing context.

---

## Section 2: Relevance Quality Improvements

### 2.1 Query-Time Signals Currently Unused

| Signal | How it could improve retrieval |
|---|---|
| **Player message keywords** | Extract noun phrases/proper nouns; boost beliefs/secrets/events whose content contains those tokens — much more reliable than the current character-hash embedding. |
| **NPC active goals (urgency)** | Re-embed goal descriptions; boost events/memories/items whose embedding is close to any active goal. Boost beliefs whose `target_id` matches a goal's `target_id`. |
| **Player quest status** | A `MATCH (p:Character {id:$player_id})-[:ON_QUEST]->(q:Quest)` would surface the player's quest objective — anything related to that quest should rank highly. |
| **NPC arousal + valence** | Use arousal to boost recent high-severity events; use negative valence to boost grievance/debt items; use mood for mood-congruent memory recall. |
| **Location filter on vector search** | Filter the global vector search to events tagged with the NPC's current `LOCATED_AT.location_id` — eliminates cross-region noise. |
| **Active faction-standing changes (last N ticks)** | Surface recent standing swings as high-priority Tier A items — "the player just lost 30 reputation with Faction X" is critical context. |
| **Last turn's `mood_update`/`relation_deltas`** | Structured signal from the previous turn's output that primes the next retrieval without relying on the LLM to re-derive it from session text. |

### 2.2 Graph-Traversal-Based Relevance

**a. Trust-weighted second-hop events**
Pattern: `(npc)-[:RELATES_TO {trust > 50}]->(friend)-[:KNOWS_ABOUT]->(event) WHERE NOT (npc)-[:KNOWS_ABOUT]->(event)`. Surfaces events the NPC's trusted friends know about — natural seeds for what the NPC would be curious about. One extra `OPTIONAL MATCH` from the existing relation fetch; sub-50 ms with `Character.id` index.

**b. Goal-connected events**
Pattern: `(npc)-[:PURSUES]->(g:Goal {status:'active'}) WITH g.target_id AS target MATCH (e:Event) WHERE e.actor_id = target RETURN e`. Pulls events about the targets of active goals — directly relevant to what the NPC cares about.

**c. Topic-relevant secrets by keyword**
Pattern: `(npc)-[:KNOWS_SECRET]->(s:Secret) WHERE toLower(s.content) CONTAINS toLower($keyword)`. Substring match when the player mentions a known entity. Cheap and complementary to vector retrieval.

**d. NPC knowledge filter on vector search**
Constrain the vector search results to only nodes the NPC has a `KNOWS_ABOUT` edge to — removes cross-region noise and improves correctness.

**e. Trade-network awareness**
Check `(player)-[:TRANSFERRED_ITEM_TO]->(:Character)` for recent transfers, then check if the NPC has a `RELATES_TO` edge with any destination. Surfaces "the player traded with the NPC's acquaintance" as gossip-worthy context.

### 2.3 Contextual Belief/Goal/Secret Retrieval

Currently flat: `ORDER BY confidence DESC LIMIT 3` — static within a session, identical for "What's the weather?" and "What do you think of the king?". The top-3 most intense beliefs may have nothing to do with what was asked.

**Risk of always-include irrelevant beliefs:**
- ~75 tokens per turn permanently consumed regardless of relevance.
- The LLM may anchor on a high-confidence-but-off-topic belief and insert it into unrelated responses.
- If top beliefs are all about one subject, the NPC sounds monomaniacal.

A two-pass approach (fetch top-N by intensity, then re-rank top-N by keyword overlap with player message, keep top-3) addresses this without schema changes.

### 2.4 Conversation-Aware Retrieval

Session turns are included as an opaque serialized blob (`context_builder.py:142`). Nothing extracts entities or topics from prior turns to influence what gets retrieved.

**Concrete missed opportunities:**
- If turn N-1 was "Tell me about the guild" and turn N is "What about the leader?", retrieval treats turn N as a self-contained query — no concept that "the leader" refers to the guild leader.
- The vector index would benefit from a concatenated query (last 2 turns + current message) rather than the current message alone — cheap conversational expansion with no LLM call.
- Keyword extraction over the last 2–3 turns could maintain a small "topic set" used to boost beliefs/secrets/events sharing those tokens.

---

## Section 3: Token Efficiency Improvements

### 3.1 Context Format Optimization

Issues in the current serialized JSON (observable from `context_serializer.py`, `subgraph_retriever.py`, `context_utils.py:49–61`):

**a. Null/empty fields are not stripped.** `serialize_json` with `sort_keys=True` does not skip null fields. `"created_at_game_time": null` is ~30 tokens per item across beliefs/goals/secrets.

**b. Low-value ID fields are serialized into the prompt.** Events from `get_events_for_npc` include `id`, `actor_id`, `location_id` — identifiers the LLM cannot act on. Dropping them is pure savings.

**c. Nearby NPCs emit full property dicts** via `collect(properties(c))` in `CYPHER_GET_LOCATION_CONTEXT`. Name + id + faction would suffice for location context.

**d. ISO timestamps are verbose.** `2026-05-13T14:32:11.123456+00:00` is ~8 tokens. Game-time compact encoding (year, season, day, time_of_day) is ~4 tokens.

**e. Item list is unbounded.** An NPC with 50 items dumps all 50 into Tier A with no limit or relevance filter.

**Estimated aggregate savings from (a)–(d) alone: 25–35% reduction in Tier A serialized size** with no information loss.

### 3.2 Progressive Context Loading

The pipeline fetches all tier-A queries before the budget enforcer runs. If Tier 0 + character profile + relations alone exceed 800 tokens, the subsequent 7 graph queries are wasted. A progressive model would short-circuit: fetch essentials, measure budget remaining, then decide whether to expand beliefs/goals/items. Each skipped query saves 5–15 ms at Neo4j round-trip latency.

### 3.3 Session-Level Caching

`DialogueContextCache` (`dialogue_context_cache.py`) caches the full serialized context keyed on `(npc_id, session_id, player_id, npc_last_graph_updated_at, world_last_updated_at, current_mood)`. The cache key invalidates when `current_mood` changes — which happens after most dialogue turns (EmotionUpdater runs after each reply). In practice the cache misses on nearly every turn within an active conversation.

Sub-caches with different invalidation conditions per component (world state, NPC profile, beliefs) would convert most full misses into partial hits, avoiding 70–80% of the graph query work per turn.

### 3.4 Differential Context (Delta Updates)

Between turns N and N+1, most context is unchanged: world state, NPC profile, beliefs/goals/items (unless a writer ran). Only session turns, emotion, and relation deltas from the previous turn's output reliably change. A context-delta model that patches only changed fields and re-serializes would avoid 9 of 11 graph queries on most repeat turns. This requires the serializer to support diff-style updates — significant refactor, but the highest efficiency ceiling.

---

## Section 4: Production RAG Patterns — Applicability

### 4.1 HyDE (Hypothetical Document Embeddings)

**Low applicability now.** Requires a small LLM call per turn (latency), and the current embedding is a character-bucket hash — HyDE on a hash adds nothing. Revisit after a real embedding model is in place.

### 4.2 Multi-Query Retrieval

**Medium applicability.** Player messages are often very short ("hi", "what's that?"). Deterministic reformulation — extract proper nouns from the message, concat with the last 1–2 turns — is a no-LLM approach that would significantly improve recall from the vector index. Each additional query is ~1 ms on the in-memory store. Worth implementing once the embedding is real.

### 4.3 Reranking (Cross-Encoder)

**High applicability.** After vector retrieval, a `cross-encoder/ms-marco-MiniLM-L-6-v2`-class model reranks the top-K results. Latency: ~15–30 ms on CPU (sub-millisecond on GPU). This is the standard quality lever for vector retrieval and would substantially improve Tier B/C precision given the current bi-encoder's limitations. Depends on first having a real bi-encoder (recommendation #1 in Section 6).

### 4.4 Contextual Compression (LLM-Based)

**High applicability — but the dependency is a schema-aware compressor, not an LLM.** The current `_compress_text` chops bytes and produces invalid JSON. A field-selection compressor that defines per-node-type "essential field sets" (e.g., for events: keep `summary + severity + occurred_at`, drop `actor_id + location_id + schema_version`) is the right intermediate step — no LLM needed, no schema parsing required.

LLM-based contextual compression (extract only sentences relevant to the current query) is worth exploring for long Biography or Event summary fields once the budget is increased to accommodate it.

### 4.5 Parent-Child Chunking

**Low applicability.** Each indexed node (Character, Event, Location) is already small (a few hundred chars). The text being indexed is already a concatenation of short fields. Nothing to subdivide. Revisit if long-form content (quest descriptions, location lore, faction histories) is added to the schema.

### 4.6 Knowledge Graph-Augmented Retrieval (GraphRAG)

**The highest-fit pattern for this codebase.** The graph already has rich relationship structure. A GraphRAG pattern would:
1. Vector-search for top-K seed nodes (Events, Characters, Locations).
2. Filter seeds by `KNOWS_ABOUT` edge to the NPC — corrects the global-search problem.
3. Expand 1-hop from each seed along trust-weighted or quest-relevant edges (e.g., from an Event to participants the NPC has RELATES_TO with).
4. Return seed + expansion as a small subgraph.

Today's pipeline does (1) and (3) independently — Tier A pulls character facts, Tier B/C pulls vector results, but the two never cross-reference. A GraphRAG pattern unifies them: a single traversal starting from the player message that respects the NPC's knowledge boundary. Cost: one additional Cypher query per turn (with `Character.id`, `Event.id` indexes, sub-50 ms). This is the end-state retrieval architecture worth building toward.

---

## Section 5: Latency Analysis

### 5.1 Current Retrieval Latency Breakdown

From `context_builder.build_serialized_context` (`context_builder.py:109–254`):

| Step | Sequential? | Notes |
|---|---|---|
| `get_world_state` | Yes | |
| `get_character_with_relations` (line 110) | Yes | **Redundant** — called again inside `retrieve_tier_a_context` |
| `retrieve_tier_a_context` (4 internal queries: character, events, location_id, location_context) | Sequential internally | Location_id → location_context is a dependency chain |
| `get_reputation_context_for_npc` | Yes (follows tier_a) | Independent of tier_a results |
| `get_memories_for_character` | Yes | Independent |
| `get_beliefs_for_character` | Yes | Independent |
| `get_goals_for_character` | Yes | Independent |
| `get_items_for_character` | Yes | Independent |
| `get_secrets_for_character` | Yes | Independent |
| `get_debts_for_character` (2 internal queries: debtor + creditor) | Sequential internally | Could be a single UNION query |
| `embedding_index.search` | Yes (after all graph queries) | Independent of all graph queries |

**Total: ~13 sequential round trips to Neo4j + 1 vector store call.** At 5–15 ms per Neo4j query on local Bolt, the lower bound is ~65 ms; realistic context-build latency is **150–250 ms before LLM call**. Actual numbers require instrumentation — none exists today (see Report 1, Section 8: no LLM or retrieval latency metrics).

### 5.2 Parallelization Opportunities

After `character_payload` is available, all of these are independent of each other and can run in one `asyncio.gather`:
- `get_reputation_context_for_npc`
- `get_memories_for_character`
- `get_beliefs_for_character`
- `get_goals_for_character`
- `get_items_for_character`
- `get_secrets_for_character`
- `get_debts_for_character`
- `get_events_for_npc` (inside `retrieve_tier_a_context`)
- `embedding_index.search` (depends only on `player_message` — can start in parallel with the very first query)

True dependency chain: `get_npc_location_id` → `get_location_context`.

With `asyncio.gather`, ~13 sequential queries collapse to roughly **3 sequential stages**:
1. `get_character_with_relations` + `embedding_index.search` in parallel
2. `get_npc_location_id`
3. Gather of all remaining independent queries + `get_location_context`

**Expected latency reduction: ~130 ms → ~40–60 ms** (3 round-trip stages instead of 13).

### 5.3 Graph Query Optimization

**Redundant query**: `get_character_with_relations` is called at `context_builder.py:110` (for cache key) and again inside `retrieve_tier_a_context` at `subgraph_retriever.py:31`. Two identical queries per turn.

**Two-query debt fetch**: `get_debts_for_character` runs separate debtor + creditor queries then Python-sorts (`owes_queries.py:85–107`). These could be a single Cypher `UNION` or one `MATCH` with directional `OR`.

**Nearby NPC payload size**: `CYPHER_GET_LOCATION_CONTEXT` returns `collect(properties(c))` — full property bags for every NPC at the location. A busy market with 6 NPCs emits ~600 tokens of properties the LLM doesn't use. A projection of `{id, name, archetype, faction}` would be sufficient.

**Index coverage**: cannot determine from code whether `Character.id`, `Event.id`, `Location.id`, `Belief.id`, `Goal.id`, `Secret.id`, `Memory.id` are indexed in Neo4j. If any are missing, those queries do a full label scan. `SHOW INDEXES` in Neo4j is the verification step.

### 5.4 Embedding Index Latency

**Embedding model in use**: 16-dimension character-bucket hash (`embedding_index.py:13–23`). Latency: microseconds — effectively free. `Settings.EMBEDDING_MODEL = "all-MiniLM-L6-v2"` (`config.py:69`) is dead config — no sentence-transformer is loaded.

Switching to `all-MiniLM-L6-v2` (384-dim): ~5 ms per query on CPU, sub-millisecond on GPU. Four orders of magnitude slower, but semantically meaningful. The latency delta is small relative to the Neo4j round trips.

**Storage**: in-memory dict, O(N × 16) dot-product. At 10K nodes, sub-millisecond. No ANN index needed at current scale; would need FAISS or Qdrant beyond ~500K nodes. **Index is not persisted** — restart clears it; the EmbeddingReconciler refills it over the next 5-minute cycle. Cold-start quality: no vector results for first reconcile interval.

---

## Section 6: Prioritized Recommendations

| # | Recommendation | Relevance | Tokens | Latency | Effort |
|---|---|---|---|---|---|
| 1 | **Replace `_embed_text` with a real embedding model** (`all-MiniLM-L6-v2` or similar). The character-bucket hash is the root cause of Tier B/C being nearly useless. | **High** | — | +5–20 ms | M |
| 2 | **Fix compression to be JSON-safe.** Switch from byte-truncation to per-node-type field-selection (keep essential fields, drop verbose ones). | Medium | **High** | — | S |
| 3 | **Strip null fields and low-value ID fields from serialized items** (event `id`, `actor_id`, `location_id`; goal/belief null timestamps). Estimated 25–35% Tier A reduction. | — | **High** | — | S |
| 4 | **Parallelize independent Tier A queries with `asyncio.gather`** (~13 sequential → 3 stages). | — | — | **High** (~70–100 ms saved) | M |
| 5 | **Remove redundant `get_character_with_relations` call** at `context_builder.py:110` (called again inside `retrieve_tier_a_context`). | — | — | −5–15 ms | XS |
| 6 | **Cap Tier 0 in `context_budget_enforcer`** — `TIER0_MAX_TOKENS` exists in the unused legacy enforcer but is never applied in the active code path. | — | Medium | — | S |
| 7 | **Increase `PROMPT_TOKEN_BUDGET` from 800 to 2000–3000** given Mixtral's 32K window. The current cap starves the context pipeline. Apply after #2 and #3 to avoid filling the new budget with low-value text. | **High** | — | — | XS |
| 8 | **Map `Memory.emotional_charge`, `Goal.urgency`, `Belief.confidence` into the severity scoring dimension** (`context_scoring._extract_severity_score`). These all return 0.0 today. | **High** | — | — | S |
| 9 | **Fix recency scoring to use game time, not wall-clock time** (`context_scoring._extract_recency_score:70–83`). | Medium | — | — | S |
| 10 | **Add `RELATES_TO.trust` as a scoring signal** for events involving participants the NPC knows. Frees the `relation` weight from conflating graph-relation with vector-similarity. | **High** | — | +1 join | M |
| 11 | **Cap nearby NPC payload to `{id, name, archetype, faction}`** instead of `collect(properties(c))` from `CYPHER_GET_LOCATION_CONTEXT`. | — | Medium | — | S |
| 12 | **Add item limit (`k=10`) and recency/value ordering to `get_items_for_character`**. Currently unbounded. | — | Medium | — | S |
| 13 | **Add `KNOWS_ABOUT` filter to vector retrieval** — restrict to events the NPC actually knows, eliminating cross-region noise. | **High** (correctness) | — | +1 filter | M |
| 14 | **Two-pass belief/goal/secret retrieval**: fetch top-N by intrinsic score, re-rank by keyword overlap with player message, keep top-3. | **High** | Medium | +5 ms | M |
| 15 | **Conversation-aware query expansion**: concat last 1–2 session turns with current message for vector search. | Medium | — | — | S |
| 16 | **Add player quest state as a retrieval signal** (`get_player_quest_state` accessor + `quest` scoring using actual quest data). Today the quest dimension fires on key-string match only. | High | — | +1 query (parallelizable) | M |
| 17 | **Cross-encoder rerank for Tier B/C** after vector retrieval. | High | — | +15–30 ms (CPU) | M |
| 18 | **Sub-cache decomposition of `DialogueContextCache`**: separate TTLs for world state / NPC profile / dynamic fields. Eliminates full-context cache misses on emotion changes. | — | — | Medium | L |
| 19 | **GraphRAG pattern**: unify Tier A graph traversal with Tier B/C vector retrieval into a single traversal respecting `KNOWS_ABOUT`. | **High** | Medium | Likely faster overall | L |
| 20 | **Drop or repurpose the `explicit` scoring weight (0.05)**. It returns 1.0 for Tier A and 0.0 everywhere else — it is a constant, not a signal, and contributes nothing to ranking. | Low | — | — | XS |

**Suggested phasing:**

| Phase | Items | Goal |
|---|---|---|
| 1 — Quick wins (all S/XS) | #2, #3, #5, #6, #8, #9, #11, #12, #15, #20 | Remove obviously broken behavior; significant token savings |
| 2 — Foundation | #1, #4, #7 | Real embeddings + parallelism + budget breathing room |
| 3 — Quality lift | #10, #13, #14, #16, #17 | Relevance-aware retrieval; needs phase 2 first |
| 4 — Scale | #18, #19 | Session caching + GraphRAG unification |
