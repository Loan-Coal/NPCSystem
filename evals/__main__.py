"""
Module: __main__
Layer: evals (evaluation harness — standalone, outside the npc_engine layer model)
Purpose: Single verb-dispatch entry point for the eval harness (`python -m evals <verb>`),
         so every runner is reachable through one CLI instead of seven make targets.
Dependencies: stdlib only (argparse, importlib, sys, pathlib). Verb targets are imported
              lazily, never at module import.
Used by: Makefile eval targets (EVAL-P6.3), tests/unit/evals/test_cli_dispatch.py.

Two import styles coexist in evals/. `retrieval_runner` uses package-absolute imports
(`from evals import ...`); every other runner uses flat imports (`import matchers`) that
only resolve with evals/ itself on sys.path — which is what `python evals/runner.py`
provides implicitly and `python -m evals` does not. This module therefore prepends its
own directory to sys.path before dispatching, so both styles resolve. Unifying the two
is deliberately out of scope here (no behaviour change at a phase whose constraint is a
green gate at every commit); tracked as ISSUE-132.

Verb targets are imported lazily because `matchers` resolves the judge model, URL and
timeout at module import (matchers.py:117-119). Importing eagerly would make
`python -m evals --help` fail on a machine with no judge configured.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

_EVALS_DIR = str(Path(__file__).resolve().parent)
if _EVALS_DIR not in sys.path:
    sys.path.insert(0, _EVALS_DIR)

_HELP_FLAGS = frozenset({"--help", "-h", "help"})
_EXIT_USAGE = 2
_EXIT_OK = 0


@dataclass(frozen=True)
class VerbTarget:
    """Where a verb dispatches to, and what it does.

    Attributes:
        module: Importable module name exposing the entry point.
        attr: Name of the callable on that module (always ``main``).
        summary: One-line description shown in ``--help``.
    """

    module: str
    attr: str
    summary: str


VERBS: dict[str, VerbTarget] = {
    "generate": VerbTarget(
        "generate_runner", "main", "Run the generation pass; write a v2 transcript."
    ),
    "judge": VerbTarget(
        "judge_runner", "main", "Score a cached transcript with the LLM judge."
    ),
    "score": VerbTarget(
        "deterministic_pass", "main", "Deterministic graph scorers over a transcript (no LLM)."
    ),
    "report": VerbTarget(
        "runner", "main", "Run the YAML case suite live and write a markdown report."
    ),
    "retrieval": VerbTarget(
        "retrieval_runner", "main", "Retrieval precision@k / recall@k / MRR over the demo world."
    ),
    "calibrate": VerbTarget(
        "calibration", "main", "Per-scorer confusion matrices and Cohen's kappa with CI."
    ),
    "anti-hallucination": VerbTarget(
        "anti_hallucination_runner", "main", "Run the JSON-fixture anti-hallucination eval."
    ),
    "adjudicate": VerbTarget(
        "adjudicate", "main", "Resumable interactive adjudication of calibration labels."
    ),
    "label-export": VerbTarget(
        "label_export", "main", "Export transcript records as JSON batches for CLI labelling."
    ),
    "label-import": VerbTarget(
        "label_import", "main", "Import a CLI labelling session into validated CalibrationLabel rows."
    ),
    "compare": VerbTarget(
        "compare", "main", "McNemar paired comparison of two generation directories."
    ),
    "draft-cases": VerbTarget(
        "case_drafts", "main", "Generate draft capability cases from the live graph into evals/cases/_drafts/."
    ),
}


def _usage_lines() -> list[str]:
    """Build the help text listing every verb and its summary."""
    width = max(len(verb) for verb in VERBS)
    lines = ["usage: python -m evals <verb> [options]", "", "verbs:"]
    lines.extend(f"  {verb.ljust(width)}  {target.summary}" for verb, target in VERBS.items())
    lines.extend(
        [
            "",
            "Run `python -m evals <verb> --help` for a verb's own options.",
        ]
    )
    return lines


def _fail_with_usage(message: str) -> int:
    """Print an error plus the verb list to stderr and return the usage exit code."""
    print(message, file=sys.stderr)
    print("", file=sys.stderr)
    for line in _usage_lines():
        print(line, file=sys.stderr)
    return _EXIT_USAGE


def main(argv: list[str] | None = None) -> int:
    """Dispatch a verb to its runner's ``main``, forwarding the remaining arguments.

    Args:
        argv: Argument list; defaults to sys.argv[1:]. The first element is the verb.
    Returns:
        The verb's exit code, 0 for ``--help``, or 2 for a missing/unknown verb.
        A verb whose main() returns None (deterministic_pass) is normalised to 0.
    """
    args = sys.argv[1:] if argv is None else list(argv)

    if not args:
        return _fail_with_usage("error: no verb given.")

    verb, rest = args[0], args[1:]

    if verb in _HELP_FLAGS:
        for line in _usage_lines():
            print(line)
        return _EXIT_OK

    target = VERBS.get(verb)
    if target is None:
        return _fail_with_usage(f"error: unknown verb {verb!r}.")

    module = importlib.import_module(target.module)
    exit_code = getattr(module, target.attr)(rest)
    return _EXIT_OK if exit_code is None else int(exit_code)


if __name__ == "__main__":
    sys.exit(main())
