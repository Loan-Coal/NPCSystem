# FIX-SEV-18 — Replace silent error swallowing with log-and-(re)raise

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** S
**Category:** correctness / error-handling · **Absorbs:** PY-06, PY-07, ENG-06, DEMO-07

## Problem
Multiple `except Exception: pass` / warn-and-continue blocks swallow failures with no log/metric, some leaving the graph in an inconsistent state — violating the strict "never swallow errors" rule.

## Current shape (all instances)
- `engines/dialogue/degradation.py:34-41` — `except Exception: pass` on canned-response YAML load (corrupted file → silent).
- `engines/memory_consolidation/memory_consolidation_engine.py:146-147` — `except Exception: pass` on the WITNESSED query (schema change → silent).
- `engines/dialogue/dialogue_handler.py:212-213` — TTS failure returns `response` silently, no log/metric, fallback undocumented in the docstring.
- `engines/gossip/gossip_handler.py:152-171` — `except Exception: LOGGER.exception(...)` but continues, leaving `KNOWS_ABOUT` written while the Rumor node/`BELIEVES_RUMOR` edge are not → `/gossip/trace` undercounts.
- Demo: `gold_poller.py:58-64`, `ui/game_window.py:206-209`, `game_controller.py:508-515` (`except EngineClientError: pass`), `action_workers.py:26-40` (`except Exception: return None`).

## Target shape
Every `except` logs (with `npc_id`/context/`duration_ms`) and then re-raises, raises a domain error, or continues only when continuing is correct and observable. Domain `except Exception` is narrowed to the expected error type.

## Steps
1. `degradation.py`: `except Exception: _logger.warning("canned_response_load_failed", extra={"archetype": name, "path": str(candidate)})` then fall through to the default.
2. `memory_consolidation_engine.py`: `except Exception: _LOGGER.warning("witnessed_query_failed", extra={"npc_id": npc_id})` then continue with default vividness (document the fallback in the docstring).
3. `dialogue_handler.py` TTS: log `WARNING` + `increment_metric("tts_failures_total", ...)` + document the no-audio fallback in the docstring; keep returning `response`.
4. `gossip_handler.py` rumor record: make rumor recording part of the same transactional unit as `propagate(...)` (so the two graphs stay consistent) OR re-raise; do not leave the graphs inconsistent silently.
5. Demo pollers/workers: log to stderr (matching the existing `print(f"[X] error: {exc}", file=sys.stderr)` pattern — or stdlib `logging` per SEV-37) before continuing; narrow `except Exception` to `EngineClientError` where only API failures are expected.

## Verification
- `rg "except Exception:\s*$" -A1 src/npc_engine | rg "pass"` → 0; `rg "except.*:\s*$" -A1 demo_game | rg "pass|return None"` → each remaining site has a preceding log call.
- Mock-raise unit tests assert the warning/metric fires (canned-response load, WITNESSED query, TTS).
- Gossip integration: force the rumor-record write to fail → either the `KNOWS_ABOUT` edge is also absent (atomic) or the error propagates.

## Blast radius
Dialogue degradation (every turn when LLM is down), memory consolidation, the gossip rumor graph (and `/gossip/trace`), demo pollers. Mostly small per-site changes; the gossip one couples to SEV-04 (transaction ownership).
