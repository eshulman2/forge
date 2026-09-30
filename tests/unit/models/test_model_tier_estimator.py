"""RED-phase tests for the heuristic model-tier estimator.

These tests are authored *before* ``forge.models.model_tier_estimator`` exists
(TDD RED step, AISOS-2467).  Until the estimator module is implemented, this
suite fails at import/collection time with ``ModuleNotFoundError``.

The contract pinned here (which the GREEN implementation must satisfy):

* ``estimate_tier(text: str) -> TierEstimate`` is a pure, deterministic function
  that inspects the free-text description of a unit of work and returns a
  :class:`~forge.models.model_tier.TierEstimate` — a chosen
  :class:`~forge.models.model_tier.ModelTier` plus a **non-empty** list of
  human-readable ``reasons`` explaining the decision.
* Critical signals (e.g. security/incident/data-loss keywords) escalate to
  ``ModelTier.CRITICAL`` (TS-020).
* Heavy signals — architectural/complexity keywords such as *refactor*,
  *migration*, *concurrency*, *distributed*, or a long description — escalate to
  ``ModelTier.HEAVY`` (TS-021, TS-024).
* Small / isolated / UI-copy signals paired with a short description demote to
  ``ModelTier.LIGHT`` and record the demotion in ``reasons`` (TS-022).
* Every estimate — including the baseline (no strong signal) and empty /
  whitespace-only input — yields a **non-empty** ``reasons`` list (TS-023).
* ``estimate_tier`` is deterministic: repeated calls on the same input return an
  identical tier and identical reasons (TS-019).
"""

import pytest

from forge.models.model_tier import ModelTier, TierEstimate
from forge.models.model_tier_estimator import estimate_tier

# ---------------------------------------------------------------------------
# Sample inputs grouped by the tier they are expected to produce.
# ---------------------------------------------------------------------------

# TS-020 — critical signals escalate to CRITICAL.
CRITICAL_TEXTS = [
    "Security vulnerability allows authentication bypass in the login flow.",
    "Production incident: customer data loss during the nightly export job.",
    "Critical outage — the payment gateway is returning 500s for all users.",
    "Data corruption detected in the billing ledger; PII may be exposed.",
]

# TS-021 / TS-024 — heavy signals (complexity keywords + long description).
HEAVY_TEXTS = [
    "Refactor the authentication subsystem to support pluggable providers.",
    "Migrate the event queue from Redis Streams to a distributed log.",
    "Redesign the concurrency model to remove the global scheduler lock.",
    "Introduce a distributed caching layer with cross-region replication.",
    # TS-024 — a long description alone is a heavy signal.
    (
        "We need to overhaul the ingestion pipeline end to end. "
        "The current implementation buffers events in memory before writing "
        "them to Redis, which does not scale beyond a single worker. This "
        "work spans the queue producer, the consumer group topology, the "
        "checkpointing logic, the retry/backoff policy, the dead-letter "
        "handling, the metrics exporters, and the operator runbook. Each of "
        "these has downstream consumers that must be kept backwards "
        "compatible while the migration is rolled out region by region."
    ),
]

# TS-022 — small / isolated / UI-copy signals + short description demote to LIGHT.
LIGHT_TEXTS = [
    "Fix typo in the settings page heading.",
    "Update the tooltip copy on the export button.",
    "Change the placeholder text in the search box.",
    "Small isolated tweak: rename a label in the footer.",
]

# TS-023 — baseline text with no strong signal in either direction.
BASELINE_TEXTS = [
    "Add a new field to the user profile form.",
    "Wire up the existing endpoint to the reporting dashboard.",
]

# TS-023 — empty / whitespace-only input must still yield reasons.
EMPTY_TEXTS = [
    "",
    "   ",
    "\n\t  \n",
]

# The full corpus is reused by the determinism test (TS-019).
ALL_TEXTS = CRITICAL_TEXTS + HEAVY_TEXTS + LIGHT_TEXTS + BASELINE_TEXTS + EMPTY_TEXTS


# ---------------------------------------------------------------------------
# Return-type contract
# ---------------------------------------------------------------------------


def test_estimate_tier_returns_tier_estimate() -> None:
    """``estimate_tier`` returns a :class:`TierEstimate` with the right shape."""
    estimate = estimate_tier("Add a new field to the user profile form.")
    assert isinstance(estimate, TierEstimate)
    assert isinstance(estimate.tier, ModelTier)
    assert isinstance(estimate.reasons, list)


# ---------------------------------------------------------------------------
# TS-020 — critical signals escalate to CRITICAL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", CRITICAL_TEXTS)
def test_critical_signals_escalate_to_critical(text: str) -> None:
    """Security / incident / data-loss signals yield the CRITICAL tier."""
    estimate = estimate_tier(text)
    assert estimate.tier is ModelTier.CRITICAL
    assert estimate.reasons, "critical estimate must record supporting reasons"


# ---------------------------------------------------------------------------
# TS-021 / TS-024 — heavy signals escalate to HEAVY
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", HEAVY_TEXTS)
def test_heavy_signals_escalate_to_heavy(text: str) -> None:
    """Complexity keywords or a long description yield the HEAVY tier."""
    estimate = estimate_tier(text)
    assert estimate.tier is ModelTier.HEAVY
    assert estimate.reasons, "heavy estimate must record supporting reasons"


# ---------------------------------------------------------------------------
# TS-022 — small / isolated / UI-copy signals demote to LIGHT with reasons
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", LIGHT_TEXTS)
def test_light_signals_demote_to_light_with_reasons(text: str) -> None:
    """Small / isolated / UI-copy + short description demote to LIGHT.

    The demotion must be explained: ``reasons`` is non-empty for the LIGHT
    outcome (TS-022, TS-023).
    """
    estimate = estimate_tier(text)
    assert estimate.tier is ModelTier.LIGHT
    assert estimate.reasons, "light demotion must record a demotion reason"


# ---------------------------------------------------------------------------
# TS-023 — every estimate carries non-empty reasons (baseline + empty text)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", BASELINE_TEXTS + EMPTY_TEXTS)
def test_baseline_and_empty_text_yield_non_empty_reasons(text: str) -> None:
    """Baseline and empty / whitespace-only input still produce reasons."""
    estimate = estimate_tier(text)
    assert isinstance(estimate.tier, ModelTier)
    assert estimate.reasons, "every estimate must carry at least one reason"
    assert all(isinstance(reason, str) and reason for reason in estimate.reasons)


# ---------------------------------------------------------------------------
# TS-019 — determinism: repeated calls return identical tier + reasons
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ALL_TEXTS)
def test_estimate_tier_is_deterministic(text: str) -> None:
    """Two calls on the same input return an identical tier and reasons."""
    first = estimate_tier(text)
    second = estimate_tier(text)
    assert first.tier is second.tier
    assert first.reasons == second.reasons
