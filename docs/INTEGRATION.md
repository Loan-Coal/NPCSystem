# NPC Engine — Unity Integration Contract

> **Scope:** This document describes the REST/WS surface a native Unity client
> (or any native game client) uses to communicate with the NPC Engine backend.
> It is a **runtime contract** — not a frozen OpenAPI spec (that is SX.1).
> Routes and shapes may evolve; breaking changes will be announced.

---

## 1. Process model

```
game.exe
  └── spawns  launcher.exe  (PyInstaller binary from scripts/launcher.py)
                  ├── starts  Neo4j
                  ├── starts  Ollama  (local-inference path only)
                  └── starts  uvicorn  →  NPC Engine FastAPI app  (localhost:8080)
```

- The launcher binds the engine to **127.0.0.1:8080** only — not reachable off-box.
- The Unity process polls `GET /readiness` (see §3) until the engine signals ready.
- The launcher writes `NPC_ENGINE_READY` to stdout when `/readiness` responds 200.
  Game process can wait for this line rather than polling.
- On game exit, the game process kills `launcher.exe`; the launcher's `shutdown()`
  terminates Neo4j and Ollama sub-processes.

---

## 2. Authentication

All routes require a **Bearer token** except the three public groups:

| Path | Auth required | Notes |
|------|--------------|-------|
| `GET /health` | No | Liveness probe — always public |
| `GET /readiness` | No | Dependency readiness — always public |
| `POST /setup/*`, `GET /setup/*` | No | First-run wizard routes (localhost-only by bind, DEC-131) |
| All other `/v1/*` routes | Yes | `Authorization: Bearer <API_KEY_SECRET>` |

The **engine API key** (`API_KEY_SECRET`) is a shared secret distributed with the
game package (or generated at install time). It is NOT the player's LLM API key.

### Security posture (DEC-131)

- **No CORS middleware.** The Unity client is a native desktop process, not a browser.
  CORS is a browser-only concern; revisit only if a WebGL target is added.
- **Setup routes are localhost-only by bind**, not by middleware token check. The
  `127.0.0.1` bind (set in `stack_launcher.py`) is the trust boundary. No token
  bootstrap is needed for setup routes.
- **The player's LLM API key (path B) is stored plaintext** in
  `~/.npc_engine/wizard_config.json` by design. It is the player's own key on their
  own machine. File permissions are controlled by the OS user profile.

---

## 3. Startup sequence for Unity

```
1. Spawn launcher.exe
2. Poll stdout line-by-line; wait for "NPC_ENGINE_READY"
   -or- poll GET /readiness every 500ms until HTTP 200

3. If first run (wizard not completed):
   GET  /setup/config           → 404 → show wizard screen
   POST /setup/validate  {path, config}   → ValidationResult
   POST /setup/config    {WizardConfig}   → echo saved config
   GET  /setup/config           → 200 + WizardConfig

4. Normal operation:
   Authorization: Bearer <API_KEY_SECRET>
   → all /v1/* routes
```

---

## 4. Key routes (summary)

Full OpenAPI docs at `GET /docs` (dev mode only).

### Liveness / readiness

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Process liveness; returns `{status: "ok", version}` |
| GET | `/readiness` | No | Dependency readiness; returns `{status: "ready"\|"degraded", llm}` |

### First-run setup

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/setup/validate` | No | Validate LLM path A (local) or B (BYO key) |
| GET | `/setup/config` | No | Load persisted wizard config (404 if not yet written) |
| POST | `/setup/config` | No | Save wizard config; echoes body back |

`POST /setup/validate` body:
```json
{
  "path": "a",
  "config": {
    "llm_path": "local",
    "local_model": "qwen2.5:7b"
  }
}
```
Response: `{success: true, data: {status: "ok" | "ollama_not_running" | "model_not_present" | "api_unreachable" | "api_auth_failed", message: ""}}`.

### Dialogue (core loop)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/dialogue` | Yes | Send player message; receive NPC reply |
| WS | `/v1/dialogue/ws/{npc_id}` | Yes | Streaming dialogue (first-token latency) |
| GET | `/v1/dialogue/pending` | Yes | Poll NPC-initiated intents (proactive dialogue) |

### Error envelope

All non-2xx responses and 4xx/5xx errors use a consistent envelope:
```json
{
  "success": false,
  "error": { "code": "http_401", "message": "Unauthorized" }
}
```

Success responses:
```json
{
  "success": true,
  "data": { ... }
}
```

---

## 5. LLM path configuration

The wizard config is stored at `~/.npc_engine/wizard_config.json`:

```json
{
  "llm_path": "local",          // "local" or "api"
  "local_model": "qwen2.5:7b", // path A: Ollama model tag
  "api_key": null,              // path B: player-supplied key
  "api_url": "https://api.openai.com/v1",
  "api_model": "gpt-4o-mini"
}
```

Unity reads this file after `POST /setup/config` to confirm persistence, or uses
`GET /setup/config` which returns the same structure via the API.

---

## 6. Idempotency

State-mutating routes (POST, PATCH, DELETE) that risk duplicate execution on retry
require an `Idempotency-Key: <UUIDv4>` header. The engine stores the first response;
subsequent requests with the same key return it immediately without re-executing.

Omit the header on reads (GET). Supply a fresh UUID per user-initiated action.
