# k3_61b01dad_negadv — recovered run status note

`make eval-judge ARGS=--panel` completed its LLM judging normally and wrote
`judged.jsonl` and `judged_panel_votes.jsonl` correctly, but crashed inside
`write_report` before it could write `run_status.json` — see **ISSUE-288**
(`project-harness/ISSUES.md`): `_assert_paired_rates` refuses to render a
markdown report for a generation with guard cases and zero capability cases,
which this one has by design (`docs/EVAL_NEXT_GENERATION_CASE_SET.md`).

No markdown report exists for this run. `run_status.json` (panel kappa,
per-criterion kappa, repeat-flip decomposition) was reconstructed from
`judged_panel_votes.jsonl` + `outputs.jsonl` without re-running the panel —
see `evals/trend/trend_v1.jsonl`'s `k3_61b01dad_negadv` row and
`project-harness/DECISIONS.md` (DEC-265) for the numbers and how they were
recovered.
