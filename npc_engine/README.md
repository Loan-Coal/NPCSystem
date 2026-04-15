# NPC Engine (Work In Progress)

Current stage: M5 (Tests, CI, and Docs)

## Quick Start

1. Install dependencies.
2. Copy or edit .env if needed.
3. Start Neo4j (docker compose included).
4. Run the app.

```bash
make install
make run
```

If you use Ollama backend (`LLM_BACKEND=ollama`), ensure Ollama is running and the selected model is pulled first:

```bash
ollama pull mixtral:8x7b
ollama run mixtral:8x7b
```

## Development Commands

```bash
make lint
make type
make test
make test-cov
make check
make seed
```

## Auth Testing

Set a unique development API secret in .env (length >= 16), for example:
- API_KEY_SECRET=local_dev_secret_change_this_2026

Example protected route check:

```bash
curl -H "Authorization: Bearer <your_api_key_secret>" http://localhost:8000/protected
```

## Stage Tracker

Implementation progress is tracked in ../IMPLEMENTATION_TRACKER.md.

## Ollama Models

Ollama is supported as an LLM backend. The backend stays the same while models are switched by environment variables.

Environment settings:
- `LLM_BACKEND=ollama`
- `OLLAMA_API_URL=http://localhost:11434`
- `OLLAMA_MODEL=mixtral:8x7b`

Examples:
- Use Mixtral locally: `OLLAMA_MODEL=mixtral:8x7b`
- Switch to Mistral: `OLLAMA_MODEL=mistral:7b`
- Switch to Llama: `OLLAMA_MODEL=llama3:8b`

## Distributed Tick Lease

Scheduler ticks now support a Neo4j-backed distributed lease so multiple app workers do not execute the same engine tick.

Environment settings:
- `DISTRIBUTED_TICK_LEASE_ENABLED=true`
- `TICK_SCHEDULER_ID=main`
- `TICK_LEASE_OWNER_ID=` (optional; defaults to hostname-pid)
- `TICK_LEASE_TTL_SECONDS=30`

Operational behavior:
- Worker claims per-engine tick (`gossip` or `event`) before running handler logic.
- Claims are marked done after successful handler execution.
- Handler failures release lease for retry.
- Lease expiration allows takeover by another worker.
