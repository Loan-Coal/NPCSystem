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
- No migration path from EVAL-P12 — the trigger condition and migration cost are in the
  **Migration cost** and **Implementation trigger** sections below.

---

## Cost model

Wall-clock time for a run of `S` scenarios at `k` repetitions with the EVAL-P12 adapter design:

```
T_total ≈ k × Σ_s T_rep(s)  +  S × k × T_reset

T_rep(s) = n_llm(s) × T_llm  +  n_clock(s) × T_clock  +  n_rest(s) × T_rest
T_reset  = 54 ms  (median over 5 consecutive resets, EVAL-P12.1, commit c0c3836)
```

**Per-scenario call budget (per repetition):**

| Scenario | n_llm | n_clock (`/v1/clock/advance`) | n_rest | Notes |
|---|---|---|---|---|
| gossip_chain | 0 | 0 | 5 | Uses `/v1/admin/batch/gossip_tick`, not `/v1/clock/advance` |
| grief_persistence | 2 | 0 | 3 | 2 `/v1/dialogue` calls |
| reputation_drift | 0 | 0 | 7 | Pure graph REST |
| memory_consolidation | 6 | 0 | 4 | 6 `/v1/dialogue` calls |
| time_passage | 0 | 33 | 2 | 5 time-of-day + 28 day advances (steady-state under PARTIAL fidelity: day resets to 1 each rep, so (28−1)%28+1=28 day advances every time) |
| mood_contagion | 0 | 3 | 7 | 3 `/v1/clock/advance` calls |
| **Totals** | **8** | **36** | **28** | Per rep-set (one pass through all 6 scenarios) |

**Calibrated steady-state latencies:**

| Call type | Symbol | Calibrated value | Source |
|---|---|---|---|
| `/v1/dialogue` (LLM inference) | T_llm | ~18 s | Fit to EVAL-P12.4 corrected run |
| `/v1/clock/advance` (tick engine cascade) | T_clock | ~4 s | Fit to EVAL-P12.4 corrected run |
| Graph REST (reads, writes) | T_rest | ~0.5 s | Fit to EVAL-P12.4 corrected run |
| `preconditions.reset_world` | T_reset | 54 ms | Directly measured, EVAL-P12.1 |

**Model prediction vs. EVAL-P12.4 measured:**

```
T_rep_total = 8×18 + 36×4 + 28×0.5
            = 144 + 144 + 14
            = 302 s  (one pass through all 6 scenarios)

T_total = k × T_rep_total + S × k × T_reset
        = 3 × 302 + 18 × 0.054
        = 906 + ~1
        ≈ 907 s ≈ 15.1 min
```

Measured (EVAL-P12.4 corrected re-run): **~15 min** (900 s).
Error: **0.8%** — within the 25% validation window. ✓

**Variance term — the 63 s/call observation:**

The first EVAL-P12.4 pass measured `POST /v1/clock/advance` at ~63 s/call under transient server load.
At that latency:

```
T_rep_total = 8×18 + 36×63 + 28×0.5
            = 144 + 2,268 + 14
            = 2,426 s / rep-set

T_total ≈ 3 × 2,426 ≈ 7,278 s ≈ 121 min
```

Measured first pass: **~121 min**. The model accounts for the full observed time. ✓

A 4× load swing (T_clock = 16 s) instead of the 16× peak would produce:
```
T_total = 3 × (8×18 + 36×16 + 28×0.5) = 3 × 734 ≈ 2,202 s ≈ 37 min
```

A go/no-go decision based on the 15-minute figure should therefore carry ±2× as its practical
uncertainty band on any endpoint that cascades through tick engines. The 25% window above is
the model validation threshold, not a scheduling guarantee.

---

## Migration cost

What EVAL-P12's existing runner infrastructure gives up to adopt the v2 schema:

| EVAL-P12 asset | Migration action | Effort |
|---|---|---|
| `evals/sequence_runner.py` | Rewrite `run_sequence` to produce `Repetition` + `Turn` objects instead of a bare `bool` | Medium — new return contract, same control flow |
| `evals/sequence_rates.py` | Rewrite `SequenceStat` assembly to read from `SequenceRun.repetitions` | Small — structural change only |
| `evals/sequence_fidelity.py` | No change needed — already reads `ResetReceipt`; v2 carries one per `Repetition` | None |
| `evals/sequence_order_effect.py` | No change — reads `list[bool]` from stats; source changes but shape does not | None |
| `evals/scenario_adapters.py`, `evals/scenario_adapters_extra.py` | Rewrite every adapter from `() -> bool` to `() -> list[Turn]` | High — every adapter, every call site; irreversible once started |
| Per-turn `retrieved_context` | Add retrieval reader injection into every adapter; no injection mechanism exists today | High — new infrastructure |
| Per-turn judging | Wire a judge to each `Turn`; no per-turn binding layer exists today | High — new infrastructure |

The scenario adapters rewrite is the load-bearing cost: every adapter must be audited to record
what it currently discards, with no way to backfill from the existing `bool` return.

---

## Implementation trigger

Build the v2 runner when **any** of the following conditions is first met — not before:

1. **Per-turn retrieval capture** — a scenario needs to record what context was retrieved on
   each turn, not just the final outcome. (`Turn.retrieved_context` has no equivalent in
   the EVAL-P12 `bool` schema; the data is gone after the call returns.)

2. **Per-turn judging** — a scenario's pass/fail depends on judging individual turns, not
   the outcome of the whole repetition.

3. **Branching** — a scenario has more than one possible dialogue path and the branch taken
   must be recorded, not collapsed into a single bool.

4. **Scale** — more than 10 promoted scenarios, at which point maintaining
   `scenario_adapters.py` as a hand-authored `() -> bool` registry becomes error-prone.

Building before any condition is met means maintaining two runners in parallel for a scenario
set that does not yet require the second one.
