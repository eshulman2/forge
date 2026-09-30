"""Tests for model tier value types, label parsers, and marker parsers.

These tests pin the contract that :mod:`forge.models.model_tier` must satisfy:

* :class:`ModelTier` is a string enum with exactly four members
  (LIGHT/STANDARD/HEAVY/CRITICAL) mapped to their lowercase values.
* ``tier_label`` / ``parse_tier_label`` round-trip through the
  ``forge:model-tier:`` prefix and ``parse_tier_label`` returns ``None`` for
  invalid or out-of-set values (BR-004, TS-002, TS-003).
* ``format_marker`` emits the exact ``forge.model-tier: {tier}`` line and
  ``parse_marker_line`` scans full body text line-by-line, returning the tier
  for a valid in-set marker and ``None`` for missing, unparseable, or
  out-of-set markers (Section 9.2).
"""

import dataclasses

import pytest

from forge.models.model_tier import (
    TIER_LABEL_PREFIX,
    TIER_MARKER_PREFIX,
    ModelTier,
    TierEstimate,
    format_marker,
    parse_marker_line,
    parse_tier_label,
    tier_label,
)

# ---------------------------------------------------------------------------
# ModelTier enum membership / values
# ---------------------------------------------------------------------------


def test_model_tier_members_and_values() -> None:
    """The enum exposes exactly the four expected members and values."""
    assert {tier.value for tier in ModelTier} == {
        "light",
        "standard",
        "heavy",
        "critical",
    }
    assert ModelTier.LIGHT.value == "light"
    assert ModelTier.STANDARD.value == "standard"
    assert ModelTier.HEAVY.value == "heavy"
    assert ModelTier.CRITICAL.value == "critical"


def test_model_tier_has_exactly_four_members() -> None:
    """No members beyond the four specified are defined."""
    assert len(list(ModelTier)) == 4


def test_model_tier_is_string_enum() -> None:
    """Members behave as plain strings (StrEnum)."""
    assert ModelTier.STANDARD == "standard"
    assert str(ModelTier.HEAVY) == "heavy"
    assert isinstance(ModelTier.LIGHT, str)
    assert ModelTier.CRITICAL == "critical"


def test_model_tier_membership() -> None:
    """Known values construct; unknown values raise ``ValueError``."""
    assert ModelTier("light") is ModelTier.LIGHT
    assert ModelTier("critical") is ModelTier.CRITICAL
    with pytest.raises(ValueError):
        ModelTier("gigantic")


# ---------------------------------------------------------------------------
# tier_label / parse_tier_label round-trip (TS-002)
# ---------------------------------------------------------------------------


def test_tier_label_prefix_constant() -> None:
    assert TIER_LABEL_PREFIX == "forge:model-tier:"


@pytest.mark.parametrize("tier", list(ModelTier))
def test_tier_label_round_trip(tier: ModelTier) -> None:
    """``parse_tier_label(tier_label(tier))`` returns the original tier."""
    label = tier_label(tier)
    assert isinstance(label, str)
    assert label.startswith(TIER_LABEL_PREFIX)
    assert parse_tier_label(label) is tier


def test_tier_label_values() -> None:
    """Labels are the prefixed tier value strings."""
    assert tier_label(ModelTier.LIGHT) == "forge:model-tier:light"
    assert tier_label(ModelTier.STANDARD) == "forge:model-tier:standard"
    assert tier_label(ModelTier.HEAVY) == "forge:model-tier:heavy"
    assert tier_label(ModelTier.CRITICAL) == "forge:model-tier:critical"


def test_parse_tier_label_accepts_all_members() -> None:
    for tier in ModelTier:
        assert parse_tier_label(f"{TIER_LABEL_PREFIX}{tier.value}") is tier


