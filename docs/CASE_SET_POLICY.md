# Case-Set Policy

**Status:** Human decision, EVAL-P20.1 (HUMAN GATE H6). Governs `evals/cases/*.yaml`.

## Hedging rule

**Rule:** an NPC's epistemic framing must match the provenance of the knowledge
being asked about — an NPC answering from a **direct** `KNOWS_ABOUT` edge must
answer with confidence and must **not** hedge; an NPC answering from **gossip
or rumour-propagated** knowledge **should** hedge, and hedging there is a pass,
not a failure.

This single rule is what both previously-contradicting cases already test:

- `case_neg_captain_sorn_no_hedging` — captain_sorn holds a **direct**
  `KNOWS_ABOUT northern_war_begins` edge (see `demo_game/seeds/seed.py`), so
  hedging markers (`"i heard"`, `"they say"`, `"perhaps"`, ...) are a
  **failure**: he has no reason to speak with borrowed uncertainty.
- `case_pos_mira_gossip_hedging` — mira_innkeeper's knowledge of the same
  event is **gossip-propagated** (a `distorted_summary` with explicit
  third-party attribution), so hedging markers are a **pass**: surfacing that
  epistemic framing is the correct voice, per Rule 9 (see the case's own
  description).

The rule was already implicit in three other cases before this policy existed
— `case_pos_mira_war_gossip_tokens`, `case_pos_old_henryk_war_rumor_tokens`,
and `case_pos_captain_sorn_war_knowledge` all state the direct-vs-gossip
distinction in their `notes:`. This document is that implicit rule made
explicit and load-bearing, so `case_neg_captain_sorn_no_hedging` and
`case_pos_mira_gossip_hedging` can both be pointed at one written sentence
instead of reading as opposite verdicts on "hedging."

**Not adopted (for the record):** a content-specificity rule ("hedge + no
invented fact = pass; hedge + invented fact = fail", judged independent of
who the NPC is) was considered and rejected as the *sole* rule — it would
pass captain_sorn hedging about the war he commands, which is a voice failure
this case set exists to catch regardless of whether he invents a fact while
doing it. A hybrid (provenance sets the register, content-specificity
separately catches invented facts under any register) was also considered and
rejected as unnecessary duplication of policy surface for this pass; revisit
if a case surfaces where the provenance rule alone lets a hallucinated
specific fact through as long as it's hedged.

## Byte-identical player messages

Three cases shared the exact player message `"What is happening in the
north?"`, which the EVAL-P19.3 audit flagged as n-inflation. All three are
**deliberately paired**, across two distinct pairing categories, both now
declared in-file (`notes:`):

1. **Same-NPC, dual-lens pair** — `case_neg_captain_sorn_no_hedging`
   (negative `keyword_none` check) and `case_voice_captain_sorn_001`
   (`tone_judge` check). Both test captain_sorn's no-hedging property, via
   two independent measurement mechanisms (a literal keyword blocklist and an
   LLM tone judge) as a cross-check against either mechanism's individual
   blind spots. This is not n-inflation in the sense the audit meant — it's
   the same claim measured twice, on purpose.
2. **Cross-NPC register-contrast pair** — `case_neg_captain_sorn_no_hedging`
   and `case_neg_mira_no_military_authority`. The identical stimulus is sent
   to two NPCs with opposite expected registers (captain_sorn: authoritative,
   no hedging; mira: warm gossip, no military authority) specifically to
   prove the engine produces two distinctly different voices from one prompt,
   not one generic NPC-shaped response. Same pattern already used elsewhere
   in the case set (e.g. `case_voice_captain_sorn_001` vs
   `case_voice_mira_innkeeper`).

**General rule going forward:** no two cases may share a `player_message`
unless the pairing is declared, by name, in both cases' `notes:` field, under
one of the two categories above (same-NPC dual-lens, or cross-NPC
register-contrast). An undeclared duplicate is a bug; a declared one is not.

## Wording-mismatch fix landed in this commit

`make check-dead-keywords` (EVAL-P19.3) flagged `case_neg_lira_no_trust_disclosure`'s
forbidden phrase `"thieves guild"` as having zero corpus hits — but the real
corpus writes `"thieves' guild"` (apostrophe) **20 times**, never the
no-apostrophe form. That is a wording mismatch, not a case that correctly
never fires: fixed by replacing it with the apostrophe form in the
`keyword_none` list. Same bug, same fix, applied to
`case_neg_captain_sorn_no_hedging`'s `"i heard"` entry — the corpus writes
`"i've heard"` 612 times and `"i heard"` zero times, so `"i heard"` was
replaced with `"i've heard"`.

The remaining ~200 dead-keyword entries from the EVAL-P19.3 work-list are not
triaged here — most are, per that phase's own analysis, keywords that
*should* have zero corpus hits (invented warlord names, banned system-leak
strings, moderation terms). Full triage of the rest is tracked as
[ISSUE-157](../project-harness/ISSUES.md).
