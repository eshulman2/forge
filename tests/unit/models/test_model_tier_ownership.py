"""RED-phase tests for tier ownership resolution and the single-tier invariant.

These tests are authored *before* ``forge.models.model_tier_ownership`` exists
(TDD RED step, AISOS-2469).  Until the ownership module is implemented, this
suite fails at import / collection time with ``ModuleNotFoundError``.

The contract pinned here (which the GREEN implementation must satisfy):

* ``parse_latest_tier_marker(text) -> ModelTier | None`` scans a full body text
  line-by-line and returns the tier of the **last** valid in-set marker
  (newest-last / latest-wins), or ``None`` when no valid marker is present.
  This is deliberately the opposite selection policy from
  :func:`forge.models.model_tier.parse_marker_line`, which returns the *first*
  valid marker (TS-006, TS-007, TS-008).
* ``resolve_tier_ownership(marker, label) -> TierOwnership`` decides the owning
  tier given the marker tier parsed from the body and the tier of the current
  label (each ``ModelTier | None``).  It covers the three input combinations
  (TS-009):
    - no marker present -> the current label (if any) is retained;
    - marker present and differs from the label -> the marker takes ownership
      and the label must be reconciled;
    - marker present and equals the label -> already in sync, nothing changes.
* ``enforce_single_tier(current_labels, desired_tier) -> LabelChange`` computes
  the label adds / removes required so that, once applied, **exactly one** tier
  label remains — the one for ``desired_tier`` — regardless of whether the
  starting set had zero, one, or multiple tier labels (TS-016).  Non-tier
  labels are never touched.
"""

import dataclasses

import pytest

from forge.models.model_tier import (
    ModelTier,
    format_marker,
    tier_label,
)
from forge.models.model_tier_ownership import (
    LabelChange,
    TierOwnership,
    enforce_single_tier,
    parse_latest_tier_marker,
    resolve_tier_ownership,
)

# ---------------------------------------------------------------------------
# parse_latest_tier_marker — newest-last selection (TS-006, TS-007)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier", list(ModelTier))
def test_parse_latest_tier_marker_single_marker(tier: ModelTier) -> None:
    """A single valid marker line resolves to its tier."""
    assert parse_latest_tier_marker(format_marker(tier)) is tier


def test_parse_latest_tier_marker_scans_multiline_body() -> None:
    """A lone valid marker embedded in a multi-line body is found."""
    body = "This ticket needs extra compute.\n\nforge.model-tier: heavy\n\nThanks!\n"
    assert parse_latest_tier_marker(body) is ModelTier.HEAVY


def test_parse_latest_tier_marker_returns_last_valid_marker() -> None:
    """When several valid markers exist, the LAST one wins (TS-006)."""
    body = "forge.model-tier: light\nforge.model-tier: heavy\n"
    assert parse_latest_tier_marker(body) is ModelTier.HEAVY


def test_parse_latest_tier_marker_last_wins_across_all_tiers() -> None:
    """The final valid marker determines the result regardless of order."""
    body = (
        "forge.model-tier: heavy\n"
        "forge.model-tier: light\n"
        "forge.model-tier: standard\n"
        "forge.model-tier: critical\n"
    )
    assert parse_latest_tier_marker(body) is ModelTier.CRITICAL


def test_parse_latest_tier_marker_differs_from_first_wins() -> None:
    """Latest-wins is genuinely distinct from first-wins for the same body."""
    from forge.models.model_tier import parse_marker_line

    body = "forge.model-tier: light\nforge.model-tier: critical\n"
    assert parse_marker_line(body) is ModelTier.LIGHT
    assert parse_latest_tier_marker(body) is ModelTier.CRITICAL


def test_parse_latest_tier_marker_skips_trailing_invalid_marker() -> None:
    """A later *invalid* marker does not override an earlier valid one (TS-007)."""
    body = "forge.model-tier: heavy\nforge.model-tier: medium\n"
    assert parse_latest_tier_marker(body) is ModelTier.HEAVY


