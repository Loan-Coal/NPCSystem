# Prompt Inventory

Read-only pass over all engines. Below are every hardcoded prompt string, template, and response blob found in the codebase, with file:line references and proposed YAML target names.

**Phase 2 extraction is blocked until you review and approve this list.**

---

## Inventory

### 1. Main dialogue prompt
**File:** `npc_engine/engines/dialogue/prompt_builder.py:12–25`

**Type:** LLM prompt template (primary, hot path)

**Current code:**
```python
PROMPT_VERSION = "stage_b_v1.0"

def build_dialogue_prompt(request: DialogueRequest, serialized_context: str) -> str:
    return (
        f"PROMPT_VERSION={PROMPT_VERSION}\n"
        "INSTRUCTIONS: Respond with JSON matching required schema only.\n"
        f"NPC_ID={request.npc_id}\n"
        f"PLAYER_ID={request.player_id}\n"
        f"CONTEXT={serialized_context}\n"
        f"PLAYER_MESSAGE={request.player_message}\n"
    )
```

**Placeholders in use:** `npc_id`, `player_id`, `serialized_context`, `player_message`

**Proposed YAML:** `prompts/dialogue/dialogue_main_v1.yaml`
```yaml
name: dialogue_main
version: 1
description: Main structured-output dialogue prompt sent to the LLM.
schema_version: "stage_b_v1.0"
template: |
  PROMPT_VERSION={schema_version}
  INSTRUCTIONS: Respond with JSON matching required schema only.
  NPC_ID={npc_id}
  PLAYER_ID={player_id}
  CONTEXT={serialized_context}
  PLAYER_MESSAGE={player_message}
required_placeholders:
  - npc_id
  - player_id
  - serialized_context
  - player_message
output_schema_ref: dialogue_response_v1
```

**Notes:** `schema_version` should come from the YAML's own `schema_version` field, not from a separate Python constant. Caller passes `npc_id`, `player_id`, `serialized_context`, `player_message`.

---

### 2. Ollama schema injection template
**File:** `npc_engine/engines/llm/ollama_adapter.py:62`

**Type:** LLM protocol glue (appended to any prompt before sending to Ollama)

**Current code:**
```python
"prompt": f"{prompt}\n\nRequired JSON schema:\n{json.dumps(schema, ensure_ascii=True)}",
```

**Proposed YAML:** `prompts/llm/schema_injection_v1.yaml`
```yaml
name: schema_injection
version: 1
description: Appends JSON schema requirement to any structured-output prompt for Ollama.
schema_version: "1.0"
template: |
  {prompt}

  Required JSON schema:
  {schema_json}
required_placeholders:
  - prompt
  - schema_json
output_schema_ref: null
```

**Notes:** This is a protocol-level wrapper, not a content prompt. It wraps the main dialogue prompt. Extraction here means the adapter calls `prompt_loader.get_prompt("schema_injection", 1).render(prompt=..., schema_json=...)` instead of the inline f-string.

---

### 3. Gossip distortion templates
**File:** `npc_engine/engines/gossip/gossip_distort.py:44–49`

**Type:** Text transformation templates (not LLM prompts — deterministic string transforms)

**Current code:**
```python
def _apply_template(summary: str, distortion_type: str) -> str:
    if distortion_type == "omission":
        words = summary.split()
        return " ".join(words[: max(1, len(words) // 2)])
    if distortion_type == "exaggeration":
        return f"It was utterly catastrophic: {summary}"
    if distortion_type == "role_swap":
        return f"They say the opposite happened: {summary}"
    if distortion_type == "timeline_shift":
        return f"Long ago, {summary}"
    return summary
```

**Proposed YAML:** `prompts/gossip/distortion_templates_v1.yaml`
```yaml
name: distortion_templates
version: 1
description: String templates for gossip distortion types applied to event summaries.
schema_version: "1.0"
templates:
  exaggeration: "It was utterly catastrophic: {summary}"
  role_swap: "They say the opposite happened: {summary}"
  timeline_shift: "Long ago, {summary}"
required_placeholders:
  - summary
output_schema_ref: null
```

**Notes:** `omission` is algorithmic (truncation), not a string template — it stays in code. The other three are pure string templates. If extracted, `_apply_template()` loads the template map from the YAML and does `template.format(summary=summary)`. **Low priority for extraction** — these are 3 short strings with no content ambiguity and no LLM involvement. Worth extracting for consistency, but not urgent.

---

### 4. Fallback dialogue responses
**File:** `npc_engine/data/fallback_responses.json`

**Type:** Canned response data (already externalized to JSON, not hardcoded Python)

**Current structure:** Per-archetype lists of fallback strings (`merchant`, `guard`, `elder`, `default`).

**Proposed target:** `prompts/canned/<archetype>.yaml` — one file per archetype (covered by Task 7, graceful degradation). Not strictly needed in Phase 2 since this is already in a separate file. **Defer to Task 7.**

---

## Scope Decision Needed

**Before Phase 2, please confirm:**

1. **Should I extract items 1 and 2** (dialogue prompt + Ollama schema injection)?
   - These are the real LLM prompts. Extraction lets you edit them without touching Python.

2. **Should I extract item 3** (gossip distortion templates)?
   - These are deterministic string templates, not LLM prompts. Extraction is optional.

3. **Should I skip item 4** (fallback JSON) and handle it in Task 7?
   - Recommendation: yes, defer to Task 7.

4. **Should the schema injection (item 2) live in `prompts/llm/` or be treated as Ollama-adapter-internal?**
   - If all adapters eventually need schema injection, `prompts/llm/` makes sense. If it's Ollama-specific, it can stay inline.

---

## Spotted Improvements (NOT changing content — listing for `proposals/prompt_improvements.md`)

- The dialogue prompt has no NPC `archetype`, `biography`, or `current_mood` in the template itself — those are embedded inside `serialized_context`. The template currently has no visible structure for reviewers. A future improvement could add a `WORLD_STATE=` line for readability.
- `INSTRUCTIONS: Respond with JSON matching required schema only.` is minimal. A more detailed instruction with example JSON would improve structured output reliability.
- The Ollama schema injection appends the schema *after* the prompt. For some models, prepending the schema or embedding it inline performs better. Worth A/B testing.
- Distortion templates have no `{severity}` variable — exaggeration level is uniform regardless of event severity.
