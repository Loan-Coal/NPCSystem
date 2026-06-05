# FIX-SEV-36 — Separate gossip distortion probability from `BELIEVES_RUMOR.confidence`

**Severity:** LOW · **Confidence:** Likely · **Effort:** M
**Category:** engine · **Absorbs:** ENG-09, ENG-10 (partial), ENG-13 (partial)

## Scope
**In scope:** Separate distortion probability from `BELIEVES_RUMOR.confidence` (owner confirmed these are distinct concepts).
**Out of scope:** Emotion shock valence-gating — owner confirmed shock fires on ANY high-severity event including positive ones; this is intentional behavior, not a bug.
**Deferred:** Quest `completed` terminal state — write a DECISIONS entry asking for owner direction; do not change the quest model here.

## Problem
In `gossip_handler.py` (around lines 204, 210), distortion *probability* (the RNG roll that decides whether a rumor gets garbled) is conflated with `confidence` written to the `BELIEVES_RUMOR` relationship (how certain the NPC is in what they heard). These are different values:
- **Distortion probability**: function of hop count, NPC personality, base rate config. Used only to decide whether distortion occurs. Never written to the graph.
- **Confidence**: function of trust in the source, rumor plausibility, NPC personality. Written to `BELIEVES_RUMOR.confidence`. Has downstream effects on memory vividness and dialogue hedging.

## Steps
1. In `config.py`: add `BASE_DISTORTION_RATE: float = 0.3`.
2. In `gossip_handler.py` distortion logic, split into two explicit calculations:
   ```python
   # Step 1: should distortion occur?
   distortion_probability = _compute_distortion_probability(
       hop_count, npc_personality, settings.BASE_DISTORTION_RATE)
   should_distort = rng.random() < distortion_probability

   # Step 2: what confidence does the hearer have?
   confidence = _compute_confidence(source_trust, rumor_plausibility, npc_personality)
   ```
3. Write `confidence` (not the probability) to `BELIEVES_RUMOR.confidence`.
4. Extract both helpers as named functions with docstrings.
5. Log the `distortion_probability` and seed value per the RNG logging rule.
6. Add a DECISIONS entry (DEC-0XX): "Quest `completed` terminal state — is `completed` irreversible? Owner decision required. Deferred from SEV-36."

## Verification
- `tests/unit/test_gossip_distortion_sev36.py`:
  - High source-trust + plausible rumor → `BELIEVES_RUMOR.confidence` is high, regardless of whether distortion happened.
  - Low source-trust → `BELIEVES_RUMOR.confidence` is low.
  - Over many runs with `distortion_probability=1.0` → every rumor distorts; confidence still tracks trust not probability.
  - Log output contains `distortion_probability` and seed value.
- `make test` passes.

## Blast radius
Gossip distortion pipeline; `BELIEVES_RUMOR.confidence` values written to the graph (values will change for existing data — downstream memory/dialogue reads of confidence will see more semantically accurate values).