def test_parse_latest_tier_marker_last_valid_among_invalid() -> None:
    """Only valid in-set markers are considered; the last valid one wins."""
    body = (
        "forge.model-tier: medium\n"
        "forge.model-tier: light\n"
        "forge.model-tier: LIGHT\n"
        "forge.model-tier: bogus\n"
    )
    assert parse_latest_tier_marker(body) is ModelTier.LIGHT


# ---------------------------------------------------------------------------
# parse_latest_tier_marker — None when no valid marker is present (TS-008)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_text",
    [
        "",
        "   ",
        "light",
        "forge.model-tier:",
        "forge.model-tier: ",
        "forge.model-tier: medium",
        "forge.model-tier: LIGHT",
        "model-tier: light",
        "forge.model_tier: light",
        "some other line",
        "forge.model-tier light",
        "no marker here\njust plain text\n",
        # Multiple *invalid* markers still yield None.
        "forge.model-tier: medium\nforge.model-tier: bogus\n",
    ],
)
def test_parse_latest_tier_marker_returns_none_when_no_valid_marker(
    bad_text: str,
) -> None:
    """Missing / unparseable / out-of-set markers all resolve to ``None``."""
    assert parse_latest_tier_marker(bad_text) is None


# ---------------------------------------------------------------------------
# resolve_tier_ownership — three input combinations (TS-009)
# ---------------------------------------------------------------------------


def test_resolve_ownership_no_marker_keeps_label() -> None:
    """No marker present: the current label retains ownership (TS-009)."""
    ownership = resolve_tier_ownership(marker=None, label=ModelTier.STANDARD)
    assert isinstance(ownership, TierOwnership)
    assert ownership.tier is ModelTier.STANDARD
    assert ownership.changed is False


def test_resolve_ownership_no_marker_no_label() -> None:
    """No marker and no label: nothing is owned and nothing changes."""
    ownership = resolve_tier_ownership(marker=None, label=None)
    assert ownership.tier is None
    assert ownership.changed is False


def test_resolve_ownership_marker_differs_from_label() -> None:
    """Marker present and different: the marker takes ownership (TS-009)."""
    ownership = resolve_tier_ownership(marker=ModelTier.CRITICAL, label=ModelTier.LIGHT)
    assert ownership.tier is ModelTier.CRITICAL
    assert ownership.changed is True


def test_resolve_ownership_marker_present_no_label() -> None:
    """Marker present with no existing label: the marker takes ownership."""
    ownership = resolve_tier_ownership(marker=ModelTier.HEAVY, label=None)
    assert ownership.tier is ModelTier.HEAVY
    assert ownership.changed is True


def test_resolve_ownership_marker_equals_label() -> None:
    """Marker equals label: already in sync, nothing changes (TS-009)."""
    ownership = resolve_tier_ownership(marker=ModelTier.STANDARD, label=ModelTier.STANDARD)
    assert ownership.tier is ModelTier.STANDARD
    assert ownership.changed is False


@pytest.mark.parametrize("tier", list(ModelTier))
def test_resolve_ownership_marker_equals_label_all_tiers(tier: ModelTier) -> None:
    """For every tier, marker==label is a no-op sync."""
    ownership = resolve_tier_ownership(marker=tier, label=tier)
    assert ownership.tier is tier
    assert ownership.changed is False


# ---------------------------------------------------------------------------
# enforce_single_tier — exactly one tier label remains (TS-016)
# ---------------------------------------------------------------------------

# Some non-tier labels that must be preserved untouched by enforcement.
OTHER_LABELS = ["forge:managed", "team-frontend", "priority-high"]


def _apply(labels: list[str], change: LabelChange) -> set[str]:
    """Apply a :class:`LabelChange` to ``labels`` and return the resulting set."""
    result = set(labels)
    result.difference_update(change.remove)
    result.update(change.add)
    return result


def _tier_labels(labels: set[str]) -> set[str]:
    """Return only the tier labels within ``labels``."""
    return {tier_label(t) for t in ModelTier} & labels


def test_enforce_single_tier_from_zero_tier_labels() -> None:
    """Zero pre-existing tier labels: the desired label is added (TS-016)."""
    current = list(OTHER_LABELS)
    change = enforce_single_tier(current, ModelTier.HEAVY)
    assert isinstance(change, LabelChange)
    result = _apply(current, change)
    assert _tier_labels(result) == {tier_label(ModelTier.HEAVY)}
    # Non-tier labels are preserved.
    assert set(OTHER_LABELS) <= result


