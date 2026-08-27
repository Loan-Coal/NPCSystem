# Session prompt — INTEGRATION: close out Program 4's EVAL-P25/P26 (both tracks)

**Written:** 2026-08-27, after Track A and Track B both reported complete. **Serial — do not run
in parallel with anything.** Paste everything below "PROMPT — copy from here" into a fresh session
at the repo root, on `eval-ab-context-arms`.

Three maintainer decisions are already folded into the prompt below and need no re-asking:
Track A's untracked deliverables get committed; **the six ungrounded legacy cases get fixed during
integration** (not ratcheted); and `EVAL-P26.2`/`P26.3` are ticked now with an issue filed for the
outstanding human content review.

---

## PROMPT — copy from here

You are working on NPC Engine (`c:\Users\lohan\Documents\hackathons\NPCSystem`), branch
`eval-ab-context-arms`. Read `project-harness/CLAUDE.md` first — binding.

You are the **serial integration step** for Program 4's EVAL-P25/P26. Two parallel sessions
(Track A tooling, Track B contract + cases) have finished. Both were forbidden from editing
`Makefile`, `ROADMAP.md`, `ISSUES.md` and `DECISIONS.md` to avoid colliding, and wrote handoff
files instead. Your job: apply those handoffs, build the one remaining phase, fix six legacy
cases, and get `make check` green **with no regression**.

Read in full before acting:
- `project-harness/HANDOFF_TRACK_A.md` (§1–6)
- `project-harness/HANDOFF_TRACK_B.md` (§0–6)
- `project-harness/EVAL_P25_TO_P31_PLAN.md` §3 for EVAL-P26.3
- `docs/CAPABILITY_CASES.md` — the case contract you are gating against

### State of the tree, measured 2026-08-27 — verify each, do not assume

These were measured against the working tree, not read off either track's summary. **Re-check
each one yourself first. If any disagrees, stop and say so — the tree moved under you.**

| fact | how to check |
|---|---|
| Track B **committed** (`72594dd`, `ee14ae2`) and its handoff is in git | `git log --oneline -8` |
| Track A's deliverables are **already committed** as `d7b7c8b`, verbatim, with `HANDOFF_TRACK_A.md` | `git show --stat d7b7c8b` |
| Programs 4/5 + `ISSUE-223` are **already committed** as `b9717ef` — the checkboxes you tick exist | `git show --stat b9717ef` |
| `evals/cases/case_pos_*` is **46** (16 pre-existing + 30 new) | `ls evals/cases/case_pos_* \| wc -l` |
| A concurrent EVAL-P10 session is separately active on `src/npc_engine/config*.py` | `git log --oneline` — `de746ed`, `96d83eb`, `e5144f7` |
| `project-harness/PROMPT_CODEBASE_REVIEW_2026-08.md` is untracked and belongs to **neither** track — leave it alone | `git status --short` |

### Regression baseline — capture this BEFORE you change anything

The maintainer's requirement is **no regressions**. You cannot prove that without a before-state,
and you must not infer one from a summary.

1. `git rev-parse --short HEAD` and `git status --short > /tmp/pre_integration_status.txt`.
2. `make check 2>&1 | tee /tmp/pre_integration_check.log; echo "EXIT=$?"` — record the exit code,
   the passed/failed counts, and both coverage percentages (`test-cov` for `src`, `test-cov-evals`
   for `evals`, floors 80 and 75 respectively).
3. `python scripts/check_label_survival.py --transcript evals/generations/k3_77688e7_regen1/outputs.jsonl`
   — record the survive/drift/orphan counts and the FROZEN verdict.
4. `python scripts/check_base_rate.py evals/generations/k3_77688e7_regen1` — record the report.

**Measured 2026-08-27 on this tree (Track A's untracked files present, since untracked files are
still on disk and importable) — your Step-0 run should reproduce these:**

    make check                EXIT=0
    test-cov        (src)     4048 passed, 36 skipped   coverage 87.86%  (floor 80)
    test-cov-evals  (evals)   1007 passed,  1 skipped   coverage 79.76%  (floor 75)
    check_label_survival      survive 393, drift 0, orphaned 0 -> FROZEN
    check_base_rate           ALL n=975 rate=0.943 above_band, exit 0 (advisory)

