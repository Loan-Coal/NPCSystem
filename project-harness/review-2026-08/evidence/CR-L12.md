# CR-L12 — Product coherence

Lens L12 of the 16-lens review. Branch `eval-ab-context-arms`, HEAD `d46ae42`, audited 2026-08-28.
Read-only; no source file was modified. Live API at `http://127.0.0.1:8000` used for read-only probes
(`Authorization: Bearer $API_KEY_SECRET` from `.env`). Sibling lenses CR-L01, CR-L02, CR-L03, CR-L07,
CR-L10, CR-L13, CR-L16 are cited, not re-derived.

**Verdict in one line:** this repository is an eval-research project that is building an increasingly
rigorous measuring instrument for a game engine whose signature feature does not work
(CR-L01-01/02), whose headline number is beaten by a fixed string (CR-L03-01), whose only shipping
artifact has never once been buildable, and which has no integrator, no pilot, and no second human.

---

## Required measurements

### 1. Convergence — licensable middleware, or an eval research project?

**Verdict: an eval research project. The product roadmap was formally deferred on 2026-07-31 and has
not been touched since.** The project says so itself.

`project-harness/UNREAL_DEFERRED.md:3-7`:

> **Moved out of `ROADMAP.md` on 2026-07-31**, during the eval-program planning session.
> **Why:** the active program is the eval pipeline (`ROADMAP.md` → *Active — Eval pipeline
> (EVAL-P0..P7)*). Everything below is **game-client integration work** — it is neither the
> engine nor its evals, and none of it is being worked on.

What was moved into that file: the Unity setup screen (SHIP-05b), the legible emergent hook
(SHIP-06), the talk-to-NPC client (SHIP-07), the 10-minute arc (SHIP-08), public distribution
(SHIP-09), the instrumentation/perf one-pager for the pitch (SHIP-10), the marketing clip (SHIP-11),
and all four Engine-SDK steps (SX.1 OpenAPI freeze, SX.2 Unity C# package, SX.3 Unreal plugin,
SX.4 sample scenes). **12 unchecked boxes, 119 lines, zero commits since.**

The framing that block sits under is retained verbatim in the same file (`UNREAL_DEFERRED.md:110-115`):

> **End goal: license the engine to studios (B2B).** … the near-term deliverable is a **small,
> downloadable, distributable demo game** … instrumented for the pitch.

That deliverable is 0% built.

**ROADMAP.md composition.** Every `## Active` / `## Program` heading in the live roadmap:

| Roadmap section (`project-harness/ROADMAP.md`) | Line | Subject |
|---|---:|---|
| Active — Eval suite redesign (EVAL-B2..FINAL) | 39 | evals |
| Active — Eval pipeline (EVAL-P0..P7) ← *"the current program"* | 122 | evals |
| Program 2 — Metric validity and the portfolio artifact (P9..P14) | 1120 | evals |
| Program 3 — Audit remediation and the regression harness (P15..P24) | 1600 | evals |
| Program 4 — The golden set rebuild and judge repair (P25..P28) | 3449 | evals |
| Program 5 — The first-class prompt arm (P29..P31) | 3540 | evals |
| Active — Folder reorganisation (REORG-PR6..PR9) | 3616 | harness |
| Active — ISSUES.md remediation program (REM-*) | 3639 | harness |

**Eight active programs, eight of them eval or harness meta-work. Zero product programs.** This is
the composition, not a sample of it. It corroborates the brief's 71% figure from a different angle:
71% of *items* are eval meta-work because 100% of *programs* are.

**Churn, last 200 commits** (`--no-merges`, file-touches; independently reproduced this session,
matches the brief to within rounding):

| Area | file-touches |
|---|---:|
| `evals/` | 393 |
| `tests/` | 322 |
| `project-harness/` | 288 |
| `src/npc_engine/` | 172 |
| `docs/` | 22 |
| `demo_game/` | **8** |
| `packaging/` | **1** |

**Commits, last 8 weeks (233 total):**

```
$ git log --since='8 weeks ago' --oneline -- <dir> | wc -l
project-harness  184      src         42
tests            149      scripts     38
evals            100      docs        20
                          demo_game    4
                          e2e          2
                          packaging    0
```

**Commit subjects, last 8 weeks, by conventional-commit scope:** `evals`/`eval` = **107 / 233 (46%)**;
add `harness`, `loop`, `roadmap` = **177 / 233 (76%)**. Everything touching engine code —
`retrieval`, `config`, `engines`, `dialogue`, `api`, `world`, `llm`, `seeds`, `quest` — totals
**33 / 233 (14%)**, and CR-L02-07 already established that 100% of the roadmap items that touch
engine code require editing an existing file rather than adding one.

