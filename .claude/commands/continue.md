Build a full session-start context for the NPC Engine project and present a structured briefing, then ask the user to confirm before starting work.

## Steps

1. **Read the handoff** — `project-harness/NEXT_SESSION.md`
   Extract: branch, last completed task, next task, roadmap ref, open issue IDs.

2. **Read the relevant roadmap section** — `project-harness/ROADMAP.md`
   Find the phase/subphase that matches the next task from NEXT_SESSION.md.
   Read *only that section* (not the whole file) to get the full task spec, exit criteria,
   and any dependencies or notes.

3. **Read open issues** — `project-harness/ISSUES.md`
   Read only the `## Open` section (stop at the first `## [FIXED]` heading).
   Cross-reference against the next task: flag any open issues that are relevant.

4. **Present the briefing** in this format:

---
## Session Start — NPC Engine

**Branch:** `<branch>`
**Last completed:** <task ID + one-line summary>
**Next task:** <task ID + title>

### Task spec
<paste the full task spec from ROADMAP.md — exit criteria, dependencies, approach>

### Relevant open issues
<list only issues that intersect with the next task; "None" if none>

### Pre-task checklist
<if NEXT_SESSION.md lists any pre-task steps, list them here; else omit>
---

5. **Ask:** "Ready to proceed with [task ID]?" before touching any code or files.

## After completing a task

When a task finishes, regenerate `project-harness/NEXT_SESSION.md` with:
- Updated "Last completed" line
- Updated "Next task" line (advance to the next unchecked item in the roadmap phase)
- Updated open issues list (remove any fixed in this session)
- Keep the file under 30 lines

Also mark the task `✅` in `project-harness/ROADMAP.md` and add a session log row.