**Every one of these must read the same or better at the end.** A dropped test, a coverage
percentage below its floor, or a label that starts drifting is a regression, not a side effect.
If the baseline `make check` is already red, **say so and stop** — you must not inherit someone
else's red and hand it back as yours.

### Four measured facts that contradict the handoffs — read before applying them

**1. ⚠️ ISSUE-ID COLLISION. Track A's issue numbers are already taken.**
Track A was allocated `ISSUE-224+`. While it worked, the concurrent EVAL-P10 session **committed
ISSUE-224, ISSUE-225 and ISSUE-226** for unrelated things. The committed ledger runs to
**ISSUE-226**; Track B holds **230–236**; `ISSUE-223` is the prompt-singleton issue.

**Renumber Track A's four issues to `ISSUE-237`, `238`, `239`, `240`**, in that order, text
verbatim. A `grep` over `docs/ evals/ scripts/ prompts/` found A's numbers **only** inside
`HANDOFF_TRACK_A.md`, so the renumber is contained — **re-run that grep to confirm before you
renumber**. Gaps at 227–229 are fine: CLAUDE.md requires IDs monotonic and never reused, not
contiguous.

**2. ⚠️ DEC-216's switch condition is falsified. Do NOT flip the base-rate gate to blocking.**
`DEC-216` says *"switch ENFORCE to blocking in the same commit that lands EVAL-P26.2."* P26.2 has
landed — and the switch still cannot happen, because **no generation over the rebuilt battery
exists.** Measured:

    python scripts/check_base_rate.py evals/generations/k3_77688e7_regen1
    → ALL n=975 rate=0.943 above_band; 9 of 10 families out of band; exit 0

Those 975 rows are the **pre-rebuild** battery — Track B's 30 cases have never been generated
against, and the EVAL-P10 session deliberately ran no generation. Flipping to blocking now would
gate the repo on a stale run that does not contain the new cases.

**Amend `DEC-216` as you apply it** — an appended paragraph, not a rewrite. New switch condition:
*"the first commit after a generation over the rebuilt 46-case battery exists,"* quoting the
measurement above. Keep `check-base-rate` **out of `make check`**. Do not widen the band to make
anything pass.

**3. ⚠️ Track A's fix-note for the six ungrounded cases assumed a rewrite that never happened.**
`ISSUE-224` (→ `237`) says the six "are being rewritten wholesale by EVAL-P26.2." **They were
not.** Track B *added* 30 cases and left the original 16 untouched — verified: 46 = 16 + 30, and
all six original filenames still exist. Its "To fix" therefore has no owner. You are that owner;
see Step 2.

**4. Six `make check` gates already pass** — `check-label-survival`, `check-harness`,
`check-test-quality`, `roadmap-verify`, `check-human-gates`, `check-docstrings`, run against the
current tree. Adding 30 cases did **not** break label survival. `lint`, `type`, `test-cov` and
`test-cov-evals` were not in that spot-check, which is why you capture a full baseline above.

### The work, in order

> **Already done for you, so do not redo it:** Track A's ten deliverables landed verbatim as
> `d7b7c8b` (2372 insertions, zero deletions, no `src/`), and the Programs 4/5 ROADMAP block plus
> `ISSUE-223` landed as `b9717ef` (193 insertions, line-ending preserving). Your work starts at
> Step 1 below. If either commit is missing from `git log`, stop — you are on the wrong branch.

**Step 1 — Apply both handoffs.**
- `Makefile`: Track A's `check-base-rate`, `review-cases` (and `variance-score` if defined) plus
  Track B's recipe, and the `.PHONY` additions. **`.PHONY` is a single continued line — edit it
  once, carefully, with both tracks' names.**
