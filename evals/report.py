"""
Module: report
Layer: evals harness (standalone — not part of the npc_engine layer model)
Purpose: Write markdown reports for completed eval runs, embedding the anti-hallucination
         guarantee section (guard + capability rates paired) and per-case pass/fail details.
Dependencies: summary.py, battery_trust.py (load_current_scorer_kappas — the scorer
              trust policy gate), retrieval_summary.py, stdlib (datetime, pathlib).
Used by: runner.py (writes report at end of run), __main__.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from battery_trust import load_current_scorer_kappas
from retrieval_summary import RetrievalSummary, format_retrieval_summary_markdown
from summary import format_summary_markdown, summarize


def write_report(
    results: list[dict],
    output_dir: Path,
    retrieval_summary: RetrievalSummary | None = None,
) -> Path:
    """
    Write a markdown report for a completed eval run.

    Each entry in results must have:
      case_id, description, passed (bool), expectations (list of expectation result dicts),
      response (dict or None), error (str or None).

    Returns the path of the written report file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = output_dir / f"{timestamp}.md"

    skipped = sum(1 for r in results if r.get("skipped"))
    non_skipped = [r for r in results if not r.get("skipped")]
    total = len(non_skipped)
    passed = sum(1 for r in non_skipped if r["passed"])
    failed = total - passed

    lines: list[str] = [
        f"# Eval Report — {timestamp}",
        "",
        f"**{passed}/{total} cases passed, {skipped} skipped** ({failed} failed)",
        "",
        "---",
        "",
    ]
    lines.extend(format_summary_markdown(
        summarize(results), scorer_kappas=load_current_scorer_kappas(),
    ))
    if retrieval_summary is not None:
        lines.extend(format_retrieval_summary_markdown(retrieval_summary))

    for result in results:
        if result.get("skipped"):
            status = "SKIP"
        elif result["passed"]:
            status = "PASS"
        else:
            status = "FAIL"
        lines.append(f"## [{status}] {result['case_id']}")
        lines.append("")
        lines.append(f"_{result.get('description', '')}_")
        lines.append("")

        if result.get("error"):
            lines.append(f"> **ERROR:** {result['error']}")
            lines.append("")

        if result.get("response"):
            resp = result["response"]
            npc_text = resp.get("npc_response", "")
            degradation = resp.get("degradation_level", "full")
            lines.append(f"**NPC response** (degradation={degradation}):")
            lines.append(f"> {npc_text}")
            lines.append("")

        for exp_result in result.get("expectations", []):
            mark = "✓" if exp_result["passed"] else "✗"
            skip = " _(skipped)_" if exp_result.get("skipped") else ""
            lines.append(f"- {mark} `{exp_result['kind']}`{skip}: {exp_result['detail']}")

        lines.append("")
        lines.append("---")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
