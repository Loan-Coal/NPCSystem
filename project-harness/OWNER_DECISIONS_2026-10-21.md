# Owner decisions 2026-10-21: handoff to the roadmap builder

**Reader:** the roadmap-building session.
**Inputs:** `project-harness/REVIEW_2026-10-21.md` (facts) and DEC-296..DEC-315 in `DECISIONS.md` (choices, rejected options, owner notes).
**This file** holds what the roadmap must be built on. It contains no sprints or tasks.

> **Amended 2026-10-21 by the challenge session (DEC-316..DEC-327).** A four-lens challenge (drainability, safety, simplicity, consistency) found twelve decisions that would stop an unattended drain, or that rested on a stale fact. The owner resolved each of them. Rows below marked **→ DEC-3xx** have been superseded or amended; read the new entry. The roadmap built from all of this is `ROADMAP.md`, the drain programme: 45 tasks, 10 phases.

---

## 1. The end goal, restated, and the themes that serve each pillar

The review's §9 themes are renamed below in the terms of these decisions. The old ids are in brackets.

| # | Pillar | Served by |
|---|---|---|
| 1 | **Evaluate reliably.** A deterministic, repeatable check that NPCs remember, feel and gossip, and goes red when they don't | **Pillar transcript eval** [T2] (DEC-301), **pillar fixes** [T1], judge repair [T8] (DEC-302, secondary), loop safety [T10] (DEC-309), ledger truth [T12] (DEC-308) |
| 2 | **Expand.** A new engine, emotion model, output field or backend is a new file plus at most 1–2 edits | Seams [T7]: emotion registry and node labels (DEC-303); dialogue-output field via the unified model (DEC-299); dead-surface deletion [T5]. Tick-engine registration and the Ollama-derived token budget are **by-design** (DEC-303) |
| 3 | **Work on through text.** API/WS transcripts, a scripted runner, diffable output; no GUI needed | Text-first (DEC-296); **demo shrink** [T6] (DEC-297); transcript runner [T2] (DEC-301); evaluator first run [T3] |
| 4 | **Plug easily into Unreal.** Engine improvements reach `../DemoGame` without client changes, through a stable, versioned contract | **Engine-owned contract** [new] (DEC-298); unified HTTP/WS model (DEC-299); additive-only + `contract_version` (DEC-300) |
| — | Simplicity, the tie-breaker | Harness weight [T11] (DEC-310); LOC policy (DEC-313); dead surface [T5] |

**The binding link between pillars 1 and 4 (owner, DEC-299):** the eval drives exactly the public HTTP/WS routes Unreal calls. A pillar that passes in the eval passes for Unreal, because both use the same code path.

---

## 2. Decision table

