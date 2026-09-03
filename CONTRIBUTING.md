# Contributing

## Prerequisites

- Python 3.14+
- Neo4j 5 (Docker recommended — see quick start below)
- Ollama with `qwen2.5:7b` (DEC-149). `mixtral:8x7b` is additionally required only for
  the LLM-judge eval suite (DEC-143).

### Running without a local LLM

There is **no env var for this** — `LLM_BACKEND` was removed in ISSUE-003 and the leftover
`.env` key was deleted in DEC-150. Backend and model are per-engine: set `llm.backend: mock`
in each of the five `src/npc_engine/engines/*/llm_config.yaml` files to use the deterministic
`MockLLMAdapter`. Registered backends are `mock`, `ollama`, `openai`; an unregistered name
fails at config load, not at request time.

Note this leaves five tracked files dirty in your working copy — do not commit them.

## Setup

```bash
# On Windows, BEFORE cloning. Some paths under project-harness/archive/ exceed the
# 260-character default; without this the checkout aborts with "fatal: unable to
# checkout working tree" and silently leaves thousands of files missing.
git config --global core.longpaths true

pip install -e .[dev]
cp .env.example .env        # fill in NEO4J_URI, API_KEY_SECRET
```

`.env` is gitignored — only `.env.example` is tracked — so a fresh clone has no `.env` at
all and the server will not start until you copy it.

## Running the server

```bash
docker compose up -d neo4j
uvicorn npc_engine.main:app --reload
# seed the demo world in a second terminal:
make demo-seed
```

## Tests

```bash
make test              # unit suite
make test-integration  # needs Neo4j reachable on bolt — see below
make eval              # eval harness (requires running server + Neo4j)
make smoke             # boot smoke test
```

Integration tests need the **test compose override** (DEC-232). The base compose does not
publish bolt to the host, so without it the suite reports passes and skips while testing
nothing:

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d neo4j
NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=password   make test-integration
```

Three integration tests are known-failing and allowlisted in
`scripts/integration_baseline.txt`; `make check-integration-baseline` fails on a fourth.

All tests must be green before merging. `make check` is the full list — run
`make harness-status` to see what it covers and where each baseline stands.

## Before you commit

Read `project-harness/CLAUDE.md` before writing any code — it is the authoritative rules file.
Key points:

- **Layer model**: dependencies point downward only. `scripts/check_layers.py` holds the
  authoritative edge list and `make check-layers` enforces it. No upward imports.
- **File size**: two tiers (DEC-226) — 400 lines advisory, 800 lines a hard unwaivable
  gate, and a file already on the `check-rules` baseline may not grow past its recorded
  count. `make check-rules` enforces all three.
- **Docstrings**: every public function and class requires a docstring. See CLAUDE.md § "Documentation" for the exact format.
- **Prompts**: no prompt strings outside `prompts/`. Everything passed to an LLM lives in versioned YAML.
- **Deferred work**: anything you notice but do not fix goes in `project-harness/ISSUES.md`.
- **Non-obvious choices**: write a `project-harness/DECISIONS.md` entry and get approval before changing a public interface, adding a dependency, or modifying graph schema.

## Commit format

```
<type>: <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

## Design changes

Stop and write a `project-harness/DECISIONS.md` entry before:
- Changing a public interface that has callers outside its module
- Adding a new dependency
- Changing the schema of a graph node or edge
- Touching CI configuration
- Violating any layer rule
