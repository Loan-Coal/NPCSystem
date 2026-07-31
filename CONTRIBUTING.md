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
pip install -e .[dev]
cp .env.example .env        # fill in NEO4J_URI, API_KEY_SECRET
```

## Running the server

```bash
docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5
uvicorn npc_engine.main:app --reload
# seed the graph in a second terminal:
python -m npc_engine.scripts.seed
```

## Tests

```bash
make test       # unit + integration (no live server needed)
make eval       # eval harness (requires running server + Neo4j)
make smoke      # gateway smoke test (requires running server)
```

All tests must be green before merging. See `project/CLAUDE.md` § "Pre-merge checklist"
for the full list of required checks.

## Before you commit

Read `project/CLAUDE.md` before writing any code — it is the authoritative rules file.
Key points:

- **Layer model**: dependencies point downward only (`api → engines → retrieval → graph → config`). No upward imports.
- **File size**: 300-line hard limit on non-test code. Split before merging.
- **Docstrings**: every public function and class requires a docstring. See CLAUDE.md § "Documentation" for the exact format.
- **Prompts**: no prompt strings outside `prompts/`. Everything passed to an LLM lives in versioned YAML.
- **Deferred work**: anything you notice but do not fix goes in `project/ISSUES.md`.
- **Non-obvious choices**: write a `project/DECISIONS.md` entry and get approval before changing a public interface, adding a dependency, or modifying graph schema.

## Commit format

```
<type>: <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

## Design changes

Stop and write a `project/DECISIONS.md` entry before:
- Changing a public interface that has callers outside its module
- Adding a new dependency
- Changing the schema of a graph node or edge
- Touching CI configuration
- Violating any layer rule
