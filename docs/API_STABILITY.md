# API stability policy

The Unreal DemoGame is a real external consumer (DEC-229), so the `/v1` surface is now
something other software depends on. This document says what may change under a consumer
and what may not.

Scope: everything served under `settings.API_V1_PREFIX` (default `/v1`), **including the
WebSocket route `/v1/ws/dialogue`**. Out of scope: `/health`, `/readiness`, `/setup/*`,
`/docs`, `/redoc`, `/dashboard/*` — these are operator and first-launch surfaces, are
auth-exempt in `dev` only, and carry no stability promise.

Measured at R5.1: **149 operations** (148 HTTP + 1 WebSocket) across **153 schemas**.

---

## What may change without a version bump

These are additive. A consumer written against the old contract keeps working.

- A new route or a new operation on an existing route.
- A new **optional** request field, or a new optional query/path/header parameter.
- A new field on a response body.
- A new declared status code.
- A response field becoming always-present (optional → required).
- A **request** enum accepting a new value.
- Marking an operation `deprecated`.
- Any change to descriptions, summaries, titles, examples, `operationId` or tags. The
  gate does not record prose at all, so docstring edits never show up as contract churn.

## What may not

Each of these is detected and reds `make check-api-contract`:

| Change | Why it breaks a consumer |
|---|---|
| An operation is removed or renamed | The call 404s |
| The version prefix changes | Every URL moves |
| A declared status code is removed | Error handling stops matching |
| An operation becomes auth-required | Existing calls start returning 401 |
| A response field is removed | The client reads a missing key |
| A response field changes type | Deserialization fails |
| A **response** enum gains a member | The client cannot switch on a value it has never seen |
| A request field becomes required, or a new required one appears | Existing payloads are rejected |
| A request field changes type | Existing payloads are rejected |
| A **request** enum loses a member | A value the client sends stops being accepted |
| A parameter becomes required | Existing calls are rejected |

The request/response asymmetry is deliberate. A consumer *sends* requests and *reads*
responses, so tightening a request breaks it while tightening a response does not; and
widening a response breaks it while widening a request does not.

---

## Deprecation window

**This part is process, not a gate — nothing in `make check` enforces it.** It is written
down so the decision is not re-litigated per change:

1. Mark the operation or field `deprecated` and say what replaces it.
2. Leave it in place for at least one tagged release **and** 30 days.
3. Tell the integrator. With exactly one consumer today, that is a message, not a mailing
   list; when there is more than one, this line needs replacing with a real channel.
4. Only then remove it, and re-record the baseline in the same commit as the removal.

A breaking change that skips this is a bug, even when the gate has been re-recorded.

## How it is enforced

`make check-api-contract` (in `make check`) extracts the live contract and compares it to
`scripts/api_contract_baseline.json`. Additive change passes silently. A break prints the
offending element and exits 1.

To land a deliberate break, follow the window above, then:

```
python scripts/check_api_contract.py --update
```

Re-record in the **same commit** as the change, so the diff shows the break and its
justification together. Re-recording to make a red go away, without the window, is the
failure this gate exists to prevent.

## What this gate does not cover

Stated so the gate is not over-read:

- Behavioural change with an unchanged shape — same fields, different values or meaning.
- Latency, rate limits, and the text of error `detail` strings.
- Semantics of a field whose type is unchanged.
- Anything outside the scope list at the top.

A green gate means "no consumer's parsing breaks", not "nothing changed".

## Related

- `scripts/check_api_contract.py` — the gate; `scripts/api_contract_differ.py` is the
  pure detector and is tested against synthetic contract pairs, not just the baseline.
- `docs/INTEGRATION.md` — the integrator-facing overview.
- DEC-253 — why a committed baseline is safe here when R4.7 deleted `live_openapi.json`.
