# Harness Quality Gates

This repo's quality rules are now **executable and enforced**, not just prose in
`CLAUDE.md`. The design goal: the lint / type / rule / coverage debt that the
2026-06-03 review surfaced (38 lint, 254 type errors, 11 oversized files, silent CI)
**can never silently grow again**. Existing debt is grandfathered and may only shrink.

## The one command

```bash
make check        # lint + check-rules + type-ratchet + check-harness + test-cov(80% floor)
```

Same command runs locally and in CI. If `make check` is green, the tree is healthy by
the project's own rules.

## The gates

| Gate | Make target | What it enforces | Mechanism |
|------|-------------|------------------|-----------|
| Lint | `make lint` | ruff clean on `src/` | hard fail |
| Rules | `make check-rules` | CLAUDE.md strict rules (file-size, `print()`, `except: pass`, `raise Exception`, Cypher-outside-`graph/`, demo→`npc_engine` imports) | **baseline ratchet** |
| Types | `make type-ratchet` | mypy error count may not rise | **baseline ratchet** |
| Coverage | `make test-cov` | full unit suite, ≥80% | hard fail (`--cov-fail-under=80`) |
| Honesty | `make check-harness` | docs don't claim a clean state the gates contradict | advisory (warn); `--strict` to enforce |
| Contracts | `make check-contracts` / `check-contract-sync` | engine contract YAML ↔ tests | hard fail |

### Baseline ratchet (the key idea)

You can't flip mypy to gating with 254 errors — so it gets dropped and the debt grows
invisibly. Instead we commit a **baseline that can only decrease**:

- `scripts/rules_baseline.txt` — grandfathered CLAUDE.md rule violations (57 today).
- `.mypy_baseline` — grandfathered mypy error count (256 today).

A gate **fails only on a NEW violation**. When you fix some, the gate tells you, and you
lock the win in:

```bash
make check-rules-update      # rewrite scripts/rules_baseline.txt to the (smaller) current set
make type-ratchet-update     # rewrite .mypy_baseline to the (smaller) current count
```

Never hand-edit a baseline file to dodge a gate. To intentionally accept a new oversized
file, add a `DECISIONS.md` waiver, then re-baseline.

## Local fast feedback (pre-commit)

```bash
pip install pre-commit
pre-commit install                       # ruff + check-rules + check-harness on commit
pre-commit install --hook-type pre-push  # mypy ratchet on push
```

This catches failures before CI (the 30 E402 lint errors from the review would never have
survived a `ruff --fix` pre-commit run).

## CI (`.github/workflows/ci.yml`)

- Python pinned to **3.14** (matches the stack; was wrongly 3.11).
- `static-analysis` now runs **lint + check-rules + type-ratchet + check-harness** (was lint only).
- `coverage-gate` now runs the **full suite with the 80% floor** (`make test-cov`) and a
  full report including `evals/` (previously the floor was never applied in CI).
- The contract-sync guard runs on **push**, not only PRs.

### Remaining manual step (needs repo admin)

**Mark these CI jobs *required* for merge in GitHub branch-protection.** Without that, a
red CI is just decoration — which is how 38 lint + 254 type errors reached `main`'s
history. This is the single most important follow-up and can only be done in repo settings.

## How this maps to the review findings

- **SEV-15** (CI red / `make check` unrunnable) → ratchets make `check` runnable today;
  lint is the only hard-fail and is a ~30-min fix (`FIX-SEV-15`).
- **SEV-23 / SEV-04 / SEV-18 / SEV-40 / SEV-02** (file-size, Cypher-leak, swallows, prints,
  demo imports) → `check-rules` blocks any *new* instance and tracks the burn-down.
- **SEV-14** (type debt) → `type-ratchet` forces the 256 count monotonically toward 0.
- **SEV-25** (harness docs lie) → `check-harness` flags "no open issues" while debt exists.
- **SEV-43** (no-op contract guard) → sync guard now also runs on push (the guard logic
  itself is hardened separately under `FIX`/SEV-43).
- **SEV-01** (eval guarantee) → `evals/` is now in the coverage report; the matcher unit
  tests + a guard-fixture eval gate are the `FIX-SEV-01` deliverable (code fix, not pure harness).

## Adding a new rule

Add a check to `scripts/check_rules.py` (`_collect()` returns `RULE|relpath` signatures),
run `make check-rules-update` to baseline existing instances, and document the rule in the
table above. New code is then blocked from introducing it.