**Size.** Product/demo/eval LOC is 54% / 29% / 16% (68,218 / 36,961 / 20,141 — the brief's corrected
figures, re-confirmed: `git ls-files demo_game | grep '\.py$' | xargs wc -l` → `36961 total`). But the
governing artifact is not code:

```
$ git ls-files project-harness | grep '\.md$' | xargs wc -l | tail -1
  48988 total          (246 tracked markdown files, 215 of them under archive/)
```

**48,988 lines of process markdown — 72% the line count of the entire engine source tree**, and
CR-L10-06 confirms the top-3 all-time churned files in the repo are all harness markdown.

**The forcing numbers:** 8 of 8 active roadmap programs are eval/harness. 76% of eight weeks of
commit subjects are eval/harness. `demo_game` 8 file-touches and `packaging` 1 in 200 commits. The
entire game-client program was moved to a deferred file 28 days ago and has had zero commits since.

---

### 2. What a game studio integrating this would need that does not exist

| # | Gap | Evidence it is absent | Blocks a pilot, or only GA? |
|---|---|---|---|
| G1 | **Unity C# package / Unreal C++ plugin** — the two clients `BUSINESS_REQUIREMENTS.md:21-22` names | `git ls-files \| grep -icE '\.(cs\|cpp\|h\|hpp\|uplugin\|asmdef)$'` → **0**. SX.2/SX.3 unchecked in `UNREAL_DEFERRED.md:63-65` | **Pilot.** A studio cannot start without writing the client themselves. |
| G2 | **A buildable distributable** — `docs/INTEGRATION.md:12-18` tells Unity to spawn `launcher.exe` | `packaging/npc_engine.spec:29-30` references `REPO_ROOT/"config"` and `REPO_ROOT/"game_schema.yaml"`; **neither exists, and neither existed at the spec's own introducing commit** (`git ls-tree 54e3a19 --name-only` → absent; `git log --all -- game_schema.yaml` → empty). PyInstaller is in no dependency set (`pyproject.toml:24-30`) and not installed. No CI job builds it. See CR-L12-02. | **Pilot.** There is no artifact to hand over. |
| G3 | **A frozen, versioned HTTP contract** — 148 operations over 132 paths, live | Total policy in the repo is one sentence: `docs/INTEGRATION.md:6` *"Routes and shapes may evolve; breaking changes will be announced."* No deprecation policy, no `/v2`, no contract test against a published spec. SX.1 (OpenAPI freeze) unchecked. Root `live_openapi.json` is 64 days stale (CR-L13-11); `docs/API.md` is missing 6 live routes (CR-L13-09, reproduced below). | **GA**, if the pilot partner tolerates breakage. |
| G4 | **Working reference behaviour for the feature being sold** | `docs/DEMO_SCRIPT.md:147` *"Each hop introduces deterministic distortion."* — CR-L01-01/02 confirm distortion never compounds across hops and the gossip write overwrites seeded distortion back to 0. | **Pilot.** See CR-L12-04. |
| G5 | **Any evidence of behaviour at contract scale** | Four of five NFRs never measured; graph is 190x below its stated node target. See §4. | **Pilot** for a studio with >52 NPCs, i.e. all of them. |
| G6 | **An error contract for a dependency outage** | The documented Neo4j-outage→503 path does not exist: `grep -rn "503" src/npc_engine/api/` → 0 (CR-L02-01); dialogue turns a Neo4j outage into a canned HTTP 200 (CR-L01, `degradation.py:107,119`). A studio cannot distinguish "backend down" from "NPC is being terse." | **Pilot.** |
| G7 | **A boot a studio engineer can perform** | Fresh clone does not boot on Windows without two undocumented fixes; three mutually contradictory setup docs (CR-L16-01, CR-L16-02). | **Pilot.** |

**Not gaps** (checked, and they are fine for the DEC-068 one-deployment-per-studio model): auth is a
shared per-deployment bearer secret and `BUSINESS_REQUIREMENTS.md:80-86` says exactly that;
rate limiting exists (`src/npc_engine/api/rate_limit.py`, in-memory token bucket per API key);
idempotency is header-enforced and documented (`docs/INTEGRATION.md:154-160`).

`docs/API.md` route-coverage check, reproduced independently against the live server:

