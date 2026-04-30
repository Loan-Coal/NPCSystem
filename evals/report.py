"""
report.py - Markdown report generation for eval runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def write_report(results: list[dict], output_dir: Path) -> Path:
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

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    lines: list[str] = [
        f"# Eval Report — {timestamp}",
        "",
        f"**{passed}/{total} cases passed** ({failed} failed)",
        "",
        "---",
        "",
    ]

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
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