- `DECISIONS.md`: append `DEC-216`, `217`, `218` (Track A, **with the §2 amendment**) and
  `DEC-220`–`223` (Track B). `DEC-215` is taken; `DEC-219` is an intentional gap.
- `ISSUES.md`: Track A's four **renumbered 237–240**, Track B's `230`–`236`. Then close
  **ISSUE-147**: mark `[FIXED]`, add the `**Fixed:**` line, and **move it to
  `archive/ISSUES_RESOLVED.md`** — CLAUDE.md requires the move, not just the marker.
- `ROADMAP.md`: tick `EVAL-P25.1`, `P25.2`, `P25.3`, `P25.4`, `P26.1`, `P26.2`.

**Step 2 — Fix the six ungrounded legacy cases. ⚠️ Read all of this before editing.**

The six: `case_pos_{aldric_trade_disruption, captain_sorn_war_knowledge, lira_fence_trade,
mira_war_gossip_tokens, old_henryk_war_rumor_tokens, world_blight_guard}.yaml`. Each lacks the
grounding edge type `docs/CAPABILITY_CASES.md` requires in `notes`.

**You are authorized to edit exactly these six files under `evals/cases/`. No others.**

- **Read the grounding from the LIVE GRAPH, not the seed file.** `DEC-223` records that live wins
  — Track B found `seed_tavern_world.py` disagreeing with the live graph on knowledge state and
  summary text, and authoring from the seed file would have produced fabricated cases. Requires
  the stack up (`docker compose up -d`, worlds seeded). Use the typed admin endpoints
  `GET /v1/admin/{beliefs,goals,memories,secrets}/{npc_id}`; **`make draft-cases` is broken
  (ISSUE-148) — do not use it.**
- **Match Track B's format exactly:** `Grounding: REMEMBERS(tw_innkeeper, mem_tw_innkeeper_0).`
  Real edge types only: `KNOWS_ABOUT`, `BELIEVES`, `REMEMBERS`, `PURSUES`, `KNOWS_SECRET`.
  `HAS_MEMORY` / `HAS_GOAL` / `HAS_SECRET` do not exist.
- **If a case's grounding cannot be found in the live graph, STOP and report it.** That would mean
  the case asserts a fact the NPC does not hold, which is a fabricated case — a finding, not a
  formatting problem. Do not invent an edge to satisfy the gate.

**⚠️ These six are broken on TWO axes and you are fixing ONE.** All six are also in
`test_capability_echo_resistance.GAMEABLE_BASELINE` (7 members; the seventh,
`case_pos_mira_gossip_hedging`, *is* grounded). Adding a `Grounding:` line does not make a case
ungameable — their `keyword_any` lists are drawn from their own player messages, and re-authoring
those lists is case-authoring work, not integration work.

**So: fix `notes` on all six and gate hard on `undeclared_grounding_edge`. Leave gameability on
the existing `GAMEABLE_BASELINE` ratchet**, which predates this program (same shape as
`UNCOVERED_BASELINE`, DEC-161) and already "binds every case authored from now on while the
known-bad set stays visible and countable." **Do not widen EVAL-P26.3's gate to gameability for
legacy cases, and do not shrink `GAMEABLE_BASELINE`** unless you actually re-author the keyword
lists — which is out of scope here. Record this two-axis split in a DECISIONS entry so the next
reader does not mistake "grounded" for "ungameable".

**After editing, re-run `python scripts/check_label_survival.py --transcript
evals/generations/k3_77688e7_regen1/outputs.jsonl` and confirm it still reports FROZEN with 0
drift.** Editing case bytes moves `golden_set_version` and `harness_version`; `notes` is not
judging criteria so labels *should* survive — **confirm it, do not assume it.**

**Step 3 — EVAL-P26.3, the one phase still unbuilt.**
`edit tests/unit/evals/test_capability_coverage.py`. Every authored case must pass the P26.1
adversary and the existing echo/hedge gates before it counts toward coverage. Spec in plan §3.
- Require `undeclared_grounding_edge` **empty** — Step 2 makes that achievable for all 46.
- Respect `DEC-221`: `test_capability_echo_resistance` excludes **judge-decided** cases from the
  gameability ratchet and pins that excluded set to exactly two names. Your gate must respect that
  pin, **not silently widen it**.
