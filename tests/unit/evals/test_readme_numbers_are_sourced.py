"""
Module: test_readme_numbers_are_sourced
Layer: test (unit)
Purpose: RED anchor + mechanism for EVAL-P24.3 — every metric quoted in
         README.md must carry a machine-checkable citation
         (<!-- metric gen_id="..." field="..." value="..." n="..." -->)
         that this test resolves against the real committed artifact and
         verifies. Editing a README number without updating the artifact
         it cites (or without updating the citation to match) fails the
         build — the mechanism that makes a stale published claim
         impossible rather than merely discouraged.

         The annotation format:
           <!-- metric gen_id="<gen_id>" field="<field>" value="<num>" n="<int>" -->
         placed immediately after the sentence/table-cell it supports.
         `field` is one of: "adversarial_rate", "anti_hallucination_rate", "capability_rate" (read via
         summary.summarize_from_dir), or "kappa:<scorer>" (read via
         calibration.run_calibration against the real labels file).

         Today README.md cites nothing (Program 3's numbers have not been
         published yet — EVAL-P24.3 itself is still blocked on the labelling
         pass), so this test passes vacuously: zero citations, zero checks,
         zero failures. It starts enforcing the moment the first citation
         is added. The RED-anchor test below proves the mechanism itself
         works, independent of README.md's current (empty) state.
Dependencies: pytest, re, pathlib; summary, calibration, calibration_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from calibration import run_calibration
from calibration_records import LABELS_FILE, read_calibration_labels
from summary import summarize_from_dir

_REPO_ROOT = Path(__file__).resolve().parents[3]
_README = _REPO_ROOT / "README.md"

_METRIC_RE = re.compile(
    r'<!--\s*metric\s+gen_id="(?P<gen_id>[^"]+)"\s+field="(?P<field>[^"]+)"\s+'
    r'value="(?P<value>[^"]+)"\s+n="(?P<n>\d+)"\s*-->'
)


def find_citations(readme_text: str) -> list[re.Match]:
    """Return every metric citation comment found in a README's text."""
    return list(_METRIC_RE.finditer(readme_text))


def resolve_field(gen_id: str, field: str) -> tuple[float, int]:
    """Resolve a cited (gen_id, field) pair to (actual_value, actual_n).

    Args:
        gen_id: A generation directory name under evals/generations/.
        field: "adversarial_rate", "anti_hallucination_rate", "capability_rate", or
            "kappa:<scorer>". "guard_rate" is deliberately NOT resolvable: DEC-243
            retired the combined guard rate, so a README that cites one must fail
            rather than silently resolve against a number nothing computes.
    Returns:
        (actual_value, actual_n) computed live from the committed artifact.
    Raises:
        ValueError: If field names an unsupported metric.
        FileNotFoundError: If gen_id's directory doesn't exist.
        StopIteration: If field names a scorer with no calibration report
            (fewer than 2 adjudicated rows).
    """
    gen_dir = _REPO_ROOT / "evals" / "generations" / gen_id
    if field in ("adversarial_rate", "anti_hallucination_rate", "capability_rate"):
        s = summarize_from_dir(gen_dir)
        value = getattr(s, field)
        n = getattr(s, field.replace("_rate", "_turns"))
        return value, n
    if field.startswith("kappa:"):
        scorer = field.split(":", 1)[1]
        labels = read_calibration_labels(LABELS_FILE)
        reports = run_calibration(labels, print_fn=lambda *_a, **_k: None)
        report = next(r for r in reports if r.scorer == scorer)
        return report.kappa, report.counts.n
    raise ValueError(f"unsupported metric field: {field!r}")


