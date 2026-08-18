# Brief: ISSUE-165 (tick contract) and EVAL-P20.0's ≥95% reproduction gate

**Written:** 2026-08-17, for whoever picks up the "fix before regen #1" work.
**Purpose:** These two problems get talked about together (both surfaced in the same
`EVAL-P20.0` investigation) but they are **independent** — fixing one does not move the
other. This brief separates them, corrects a stale cost estimate still sitting in
`ROADMAP.md`, and ends with a plain recommendation.

**TL;DR, read this first:** the "≥95% reproduction gate NOT MET" finding sounds like an
open bug you can fix. It mostly isn't — it's a measured, structural property of running
this LLM at `max_tokens=512` on this runtime (DEC-176), and the concrete pain it
threatened (mass human-label loss on every regeneration) has **already been resolved**
by a separate, already-landed change (DEC-181/`ISSUE-168`, fixed 2026-08-16). Live-checked
right now: `python scripts/check_label_survival.py` reports **393/393 survive, 0 drift, 0
orphaned**. `ISSUE-165` is real and still open, but it is a game-simulation correctness
bug, not an eval-reproduction blocker — fixing it will not change the 62.5% number.

---

## Part 1 — EVAL-P20.0: the ≥95% seed-reproduction gate (DEC-176)

### What was measured

Gate: two generations of ≥20 records at the same seed reproducing ≥95% byte-identical
`npc_response`. Measured via `scripts/seed_reproduction_probe.py` (`make seed-probe`)
over 24 `case_neg_*` cases (145 records / 24 independent LLM draws), app container
restarted between runs.

| Stage | rate_calls |
|---|---|
| No seed, no fix (pre-existing baseline) | 19.0% |
| Seed only | 25.0% |
| Seed + wall-clock stripped from prompts + state reset | **62.5%** (15/24) |
| Gate | ≥95% — **NOT MET** |

### Root cause — and why it is not really a "bug"

Two contributing causes were found. **Both are already fixed or already understood not
to matter:**

1. **Wall-clock values were leaking into prompt content** (`context_builder`'s Tier-0
   dump had no field stripping; `NON_PROMPT_NODE_FIELDS` existed but wasn't applied to
   `last_updated_at`/`emotion_updated_at_tick`/`expires_at_tick`). Measured: 145/145
   records differed between runs on those two fields alone; of 36 records whose *only*
   difference was those fields, 36/36 produced different output text. **Fixed** — both
   gaps closed. After the fix, `retrieved_context` drift went from 145/145 records to
   **0/145**. Prompts are now byte-identical between runs.

2. **Residual non-determinism is per-token floating-point drift compounding over
   generated length**, not anything in the prompt or the sampler config:

   | Output length | Reproduction (same prompt, same seed) |
   |---|---|
   | Short (~60 tokens) | 91.7% |
   | Structured `DialogueResponse` | 45.8% |
   | `max_tokens=512` (the shipped dialogue config) | **4.2%** |

   `P(identical) ≈ (1−p)^N` — a seed fixes the *sampling draw*, it cannot make
   inference itself bitwise-deterministic. DEC-176's own conclusion, verbatim: **"Byte-
   identical reproduction at dialogue output lengths is not achievable on this runtime"**
   (qwen2.5:7b Q4_K_M, Ollama 0.32.9, GPU). This was confirmed by measurement, not
   assumed — nobody has since found a config knob that changes it.

**There is no code fix pending here.** The prompt-leakage cause (the one that *was* a
bug) is closed. The remaining cause is a property of quantized local inference at long
output lengths — not somewhere `dialogue_handler.py` or any engine file has a lever.

### The consequence that mattered — and it's already handled

The 62.5%/37.5% split only matters because human labels were originally trusted-or-not
based on **exact output-text match** (`ISSUE-168`) — so every regeneration would silently
invalidate ~37.5% of the 393 existing labels (**~147 rows**, ~295 across both budgeted
regenerations). That is the number still quoted in `ROADMAP.md`'s `EVAL-P20.4` Notes.

**That number is stale.** `ISSUE-168` was fixed 2026-08-16 (`DEC-181`, `EVAL-P20.3b`):
label trust (`label_merge._has_drifted`) was redefined to compare `criteria_sha256`
only — a regeneration changes `output_text`, never `criteria`, so it no longer drifts
existing labels *by construction*. `DEC-181` explicitly considered and rejected
normalized-text hashing (measured 0/746 recovery — the residual gap is real content
drift, not formatting noise) and similarity thresholds (an uncalibrated free parameter)
before landing on the criteria-only definition.

Live-verified just now, against the current (pre-regen) transcript:

```
$ python scripts/check_label_survival.py
Labels checked: 393
  survive:  393
  drift:    0
  orphaned: 0
New (unlabelled) rows in the candidate transcript: 528
FROZEN
```

This is a self-check (same transcript), not proof the *post-regeneration* transcript
survives — but the mechanism that would cause loss (output-text drift) no longer counts
as drift at all under DEC-181's definition, so there's no structural reason regen #1
should cost anywhere near the ~147-row estimate. Re-run this same command with
`--transcript` pointed at the new gen-dir right after regenerating to get the real number
before trusting it either way — don't assume, DEC-185 already flagged this exact stale-
number risk once.

### What "fixing" this gate would actually mean

There isn't a bug-fix path left. The realistic options, in order of how much they cost:

