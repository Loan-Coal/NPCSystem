# Skills Queue

_(Populated when a skill opportunity is identified during development. Append only.)_

## graph-node-field-migration
**Identified:** 2026-05-27 (R1.4)
**Pattern:** Adding a new optional field to a graph node type end-to-end: schema → seed → serialization → consumer → tests.
**Checklist:**
1. Add field to `type_registry/base_nodes/<type>.yaml` (schema source of truth).
2. Update all seed scripts — `build_*_payload()` function signature + returned dict + data tuples.
3. Confirm Cypher query uses `RETURN properties(c)` (all-fields pattern) — no change needed. If explicit RETURN, add the field.
4. Trace serialization: `subgraph_retriever` → `context_serializer` → confirm field appears at `npc.profile.<field>` in the context JSON.
5. Update consumer (e.g. `prompt_builder.py`) to read from context JSON.
6. Update tests: builder shape tests + consumer extraction tests.
7. **Docker note:** The app container has a baked copy of the YAML schemas. After updating `character.yaml`, run `docker cp <local_path> npcsystem-app-1:<container_path>` and `docker restart npcsystem-app-1` before re-seeding. Then wipe graph with `docker exec npcsystem-neo4j-1 cypher-shell -u neo4j -p password "MATCH (n) DETACH DELETE n"` and run `make demo-seed`.
**Reuse when:** Any Phase 3+ Character/Location node field addition (e.g. `schedule`, `mood_modifier`, `reputation_threshold`).


## context-driven-prompt-rule
**Identified:** 2026-05-27 (R2.1)
**Pattern:** When a new LLM behavioral rule must key off a specific context JSON field,
follow this workflow end-to-end:
1. Identify the context field and its value space (e.g. `knowledge_state: "rumor" | "knows"`).
2. Write a **paired** eval case: `keyword_none` (NPC must NOT do X when authoritative) +
   `keyword_any` (NPC MUST do Y when rumour-state). Both cases use `requires_world`.
3. Write the rule in `system_v1.yaml` referencing the field by exact JSON key name.
4. Bump `PROMPT_VERSION` in `prompt_builder.py`.
5. Delete `.cache/demo/` and run `make demo-run` to rebuild cache.
6. Verify: `make eval` all green, `make demo-run ARGS=--cached` completes clean.
**Reuse when:** Any Phase 3+ graph field needs to drive LLM behavior
(e.g. new Character fields, relationship-state flags, location conditions).
**Also applies to:** Generalizing an existing context-driven rule that has hardcoded
specifics (e.g. hardcoded location names, entity types, or domain references). Replace
the specific reference with the general context field. Same workflow: write paired evals,
edit YAML, bump version, cache rebuild.


## eval-case-authoring
**Identified:** 2026-05-27 (pre-Phase 3 cleanup)
**Pattern:** End-to-end workflow for adding a new eval YAML case to `evals/cases/`.
**Checklist:**
1. **Pick a seed world.** Which world has the NPC you need? Demo world: `mira_innkeeper`, `aldric_merchant`, `captain_sorn`, `lira_fence`, `old_henryk`. Village world: `vw_elder`, `vw_guard`. Tavern world: `tw_merchant`. If none fit, add the NPC to the relevant seed file first.
2. **Set `requires_world`** in the `seed` block. Omitting it means the case will fail with an HTTP error if the server doesn't have the NPC — not a helpful failure.
3. **Positive + negative pair discipline.** Every behavioral claim gets a positive case (`keyword_any`, `tone_judge`) AND a negative case (`keyword_none`). "Mira hedges gossip" must be paired with "Mira does NOT speak with military authority."
4. **`tone_judge` format.** Use `judge_prompt` (explicit YES/NO criteria) for nuanced behavioral tests. Use `description` only for simple sentiment checks. `judge_prompt` should end in "YES if …, NO if …." to force a binary verdict.
5. **Verify the case exercises the graph, not a fallback.** Run once with a wrong `npc_id` (e.g. `npc_id: doesnt_exist`). Expect the runner to show FAIL with an HTTP error. If you get a canned response instead, the server is returning a fallback — investigate `degradation_level` in the response.
6. **Wire a Makefile shortcut if needed.** Single-NPC voice sets don't need one. A new world's cases should have a `seed-<world>-world` target.
7. **Confirm all cases pass with `make eval`.** Voice/tone cases also require `make eval-llm-demo`.
**Reuse when:** Adding any new NPC to the eval harness, after a new world seed is created, or when a `context-driven-prompt-rule` skill run generates new behavioral constraints.