def check_readme_citations(readme_text: str) -> list[str]:
    """Verify every citation in readme_text against its artifact.

    Args:
        readme_text: Full README.md contents (or a fixture standing in for it).
    Returns:
        A list of mismatch descriptions; empty when every citation checks out.
    """
    problems: list[str] = []
    visible_text = _METRIC_RE.sub("", readme_text)  # the comment's own value="..." doesn't count
    for match in find_citations(readme_text):
        gen_id, field, value_str, n_str = (
            match["gen_id"], match["field"], match["value"], match["n"]
        )
        cited_n = int(n_str)
        try:
            actual_value, actual_n = resolve_field(gen_id, field)
        except Exception as exc:  # noqa: BLE001 — surfaced as a readable mismatch, not a crash
            problems.append(f"{field}@{gen_id}: could not resolve artifact ({exc})")
            continue
        if actual_n != cited_n:
            problems.append(f"{field}@{gen_id}: cited n={cited_n} but artifact has n={actual_n}")
        if float(value_str) != pytest.approx(actual_value, abs=1e-3):
            problems.append(
                f"{field}@{gen_id}: cited value={value_str} but artifact computes {actual_value:.3f}"
            )
        if value_str not in visible_text:
            problems.append(f"{field}@{gen_id}: value={value_str} not found in visible README text")
    return problems


# ---------------------------------------------------------------------------
# RED anchor — proves the mechanism itself works
# ---------------------------------------------------------------------------


def test_every_readme_metric_matches_its_cited_artifact_fixture() -> None:
    """A citation whose declared value does not match its cited artifact must
    be caught — this is the mechanism EVAL-P24.3 exists to build, proven
    against a synthetic fixture so it does not depend on README.md ever
    having a citation in it."""
    repo_root = Path(__file__).resolve().parents[3]
    gen_dir = repo_root / "evals" / "generations" / "k3_73e6c36"
    if not gen_dir.exists():
        pytest.skip("real committed artifact not present in this checkout")

    real_value, real_n = resolve_field("k3_73e6c36", "adversarial_rate")
    wrong_value = round(real_value + 0.5, 3) if real_value is not None else 0.99

    fixture = (
        f'The engine passes {wrong_value} of guard turns.\n'
        f'<!-- metric gen_id="k3_73e6c36" field="adversarial_rate" '
        f'value="{wrong_value}" n="{real_n}" -->\n'
    )
    problems = check_readme_citations(fixture)
    assert problems, "expected a mismatch to be caught, found none"
    assert any("adversarial_rate" in p for p in problems)


def test_a_correct_citation_passes() -> None:
    """The positive case: a citation whose value genuinely matches its
    artifact must not be flagged."""
    repo_root = Path(__file__).resolve().parents[3]
    gen_dir = repo_root / "evals" / "generations" / "k3_73e6c36"
    if not gen_dir.exists():
        pytest.skip("real committed artifact not present in this checkout")

    real_value, real_n = resolve_field("k3_73e6c36", "adversarial_rate")
    fixture = (
        f'The engine passes {real_value:.3f} of guard turns.\n'
        f'<!-- metric gen_id="k3_73e6c36" field="adversarial_rate" '
        f'value="{real_value:.3f}" n="{real_n}" -->\n'
    )
    assert check_readme_citations(fixture) == []


def test_cited_value_absent_from_visible_text_is_flagged() -> None:
    """A citation is worthless if the number it certifies doesn't actually
    appear in the prose a reader sees — that gap must be caught too."""
    repo_root = Path(__file__).resolve().parents[3]
    gen_dir = repo_root / "evals" / "generations" / "k3_73e6c36"
    if not gen_dir.exists():
        pytest.skip("real committed artifact not present in this checkout")

    real_value, real_n = resolve_field("k3_73e6c36", "adversarial_rate")
    fixture = (
        "The engine passes most guard turns.\n"  # no number in the visible prose
        f'<!-- metric gen_id="k3_73e6c36" field="adversarial_rate" '
        f'value="{real_value:.3f}" n="{real_n}" -->\n'
    )
    problems = check_readme_citations(fixture)
    assert any("not found in visible" in p for p in problems)


# ---------------------------------------------------------------------------
# The actual gate — runs against the real README.md
# ---------------------------------------------------------------------------


def test_every_readme_metric_matches_its_cited_artifact() -> None:
    """The live gate. Passes vacuously today (README.md cites nothing yet);
    starts enforcing the moment EVAL-P24.3 adds the first citation."""
    readme_text = _README.read_text(encoding="utf-8")
    problems = check_readme_citations(readme_text)
    assert problems == [], "\n".join(problems)
