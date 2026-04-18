# NPC Engine (v1.4 rollout)

Current stage: P5 (Observability and dashboards)

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
make test-cov-v13
make check
make test-v13-contracts
make test-v13-graph-admin
make test-v13-retrieval
make test-v14-p4
make test-v14-p5
make check-contract-sync
make verify-v14-p4
make verify-v14-p5
make verify-v13
make seed
```

## Observability Artifacts

- Staging dashboard definition: observability/staging_dashboard.json
- Staging alert rules: observability/staging_alert_rules.yaml
- Notes and label policy: observability/README.md

## v1.3 API and Runtime Notes

- Runtime and graph APIs are versioned under `/v1/*` (except `/health`).
- Graph write routes require `graph_write` scope.
- Graph admin routes require `graph_admin`, which is a strict superset of `graph_write`.
- Startup is fail-fast on schema issues (`GAME_SCHEMA_PATH`).
- A background embedding reconciler runs every `EMBEDDING_RECONCILE_INTERVAL_SECONDS` and heals stale embedding entries by comparing graph write timestamps.

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

## Embedding Reconciliation

Embedding staleness is self-healed in the background.

Environment settings:
- `EMBEDDING_RECONCILE_INTERVAL_SECONDS=300`
- `EMBEDDING_REFRESH_ON_WRITE=true`

Operational behavior:
- Reconciler scans graph nodes for stale embedding timestamps.
- Each stale node is re-embedded and marked with `last_embedding_indexed_at`.
- Admin route `/v1/graph/admin/reindex` remains available for manual reindex workflows.

Operational behavior:
- Worker claims per-engine tick (`gossip` or `event`) before running handler logic.
- Claims are marked done after successful handler execution.
- Handler failures release lease for retry.
- Lease expiration allows takeover by another worker.
