"""Unit tests for ``roadmap_cursor.py --audit-deferred`` (T0B.2).

``compute_next`` never returns a flagged task, which is correct — an unattended session must
not guess at a human decision — but it means a flagged task is passed over in silence while
the loop ticks everything around it. ``--audit-deferred`` is the report that makes that debt
visible. These tests pin three things:

* it lists exactly the flagged-and-unticked tasks and exits non-zero when any exist;
* each flag names the line that raised it, so an accidental flag leaking in from the next
  sprint's prose (ISSUE-134, ``BLOCK_END_RE`` not matching a level-1 heading) is visible on
  the first run instead of never;
* the four records of the deferred set in the real repo agree — the audit's output, the
  ROADMAP Deferred backlog table, the carry-forward note's count, and ``EXPECTED_FLAGS``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import roadmap_cursor  # noqa: E402

from tests.unit.harness.test_roadmap_cursor import EXPECTED_FLAGS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_ROADMAP = REPO_ROOT / "project-harness" / "ROADMAP.md"

AUDIT_ROW_RE = re.compile(r"^(\S+)\tphase=")

FLAGGED = (
    "# Roadmap\n"
    "- [ ] **OUTSIDE.1** ⏸️ outside the fence, never reported\n"
    "<!-- LOOP:QUEUE start -->\n"
    "### Phase A\n"
    "- [ ] **A.1** plain work\n"
    "- [ ] **A.2** ⏸️ needs a running stack\n"
    "- [x] **A.3** ⏸️ already done by a human\n"
    "- [ ] **A.4** gated work\n"
    "      ⚠️ ask-gate: edits the shared gate\n"
    "<!-- LOOP:QUEUE end -->\n"
)

CLEAN = (
    "<!-- LOOP:QUEUE start -->\n"
    "### Phase A\n"
    "- [ ] **A.1** plain work\n"
    "- [x] **A.2** ⏸️ done\n"
    "<!-- LOOP:QUEUE end -->\n"
)

# A level-1 sprint heading does not end a task block, so A.1 absorbs it (ISSUE-134).
LEAKY = (
    "<!-- LOOP:QUEUE start -->\n"
    "### Phase A\n"
    "- [ ] **A.1** plain work with no flag of its own\n"
    "Files: scripts/x.py\n"
    "# SPRINT 2 — the sprint whose prose says ask-gate\n"
    "### Phase B\n"
    "- [ ] **B.1** more plain work\n"
    "<!-- LOOP:QUEUE end -->\n"
)


def _audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> int:
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text(text, encoding="utf-8", newline="")
    monkeypatch.setenv("ROADMAP_FILE", str(roadmap))
    return roadmap_cursor.main(["--audit-deferred"])


def _ids(output: str) -> list[str]:
    return [m.group(1) for line in output.splitlines() if (m := AUDIT_ROW_RE.match(line))]


def test_audit_lists_exactly_flagged_unticked_tasks_and_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _audit(tmp_path, monkeypatch, FLAGGED)
    out = capsys.readouterr().out
    assert _ids(out) == ["A.2", "A.4"]
    assert code != 0


def test_audit_row_names_phase_flags_and_title(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _audit(tmp_path, monkeypatch, FLAGGED)
    out = capsys.readouterr().out
    assert "A.4\tphase=A\tflags=ask-gate\tgated work" in out


def test_audit_exits_zero_when_nothing_is_deferred(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _audit(tmp_path, monkeypatch, CLEAN)
    assert code == 0
    assert _ids(capsys.readouterr().out) == []


def test_audit_shows_the_line_that_raised_each_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _audit(tmp_path, monkeypatch, LEAKY)
    out = capsys.readouterr().out
    assert _ids(out) == ["A.1"]
    assert "ask-gate: # SPRINT 2 — the sprint whose prose says ask-gate" in out


def _backlog_table_ids(text: str) -> list[str]:
    section = text.split("## Deferred backlog", 1)[1].split("<!-- LOOP:QUEUE start -->", 1)[0]
    return re.findall(r"^\| \*\*([A-Z0-9.]+)\*\* \|", section, flags=re.MULTILINE)


def _carry_forward_count(text: str) -> int:
    match = re.search(r"\*\*(\d+)\*\* tasks in the fence are flagged", text)
    assert match, "carry-forward note no longer states the flagged-task count"
    return int(match.group(1))


def test_real_roadmap_deferred_records_agree(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ROADMAP_FILE", str(REAL_ROADMAP))
    roadmap_cursor.main(["--audit-deferred"])
    audited = _ids(capsys.readouterr().out)
    text = REAL_ROADMAP.read_text(encoding="utf-8")

    assert sorted(_backlog_table_ids(text)) == sorted(audited)
    assert _carry_forward_count(text) == len(audited)
    assert set(audited) <= set(EXPECTED_FLAGS)
