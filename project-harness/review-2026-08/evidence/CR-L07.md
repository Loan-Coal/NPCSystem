# CR-L07 — Backlog health

Scope: `project-harness/ISSUES.md`, `DECISIONS.md`, `ROADMAP.md`, `HUMAN_TASKS.md`,
`SKILLS_QUEUE.md`, `PATTERNS.md`, `archive/ISSUES_RESOLVED.md`, and the other planning docs.
Repo at HEAD `d46ae42`, branch `eval-ab-context-arms`, 2026-08-27.

## Required measurements

### 1. Open-issue age distribution

Extracted every `**Found:**` date from `project-harness/ISSUES.md` (67 real entries — the raw
`grep -c "^## ISSUE-"` gives 68, but one match is the literal `## ISSUE-NNN: <short title>`
template line in the "how to log an issue" section, not a real issue).

```
n = 67, median age = 10 days, max age = 79 days, min age = 0 days
By month: 2026-06 → 4 issues, 2026-08 → 63 issues
```

| Age bucket | Count |
|---|---:|
| 0–7 days | 31 |
| 8–14 days | 14 |
| 15–30 days | 12 |
| 31–60 days | 5 |
| 61–90 days | 5 |

The backlog is heavily skewed young (median 10 days) — consistent with a burst of review
activity in the last two weeks, not with a long-neglected queue. The five 61–90-day outliers
are `ISSUE-083` (79d, P3, actively tracked with two dated updates — legitimately deferred, not
neglected), `ISSUE-092` (79d, P3, explicitly deferred to a future engine phase), `ISSUE-122`
(63d, P2 — see CR-L07-04, this one is neglected because it's wrong, not because it's hard),
`ISSUE-085` (79d, P3, `datetime.utcnow()` deprecation), and the `[WONTFIX]` `ISSUE-051` (86d,
never archived — see CR-L07-08).

### 2. P1 severity-inflation check