- **RED anchor required:** break one case deliberately (point a `keyword_any` token at its own
  `player_message`, or strip a `Grounding:` line) and confirm the gate fails **for that reason**
  before the implementation exists. Revert the break afterwards.

**Step 4 — Wire the gates.** Add **`check-engine-coverage`** to the `check:` target (Track B's
`ISSUE-230` exists because it is not wired). Do **not** add `check-base-rate` (§2). You are adding
a gate to the gate list — it can legitimately fail on an unclassified package, so run `make check`
immediately after.

**Step 5 — Run the adversary over all 46, then the judgment pass.**
Track A ran the adversary over the 16 pre-existing cases only, where it flagged exactly the seven
`GAMEABLE_BASELINE` members and exactly the two judge-decided cases — same sets, no more, no
fewer, which is the evidence it works. **Nobody has run it over Track B's 30.** Run all 46, report
counts, act on anything new — fix the case, never weaken the adversary.

Then the **EVAL-P26.1 judgment pass**, which no session has run. Runbook: `HANDOFF_TRACK_A.md` §6.
Batch/paste, mirroring `evals/calibration/oracle_batches/` — **there is no Anthropic client in
this repo and you must not add one.** Checks: leading prompt, self-answering, insider vocabulary.
**You are Opus** — you may perform the judgment yourself against `prompts/eval/case_adversary.yaml`,
but route it through the batch artifact the module emits so the result is a file with provenance,
not an opinion in the transcript. Report how many of 46 fail each check.

**Step 6 — Tick `EVAL-P26.3`, file the review issue, run the final `make check`.**
File an issue (next free id after 240) recording that **the 30 authored cases have had no human
content review**, naming all 30 case ids. Track B relaxed EVAL-P26.2's ⏸️ *human authoring* marker
as its brief directed; the guard is real (live-graph grounding, echo and hedge gates, hedge-probe
6/46 = 0.130 against a 0.30 ceiling, all six failures pre-existing) but **no gate can tell you
whether these are the right questions to ask an NPC**. The tick must not imply a review that did
not happen.

### Verification discipline — what to ground rather than trust

Both handoffs are self-reports. Four of their claims already turned out wrong (§1–4 above). Before
relying on any load-bearing claim, re-derive it:

- **Counts and sets** — case counts, `GAMEABLE_BASELINE` membership, per-family base rates,
  ID ranges. Cheap to check, and three of the four contradictions above were count/ID errors.
- **"X was rewritten / handled by the other track"** — cross-track claims are exactly where the
  parallel split loses information. §3 is one such claim and it was false.
- **Anything that decides whether a gate fires.** A gate wired against a wrong assumption is worse
  than no gate: it reports green.
- **Do not re-derive** the six gates listed in §4 as already passing, or the per-family base-rate
  table — those were measured this session against this tree.

### Stop and ask before

- **Any change under `src/`.** This session touches **zero** `src/` files. Two temptations are
  already logged and correctly deferred (see below).
- Adding any dependency.
- Editing any case under `evals/cases/` **other than the six named in Step 2** — in particular any
  of Track B's 30, beyond fixing a genuine adversary finding.
- Weakening the base-rate band, the 0.60 kappa threshold, the echo/hedge gates, the `DEC-221`
  two-name pin, or the `GAMEABLE_BASELINE` ratchet.
- Any case in Step 2 whose grounding you cannot find in the live graph.

### Do NOT

- **Do not commit the EVAL-P10 session's work.** `git status` before every commit; that session is
  separately active on `src/npc_engine/config*.py`. ISSUE-139 is this repo's recurring failure.
