# CR-L16 — Operational & Dependency Risk

Lens: L16. Branch `eval-ab-context-arms` @ `d46ae42`. Windows 11, Git Bash + PowerShell.
Live stack: `npcsystem-app-1`, `npcsystem-neo4j-1` (untouched throughout — verified running
at end of session). All destructive/build tests were run against an isolated clone in
`%TEMP%\...\scratchpad\freshclone\NPCSystem` under compose project `npcfreshtest`, on
remapped port 18000, torn down and deleted at the end (`docker compose down -v`, `docker rmi
npcfreshtest-app`, `rm -rf`).

## Required measurements

### 1. Fresh clone boot (actually attempted, not simulated)

| # | Documented step (README.md Quick Start) | Worked as written? | Gap found |
|---|---|---|---|
| 0 | (implicit) `git clone` | **NO** | Windows `MAX_PATH`: `git clone` aborts with `Filename too long` on `project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-*.md` (15+ paths). Fixed only by `git config core.longpaths true`, which the repo tells no one to set (`git grep -il longpath` → 0 hits in tracked files). |
| 0b | (implicit) provide `.env` | **NO** | `docker-compose.yml:76` declares `env_file: - .env`; only `.env.example` is tracked (`.gitignore:38-40`). `docker compose config` on a truly fresh clone fails immediately: `env file ...\.env not found`. README never says `cp .env.example .env`; that step exists only in `CONTRIBUTING.md`, a different document with a different (contradictory) setup path. |
| 1 | `docker-compose up -d` | **YES, once 0/0b fixed** | After `core.longpaths=true` + `cp .env.example .env`, `docker compose up -d --build` succeeded end-to-end: image built (2.02 GB), neo4j reached healthy, app answered `GET /health` → `{"status":"ok","version":"dev"}`. |
| 2 | `make demo-seed` | Not exercised | Requires `API_KEY_SECRET` alignment with `.env` and a Windows `make`; out of time budget once (1) proved the documented path is two undocumented steps short. |
| 3 | `make demo` | Not exercised (pygame window) | — |
| 4 | `make test` | Not exercised | — |
| 5 | `make eval` | Not exercised | — |

**Result: 5 documented Quick Start lines; step 0 (clone) and step 1 (`docker-compose up -d`)
both fail as written on this platform; 2 undocumented fixes are required before step 1 ever
runs.** Time to a working stack once the fixes were known: ~90 s (build) + ~15 s (neo4j
healthy) after the two blockers were resolved by hand.

Command evidence (paths redacted to `<clone>`):
```
$ git clone <repo> <clone>
error: unable to create file project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-208-retrieval-explainer-panel.md: Filename too long
...(15 similar)...
fatal: unable to checkout working tree

$ git config --global --get core.longpaths   # (empty — not set on this machine)

$ git -c core.longpaths=true clone <repo> <clone>   # succeeds

$ docker compose config
env file <clone>\.env not found: CreateFile <clone>\.env: The system cannot find the file specified.

$ cp .env.example .env && docker compose up -d --build
...
Container npcfreshtest-app-1 Started

$ curl http://127.0.0.1:18000/health
{"success":true,"data":{"status":"ok","version":"dev"},"meta":null}
```

