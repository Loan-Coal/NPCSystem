# Deferred — Game-client integration (Unity / Unreal)

**Moved out of `ROADMAP.md` on 2026-07-31**, during the eval-program planning session.

**Why:** the active program is the eval pipeline (`ROADMAP.md` → *Active — Eval pipeline
(EVAL-P0..P7)*). Everything below is **game-client integration work** — it is neither the
engine nor its evals, and none of it is being worked on. Completed shippable-runtime work
(`P0` / `SHIP-01..05a`, `INTEG-01..05`, Phases `F`/`G`/`H`) **stays in `ROADMAP.md`** because
it is engine-side and shipped.

**Step IDs are preserved.** Nothing here is renumbered. When this work resumes, move the
relevant block back verbatim.

**Not moved here (deliberately):**
- `OD-Ship-graph` — the Neo4j GPLv3 / Kùzu question is an *engine licensing + performance*
  decision (DEC-124/DEC-132) and is gated on `PERF-04`. It stays in `ROADMAP.md`.
- `Phase P0` / `SHIP-01..05a` — shipped engine-side runtime work.
- `Phase INTEG` — shipped; lands on `main`, engine surface.

---

## Phase P1 — The game slice (gated on SHIP-01)

> Moved verbatim from `ROADMAP.md` § *Next — Shippable demo game (B2B proof-slice)*.

- **Goal:** a ~10-minute authored experience whose core loop makes one emergent behaviour *visible and
  re-tellable in a 30-second clip*. Reuse the existing seed world (5–8 NPCs / existing locations/factions).
- **Constraints:** keep scope brutally small — one town, one hook, one win/lose; the simulation must be the star.
- [ ] **SHIP-05b (wizard Unity screen)** — Unity setup screen (C#) that presents the A/B choice,
  collects the API key for path B, calls the validators (drives `wizard_config.py` / `path_validator.py`
  from SHIP-05a), and writes `wizard_config.json`. Exit: both paths reachable from one Unity scene;
  choice survives restart. (DEC-129)
- [ ] **SHIP-06 (the legible hook)** — implement ONE emergent payoff the player can trigger and watch:
  e.g. *tell NPC A a secret → advance a gossip tick → NPC C across town repeats it, distorted*; or *betray
  someone, leave, return → they remember*. Exit: the hook is demonstrable end-to-end in the chosen client.
- [ ] **SHIP-07 (client + live legibility panel)** — talk-to-NPC UI plus a live relationship/knowledge-graph
  side panel (port the pygame graph-viz concept) so the invisible state is on screen. Exit: graph mutates
  visibly as the player acts.
- [ ] **SHIP-08 (10-minute arc)** — an authored short scenario over the seed world with a clear win/lose and
  the hook on the critical path. Exit: a first-time player reaches an ending in ~10 min.
- [ ] **SHIP-09 (distribution)** — a public build (itch.io and/or a Steam Next Fest demo) of the chosen path(s).
  Exit: a stranger can download and play without a setup call.

## Phase P2 — B2B proof wrap

- **Goal:** convert player reactions into the evidence a studio's product/eng leads ask for.
- [ ] **SHIP-10 (instrumentation + perf)** — capture engagement/retention signals and per-dialogue
  **latency + cost** (both LLM paths). Exit: a one-pager of real numbers for the pitch.
- [ ] **SHIP-11 (marketing clip)** — a ≤30-second screen capture of the SHIP-06 hook propagating across town.
  Exit: a shareable clip that makes the differentiator legible without narration.

> **Note (2026-07-31):** SHIP-10's *latency* half was already absorbed into `Phase EVAL — EVAL-01`
> (per-stage latency timer), which remains in `ROADMAP.md`. Only the engagement/retention half is
> genuinely deferred here.

---

## Phase X — Engine SDKs (Unity / Unreal)

> Moved verbatim from `ROADMAP.md` § *Parked backlog (carried forward, not active)*.

- [ ] **Phase X — Engine SDKs (Unity / Unreal)** — DEFERRED COMMERCIAL MILESTONE. Drop-in plugins
  wrapping the REST/WS API; highest commercial ROI but its own 8+ session milestone, sequenced after
  the OpenAPI contract is frozen. See OPEN_QUESTIONS OQ-13 (start vs finish engine depth).
  - [ ] **SX.1** OpenAPI contract freeze + versioned client spec.
  - [ ] **SX.2** Unity C# package (REST + WS, auth, models).
  - [ ] **SX.3** Unreal plugin (parity).
  - [ ] **SX.4** Sample integration scene per engine + docs.

---

## From the 2026-06-22 Sign-off Review — open items

> Moved verbatim from `ROADMAP.md` § *Sign-off Review (2026-06-22)* → *❌ Not Done — open items*.

### Unity game slice (blocked on Unity development — not engine issues)

| ID | Item |
|----|------|
| SHIP-05b | Unity setup wizard screen (drives `wizard_config.py` / `path_validator.py` from SHIP-05a) |
| SHIP-06 | The legible hook — one emergent payoff demonstrable end-to-end in Unity |
| SHIP-07 | Talk-to-NPC UI + live relationship/knowledge-graph side panel in Unity |
| SHIP-08 | Authored 10-minute arc with clear win/lose |
| SHIP-09 | Public distribution build (itch.io / Steam Next Fest) |

### B2B proof wrap (post-game)

| ID | Item |
|----|------|
| SHIP-10 | Instrumentation + perf numbers (engagement signals, per-dialogue latency + cost) |
| SHIP-11 | ≤30-second marketing clip of the hook propagating across town |

### Parked backlog row

| ID | Item |
|----|------|
| Phase X | Engine SDKs — SX.1 OpenAPI freeze, SX.2 Unity C# package, SX.3 Unreal plugin, SX.4 sample scenes |

---

## Standing context (kept so this file is readable cold)

From `ROADMAP.md` § *Next — Shippable demo game (B2B proof-slice)*, the framing these phases sit under:

> **End goal: license the engine to studios (B2B).** The thing that closes that sale is not a bigger engine
> — it's proof that the (invisible) simulation *carries a real experience players react to*, plus a recognizable
> integration path. So the near-term deliverable is a **small, downloadable, distributable demo game**: a
> ~10-minute experience built on one **legible emergent hook**, with the engine's runtime made shippable to a
> player's machine. **Do NOT grow this into a full game** — it is a proof artifact, instrumented for the pitch.

Relevant decisions already taken: **DEC-124** (dual LLM path; stay on Neo4j for now),
**DEC-125** (Unity selected as the game-client platform — SHIP-01), **DEC-126** (`OpenAICompatibleAdapter`),
**DEC-127** (local first-run flow), **DEC-128** (stack launcher + PyInstaller packaging),
**DEC-129** (wizard config + path validators), **DEC-131** (setup-route bootstrap auth exemption).

`SHIP-05a` (`setup/wizard_config.py`, `setup/path_validator.py`) and `INTEG-01..05`
(`POST /setup/validate`, `GET/POST /setup/config`, `/readiness`, `docs/INTEGRATION.md`)
are **shipped** and remain in `ROADMAP.md` — `SHIP-05b` is the only thing standing between
them and a working Unity first-run.