```
live paths: 125   doc-referenced paths: 126   live-but-undocumented: 6
    /setup/config, /setup/validate, /v1/admin/debug/vector-store,
    /v1/admin/factions/{}/standings/{}, /v1/admin/schedules/character/{}/at,
    /v1/admin/vector-store/rehydrate
```

Exactly CR-L13-09's six. Cited, not claimed as new.

---

### 3. Top 3 gaps between the stated product and the built artifact

Ranked by how much they would surprise a buyer in the room.

| # | Documented claim (quoted, with file:line) | Measured reality |
|---|---|---|
| **1** | `docs/DEMO_SCRIPT.md:147` — *"tells Henryk. Each hop introduces deterministic distortion."* `:109` — *"One hop later. Faction name already garbled — the distortion engine ran."* `README.md:16` — *"Gossip engine (deterministic distortion, KNOWS_ABOUT propagation) ✅"* | Distortion **never compounds across hops** — `gossip_batch_queries.py:29-47` returns the canonical event summary, not the sharer's distorted one, and the gossip write overwrites seeded distortion back to 0 (CR-L01-01, CR-L01-02, both Confirmed). The 2-hop chain in the pitch is **hand-seeded**. The buyer is watching a fixture, narrated as an engine. |
| **2** | `README.md:56-71` requires every published rate to carry a machine-checked citation; the guard rate is the number the anti-hallucination story rests on | A **null responder emitting one fixed string scores 0.949 on the guard battery vs the engine's 0.897** (CR-L03-01, Confirmed). The number the product is sold on is not a measurement of the product. Two of four scorers are REFUSED by the project's own policy; not one has a κ interval excluding chance (CR-L03). |
| **3** | `docs/DEMO_SCRIPT.md:185-187` — *"This is middleware. Studio integration is a single API call. The knowledge graph, five engines, and streaming dialogue license as a bundle."* `BUSINESS_REQUIREMENTS.md:11` — *"designed as a plugin for both Unity and Unreal Engine games."* | **148 operations across 132 live paths**, six of them undocumented; **zero lines of C# or C++** in the tree; **no plugin, no SDK, no sample scene**; and the only packaging artifact has never been buildable (CR-L12-02). "A single API call" and "a plugin" are both untrue of the artifact as it stands. |

---

### 4. Non-functional requirements vs. reality

Targets from `docs/BUSINESS_REQUIREMENTS.md:34-38`. These five strings appear **nowhere else in the
tree except archived intent docs** — `grep -rniE "pairs/tick|10,?000 nodes|99\.5"` over all `.py`/`.md`
returns only `BUSINESS_REQUIREMENTS.md` and `project-harness/archive/2026-06-18-shipped-programs/`.
`git ls-files | grep -iE "bench|load_?test|locust|perf"` returns one eval **case** YAML and no benchmark.

| NFR | Target | Measured anywhere? | Ever met? |
|---|---|---|---|
| Gossip tick throughput | ≥ 200 NPC pairs / tick | **No.** No benchmark exists. The largest `max_pairs` value used anywhere in the repo — source, tests, evals, fixtures — is **20** (`gossip_handler.py:114` default; `api/routes/admin/batch.py:30` `Field(default=20, ge=1, le=500)`). The API will accept 200; nothing has ever sent it. | **Unknown, 10x untested.** |
| Knowledge graph size | ≥ 10,000 nodes | **Yes, this session, against the live seeded world:** `GET /v1/graph/nodes/{Character,Event,Location}?limit=1000` → **23 + 12 + 17 = 52 nodes**. No test or seeder in the tree creates >100 nodes (largest seeder: `src/npc_engine/data/seed_data.py`, 27 ids). | **No — 0.5% of target.** |
| Service uptime | 99.5% during active sessions | **No.** No SLO, no uptime probe, no restart history. `/v1/admin/system/metrics` counts requests in-process and resets on restart. CR-L16-07 confirms the `app` container has **no healthcheck**. | **Unmeasurable as built.** |
| LLM fallback on timeout | < 100 ms (serve canned) | **Yes, measured this session** (`get_canned_response`, `prompts/canned/merchant.yaml`, n=21): **median 0.687 ms, max 0.886 ms**. | **Met — and the metric is the wrong one.** Player-visible fallback latency is `LLM_TIMEOUT_SECONDS` (default **10.0**, `config.py:104`) **+ 0.7 ms**. The NFR measures the cheap half. |
| Test coverage | ~70% line on non-prompt code | **Yes.** `python -m coverage report` on the committed `.coverage`: `TOTAL 23789 stmts, 3405 miss, **85.7%**`. Gated at `--cov-fail-under=80` in `make test-cov`, which CI runs. | **Met.** |
| (same row) "100% pass on `make eval` (Layer 1+2)" | | See CR-L03: the instrument is invalid (CR-L03-01), two gates audit a superseded generation (CR-L03-07), and 1,522 lines of the newest gate layer are reachable from no `make` target (CR-L03-04). | **Not meaningfully assessable.** |