## llm-eval-as-e2e
**Identified:** 2026-05-28 (S3.0)
**Pattern:** Integrating YAML eval cases into the pytest e2e suite as parametrized tests.
**When to use:** Any time you want pytest reporting, skip semantics, or CI integration for YAML eval cases.
**Key files:** `e2e/scenarios/scenario_yaml_evals.py`, `evals/matchers.py`, `evals/cases/*.yaml`
**Checklist:**
1. YAML cases load at module level via `_load_cases()` for `@pytest.mark.parametrize` to see all IDs at collection time.
2. Add `evals/` to `sys.path` at the top of the scenario file — `matchers.py` uses bare imports. Pattern:
   ```python
   _EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"
   if str(_EVALS_DIR) not in sys.path:
       sys.path.insert(0, str(_EVALS_DIR))
   from matchers import evaluate
   ```
3. **Skip semantics (not failure):** NPC 404 → wrong world seeded → skip with `requires_world` hint. Connection error → skip. Only fail on assertion failure after 200 OK.
4. **Do NOT duplicate matchers logic.** Import `evaluate()` from `evals/matchers.py` directly.
5. **Run:** `make eval-e2e` (pytest) or `make eval` (CLI runner — faster, no pytest overhead).
6. Both systems must stay green. Never remove a YAML case to fix a failing test — fix the evaluation.
**Reuse when:** Adding new eval cases, wiring evals to CI, or onboarding to test infrastructure.


## multi-demo-scenario
**Identified:** 2026-05-28 (S3.0)
**Pattern:** Building a new storyline demo script in `demo_game/scenarios/`.
**When to use:** Adding a 3rd or 4th story arc demo; or adapting an existing arc to a new world.
**Checklist:**
1. **Pick a seed world** with NPCs and events that showcase different features than existing demos. Each demo should highlight 2-3 features the others don't prominently show.
2. **Outline 5-7 beats** with a narrative arc: establish world state → introduce event → show knowledge propagation → contrast voices. At least one beat should show gossip hedging (Rule 9).
3. **Create `demo_game/scenarios/run_<name>.py`** modelled on `run_village_crisis.py`. Each script is self-contained — its own `LLMCache`, `Scene` dataclasses, and `DemoRunner`. `_CACHE_DIR` must be unique (`.cache/<name>/`).
4. **Add Makefile targets:**
   ```makefile
   demo-<name>:
       $(PYTHON) -m demo_game.scenarios.run_<name> $(ARGS)
   ```
   Add to `.PHONY` list.
5. **Build cache:** Run `make demo-<name>` (live) to warm the LLM cache. Then verify `make demo-<name> ARGS=--cached` completes in < 5s.
6. **Dry-run check first:** `make demo-<name> ARGS=--dry-run` must print the full beat sequence cleanly before any live run.
**Feature coverage matrix** (update when adding new demos):
| Feature | Gossip chain demo | Village crisis | Tavern intrigue |
|---------|-------------------|----------------|-----------------|
| epoch=war | ✅ | — | — |
| active_conditions (non-war) | — | ✅ crop_blight | ✅ theft_at_market |
| gossip hedging Rule 9 | ✅ Henryk | ✅ Farmer Jorin | ✅ Wanderer |
| voice distinctiveness | ✅ Sorn/Mira | ✅ Elder/Healer/Guard | ✅ Innkeeper/Bard/Merchant |
| knowledge guards | ✅ Mira/Henryk | ✅ Guard/Farmer | ✅ Wanderer |
| event propagation | ✅ war/market fire | ✅ bandit raid | ✅ theft |


## per-npc-dialogue-log
**Identified:** 2026-05-28 (S3.1)
**Pattern:** In a pygame game on top of NPC Engine, maintain one `ScrollableLog` per NPC using a `dict[npc_id, ScrollableLog]` in the `GameWindow`. Lazy-init on first message. Switch active log on NPC select — do NOT clear other logs.
**Key detail:** The dialogue background thread returns responses after the player may have switched NPC. Store `_pending_npc_id` (the NPC the request was sent for) separately from `_active_npc_id` (the NPC currently on screen). Route the response to `_logs[_pending_npc_id]`, not to the currently selected NPC's log.
**Checklist:**
1. Replace `self._log: ScrollableLog` with `self._logs: dict[str, ScrollableLog] = {}`.
2. Add `self._pending_npc_id: str | None = None` to `__init__`.
3. Add `_get_log(npc_id) -> ScrollableLog` helper (lazy init).
4. In `_submit_dialogue`: set `self._pending_npc_id = npc_id` before launch.
5. In `_poll_response_queue`: route to `self._get_log(pending_npc_id)`.
6. In `_handle_event`: route scroll events to `self._get_log(active_npc_id).handle_event`.
7. Add a header strip showing "Talking to [NPC name]" above the log area.
**Reuse when:** Phase 4 UI work, any new demo scenario with per-NPC conversation tracking.


