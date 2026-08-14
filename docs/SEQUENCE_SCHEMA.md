# Sequence Transcript Schema (v2)

**Phase:** EVAL-P14.1  
**Status:** Design complete — implementation is a separate programme.  
**Frozen at:** the commit that introduced `evals/sequence_records.py`.

---

## Why this schema exists

EVAL-P12 bends the single-turn record shape (`GenerationRecord`) to fit multi-turn
sequences by running each scenario k times and aggregating into a `CaseStat`. That
bend has a known breaking point: when a scenario needs **per-turn retrieval capture**,
**per-turn judging**, or **branching**, the single-turn record shape cannot accommodate
it without lossy workarounds.

This schema is designed now, while the EVAL-P12 constraints are fresh, so the later
implementation session does not have to re-derive the decisions.

---

## Models

All models are **frozen Pydantic v2** (`ConfigDict(frozen=True)`). Once created,
instances are immutable. No raw `dict` crosses a module boundary.

### `SequenceRun`

The top-level record for one k-repetition run of one scenario.

| Field | Type | Description |
|---|---|---|
| `run_id` | `str` | Unique run identifier (e.g. `run_20260810_001`). |
| `scenario_id` | `str` | Canonical scenario identifier (e.g. `gossip_chain`). |
| `k` | `int` | Number of repetitions requested. |
| `config` | `SequenceRunConfig` | Reproducibility snapshot. |
| `repetitions` | `tuple[Repetition, ...]` | One per run, in execution order. |

### `SequenceRunConfig`

Reproducibility snapshot. Carries only what the harness can populate without
external intervention.

| Field | Type | Description |
|---|---|---|
| `generation_model` | `str` | LLM model name used for NPC responses. |
| `git_sha` | `str` | Short commit hash at run start. |

### `Repetition`

One full run of the multi-turn scenario within the k-set.

| Field | Type | Description |
|---|---|---|
| `index` | `int` | Zero-based position within the k-set. |
| `reset_receipt` | `ResetReceipt` | **Required.** Evidence of what was cleared. |
| `turns` | `tuple[Turn, ...]` | Ordered turns for this repetition. |

`reset_receipt` is **required** (no default). A `Repetition` without a receipt
cannot be constructed — `ValidationError` is raised. This is the enforcement
mechanism for the independence evidence requirement: if the harness cannot
produce a receipt, it cannot claim the repetition was independent.

### `Turn`

One message-response exchange.

| Field | Type | Description |
|---|---|---|
| `index` | `int` | Zero-based position within the repetition. |
| `actor` | `str` | Player id or NPC id who sent the message. |
| `message` | `str` | Input message sent to the NPC. |
| `response` | `str` | NPC reply. |
| `world_epoch` | `int` | World state epoch at turn time. |
| `tick` | `int` | Engine tick at turn time. |
| `retrieved_context` | `tuple[RetrievedItem, ...]` | Per-turn retrieval capture. |
| `duration_ms` | `int` | Wall-clock milliseconds for the engine call. |

### `ResetReceipt`

Evidence of what the world reset actually cleared before one repetition.

| Field | Type | Description |
|---|---|---|
| `cleared` | `tuple[str, ...]` | Component labels fully reset. |
| `surviving` | `tuple[str, ...]` | State items that survived (may correlate repeats). |
| `duration_ms` | `int` | Wall-clock milliseconds for the reset. |

`cleared` and `surviving` come from the fidelity measurement in EVAL-P12.1. The
distinction is load-bearing: if `surviving` is non-empty, per-repetition Wilson CIs
are not valid (the repeats are not independent). The SEQUENCE_STATS_POLICY (EVAL-P14.2)
codifies which statistics are permitted under which reset fidelity.

---

## What v1 (EVAL-P12) cannot do

| Capability | v1 (single-turn shape) | v2 (this schema) |
|---|---|---|
| Per-turn retrieval capture | Approximation only (re-run with `session_turns=[]`) | Exact per-turn `retrieved_context` field |
| Per-turn judging | Not possible — judge operates on one reply | `Turn` is the unit; judge can bind to any turn |
| Independence evidence | Assumed — reset cost only, no content audit | `ResetReceipt` on every `Repetition` |
| Branching scenarios | No model for branch points | Can be represented as multiple `Turn` lists per `Repetition` in a future extension |

---

## What this schema does NOT contain

- No scenario script or expected-output fields — those live in case files, not transcripts.
- No `seed` field *on a `Turn`* — the run seed is recorded once in `RunConfig.seed` and every
  `Repetition` inherits it. As of EVAL-P20.0 / DEC-176 that seed is real: the protocol carries it,
  `ollama_adapter` sets `options.seed`, and the dialogue engine forwards it. It reproduces text only
  partially (62.5% measured, not the ≥95% hoped for) — see DEC-176 before relying on it.
- No judge verdict — that is a separate record bound to a `Turn` in the judging phase.
- No migration path from EVAL-P12 — the trigger condition and migration cost are specified
  in EVAL-P14.3 (blocked on EVAL-P12.4's measured run time).

---

## Implementation trigger

Do **not** start building the v2 runner until the trigger condition from EVAL-P14.3 is
met. Building it early means maintaining two runners in parallel before there is a
scenario that requires the second one.