**Score: 1 of 5 NFRs measured and met (coverage). 1 met on a technicality that measures the wrong
half (fallback). 3 never measured, one of them 190x off.**

---

### 5. `demo_game/` — what is it for now?

**Verdict: it is not abandoned, it is not broken, and it is not a subtraction candidate. It has been
silently repurposed from sales demo into the eval program's world-fixture generator, and CI does not
run a single one of its 1,116 tests.**

Evidence it still runs (both commands executed this session):

```
$ python -m pytest demo_game/tests/ -q
1116 passed, 30 warnings in 9.28s

$ python -m demo_game.runners.run --dry-run
  === Demo complete. 12 acts. ... ===
[done] 0.0s elapsed
```

Evidence it is frozen: last **feature** commit `e975215 feat(G2.2): demo intrigue board` on
**2026-06-13 — 76 days ago**. The four commits since are `chore: restore the line endings my own edits
rewrote across P8`, a `feat(graph)` embedding change that swept it up, one `fix(demo)` restore-guard,
and a model-tag rename. 8 file-touches in 200 commits.

Evidence it is load-bearing for the *eval* program, not the sales pitch:

- `Makefile:627` builds the eval baseline fixture `evals/fixtures/eval_world_baseline.json` by running `python -m demo_game.snapshot`.
- `evals/anti_hallucination_runner.py:30` depends on "the demo-world player that `demo_game.seed` always creates."
- `tests/unit/api/test_client_paths_phase2.py:17`, `tests/unit/api/test_interaction_phase1.py:25`, and
  `tests/unit/config/test_seed_chain_quests.py:19` import from `demo_game` — and those tests run inside
  `make test-cov`, which **is** CI-gated.