# ---------------------------------------------------------------------------
# parse_tier_label returns None for invalid / out-of-set values (TS-002, TS-003)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_label",
    [
        "",
        "   ",
        # Unprefixed bare values are not valid labels.
        "light",
        "standard",
        "critical",
        # Prefixed but out-of-set / wrong-case values.
        "forge:model-tier:medium",
        "forge:model-tier:LIGHT",
        "forge:model-tier:Standard",
        "forge:model-tier:heavyweight",
        "forge:model-tier:light ",
        "forge:model-tier:",
        # Wrong prefix.
        "model-tier:light",
        "forge:model_tier:light",
        # Marker prefix is not a label prefix.
        "forge.model-tier: light",
    ],
)
def test_parse_tier_label_returns_none_for_invalid_values(bad_label: str) -> None:
    assert parse_tier_label(bad_label) is None


# ---------------------------------------------------------------------------
# format_marker emits the exact line
# ---------------------------------------------------------------------------


def test_tier_marker_prefix_constant() -> None:
    assert TIER_MARKER_PREFIX == "forge.model-tier:"


@pytest.mark.parametrize(
    ("tier", "expected"),
    [
        (ModelTier.LIGHT, "forge.model-tier: light"),
        (ModelTier.STANDARD, "forge.model-tier: standard"),
        (ModelTier.HEAVY, "forge.model-tier: heavy"),
        (ModelTier.CRITICAL, "forge.model-tier: critical"),
    ],
)
def test_format_marker_exact_line(tier: ModelTier, expected: str) -> None:
    assert format_marker(tier) == expected


def test_format_marker_round_trips_through_parse_marker_line() -> None:
    for tier in ModelTier:
        assert parse_marker_line(format_marker(tier)) is tier


# ---------------------------------------------------------------------------
# parse_marker_line accepts valid markers (single line and multi-line body)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("forge.model-tier: light", ModelTier.LIGHT),
        ("forge.model-tier: standard", ModelTier.STANDARD),
        ("forge.model-tier: heavy", ModelTier.HEAVY),
        ("forge.model-tier: critical", ModelTier.CRITICAL),
    ],
)
def test_parse_marker_line_accepts_valid_markers(line: str, expected: ModelTier) -> None:
    assert parse_marker_line(line) is expected


def test_parse_marker_line_scans_multiline_body() -> None:
    """A valid marker is found even when embedded in a multi-line body."""
    body = "This ticket needs extra compute.\n\nforge.model-tier: heavy\n\nThanks!\n"
    assert parse_marker_line(body) is ModelTier.HEAVY


def test_parse_marker_line_returns_first_valid_marker() -> None:
    """The first valid in-set marker line wins."""
    body = "forge.model-tier: light\nforge.model-tier: heavy\n"
    assert parse_marker_line(body) is ModelTier.LIGHT


def test_parse_marker_line_skips_invalid_and_finds_later_valid() -> None:
    """Invalid marker lines are skipped in favour of a later valid one."""
    body = "forge.model-tier: medium\nforge.model-tier: critical\n"
    assert parse_marker_line(body) is ModelTier.CRITICAL


# ---------------------------------------------------------------------------
# parse_marker_line returns None for missing / unparseable / out-of-set (TS-003)
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
    ],
)
def test_parse_marker_line_returns_none_for_bad_text(bad_text: str) -> None:
    assert parse_marker_line(bad_text) is None


# ---------------------------------------------------------------------------
# TierEstimate value type
# ---------------------------------------------------------------------------


def test_tier_estimate_carries_tier_and_reasons() -> None:
    estimate = TierEstimate(tier=ModelTier.HEAVY, reasons=["large diff"])
    assert estimate.tier is ModelTier.HEAVY
    assert estimate.reasons == ["large diff"]


def test_tier_estimate_reasons_default_empty() -> None:
    estimate = TierEstimate(tier=ModelTier.LIGHT)
    assert estimate.reasons == []


def test_tier_estimate_is_frozen() -> None:
    estimate = TierEstimate(tier=ModelTier.STANDARD)
    with pytest.raises(dataclasses.FrozenInstanceError):
        estimate.tier = ModelTier.HEAVY  # type: ignore[misc]