## pygame-word-wrap
**Identified:** 2026-05-28 (S3.1)
**Pattern:** `pygame.font.Font.render()` renders text as a single surface with no automatic word-wrap. Use `_wrap_text(font, text, max_px)` to split text into lines before rendering.
**Implementation:**
```python
def _wrap_text(font, text, max_width):
    words = text.split()
    if not words:
        return [""]
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines if lines else [""]
```
**ScrollableLog integration:**
- Use pixel-based scroll: `_scroll_px: int = 0` (not line-count).
- Mouse wheel: `_scroll_px = max(0, _scroll_px - event.y * font.get_linesize())`.
- In `draw()`: pre-compute wrapped lines per message, compute cumulative heights, skip out-of-viewport entries.
- `entry_h = label_h + len(lines) * line_h + 6` (variable per message).
**Reuse when:** Any pygame widget that displays multi-sentence text (dialogue log, knowledge sidebar in S3.3, quest log in Phase 4).


## pygame-diff-rendering
**Identified:** 2026-05-28 (S3.3)
**Pattern:** Two-column side-by-side diff widget in pygame for comparing "what was believed" vs "what actually happened".
**Implementation:**
- Equal-width columns separated by a 1px `_CLR_DIVIDER` vertical line.
- Field-level colour coding: `_CLR_WHITE` (match/ground truth), `_CLR_AMBER` (distorted), `_CLR_DIM` (missing/absent).
- Classification via `_classify_row(edge, event) -> "matching" | "distorted" | "missing"`:
  - `distortion_level == 0` → `"matching"`
  - `distortion_level > 0` and `distorted_summary is None` → `"missing"`
  - `distortion_level > 0` and `distorted_summary is not None` → `"distorted"`
- Pixel-based scroll: `_scroll_px: int = 0`, same pattern as `ScrollableLog`.
- Render into a `surface.subsurface(clip_rect)` to avoid drawing outside the panel bounds.
- Reuse `_wrap_text(font, text, max_col_w)` from `demo_game.ui.widgets` for all text in both columns.
- Pre-compute row heights before drawing (`_build_row`) so total scroll height is known.
**Key files:** `demo_game/ui/knowledge_sidebar.py`, `demo_game/knowledge_sidebar_fetcher.py`
**Reuse when:** Phase 4 quest log comparison (quest expected vs. actual outcome), inventory before/after
display, any before/after or NPC-vs-ground-truth comparison in a pygame panel.


## pygame-tab-panel-toggle
**Identified:** 2026-05-28 (S3.4)
**Pattern:** Switching between two right-panel views with a single key in pygame.
**Implementation:**
1. Add `self._show_<panel>: bool = False` state flag in `__init__`.
2. In `_handle_key`: `elif key == pygame.K_TAB: self._show_<panel> = not self._show_<panel>`.
3. In `_handle_event`: exclusive scroll routing — `if self._show_<panel>: widget.handle_event(event) elif ...: other.handle_event(event)`. Never additive (see DEC-027).
4. Add `_draw_right_panel_header(rect, label)` helper: 24px strip at `rect.topleft`, `_CLR_NPC_HEADER_BG` fill, amber label via `_CLR_NPC_HEADER_TEXT`.
5. In `_draw_right_panel`: branch on flag, call header helper first, then pass `content_rect = Rect(rect.x, rect.y + PANEL_HEADER_H, rect.width, rect.height - PANEL_HEADER_H)` to the active widget.
6. Blit oversized surfaces (e.g. GraphPoller sized to `_RIGHT_H`) at `(rect.x, rect.y + PANEL_HEADER_H)` — nav bar drawn after covers overflow cleanly.
**Key files:** `demo_game/ui/game_window.py`
**Reuse when:** Phase 4 adds a quest log panel, inventory view, or any second panel that shares the right-panel slot. Also applies to any pygame panel-swap keybinding pattern.


## eval-harness
**Identified:** 2026-05-26 (R1.1)
**Pattern:** YAML-driven eval cases + synchronous runner + matcher library + markdown reports.
**Key files:** `evals/runner.py`, `evals/matchers.py`, `evals/cases/*.yaml`, `evals/report.py`
**Reuse when:** Adding new matcher kinds, new case categories, wiring the harness to CI, or onboarding to the eval structure from a cold start.
**Updated (R1.2):** `keyword_none` matcher added — mirrors `keyword_any`/`keyword_all`; checks that forbidden substrings do NOT appear in `npc_response`. Symmetric design: same field path, same case-insensitive substring logic. Use for behavioral constraint tests (voice bleed, role bleed, knowledge hallucination, self-incrimination).