Evidence it is off the revenue path: it is a **pygame** app. `BUSINESS_REQUIREMENTS.md:21-22` names
Unity (C#) and Unreal (C++) as the target clients; DEC-125 selected Unity. The revenue artifact
described in `UNREAL_DEFERRED.md:110-115` is a *different, Unity* demo game that does not exist.

Evidence it is ungated: `grep -c "test-demo\|demo_game\|package" .github/workflows/ci.yml` → **0**.
`make check` (`Makefile:200`) does not include `test-demo`. 36,961 lines and 1,116 tests are verified by
nobody except a human who remembers to type `make test-demo`.

Subtraction verdict: **do not subtract it** — it is wired into the gated test suite and the eval
fixture pipeline, and it is the only working demonstration of the product that exists. The largest
genuine subtraction candidate in the repo is not code: **48,988 lines of `project-harness/` markdown,
215 of whose 246 tracked files are already under `archive/`**.

---

### 6. Is there a customer, a pilot, or a design partner?

**No. There is not, and nothing in the tree or history suggests there ever has been.**

```
$ git log --pretty=format:"%an <%ae>" | sort | uniq -c
    967 Lohann Colle <lohanncolle2022@gmail.com>
```

**967 commits, one author, zero external contributors.** `git remote -v` → one personal GitHub
remote. A tree-wide grep for `design partner|pilot customer|pilot studio|first customer|prospect|
licensee|LOI|letter of intent|NDA|contract signed|invoice|trial account|tenant` across all `.md` and
`.py` returns **zero** hits that are not in-game dialogue transcripts about bribing a gate guard.

Every occurrence of "studio" in a business sense is either aspirational pitch copy
(`docs/DEMO_SCRIPT.md:187`) or lives in `project-harness/archive/2026-06-18-shipped-programs/`, i.e.
it was archived 71 days ago. There is one reference to a "Munich demo"
(`archive/.../briefs/EXP-12-relation-delta-audit-log.md:8`) — a hackathon, not an integrator.

**Why this changes the rest of the review:** with no integrator, nothing in this repo has an external
deadline or an external definition of "done." That is the mechanism behind CR-L07-05 (roadmap
completion diverging), CR-L10-06 (30% of commits are pure process bookkeeping), and CR-L10-07
(loop-driven velocity). The eval harness is the only thing supplying a success criterion, which is
precisely why the tree has spent eight weeks growing one — and why CR-L03-01 (the harness's own
headline is beaten by a fixed string) is the most expensive defect in the repository.

---

## Findings

### [CR-L12-01] Restore one product program to `ROADMAP.md`, or state in writing that the product is paused

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `project-harness/UNREAL_DEFERRED.md:3-7` moved all 12 game-client items out of the roadmap on 2026-07-31 "because the active program is the eval pipeline"; `packaging/` has had **0 commits in the last 8 weeks and 1 file-touch in 200 commits** since. All 8 `## Active`/`## Program` headings in `ROADMAP.md` (lines 39, 122, 1120, 1600, 3449, 3540, 3616, 3639) are eval or harness meta-work; **zero** are product. 76% of 233 commit subjects in the last 8 weeks are eval/harness-scoped; 14% touch engine code; 4 commits touch `demo_game`.
- **Cost of inaction:** The measuring instrument keeps improving and the thing being measured does not. Concretely: by the time Programs 4 and 5 (EVAL-P25..P31) land, the engine will still have a no-op signature feature (CR-L01-01), no client SDK, and no buildable artifact — and another ~8 weeks of the only engineer's time will be spent. The failure is silent because no external party is waiting.
- **Fix sketch:** Pick one: either move `SHIP-06` (the one legible emergent hook, end-to-end) back into `ROADMAP.md` above the loop fence and let the loop starve until it lands, or add an explicit `## Paused — product` heading to `ROADMAP.md` saying the B2B track is deliberately stopped and naming the resume condition. The current state — deferred in a side file the loop cannot see — is the worst of both.
- **Effort:** S (the decision) / XL (the work it unblocks)
- **Removes:** 0 lines
- **Blast radius:** `ROADMAP.md`, `UNREAL_DEFERRED.md`, the `roadmap_cursor.py --verify` span, a DECISIONS entry.

### [CR-L12-02] `make package` has never been buildable — the PyInstaller spec references two paths that have never existed

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `packaging/npc_engine.spec:29-30` lists `datas` entries `(str(REPO_ROOT / "config"), "config")` and `(str(REPO_ROOT / "game_schema.yaml"), ".")`.
  ```
  $ python -c "from pathlib import Path; R=Path('.').resolve(); [print(p, p.exists()) for p in (R/'src/npc_engine/prompts', R/'config', R/'game_schema.yaml')]"
  ...\src\npc_engine\prompts  True
  ...\config                  False
  ...\game_schema.yaml        False
  ```
  Not merely stale — they were **already absent at the spec's own introducing commit**:
  ```
  $ git ls-tree 54e3a19 --name-only | grep -E "^(config|game_schema.yaml)$"    → (empty)
  $ git log --all --oneline -- game_schema.yaml                                → (empty; the file has only ever lived at src/npc_engine/game_schema.yaml)
  ```
  PyInstaller is absent from `pyproject.toml:24-30` `[dev]` and from the venv (`ModuleNotFoundError: No module named 'PyInstaller'`). No CI job runs `make package` (`grep -c package .github/workflows/ci.yml` → 0). `dist/` is not even in `.gitignore` — the target has never produced output.
- **Cost of inaction:** The entire distribution story — DEC-128, SHIP-04, and `docs/INTEGRATION.md:12-18`'s "game.exe spawns launcher.exe" — is documented, decided, and non-existent. The day a studio asks for a build, there is nothing to send and the first attempt to make one fails on a two-month-old path error. This is the cheapest-to-fix item that blocks a pilot outright.
- **Fix sketch:** Repoint the two `datas` entries at `src/npc_engine/config` and `src/npc_engine/game_schema.yaml`, add `pyinstaller` to a `[project.optional-dependencies] package` extra, and add one CI job that runs `make package` and asserts the binary starts and answers `GET /health`. Note the launcher binds **8080** (`stack_launcher.py:37`) while every make target, eval and doc example uses **8000** — the packaged path has never been exercised end to end.
- **Effort:** M
- **Removes:** 0 lines / 0 files (adds ~15 lines of CI)
- **Blast radius:** `packaging/npc_engine.spec`, `pyproject.toml`, `.github/workflows/ci.yml`, `.gitignore`; `docs/INTEGRATION.md` §1 if the port is unified.

### [CR-L12-03] Ship a thin Unity C# client, or stop naming Unity and Unreal as target clients

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `docs/BUSINESS_REQUIREMENTS.md:19-23` tabulates Unity (C#) and Unreal (C++) as the two target clients. `git ls-files | grep -icE '\.(cs|cpp|h|hpp|uplugin|asmdef)$'` → **0**. All four SDK steps are unchecked and deferred (`UNREAL_DEFERRED.md:63-65`: SX.1 OpenAPI freeze, SX.2 Unity C# package, SX.3 Unreal plugin, SX.4 sample scenes). The only client in the tree is `demo_game/` — 36,961 lines of **pygame**, which is neither.
- **Cost of inaction:** Every hour spent on eval rigour is spent on a claim ("NPCs that remember") that a studio cannot evaluate without first writing the HTTP client, the WS reconnect logic, the auth header handling and the model bindings themselves — against a 148-operation surface with no frozen contract (CR-L12-07). The pitch line `docs/DEMO_SCRIPT.md:187` "Studio integration is a single API call" is false today and will read as a bluff in the first technical call.
- **Fix sketch:** SX.2 as a deliberately minimal slice: one C# file wrapping `POST /v1/dialogue`, `GET /v1/npc/{id}/state` and `POST /v1/clock/advance`, with the `ErrorEnvelope` shape and a bearer header — not the full surface. That is the smallest artifact that makes the "plugin" claim non-fiction.
- **Effort:** L
- **Removes:** 0 lines
- **Blast radius:** New top-level `sdk/` tree; `docs/INTEGRATION.md`; forces SX.1 (contract freeze) to at least a versioned snapshot.

### [CR-L12-04] The pitch narrates a hand-seeded fixture as a working engine

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `docs/DEMO_SCRIPT.md:147` — *"tells Henryk. Each hop introduces deterministic distortion."*; `:109` — *"One hop later. Faction name already garbled — the distortion engine ran."*; `:161` — *"The engine tracked every distortion hop."*; `README.md:16` marks the gossip engine ✅; `docs/ENGINES.md:102` advertises "deterministic distortion (omission, exaggeration, role-swap, timeline-shift) … Fully reproducible (seeded)." CR-L01-01 and CR-L01-02 are both Confirmed: `gossip_batch_queries.py:29-47` returns the canonical event summary rather than the sharer's distorted one, so distortion cannot compound, and the gossip write overwrites seeded distortion back to 0. The `captain_sorn → mira_innkeeper → old_henryk` chain in the script is hand-seeded (`project-harness/CLAUDE.md`, demo-world table).
- **Cost of inaction:** This is the one demo moment a buyer will try to reproduce on their own world, and it is the first thing that will fail. The reputational cost of a narrated fixture is categorically worse than the cost of a missing feature — it converts a gap into a credibility question about every other ✅ in `README.md`.
- **Fix sketch:** Until CR-L01-01 lands, change `DEMO_SCRIPT.md:147/161` to state that the two-hop chain is seeded illustration, not live propagation. After it lands, revert. Do not run the demo for an external audience in between.
- **Effort:** S (the doc honesty) / M (CR-L01-01 itself)
- **Removes:** 0 lines
- **Blast radius:** `docs/DEMO_SCRIPT.md`, `docs/ENGINES.md:102`, `README.md:16`; overlaps CR-L01-01/02 remediation.

### [CR-L12-05] Four of five NFRs have never been measured; the graph target is off by 190x and the throughput target is 10x untested

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `docs/BUSINESS_REQUIREMENTS.md:34-38`. The five target strings occur nowhere else in the tree except `project-harness/archive/2026-06-18-shipped-programs/`. No benchmark file exists (`git ls-files | grep -iE "bench|load_?test|locust|perf"` → one eval **case** YAML). Live graph measured this session: **52 nodes** (23 Character + 12 Event + 17 Location) against a **≥10,000** target. Largest `max_pairs` value used anywhere in source, tests, evals or fixtures: **20** (`gossip_handler.py:114`, `api/routes/admin/batch.py:30`), against a **≥200 pairs/tick** target. No uptime telemetry exists and the `app` container has no healthcheck (CR-L16-07). Coverage is the one target genuinely met: `coverage report` → `TOTAL 23789 3405 85.7%`, gated at 80% in CI.
- **Cost of inaction:** The first pilot world will be an order of magnitude larger than anything ever run. Failure modes at 10k nodes — Cypher plan degradation in `select_pairs`, the in-process `emotion_store`/`session_store` singletons (CR-L02-03), the in-memory rate-limit buckets, the token budget guard frozen against constants measured on a 52-node world (CR-L01-07) — are all unmeasured. These surface during the pilot, not before it.
- **Fix sketch:** One script that seeds N synthetic characters/events/locations and runs a single gossip tick at `max_pairs=200`, reporting wall-clock and Neo4j round-trips at N ∈ {100, 1000, 10000}. That is the whole gap — it is a script, not a program. Then either record the real numbers in `BUSINESS_REQUIREMENTS.md` or restate the targets to what the engine actually does.
- **Effort:** M
- **Removes:** 0 lines
- **Blast radius:** New `scripts/` benchmark; `docs/BUSINESS_REQUIREMENTS.md:34-38`; likely surfaces graph-layer work.

### [CR-L12-06] There is no integrator, and nothing in the repo supplies an external definition of "done"

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `git log --pretty="%an <%ae>" | sort | uniq -c` → **967 Lohann Colle**, single author, zero external contributors. `git remote -v` → one personal GitHub remote. A tree-wide grep for `design partner|pilot customer|pilot studio|first customer|prospect|licensee|LOI|letter of intent|NDA|contract signed|invoice|trial account|tenant` across `*.md` and `*.py` returns zero business hits. Every business-sense "studio" reference is either pitch copy (`docs/DEMO_SCRIPT.md:187`) or lives in `project-harness/archive/2026-06-18-shipped-programs/`, archived 71 days ago.
- **Cost of inaction:** Already being paid. With no external clock, "done" is defined by the harness, and the harness is the thing being built — CR-L07-05 (roadmap completion diverging), CR-L10-06 (30% of the commit stream is process bookkeeping), CR-L10-07 (loop-driven velocity causing fix-of-fix). Each additional eval program deepens the loop rather than closing it.
- **Fix sketch:** Human decision, not an engineering task. Name one external party — a jam team, a solo Unity dev, a friend's studio — who will attempt an integration against a fixed date. That single constraint reprioritises CR-L12-02, CR-L12-03 and CR-L12-05 automatically and makes CR-L12-01 answer itself.
- **Effort:** S (to decide) / L (to serve)
- **Removes:** 0 lines
- **Blast radius:** The whole roadmap.

### [CR-L12-07] The HTTP contract has 148 operations and one sentence of stability policy

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Live `openapi.json` this session: **148 operations across 132 paths**. The complete stability policy in the repo is `docs/INTEGRATION.md:6`: *"Routes and shapes may evolve; breaking changes will be announced."* No deprecation window, no `/v2` scheme, no contract test against a published spec. SX.1 (OpenAPI contract freeze) is unchecked in `UNREAL_DEFERRED.md:63`. The root `live_openapi.json` snapshot is 64 days stale (CR-L13-11) and `docs/API.md` is missing 6 live routes (CR-L13-09, re-confirmed here: `/setup/config`, `/setup/validate`, `/v1/admin/debug/vector-store`, `/v1/admin/factions/{}/standings/{}`, `/v1/admin/schedules/character/{}/at`, `/v1/admin/vector-store/rehydrate`). The generic node-list endpoint returns no `total` in `meta` (`GET /v1/graph/nodes/Character?limit=1` → `{"limit":1,"offset":0,"sort":"id:asc","strategy":"offset"}`), so a client cannot size a paginated read without walking it.
- **Cost of inaction:** Any client written today — the SDK of CR-L12-03 included — is written against a moving target with no signal when it moves. The first integrator upgrade breaks silently.
- **Fix sketch:** Regenerate `live_openapi.json` in CI on every push and fail the build when it changes without a `CHANGELOG.md` entry. That is SX.1's cheap 80%, and it costs one CI step rather than a program.
- **Effort:** S
- **Removes:** 0 lines
- **Blast radius:** `.github/workflows/ci.yml`, `live_openapi.json`, `CHANGELOG.md` (already 96 commits stale — CR-L13-08).

### [CR-L12-08] `demo_game/`'s 1,116 tests are gated by nothing, while gated code imports it

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `grep -c "test-demo\|demo_game\|package" .github/workflows/ci.yml` → **0**. `make check` (`Makefile:200`) omits `test-demo`. Yet `tests/unit/api/test_client_paths_phase2.py:17`, `tests/unit/api/test_interaction_phase1.py:25` and `tests/unit/config/test_seed_chain_quests.py:19` import `demo_game.client` / `demo_game.dialogue` / `demo_game.seeds.seed`, and those files run inside `make test-cov`, which **is** CI-gated. `Makefile:627` builds the eval baseline fixture `evals/fixtures/eval_world_baseline.json` from `python -m demo_game.snapshot`, and `evals/anti_hallucination_runner.py:30` depends on the player id `demo_game.seed` creates. Run by hand this session: `1116 passed in 9.28s`; `python -m demo_game.runners.run --dry-run` completes 12 acts.
- **Cost of inaction:** 36,961 lines whose failure mode is silent. A `demo_game` regression breaks the eval baseline fixture and three CI-gated unit tests, and the first symptom will be an unexplained eval number rather than a red demo test. The most likely trigger is the `chore: restore the line endings my own edits rewrote across P8` class of sweep-up commit, which already accounts for half of `demo_game`'s recent churn.
- **Fix sketch:** Add `test-demo` to the CI test job (9 seconds) and to `make check`. If `demo_game` is genuinely not worth gating, then move `snapshot.py`, `client.py`, `dialogue.py` and `seeds/` out of it into a small `fixtures/` package that *is* gated, and let the pygame UI rot honestly.
- **Effort:** S (CI) / M (the extraction)
- **Removes:** 0 lines (or ~30,000 lines of pygame UI moved off the gated path, if the extraction is chosen)
- **Blast radius:** `.github/workflows/ci.yml`, `Makefile:200`; the extraction would touch `evals/fixtures`, three `tests/unit` files and 12 Makefile targets.

### [CR-L12-09] The engine package cannot be imported except in one undocumented order

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** Executed this session with `PYTHONPATH=src`:
  ```
  OK  npc_engine.retrieval.dialogue_context
  OK  npc_engine.main
  ImportError: cannot import name 'build_serialized_context_with_receipt' from partially
    initialized module 'npc_engine.retrieval.context.context_builder'
    (most likely due to a circular import)          ← npc_engine.engines.dialogue.degradation
  ImportError: (same)                               ← npc_engine.retrieval.context
  ```
  The cycle is `retrieval/context/__init__.py:46` → `context_builder.py:80` → `retrieval/dialogue_context/__init__.py:13` → `dialogue_context_adapter.py:21` → back into `context_builder`. It resolves only if `npc_engine.retrieval.dialogue_context` is imported first, which `npc_engine.main` happens to do.
- **Cost of inaction:** Anyone embedding the engine as a library rather than a server — which is what `scripts/launcher.py` and the PyInstaller path do, and what an in-process integration would do — hits an ImportError whose message names neither the real cause nor the workaround. It also makes any targeted unit-level import of `engines/dialogue` fragile, which is why the fallback-latency measurement in §4 needed a manual pre-import.
- **Fix sketch:** Move the `dialogue_context_adapter` import in `context_builder.py:80` under `TYPE_CHECKING` or into the function body — CLAUDE.md already mandates `TYPE_CHECKING` blocks for cycle resolution.
- **Effort:** S
- **Removes:** ~0 lines
- **Blast radius:** `retrieval/context/context_builder.py`, `retrieval/dialogue_context/dialogue_context_adapter.py`; import-order assumptions in `main.py` and `api/dependencies.py`.

---

## Severity summary

| Severity | Count | IDs |
|---|---:|---|
| CRITICAL | 0 | — (the CRITICALs bearing on this lens are CR-L01-01, CR-L01-02, CR-L03-01) |
| HIGH | 6 | CR-L12-01 … CR-L12-06 |
| MEDIUM | 3 | CR-L12-07, CR-L12-08, CR-L12-09 |
| LOW | 0 | — |

**Note on the ceiling.** CR-L12-02 (`make package` has never been buildable, on any commit, since the
day the spec was written) is the finding I would have raised to CRITICAL had the budget allowed: it is
a Confirmed defect, in the shipping path, in the only artifact a studio would ever receive.

## Method notes

- All live-API probes were reads. No gossip tick, event tick, clock advance, seed or write of any kind
  was issued; the ≥200-pairs/tick target was therefore assessed from the largest value ever used in the
  tree rather than by running one, per the read-only constraint.
- LOC figures are tracked files only (`git ls-files`), matching the corrected split in the brief;
  `demo_game` re-measured at exactly 36,961.
- The last-200-commit churn table was reproduced independently (`git log -n 200 --no-merges`, per-file
  `git show --name-only`) and matches the brief's figures to within rounding (288/393/322/172/8).