| Decision | Choice | DEC | Effect on review themes |
|---|---|---|---|
| A1 Primary surface | Text-first; Unreal is the showcase | DEC-296 | Reframes T2, T3 and T6 around text |
| A2 pygame `demo_game/` | Shrink to the runner, the seeder and a text client; delete the interactive UI (~12.8k LOC) | DEC-297 | T6 becomes a deletion phase; **T13.1/T13.2 and the D3 keep-list are moot**; remove the ⏸️ flag |
| A3(a) Contract | Engine-owned `contracts/openapi_v1.json` + WS frame JSON Schema; type-level `check-api-contract`; DemoGame's sync check repointed. **→ DEC-324:** the gate already exists, so the dump becomes its single baseline; WS frames are a Pydantic union; no new dependency | DEC-298, DEC-324 | New theme "engine-owned contract"; absorbs `check-api-stability` deletion (C7) |
| A3(b) HTTP/WS payload | One model; WS `done.data` == HTTP `DialogueResponse`; eval uses the Unreal path. **→ DEC-325:** delete only the WS whitelist; keep `DialogueGeneration`; keep `audio_bytes_b64` as a WS extra | DEC-299, DEC-325 | Closes the T7 dialogue-output seam; constrains T2's runner design |
| A3(c) Versioning | Additive-only + `contract_version` in `/health` and every response | DEC-300 | Part of the contract theme |
| A4(a) Primary eval | Deterministic pillar assertions over HTTP/WS transcripts, live, N-of-M for LLM-dependent checks. **→ DEC-321:** extend the kept runner, delete `demo_run_live.py`, run 2-of-3 only on FEEL/REMEMBER-delta/GOSSIP, commit verdicts to `evals/pillar_verdicts.jsonl` | DEC-301, DEC-321 | T2 becomes the primary eval; subsumes D5 |
| A4(b) Judged layer | **Repair**; this differs from the review's recommendation (retire). **→ DEC-322:** the loop-runnable half is in the fence (T17); labels, T18.1 and T18.2 are owner work | DEC-302, DEC-322 | T8 = D2-A path; ≥60 owner labels; C8 declined; eval LOOSE-KEEPs fold into T8 |
| A5 Seams | Fix the emotion registry (ISSUE-362) and labels-in-4-places; tick-engine and token budget are by-design. **→ DEC-326:** collapse the 1-implementor emotion protocol instead of reshaping it | DEC-303, DEC-326 | T7 narrowed; ISSUE-315 closes as by-design; ISSUE-209/297 stay under T3 |
| B1 Triage bar | Hybrid (D1-C) | DEC-304 | Executed by C3; eval LOOSE-KEEPs go to T8 |
| B2.1 Sprint 10 bundling | Unbundle T20.1 and the rule-17 renumber | DEC-305 | T9 parts become loop-runnable now |
| B2.2 Rule 11 | Rewrite its trigger; no `available_interactions` producer | DEC-306 | T9, prompt-only |
| B2.3 Hash set | `system_v1`, `system_state_v1`, `moderation/content_ceiling_v1`, `llm_config prompt.version` | DEC-307 | Specifies T20.1 |
| B3 Ticked-but-unmet | Un-tick T16.1, T16.4, T15.4; waive T7.5 into T4. **→ DEC-318:** re-issued as T26.5/T26.6 (archived ticks say "superseded"); every Done-when names a checkable artefact | DEC-308, DEC-318 | T12; T4 inherits the 2.63x |
| B4 Loop permissions | Keep the flag; frozen-path diff check on **task** sessions; **no deny rule**. **→ DEC-316:** a narrow bash regex fixed in the driver; scan `$before..HEAD` plus untracked files; on a hit, reset and end the night. **DEC-319** adds a guard between nights | DEC-309, DEC-316, DEC-319 | T10; must precede any eval-touching task |
| B5 Harness cuts | C1, C2, C3, C4, C7, C9, C10, C11, C12, C14 approved; C5, C6, C8, C13 declined. **→ DEC-327:** C2 is a verbatim move plus a one-line ledger-checker change. C12 keeps the 5 targets CI runs | DEC-310, DEC-327 | T11 |
| B6 Classes | file-deletion, public-interface, graph-schema, new-dependency | DEC-311 | Unblocks T5, T6, T7, contract, T8 |
| B6 Harness edits | D4 #1, #2, #3, #7 + a new `harness-edit` class. **→ DEC-317:** no class (the halt table never halts on harness edits); edit #4 dropped and the HUMAN GATE machinery deleted; #3 made by the builder | DEC-312, DEC-317 | Unblocks T10 and fence moves |
| B6 LOC policy | Net-negative per phase; no baseline raise; lower the baseline after each phase. **→ DEC-320:** each phase pairs its own deletions, ordered first; each phase's last task lowers the baseline | DEC-313, DEC-320 | Forces the demo shrink first |
| B6 Infra | Docker + Ollama up overnight | DEC-314 | Live tasks may be unattended |
| B7 Priority | 1 demo shrink, 2 pillar transcript eval, 3 pillar fixes. **→ DEC-323:** full drain order is bootstrap, harness cuts, then these three, then contract, seams, judge half, prompt and latency | DEC-315, DEC-323 | Top of the sequence; builder orders the rest |

---

## 3. Pre-approved lines (copy exactly onto the tasks they cover)

```
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Pre-approved: public-interface · owner 2026-10-21 · DEC-311
Pre-approved: graph-schema · owner 2026-10-21 · DEC-311
Pre-approved: new-dependency · owner 2026-10-21 · DEC-311
Pre-approved: file-deletion, public-interface · owner 2026-10-21 · DEC-311
```

> **Amended (DEC-317):** the `harness-edit` line above was removed. The class does not exist, because the session's halt table never halts on a harness, test or script edit. **DEC-324:** `new-dependency` goes unused.

