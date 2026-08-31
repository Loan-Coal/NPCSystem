# Fix Plans — 2026-08 Remediation Program

One plan per surviving finding from [TRIAGE.md](TRIAGE.md). 118 canonical problems, planned as
**37 work items** across 7 phases — small findings that share a file, a command, or a single commit
are planned together rather than as separate checkboxes.

**Every plan carries a Proof: a check that is red today and green after.** No item enters
`ROADMAP.md` without one. Where a behavioural test is impossible (a deletion, a doc correction) the
Proof is a verification command with its expected output. This rule exists because the review's
root-cause C1 is checks that bind to an artifact's form rather than the behaviour it stands for — a
remediation plan without behavioural proofs would recreate exactly that.

Effort: **S** < 2h · **M** < 1d · **L** 2–4d · **XL** > 1w.

---

# R0 — Security (out of band)

### [CR-L05-11] Close the `/setup/*` unauthenticated remote read

- **Verdict:** UPHELD (Phase 1) — verified live at HEAD
- **Severity:** CRITICAL
- **Depends on:** none
- **Blocks:** nothing — deliberately, so it can ship alone
- **Chosen approach:** Three changes in one commit. (a) `docker-compose.yml:72` → `"127.0.0.1:8000:8000"`. (b) Gate the `/setup` exemption in `middleware_helpers.py` on `settings.ENV == "dev"`, matching the pattern `/docs` already uses — so the exemption survives local development and vanishes everywhere else. (c) Drop the schema-hidden `config_dir` query param from `POST /setup/config`, or restrict it to a whitelisted root; it currently `mkdir -p`s and writes as root at an attacker-chosen path. Supersede DEC-131, whose premise (loopback is the trust boundary) the compose file falsified.
- **Alternatives rejected:** (a) *Add auth to `/setup/*`* — the wizard runs before a key exists, so it cannot authenticate; this is why the exemption was created. (b) *Bind-only fix* — leaves the exemption unconditional, so the next deployment that publishes the port re-opens it. The premise must be enforced in code, not documented in a comment. (c) *Encrypt the key at rest* — does not help; the endpoint returns it decrypted.
- **Proof:** `tests/integration/test_setup_auth.py::test_setup_config_requires_auth_outside_dev` — set `ENV=staging`, `GET /setup/config` with no API key, assert `401`. **Today this returns `200` with the wizard config body** (the exemption at `middleware_helpers.py:51` is unconditional), so the test is red before and green after. Plus the one-line check: `grep -n '8000:8000' docker-compose.yml` must return **only** the `127.0.0.1`-prefixed form.
- **Files touched:** `docker-compose.yml`, `src/npc_engine/auth/middleware_helpers.py`, `src/npc_engine/api/routes/setup/setup.py`, `project-harness/DECISIONS.md`
- **Effort:** S
- **Risk:** Binding loopback breaks any workflow reaching the API from another host or from a non-host-network container. If the demo or DemoGame ever calls the engine from outside the host, this is a visible break — which is the correct outcome, but it should be expected rather than discovered.
- **Roadmap phase:** R0 — do before the rest of this program

**Also required, not a code change:** rotate the wizard API key if port 8000 has ever been reachable off-box. Closes CR-L05-06 (the auth-surface claim) as a side effect once the CLAUDE.md rewrite lands.

---

# R1 — Gate integrity

Nothing downstream is trustworthy until the gates can fail. This phase must precede the CI work
(R2) — wiring theatre gates into CI makes them harder to remove, not easier.

### [CR-L06-05 + CR-L06-04 + CR-L05-04] Make `check-rules` signatures line-count-bearing

- **Verdict:** UPHELD — confirmed by the gate's own docstring
- **Severity:** HIGH
- **Depends on:** none
- **Blocks:** CR-L08-01, CR-L08-02, CR-L02-06 — file splits re-grow without this
- **Chosen approach:** Record the line count at grandfathering time in the signature (`R001|path|925`) and fail when a grandfathered file exceeds its recorded size. Adopt the **two-tier limit** decided in Phase 0: soft advisory at 400 lines (no gate, cohesion judgement), hard unwaivable gate at 800. Chosen over a hard re-baseline because it stops the bleed immediately without forcing 31 file splits at once, and over keeping 300 because the review exonerated the 300 rule as a *cause* (median `graph/` file is 103 lines) while proving it functions as a floor.
- **Alternatives rejected:** (a) *Hard-fail all 133 entries now* — blocks all other work for days and would be reverted. (b) *Time-boxed expiry per entry* — needs a calendar nobody maintains; this project has already proven that (7.8-year burn-down). (c) *Keep 300 hard* — the exemption list is the evidence it does not hold.
- **Proof:** Append a no-op comment line to `demo_game/client.py` and run `make check-rules`. **Today it stays green** — `check_rules.py:27` states "Signatures are file-level … so they stay stable across edits", and the file demonstrably gained 481 lines while grandfathered. After the fix it goes red. Revert the comment. Second proof: create a 3-line file at 801 lines and confirm the hard gate reds with no waiver available.
- **Files touched:** `scripts/check_rules.py`, `scripts/rules_baseline.txt`, `scripts/evals_baseline.txt`
- **Effort:** M
- **Risk:** Re-baselining locks in today's sizes; a file mid-refactor gets its inflated size as its ceiling. Mitigate by re-baselining in the same commit as this change and not before.
- **Roadmap phase:** R1

### [CR-L06-03 + CR-L06-01] Gates that cannot fail

- **Verdict:** CR-L06-03 UPHELD · CR-L06-01 RECALIBRATED (remedy inverted)
- **Severity:** HIGH / MEDIUM
- **Depends on:** none
- **Blocks:** CR-L15-01 (do not wire a gate that cannot fail into CI)
- **Chosen approach:** Both gates get a real exit code, neither is deleted. `check_test_quality.py:261` returns `0` unconditionally with a docstring admitting it ("Exits 0 always (report-only until EVAL-P15.4)") — make it return `1` when findings exceed a recorded baseline, ratchet-style, so it starts useful instead of starting red. `check_human_gates.py` keeps its content — it emits 14 real gates and 16 blocked tasks and is the only tracker of them — but gains `--strict` wired into `make check` that fails when a gate is `OPEN` past its declared date. **The review's recommendation to delete `check-human-gates` is rejected:** it would destroy live information in a program you are keeping.
- **Alternatives rejected:** (a) *Delete both* — `check-test-quality` has a real signal (47 zero-call, 23 assertion-free tests per CR-L14-06) and `check-human-gates` tracks blocked work. (b) *Fail `check-test-quality` immediately on any finding* — instantly red on 70 existing findings, so it gets removed from `make check` within a day.
- **Proof:** For `check-test-quality`: add a test file containing `def test_nothing(): pass`, run `make check-test-quality`, assert exit `1`. **Today `echo $?` prints `0`** no matter what it reports. For `check-human-gates`: `python scripts/check_human_gates.py --strict; echo $?` must print `1` while H1–H6 are `OPEN`. **Today the non-strict run prints 6 OPEN gates and exits `0`** (verified at HEAD).
- **Files touched:** `scripts/check_test_quality.py`, `scripts/check_human_gates.py`, `Makefile`
- **Effort:** S
- **Risk:** `--strict` on human-gates goes red immediately and stays red until the 16 blocked tasks clear. That is honest but will be loud. Consider landing it as a separate `make check-blocking` target if the noise is intolerable — but do not silence it by returning 0.
- **Roadmap phase:** R1

### [CR-L06-09 + CR-L03-07 + CR-L06-02] Remove the three gates that audit unchangeable inputs

