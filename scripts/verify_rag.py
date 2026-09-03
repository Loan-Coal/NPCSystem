#!/usr/bin/env python
"""
Module: verify_rag
Layer: scripts (dev tooling)
Purpose: Exercise the real embedding path end to end — load the sentence-transformers
         model and assert it returns a normalized vector of the expected width.
Does NOT: reach Neo4j, call an LLM, or run in `make check`.
Dependencies: argparse, math, sys, pathlib, npc_engine.retrieval.embedding
Dependencies injected: None.
Used by: make verify-rag

Deliberately NOT a pytest test. `make check` runs `pytest tests/`, and CI has neither a
GPU nor torch installed, so a test here would red CI; guarding it with
`skipif torch is None` would make it pass by skipping, which is worse than not having it
— the failure mode this repo calls "green because nobody looked". This is an explicit,
human-run verification with a printed result instead (R5.2, CR-L16-04).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Sequence

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path[:1]:
    sys.path.insert(0, str(_SRC_ROOT))

DEFAULT_MODEL = "all-MiniLM-L6-v2"
EXPECTED_DIM = 384
NORM_TOLERANCE = 1e-5
SAMPLE_TEXT = "the innkeeper remembers your last visit"


def main(argv: Sequence[str] | None = None) -> int:
    """Load the encoder and report device, dimension and vector norm.

    Returns:
        0 when the embedding path works; 1 when a dependency is missing or the
        vector is the wrong shape.
    """
    parser = argparse.ArgumentParser(description="Verify the real embedding path (R5.2).")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)

    try:
        import torch
    except ImportError:
        print("verify-rag: torch is not installed. Install it for your GPU, e.g.")
        print("  pip install torch --index-url https://download.pytorch.org/whl/cu128")
        return 1

    from npc_engine.retrieval.embedding.sentence_encoder import embed, get_encoder

    encoder = get_encoder(args.model)
    vector = embed(SAMPLE_TEXT, args.model)
    norm = math.sqrt(sum(value * value for value in vector))

    print(f"verify-rag: torch {torch.__version__}, cuda={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        major, minor = torch.cuda.get_device_capability(0)
        print(f"verify-rag: {torch.cuda.get_device_name(0)} (sm_{major}{minor})")
    print(f"verify-rag: model {args.model} on {encoder.device}")
    print(f"verify-rag: dim={len(vector)} norm={norm:.6f}")

    if len(vector) != EXPECTED_DIM:
        print(f"verify-rag: FAIL - expected dim {EXPECTED_DIM}, got {len(vector)}")
        return 1
    if abs(norm - 1.0) > NORM_TOLERANCE:
        print(f"verify-rag: FAIL - vector is not normalized (norm {norm})")
        return 1
    print("verify-rag: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
