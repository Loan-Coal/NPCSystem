#!/usr/bin/env python
"""
Module: check_ledger_ids
Layer: harness (repo-level dev tool)
Purpose: Detect reused DEC/ISSUE ids across the project ledgers and citations to ids that
         were never assigned, so an ambiguous cross-reference cannot be introduced silently.
Dependencies: stdlib only.
Used by: `make check-ledger-ids`, and tests/unit/scripts/test_check_ledger_ids.py.

Why this does NOT renumber (DEC-239, R4.5): every one of the four genuinely colliding DEC
ids is cited by name from live source -- demo_game/game_controller.py, demo_game/runners/
run_scenes.py, src/npc_engine/engines/proactive_dialogue/models.py and
src/npc_engine/graph/economy/currency_writer.py -- plus 38 document citations between them.
ISSUE-248 already settled the same question for the resolved archive: renumbering breaks
inbound references, which is worse than the ambiguity. So the contract is *document every
reuse*, not *eliminate it*: a collision is allowed only when a "Reused ids" note names it.

Why an outcome heading is not a declaration: DEC-116 is one decision written as a question
(`## DEC-116: ...`, 2026-06-13) plus its outcome (`## DEC-116 outcome (...): ...`,
2026-06-14). A regex that counts every heading reports it as a collision, which is how
R4.5's spec came to say "5 reused DEC ids" when the real number is 4. A declaration is
therefore an id followed immediately by a colon.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_ROOT = REPO_ROOT / "project-harness"

# Ledgers that DECLARE ids.
_DECISION_FILES = ("DECISIONS.md",)
_ISSUE_FILES = ("ISSUES.md", "archive/ISSUES_RESOLVED.md")
# Documents that CITE ids and must not name one that was never assigned.
_CITING_GLOBS = ("ROADMAP.md", "review-2026-08/*.md")

# A declaration: an optional [STATUS] tag, the id, then a colon. `## DEC-116 outcome (...)`
# has no colon straight after the id and is a continuation of its parent decision.
_DECL_TEMPLATE = r"^#{{1,6}}\s*(?:\[[A-Z]+\]\s*)?({prefix}-\d+):"
# The disambiguation note: bullets carrying a backticked id under a "Reused ids" heading.
_REUSE_HEADING_RE = re.compile(r"^#{1,6}\s+Reused ids\b.*$", re.MULTILINE)
_NEVER_HEADING_RE = re.compile(r"^#{1,6}\s+Never assigned\b.*$", re.MULTILINE)
_NEXT_H2_RE = re.compile(r"^#{1,2}\s", re.MULTILINE)
_BULLET_ID_RE = re.compile(r"^\s*[-*]\s+`((?:DEC|ISSUE)-\d+)`", re.MULTILINE)


def declarations(text: str, prefix: str) -> dict[str, list[int]]:
    """Map each declared id to the 1-based line numbers declaring it.

    Args:
        text: Full markdown text of one ledger file.
        prefix: Id family, "DEC" or "ISSUE".
    Returns:
        Dict of id -> line numbers where it is declared.
    """
    pattern = re.compile(_DECL_TEMPLATE.format(prefix=prefix), re.MULTILINE)
    found: dict[str, list[int]] = {}
    for match in pattern.finditer(text):
        line_no = text.count("\n", 0, match.start()) + 1
        found.setdefault(match.group(1), []).append(line_no)
    return found


def collisions(texts: dict[str, str], prefix: str) -> dict[str, list[str]]:
    """Return ids declared more than once, with every `file:line` that declares them.

    Args:
        texts: Map of display name -> file text.
        prefix: Id family, "DEC" or "ISSUE".
    Returns:
        Dict of id -> sorted "name:line" sites, for ids with two or more sites.
    """
    sites: dict[str, list[str]] = {}
    for name, text in texts.items():
        for ident, lines in declarations(text, prefix).items():
            sites.setdefault(ident, []).extend(f"{name}:{line}" for line in lines)
    return {i: sorted(s) for i, s in sites.items() if len(s) > 1}


def _sections(text: str, heading_re: re.Pattern[str]) -> list[str]:
    """Return the body of each section introduced by a heading matching heading_re."""
    out: list[str] = []
    for match in heading_re.finditer(text):
        rest = text[match.end():]
        nxt = _NEXT_H2_RE.search(rest)
        out.append(rest[: nxt.start()] if nxt else rest)
    return out


def documented_reuses(text: str) -> set[str]:
    """Return ids named by a bullet under a "Reused ids" heading."""
    return {i for body in _sections(text, _REUSE_HEADING_RE) for i in _BULLET_ID_RE.findall(body)}


def never_assigned(text: str) -> set[str]:
    """Return ids named by a bullet under a "Never assigned" heading."""
    return {i for body in _sections(text, _NEVER_HEADING_RE) for i in _BULLET_ID_RE.findall(body)}


def unresolved_citations(
    citing: dict[str, str], declared: set[str], prefix: str
) -> dict[str, list[str]]:
    """Return cited ids that are neither declared nor recorded as never assigned.

    Args:
        citing: Map of display name -> text of a document that cites ids.
        declared: Ids that resolve -- declared in a ledger or recorded never-assigned.
        prefix: Id family, "DEC" or "ISSUE".
    Returns:
        Dict of unresolved id -> sorted "name:line" citation sites.
    """
    pattern = re.compile(rf"\b({prefix}-\d+)\b")
    found: dict[str, list[str]] = {}
    for name, text in citing.items():
        for match in pattern.finditer(text):
            if match.group(1) in declared:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            found.setdefault(match.group(1), []).append(f"{name}:{line_no}")
    return {i: sorted(set(s)) for i, s in found.items()}


def _read(root: Path, names: tuple[str, ...]) -> dict[str, str]:
    """Read the named files under root, skipping any that do not exist."""
    out: dict[str, str] = {}
    for name in names:
        path = root / name
        if path.is_file():
            out[name] = path.read_text(encoding="utf-8")
    return out


def _read_glob(root: Path, globs: tuple[str, ...]) -> dict[str, str]:
    """Read every file matching the given globs under root."""
    out: dict[str, str] = {}
    for pattern in globs:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                key = str(path.relative_to(root)).replace("\\", "/")
                out[key] = path.read_text(encoding="utf-8")
    return out


def _report_collisions(found: dict[str, list[str]], documented: set[str], family: str) -> int:
    """Print undocumented collisions and return how many there are."""
    undocumented = {i: s for i, s in found.items() if i not in documented}
    for ident, sites in sorted(undocumented.items()):
        print(f"  UNDOCUMENTED REUSE {ident} declared at {', '.join(sites)}")
    print(f"  {family}: {len(found)} reused id(s), {len(undocumented)} undocumented")
    return len(undocumented)


def _report_citations(citing: dict[str, str], texts: dict[str, str], prefix: str,
                      never: set[str]) -> int:
    """Print citations to ids that were never declared and return how many there are."""
    declared = {i for t in texts.values() for i in declarations(t, prefix)} | never
    bad = 0
    for ident, sites in sorted(unresolved_citations(citing, declared, prefix).items()):
        print(f"  UNDECLARED CITATION {ident} cited at {', '.join(sites)}")
        bad += 1
    return bad


def main(root: Path | None = None) -> int:
    """Red when a reused id is undocumented or a cited id was never assigned.

    Args:
        root: Directory holding the ledgers; defaults to project-harness/.
    Returns:
        0 when every reuse is documented and every citation resolves, else 1.
    """
    base = HARNESS_ROOT if root is None else root
    dec_texts = _read(base, _DECISION_FILES)
    issue_texts = _read(base, _ISSUE_FILES)
    notes = "\n".join([*dec_texts.values(), *issue_texts.values()])
    documented, never = documented_reuses(notes), never_assigned(notes)

    print("check-ledger-ids:")
    bad = _report_collisions(collisions(dec_texts, "DEC"), documented, "DEC")
    bad += _report_collisions(collisions(issue_texts, "ISSUE"), documented, "ISSUE")

    citing = _read_glob(base, _CITING_GLOBS)
    bad += _report_citations(citing, dec_texts, "DEC", never)
    bad += _report_citations(citing, issue_texts, "ISSUE", never)

    if bad:
        print(f"  FAIL - {bad} unresolved item(s).")
        return 1
    print("  OK - every reused id is documented and every citation resolves.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ledger id collision detector (R4.5).")
    parser.add_argument("--root", type=Path, default=None, help="Ledger directory to scan.")
    sys.exit(main(root=parser.parse_args().root))
