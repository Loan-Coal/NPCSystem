# NPC Engine — Interactive Demo Game

Live demo of the NPC knowledge graph. Five characters across three locations.
Press **W** to inject a war event. Press **C** to advance the gossip clock.
Watch the graph panel update in real time.

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Docker + Docker Compose running | `docker compose ps` |
| Python venv with demo deps installed | `pip install -r demo_game/requirements.txt` |
| Ollama running with `qwen2.5:14b` pulled | `ollama list` |

One-time model pull:

```bash
ollama pull qwen2.5:14b
```

## Setup

```bash
docker-compose up -d
make demo-seed          # created=0 skipped=53 on re-run — safe every time
make demo               # opens the Pygame game window
```

> `CLOCK_MODE=game_driven` is set in `docker-compose.yml`. The gossip engine
> only ticks when **C** is pressed — it does not advance automatically.

## Scripted 90-Second Demo Flow

### Beat 1 — Point to the graph panel (0:00–0:20)

> "This is the NPC knowledge graph, live from the engine.
> Blue nodes are characters. Red are factions. Orange are events.
> Dashed arrows are `KNOWS_ABOUT` edges — knowledge that can spread via gossip."

Wait ~5 seconds for the first graph render. Note that `captain_sorn` has no
`northern_war_begins` event in his neighbourhood yet.

### Beat 2 — Press W (0:20–0:35)

> "I'm injecting a war event — `epoch=war`, condition `northern_war_active`."

Yellow **"War declared!"** overlay appears bottom-left for 2 seconds.
The `world_state` node updates on the next graph poll (~5 s).

### Beat 3 — Press C × 2 (0:35–0:55)

Press **C**. Pause ~2 s. Press **C** again.

> "Each keypress fires one gossip tick. The clock is game-driven — I control
> when time advances. Watch the edges."

Yellow **"Clock advanced"** overlay after each press. After the next poll,
new `KNOWS_ABOUT` edges or belief satellite nodes may appear.

### Beat 4 — Talk to captain_sorn (0:55–1:15)

Navigate to `guard_barracks`. Select `captain_sorn`. Type:

> "What is happening in the north?"

Expected: captain_sorn references the war or the northern conflict.
He has a direct `KNOWS_ABOUT northern_war_begins` edge seeded from the start.

### Beat 5 — Talk to old_henryk (1:15–1:30)

Navigate to `market_square`. Select `old_henryk`. Type:

> "Have you heard any news lately?"

Expected: old_henryk may reference the war — he is two hops from the event
and reachable only after gossip has propagated. His response demonstrates
knowledge spreading through the social graph.

## Graph Panel Legend

| Element | Colour / style |
|---------|----------------|
| Character | Blue |
| Faction | Red |
| Event | Orange |
| Location | Green |
| Belief (inner life) | Gold satellite node |
| Goal (inner life) | Amber satellite node |
| `KNOWS_ABOUT` edge | Dashed arrow |
| Newly propagated edge | Yellow highlight (2 poll cycles, then fades) |

## Key Bindings

| Key | Action |
|-----|--------|
| **W** | Inject war epoch (`epoch=war`, `active_conditions=["northern_war"]`) |
| **C** | Advance clock 1 tick (`advance_clock(delta_ticks=1)`) |
| Arrow keys / click | Navigate between locations |
| Enter | Submit player dialogue |

## Environment Variables (`.env.demo`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `NPC_BASE_URL` | `http://localhost:8000` | Engine API base URL |
| `NPC_API_KEY` | `local_dev_secret_change_this_2026` | Bearer token |
| `DEMO_GRAPH_POLL_INTERVAL` | `5` | Graph refresh interval in seconds |

## LLM Judge (CI gate)

```bash
make eval-llm-demo
```

Requires Ollama with `qwen2.5:14b` running. Runs 2 judge tests:

- `test_war_epoch_captain_sorn_acknowledges_war` — does captain_sorn reference war/conflict?
- `test_gossip_propagates_after_clock_advance` — is `northern_war_begins` present in the graph?

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Graph shows "Waiting for data…" | Engine not running or bad API key | `docker-compose up -d`; check `.env.demo` |
| W/C keys show no overlay | Pygame window not focused | Click the game window first |
| `make demo-seed` → `created=53 skipped=0` | Fresh DB (first run) | Normal |
| `make demo-seed` → `created=0 skipped=53` | World already seeded | Normal on re-run |
| `make eval-llm-demo` skips all tests | Ollama not running | `ollama serve` then retry |
| captain_sorn gives a generic response | Model not pulled | `ollama pull qwen2.5:14b` |
| Pygame window fails to open | pygame-ce not installed | `pip install -r demo_game/requirements.txt` |

---

## Legacy: Automated Scenario (`make demo-video`)

The original automated demo scenario is still available. It creates a self-contained
world (Mira, Gareth, a plague event), runs gossip propagation, queries both NPCs via
dialogue, and cleans up. It does not use the interactive game window.

```bash
make demo-video
```

Source: `e2e/scenarios/scenario_demo_video.py`.
Transcript written to `e2e/transcripts/` after each run.