- **Verdict:** UPHELD — `x == x` confirmed verbatim
- **Severity:** HIGH / MEDIUM
- **Depends on:** none
- **Blocks:** nothing
- **Chosen approach:** Drop `check-conservation` and `check-label-survival` from `make check` and delete `_check_identity_2`. `check_conservation.py:164` reads `all_slots = compare_slots` and line 169 asserts `ok=(compare_slots == all_slots)` — a literal tautology, with a comment explaining that it holds by construction, introduced in a commit labelled a bug fix. Identities 1 and 3 are real; they move to `make eval-generate` where the data they audit actually changes, per L9's ordering resolution (gate removal first, repoint second).
- **Alternatives rejected:** *Repair Identity 2* — this is TRIAGE conflict #3. Repairing it means inventing an invariant for a gate whose inputs cannot change. If the invariant is wanted later it returns as a probe under the new counterfactual rule (DEC below), which is the correct home for it.
- **Proof:** `grep -n 'all_slots = compare_slots' scripts/check_conservation.py` returns 0 rows, and `grep -n 'check-conservation\|check-label-survival' Makefile` shows them absent from the `check:` target and present under `eval-generate`. Behavioural proof for the surviving identities: corrupt one row in a generation dir's `judged.jsonl` and confirm `make eval-generate` reds on Identity 1.
- **Files touched:** `scripts/check_conservation.py`, `scripts/check_label_survival.py`, `Makefile`
- **Effort:** S
- **Risk:** Low. Neither gate has ever caught anything — they audit files that cannot change between runs.
- **Roadmap phase:** R1

### [CR-L06-07 + CR-L13-06] `check-harness` H3 is permanently inert

- **Verdict:** UPHELD — confirmed
- **Severity:** MEDIUM
- **Depends on:** none · **Blocks:** nothing
- **Chosen approach:** Repoint H3 at a file that exists, or delete H3. `NEXT_SESSION.md` exists **only** at `project-harness/archive/stale-2026-06/NEXT_SESSION.md`, so H3's "ISSUES.md has open tickets but NEXT_SESSION.md claims none" can never fire. Since the archive is being deleted in R4 and no live `NEXT_SESSION.md` is planned, **delete H3** and keep H1/H2. Also fix the ordering defect: `check_harness_honesty.py`'s only hard check sits behind `lint`, which runs first in `make check` and short-circuits it.
- **Alternatives rejected:** *Recreate `NEXT_SESSION.md`* — adds a document to satisfy a gate. Precisely the C1/C2 pathology.
- **Proof:** Add a fake open ticket to `ISSUES.md`, run `make check-harness`. **Today H3 cannot fire regardless** (its input path does not exist). After the fix, `grep -c H3 scripts/check_harness_honesty.py` returns 0 and H1/H2 still fire on their own counterfactuals — verified by removing a required DECISIONS heading and watching H1 red.
- **Files touched:** `scripts/check_harness_honesty.py`, `Makefile`
- **Effort:** S · **Risk:** Low · **Roadmap phase:** R1

### [CR-L06-08 + CR-L14-07 + CR-L05-03] Make the docstring gate read content

- **Verdict:** UPHELD
- **Severity:** MEDIUM
- **Depends on:** none · **Blocks:** CR-L09-04 (the CLAUDE.md rewrite must describe the gate that exists)
- **Chosen approach:** `docstring_audit.py` verifies the substring `Layer:` exists. Make it verify the value is one of the declared layer names and that it matches the file's actual directory. This is the cheapest available demonstration of the counterfactual principle: it converts a form check into a behaviour check in about 20 lines. Do **not** extend the gate to function docstrings — CR-L05-03 shows compliance tracks whatever is gated (100%/100% on gated fields, 28%/66% on ungated, with *ungated* `demo_game/` scoring higher than gated `src/`), so gating more fields buys conformance, not quality.
- **Alternatives rejected:** (a) *Gate all four docstring fields* — manufactures 100% compliance on `Purpose:` lines that say nothing. This is how CR-L08-03's documentation was manufactured in the first place (CR-L11-06). (b) *Delete the gate* — it is one of the cheap ones and the layer/directory check is genuinely useful.
- **Proof:** Change `Layer: graph` to `Layer: banana` in any `graph/` module and run `make check-docstrings`. **Today it stays green** — only the substring `Layer:` is checked. After the fix it reds. Second counterfactual: move a file between layer directories without updating its docstring; the gate must red.
- **Files touched:** `scripts/docstring_audit.py`
- **Effort:** S · **Risk:** Will red on existing files with wrong layer values; fix them in the same commit. · **Roadmap phase:** R1

### [CR-L02-04 + CR-L05-05 + CR-L08-04] Rule-scope gaps

- **Verdict:** UPHELD · **Severity:** MEDIUM · **Effort:** S · **Risk:** Low
- **Depends on:** CR-L06-05 · **Blocks:** none
- **Chosen approach:** Three scope corrections in one commit. R005 (Cypher leak) currently scans a `_CYPHER_SCAN_DIRS` set that excludes `api/`, `auth/`, `data/`, `cache/`, `mutation/` — extend it to all non-`graph/` packages. R004 matches the literal string `raise Exception(`, never written in 967 commits, while missing the two real violations inside `utils/errors.py` — the file its own rule names; match `raise Exception` and `raise BaseException` with optional whitespace and add an AST check for `class X(Exception)` outside `utils/errors.py`. Add `scripts/` (7,821 LOC) to the R001/R006 scan set, since the gate scripts enforcing every rule are exempt from all of them.
- **Alternatives rejected:** *Leave `scripts/` exempt* — CR-L15-06 shows the gate scripts also have no coverage floor. Exempt from rules *and* from coverage is not defensible for the code that enforces both.
- **Proof:** Add `session.run("MATCH (n) RETURN n")` to `src/npc_engine/api/routes/quest/quest.py` → `make check-rules` must red (**today it passes**, `api/` is unscanned). Add `raise Exception("x")` to any engine → must red (**today it passes** unless written with the exact parenthesis form). Add a 45-line function to `scripts/check_rules.py` → must red (**today `scripts/` is unscanned**).
- **Files touched:** `scripts/check_rules.py`, `scripts/rules_baseline.txt`
- **Roadmap phase:** R1

### [NEW-DEC] A gate must pass a counterfactual before joining `make check`

- **Verdict:** derived from CR-L11-05, CR-L11-02, CR-L11-06 (all DEFERRED-VALID as findings — their remedy is this policy, not a code change)
- **Severity:** n/a — a decision
- **Depends on:** R1 complete · **Blocks:** every future gate
- **Chosen approach:** File as a DEC. A gate may be added to `make check` only if the commit adding it demonstrates the gate red with the guarded behaviour removed. Existing gates failing this are removed, not repaired. New verification effort goes into **probes**, not gates — the ~1,200-line probe set holds the only shipped-behaviour catch in 967 commits. This is the single highest-leverage item in the program and costs nothing to adopt.
- **Alternatives rejected:** *A checklist in CLAUDE.md* — 22 of 28 strict rules are ungated and ignored; another unenforced rule would join them. The enforcement is social and lives in the commit, which is the only place it can live.
- **Proof:** Verification command, not a test: for each of the 14 `make check` targets, `git log -1 --format=%B <gate-file>` must reference a counterfactual, or the gate must be absent from `check:`. Run once at R1 close; the count of `check:` targets should be **10, not 14**.
- **Files touched:** `project-harness/DECISIONS.md`
- **Effort:** S · **Risk:** None · **Roadmap phase:** R1

---

# R2 — Measurement

**Nothing downstream of this phase is measurable until it lands.** This is where the fifth CRITICAL
sits, and it gates the eval program, the gossip fix's verification, and the model swap you want.

### [CR-L15-01] Unit tests make live network calls; CI records `None` model digests

