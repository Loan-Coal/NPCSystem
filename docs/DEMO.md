# NPC Engine — 90-Second Video Demo

This document explains how to reproduce the video demo scenario.

## What the demo shows

The scenario runs a complete world loop:

1. **World creation** — A tavern location, two factions, and two NPCs are created from scratch.
2. **Knowledge injection** — A plague-sighting event is seeded. Only Mira (the innkeeper) is a direct witness.
3. **Gossip propagation** — A gossip tick fires. Gareth (the wanderer) may overhear the news, with possible distortion.
4. **Dialogue** — The player asks each NPC what they know. Mira gives the original account. Gareth's version may have changed in the retelling.
5. **Cleanup** — All demo-created nodes are removed.

This demonstrates the core NPC Engine loop: events propagate through the social graph, memory distorts through gossip, and every NPC carries their own version of truth.

## Prerequisites

1. The NPC Engine stack must be running:
   ```bash
   docker compose up
   ```
2. Python environment must be installed:
   ```bash
   pip install -e .[dev]
   ```
3. An LLM backend must be reachable (Ollama by default). The dialogue steps depend on it; gossip and setup do not.

No seed data is required — the scenario is entirely self-contained.

## Running the demo

```bash
make demo-video
```

This runs `pytest e2e/scenarios/scenario_demo_video.py -v -s -m demo_video --scenarios-only`.

The full transcript is saved to `transcripts/scenario_demo_video_demo_video_<timestamp>.md`.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NPC_BASE_URL` | `http://localhost:8000` | API base URL |
| `NPC_API_KEY` | `local_dev_secret_change_this_2026` | Bearer token |

Override for non-local stacks:

```bash
NPC_BASE_URL=http://staging.example.com NPC_API_KEY=<key> make demo-video
```

## Scenario structure

| Phase | What happens |
|-------|-------------|
| Setup | Tavern location, Innkeepers Guild, Guild of Wanderers, Mira, Gareth, and the player character are created. Both NPCs are placed at the tavern. |
| Act 1 | A merchant's plague report is seeded as an event. Mira receives direct `KNOWS_ABOUT` knowledge. A gossip tick fires. |
| Act 2 | Player speaks to Mira via `POST /v1/dialogue`. She has first-hand knowledge. |
| Act 3 | Player speaks to Gareth via `POST /v1/dialogue`. His account depends on whether gossip reached him and how much it was distorted. |
| Cleanup | Characters, event, and location are deleted via admin endpoints. |

## Expected output

The scenario prints a human-readable voiceover transcript to stdout, with NPC dialogue responses prominently displayed. Example (responses are LLM-generated and vary):

```
  [Mira]
    "A merchant came in near nightfall, half out of his mind with fear.
    Said the fields east of Millford are quiet — wrong kind of quiet.
    Dead stock in the ditches. Travelers turning back. I don't know what
    it is, but I've heard that silence before and it doesn't end well."

  [Gareth]
    "Heard something from the innkeep — something about livestock going
    wrong up past the border. Could be nothing. Could be the sweating
    sickness again, the way they talked about it."
```

The distortion in Gareth's version is driven by his `credulity=80` and `honesty=45` traits, the faction standing between Innkeepers Guild and Guild of Wanderers, and the gossip engine's distortion logic.

## Transcript file

After every run, a full JSON transcript is written to `transcripts/`. The file records every API call with request/response bodies, suitable for post-run inspection or sharing.

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| `404` on dialogue endpoint | LLM backend (Ollama) is not running |
| `500` on node creation | Neo4j is not running or unhealthy |
| `422` on character creation | Schema mismatch — run `make install` to pick up latest type registry |
| Gareth gives original account unchanged | Gossip tick didn't propagate this run (probabilistic) — re-run or increase `max_pairs` |
