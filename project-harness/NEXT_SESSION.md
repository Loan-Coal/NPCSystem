# Session Handoff

**Branch:** `munich-demo`
**Last completed:** S13.1 — Phases 11 & 12 + the codebase review committed as 4 atomic commits;
working tree clean; `.cache/`, `.claude/`, `review-evidence/` gitignored. Tests green (1326 unit + 525 demo).
**Next task:** **S13.2** — runtime config mutation (ISSUE-051). **Needs sign-off before coding:**
adds a `RuntimeConfigStore` read by the autopilot loop + a public `PATCH /v1/system/config`
(graph_admin scope, bounded values) + wires the dashboard Engines-tab inputs.
**Roadmap ref:** `project-harness/ROADMAP.md` → Phase 13 → S13.2.

---

## ⚠️ Strategic decision pending — review backlog vs. feature phases

The 2026-06-03 audit (now committed: `REVIEW_FINDINGS.md` + `review-fixes/`) returned **BLOCK**:
43 findings (2 CRITICAL, 16 HIGH). The clean-slate is now *version-controlled* but **not healthy**:

- **SEV-01 (CRITICAL):** anti-hallucination guarantee unmeasured (matchers pass on empty/fallback/
  synonym/refusal; live eval 27/31). The headline moat is asserted, not proven.
- **SEV-02 (CRITICAL):** `demo_game` imports `npc_engine` internals — not a standalone client.
- **SEV-15/SEV-25 (HIGH):** `make lint` (38 ruff) + `make type` (254 mypy) red, not in CI → `make check` cannot pass.
- **SEV-04/03/14/12/11 (HIGH):** layer erosion (Cypher in 16+ engines), prompt-injection surface,
  `dict[Any,Any]` API boundary, no multi-tenant isolation, game cannot be won/lost.

**Open question for the user:** the `review-fixes/` remediation backlog (Blocks A–F, dependency-ordered
critical path in `review-fixes/INDEX.md`) very likely outranks the new-feature Phases 14–16. Recommend
inserting a **Phase 13.5 / "Remediation"** block (start: SEV-15 → SEV-01 to prove the moat; SEV-02; the
S-sized no-dep wins SEV-09/13/16/17/07) **before** Phase 14. Confirm sequencing before building features.

## Open issues

- **ISSUE-051** (P3): dashboard engine controls read-only → S13.2 (needs sign-off).

**Next ID to use: ISSUE-052.**

*Regenerated 2026-06-03 after S13.1.*