`CONTRIBUTING.md` documents a **third, incompatible** setup path: `docker run -p 7687:7687
neo4j:5` (bypassing `docker-compose.yml` entirely) plus `python -m npc_engine.scripts.seed`,
which does not exist (`src/npc_engine/scripts/` contains only `check_contracts.py`,
`guard_contract_test_sync.py`, `manual_system_test_v14.ps1`, `simulate_world_flow.py` —
confirmed by directory listing). It also points at `project/CLAUDE.md`, which does not exist
(`project-harness/CLAUDE.md` does). Three onboarding documents (README, CONTRIBUTING,
docker-compose.yml's own header comment on ISSUE-131) describe three different, mutually
inconsistent ways to start Neo4j.

### 2. Python 3.14 exposure

Dockerfile (`Dockerfile:1`) is `FROM python:3.11-slim`; `mypy.ini:2` pins `python_version =
3.11`; `pyproject.toml:5` says `requires-python = ">=3.11"`. But `README.md:43` and
`CONTRIBUTING.md:5` say `Python 3.14+`, and `.github/workflows/ci.yml` sets
`python-version: "3.14"` in **every** job (5 occurrences). CI therefore lints, type-checks
(mypy configured for 3.11 syntax rules but *executed* under 3.14), and tests the whole suite
on a Python the production Docker image never runs.

Local dev venv actually in use (`.venv`, Python 3.14.2) confirmed via `pip list`:

| Package | Pinned (pyproject) | Installed in 3.14 venv | Requires-Python (pinned release) | 3.14 verdict |
|---|---|---|---|---|
| fastapi | ==0.116.1 | 0.116.1 | >=3.8 (no 3.14 classifier) | Installs, untested-on-3.14 by upstream |
| uvicorn[standard] | ==0.35.0 | 0.35.0 | >=3.9 (no 3.14 classifier) | Installs, untested |
| pydantic | ==2.12.1 | 2.12.1 | >=3.9, **3.14 classifier present** | OK |
| pydantic-settings | ==2.11.0 | 2.11.0 | >=3.9 (no 3.14 classifier) | Installs, untested |
| PyYAML | ==6.0.2 | 6.0.2 | >=3.8 (no 3.14 classifier), has C ext (libyaml) | Installs, untested |
| types-PyYAML | unpinned | 6.0.12.20260408 | n/a (stub-only) | n/a |
| neo4j | ==5.28.2 | 5.28.2 | >=3.7 (no 3.14 classifier) | Installs, untested |
| redis | ==5.2.1 | 5.2.1 | >=3.8 (no 3.14 classifier) | Installs, untested |
| httpx | ==0.28.1 | 0.28.1 | >=3.8 (no 3.14 classifier) | Installs, untested |
| sentence-transformers | >=2.6.0 (unbounded) | **NOT INSTALLED** | — | **BLOCKS** — see below |
| torch | >=2.0.0 (unbounded) | **NOT INSTALLED** | — | **BLOCKS** — see below |
| pytest | ==8.4.2 | 8.4.2 | >=3.9, 3.14 classifier present | OK |
| pytest-asyncio | ==1.2.0 | 1.2.0 | >=3.9, 3.14 classifier present | OK |
| pytest-cov | ==6.3.0 | 6.3.0 | >=3.9 (no 3.14 classifier) | Installs, untested |
| ruff | ==0.13.0 | 0.13.0 | >=3.7 (Rust binary, no ext build) | OK |
| mypy | ==1.18.2 | 1.18.2 | >=3.9, 3.14 classifier present | OK |

**Confirmed defect, not merely a version-lag risk**: the checked-in, hard (non-optional)
dependencies `torch>=2.0.0` and `sentence-transformers>=2.6.0` (`pyproject.toml:15-16`) are
**absent** from the maintainer's own 3.14 dev venv:
```
$ .venv/Scripts/python.exe -m pip show torch
WARNING: Package(s) not found: torch
$ .venv/Scripts/python.exe -c "import torch"
ModuleNotFoundError: No module named 'torch'
```
Every call site that imports them is a lazy import guarded only at call time, not at process
start (`src/npc_engine/retrieval/embedding/sentence_encoder.py:33,36`,
`src/npc_engine/retrieval/embedding/cross_encoder_reranker.py:28`), so the RAG/embedding path
(a stated core feature — README "Embedding reconciler ✅") is silently unexercised by anyone
running the documented dev venv, and will only fail the first time embedding code actually
runs. A `pip download --no-deps torch` dry run (network, no install) shows a `cp314-win_amd64`
wheel for `torch==2.13.0` *does* exist as of this session's date, so the gap is a stale/never-
completed local install, not (currently) a hard PyPI wall — but nothing pins a wheel-tested
`torch`/`sentence-transformers` version, so this is one silent transitive bump away from
reappearing when a wheel is later pulled.

**3.13-downgrade / 3.15-upgrade blockers**: none of the pinned packages declare an upper Python
bound, so nothing in the manifest *forbids* either move — but `torch`/`sentence-transformers`
have no floor pin either, so either move re-resolves to whatever the latest matching wheel is
at install time, with no record of what was actually validated.

### 3. Unpinned dependencies

| Manifest | Total deps | Exact-pinned (`==`) | Open range (`>=`, no ceiling) | Fully unpinned (no spec) |
|---|---|---|---|---|
| `pyproject.toml` (main + `[dev]`) | 16 | 13 | 2 (`sentence-transformers`, `torch`) | 1 (`types-PyYAML`) |
| `demo_game/requirements.txt` | 5 | 0 | 5 (`httpx`, `pydantic-settings`, `pygame-ce`, `networkx`, `matplotlib`) | 0 |
| **Combined** | **21** | **13 (62%)** | **7 (33%)** | **1 (5%)** |

**No lockfile of any kind** exists — confirmed by `find . -iname "requirements*.txt"` (only
`demo_game/requirements.txt`, itself unpinned) and absence of `poetry.lock`, `uv.lock`,
`Pipfile.lock`, or a hash-pinned `requirements.txt` anywhere in the tree. Even the 13
exact-pinned top-level packages have **zero transitive pins** — `fastapi==0.116.1` pulls
`starlette`, `pydantic_core`, etc. at whatever version resolves *today*. Rebuilding the image
from a commit six months old will silently resolve different `torch`, `sentence-transformers`,
`pygame-ce`, `networkx`, `matplotlib`, and every transitive dependency of every package —
there is no way to reproduce a specific past build byte-for-byte.

### 4. Single-LLM SPOF (`qwen2.5:7b` via Ollama)

- **Configured model, traced**: `src/npc_engine/engines/dialogue/llm_config.yaml:3-4` →
  `backend: ollama`, `model: qwen2.5:7b`. Matches README/CONTRIBUTING's documented model.
- **Live Ollama** (`GET /api/tags`, confirmed): `llama3.1:8b`, `cyoa-lora:latest`,
  `qwen2.5:7b`, `qwen2.5:14b`, `mixtral:8x7b` — the configured tag is present; no drift found
  between config and running server.
- **Fallback contract, traced end to end and CONFIRMED wired** (contrary to a naive read of
  "sibling lens confirmed the Neo4j half is unimplemented" — the dialogue LLM half is real):
  `dialogue_handler.py:179` → `DialogueLLMClient(fallback_path=settings.LLM_FALLBACK_PATH, ...)`
  → `llm_client.py:107-113`: `except LLMTimeoutError` / `except LLMRequestError` both call
  `self._fallback_with_metrics(...)` → `_load_fallback_dialogue()` →
  `json.loads(Path(self._fallback_path).read_text())` reading
  `src/npc_engine/data/fallback_responses.json` (file exists, confirmed present on disk).
  Also wired on `stream_text()` (`llm_client.py:~230`, same exception pair).
- **Coverage gap**: `grep -rl "fallback_path\|LLMTimeoutError" src/npc_engine/engines/{chapter,proactive_dialogue,quest_generation,memory_consolidation}` finds it only in `proactive_dialogue` and `quest_generation`; `chapter` and `memory_consolidation` have **no** matching hit, i.e. no traced timeout-fallback path in this pass — not confirmed broken (needs a targeted repro), so reported as Suspected, not Critical.
- **Model-tag mutability**: Ollama tags (`qwen2.5:7b`) are **not content-addressed** — a
  `docker exec ... ollama pull qwen2.5:7b` re-pull can silently swap the underlying weights
  the tag points to. `llm_config.yaml` records only the tag string, never a digest. Any two
  eval runs months apart that both say "qwen2.5:7b" are not provably the same model.

### 5. Secrets

- Working tree `git grep` (API-key/AWS-key/private-key/password patterns) across all tracked
  files: **0 hits** outside test fixtures and `.env.example` placeholders.
- `git log --all -p -S"sk-"` / `-S"AKIA"` / `-S"BEGIN ... PRIVATE KEY"`: **0 real matches**
  (only unrelated doc content containing the substring "sk-" as part of prose; no key-shaped
  strings; one `git log` diff-scan error on an unrelated orphaned `~$esting.docx` blob in this
  machine's local git-blob temp cache, not part of the repo history).
- `.env` was **never committed**: `git log --all --oneline -- .env` → empty. `.env.demo`
  likewise empty. `.gitignore:38-41` covers `*.env`, `.env.*`, with an explicit
  `!.env.example` carve-out — correctly scoped.
- All `API_KEY_SECRET=` values found in history (`git log --all -p -S"API_KEY_SECRET="`) are
  clearly-fake dev/test placeholders: `"npc_dev_secret_2026_alpha"`,
  `"local_dev_secret_change_this_2026"`, `"test-api-key-secret-ci"`. **No live secret found,
  in working tree or history.**
- `docker-compose.yml:34` ships `NEO4J_AUTH: neo4j/password` — the Neo4j-documented default
  credential pair, unchanged. Not a leaked secret (it's a public, well-known default), but it
  is the literal shipped default in a file every clone gets. Neo4j has no host port mapping
  (by design, per the file's own header comment, EVAL-P20.3a/ISSUE-131), so today this is not
  externally reachable — but the credential is real and would matter the moment anyone adds a
  host port mapping (e.g. copying the `demo-snapshot` "run inside app container" pattern to a
  quick local hack, or a future prod compose file inheriting this default uncritically).

### 6. Licence conflicts

`pip-licenses` run against the actual 3.14 dev venv (`piplicenses --format=markdown`):

| Package | Licence | Confined to |
|---|---|---|
| **pygame-ce 2.5.7** | **GNU LGPL** | `demo_game/` only (`demo_game/requirements.txt`) |
| numpy | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | transitive (via sentence-transformers/matplotlib) |
| everything else (fastapi, uvicorn, pydantic\*, neo4j, redis, httpx, PyYAML, matplotlib, networkx, tiktoken, etc.) | MIT / BSD / Apache-2.0 / PSF | — |

**Only copyleft package found: `pygame-ce`, LGPL.** Per `CLAUDE.md`'s own architecture table,
`demo_game/` has "zero imports from `src/`" and is explicitly the pygame demo UI, not the
licensed engine. `docs/BUSINESS_REQUIREMENTS.md` describes the licensed product as "a plugin
for both Unity and Unreal Engine games" exposing "a clean HTTP + WebSocket API" — i.e. the
`src/npc_engine` FastAPI service, which does not import pygame-ce anywhere (`pyproject.toml`
main dependencies list has no pygame reference; it lives solely in
`demo_game/requirements.txt`). **No copyleft package is inside the artefact that gets licensed
to game studios**, on current evidence. Flagging as LOW/Process rather than HIGH: the risk is
that nothing in the repo *enforces* this separation (no test, no CI check, no packaging
manifest excludes `demo_game/` from a hypothetical "engine" distribution build) — it currently
holds only because no packaging step exists yet that bundles the two together.

### 7. Image/runtime hygiene

| Check | Result |
|---|---|
| Runs as root? | **YES** — no `USER` directive in `Dockerfile`; `docker exec npcsystem-app-1 id` → `uid=0(root) gid=0(root) groups=0(root)` |
| Healthcheck on `app` service? | **NO** — `docker-compose.yml` has `healthcheck:` blocks only for `neo4j` (line 43) and `redis` (line 58); the `app` service (lines ~62-83) has none, despite `GET /health` existing and being polled externally by `boot_check.py` |
| `restart` policy on `app`? | `restart: on-failure:5` (present) |
| `BUILD_SHA` actually used for staleness detection? | **Partially.** `Dockerfile:24-26` bakes `ARG BUILD_SHA=dev` → `ENV BUILD_SHA` and `/health` reports it as `version`. `make boot-check` (`Makefile:45-46`) *does* pass `BUILD_SHA=$(git rev-parse --short HEAD)` and forces `--build`. But the currently-running `npcsystem-app-1` reports `"version":"dev"` — proving it was **not** started via `make boot-check`, but via a plain `docker-compose up -d` / `up -d --build` (`make demo`, `make demo-seed`'s prerequisite, and the README Quick Start all say exactly `docker-compose up -d`, none pass `BUILD_SHA`). So the staleness detector exists and works when invoked, but no documented day-to-day command path invokes it — `version: "dev"` is what everyone actually sees, always. |
| Is the running image actually stale right now? | **NO, checked and confirmed fresh** — despite the image being built at `2026-08-27T19:09:21Z` and commit `96d83eb` (touching `src/npc_engine/config.py`) landing later at `19:23:00Z`, a live `md5sum` diff of `config.py`, `config_prompt_window.py`, `main.py`, and `dialogue_handler.py` between host and `docker exec` shows **byte-identical** content (working-tree edit predates both the commit and the build, at `19:02:07Z`). This particular container is current; the finding is about the *process*, not this instant. |
| Reproducible build? | **NO** — see §3 (no lockfile, no transitive pins); `Dockerfile:12` even installs CPU-only `torch` via a separate untagged index step before the pinned-but-unbounded `sentence-transformers`/`torch` resolve in `pip install -e .` |

## Findings

### [CR-L16-01] Fresh clone cannot boot on Windows without two undocumented fixes

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `git clone` of HEAD on this Windows 11 machine fails with `error: unable to
  create file project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-208-retrieval-explainer-panel.md: Filename too long` (15 similar paths) unless
  `git config core.longpaths true` is set first (`git config --global --get core.longpaths`
  returns empty on this machine). Separately, `docker-compose.yml:76` requires `env_file:
  - .env`, but only `.env.example` is tracked (`.gitignore:38-40`); `docker compose config`
  on a fresh clone fails with `env file ...\.env not found`. README.md's Quick Start
  (`README.md:42-54`) contains neither fix. Both were reproduced and then fixed in an isolated
  clone (`compose project npcfreshtest`, port 18000), after which `docker compose up -d --build`
  succeeded and `/health` returned 200.
- **Cost of inaction:** Every new Windows contributor or evaluator hits a dead stop at `git
  clone`, then a second dead stop at the very first documented command, with an error message
  that does not point at either root cause.
- **Fix sketch:** Add `git config core.longpaths true` (or shorten the offending
  `project-harness/archive/...` paths / split them across shorter directories) and add `cp
  .env.example .env` as an explicit Quick Start line in README.md, matching what
  CONTRIBUTING.md already does for its (different) path.
- **Effort:** S (<2h)
- **Blast radius:** Onboarding docs only; no code change required for the `.env` half, a
  one-line git-config note or repo-relative path shortening for the long-path half.

### [CR-L16-02] Three mutually contradictory setup docs (README vs CONTRIBUTING vs compose header)

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `README.md:42-48` says `docker-compose up -d` then `make demo-seed`.
  `CONTRIBUTING.md:20-30` says `pip install -e .[dev]`, `docker run -p 7474:7474 -p 7687:7687
  -e NEO4J_AUTH=neo4j/password neo4j:5`, `uvicorn npc_engine.main:app --reload`, then `python -m
  npc_engine.scripts.seed` — a module that does not exist (`src/npc_engine/scripts/` contains
  only `check_contracts.py`, `guard_contract_test_sync.py`, `manual_system_test_v14.ps1`,
  `simulate_world_flow.py`, confirmed by directory listing). CONTRIBUTING.md also references
  `project/CLAUDE.md`, which does not exist (`project-harness/CLAUDE.md` does — confirmed with
  `ls`). `docker-compose.yml`'s own header comment documents *why* Neo4j has no host port
  mapping (EVAL-P20.3a/ISSUE-131) — directly contradicting CONTRIBUTING's raw `docker run -p
  7687:7687` instruction, which assumes host-reachable Bolt.
- **Cost of inaction:** A contributor following CONTRIBUTING.md verbatim hits an
  `ImportError`/`ModuleNotFoundError` on the seed step and a wrong mental model of how Neo4j
  networking works in this repo.
- **Fix sketch:** Delete CONTRIBUTING.md's `Setup`/`Running the server` sections and point to
  the README Quick Start as the single source of truth, or update its module path and
  `project/` → `project-harness/` reference.
- **Effort:** S (<2h)
- **Blast radius:** Documentation only.

### [CR-L16-03] Documented day-to-day path never rebuilds the app image; staleness detector exists but is unused by it

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `Makefile:45-46` (`boot-check`) is the only target that passes `BUILD_SHA=$(git
  rev-parse --short HEAD)` with `--build`. `demo:` (`Makefile:571-573`), `demo-seed`, and the
  README/Quick-Start's own `docker-compose up -d` all start the stack **without** `--build` and
  without `BUILD_SHA`. The live container `npcsystem-app-1` right now reports
  `{"version":"dev"}` via `/health` — proving normal operation never exercises the SHA-based
  staleness check `e2e/scripts/boot_check.py` implements. If a developer edits `src/` and then
  runs `make demo` (the documented demo path), the container keeps serving the pre-edit image
  with no visible signal — `version` stays `"dev"` whether the image is one hour or one month
  old.
- **Cost of inaction:** Exactly the failure mode the maintainer's own memory note already
  flagged: a live before/after measurement (an eval run, a demo recording, a bug
  reproduction) silently runs stale code, and nothing in the tool's own output distinguishes
  stale from fresh.
- **Fix sketch:** Make `demo`/`demo-seed`/`demo-run` depend on `boot-check` (or on a
  lighter `docker compose up -d --build` with `BUILD_SHA` set), or have `/health` refuse to
  report a bare `"dev"` and instead always compute a content hash of the installed package at
  startup.
- **Effort:** S (<2h) — wire existing `boot-check` target as a prerequisite of `demo`/`demo-seed`.
- **Blast radius:** `Makefile` demo targets only; no application code changes.

### [CR-L16-04] `torch` and `sentence-transformers` are hard dependencies but absent from the maintainer's own 3.14 dev venv

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `pyproject.toml:15-16` lists `sentence-transformers>=2.6.0` and
  `torch>=2.0.0` as unconditional (non-optional) `[project.dependencies]`. In the repo's own
  `.venv` (Python 3.14.2, the version CI and README/CONTRIBUTING mandate):
  `python -m pip show torch` → `WARNING: Package(s) not found: torch`;
  `python -c "import torch"` → `ModuleNotFoundError: No module named 'torch'`. Same for
  `sentence_transformers`. These are imported (lazily, at call time, not at process start) by
  `src/npc_engine/retrieval/embedding/sentence_encoder.py:33,36` and
  `src/npc_engine/retrieval/embedding/cross_encoder_reranker.py:28` — the embedding/RAG path
  the README lists as a shipped feature ("Embedding reconciler ✅").
- **Cost of inaction:** Anyone running unit tests or the API server out of this venv gets a
  silent gap: embedding/RAG code paths are never exercised locally and only fail the first time
  they're hit (e.g. in Docker, where the Dockerfile does separately `pip install torch` via the
  CPU wheel index — so the container is fine; only the bare local venv is affected). A
  contributor debugging retrieval issues locally will get an opaque `ModuleNotFoundError`
  instead of the real bug.
- **Fix sketch:** Re-run `pip install -e .[dev]` in the tracked dev venv (or document that the
  venv must be rebuilt after any `pyproject.toml` dependency change), and add a `make
  check-venv` sanity import check.
- **Effort:** S (<2h)
- **Blast radius:** Local dev environment only; Docker image already installs these correctly.

### [CR-L16-05] No dependency ceiling anywhere and no lockfile — unreproducible builds

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** Of 21 total declared dependencies across `pyproject.toml` and
  `demo_game/requirements.txt`, 13 are exact-pinned, 7 use an open `>=` range with no ceiling
  (`sentence-transformers`, `torch`, and all 5 of `demo_game/requirements.txt`'s deps), and 1
  (`types-PyYAML`) has no version specifier at all. No `poetry.lock`, `uv.lock`,
  `Pipfile.lock`, or hash-pinned `requirements.txt` exists anywhere in the tree (`find . -iname
  "requirements*.txt"` returns only the unpinned `demo_game/requirements.txt`). Even the 13
  exact-pinned top-level packages carry zero transitive pins.
- **Cost of inaction:** A build from a commit six months old will silently resolve whatever
  `torch`/`sentence-transformers`/`pygame-ce`/`networkx`/`matplotlib`/transitive-dependency
  versions are current *then*, not what was validated *at that commit*. A regression bisect
  across old commits cannot trust that the dependency tree, not the code, is the variable that
  changed.
- **Fix sketch:** Add upper bounds to the 7 ranged deps, pin `types-PyYAround`, and generate a
  lockfile (`pip-compile` / `uv lock`) checked into the repo.
- **Effort:** M (<1d)
- **Blast radius:** Build tooling only; touches `Dockerfile`'s pip install layer caching
  strategy (lockfile becomes the new cache key).

### [CR-L16-06] Two incompatible Python-version targets: Docker/mypy on 3.11, CI/README on 3.14

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `Dockerfile:1` → `FROM python:3.11-slim`; `mypy.ini:2` →
  `python_version = 3.11`; `pyproject.toml:5` → `requires-python = ">=3.11"`. Meanwhile
  `.github/workflows/ci.yml` sets `python-version: "3.14"` in all 5 jobs, and
  `README.md:43`/`CONTRIBUTING.md:5` both say "Python 3.14+". CI therefore lints, type-checks,
  and runs the full test suite under 3.14 while the artefact that actually ships (the Docker
  image) runs 3.11.
- **Cost of inaction:** A 3.14-only stdlib/typing behaviour difference that CI is green on
  could behave differently — or not be exercised at all — in the production container, and
  vice versa; mypy is configured for 3.11 syntax rules while actually invoked under a 3.14
  interpreter in CI, an unverified combination.
- **Fix sketch:** Pick one target. If the shipped image is 3.11 (as Dockerfile says), run CI on
  3.11 too, or explicitly document why the demo (`pygame-ce`, no 3.14 wheel for classic
  `pygame`) needs 3.14 while the engine ships on 3.11, and gate CI on both.
- **Effort:** M (<1d) — requires deciding the real target, not just a config edit.
- **Blast radius:** CI workflow, `Dockerfile` base image, `mypy.ini` — a real compatibility
  decision, not a mechanical fix.

### [CR-L16-07] `app` container runs as root with no healthcheck

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `Dockerfile` has no `USER` directive at any layer;
  `docker exec npcsystem-app-1 id` → `uid=0(root) gid=0(root) groups=0(root)`.
  `docker-compose.yml` has `healthcheck:` blocks for `neo4j` (line 43) and `redis` (line 58)
  but none for `app`, despite `GET /health` existing and being polled externally by
  `e2e/scripts/boot_check.py` and `restore-with-app-stopped`'s own curl loop
  (`Makefile:657-660`) — the exact probe a compose-native healthcheck would replace.
- **Cost of inaction:** A container-escape bug in any dependency (torch, PyYAML's C extension,
  Pillow) runs as root inside the container by default; `docker compose`/orchestrators cannot
  use `depends_on: condition: service_healthy` on `app` the way they already do on `neo4j`.
- **Fix sketch:** Add `USER app` after installing dependencies (before `COPY src/`, adjusting
  file ownership), and add a `healthcheck:` block on `app` reusing the existing `/health`
  endpoint the Makefile already polls.
- **Effort:** S (<2h)
- **Blast radius:** `Dockerfile` (needs a non-root user + chown of `/app`), `docker-compose.yml`.

### [CR-L16-08] Ollama model tag is not content-addressed — eval scores are not provably comparable across time

- **Severity:** LOW
- **Confidence:** Likely
- **Kind:** Risk
- **Evidence:** `src/npc_engine/engines/dialogue/llm_config.yaml:3-4` records only
  `backend: ollama`, `model: qwen2.5:7b` — a mutable tag, not a digest. Live `GET
  /api/tags` confirms the tag currently resolves to a running `qwen2.5:7b`, but nothing in
  the repo records or checks a model digest/hash anywhere a generation record is written
  (not found in this pass; scoped search only).
  `docs/EVAL_METHODOLOGY.md`/`evals/` were not audited for a digest-pinning mechanism in this
  lens — reported as Likely, not Confirmed, pending that check.
- **Cost of inaction:** A `docker exec ... ollama pull qwen2.5:7b` re-pull between two eval
  runs both labelled "qwen2.5:7b" can silently swap the weights being scored, invalidating any
  before/after comparison that assumes model identity.
- **Fix sketch:** Record the Ollama model digest (`ollama show qwen2.5:7b --modelfile` or the
  `/api/show` digest field) alongside every generation record.
- **Effort:** S (<2h)
- **Blast radius:** `evals/` generation-record schema; additive field only.

### [CR-L16-09] Neo4j ships with the documented default credential pair

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `docker-compose.yml:34` → `NEO4J_AUTH: neo4j/password`, Neo4j's own
  documented default. Currently contained by network isolation (`internal: true`, no host
  port mapping — confirmed by the file's own header comment and by this session's `docker ps`
  showing no `7474`/`7687` host binding). No secret leak — this is a public, well-known
  default, not a credential someone else can see — but it is the literal value every clone
  gets, with nothing forcing it to change before any future compose variant adds a host port.
- **Cost of inaction:** The moment anyone (a demo tweak, a debugging session, a different
  compose profile) republishes Neo4j's port without also changing this default, it is
  immediately exploitable.
- **Fix sketch:** Generate a random password at `docker-compose up` time via a `.env`-sourced
  variable with no shipped default, or add an explicit comment in `docker-compose.yml` warning
  against ever publishing Neo4j's port without changing it first.
- **Effort:** S (<2h)
- **Blast radius:** `docker-compose.yml`, `.env.example`.

## Not investigated / needs a human decision

- Whether `chapter` and `memory_consolidation` engines have a working LLM-timeout fallback —
  no matching `fallback_path`/`LLMTimeoutError` hit found in this pass (Suspected only, not
  traced end to end; see §4).
- Whether `evals/` records an Ollama model digest anywhere (CR-L16-08 is Likely, not Confirmed).
- `make demo-seed` / `make demo` / `make test` / `make eval` were not exercised end-to-end in
  the fresh-clone test (time-boxed after the clone/`.env` blockers alone proved the finding);
  a follow-up session could complete the walkthrough now that both blockers are known.
- Whether `demo_game/`'s LGPL (`pygame-ce`) exposure is acceptable long-term depends on a
  packaging decision (does a future "licensed engine" distribution ever bundle `demo_game/`?)
  that only the maintainer can make — currently the two are cleanly separated by the existing
  layer rule, but nothing mechanically enforces that separation into a packaged artefact.
