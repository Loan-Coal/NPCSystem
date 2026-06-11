# Improvements Backlog

This file captures recommendations and optional improvements discovered during implementation.

## Candidate Improvements

1. Add strict lint + type checks in CI from M0 onward
Reasoning: catches architectural and typing drift early.

2. Add module-level complexity/size guard script
Reasoning: enforces file/function limits from CODING_PRINCIPLES.xml automatically.

3. Add docker-compose for Neo4j + app + test profile
Reasoning: reduces setup friction and improves reproducibility.

4. Add request-id middleware and structured correlation logging
Reasoning: easier tracing across dialogue, gossip, and event flows.

5. Add health subchecks for Neo4j and LLM adapter readiness
Reasoning: deployment diagnostics become actionable.

6. Add pydantic settings validation smoke test in CI
Reasoning: fail fast when env keys are missing or malformed.

7. Add deterministic replay command for gossip/event seeds
Reasoning: simplifies debugging and regression analysis.

8. Add architecture conformance tests for extension points
Reasoning: ensures open/closed goals remain intact when code evolves.