**Scope of each class.**
- **file-deletion:** the `demo_game/` shrink (DEC-297); harness cuts C1–C4, C7, C9–C12 (DEC-310); dead-surface theme T5; the `check-api-stability` script.
- **public-interface:** the unified WS `done` frame (DEC-299); `contract_version` (DEC-300); the emotion-model protocol reshape (DEC-303); deleting the `stream` chain (ISSUE-322); tone-band resolution (ISSUE-328).
- **graph-schema:** only as needed by the pillar fixes (for example the ISSUE-373 location fix, or an emotion property). The task spec must name the node/edge change.
- **new-dependency:** the task spec must name the package and its reason, for example a JSON Schema validator for the WS schema or an OpenAPI diff tool.
- **harness-edit:** exactly these, and nothing else:
  1. the frozen-path check on task diffs (`scripts/expand_loop.sh:506`);
  2. the `tests/unit/evals/test_label_adequacy.py:70-89` rewrite;
  3. the synchronised tripwire records (`test_roadmap_cursor.py:171-192,219`, `ROADMAP.md:504-507,112`);
  4. T-ids in `scripts/check_human_gates.py:34`;
  5. adding the `harness-edit` class itself to `expand-linear-next.md:95`.

  **Superseded by DEC-317.** There is no `harness-edit` class. The builder made edit 3 by hand on 2026-10-21. Edit 4 was dropped, and the gate script is deleted in T21.1. Edit 1 is T21.4 and edit 2 is T17.2; neither carries a class line.

**LOC policy line** (state it in the ROADMAP header, not on tasks): every phase is net-negative in the rule-1 four-directory count. `scripts/loc_baseline.txt` is lowered to the new total after each phase and is never raised (DEC-313).

---

## 4. Orderings the builder must respect

> **Amended (DEC-323, DEC-316).** The fence's file order is:
> T21 bootstrap → T22 harness cuts → T23 shrink → T24 pillar eval → T25 pillar fixes → T26 contract + ledger truth → T28 seams + dead surface → T17 judge half → T19 prompt parts → T29 latency.
>
> - Night 1 runs `--max-phases 1`, so the frozen check is live before any later phase.
> - Items 4 and 5 below are satisfied by T21.
> - Item 6 lives under "Owner work" in `ROADMAP.md`.

1. **Demo shrink first** (DEC-315, DEC-313). It frees ~12.8k LOC of headroom for the additive work.
2. **Pillar transcript eval second.** It goes red on FEEL, relationships, distortion and location (§4). Every later pillar fix is "done" when its assertion goes green.
3. **Pillar fixes third** (old T1, including ISSUE-373, ISSUE-228 and the `head(collect())` mispairing).
4. **The `harness-edit` class lands before any task stamped with it.**
5. **The frozen-path check (DEC-309) lands before any task touching `evals/`.**
6. Sprint 9 judge repair: T17.1 detailing is **due 2026-10-27**. T18.1 needs the owner's ≥60 fail labels (+18 tone, +17 affirms, +25 commits), and the loop can never do that part. Schedule it as owner labour, outside the fence.

---

## 5. Deferred or open, and why

| Item | Status | Why |
|---|---|---|
| Owner labelling pass (≥60 fail verdicts) | Open, **owner labour** | Required by DEC-302. No date was set in this session; T18.1 cannot start without it |
| T17.1 detailing | **Done 2026-10-21** by the builder (DEC-322) | `ROADMAP.md` T17.1 is the roster fix plus the draft-case deletion. The owner reviews it by 2026-10-27 |
| Rule 16 vs Rule 2 tie-break (T19.1) | Not asked | A product-behaviour call that only bites when T19.1 is detailed. Ask then |
| T18.2 baseline acceptance | Deferred to the time | A judgement on real kappa/adequacy numbers that don't exist yet |
| DemoGame-side repoint of `Scripts/check_contract_sync.py` | Outside this repo | DEC-298. It is a DemoGame-repo change; the engine loop cannot make it |
| Unreal WS wiring (`TODO(SLICE-2-WS)`) | Not an engine decision | DemoGame roadmap. DEC-299 makes it a pure client change |
| Frozen-path list | **Resolved by DEC-316** | The existing list would halt every TDD task. The task-session list is `evals/calibration/`, `evals/generations/k3_73e6c36/`, the loop machinery and the session instructions (T21.4) |
| New defects listed in review §6 ("propose logging") | Not logged here | Most fold into the pillar-fix theme. The builder logs any that no theme covers, per DEC-304 |
