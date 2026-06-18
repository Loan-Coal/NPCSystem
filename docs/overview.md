# NPC Engine — Documentation Overview

NPC Engine is a game backend that gives non-player characters persistent memory,
relationships, and emotional state — enabling natural-feeling conversations and an
off-screen living world via Neo4j + local LLM.

Designed as a plugin for Unity and Unreal Engine games. Exposes a clean HTTP +
WebSocket API so any game engine can integrate without depending on internal
implementation details.

---

## For game developers

| Document | What it covers |
|---|---|
| [BUSINESS_REQUIREMENTS.md](BUSINESS_REQUIREMENTS.md) | Product vision, target clients, and non-functional requirements |
| [ENGINES.md](ENGINES.md) | Engine capability catalog — every domain engine, its business capability, tick cadence, and linked API routes |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System overview, data flow diagrams, middleware stack, extension points |
| [API.md](API.md) | Complete HTTP + WebSocket API reference (public `/v1`, graph, and admin) with authentication and curl examples |
| [DATA_MODELS.md](DATA_MODELS.md) | Neo4j graph schema: nodes, edges, constraints, indexes, and game schema extensibility |
| [RELEVANCE_WEIGHTS.md](RELEVANCE_WEIGHTS.md) | Context scoring formula that controls what each NPC "thinks about" during dialogue |
| [PROMPT_DESIGN.md](PROMPT_DESIGN.md) | Two-stage LLM dialogue pipeline: planner, realizer, context skeleton, and token budget |

**Quick start:** see [README.md](../README.md) for setup instructions, Docker commands,
and `make` targets.

---

## For contributors and maintainers

The developer playbook lives in [project-harness/](../project-harness/). These files are
read at the start of every session and are not intended for external audiences.

| File | Purpose |
|---|---|
| [CLAUDE.md](../project-harness/CLAUDE.md) | Working rules: layer model, coding standards, docstring format, testing discipline |
| [ROADMAP.md](../project-harness/ROADMAP.md) | Feature phases, dependency order, and definition of done per feature |
| [ISSUES.md](../project-harness/ISSUES.md) | Persistent issue log — read at the start of every session, updated throughout |
| [DECISIONS.md](../project-harness/DECISIONS.md) | Architecture decision log — append-only; records context, options, and consequences |
| [PATTERNS.md](../project-harness/PATTERNS.md) | Reusable code patterns and anti-patterns discovered during development |
| [SKILLS_QUEUE.md](../project-harness/SKILLS_QUEUE.md) | Open questions and skill/knowledge gaps to resolve |
| [proposals/](../project-harness/proposals/) | Active design proposals awaiting decision |

See [CONTRIBUTING.md](../CONTRIBUTING.md) for setup, test commands, and the pre-merge checklist.
