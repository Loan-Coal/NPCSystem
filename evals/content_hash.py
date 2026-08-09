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

    Used to fingerprint the (output_text, criteria) pair a human labelled. A
    changed fingerprint means the human judged different content, which must
    invalidate — or at minimum flag — the stored verdict.

    Args:
        text: The text to fingerprint. Hashed verbatim; no normalisation is
            applied, because whitespace and punctuation changes can alter what
            a labeller would have decided.
    Returns:
        Lowercase hex digest.
    """
    return hashlib.sha256(text.encode(_ENCODING)).hexdigest()