`grep -c '\*\*Severity:\*\* P1'` → **8**, but one hit is again the `ISSUE-NNN` template. **7 real
open P1s.** (The review brief's stated "~23 P1" does not match the file — see note below.)

| ID | Blocking? | Justification |
|---|---|---|
| ISSUE-155 | **Yes** | `verdict_sources.load_unified_rows` dedup bug corrupts every headline number computed via `summarize_from_dir`, still live in code. |
| ISSUE-156 | **Yes** | `_bucket_expectation` undercounts hallucination failures in the published headline metric, still live. |
| ISSUE-141 | **Yes** | `refusal_judge` chance-level agreement is cited as still-unresolved by the later `ISSUE-184` (2026-08-18, kappa 0.23/0.28) — invalidates any gate that trusts that judge. |
| ISSUE-176 | **Yes** | `check_conservation.py` still hardcodes the stale `k3_73e6c36` gen-dir as of this review (confirmed at `scripts/check_conservation.py:34-36`) — the `make check-conservation` gate audits nothing current. |
| ISSUE-129 | **Soft** | Judge-disagreement is a measurement-validity finding, not a runtime break; nothing currently gates on it. |
| ISSUE-171 | **No** | Pure governance/process gap (loop-queue moves lack a mechanical DEC-entry check) — no runtime or build breakage today. |
| ISSUE-145 | **No — stale** | Root cause fully diagnosed and fixed under `ISSUE-163`/`ISSUE-197` (both `[FIXED]`, archived); the fix is live in code (`context_score_extractors.py:228`, `NPC_SELF_STATE_KEYS`). See CR-L07-01. |

**Ratio: 4/7 (57%) currently block something concrete; 3/7 do not** (1 soft/credibility-only, 1
pure-process, 1 stale/already-fixed). See CR-L07-01, CR-L07-05.

### 3. DECs superseded / contradicted / never implemented (sampled)

**Sampling method:** stratified every-10th unreferenced-in-code DEC ID (n=12, IDs
002/013/026/045/062/074/086/113/132/151/173/200) out of 113 DEC numbers never grepped in
`src/`, `evals/`, `tests/`, `scripts/`, `demo_game/`, `seeds/`, `e2e/` — each checked against
current code.

| DEC | Verdict | Evidence |
|---|---|---|
| DEC-074 | **Stale, confirmed** | Waived `game_window.py` at 350 lines with "No further growth ... without a real extraction." File (now `demo_game/ui/layout/game_window.py`) is **925 lines** (2.6×) — verified with `wc -l`. No later DEC re-authorizes this. |
| DEC-086 | **Stale, confirmed** | Waived `quest_lifecycle_engine.py` at 305 lines, "Next editor must split before adding anything new." File (`src/npc_engine/engines/quest/quest_lifecycle_engine.py`) is **383 lines** — verified with `wc -l`. No follow-up DEC. |
| DEC-002 | Likely stale | `military_engine.py:34` `run_tick` now calls `resolve_battles`/`process_resource_yield`, contradicting DEC-002's "stub" description; no DEC documents the replacement. |
| DEC-132 | Likely never implemented | Decision named Kùzu evaluation + per-stage latency instrumentation as gated next steps; no `kuzu` import anywhere under `src/`, no dialogue-turn latency breakdown found. |
| DEC-013, 026, 045, 062, 113, 151, 173, 200 | Confirmed still accurate | Each checked against its named file/behavior and matches current code (e.g. DEC-113 → `pyproject.toml:77` `strict = true`; DEC-151 → all 10 named loop scripts exist). |

At n=12, 4/12 (33%) sampled DECs are stale or unimplemented. Extrapolated (not measured) over
113 unreferenced DECs this would be a meaningful fraction, but the true rate is unverified beyond
this sample — reported as **Likely**, not Confirmed, at the aggregate level.

### 4. Roadmap burn rate

Checked/unchecked (`- [x]` / `- [ ]`) line counts from `project-harness/ROADMAP.md` at the git
commit in effect at each weekly boundary (`git show <sha>:project-harness/ROADMAP.md`):

| Date | Commit | Checked | Unchecked | Total |
|---|---|---:|---:|---:|
| 2026-07-02 | d0f473d | 119 | 28 | 147 |
| 2026-07-09 | d0f473d | 119 | 28 | 147 |
| 2026-07-16 | d0f473d | 119 | 28 | 147 |
| 2026-07-23 | d0f473d | 119 | 28 | 147 |
| 2026-07-30 | d0f473d | 119 | 28 | 147 |
| 2026-08-06 | 427dd43 | 134 | 35 | 169 |
| 2026-08-13 | efbe7ce | 196 | 44 | 240 |
| 2026-08-20 | bdaa55b | 210 | 40 | 250 |
| 2026-08-27 | b9717ef | 210 | 65 | 275 |

Four flat weeks (07-02→07-30, zero roadmap commits), then a burst. **Arithmetic:** over the
active 8-week window, checked items grew 119→210 (+91, ≈11.4/week average) but total items grew
147→275 (+128) — the backlog is growing 40% faster than it's being cleared. The most recent week
(08-20→08-27) shipped **zero** newly-checked items while unchecked grew by 25 (+63%). An ETA
computed from the 8-week average (65 unchecked ÷ 11.4/week ≈ **5.7 weeks**) assumes no further
scope growth, which the last week's data directly contradicts — **no honest single-number ETA is
supportable**; the trend is currently diverging, not converging.

### 5. Counts

| Item | Count |
|---|---:|
| Open issues (real, excl. template) | 67 |
| — of which P1 | 7 (raw grep: 8, minus 1 template) |
| — of which P2 | 32 |
| — of which P3 | 30 |
| `[WONTFIX]` left un-archived in ISSUES.md | 2 (`ISSUE-051`, `ISSUE-138`) |
| Resolved-archive issues (`[FIXED]`) | 155 |
| Duplicate IDs within the archive itself | 2 (`ISSUE-035`, `ISSUE-056`, each used for two unrelated fixes) |
| DECISIONS.md `## DEC-` headings | 219 |
| — unique DEC numbers | 214 (5 numbers reused: 051, 052, 058, 073, 116 — 116 is an intentional "outcome" follow-up, the other 4 are true collisions) |
| DEC IDs referenced anywhere in `src/evals/tests/scripts/demo_game/seeds/e2e` | 101 unique (47%) |
| DEC IDs never referenced outside `project-harness/` | 113 unique (53%) |
| ROADMAP.md checked / unchecked | 210 / 65 (275 total) |

### 6. Duplicate / near-duplicate issues

- **`ISSUE-145` vs `ISSUE-163`** — true duplicate-by-supersession: `ISSUE-163` was opened
  "verifying the `ISSUE-145` fix end to end," found the real root cause, and was `[FIXED]`.
  `ISSUE-145` was never closed or cross-referenced. See CR-L07-01.
- **`ISSUE-171` / `ISSUE-173`** — same family (mechanical enforcement of process/queue
  discipline gaps), filed on the same day, not literal duplicates but overlapping remediation.
- **`ISSUE-219`/`ISSUE-220`/`ISSUE-221`/`ISSUE-222`** and **`ISSUE-224`/`ISSUE-225`** — clusters
  of related-but-distinct retrieval-probe defects found on the same day (P9, P10 sessions); not
  duplicates, but indicate one investigation session reliably produces 3-5 tickets, which is
  useful context for the burn-rate divergence in §4.
- **ID collisions** (`DEC-051/052/058/073`, `ISSUE-035/056` in archive) are a structural
  duplication problem distinct from content duplication — see CR-L07-02.

---

## Findings

### [CR-L07-01] `ISSUE-145` is a stale P1 whose root cause was already fixed under different IDs

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect (in the backlog process, not the engine)
- **Evidence:** `ISSUE-145` (`project-harness/ISSUES.md`, found 2026-08-10, still P1 "blocking...
  FOR HAND REVIEW") describes the exact defect that `[FIXED] ISSUE-163`
  (`project-harness/archive/ISSUES_RESOLVED.md:2697`) explicitly opened to verify ("Found:
  2026-08-14, during RET-P0 (verifying the ISSUE-145 fix end to end)") and root-caused: NPC
  self-state items (`beliefs`, `memories`, `top_need`) were scored at the graph horizon by
  `_infer_proximity_hops`, losing the tier-A budget. That fix is live: `src/npc_engine/retrieval/context/context_score_extractors.py:228`
  now special-cases `NPC_SELF_STATE_KEYS` with `SELF_STATE_PROXIMITY_HOPS`. The companion budget
  cause was separately `[FIXED]` as `ISSUE-197`. `ISSUE-145` itself carries no update note, no
  `[FIXED]` marker, and no cross-reference to either fix.
- **Cost of inaction:** Anyone triaging "open P1s" (7 total) counts a defect that is
  substantially resolved, inflates the perceived blocking-issue count by ~14%, and risks
  duplicate investigation of an already-closed root cause.
- **Fix sketch:** Re-verify `ISSUE-145`'s original repro (`GET /v1/admin/debug/retrieval`) against
  current code; if it now returns non-empty, mark `[FIXED] ISSUE-145 (superseded by ISSUE-163/197)`
  and move it to the archive per the CLAUDE.md issue-lifecycle rule.
- **Effort:** S (<2h)
- **Blast radius:** None — pure bookkeeping; does not touch running code.

### [CR-L07-02] `DECISIONS.md` and the archive reuse IDs, breaking the citation ledger

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Four DEC numbers head two unrelated decisions each: `DEC-051`
  (`DECISIONS.md:543` "S10.3 correct rumor marks..." vs `DECISIONS.md:1011` "run_scenes.py
  accepted over 300-line hard limit"), `DEC-052` (`:553` vs `:1018`), `DEC-058` (`:1036` vs
  `:1069`), `DEC-073` (`:457` vs `:1150`). The archive has the same pattern: `ISSUE-035`
  (`archive/ISSUES_RESOLVED.md:280` vs `:749`) and `ISSUE-056` (`:883` vs `:1197`) each label two
  unrelated fixes. `DEC-NNN` is cited 352 times across `src/evals/tests/scripts/...` — any citation
  of one of the 4 collided IDs is now ambiguous to a reader without opening `DECISIONS.md`.
- **Cost of inaction:** A future session citing e.g. "per DEC-073" in a commit message or code
  comment is unverifiable without manual disambiguation; this compounds every time the file grows.
- **Fix sketch:** Renumber the second occurrence of each collided ID to the next free number,
  add a one-line "renumbered from DEC-NNN, see DEC-MMM" pointer at the old anchor, and grep for
  any in-code reference to the renumbered ID to update it.
- **Effort:** S (<2h)
- **Blast radius:** Any code comment or doc citing the renumbered ID (grep first — none currently
  reference `DEC-051`/`052`/`058`/`073` per the code-reference scan in §5, so blast radius is
  effectively zero for this repo today).

### [CR-L07-03] Two file-size waivers in `DECISIONS.md` are silently violated, live on main

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `DEC-074` (`DECISIONS.md`) waived `game_window.py` at 350 lines with "No further
  growth should be allowed without a real extraction." Current file
  `demo_game/ui/layout/game_window.py` is **925 lines** (`wc -l`, verified) — 2.6× the waiver, no
  follow-up DEC. `DEC-086` waived `quest_lifecycle_engine.py` at 305 lines, "Next editor must
  split before adding anything new." Current `src/npc_engine/engines/quest/quest_lifecycle_engine.py`
  is **383 lines** (`wc -l`, verified) — 25% over, no follow-up DEC. Neither file's module
  docstring carries a justifying comment referencing the current size, as CLAUDE.md's own file-limit
  rule requires ("write a justifying comment at the top... and add an entry to DECISIONS.md").
- **Cost of inaction:** The 300-line hard limit is stated in `project-harness/CLAUDE.md` as
  "not a suggestion... violating it is a bug" — these two files are currently in that state with
  no paper trail, so the rule is unenforced exactly where it says it is strictest.
- **Fix sketch:** Either split `game_window.py` (a `RenderLayer`/poller-registry extraction is
  already named as the intended relief valve in `DEC-074`) or write the new waiving DEC
  acknowledging the current size; same for `quest_lifecycle_engine.py`.
- **Effort:** M (<1d) for the DEC-only path; L for an actual split.
- **Blast radius:** `game_window.py` is the demo's central event-loop coordinator (imported by
  `demo_game.__main__`); a split touches all poller wiring. `quest_lifecycle_engine.py` split
  touches the quest engine's public surface.

### [CR-L07-04] `ISSUE-122` prescribes a fix that was already present when the issue was filed

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect (in the ticket, not the code)
- **Evidence:** `ISSUE-122` (found 2026-06-25) claims `docker-compose.yml`'s `app` service "has
  no restart policy" and prescribes adding `restart: on-failure` plus
  `depends_on: neo4j: condition: service_healthy`. `git show ae3dc78:docker-compose.yml` — the
  commit in effect on the issue's own found-date — already contains both:
  `restart: on-failure:5` and `depends_on: { neo4j: { condition: service_healthy } }`. Both are
  still present in the current `docker-compose.yml:78-80`. The line has been present continuously
  since it was first added at `4dc797a` (2026-05-05), a month before the issue was filed.
- **Cost of inaction:** The ticket has sat open 63 days; anyone who picks it up to "fix" it will
  find nothing to do and waste time re-diagnosing the real cause (most likely the stale
  non-bind-mounted app image noted separately in session memory) instead of the compose file.
- **Fix sketch:** Re-diagnose against the actual failure mode (stale image / build-not-rebuilt),
  correct or close `ISSUE-122`, and re-file against the real cause if still reproducible.
- **Effort:** S (<2h)
- **Blast radius:** None — documentation-only correction.

### [CR-L07-05] Roadmap completion trend is diverging, not converging

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** See §4 table. Checked items: 119→210 over 8 weeks (+91). Total items (checked +
  unchecked): 147→275 (+128). The most recent week added 25 new unchecked items and 0 new checked
  ones. A backlog that grows 40% faster than it clears, and just posted a zero-completion week,
  cannot support a single honest "N weeks to done" estimate.
- **Cost of inaction:** Any roadmap status reported upward (e.g. "5.7 weeks to zero") using the
  naive average will be wrong in the direction of false confidence, exactly when the trend just
  inverted.
- **Fix sketch:** Report burn rate as a range bracketing both the historical average and the
  most recent week (roughly 0–11/week), and flag scope growth explicitly in `ROADMAP.md`'s own
  status header rather than only tracking checked/unchecked counts.
- **Effort:** S (<2h)
- **Blast radius:** None — reporting change only.

### [CR-L07-06] Over half of DECISIONS.md is unreferenced outside project-harness, and a sample shows real drift

- **Severity:** MEDIUM
- **Confidence:** Likely
- **Kind:** Debt
- **Evidence:** 113 of 214 unique DEC numbers (53%) never appear in `src/`, `evals/`, `tests/`,
  `scripts/`, `demo_game/`, `seeds/`, or `e2e/` (grep, see §5). A stratified n=12 sample of these
  unreferenced IDs found 2 confirmed-stale waivers (CR-L07-03) and 2 further likely-stale/
  unimplemented decisions (`DEC-002`, `DEC-132`) — a 33% stale rate in the sample. Not all 113 are
  expected to have code references (many are pure process/meta decisions), so the 53% figure is
  not itself a defect count, but the sampled stale rate suggests the file needs a re-validation
  pass, not just growth.
- **Cost of inaction:** DECISIONS.md is meant to let "future maintainers judge edge cases without
  re-deriving the rationale" (its own header) — a maintainer trusting a stale entry will make the
  wrong call.
- **Fix sketch:** A single pass re-verifying line-count waivers (`DEC-*.*-line*` entries are
  mechanically checkable with `wc -l`) would catch the cheapest class of drift; extend the n=12
  sample before trusting the 53% figure as a defect rate.
- **Effort:** M (<1d) for the mechanical line-count pass alone.
- **Blast radius:** None — audit only.

### [CR-L07-07] Three scripts share one hardcoded stale corpus default; only one is tracked

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `ISSUE-176` tracks `scripts/check_conservation.py:34-36`'s hardcoded
  `_DEFAULT_GEN_DIR = .../k3_73e6c36`. The identical pattern exists, untracked, in
  `scripts/check_dead_keywords.py:35` and `scripts/check_label_survival.py:27` (both hardcode
  the same `k3_73e6c36` path as a default gen-dir). `ISSUE-186` independently documents that
  `k3_73e6c36`'s own metadata (`harness_version`, `seed`) is null and structurally unfit as a
  baseline — three separate `make check` gates default to auditing it.
- **Cost of inaction:** Fixing only `ISSUE-176`'s named file leaves two gates
  (`check-dead-keywords`, `check-label-survival`) silently auditing the same stale, metadata-null
  corpus after any regeneration.
- **Fix sketch:** Factor the default gen-dir resolution into one shared helper (e.g. "latest
  gen-dir under `evals/generations/`") and have all three scripts call it instead of each
  hardcoding the literal.
- **Effort:** S (<2h)
- **Blast radius:** Three `make check` gate scripts; low risk, mechanical.

### [CR-L07-08] `SKILLS_QUEUE.md` is dead for ~90 days while still normatively referenced

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `git log -1 --format=%ad -- project-harness/SKILLS_QUEUE.md` → `2026-05-29`.
  `project-harness/CLAUDE.md:306` still tells contributors that undecided questions "go in
  `DECISIONS.md` or `SKILLS_QUEUE.md`." In the same ~90-day window, `DECISIONS.md` grew by over
  100 entries and `PATTERNS.md` was touched as recently as 2026-08-22. No `DECISIONS.md` entry
  documents deprecating or superseding `SKILLS_QUEUE.md` (`grep -in SKILLS_QUEUE
  project-harness/DECISIONS.md` → no hits).
- **Cost of inaction:** Low — but the file misleads a new contributor into thinking it's an
  active queue, and its 13 recorded skill-opportunity entries (last dated 2026-05-27) are aging
  out of relevance unreviewed.
- **Fix sketch:** Either resume using it, or add one `DECISIONS.md` entry retiring it and update
  the `CLAUDE.md:306` pointer.
- **Effort:** S (<2h)
- **Blast radius:** None.

---

## Other planning docs — live vs abandoned (by last git touch)

| File | Last touch | Status |
|---|---|---|
| `EVAL_STRATEGY.md` | 2026-05-28 | Abandoned (91 days) |
| `SKILLS_QUEUE.md` | 2026-05-29 | Abandoned (90 days) — see CR-L07-08 |
| `HARNESS_GATES.md` | 2026-06-03 | Abandoned (85 days) |
| `BATCH5_RESPONSE_MODEL.md` | 2026-06-04 | Abandoned (84 days) |
| `eval_roadmap_session_prompt.md`, `UNREAL_DEFERRED.md` | 2026-07-31 | Explicitly deferred / one-shot prompt, not live |
| `OVERNIGHT_LOOP_PLAN.md` | 2026-08-01 | Likely superseded by `OVERNIGHT_LOOP.md` (2026-08-09) |
| `EVAL_P20_TO_P24_UNBLOCK_PLAN.md`, `PROMPT_P23_UNBLOCK.md` | 2026-08-15/18 | Phase-complete artifacts; roadmap has moved to `EVAL_P25_TO_P31_PLAN.md` |
| `MORNING_HANDOFF_PHASE1.md` | 2026-08-18 | Likely superseded by `MORNING_HANDOFF_COMBINED.md` (2026-08-26) |
| `HUMAN_TASKS.md`, `human_verification.md`, `soft_review.md` | 2026-08-15 | Referenced by name in `ROADMAP.md`'s HUMAN GATE mechanism; still live |
| `PATTERNS.md` | 2026-08-22 | Live |
| `MORNING_HANDOFF_COMBINED.md`, `HANDOFF_TRACK_A/B.md`, `EVAL_P25_TO_P31_PLAN.md`, `PROMPT_P25_*`, `PROMPT_P26_INTEGRATION.md`, `ISSUES.md`, `DECISIONS.md`, `ROADMAP.md` | 2026-08-26/27 | Live, current session set |

`project-harness/` itself carries **48,988 lines of Markdown across 253 tracked files** (measured
by the sibling synthesis file `project-harness/CODEBASE_REVIEW.md` at time of writing) against
68,218 Python LOC in `src/npc_engine/` — a planning-to-code ratio worth noting for whoever owns
process overhead, though sizing that tradeoff is outside this lens's scope.

**Note on the review brief's own numbers:** the brief states "~68 open, ~23 P1" — the real counts
are 67 open / **7 P1** (raw grep before excluding the template line: 68/8). The brief's P1 count
is off by more than 3×; treat any other un-verified count in review tooling with the same
skepticism applied here.
