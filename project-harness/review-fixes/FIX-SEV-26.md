# FIX-SEV-26 — Repo hygiene: remove committed logs; close .gitignore gaps

**Severity:** MEDIUM · **Confidence:** Confirmed · **Effort:** S
**Category:** hygiene · **Absorbs:** HARN-06, HARN-07

## Problem
`git ls-files` tracks `server.log`, `server2.log` (288 KB each) and `reports/*.md`; `.gitignore` lacks `*.log`, `/reports/`, `.cache/`. Runtime artifacts bloat history and leak server output.

## Current shape
- `server.log`, `server2.log` in repo root, tracked by git
- `reports/` directory tracked by git
- `.gitignore` has no `*.log`, `/reports/`, or `.cache/` entries

## Steps
1. `git rm --cached server.log server2.log` (untrack, keep local copies)
2. `git rm --cached reports/*.md` (untrack; verify with `git ls-files reports/` first)
3. Append to `.gitignore`:
   ```
   *.log
   /reports/
   .cache/
   ```
4. Run `git status` to confirm the files appear as untracked, not modified.

## Verification
- `git ls-files server.log server2.log` → no output
- `git ls-files reports/` → no output
- `.gitignore` contains `*.log` entry
- `make check` passes (no code changes)

## Blast radius
Repo tracking only; no source code changes.
