"""
Module: content_hash
Layer: evals (eval harness — not part of src/)
Purpose: Content-addressing helper — stable SHA-256 of a text field, used to bind
         a human calibration judgment to the exact output_text and criteria the
         human read, so later drift is detectable rather than silent.
Dependencies: hashlib (stdlib)
Used by: calibration_records, label_import, label_merge, label_verify
"""

from __future__ import annotations

import hashlib

_ENCODING: str = "utf-8"


def sha256_text(text: str) -> str:
    """Return the hex SHA-256 of a text value.

    Used to fingerprint both `output_text` and `criteria` on a CalibrationLabel
    row, but the two hashes now play different roles (EVAL-P20.3b / DEC-181):
    `criteria_sha256` is what `label_merge._has_drifted` reads to decide
    whether a stored `human_verdict` is still trusted — a `criteria` change
    invalidates the verdict, an `output_text` change does not. `output_sha256`
    is still computed and stored on every row as an audit/evidence trail (what
    exact text a verdict was originally recorded against), it is simply no
    longer consulted for trust. See docs/EVAL_METHODOLOGY.md §3 for why.

    Args:
        text: The text to fingerprint. Hashed verbatim; no normalisation is
            applied, because whitespace and punctuation changes can alter what
            a labeller would have decided.
    Returns:
        Lowercase hex digest.
    """
    return hashlib.sha256(text.encode(_ENCODING)).hexdigest()