def test_enforce_single_tier_from_one_matching_label_is_noop() -> None:
    """One pre-existing tier label equal to desired: no changes (TS-016)."""
    current = [*OTHER_LABELS, tier_label(ModelTier.STANDARD)]
    change = enforce_single_tier(current, ModelTier.STANDARD)
    assert list(change.add) == []
    assert list(change.remove) == []
    result = _apply(current, change)
    assert _tier_labels(result) == {tier_label(ModelTier.STANDARD)}


def test_enforce_single_tier_from_one_different_label() -> None:
    """One pre-existing tier label different from desired: swap it (TS-016)."""
    current = [*OTHER_LABELS, tier_label(ModelTier.LIGHT)]
    change = enforce_single_tier(current, ModelTier.CRITICAL)
    result = _apply(current, change)
    assert _tier_labels(result) == {tier_label(ModelTier.CRITICAL)}
    assert tier_label(ModelTier.LIGHT) not in result


def test_enforce_single_tier_from_multiple_labels() -> None:
    """Multiple pre-existing tier labels collapse to exactly one (TS-016)."""
    current = [
        *OTHER_LABELS,
        tier_label(ModelTier.LIGHT),
        tier_label(ModelTier.STANDARD),
        tier_label(ModelTier.HEAVY),
        tier_label(ModelTier.CRITICAL),
    ]
    change = enforce_single_tier(current, ModelTier.HEAVY)
    result = _apply(current, change)
    assert _tier_labels(result) == {tier_label(ModelTier.HEAVY)}
    # Every other tier label was removed.
    assert tier_label(ModelTier.LIGHT) not in result
    assert tier_label(ModelTier.STANDARD) not in result
    assert tier_label(ModelTier.CRITICAL) not in result


def test_enforce_single_tier_preserves_non_tier_labels_always() -> None:
    """Non-tier labels are never added or removed by enforcement."""
    current = [
        *OTHER_LABELS,
        tier_label(ModelTier.LIGHT),
        tier_label(ModelTier.HEAVY),
    ]
    change = enforce_single_tier(current, ModelTier.STANDARD)
    # No non-tier label appears in either side of the change.
    touched = set(change.add) | set(change.remove)
    assert touched.isdisjoint(set(OTHER_LABELS))
    result = _apply(current, change)
    assert set(OTHER_LABELS) <= result


@pytest.mark.parametrize("desired", list(ModelTier))
def test_enforce_single_tier_result_always_exactly_one(desired: ModelTier) -> None:
    """For every desired tier, the applied result has exactly one tier label."""
    current = [
        *OTHER_LABELS,
        tier_label(ModelTier.LIGHT),
        tier_label(ModelTier.STANDARD),
        tier_label(ModelTier.HEAVY),
        tier_label(ModelTier.CRITICAL),
    ]
    change = enforce_single_tier(current, desired)
    result = _apply(current, change)
    remaining_tiers = _tier_labels(result)
    assert len(remaining_tiers) == 1
    assert remaining_tiers == {tier_label(desired)}


def test_enforce_single_tier_does_not_mutate_input() -> None:
    """``enforce_single_tier`` must not mutate the caller's label list."""
    current = [*OTHER_LABELS, tier_label(ModelTier.LIGHT)]
    snapshot = list(current)
    enforce_single_tier(current, ModelTier.HEAVY)
    assert current == snapshot


# ---------------------------------------------------------------------------
# Value-type shape contracts
# ---------------------------------------------------------------------------


def test_tier_ownership_is_frozen() -> None:
    """:class:`TierOwnership` is an immutable value type."""
    ownership = resolve_tier_ownership(marker=ModelTier.HEAVY, label=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ownership.tier = ModelTier.LIGHT  # type: ignore[misc]


def test_label_change_is_frozen() -> None:
    """:class:`LabelChange` is an immutable value type."""
    change = enforce_single_tier([], ModelTier.LIGHT)
    with pytest.raises(dataclasses.FrozenInstanceError):
        change.add = []  # type: ignore[misc]