- **Do not fix ISSUE-231.** It is a `src/` prompt change belonging to EVAL-P29 — see below.
- **Do not start EVAL-P27** (multi-turn) or **EVAL-P28** (labelling, behind 🔴 HUMAN GATE H13).
- **Do not run a generation.** None is needed, and EVAL-P10 gate 6 currently fails (see below).
- **Do not rewrite line endings.** `ROADMAP.md`, `ISSUES.md`, `DECISIONS.md` are **CRLF**; Track
  A's new files are **LF**; there is no `.gitattributes` (ISSUE-215). Edit the ledgers byte-level.
  A small edit showing thousands of changed lines is a bug — revert and redo it.

### Three findings you are inheriting — route them, do not solve them

**ISSUE-231 is the most consequential thing either track found, and it lands on the golden set you
are integrating.** `context.npc.beliefs` is produced, ranked, budgeted and serialized into every
prompt — and **no rule in `system_v1.yaml` ever tells the model to use it.** Rules exist for world,
reputation, emotion, profile, known_events, session turns, goals (7), propagated_reputation (13),
retrieved_context (17) and memories (15). Never beliefs. **16 of the 46 capability cases are
belief-grounded** (8 pre-existing, 8 of Track B's 30) — roughly a third of the battery tests a
channel the model was never taught to read. Write both consequences into your final message:
1. A strong candidate cause for the belief-grounded half of **ISSUE-145**.
2. An **excellent first prompt arm for EVAL-P31** — `system_v1` versus `system_v1 + a beliefs
   rule` is exactly the A/B Program 5's variant machinery exists to make measurable, and adding
   the rule directly would move `dialogue_prompt_hash` and break comparability. **Add it to
   `ROADMAP.md` under EVAL-P31 as a named candidate arm.**

**EVAL-P10 gate 6 FAILS and it blocks the next generation.**
`VECTOR_STORE_INCREMENTAL_UPSERT` defaults True and is absent from `.env`; 58
`vector_store.incremental_upsert` events were observed emitted by the **gossip tick**, not
dialogue. Nothing here is blocked by it, but the base-rate flip (§2), EVAL-P28's labelling run,
and any regeneration all sit behind it. **Name it as the next blocker**, and check whether it
already has an ISSUE before filing a duplicate.

**`case_pos_mira_gossip_hedging` is grounded but gameable** — the one `GAMEABLE_BASELINE` member
Step 2 does not touch. It stays on the ratchet. Mention it so nobody later reads "all six fixed"
as "GAMEABLE_BASELINE is empty".

### Definition of done

- [ ] `make check` **exit 0**, with `check-engine-coverage` newly wired in and `check-base-rate`
      deliberately not.
- [ ] **No regression against the Step-0 baseline:** test counts equal or higher, both coverage
      percentages at or above their floors and not lower than baseline, `check_label_survival`
      still FROZEN with 0 drift. Quote before/after for each.
- [ ] `make roadmap-verify` and `make check-human-gates` green.
- [ ] Both handoffs applied: Makefile, DECISIONS (216–218 **with the amendment**, 220–223), ISSUES
      (Track A renumbered **237–240**, Track B 230–236), ISSUE-147 `[FIXED]` **and moved to the
      archive**, plus the new content-review issue and the Step-2 two-axis decision.
- [ ] All six legacy cases carry a `Grounding:` line **verified against the live graph**.
- [ ] `EVAL-P25.1`–`P26.3` all ticked.
- [ ] EVAL-P26.3 has a RED anchor confirmed failing for the right reason, and the deliberate break
      reverted. Say how you confirmed it.
- [ ] Adversary run over **all 46** and judgment pass over all 46, counts reported.
- [ ] EVAL-P31 in `ROADMAP.md` names the beliefs-rule candidate arm.
- [ ] Commits are yours only (Track A's already landed) — no `src/` files, nothing from the EVAL-P10 session.
- [ ] Final message answers in one line each: **what the adversary found across all 46**, **what
      the judgment pass found**, **which edge type each of the six legacy cases turned out to
      have**, and **what now blocks the base-rate flip**.