- **Verdict:** RECALIBRATED — **HIGH → CRITICAL** (Phase 1)
- **Severity:** CRITICAL
- **Depends on:** R1 complete
- **Blocks:** CR-L03-01, CR-L09-02, CR-L16-08, CR-L14-02 — the entire eval program
- **Chosen approach:** Two changes, and the second is the important one. (a) Make the network-touching defaults **explicit rather than implicit**: `run_config.resolve()` currently falls back to `_engine_adapter.fetch_ollama_version` / `fetch_model_digest` when no injector is passed ([run_config.py:260-262](../../evals/run_config.py#L260-L262)), so 15 of 17 "unit" tests in `tests/unit/evals/test_run_config.py` make three real HTTP attempts each. Require the injector in unit tests via a session-scoped `conftest.py` autouse fixture that raises on real `httpx` use under `tests/unit/`. (b) **Make a `None` digest fatal, not silent.** `fetch_model_digest` returning `None` must raise in any run that will publish a number. Today it is swallowed, so CI records `generation_model_digest=None` and the run looks fine.
- **Alternatives rejected:** (a) *Add Neo4j and Ollama services to CI* — the review's §E item 7, and it is right, but it is a **separate** item (see next plan) and it does not fix this: with a real Ollama in CI the tests would pass while still being integration tests mislabelled as unit tests, and the `None`-digest hole would stay open for every environment without one. (b) *Mark them `@pytest.mark.integration` and skip* — hides the defect; the digest would still be `None` wherever the eval actually runs. (c) *Reduce the httpx timeout* — treats a 120-second symptom, not the cause.
- **Proof:** Two, both red today. (1) `python -m pytest tests/unit/evals/test_run_config.py -q` must complete in **under 5 seconds with no network available**. **Today it exceeds 120 seconds** (measured at HEAD: collection 0.07 s, execution timed out at 120 s). (2) `tests/unit/evals/test_run_config.py::test_resolve_raises_when_digest_unavailable` — call `resolve()` with a digest fn returning `None`, assert it raises. **Today it returns a `RunConfig` with `generation_model_digest=None` and no error**, which is the defect that makes every published eval number unattributable to a model.
- **Files touched:** `evals/run_config.py`, `evals/engine_adapter.py`, `tests/unit/evals/test_run_config.py`, `tests/unit/conftest.py`
- **Effort:** M
- **Risk:** Making `None` digests fatal will red any eval run without a reachable Ollama — including, possibly, CI. That is the correct behaviour and the whole point, but it converts a silent wrong answer into a loud failure, and the loud failure will arrive first.
- **Roadmap phase:** R2 — **first item**

### [CR-L06-06 + CR-L14-02 + CR-L15-06 + CR-L06-10 + CR-L12-08 + CR-L09-07] Put real services in CI and gate what CI ignores

- **Verdict:** UPHELD (all six; four merged)
- **Severity:** HIGH
- **Depends on:** R1 complete, CR-L15-01, **ISSUE-232**
- **Blocks:** CR-L03-01's re-baseline, and R3.2/R3.3's Proofs
- **Do ISSUE-232 first (found 2026-08-28, after this plan was written):** `neo4j` publishes no
  host ports, so a host-run `pytest tests/integration` cannot connect at all — 34 failed / 9
  passed / 5 errors, every failure `ServiceUnavailable` on `localhost:7687`. The review's
  "9 passed, 34 skipped" was the same 34 tests skipping. **Their real pass/fail split is
  unknown**, so this plan's estimate of what CI will surface is unmeasured. Add
  `ports: ["127.0.0.1:7687:7687"]` (loopback — do not repeat ISSUE-227), re-run, and record the
  actual split before sizing the CI work.
- **Chosen approach:** Add `neo4j:5` to the CI test job — **not Ollama** (corrected 2026-08-31: **zero** tests under `tests/integration/` call an LLM; `test_engine_llm_config_integration.py` documents "Does NOT: call live LLM services". The Ollama-in-CI exclusion belongs to the eval/judge path, ISSUE-240); run the **11** currently-skipped `make check` gates (was 8 when written; R1.8 added 3 and R2.3 added 2 — derive the count, never hardcode it); add `make test-demo` and `demo_game` mypy to CI. `demo_game/` is **gated, not cut** — L9 established it is the eval program's fixture generator (`Makefile:627`) and three CI-gated tests import it, and it costs +9 s. Add a coverage floor to `scripts/`, `e2e/` and `demo_game/` (36,527 LOC currently under none, including the gate scripts).
- **Alternatives rejected:** (a) *Mock Neo4j in CI* — CR-L14-02's counterfactual is the refutation: gutting 105 of 180 repository methods to constants left mypy clean and broke only the layer's own passthrough tests. Mocks are what let that happen. (b) *Cut `demo_game/`* — explicitly rejected by L9 with a reference check.
- **Proof:** Re-run CR-L14-02's counterfactual in CI: stub 10 graph repository methods to return constants and push. **Today CI stays green** (34 integration tests skip without `NEO4J_URI`; verified locally as "9 passed, 34 skipped"). After the fix CI must red. Second proof: `make test-demo` appears in a CI job and `demo_game/` mypy error count is recorded as a baseline (**currently 256, gated by nothing**).
- **Files touched:** `.github/workflows/ci.yml`, `Makefile`, `.mypy_baseline_demo`
- **Effort:** M
- **Risk:** CI wall-clock rises substantially (the two coverage runs are already 94% of `make check`'s 595 s). Split into parallel jobs. Also: this is the change most likely to reveal that CI has been red or vacuous — expect a bad day.
- **Roadmap phase:** R2

### [CR-L09-02 + CR-L13-03] Wire `check-base-rate`, delete `check-engine-coverage`

- **Verdict:** UPHELD · **Severity:** HIGH · **Effort:** S · **Risk:** Low
- **Depends on:** CR-L15-01 · **Blocks:** CR-L03-01
- **Chosen approach:** L9 resolved this escalated conflict and it is not re-litigated: **wire** `check_base_rate.py` (386 ln — it measures the very breach CR-L03-01 documents), **delete** `check_engine_coverage.py` + its contract + test (658 ln, reachable from no `make` target and no CI job). Per your integrate-or-delete instruction: base-rate is high value and gets integrated; engine-coverage answers the same question worse and goes.
- **Alternatives rejected:** *Keep both* — two gates for one question, and the review escalated the conflict precisely to avoid doing this work twice.
- **Proof:** `make check-base-rate` exists and reds against the current corpus, where the YAML guard-case base rate is **1.000** — a battery every responder passes. **Today `grep -n 'check-base-rate' Makefile` returns 0 rows** (verified). Deletion proof: `git grep -l check_engine_coverage` returns nothing outside the review's own files.
- **Files touched:** `Makefile`, `scripts/check_base_rate.py`, `scripts/check_engine_coverage.py` (del), `docs/CAPABILITY_CASES.md`, `docs/CASE_SET_POLICY.md`, `docs/ENGINE_EVAL_COVERAGE.md`
- **Roadmap phase:** R2

### [CR-L03-08] Delete the guaranteed-pass assertions — *before* re-baselining

- **Verdict:** UPHELD · **Severity:** MEDIUM · **Effort:** M
- **Depends on:** CR-L09-02 · **Blocks:** CR-L03-01 — **this ordering is TRIAGE conflict #1 and must be respected**
- **Chosen approach:** Delete the 18 of 36 forbidden-keyword assertions that cannot fail, plus the dead `keyword_none` expectation blocks and the 3 `moderation_everyone_*` cases. Do this **as its own commit, before** the null-baseline comparison. If both land together the guard rate moves for two reasons at once and the delta is unattributable — which is the same error that produced the 0.914 figure.
- **Alternatives rejected:** *Fix the assertions to be meaningful* — a bigger job that belongs to the golden-set rebuild, and it would again change the number under measurement.
- **Proof:** Base rate over the guard battery drops below 1.000. **Today `check-base-rate` measures exactly 1.000** — every case passes for every responder. Record the new rate; it is the denominator everything else is judged against. Expect the published guard score to **fall**, correctly.
- **Files touched:** `evals/cases/**`
- **Risk:** The headline number gets worse. That is the fix working.
- **Roadmap phase:** R2

### [CR-L03-01] Publish the null baseline beside every eval number

- **Verdict:** UPHELD (Phase 1) — attacked directly, survived
- **Severity:** CRITICAL
- **Depends on:** CR-L15-01, CR-L09-02, CR-L03-08 — **all three**
- **Blocks:** CR-L01-01's verification, CR-L12-05, any published claim
- **Chosen approach:** (a) Remove `NotACapabilityCaseError` from `hedge_responder_probe.py` so the null responder **can** be scored against guard cases — today the probe structurally refuses, which is why the baseline was never taken. (b) Make `evals/report.py` emit `engine_score` and `null_score` side by side and refuse to print a headline where `engine ≤ null`. (c) Retract the `0.914` guard claim from the README and reports until it clears its baseline. (d) Fix `check_publication` (CR-L03-02): it ignores the interval it is handed, and `dashboard/headline.py:140` calls it with a **hardcoded `(0.0, 0.0)`** — the interval is not merely unused, it is fabricated. Make the interval decide, and make `report.py` call it.
- **Alternatives rejected:** (a) *Fix the scorers first (CR-L03-03's MDE problem)* — MDE work is L-effort and cannot start without a trustworthy baseline to size the effect against. (b) *Keep publishing 0.914 with a caveat* — a number that ranks a fixed string above the engine is not improved by a footnote.
- **Proof:** `python scripts/hedge_responder_probe.py --battery guard` runs and prints a score. **Today it raises `NotACapabilityCaseError`** ("Raised when a case that is not `case_pos_*` is handed to the probe") — verified in source. Then: `evals/report.py` must exit non-zero when the null score ≥ the engine score. **Today the engine's 0.897 against the null's 0.949 prints as a clean `0.914` headline** at `evals/reports/20260825T231028Z.md:11`.
- **Files touched:** `scripts/hedge_responder_probe.py`, `evals/report.py`, `evals/scorer_trust_policy.py`, `evals/dashboard/headline.py`, `README.md`
- **Effort:** M
- **Risk:** The published capability claim will not survive. Every downstream doc citing 0.914 must be corrected in the same pass.
- **Roadmap phase:** R2

### [CR-L03-02 · CR-L03-03 · CR-L03-06 · CR-L03-09 · CR-L03-10 · CR-L03-11 · CR-L16-08] Instrument repairs

- **Verdict:** UPHELD · **Severity:** HIGH×2, MEDIUM×5 · **Effort:** M each, L for CR-L03-03
- **Depends on:** CR-L03-01 · **Blocks:** the model swap
- **Chosen approach:** Sequenced repairs to the instrument, each independently provable. **CR-L03-02** folded into CR-L03-01 above. **CR-L03-10**: an unparseable judge verdict is recorded as a substantive `NO` — make it record `UNPARSEABLE` and exclude it from the denominator; remove the wall-clock dependence that flips verdicts. **CR-L03-06**: the headline aggregator reports 78 turns for 789 verdict rows and 5 hallucinations for 28 — fix the join. **CR-L03-11**: reproducibility measured 0.628 against a 0.95 gate, recorded `NOT_MET`, gated by nothing — wire the gate. **CR-L03-09**: a third of the corpus has never been scored. **CR-L03-03**: two of three judges have an MDE (17.25pp / 29.01pp) exceeding the headroom they must resolve (5.9pp / 8.0pp) — they cannot detect any physically possible effect; either raise n or retire the judge. **CR-L16-08** (upgraded to MEDIUM): pin the Ollama model by content digest, which CR-L15-01 makes possible by refusing `None`.
- **Alternatives rejected:** *Do these before CR-L03-01* — each changes a number, and until the baseline is trustworthy a changed number is uninterpretable.
- **Proof:** Per item, all red today. CR-L03-10: feed the judge a malformed response, assert the verdict is `UNPARSEABLE` not `NO` (**today it is recorded as a substantive `NO`**). CR-L03-06: assert `report.turns == len(verdict_rows)` (**today 78 vs 789**). CR-L03-11: `make check-reproducibility` reds at 0.628 against the 0.95 gate (**today the number is recorded and nothing reads it**). CR-L03-03: **corrected 2026-08-31 — this proof cannot be written as stated.** `evals/mde.py` has **no `mde()` and no `headroom()`**; its `__all__` is `arm_pairing_mde` / `implied_discordance_rate` / `observed_mde` / `required_pairs_for`, all keyword-only, and `headroom` (= 1 − measured base rate) is review prose, not code. The task must first *build* the comparison, then assert it per published judge. It also cannot be evaluated until the three rival κ families are reconciled — the 17.25/29.01 pp MDEs come from `mde.py`'s κ (1.000/0.282/0.225) while the retirement argument quotes calibration's (0.849/0.530/0.247). See ISSUE-244. CR-L16-08: assert the run record's model field is a sha256 digest, not a tag (**today it is `qwen2.5:7b`, or `None` in CI**).
- **Files touched:** `evals/matchers.py`, `evals/mde.py`, `evals/report.py`, `evals/` aggregator, `docker-compose.yml`
- **Risk:** CR-L03-03 may conclude a judge must be retired, shrinking what the harness can claim.
- **Roadmap phase:** R2

### [CR-L03-05 · CR-L03-12 · CR-L10-01 · CR-L01-07] Deferred-value eval subsystems

- **Verdict:** UPHELD · **Severity:** HIGH×2, MEDIUM, LOW · **Effort:** S–M
- **Chosen approach (per your integrate-or-delete instruction):** **Trend/regression stack (1,309 ln)** — `evals/trend/trend_v1.jsonl` has exactly **1 row** (verified `wc -l`). Do not delete: trend comparison is precisely what a model swap needs, and it is unusable today only because CR-L15-01 nulls the model identity that makes rows comparable. **Integrate after one full generation, then re-decide.** **Sequence subsystem (1,714 ln)** — keep and split; it has 6 consumers including 2 in `e2e/scripts/`, so it is not isolated (an L9 correction). **CR-L10-01/CR-L01-07** — the token-budget guard hardcodes a hand-copied measured ceiling with no re-measurement gate; add the re-measure to `make eval-generate`.
- **Proof:** Trend: after one full generation, `wc -l evals/trend/trend_v1.jsonl` returns ≥ 2 **and** the two rows share a model digest, making them comparable. **Today: 1 row, and CR-L15-01 means its digest may be `None`.** Budget: **corrected 2026-08-31 — wrong file.** `src/npc_engine/retrieval/context/context_budget_enforcer.py:35` `TIER0_MAX_TOKENS = 380` is a *design allocation* (`docs/PROMPT_DESIGN.md:91` sums world 80 + bio/emotion 120 + relation 30 + turns 150), never measured — a budget cannot be re-measured. The hand-copied *measurement* this item is about is `MEASURED_ROSTER_CEILING_TOKENS = 1151` at `tests/unit/config/test_shipped_window_holds_the_measured_ceiling.py:45` (DEC-215). Change **that** constant and assert the re-measure gate reds; wire `scripts/probe_context_ceiling.py` (exists, `make probe-ceiling`, in no gate) as the re-measure.
- **Roadmap phase:** R2 (trend re-decision deferred to R2 close)

---

# R3 — Product correctness

### [CR-L01-04] Stop the degradation ladder swallowing infrastructure errors

- **Verdict:** RECALIBRATED — promoted in the dependency graph (Phase 1)
- **Severity:** HIGH
- **Depends on:** none
- **Blocks:** **CR-L08-03** — this is the edge the review did not draw, and getting it wrong wastes the 503 work
- **Chosen approach:** Narrow both `except Exception` blocks at [degradation.py:107 and :119](../../src/npc_engine/engines/dialogue/degradation.py#L107) to the exceptions that *should* degrade (LLM timeout, retrieval miss) and let infrastructure errors propagate. Today each catches everything, logs a warning, and falls through to the next tier, ending at a canned 200. A `GraphUnavailableError` raised by CR-L08-03's fix would be caught by the first of these and converted into a successful response before any handler ran.
- **Alternatives rejected:** (a) *Re-raise `GraphUnavailableError` specifically inside the handlers* — works, but leaves the bare catch for the next error class to fall into; the review's C5 pattern is exactly this kind of locally-reasonable decision composing badly. (b) *Do CR-L08-03 first and fix this when the test fails* — the test would pass misleadingly, since a canned 200 is a valid response body.
- **Proof:** `tests/integration/test_degradation.py::test_graph_outage_is_not_degraded_to_canned` — inject a `ServiceUnavailable` from the graph factory, assert it propagates rather than returning a canned response. **Today it returns HTTP 200 with the canned tier**, because `degradation.py:107` catches it, logs "Dialogue full tier failed", and continues.
- **Files touched:** `src/npc_engine/engines/dialogue/degradation.py`, `src/npc_engine/api/routes/dialogue/dialogue.py`
- **Effort:** S · **Risk:** Errors that used to degrade silently now surface. That is the point, but it will look like new breakage.
- **Roadmap phase:** R3 — **before CR-L08-03**

### [CR-L08-03 + CR-L02-01 + CR-L01-06 + CR-L05-01] Implement the Neo4j → 503 contract

- **Verdict:** UPHELD (Phase 1) — attacked with three greps, survived
- **Severity:** CRITICAL
- **Depends on:** **CR-L01-04**
- **Blocks:** CR-L01-05
- **Chosen approach:** Implement rather than delete the claim. (a) Catch `neo4j.exceptions.ServiceUnavailable` and `SessionExpired` at the graph driver boundary and raise `GraphUnavailableError(uri=..., cause=...)`. (b) Register a handler mapping it to HTTP 503 with the canonical `ErrorEnvelope` — `register_exception_handlers()` currently registers four handlers and none for this. (c) Make `TokenBudgetExceededError` subclass `StructuredNPCSystemError` rather than bare `Exception` ([errors.py:301](../../src/npc_engine/utils/errors.py#L301)) and give it a 4xx handler. Implementation is chosen over deletion because a studio integrating this engine — now a real scenario — must be able to distinguish "retry" from "your request is broken", and that is a licensing-grade concern.
- **Alternatives rejected:** *Delete the claim from CLAUDE.md and the 11 graph docstrings* — cheaper, and the review offers it as an option. Rejected because the Unreal DemoGame is a real client: a 500 on a transient Neo4j blip is indistinguishable from a bug in the caller, and that ambiguity is expensive to debug across a process boundary.
- **Proof:** `tests/integration/test_graph_outage.py::test_neo4j_outage_returns_503` — stop the neo4j container, `POST /v1/dialogue`, assert `resp.status_code == 503`. **Today this returns 500**: `grep -rn "raise GraphUnavailableError" src/` returns 0 rows, `grep -rn "503" src/npc_engine/api/` returns 0 rows, and the catch-all `Exception` handler produces the 500. Red before, green after. Guard against regression to the CR-L01-04 failure mode by asserting the response body is an `ErrorEnvelope`, not a canned dialogue reply.
- **Files touched:** `src/npc_engine/graph/` driver boundary, `src/npc_engine/api/errors/exception_handlers.py`, `src/npc_engine/utils/errors.py`
- **Effort:** M · **Risk:** Requires a real Neo4j to test — depends on R2's CI services for the regression guard.
- **Roadmap phase:** R3

### [CR-L01-01 + CR-L01-02 + CR-L12-04] Make gossip distortion compound

- **Verdict:** UPHELD (Phase 1) — Cypher read at HEAD
- **Severity:** CRITICAL
- **Depends on:** **R2 complete** — see TRIAGE conflict #2
- **Blocks:** CR-L12-05, any external demo
- **Chosen approach:** Two changes that must land together. (a) `CYPHER_BATCH_EVENT_TRUST` returns `best_event.summary` — the canonical `Event` node's text — so every hop distorts the *original*. Return the sharer's `k.distorted_summary` (which `CYPHER_BATCH_PROPAGATE_KNOWLEDGE` already writes to the edge) falling back to `e.summary` only when the sharer holds no distortion. (b) `MERGE (receiver)-[k:KNOWS_ABOUT]->(event) SET k.distortion_level = w.distortion_level` overwrites unconditionally, so running the world erases the seeded demo — `old_henryk`, seeded at distortion_level 70, reads 0 at tick 600. Use `ON CREATE SET` for the distortion fields, or guard the overwrite on the incoming distortion being higher.
- **Alternatives rejected:** (a) *Fix the relay only* — the demo still gets erased on the first tick, so the fix is invisible and untestable end-to-end. (b) *Fix the write only* — preserves the seed but distortion still never compounds. Neither half is independently shippable. (c) *Sequence before R2* — TRIAGE conflict #2: this shifts eval golden strings and gossip determinism fixtures, and you cannot verify the fix with an instrument a fixed string beats.
- **Proof:** `tests/integration/test_gossip_chain.py::test_distortion_compounds_across_hops` — seed `captain_sorn → mira_innkeeper → old_henryk`, run two gossip ticks, assert `distortion_level` at hop 2 is **strictly greater** than at hop 1, and that `old_henryk`'s `distorted_summary` derives from mira's text rather than the canonical event summary. **Today hop 2's level equals hop 1's** (both distort the same canonical string), and a second assertion — that a seeded `distortion_level=70` survives a tick — **fails today at 0**.
- **Files touched:** `src/npc_engine/graph/gossip/gossip_batch_queries.py`, `src/npc_engine/engines/gossip/gossip_handler.py`, gossip determinism fixtures, eval golden strings
- **Effort:** M · **Risk:** Golden strings and determinism fixtures shift. Budget for the fixture churn; it is not incidental, it is most of the work.
- **Roadmap phase:** R3

### [CR-L01-03 · CR-L01-05 · CR-L01-08 · CR-L01-09 · CR-L01-10 · CR-L01-11] Engine wiring

- **Verdict:** CR-L01-03 RECALIBRATED (HIGH→MEDIUM), rest UPHELD · **Effort:** S each, M for CR-L01-10
- **Chosen approach:** **CR-L01-03**: pass `memory_consolidation_engine=get_memory_consolidation_engine()` into `get_tick_scheduler()`. Note the corrected claim — the engine is *not* dead code; it is wired and reachable via `POST /memories/consolidate` ([memories.py:275](../../src/npc_engine/api/routes/knowledge/memories.py#L275)). Only the **tick** path never runs it. One kwarg. **CR-L01-09**: add a composition-root assertion that every `TickScheduler` engine slot is non-`None`, which is the general form of the same bug — `tick_scheduler.py:530` silently no-ops a `None` slot. **CR-L01-08**: `EngineFallbackPolicy` is declared in 5 YAML blocks and read by nothing — wire it or delete the declarations. **CR-L01-10**: make gossip side effects survive one bad pair. **CR-L01-11**: log the event-sampling RNG seed, as gossip already does. **CR-L01-05**: replace the source-string "guard" with a test that exercises the 4xx.
- **Proof:** CR-L01-03: assert `TickScheduler` runs consolidation on a tick — **today `self._memory_consolidation_engine is None` short-circuits at line 530**. CR-L01-09: set any engine slot to `None` and assert startup raises — **today it starts and silently skips**. CR-L01-10: inject a failing pair into a batch, assert the other pairs' writes persist — **today the batch aborts**. CR-L01-11: `grep -c 'seed' <tick log>` ≥ 1 for event sampling — **today 0**. CR-L01-05: delete the 4xx-raising code and assert the test reds — **today it passes**, since it asserts on source text.
- **Roadmap phase:** R3

### [CR-L02-03 · CR-L02-05 · CR-L14-04 · CR-L14-05] Structural defects

- **Verdict:** UPHELD · **Severity:** HIGH×2, MEDIUM×2 · **Effort:** M, XL (CR-L02-05), M, S
- **Chosen approach:** **CR-L14-04 first, it is cheap and high-leverage**: `base_engine.py:24` is `async def run_tick(self, *args: Any, **kwargs: Any) -> dict[str, Any]` — it types 33 scheduler parameters and enforces nothing, so mypy stays clean with an incompatible engine. Replace with an explicit signature or a `Protocol` with real parameters. **CR-L02-05** (raw dicts at the two most central interfaces, 145 functions) is **XL and deliberately deferred to R7** — it is the largest item in the review and must not be attempted before the gates and the instrument work. **CR-L14-05**: three copies of the Neo4j→native converter with divergent error paths, each swallowing around a call to itself — collapse to one. **CR-L02-03**: two stateful singletons built outside every composition root, one a bare global dict under a module-level lock.
- **Proof:** CR-L14-04: add an engine whose `run_tick` takes an incompatible parameter and assert `make type` reds — **today mypy passes** (`*args, **kwargs` accepts anything); this is the counterfactual CR-L14-04 is built on. CR-L14-05: assert one converter module exists — `grep -rlc 'def.*neo4j.*native\|_to_native' src/` returns 1, **today 3**. CR-L02-03: assert the singletons are constructed only in `api/dependencies.py` — **today they are module-level**.
- **Roadmap phase:** R3 (CR-L02-05 → R7)

---

# R4 — Subtraction

Approved in Phase 0. **§D row 3 (the overnight-loop bundle, 5,178 ln) is excluded — you are keeping
it.** `engines/deception/` and `engines/currency/` are excluded — held for integration.

### [CR-L09-01 + CR-L11-07 + CR-L16-01] Delete the unreferenced archive; fix the Windows clone

- **Verdict:** RECALIBRATED (numbers restated) / UPHELD
- **Severity:** HIGH · **Effort:** S · **Risk:** Low — 177 unreferenced vs 38 referenced, measured by L9
- **Depends on:** none · **Blocks:** nothing
- **Chosen approach:** Delete the 177 unreferenced files (17,699 lines) from `project-harness/archive/`, keeping the 38 that are referenced. **Corrected numbers:** the archive holds **265 files / 30,868 markdown lines** total (measured at HEAD); 177/17,699 is the unreferenced subset. This also removes the deep paths that make `git clone` fail on Windows without `core.longpaths`. Then document the two remaining fresh-clone steps in the README: `git config core.longpaths true` and `cp .env.example .env` — verified necessary, since `.gitignore:61` ignores `.env` and only `.env.example` is tracked.
- **Alternatives rejected:** (a) *Delete the whole archive* — 38 files are referenced; L9 checked. (b) *Set `core.longpaths` in a committed `.gitconfig`* — cannot work; the setting must exist before the clone.
- **Proof:** `git clone` into a fresh directory on Windows **without** `core.longpaths` succeeds. **Today it fails on the archive's deep paths.** Plus: `grep -rn 'archive/stale-2026-06' --include=*.md . | grep -v archive/` returns 0 rows after the deletion — no live document references a deleted file.
- **Files touched:** `project-harness/archive/**` (177 files), `README.md`, `CONTRIBUTING.md`
- **Roadmap phase:** R4

### [CR-L09-05 + CR-L11-08 + CR-L11-04 + CR-L13-10 + CR-L08-09 + CR-L13-11] Delete one-shot process artifacts

- **Verdict:** UPHELD · **Severity:** MEDIUM/LOW · **Effort:** S · **Risk:** Low
- **Chosen approach:** Delete the 12 one-shot session prompts and handoffs (2,791 ln; 2 kept because `ROADMAP.md` links them) and `.gitignore` the `PROMPT_*.md` / `*_HANDOFF*.md` pattern so the class stops recurring. Delete `soft_review.md` (305 ln) **after** re-filing its one surviving HIGH as a real issue. Delete `EVAL_STRATEGY.md` (a 3-month-old uncorrected duplicate of `docs/EVAL_METHODOLOGY.md`). Delete `live_openapi.json` (182,118 bytes, dated 2026-06-24) and add a `make openapi` target that regenerates it on demand — verified zero code consumers; `git grep` finds it only in harness and review prose.
- **Alternatives rejected:** *Archive them instead of deleting* — the archive is what R4 is deleting. Moving files into the thing being deleted is the process equivalent of a no-op.
- **Proof:** `git grep -l live_openapi.json` returns nothing outside `project-harness/review-2026-08/`. `ls project-harness/PROMPT_*.md` returns only the 2 ROADMAP-linked files. `git check-ignore project-harness/PROMPT_TEST.md` exits 0. The re-filed HIGH from `soft_review.md` has an `ISSUE-NNN` heading in `ISSUES.md`.
- **Roadmap phase:** R4

### [CR-L14-01 + CR-L09-06 + CR-L08-07 + CR-L14-06 + CR-L04-02] Delete dead code and phantom guards

- **Verdict:** UPHELD · **Severity:** MEDIUM/LOW · **Effort:** S · **Risk:** Low
- **Chosen approach:** Delete the `session_kwarg` tests and the 76 phantom docstring lines — verified: `military_engine.py:34` is `async def run_tick(self, *, tick_id: int)`, with no `session` parameter, while 61 `session_kwarg` references across `tests/` and `src/` guard it. This is a live trap, not cosmetic: it teaches the next reader that a deleted parameter is load-bearing. Also: collapse the duplicated `_draw_no_data` helpers (~45 ln); delete `add_faction_support.py` (dead since 2026-06-04) and remove its mentions from `docs/API.md` and `docs/DATA_MODELS.md`; delete the 47 zero-call and 23 assertion-free tests, of which 12 restate a constant's own definition.
- **Proof:** `grep -rc session_kwarg tests/ src/` returns **0** (today **61**). `grep -rc add_faction_support docs/` returns **0** (today 2 files). `grep -rc '_draw_no_data' demo_game/` shows one definition. Behavioural guard: `make test-demo` still passes 1,116 tests after the `_draw_no_data` collapse.
- **Roadmap phase:** R4

### [CR-L09-04 + 7 merged] Rewrite `CLAUDE.md`; move narrative to skills

- **Verdict:** UPHELD · **Severity:** HIGH · **Effort:** M
- **Depends on:** **R1 complete** — the file must describe the rules that now exist, not the ones that did
- **Blocks:** nothing
- **Chosen approach (per your Phase 0 instruction, and it resolves TRIAGE conflict #4):** Three moves that are compatible only in this order. (1) **Gate what can be gated** — R1 already converted `check-docstrings`, `check-rules` R004/R005, and the file-size rule from form checks to behaviour checks; each gated rule keeps one line in `CLAUDE.md` pointing at its gate. (2) **Move the narrative to skills** — the layer model, the documentation formats, the testing discipline and the coding principles become project skills loaded on demand, not preamble paid on every session. (3) **Delete the fiction** — the 3 contracts whose machinery does not exist (now implemented by CR-L08-03, so this becomes a correction rather than a deletion), the 4-field engine-log mandate (re-measured: **43 `logger.info` calls in `engines/`, 0 containing `duration_ms`** — 0% compliance), the "every session reads ISSUES.md" mandate (~35K tokens / ~2.5 h if honoured, hence silently ignored), and the 3 pre-merge checklist items naming things that do not exist. Rewrite DIP-strict to require **2+ implementors or 3+ callers** — CR-L14-03 measures the current rule at 8,565 lines across 107 files, 44 ports, 14 with one caller, 10 with one method. State the project-over-user-level precedence in one line, and replace the 300/40 hard limits with the two-tier rule from R1. **Replace every factual claim (line counts, gate lists, layer tables) with a pointer to the file holding the truth** — this attacks C4 at its source instead of scheduling the next drift fix.
- **Alternatives rejected:** (a) *Cut to ~120 (only the 8 live rules)* — loses aspirational guidance you want kept. (b) *Correct the 26 false claims without cutting* — keeps the 9,150-token per-session tax. (c) *Add the new gated rules to `CLAUDE.md`* — pulls line count the wrong way; gates live in `scripts/`, and the file references them.
- **Proof:** Three verification commands. `wc -l project-harness/CLAUDE.md` ≤ **250** (today **476**). Every remaining numeric claim resolves: for each `N` asserted in the file, the cited command reproduces `N` — run as a one-off script at close, **today 26 of 109 claims fail it**. And `grep -c 'duration_ms' project-harness/CLAUDE.md` returns 0 (the mandate is gone) *or* `make check-engine-logs` exists and reds (it is now gated) — one or the other, not neither, which is today's state.
- **Files touched:** `project-harness/CLAUDE.md`, `.claude/skills/*`, `project-harness/DECISIONS.md`
- **Risk:** Skills load on demand, so a rule in a skill is a rule an agent may not read. Anything that must hold on *every* session stays in `CLAUDE.md`, however verbose. Judge per rule; when unsure, keep it in the file.
- **Roadmap phase:** R4

### [CR-L07-01 · CR-L07-02 · CR-L07-04 · CR-L07-06 · CR-L07-07 · CR-L07-08 · CR-L11-04] Ledger hygiene

- **Verdict:** UPHELD · **Severity:** HIGH×2, rest MEDIUM/LOW · **Effort:** S
- **Chosen approach:** Close ISSUE-145 (a stale P1 whose root cause was fixed under other IDs) and ISSUE-122 (prescribes a fix already present when filed). **Repair the 5 reused DEC IDs and 2 reused ISSUE IDs** — this is a prerequisite for Phase 4 filing, since naive `max + 1` is wrong; assign the duplicates new IDs and leave a redirect line at the old heading. Retire `SKILLS_QUEUE.md` (dead ~90 days, still normatively referenced). Fix the three scripts sharing one hardcoded stale corpus default, of which only one is tracked.
- **Proof:** A duplicate-ID detector over `DECISIONS.md` + `archive/ISSUES_RESOLVED.md` + `ISSUES.md` returns 0 collisions — **today it returns 7**. `grep -c 'ISSUE-145' project-harness/ISSUES.md` returns 0 (moved to the archive per the CLAUDE.md rule). `grep -rn '<stale corpus default>' scripts/ | wc -l` returns 0.
- **Roadmap phase:** R4

### [CR-L13-01 · CR-L13-02 · CR-L13-04 · CR-L13-08 · CR-L13-09 · CR-L10-02 · CR-L08-08 · CR-L06-12] Documentation repair

- **Verdict:** UPHELD · **Severity:** HIGH×4, rest MEDIUM · **Effort:** S–M
- **Chosen approach:** One pass, and **delete numbers from prose rather than correcting them** — correcting them schedules the next drift. `HARNESS_GATES.md:33-34` says "57 today" and "256 today" against a live 133 and 0, untouched for 85 days: replace both with a `make harness-status` invocation that prints the live values, and fix the "one command" table that lists 5 of the 14 gates `make check` runs. `CONTRIBUTING.md`: 5 links to a `project/` directory that does not exist (`ls project/` → No such file or directory) plus a missing seed command in the quickstart. `README.md`: the "Key files" table points at a source layout that no longer exists, "What's next" lists finished work as open TODOs, and the "Migration scripts" line names two files absent from the repo. `docs/API.md`: add the 6 newest live routes including the undocumented `/setup/*` surface. `CHANGELOG.md`: 96 commits / 13 days stale, still on the pre-rename `project/` tree. `context_builder.py`'s size-justification comment understates the file (799 lines) by 78%. Add the waiver-mandated top-of-file comments to the 4 highest-drift oversized files.
- **Proof:** `grep -rn 'project/' CONTRIBUTING.md README.md CHANGELOG.md` returns **0 rows** (today 5 in CONTRIBUTING alone). Every path named in README's "Key files" table exists — a 5-line script, **today it fails on the source-layout rows**. `make harness-status` prints numbers matching `wc -l scripts/rules_baseline.txt` and `.mypy_baseline`. Onboarding proof: follow `CONTRIBUTING.md` verbatim in a fresh clone and reach a running server — **today the quickstart is missing the seed step and links to a nonexistent directory**.
- **Roadmap phase:** R4

---

# R5 — Integrator-facing

Newly load-bearing: the Unreal DemoGame is a real external consumer, so API and packaging
correctness stopped being hypothetical.

### [CR-L12-07] An API stability policy for 148 operations

- **Verdict:** RECALIBRATED — **MEDIUM → HIGH** (Phase 1)
- **Severity:** HIGH · **Effort:** S · **Risk:** Low
- **Depends on:** none · **Blocks:** nothing — but every day it is late is a day the surface can drift
- **Chosen approach:** Declare a versioning and deprecation policy for the `/v1` surface: what may change without a version bump, what may not, and a minimum deprecation window. Add a contract test that snapshots the OpenAPI schema and fails on a breaking change (a removed route, a removed field, a widened required set) while allowing additive ones. Do this **early and cheaply** — it is insurance whose premium rises the moment Unreal binds to a route.
- **Alternatives rejected:** (a) *Wait until Unreal integration starts* — the whole value is being in place before the first binding. (b) *Freeze the entire surface* — too strict for a pre-1.0 engine still being built.
- **Proof:** `tests/contract/test_api_stability.py::test_no_breaking_schema_change` — remove a field from any `/v1` response model, assert the test reds. **Today no such test exists** and `docs/API.md` governs 148 operations with one sentence of stability policy. The snapshot replaces the deleted `live_openapi.json` with a checked artifact that has a consumer.
- **Files touched:** `tests/contract/test_api_stability.py`, `docs/API.md`, `Makefile`
- **Roadmap phase:** R5 — **do first in this phase**

### [CR-L16-06 + CR-L16-04] One Python target; install the hard dependencies

- **Verdict:** CR-L16-06 RECALIBRATED (resolved by Phase 0 → mechanical) · CR-L16-04 UPHELD
- **Severity:** LOW / HIGH · **Effort:** S / M
- **Depends on:** none · **Blocks:** RAG-path coverage
- **Chosen approach:** 3.14 everywhere, per Phase 0. Set `mypy.ini` `python_version = 3.14` (today 3.11), `requires-python = ">=3.14"` (today `>=3.11`), and rebuild the Docker base off 3.14. Then install the hard deps: `torch>=2.0.0` and `sentence-transformers>=2.6.0` are declared at `pyproject.toml:19-20` but **both fail to import in the dev venv** (`ModuleNotFoundError`, verified), so the embedding and RAG path has never been exercised locally. Either install them or move them to an optional extra and make the RAG path degrade explicitly — but not the current state, where they are mandatory and absent.
- **Alternatives rejected:** *3.11 everywhere* — contradicts CI, README, and the demo's pygame-ce requirement.
- **Proof:** `grep python_version mypy.ini` returns 3.14 and `make type` still passes. `python -c "import torch, sentence_transformers"` exits 0 — **today it raises `ModuleNotFoundError` on both**. Behavioural: a RAG retrieval test runs rather than skipping — count skipped tests in `tests/` mentioning embeddings, **today non-zero**.
- **Files touched:** `mypy.ini`, `pyproject.toml`, `Dockerfile`, `.github/workflows/ci.yml`
- **Risk:** A 3.14 wheel may not exist for every pinned dep. Check before committing to the bump.
- **Roadmap phase:** R5

### [CR-L12-02] Make `make package` build

- **Verdict:** RECALIBRATED — upheld with **stronger, present-tense** evidence
- **Severity:** HIGH · **Effort:** M
- **Chosen approach:** The review argued from the introducing commit; I verified at HEAD. `packaging/npc_engine.spec` declares `datas` referencing `REPO_ROOT/"config"` and `REPO_ROOT/"game_schema.yaml"` — **neither exists** (`ls` fails on both) — and PyInstaller is not a declared dependency. Fix the spec's paths to real ones, add PyInstaller as a packaging extra, and wire `make package` into CI so it cannot silently rot again.
- **Alternatives rejected:** *Delete `make package`* — packaging is a licensing-model requirement and the target is close to working; the paths are simply wrong.
- **Proof:** `make package` exits 0 and produces `dist/npc_engine_server/`. **Today it fails**: `ls -d config game_schema.yaml` → "No such file or directory" for both, and `grep -i pyinstaller pyproject.toml` returns 0 rows. Then a CI job runs it, so the next path rename reds immediately.
- **Files touched:** `packaging/npc_engine.spec`, `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`
- **Roadmap phase:** R5

### [CR-L04-01 + CR-L04-06 + CR-L04-05] Migration safety

- **Verdict:** UPHELD · **Severity:** HIGH / MEDIUM · **Effort:** M
- **Chosen approach:** Give the 7 migrations a down path and an applied-state record (a `SchemaMigration` node keyed by migration id, written in the same transaction as the migration). Add a gate that fails when a required-field schema change ships without a paired migration. Complete `migrate_faction_strings.py`, which migrates data but never retires the field it migrates away from. This matters because migrations run on a customer's data — and with an integrator now real, "customer" is no longer hypothetical.
- **Proof:** `tests/integration/test_migrations.py::test_every_migration_has_down` — enumerate `scripts/migrations/*.py`, assert each exposes `down()`. **Today 0 of 7 do.** And: apply a migration twice, assert the second is a no-op via the applied-state record — **today there is no record, so it re-applies**. Gate proof: add a required field to a node type without a migration, assert `make check-migrations` reds.
- **Files touched:** `scripts/migrations/**`, `scripts/check_migrations.py` (new — **and it must ship with its counterfactual per the R1 DEC**), `Makefile`
- **Roadmap phase:** R5

### [CR-L16-03 · CR-L16-05 · CR-L16-07 · CR-L16-09 · CR-L12-05 · CR-L12-03] Ops and NFRs

- **Verdict:** UPHELD, CR-L12-03 RECALIBRATED (HIGH→MEDIUM) · **Effort:** S each, M for CR-L12-05
- **Chosen approach:** **CR-L16-03**: the documented day-to-day path never rebuilds the app image, and `boot-check`'s staleness detector exists but nothing documented invokes it — wire it into `make demo` and the README. (This matches a standing note on this repo: the Docker app image is **not** bind-mounted, so any before/after measurement needs a rebuild first.) **CR-L16-07**: add a `USER` directive to the Dockerfile and a healthcheck to the `app` service — verified: healthchecks exist on `neo4j` and `redis` only. **CR-L16-09**: replace `NEO4J_AUTH: neo4j/password` with an env-sourced credential. **CR-L16-05**: add a lockfile and dependency ceilings (13 pinned / 7 ranged / 1 unpinned today). **CR-L12-05**: measure the 4 unmeasured NFRs — but **after CR-L01-01**, since benchmarking a broken feature is worthless; the graph holds 52 nodes against a 10,000 target and gossip throughput has never been benchmarked above `max_pairs=20`. **CR-L12-03**: 0 lines of C#/C++ for the named target clients is now planned work, not a gap — the DemoGame is the client.
- **Proof:** `docker inspect` shows a non-root user and a healthcheck on `app` (**today neither**). `grep -c 'neo4j/password' docker-compose.yml` returns 0 (**today 1**). A lockfile exists and `make install` is reproducible from it. `make boot-check` is referenced by a documented target (**today referenced by nothing**). NFR proof: a benchmark reports a number for each of the 4 NFRs (**today unmeasured**).
- **Roadmap phase:** R5

---

# R6 — Overnight loop rework

Kept per Phase 0. The subtraction ledger's §D row 3 is void.

### [CR-L11-09 + CR-L11-03 + CR-L09-03] Fix ISSUE-126, then make HALTs mean something

- **Verdict:** CR-L11-09 RECALIBRATED (**MEDIUM → HIGH**, upgraded because you are restarting the loop) · CR-L11-03 RECALIBRATED (scope changed: acceptance criterion, not deletion evidence) · CR-L09-03 RECALIBRATED (resolved: keep + rework)
- **Severity:** HIGH · **Effort:** M
- **Depends on:** **R1 complete** — the loop's HALTs come from the gate battery, so reworking the loop before the gates can fail means re-tuning it twice
- **Chosen approach:** (a) Fix ISSUE-126 — `--dry-run` hangs; it burned 11.45 h on night one and has been open 26 days. It was deferrable while the loop was dead; restarting makes it a prerequisite. (b) Adopt CR-L11-03's finding as the **acceptance criterion**: every overnight HALT to date was the harness tripping over its own self-tests, not a product defect. Classify HALT causes and make a self-test failure a distinct, non-halting outcome — the loop should stop for product defects and log-and-continue for harness noise. (c) Give the loop a real work queue: this remediation program's R3–R5 items are the first genuine queue it has had.
- **Alternatives rejected:** (a) *Delete the bundle* (the review's recommendation, §D row 3, 5,178 ln) — overridden by your Phase 0 decision. (b) *Restart before R1* — every HALT comes from gates that currently cannot fail; you would tune the loop against theatre.
- **Proof:** `python scripts/expand_loop.py --dry-run` completes in under 60 s and prints a plan. **Today it hangs** (ISSUE-126, open 26 days). Then a HALT-classification test: inject a self-test failure and assert the loop logs and continues; inject a product-test failure and assert it halts. **Today both halt identically**, which is why 100% of historical HALTs were noise.
- **Files touched:** `scripts/expand_loop.py`, `scripts/loop_gates.py`, `project-harness/OVERNIGHT_LOOP.md`
- **Risk:** A loop that continues past self-test failures can run a long way on a broken harness. Cap consecutive non-halting failures.
- **Roadmap phase:** R6

---

# R7 — Deferred large work

### [CR-L02-05] Pydantic models at `BaseEngine.run_tick()` and `LLMClientProtocol.generate_structured()`

- **Verdict:** UPHELD · **Severity:** HIGH · **Effort:** **XL** — the largest item in the review
- **Depends on:** R1, R2, R3 complete · **Blocks:** nothing
- **Chosen approach:** Deliberately last. 145 functions across `engines/`, `graph/` and `retrieval/` return raw dicts across module boundaries against a strict CLAUDE.md rule. This is real debt and the rule is right, but attempting it before the gates can fail and the instrument is trustworthy means a 145-function refactor verified by a test suite that CR-L14-02 proved will not notice if you replace the layer with stubs. Do it after R2 lands Neo4j in CI. Sequence per-package, 29 `run_tick` implementors first.
- **Alternatives rejected:** (a) *Do it now* — unverifiable, per above. (b) *Drop the rule* — it is one of the 8 live, defensible rules, and typed engine boundaries are exactly what an integrator needs.
- **Proof:** `mypy --strict` on `engines/` passes with `dict[str, Any]` banned in public engine signatures — a custom check asserting no public `engines/` function returns a bare `dict`. **Today 145 do.** Incremental proof per package so this is landable in slices.
- **Files touched:** `src/npc_engine/engines/**`, `graph/**`, `retrieval/**`
- **Risk:** Highest-risk item in the program. Do not start it until R2 is green.
- **Roadmap phase:** R7

### [CR-L14-03 + CR-L02-06 + CR-L08-01 + CR-L08-02 + CR-L10-03 + CR-L15-02 + CR-L15-04 + CR-L15-05 + CR-L06-11 + CR-L10-04] Debt with no urgency

- **Verdict:** UPHELD · **Effort:** S–L · **Depends on:** CR-L06-05 (splits re-grow without it)
- **Chosen approach:** Sequenced after R1's two-tier limit lands. **CR-L08-01/02**: `client.py` (1,901), `seed.py` (1,677), `game_window.py` (925 — corrected path: `demo_game/ui/layout/game_window.py`) all exceed the new 800 hard gate and must split. **CR-L02-06**: `config.py` at 504 lines with fan-in 74 and a stale 309-line waiver — the widest blast radius in the repo. **CR-L14-03**: rewrite DIP-strict (in CR-L09-04) then delete the single-caller ports it licensed (~552 ln across 10 files). **CR-L15-02**: `intent_queries.py` at 34.6% real coverage, mocked at three layers with no integration backstop — needs R2's Neo4j. **CR-L15-05**: `mypy src/` runs twice per `make check` under two mechanisms. **CR-L15-04**: correct CLAUDE.md's implication that the per-commit gate costs 595 s when the real hook cost is 4.9 s. **CR-L06-11**: expand the ruff rule set and enable `E501` to match the declared `line-length = 120`; note the review's "runs in 0 s" is not itself evidence of a defect.
- **Proof:** `make check-rules` green with the 800 hard gate active and no file above it (**today 3 files exceed 800**). `grep -c 'mypy src' Makefile` returns 1 (**today 2 invocation paths**). `intent_queries.py` coverage ≥ 70% with Neo4j in CI (**today 34.6% real**). Ruff: add a 130-character line, assert `make lint` reds (**today E501 is off despite `line-length = 120`**).
- **Roadmap phase:** R7

---

## Items with no fix plan, and why

- **WITHDRAWN (7)** — CR-L02-07, CR-L08-06, CR-L10-07, CR-L10-08, CR-L12-06, CR-L12-09, and the "has never run" half of CR-L01-03. Evidence in [TRIAGE.md](TRIAGE.md#withdrawn).
- **DEFERRED-VALID (11)** — CR-L01-13, CR-L07-05, CR-L10-04, CR-L10-06, CR-L11-01, CR-L11-02, CR-L11-05. These are measurements backing the review's §C, not fixable items. Their remedy is the program itself, plus the counterfactual DEC in R1. Filing them as roadmap checkboxes would be the C2 pathology in miniature: converting a diagnosis into process.
- **CR-L01-12** — `engines/deception/` (128 ln) and `engines/currency/` (12 ln stub) have zero production callers, confirmed. Held for integration per your decision; no deletion plan, and no integration plan until you name what they should do.
