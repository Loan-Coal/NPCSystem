# FIX-SEV-18 — Covert-event summary template: move to `prompts/` only if LLM-bound

**Severity:** LOW · **Decision:** DEC-116 (trace, move only if it reaches the LLM)

## Problem
`covert_event_factory` builds the Event `summary` field from a Python string template. The
no-prompt-strings-outside-`prompts/` rule applies only to text that reaches the LLM. DEC-116: trace whether
`event.summary` enters LLM context; move the template to YAML iff it does, else document it as graph data.

## Current shape (verify against code now)
- `src/npc_engine/engines/scheming/covert_event_factory.py:33` — `_COVERT_SUMMARY_TEMPLATE` (a `str.format`
  template) used to build the `summary` of a covert Event node.

## Steps
1. **Trace:** does an Event's `summary` field get serialized into LLM context? Check the retrieval/context
   path — `retrieval/subgraph_retriever.py` (`_flatten_event_row`, event serialization), `retrieval/context_builder.py`,
   and any `prompt_builder` event rendering. Grep for `summary` / `event.get("summary")` / event flattening.
2. **If LLM-bound:** move the template to `src/npc_engine/prompts/scheming/<file>.yaml`, load it via the
   existing YAML loader, and format at call time. Add a loader test.
3. **If NOT LLM-bound:** add an in-file comment on `_COVERT_SUMMARY_TEMPLATE` stating it builds a graph
   data field only (never sent to an LLM), so future readers don't re-flag it. Record the trace result here.

## Verification
- If moved: `pytest tests/ -k "covert or scheming" -q` (template loads + formats). 
- Either way: `make check` (check-rules / no-prompt-strings gate stays green).

## Blast radius
`covert_event_factory.py` (+ `prompts/scheming/` and a loader if moved). Small.
