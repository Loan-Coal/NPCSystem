# Patterns Log

Reusable code and design patterns discovered during development. A pattern is
worth recording when it has been applied at least twice and would be worth
applying again.

Rules:
- Append-only.
- Each pattern has a short name, a "when to use" description, a "why" justification,
  and a minimal runnable example.
- If a pattern is superseded, mark it as `[SUPERSEDED]` and link to the replacement.
  Do not delete.

---

## Pattern: Frozen Exception Dataclasses
**When to use:** Every domain exception in this codebase.
**Why:** Exceptions are value objects — they carry diagnostic context and are never modified after construction. `frozen=True` enforces STRUCT-06 (immutability) and enables hashing/equality comparisons in test assertions.
**Example:**
```python
from dataclasses import dataclass
from utils.errors import StructuredNPCSystemError

@dataclass(frozen=True)
class MyServiceError(StructuredNPCSystemError):
    """Raised when X violates Y."""
    code: str
    detail: str
```
**First applied in:** utils (service #1)

---

## Pattern: Typed route exit contract via `OkEnvelope[T]`

Every HTTP route declares `response_model=OkEnvelope[T]` so `/openapi.json` emits a
real body schema (generated clients get stubs, not empty `{}`). The runtime path is
unchanged — handlers still return `ok_response(...)` (a plain dict); FastAPI validates
it against the envelope on the way out.

```python
from npc_engine.api.route_helpers import OkEnvelope, ok_response

@router.get("/{id}", response_model=OkEnvelope[dict[str, Any]])
async def get_thing(id: str) -> dict[str, Any]:
    return ok_response({"thing_id": id})   # data is a dict
```

- `data` is a dict → `OkEnvelope[dict[str, Any]]`; a list → `OkEnvelope[list[dict[str, Any]]]`.
- Routes that return a **bare** (non-enveloped) dict use `response_model=dict[str, Any]`.
- Dynamic registry routes (`graph`, `graph_admin`) stay `dict[str, Any]` (DEC-088).
- `tests/unit/test_route_response_model_contract.py` enforces "no route missing `response_model`".

**First applied in:** api (Phase 20, S20.1–S20.6) — swept across ~125 routes.

---

## Anti-Pattern: Common Mistakes to Avoid

A condensed reference of recurring mistakes observed during development. Each row
shows the wrong pattern and the correct replacement.

| Mistake | Correct Pattern |
|---|---|
| `session.run(f"MATCH ... '{npc_id}'")` | `session.run(CYPHER_CONST, npc_id=npc_id)` — parameterized Cypher only; f-strings in queries are a SQL-injection-equivalent |
| `context["items"].append(x)` | `context.model_copy(update={"items": [*context.items, x]})` — all Pydantic models are `frozen=True`; never mutate in-place |
| `from engines.llm.mistral_adapter import MistralAdapter` inside an engine | Import `LLMClientProtocol` only — depend on the protocol, not the concrete adapter |
| `except Exception: pass` | `except SpecificError as e: logger.error(...); raise` — never swallow exceptions silently |
| `random.random()` inside gossip distortion | Use seeded deterministic computation — gossip must be reproducible for the same inputs |
| `llm_response["npc_response"]` | `parsed_response.npc_response` — always parse LLM output into a Pydantic model before accessing fields |
| Module-level `db = Neo4jDriver(...)` | Inject `driver` via constructor or FastAPI `Depends` — no global mutable state |
| Files > 300 lines | Extract to helper files immediately — see CLAUDE.md § "Files" |
| `print(f"Prompt: {prompt}")` | `if settings.LOG_LLM_PROMPTS and settings.ENV == "dev": logger.debug(...)` |
| Relative imports beyond one level (`from ..x import y`) | `from npc_engine.x import y` — one level max (`from .x import y` is fine) |

---

## Pattern: Force UTF-8 on stdout/stderr in any CLI that prints report glyphs
**When to use:** Every `scripts/` or `evals/` entry point whose output can contain non-ASCII —
κ, ≥, →, ✓, ⚠️, an em-dash. On this project that is most of them, because the reports quote
statistics.
**Why:** A Windows console defaults to cp1252. Printing `κ` raises `UnicodeEncodeError` *at print
time*, i.e. after the work is done — `calibration.py` crashed this way after a completed
adjudication pass and lost the summary. The failure is worse than cosmetic in a gate: a checker
that exits non-zero because of a glyph reports a red gate for a reason that has nothing to do
with what it checks, and in the overnight loop that counts toward `MAX_CONSECUTIVE_RED_GATES`.
`errors="replace"` keeps output flowing on a terminal that still cannot render the character.
Call it first thing in `main()`, before argument parsing, so even a usage error is printable.
**Example:**
```python
def _force_utf8_streams() -> None:
    """Reconfigure stdout/stderr to UTF-8 so a report glyph cannot crash the run."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass  # Non-reconfigurable stream (pipe/pytest capture) — leave as-is.
```
**Related trap:** the reverse mistake has also been made here — a cp1252 *console* rendering of a
correct UTF-8 file (`topic �`) was diagnosed as file corruption and nearly "fixed", which would
have corrupted `prompts/eval/refusal_judge.yaml`. See ISSUE-141's correction. Verify with
`python -c "open(p,'rb').read().decode('utf-8')"` before believing your terminal.
**First applied in:** `evals/__main__.py`; reused in `scripts/check_human_gates.py` (DEC-164).

---

## Pattern: Out-collector list for per-tier observations across a degradation ladder
**When to use:** A handler that may run the same inner step more than once (the dialogue
degradation ladder runs `full`, then `graph_only`, then canned) and needs to report something
the inner step observed, when that something is not part of the inner step's return contract.
Applied twice in `DialogueHandler.handle`: `memory_ids_out` (ISSUE-107) and `receipt_out`
(DEC-195).
**Why:** The inner step's return type is the response the ladder selects between, and
`execute_with_degradation` picks exactly one of them — so anything appended to that return
type would have to be threaded through the fallback machinery and would still be lost when the
canned tier answers. A caller-owned list, passed down and appended to, survives every tier and
records *how many times the step ran*, which is itself the information you need: for
`memory_ids_out` the union is wanted, for `receipt_out` only the **last** entry is, because
that is the assembly that produced the served reply. Keep the "which entry" decision in a named
helper next to the response assembly (`_selected_receipt`), never inline — the two collectors
above want different answers from the same shape, and inlining hides that.
**Example:**
```python
receipts_captured: list[ContextReceipt] = []

async def _full() -> DialogueResponse:
    return await self._run_llm_pipeline(..., receipt_out=receipts_captured)

# inside _run_llm_pipeline, after the inner step observes it:
if receipt_out is not None and receipt is not None:
    receipt_out.append(receipt)

# at response assembly:
final = parsed.model_copy(update={
    "context_receipt": _selected_receipt(request, receipts_captured),
})
```

---

## Pattern: Capture on the module logger, never `caplog`, when asserting a log line
**When to use:** Any test that asserts an `npc_engine.*` module actually logged something.
**Why:** `utils/logging.py:83` sets `root_logger.propagate = False` on the `npc_engine` logger.
`caplog` attaches its handler to the true root, so once **any** earlier test in the session calls
`configure_logging()`, records never reach it. A `caplog` assertion therefore passes in isolation
and fails in a full run — it is order-dependent, and it fails *open*: the log line can be deleted
and the test still passes if it happens to run early. Measured 2026-09-02: two new seed-logging
tests passed alone and under `pytest tests/unit/engines`, then failed under `pytest tests/`,
which is what `make check` runs.
**Example:**
```python
captured: list[str] = []

class _Capture(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        captured.append(record.getMessage())

handler = _Capture(level=logging.DEBUG)
previous_level = mod.LOGGER.level
mod.LOGGER.addHandler(handler)
mod.LOGGER.setLevel(logging.DEBUG)
try:
    ...                       # drive the code under test
finally:
    mod.LOGGER.removeHandler(handler)
    mod.LOGGER.setLevel(previous_level)

logs = [m for m in captured if "event_sampling_rng" in m]
assert logs, "expected an event_sampling_rng debug log line"
```
Restore the level in a `finally` — leaving the module logger at DEBUG leaks into later tests.
**Applied in:** `tests/unit/conformance/test_sev22_rng_determinism.py:80`,
`tests/unit/llm/test_ollama_prompt_eval_logging.py:91`,
`tests/unit/engines/test_event_rng_seed_logging.py` (R3.4c).

---

## Pattern: an environment-mode test skips by default and a per-gate env switch turns that skip into a failure

A test that can only be measured in one runtime mode — services frozen, services ticking,
a real LLM up — has two bad default behaviours. If it **fails** when the mode is absent, it
becomes a permanent entry in the failing baseline and stops carrying information. If it
**skips**, the gate that is supposed to enforce it passes vacuously and nobody notices the
check stopped running.

Do both, selected by the caller. The test skips when the mode is absent, so the ordinary
suite stays clean, and reads an env var that the dedicated gate sets, which converts that
same skip into an explicit failure naming the remedy.

```python
REQUIRE_FROZEN_ENV = "REQUIRE_FROZEN_CORPUS"

if autopilot_on:
    message = "tick autopilot is ENABLED ... Bring the stack up with `make app-frozen`."
    if os.getenv(REQUIRE_FROZEN_ENV) == "1":
        pytest.fail(message)
    pytest.skip(message)
```

```makefile
check-corpus-frozen:
	REQUIRE_FROZEN_CORPUS=1 $(PYTHON) -m pytest tests/integration/test_....py -q
```

The message must name the command that establishes the mode, because whoever trips the gate
is by definition in the wrong mode and needs to be told how to get into the right one.

This is the same reasoning as `check-integration-baseline`'s executed-test floor: a gate must
be able to distinguish "the property holds" from "the check did not run". Use it whenever two
gates have **opposite** preconditions — `check-corpus-frozen` needs the tick autopilot off and
`check-corpus-quiescent` needs it on, so one pytest target could never serve both, and each
test skips in the other's mode.

**Applied in:** `tests/integration/test_eval_world_corpus_integration.py` — `REQUIRE_FROZEN_CORPUS`
(`make check-corpus-frozen`) and `REQUIRE_TICKING_CORPUS` (`make check-corpus-quiescent`), DEC-259.

---

## Pattern: import a sibling module's private helper instead of re-deriving its logic

Two modules sometimes need the exact same small piece of logic that belongs conceptually to
one of them (a predicate, a count, a classification rule) but is not yet used by 2+ callers
in a way that would justify promoting it to a public, documented API (the DIP threshold).
Re-deriving it in the second module is how two "the same rule" implementations quietly drift
apart the first time either one is edited.

Import the leading-underscore name directly, with a `# noqa: E402`-style import if needed and
a comment at the use site naming why it's safe: the function is a small, stable, single-purpose
helper whose behaviour the second module depends on staying in sync with the first's.

```python
# deterministic_records.py reusing anti_hallucination_runner's grounded-check predicate:
from anti_hallucination_runner import _is_grounded

# label_export_yield.py reusing label_adequacy's floor helpers, so a projected ceiling
# and the floor it is projected against can never silently diverge in what they count:
from label_adequacy import MIN_CASE_CLUSTERS, MIN_MINORITY_LABELS, _clean_adjudicated, _minority_count
```

This is a deliberate exception to "no abstraction until 2+ implementors or 3+ callers" — it
is not an abstraction being added, it is an abstraction (the private function) being reused
without inventing a second one. Promote the helper to public API instead once a third module
needs it, or once its contract needs to be documented for consumers outside its home module.

**Applied in:** `evals/deterministic_records.py` → `anti_hallucination_runner._is_grounded`
(EVAL-P6.1); `evals/label_export_yield.py` → `evals/label_adequacy.py`'s floor constants and
`_minority_count`/`_clean_adjudicated` (DEC-262).

---

## Pattern: per-file `*_FACTORIES` dict, merged at one composition point via `**`-spread

**When to use:** A registry (scenario adapters, engine probes, scorers, …) that must grow by
adding a new file, never by editing a shared file's body. One module owns the composition
point; every implementation module exports its own small `dict[str, Factory]` constant under
a name ending `_FACTORIES`, and the composition point merges them with `**` spreads.
**Why:** Satisfies OCP (CLAUDE.md: "new backends … arrive as new files") without a plugin/
auto-discovery mechanism — the composition point stays one plain dict literal, readable in
full, and a new module's entry is a one-line addition there, never a change to an existing
module's body. Keeps DIP's constructor-injection discipline: nothing is registered by import
side effect (which would make load order matter); every dict is an explicit, inspectable
value, and the merge order can never mask a duplicate key. A key collision aborts import
loudly at the merge point rather than one factory silently shadowing another.
**Example:**
```python
# probe_gossip.py
GOSSIP_PROBE_FACTORIES: dict[str, GossipProbeFactory] = {"gossip": _make_gossip_probe}

# probe_events.py
EVENTS_PROBE_FACTORIES: dict[str, EventsProbeFactory] = {"events": _make_events_probe}

# probe_runner.py — the one composition point:
from probe_events import EVENTS_PROBE_FACTORIES
from probe_gossip import GOSSIP_PROBE_FACTORIES

PROBE_FACTORIES: dict[str, ProbeFactory] = {
    **GOSSIP_PROBE_FACTORIES,
    **EVENTS_PROBE_FACTORIES,
}
```
**First applied in:** `evals/scenario_adapters.py` merging
`scenario_adapters_extra.EXTRA_SCENARIO_ADAPTER_FACTORIES` into
`SCENARIO_ADAPTER_FACTORIES` (EVAL-P12.4). **Applied again in:** `evals/probe_runner.py`
merging all 6 `probe_<engine>.py` modules' `*_PROBE_FACTORIES` dicts into `PROBE_FACTORIES`
(measurement-remediation Phase 4, DEC-271).