- **(Recommended) Accept it as permanently NOT MET, already effectively done.** The
  `LOOP:QUEUE` fence was already reopened by explicit human override (`DEC-178`/`DEC-182`)
  specifically because this condition can't be met on this runtime — that decision is
  already made and standing. Nothing further to do here; the label-loss consequence is
  independently handled by DEC-181.
- **Pursue a genuinely different join strategy** (semantic/embedding similarity instead
  of exact match) — `DEC-181` rejected this as a second uncalibrated free parameter with
  no data to tune it against. Would need its own calibration pass before it could be
  trusted, i.e. a new sub-project, not a fix.
- **Reduce `max_tokens`** to push reproduction back toward the 45.8%/91.7% end of the
  curve — a real behavior change to dialogue output length, needs its own regression
  pass, and still wouldn't hit ≥95% (only the short-output row does, and 60 tokens is too
  short for real dialogue).

None of these are "go fix the bug" work. If you want this brief closed out, the honest
move is to document that the gate is structurally unmeetable at current output length and
move on — which is already what the standing override says.

---

## Part 2 — ISSUE-165: dialogue_handler stamps wall-clock time as `tick_id`

**Status:** open, P1, found 2026-08-14 during the same `EVAL-P20.0` investigation.
**File:** `src/npc_engine/engines/dialogue/dialogue_handler.py:224`

```python
tick_id = int(datetime.now(timezone.utc).timestamp())
```

`scheduler/game_clock.py` provides a deterministic `GameClock` (starts at 0, advances
only via explicit `advance()` calls), and `docker-compose.yml` runs the app with
`CLOCK_MODE: game_driven` — but this call site bypasses it entirely and uses a real
Unix timestamp as if it were a game tick.

### Where the bad value gets persisted and read back

- `graph/emotion/emotion_writer.py:21` — `c.emotion_updated_at_tick = $tick`
- `dialogue_handler.py:293` — `expires_at_tick=tick_id + 5` (routine override)
- `engines/events/event_handler.py:238` — `expires_at_tick=tick_id + rule.duration_ticks`
  (same pattern, separate call site worth auditing at the same time)
- Read back into later prompts via `retrieval/graph_rag/subgraph_retriever.py` and
  `retrieval/context/context_utils.py`'s Tier-0 serialization
- Compared against `$tick_id` for expiry in `graph/political/treaty_queries.py:52` and
  `graph/political/pledge_queries.py:80`

### Why it does NOT block the reproduction gate

This *was* part of the original 62.5%-vs-95% investigation, but DEC-176's fix already
neutralized its effect on prompts: `emotion_updated_at_tick` and `expires_at_tick` are
now stripped from prompt content by `NON_PROMPT_NODE_FIELDS` regardless of what value
they hold. `retrieved_context` drift measured 0/145 *with ISSUE-165 still unfixed* — the
symptom that mattered for evals is already gone. Fixing `ISSUE-165` will not move the
62.5% number.

### Why it's still a real bug worth fixing

`tick_id` genuinely means "seconds since epoch" everywhere it's used as if it meant
"game ticks":

- Emotion decay rates are expressed in units-per-tick (`emotion_updated_at_tick` feeds
  decay math elsewhere) — decaying against wall-clock seconds instead of game ticks is
  wrong by whatever the game-tick-to-real-second ratio actually is.
- `expires_at_tick = tick_id + 5` means "5 seconds from now," not "5 game ticks from
  now" — routine overrides, pledges, and treaties all expire on real-world-clock time
  instead of simulated time.
- `oath_engine.py:42`'s pledge-expiry logic and the treaty/pledge `expires_at_tick <=
  $tick_id` comparisons inherit the same confusion.

None of this shows up in the eval reproduction number (those fields are prompt-hidden
now), but it's live in production behavior for anyone actually playing through emotion
decay, routine overrides, pledges, treaties, or oaths.

### To fix

1. Route `tick_id` through the injected `GameClock` (or the world-state tick) instead of
   `datetime.now()`, at all three call sites named above (`dialogue_handler.py:224`,
   `event_handler.py:238`, and anywhere else the audit below finds).
2. Add a regression test asserting two dialogue calls made at the same game tick write
   the same `emotion_updated_at_tick`.
3. Audit for other `datetime.now()`-as-tick uses at the same time (this is explicitly
   called out in the original issue text, not yet done as of this brief).
4. This is a behavior change to emotion decay, routine overrides, pledge/treaty expiry,
   and the oath engine — needs its own regression coverage for each, not just the
   dialogue call site. Budget accordingly; this is bigger than a one-line fix even
   though the diff at the call site itself is small.

Related but separate and lower priority: **`ISSUE-166`** (173/228 Cypher `RETURN`
queries with no `ORDER BY`) was found in the same investigation — confirmed *not* the
dominant term (0/145 `retrieved_context` drift after the DEC-176 fix), P2, no action
needed for this decision.

---

## Recommendation

These are two decoupled questions, not one blocking chain:

1. **Does regen #1 (`EVAL-P20.4`) need to wait on anything here?** No. The label-loss
   risk it was originally paired with is already mitigated by `DEC-181`; `ISSUE-165`
   never affected reproduction in the first place. If you were holding off purely because
   of this pair, there's nothing left to hold off *for* on the eval side — re-run
   `check_label_survival.py` against the real post-regen transcript once it exists, as
   the actual (not assumed) confirmation.
2. **Is `ISSUE-165` worth fixing anyway?** Yes, on its own merits — it's a real
   correctness bug in emotion decay / routine override / pledge / treaty / oath timing —
   but treat it as independent, scheduled work with its own regression tests, not a
   precondition for the eval pipeline.
