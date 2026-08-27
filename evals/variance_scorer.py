"""
Module: variance_scorer
Layer: evals (eval harness — standalone, outside the npc_engine layer model)
Purpose: EVAL-P25.4. Score how much a set of NPC replies differs from one another, so the
         maintainer's stated goal — "replies should be incredibly varied based on context
         and situation" — becomes a measured quantity rather than an impression.
Dependencies: dataclasses, itertools, re, statistics, typing. Stdlib only, by design.
Used by: tests/unit/evals/test_variance_scorer.py; EVAL-P26 contextual-variance cases
         (`case_var_*`); `make variance-score`.
Does NOT: call the engine, call an LLM, read the graph, touch the filesystem or network.
         Every function here is pure over the strings it is handed.

Why this metric exists at all
-----------------------------
Every LLM-judged scorer in this repo pays a reliability tax: two of four are suppressed
by docs/SCORER_TRUST_POLICY.md (refusal_judge kappa 0.247, affirms_judge 0.530) and
cannot be quoted. A deterministic scorer has **kappa = 1.0 by construction** — it agrees
with itself perfectly — so its observed MDE is its true MDE and it can resolve an effect
today, with no labels and no judge repair.

Why Jaccard distance over content tokens
----------------------------------------
The measure is `1 - |A ∩ B| / |A ∪ B|` over the sets of normalized word tokens in two
replies. It was chosen over the three alternatives considered:

* **Embedding cosine** (`src/npc_engine/retrieval/embedding/sentence_encoder.py`) would be
  the semantically richer measure, and it already exists in this repo. It is rejected here
  because it is not free of I/O: `get_encoder` imports `sentence_transformers` and loads
  an ~80 MB model from disk or the network on first call. This module's contract is a pure
  function over response strings — a scorer that can fail because a model download failed
  is a scorer whose zero readings are ambiguous. `evals/` also does not import `src/`.
* **TF-IDF cosine** needs an IDF vector, which is either a corpus dependency (the score
  then changes when the corpus does, so two runs are not comparable) or estimated from the
  handful of replies being scored (unstable at n=5). Both are free parameters.
* **Normalized edit distance** is dominated by length and word order, which are surface
  properties. Two replies conveying entirely different facts at the same length can score
  as similar.

Jaccard is bounded [0, 1], symmetric, order-independent, and carries **no parameter to
calibrate** — which is the specific defect DEC-181 rejected an option for introducing.

Why there is no stopword list
-----------------------------
A stopword list would be exactly such a parameter: change the list, change every score.
It is unnecessary because the load-bearing quantity is the **contrast** (`contrast()`),
not the absolute number. Function-word overlap is a floor present in the control group
and the treatment group alike, so it largely cancels in the delta.

The known limitation, stated plainly
------------------------------------
This is a lexical measure. A reply that says the same thing in different words reads as
varied when it is not (false high), and two replies about different facts that share
vocabulary read as similar when they are not (false low). It is used for the failure mode
it does detect reliably: a state-blind engine emitting near-identical text for every
context scores near 0, and no rewording of the metric's inputs hides that.

Why the threshold is directional only
-------------------------------------
`DIRECTIONAL_DELTA_THRESHOLD` is 0.0. No measured run yet exists from which to derive a
magnitude, and inventing one now would be an uncalibrated free parameter. The gate
therefore asserts only the direction — differing states must produce more variety than
resampling one fixed state — and the magnitude threshold is deferred to EVAL-P26, when
there is a measurement to calibrate against.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: A pair needs two members. One reply is unmeasured, not invariant.
MIN_RESPONSES_FOR_PAIRWISE: int = 2

#: The delta a contextual-variance comparison must exceed. Deliberately directional
#: only — see "Why the threshold is directional only" in the module docstring.
DIRECTIONAL_DELTA_THRESHOLD: float = 0.0

#: Maximum distance. Assigned when the union of two token sets is empty (both replies
#: are empty or punctuation-only): an engine that said nothing demonstrated no variance,
#: so the pair is scored as maximally dissimilar rather than as identical. Scoring 0/0
#: as "identical" would let a silent engine read as a consistent one.
_UNMEASURABLE_PAIR_DISTANCE: float = 1.0

#: Word characters only; everything else is a separator. Case is folded before matching.
_WORD_RE: re.Pattern[str] = re.compile(r"[\w']+")


class InsufficientResponsesError(ValueError):
    """Raised when fewer than MIN_RESPONSES_FOR_PAIRWISE responses are supplied.

    A single reply yields no pair. Returning 0.0 for it would report "no variance" for
    a set that was never measured — the same confusion `has_variance` guards against in
    scripts/check_base_rate.py.
    """


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VarianceScore:
    """Pairwise dissimilarity over one group of replies.

    Attributes:
        n_responses: Replies scored.
        n_pairs: Unordered pairs compared, `n_responses * (n_responses - 1) / 2`.
        mean_dissimilarity: Mean pairwise Jaccard distance, in [0, 1]. The headline.
        min_dissimilarity: The most similar pair — the closest the group came to
            emitting one answer twice.
        max_dissimilarity: The most dissimilar pair.
    """

    n_responses: int
    n_pairs: int
    mean_dissimilarity: float
    min_dissimilarity: float
    max_dissimilarity: float


@dataclass(frozen=True)
class VarianceContrast:
    """A treatment group's variance measured against a matched control group.

    Attributes:
        control: Same NPC, same state, resampled — the variety sampling alone produces.
        treatment: One player_message, NPCs in differing states — the quantity of
            interest.
        delta: `treatment.mean_dissimilarity - control.mean_dissimilarity`. This, not
            the treatment score alone, is what attributes variety to context.
        threshold: The delta the contrast was required to exceed.
    """

    control: VarianceScore
    treatment: VarianceScore
    delta: float
    threshold: float

    @property
    def meets_directional_gate(self) -> bool:
        """True when differing states produced strictly more variety than resampling."""
        return self.delta > self.threshold


# ---------------------------------------------------------------------------
# The measure
# ---------------------------------------------------------------------------


def normalize_tokens(text: str) -> frozenset[str]:
    """Split a reply into its set of case-folded word tokens.

    Punctuation and case are surface form, not content, so both are discarded. No
    stopword list is applied — see the module docstring for why.

    Args:
        text: A reply.
    Returns:
        The frozen set of distinct word tokens; empty for an empty or symbol-only reply.
    """
    return frozenset(match.group(0).lower() for match in _WORD_RE.finditer(text))


def jaccard_distance(left: str, right: str) -> float:
    """Jaccard distance between two replies' content-token sets.

    Args:
        left: One reply.
        right: The other reply.
    Returns:
        `1 - |A ∩ B| / |A ∪ B|` in [0, 1]; 0.0 for identical token sets, 1.0 for
        disjoint ones, and 1.0 when both sets are empty (see
        `_UNMEASURABLE_PAIR_DISTANCE`).
    """
    a, b = normalize_tokens(left), normalize_tokens(right)
    union = a | b
    if not union:
        return _UNMEASURABLE_PAIR_DISTANCE
    return 1.0 - len(a & b) / len(union)


def pairwise_dissimilarity(responses: Sequence[str]) -> VarianceScore:
    """Score how much a group of replies differs from one another.

    Args:
        responses: Two or more replies, typically one player_message answered by N NPCs
            in differing states.
    Returns:
        The VarianceScore over every unordered pair.
    Raises:
        InsufficientResponsesError: When fewer than MIN_RESPONSES_FOR_PAIRWISE supplied.
    """
    if len(responses) < MIN_RESPONSES_FOR_PAIRWISE:
        raise InsufficientResponsesError(
            f"pairwise dissimilarity needs at least {MIN_RESPONSES_FOR_PAIRWISE} responses; "
            f"got {len(responses)} — one reply is unmeasured, not invariant"
        )
    distances = [jaccard_distance(a, b) for a, b in combinations(responses, 2)]
    return VarianceScore(
        n_responses=len(responses),
        n_pairs=len(distances),
        mean_dissimilarity=statistics.fmean(distances),
        min_dissimilarity=min(distances),
        max_dissimilarity=max(distances),
    )


def contrast(
    *,
    control: Sequence[str],
    treatment: Sequence[str],
    threshold: float = DIRECTIONAL_DELTA_THRESHOLD,
) -> VarianceContrast:
    """Measure a treatment group's variety against a matched control group.

    The control isolates the confound: an engine sampling at non-zero temperature
    produces lexical variety whether or not it reads context at all. Scoring the
    treatment group alone would credit that noise as contextual sensitivity. Scoring
    both and reporting the delta is what makes the number attributable.

    Args:
        control: Replies from one NPC in one fixed state, resampled — the sampling floor.
        treatment: Replies to the same player_message from NPCs in differing states.
        threshold: The delta the contrast must exceed.
    Returns:
        The VarianceContrast; `meets_directional_gate` carries the verdict.
    Raises:
        InsufficientResponsesError: When either group has fewer than
            MIN_RESPONSES_FOR_PAIRWISE replies.
    """
    control_score = pairwise_dissimilarity(control)
    treatment_score = pairwise_dissimilarity(treatment)
    return VarianceContrast(
        control=control_score,
        treatment=treatment_score,
        delta=treatment_score.mean_dissimilarity - control_score.mean_dissimilarity,
        threshold=threshold,
    )
